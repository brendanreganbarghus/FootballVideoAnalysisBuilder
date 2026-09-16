from __future__ import annotations

import argparse
from pathlib import Path

from football_poc.ball_tracking import track_cached_balls


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track ball candidates from cached SoccerTrack detections."
    )
    parser.add_argument(
        "manifest",
        type=Path,
        nargs="?",
        default=Path("benchmarks/soccertrack-117093-window.json"),
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path("benchmarks/soccertrack-117093-yolo/detections.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/soccertrack-117093-yolo"),
    )
    parser.add_argument("--static-cell-size", type=int, default=20)
    parser.add_argument("--static-occupancy", type=float, default=0.25)
    parser.add_argument("--max-gap", type=float, default=0.56)
    parser.add_argument("--max-speed", type=float, default=1600.0)
    parser.add_argument("--minimum-track-points", type=int, default=3)
    parser.add_argument(
        "--analysis-start-seconds",
        type=float,
        default=None,
        help="Optional inclusive start for an isolated cached-analysis window.",
    )
    parser.add_argument(
        "--analysis-end-seconds",
        type=float,
        default=None,
        help="Optional exclusive end for an isolated cached-analysis window.",
    )
    parser.add_argument(
        "--reuse-decoded-frame-cache",
        action="store_true",
        help=(
            "Reuse a validated temporary lossless sampled-frame cache after "
            "an interrupted run."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    track_cached_balls(
        manifest_path=args.manifest,
        cache_path=args.cache,
        output=args.output,
        static_cell_size=args.static_cell_size,
        static_occupancy=args.static_occupancy,
        max_gap_seconds=args.max_gap,
        max_speed_pixels_per_second=args.max_speed,
        minimum_track_points=args.minimum_track_points,
        analysis_start_seconds=args.analysis_start_seconds,
        analysis_end_seconds=args.analysis_end_seconds,
        reuse_decoded_frame_cache=args.reuse_decoded_frame_cache,
    )


if __name__ == "__main__":
    main()
