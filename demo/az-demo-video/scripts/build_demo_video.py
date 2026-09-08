"""Build the Football AI Platform demo video (reproducible copy).

Pipeline:
  1. Renders static calibrated screenshots and subtle high-quality motion for
     presentation graphics in assets/shots/, and/or trims real match footage.
  2. Muxes each scene's visuals (silent) with its pre-rendered narration
     audio (see synthesize_narration_edge.py / scenes.json) using fades.
  3. Concatenates video-only streams and audio (WAV) tracks SEPARATELY, then
     muxes once at the end. This avoids AAC bitstream corruption that occurs
     if you `-c copy` concat multiple independently-encoded AAC segments.
  4. Burns in the SRT caption track (see generate_srt.py).
  5. Encodes the final 1920x1080 16:9 h264/aac MP4.

Run with (from repo root):
    python demo/az-demo-video/scripts/build_demo_video.py --pace fast
    python demo/az-demo-video/scripts/build_demo_video.py --pace relaxed

Both narration pace presets (see synthesize_narration_edge.py PACE_PRESETS)
read from their own build/audio/<pace>/ folder and write to their own
differently-named output MP4, so both can be generated and compared without
re-running narration synthesis.

Requires: imageio_ffmpeg (bundled ffmpeg), Pillow.

External inputs not shipped in this repo (large/gitignored generated media):
  - RAW_MATCH_MP4 / TRACKING_MP4 below default to this worktree's own
    REPO/benchmarks/alfheim/generated/segment-0300-020 output (see
    docs/RULES_ENGINE_ARCHITECTURE.md and benchmarks/alfheim/). Set the
    FOOTBALL_DEMO_SEGMENT_ROOT environment variable to point at a different
    checkout instead (e.g. a sibling worktree), or regenerate the benchmark
    locally.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

SCRIPT_DIR = Path(__file__).resolve().parent
DEMO_DIR = SCRIPT_DIR.parent          # demo/az-demo-video
REPO = DEMO_DIR.parent.parent          # repo root

SHOTS = DEMO_DIR / "assets" / "shots"
BUILD = DEMO_DIR / "build"             # local scratch dir (gitignored: *.mp4/*.wav)

OUT_DIR = DEMO_DIR

OUT_NAMES = {
    "fast": "Football_AI_Platform_Demo_4min.mp4",
    "relaxed": "Football_AI_Platform_Demo_4m48s.mp4",
}
# The relaxed pace is the presentation default at the stable canonical URL.
# The fast cut remains available under its explicit 4min filename.
PRIMARY_PACE = "relaxed"

# --- External, machine-local benchmark footage (not shipped in the repo) ---
# Defaults to REPO/benchmarks/alfheim/generated/segment-0300-020 (this
# worktree's own benchmark output). Override with the FOOTBALL_DEMO_SEGMENT_ROOT
# environment variable to point at a different checkout, e.g. a sibling
# worktree where the benchmark clips were generated.
_DEFAULT_SEGMENT = Path(
    os.environ.get("FOOTBALL_DEMO_SEGMENT_ROOT")
    or (REPO / "benchmarks" / "alfheim" / "generated" / "segment-0300-020")
)
RAW_MATCH_MP4 = _DEFAULT_SEGMENT / "alfheim-window-playable.mp4"
TRACKING_MP4 = _DEFAULT_SEGMENT / "analytics-data" / "tracking-verification.mp4"

W, H, FPS = 1920, 1080, 30

FONT_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"
FONT_REG = r"C:\Windows\Fonts\segoeui.ttf"


def run(cmd: list[str]):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}")
    return proc.stdout


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run([FFMPEG, "-i", str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            hms = line.split(",")[0].split("Duration:")[1].strip()
            h, m, s = hms.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"Could not determine duration for {path}")


@dataclass
class ImageShot:
    src: Path
    duration: float
    zoom_end: float = 1.0
    focus: tuple[float, float] = (0.5, 0.5)


@dataclass
class VideoShot:
    src: Path
    duration: float
    start: float = 0.0


@dataclass
class Scene:
    id: int
    title: str
    audio: Path
    shots: list


def make_image_clip(shot: ImageShot, out_path: Path):
    if shot.zoom_end > 1.0:
        frames = max(2, int(round(shot.duration * FPS)))
        zexpr = f"min(zoom+{(shot.zoom_end - 1.0) / frames:.8f},{shot.zoom_end})"
        fx, fy = shot.focus
        vf = (
            f"scale=3840:2160:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad=3840:2160:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"zoompan=z='{zexpr}':x='(iw-iw/zoom)*{fx}':"
            f"y='(ih-ih/zoom)*{fy}':d={frames}:s={W}x{H}:fps={FPS},"
            f"format=yuv420p"
        )
    else:
        vf = (
            f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"format=yuv420p"
        )
    cmd = [
        FFMPEG, "-y", "-loop", "1", "-i", str(shot.src),
        "-vf", vf, "-t", f"{shot.duration:.3f}",
        "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
        str(out_path),
    ]
    run(cmd)


def make_video_clip(shot: VideoShot, out_path: Path):
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=yuv420p"
    cmd = [
        FFMPEG, "-y", "-ss", f"{shot.start:.3f}", "-i", str(shot.src),
        "-t", f"{shot.duration:.3f}", "-vf", vf,
        "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
        str(out_path),
    ]
    run(cmd)


def make_title_card(text_lines, duration: float, out_path: Path, subtitle: Optional[str] = None):
    img = Image.new("RGB", (W, H), (13, 17, 23))
    draw = ImageDraw.Draw(img)
    y = H // 2 - 90
    for text, size, color in text_lines:
        f = ImageFont.truetype(FONT_BOLD, size)
        bbox = draw.textbbox((0, 0), text, font=f)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) / 2, y), text, font=f, fill=color)
        y += size + 24
    if subtitle:
        f = ImageFont.truetype(FONT_REG, 26)
        bbox = draw.textbbox((0, 0), subtitle, font=f)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) / 2, y + 10), subtitle, font=f, fill=(139, 148, 158))
    png_path = out_path.with_suffix(".png")
    img.save(png_path)
    cmd = [
        FFMPEG, "-y", "-loop", "1", "-i", str(png_path), "-t", f"{duration:.3f}",
        "-vf", f"scale={W}:{H},format=yuv420p", "-r", str(FPS),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(out_path),
    ]
    run(cmd)


def silence_wav(duration: float, out_path: Path):
    cmd = [
        FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-t", f"{duration:.3f}", "-c:a", "pcm_s16le", str(out_path),
    ]
    run(cmd)


def normalize_wav(src: Path, out_path: Path):
    run([FFMPEG, "-y", "-i", str(src), "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out_path)])


def concat_copy(paths: list[Path], out_path: Path):
    list_file = out_path.with_suffix(".txt")
    with open(list_file, "w") as f:
        for p in paths:
            f.write(f"file '{p.as_posix()}'\n")
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)])


def fade_video(in_path: Path, out_path: Path, duration: float, fade_in: bool, fade_out: bool):
    filters = []
    if fade_in:
        filters.append("fade=t=in:st=0:d=0.5")
    if fade_out:
        filters.append(f"fade=t=out:st={max(0.0, duration - 0.5):.3f}:d=0.5")
    if not filters:
        run([FFMPEG, "-y", "-i", str(in_path), "-c", "copy", str(out_path)])
        return
    run([FFMPEG, "-y", "-i", str(in_path), "-vf", ",".join(filters), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path)])


def build_scene_video(scene: Scene, work: Path) -> tuple[Path, float]:
    """Returns (faded video-only clip path, duration)."""
    scene_dir = work / f"scene{scene.id:02d}"
    scene_dir.mkdir(parents=True, exist_ok=True)
    audio_dur = ffprobe_duration(scene.audio)
    clip_paths = []
    for i, shot in enumerate(scene.shots):
        clip_out = scene_dir / f"shot{i:02d}.mp4"
        if isinstance(shot, ImageShot):
            make_image_clip(shot, clip_out)
        elif isinstance(shot, VideoShot):
            make_video_clip(shot, clip_out)
        else:
            raise TypeError(shot)
        clip_paths.append(clip_out)

    combined = clip_paths[0] if len(clip_paths) == 1 else scene_dir / "combined.mp4"
    if len(clip_paths) > 1:
        concat_copy(clip_paths, combined)

    faded = scene_dir / "faded.mp4"
    fade_video(combined, faded, audio_dur, fade_in=True, fade_out=True)
    print(f"Scene {scene.id} ({scene.title}): {audio_dur:.2f}s -> {faded}")
    return faded, audio_dur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pace", choices=list(OUT_NAMES.keys()), default=PRIMARY_PACE)
    args = ap.parse_args()
    pace = args.pace

    audio_dir = BUILD / "audio" / pace
    work = BUILD / "work" / pace
    work.mkdir(parents=True, exist_ok=True)
    if not audio_dir.exists():
        raise RuntimeError(
            f"No narration audio found at {audio_dir}. Run "
            f"synthesize_narration_edge.py --pace {pace} first."
        )

    scenes_json = json.loads((SCRIPT_DIR / "scenes.json").read_text())
    titles = {s["id"]: s["title"] for s in scenes_json}

    def a(n):
        return audio_dir / f"scene{n:02d}.wav"

    scenes = [
        Scene(1, titles[1], a(1), None),
        Scene(2, titles[2], a(2), [ImageShot(SHOTS / "landing.png", duration=ffprobe_duration(a(2)), zoom_end=1.04, focus=(0.5, 0.3))]),
        Scene(3, titles[3], a(3), None),
        Scene(4, titles[4], a(4), None),
        Scene(5, titles[5], a(5), None),
        Scene(6, titles[6], a(6), None),
        Scene(7, titles[7], a(7), [ImageShot(SHOTS / "copilot-concept.png", duration=ffprobe_duration(a(7)), zoom_end=1.04, focus=(0.5, 0.35))]),
        Scene(8, titles[8], a(8), None),
        Scene(9, titles[9], a(9), None),
        Scene(10, titles[10], a(10), None),
    ]

    # Scene 1 (Opening): real match footage first, then a reveal of the
    # current all-in-one Football Event Review Canvas -- this is the current
    # POC workflow, not the old manual-click Validation Lab screen.
    d1 = ffprobe_duration(a(1))
    reveal1 = min(6.0, d1 * 0.35)
    scenes[0].shots = [
        VideoShot(RAW_MATCH_MP4, duration=d1 - reveal1, start=5.0),
        ImageShot(SHOTS / "review-canvas-timeline-accept.png", duration=reveal1),
    ]

    # Scene 3: segment builder concept -- replaces the old, obsolete
    # Validation Lab screenshot with the current Canvas's segment-building
    # / preparation area, then a short real clip of the raw match footage
    # being windowed into the controlled 30-60s segment.
    d3 = ffprobe_duration(a(3))
    clip3 = min(4.0, d3 * 0.35)
    scenes[2].shots = [
        ImageShot(SHOTS / "review-canvas-timeline-accept.png", duration=d3 - clip3),
        VideoShot(RAW_MATCH_MP4, duration=clip3, start=20.0),
    ]

    d4 = ffprobe_duration(a(4))
    scenes[3].shots = [
        VideoShot(TRACKING_MP4, duration=min(18.0, d4)),
        ImageShot(SHOTS / "review-canvas-zoomed-action.png", duration=d4 - min(18.0, d4)),
    ]

    # Scene 5: the guarded review/publication gate. Lead with the maximized
    # accept/validate comparison timeline (real Accept/Reject decisions and
    # the "Engine already agrees" panel), then the 105-passed protected
    # regression run.
    d5 = ffprobe_duration(a(5))
    part_a = d5 * 0.6
    scenes[4].shots = [
        ImageShot(SHOTS / "review-canvas-timeline-accept.png", duration=part_a),
        ImageShot(SHOTS / "tests-105-passed.png", duration=d5 - part_a),
    ]

    # Scene 6: statistics/maturity dashboard, then real mid-playback footage
    # from the Match Replay Preview panel with its live (non-zero) stats
    # table, then the landing page's maturity grid.
    d6 = ffprobe_duration(a(6))
    part_a6 = d6 * 0.42
    part_b6 = d6 * 0.30
    scenes[5].shots = [
        ImageShot(SHOTS / "stats-dashboard.png", duration=part_a6, zoom_end=1.04, focus=(0.5, 0.35)),
        ImageShot(SHOTS / "match-replay-playing-crop.png", duration=part_b6),
        ImageShot(SHOTS / "landing.png", duration=d6 - part_a6 - part_b6, zoom_end=1.04, focus=(0.5, 0.7)),
    ]

    # Scene 8 uses restrained motion on a presentation graphic. Calibrated
    # review screenshots remain static elsewhere so their overlays stay crisp.
    d8 = ffprobe_duration(a(8))
    half8 = d8 / 2.0
    scenes[7].shots = [
        ImageShot(SHOTS / "future-vision.png", duration=half8, zoom_end=1.04, focus=(0.5, 0.25)),
        ImageShot(SHOTS / "future-vision.png", duration=d8 - half8, zoom_end=1.04, focus=(0.5, 0.55)),
    ]

    # Scene 9: dedicated Query By Probability architecture graphic.
    d9 = ffprobe_duration(a(9))
    scenes[8].shots = [
        ImageShot(SHOTS / "query-by-probability.png", duration=d9, zoom_end=1.03, focus=(0.5, 0.45)),
    ]

    # Scene 10 uses the same restrained presentation-graphic motion.
    d10 = ffprobe_duration(a(10))
    scenes[9].shots = [
        ImageShot(SHOTS / "future-vision.png", duration=d10, zoom_end=1.04, focus=(0.5, 0.8)),
    ]

    scene_results = [build_scene_video(s, work) for s in scenes]

    # Title + closing cards -- generic, reusable pitch-deck framing with no
    # AZ Alkmaar branding.
    title_video = work / "title_faded.mp4"
    make_title_card(
        [("Football Intelligence Platform", 56, (240, 246, 252))],
        duration=4.0, out_path=work / "title_card.mp4",
        subtitle="From match video to validated football intelligence",
    )
    fade_video(work / "title_card.mp4", title_video, 4.0, fade_in=True, fade_out=True)
    title_silence = work / "title_silence.wav"
    silence_wav(4.0, title_silence)

    closing_video = work / "closing_faded.mp4"
    make_title_card(
        [("Football Intelligence Platform", 44, (240, 246, 252)),
         ("Xebia Netherlands", 34, (88, 166, 255)),
         ("Scalable AI & engineering capacity for a next phase", 28, (230, 237, 243))],
        duration=6.0, out_path=work / "closing_card.mp4",
        subtitle="Prototype build \u00b7 internal review candidate",
    )
    fade_video(work / "closing_card.mp4", closing_video, 6.0, fade_in=True, fade_out=True)
    closing_silence = work / "closing_silence.wav"
    silence_wav(6.0, closing_silence)

    # 1) Concatenate VIDEO-ONLY streams (safe: consistent h264 encode params).
    all_video = [title_video] + [v for v, _ in scene_results] + [closing_video]
    video_full = work / "video_full.mp4"
    concat_copy(all_video, video_full)

    # 2) Concatenate AUDIO as PCM WAV (safe: no AAC splice corruption).
    norm_scene_audio = []
    for i, scene in enumerate(scenes, start=1):
        norm = work / f"scene{i:02d}_audio_norm.wav"
        normalize_wav(scene.audio, norm)
        norm_scene_audio.append(norm)
    all_audio = [title_silence] + norm_scene_audio + [closing_silence]
    audio_full = work / "audio_full.wav"
    concat_copy(all_audio, audio_full)

    # 3) Mux once, encoding audio to AAC a single time.
    muxed = work / "muxed_final.mp4"
    run([
        FFMPEG, "-y", "-i", str(video_full), "-i", str(audio_full),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(muxed),
    ])

    # 4) Burn in captions (run scripts/generate_srt.py --pace <pace> first).
    srt_suffix = "" if pace == "fast" else f"_{pace}"
    srt_path = DEMO_DIR / f"Football_AI_Platform_Demo{srt_suffix}.srt"
    final_out = OUT_DIR / OUT_NAMES[pace]
    if srt_path.exists():
        srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
        style = (
            "FontName=Segoe UI,FontSize=13,PrimaryColour=&H00F0F6FC,"
            "OutlineColour=&H00161B22,BackColour=&H90000000,BorderStyle=4,"
            "Outline=0,Shadow=0,MarginV=40,Alignment=2"
        )
        run([
            FFMPEG, "-y", "-i", str(muxed),
            "-vf", f"subtitles='{srt_escaped}':force_style='{style}'",
            "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
            "-c:a", "copy", str(final_out),
        ])
    else:
        print("No SRT found; copying muxed video without burned-in captions. Run generate_srt.py first.")
        run([FFMPEG, "-y", "-i", str(muxed), "-c", "copy", str(final_out)])

    # Also drop a copy at the canonical primary name for the pace that is
    # meant to be the default deliverable.
    if pace == PRIMARY_PACE:
        canonical = OUT_DIR / "Football_AI_Platform_Demo.mp4"
        run([FFMPEG, "-y", "-i", str(final_out), "-c", "copy", str(canonical)])
        print(f"Also wrote canonical copy: {canonical}")

    print(f"\nFINAL VIDEO ({pace}): {final_out}")
    print(f"Total duration: {ffprobe_duration(final_out):.2f}s")


if __name__ == "__main__":
    main()
