"""Generate the burned-in caption track (SRT) for the Football AI Platform demo
video (reproducible copy).

Captions are split into short readable chunks per scene, timed proportionally
by word count across each scene's real narration audio duration, and offset
by each scene's actual position in the final concatenated timeline (title
card + 10 scenes + closing card).

Run with (from repo root):
    python demo/az-demo-video/scripts/generate_srt.py --pace fast
    python demo/az-demo-video/scripts/generate_srt.py --pace relaxed
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SCRIPT_DIR = Path(__file__).resolve().parent
DEMO_DIR = SCRIPT_DIR.parent
BUILD = DEMO_DIR / "build"

TITLE_DURATION = 4.0
CLOSING_DURATION = 6.0


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run([FFMPEG, "-i", str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            hms = line.split(",")[0].split("Duration:")[1].strip()
            h, m, s = hms.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"no duration for {path}")


def chunk_text(text: str, max_words: int = 11) -> list[str]:
    parts = re.split(r'(?<=[.,:;])\s+', text.strip())
    chunks, current, count = [], [], 0
    for part in parts:
        words = part.split()
        if count + len(words) > max_words and current:
            chunks.append(" ".join(current))
            current, count = [], 0
        current.extend(words)
        count += len(words)
    if current:
        chunks.append(" ".join(current))
    return chunks


def srt_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pace", choices=["fast", "relaxed"], default="fast")
    ap.add_argument("--scenes-file", type=Path, default=SCRIPT_DIR / "scenes.json")
    ap.add_argument("--audio-key", default=None)
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--title", default="Football Intelligence Platform \u2014 From match video to validated football intelligence")
    ap.add_argument("--closing", default="Xebia Netherlands \u2014 scalable AI & engineering capacity for a next phase")
    args = ap.parse_args()
    audio_dir = BUILD / "audio" / (args.audio_key or args.pace)

    scenes = json.loads(args.scenes_file.read_text(encoding="utf-8"))
    entries = [(0.3, TITLE_DURATION - 0.3, args.title)]

    cursor = TITLE_DURATION
    for scene in scenes:
        wav = audio_dir / f"scene{scene['id']:02d}.wav"
        dur = ffprobe_duration(wav)
        chunks = chunk_text(scene["text"], max_words=11)
        total_words = sum(len(c.split()) for c in chunks)
        t = cursor
        for chunk in chunks:
            words = len(chunk.split())
            chunk_dur = dur * (words / total_words)
            entries.append((t, t + chunk_dur, chunk))
            t += chunk_dur
        cursor += dur

    entries.append((cursor + 0.3, cursor + CLOSING_DURATION - 0.3, args.closing))
    cursor += CLOSING_DURATION

    suffix = "" if args.pace == "fast" else f"_{args.pace}"
    srt_path = args.output or DEMO_DIR / f"Football_AI_Platform_Demo{suffix}.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, (start, end, text) in enumerate(entries, start=1):
            f.write(f"{i}\n{srt_time(start)} --> {srt_time(end)}\n{text}\n\n")

    print(f"Wrote {len(entries)} captions to {srt_path}")
    print(f"Total timeline duration: {cursor:.2f}s")


if __name__ == "__main__":
    main()
