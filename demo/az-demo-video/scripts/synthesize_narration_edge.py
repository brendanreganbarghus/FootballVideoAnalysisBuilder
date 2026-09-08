"""Synthesize narration for the Football AI Platform demo using Microsoft Edge's
neural TTS (the `edge-tts` Python package), sentence-by-sentence, so the result
sounds like a person reading with real grammar-aware pauses rather than one
flat, non-stop block of speech.

Why sentence-by-sentence (not one Communicate call per whole scene):
  - Azure/Edge neural voices already phrase reasonably within a single call,
    but a long multi-sentence paragraph synthesized in one shot still reads
    as a continuous stream with only the engine's own (short, uneven) internal
    gaps between sentences.
  - Synthesizing each sentence as its own request lets this script insert
    explicit, calibrated silence between sentences (longer after a full stop,
    shorter mid-sentence at a comma break for long sentences), which is the
    concrete mechanism for "grammar and pauses" rather than hoping the engine
    infers it.
  - It also lets each sentence get its own subtle rate/pitch nudge based on a
    simple classification (a factual/numeric sentence is delivered a little
    slower and grounded; a short punchy closing line gets a little lift) which
    gives real, per-sentence expressive variation instead of a flat delivery
    for four minutes straight -- the "emotion" component, kept calm and
    professional rather than salesy.

Requires: `pip install edge-tts` (needs internet access to Microsoft's Edge
TTS endpoint; the rendered WAV output itself stays local). Falls back to the
Windows WinRT "Mark" voice (synthesize_narration.ps1) if edge-tts or internet
access is unavailable.

Run with (from repo root):
    python demo/az-demo-video/scripts/synthesize_narration_edge.py --pace fast
    python demo/az-demo-video/scripts/synthesize_narration_edge.py --pace relaxed
    python demo/az-demo-video/scripts/synthesize_narration_edge.py --voice en-GB-RyanNeural --only-ids 5 --pace fast

Two pacing presets are available (see PACE_PRESETS): "fast" (~4:00 total
video) and "relaxed" (~4:48 total video), each written to its own
build/audio/<pace>/ folder so both can be reviewed side by side.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import edge_tts
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SCRIPT_DIR = Path(__file__).resolve().parent
DEMO_DIR = SCRIPT_DIR.parent
TMP_DIR = DEMO_DIR / "build" / "audio_tmp"

DEFAULT_VOICE = "en-GB-RyanNeural"  # calm, natural, professional UK male neural voice

# Two pacing presets, both using the same sentence-by-sentence grammar-aware
# pause/emotion mechanism -- only the pause lengths and per-class rates
# differ, so both stay expressive rather than robotic. "fast" targets a
# ~4:00 total video; "relaxed" targets a slightly more deliberate ~4:48.
# Each writes into its own build/audio/<pace>/ folder so both can be built
# into separate MP4s for side-by-side review without re-synthesizing.
PACE_PRESETS = {
    "fast": {
        "pauses": {"normal": 0.16, "punchy": 0.24, "fact": 0.22, "mid": 0.09},
        "prosody": {
            "normal": ("+32%", "+0Hz"),
            "fact": ("+20%", "-1Hz"),
            "punchy": ("+24%", "+2Hz"),
        },
    },
    "relaxed": {
        "pauses": {"normal": 0.22, "punchy": 0.32, "fact": 0.30, "mid": 0.12},
        "prosody": {
            "normal": ("+16%", "+0Hz"),
            "fact": ("+6%", "-1Hz"),
            "punchy": ("+8%", "+2Hz"),
        },
    },
}

NUMBER_WORDS = (
    "one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen hundred percent"
).split()


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}")


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run([FFMPEG, "-i", str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            hms = line.split(",")[0].split("Duration:")[1].strip()
            h, m, s = hms.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"Could not determine duration for {path}")


def split_sentences(text: str) -> list[str]:
    """Split on sentence-ending punctuation, keeping the punctuation."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


def classify(sentence: str) -> str:
    words = sentence.rstrip(".!?").split()
    lower = sentence.lower()
    has_number = any(ch.isdigit() for ch in sentence) or any(
        f" {w} " in f" {lower} " for w in NUMBER_WORDS
    )
    if has_number and len(words) >= 8:
        return "fact"
    if len(words) <= 7:
        return "punchy"
    return "normal"


def maybe_split_long(sentence: str) -> list[str]:
    """Break a long sentence into two chunks at a comma near its midpoint, so
    a mid-sentence breath pause can be inserted (still one grammatical
    sentence, just given room to breathe)."""
    words = sentence.split()
    if len(words) < 24:
        return [sentence]
    comma_positions = [m.start() for m in re.finditer(",", sentence)]
    if not comma_positions:
        return [sentence]
    mid = len(sentence) / 2
    best = min(comma_positions, key=lambda p: abs(p - mid))
    head, tail = sentence[: best + 1].strip(), sentence[best + 1 :].strip()
    if not head or not tail:
        return [sentence]
    return [head, tail]


@dataclass
class Chunk:
    text: str
    rate: str
    pitch: str
    pause_after: float


def build_chunks(text: str, preset: dict) -> list[Chunk]:
    prosody = preset["prosody"]
    pauses = preset["pauses"]
    chunks: list[Chunk] = []
    for sentence in split_sentences(text):
        pieces = maybe_split_long(sentence)
        kind = classify(sentence)
        rate, pitch = prosody[kind]
        for i, piece in enumerate(pieces):
            is_last_piece = i == len(pieces) - 1
            pause = pauses[kind] if is_last_piece else pauses["mid"]
            chunks.append(Chunk(piece, rate, pitch, pause))
    return chunks


async def synth_chunk(text: str, voice: str, rate: str, pitch: str, out_path: Path) -> None:
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(str(out_path))


def silence_wav(duration: float, out_path: Path) -> None:
    run([
        FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-t", f"{duration:.3f}", "-c:a", "pcm_s16le", str(out_path),
    ])


def to_wav(src: Path, out_path: Path) -> None:
    run([FFMPEG, "-y", "-i", str(src), "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out_path)])


def concat_wavs(paths: list[Path], out_path: Path) -> None:
    list_file = out_path.with_suffix(".txt")
    with open(list_file, "w") as f:
        for p in paths:
            f.write(f"file '{p.as_posix()}'\n")
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)])


async def synth_scene(scene: dict, voice: str, preset: dict, audio_dir: Path) -> float:
    scene_id = scene["id"]
    chunks = build_chunks(scene["text"], preset)
    scene_tmp = TMP_DIR / f"scene{scene_id:02d}"
    scene_tmp.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    for i, chunk in enumerate(chunks):
        mp3_path = scene_tmp / f"chunk{i:02d}.mp3"
        wav_path = scene_tmp / f"chunk{i:02d}.wav"
        await synth_chunk(chunk.text, voice, chunk.rate, chunk.pitch, mp3_path)
        to_wav(mp3_path, wav_path)
        parts.append(wav_path)
        if chunk.pause_after > 0:
            pause_path = scene_tmp / f"chunk{i:02d}_pause.wav"
            silence_wav(chunk.pause_after, pause_path)
            parts.append(pause_path)
    out_path = audio_dir / f"scene{scene_id:02d}.wav"
    concat_wavs(parts, out_path)
    dur = ffprobe_duration(out_path)
    print(f"Scene {scene_id} ({scene['title']}): {len(chunks)} chunks -> {out_path.name} ({dur:.2f}s)")
    return dur


async def main_async(voice: str, only_ids: list[int] | None, pace: str) -> None:
    scenes = json.loads((SCRIPT_DIR / "scenes.json").read_text())
    preset = PACE_PRESETS[pace]
    audio_dir = DEMO_DIR / "build" / "audio" / pace
    audio_dir.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    total = 0.0
    total_words = 0
    for scene in scenes:
        if only_ids and scene["id"] not in only_ids:
            continue
        total += await synth_scene(scene, voice, preset, audio_dir)
        total_words += len(scene["text"].split())
    print(f"\nVoice: {voice}  |  Pace preset: {pace}")
    print(f"Total narrated duration: {total:.2f}s across {len(scenes) if not only_ids else len(only_ids)} scene(s)")
    print(f"Total narrated words: {total_words}")
    print(f"Audio written to: {audio_dir}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--only-ids", type=int, nargs="*", default=None)
    ap.add_argument("--pace", choices=list(PACE_PRESETS.keys()), default="fast")
    args = ap.parse_args()
    asyncio.run(main_async(args.voice, args.only_ids, args.pace))


if __name__ == "__main__":
    main()
