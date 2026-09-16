from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from football_poc.alfheim_segments import resolve_alfheim_pano


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a raw-video-only MP4 window from Alfheim H.264 segments."
    )
    parser.add_argument(
        "--pano",
        type=Path,
        default=resolve_alfheim_pano(Path.cwd()),
        help=(
            "Extracted Alfheim pano directory. Defaults to "
            "FOOTBALL_ALFHEIM_PANO, then .\\pano."
        ),
    )
    parser.add_argument("--start-segment", type=int, default=555)
    parser.add_argument("--segment-count", type=int, default=20)
    parser.add_argument("--clip-start-seconds", type=float, default=0.0)
    parser.add_argument("--duration-seconds", type=float, default=60.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/alfheim/window-555"),
    )
    parser.add_argument(
        "--ffmpeg",
        type=Path,
        default=None,
        help="FFmpeg executable. Defaults to PATH, then imageio-ffmpeg.",
    )
    return parser


def find_ffmpeg(explicit: Path | None) -> Path:
    if explicit:
        if not explicit.is_file():
            raise FileNotFoundError(f"FFmpeg executable not found: {explicit}")
        return explicit
    path = shutil.which("ffmpeg")
    if path:
        return Path(path)
    try:
        import imageio_ffmpeg
    except ImportError as error:
        raise RuntimeError(
            "FFmpeg was not found. Install imageio-ffmpeg or pass --ffmpeg."
        ) from error
    return Path(imageio_ffmpeg.get_ffmpeg_exe())


def select_segments(pano: Path, start: int, count: int) -> list[Path]:
    if start < 0:
        raise ValueError("--start-segment must be non-negative")
    if count < 1:
        raise ValueError("--segment-count must be positive")
    segments = sorted(pano.glob("*.h264"))
    selected = segments[start : start + count]
    if len(selected) != count:
        raise ValueError(
            f"Requested {count} segments from {start}, but only {len(selected)} exist"
        )
    expected = list(range(start, start + count))
    actual = [int(path.name.split("_", 1)[0]) for path in selected]
    if actual != expected:
        raise ValueError(f"Segment sequence is not continuous: {actual}")
    return selected


def write_concat_manifest(segments: list[Path], output: Path) -> Path:
    manifest = output / "segments.txt"
    lines = [
        f"file '{segment.resolve().as_posix().replace(chr(39), chr(39) * 3)}'"
        for segment in segments
    ]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def remux(ffmpeg: Path, manifest: Path, destination: Path) -> None:
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "warning",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(manifest),
        "-c:v",
        "copy",
        "-an",
        "-movflags",
        "+faststart",
        "-y",
        str(destination),
    ]
    subprocess.run(command, check=True)


def transcode_playable(
    ffmpeg: Path,
    source: Path,
    destination: Path,
    *,
    clip_start_seconds: float,
    duration_seconds: float,
) -> None:
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "warning",
        "-ss",
        f"{clip_start_seconds:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration_seconds:.3f}",
        "-vf",
        "scale=3840:-2",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-level",
        "5.1",
        "-movflags",
        "+faststart",
        "-an",
        "-y",
        str(destination),
    ]
    subprocess.run(command, check=True)


def write_benchmark_manifest(
    video: Path,
    playable_video: Path,
    output: Path,
    *,
    frame_count: int,
    source_start_seconds: float,
    duration_seconds: float,
) -> Path:
    destination = output / "manifest.json"
    destination.write_text(
        json.dumps(
            {
                "dataset": "Simula Alfheim Camera Setting 2",
                "usage": "non-commercial research only",
                "video": str(video.resolve()),
                "playable_video": str(playable_video.resolve()),
                "fps": 25.0,
                "start_frame": 0,
                "end_frame": frame_count,
                "source_start_seconds": source_start_seconds,
                "duration_seconds": duration_seconds,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return destination


def main() -> None:
    args = build_parser().parse_args()
    if not args.pano.is_dir():
        raise FileNotFoundError(f"Alfheim pano folder not found: {args.pano}")
    args.output.mkdir(parents=True, exist_ok=True)
    segments = select_segments(
        args.pano, args.start_segment, args.segment_count
    )
    if args.clip_start_seconds < 0:
        raise ValueError("--clip-start-seconds must be non-negative")
    if args.duration_seconds not in {30.0, 60.0}:
        raise ValueError("--duration-seconds must be exactly 30 or 60")
    manifest = write_concat_manifest(segments, args.output)
    video = args.output / "alfheim-window.mp4"
    ffmpeg = find_ffmpeg(args.ffmpeg)
    remux(ffmpeg, manifest, video)
    playable = args.output / "alfheim-window-playable.mp4"
    transcode_playable(
        ffmpeg,
        video,
        playable,
        clip_start_seconds=args.clip_start_seconds,
        duration_seconds=args.duration_seconds,
    )
    (args.output / "ball-ground-truth.csv").unlink(missing_ok=True)
    benchmark = write_benchmark_manifest(
        video,
        playable,
        args.output,
        frame_count=round(args.duration_seconds * 25),
        source_start_seconds=(
            args.start_segment * 3 + args.clip_start_seconds
        ),
        duration_seconds=args.duration_seconds,
    )
    print(f"Video: {video.resolve()}")
    print(f"Playable video: {playable.resolve()}")
    print(f"Benchmark manifest: {benchmark.resolve()}")


if __name__ == "__main__":
    main()
