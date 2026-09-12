from __future__ import annotations

import argparse
from pathlib import Path

from football_poc.benchmark import run_detection_cache


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cache tiled detections for a SoccerTrack benchmark manifest."
    )
    parser.add_argument(
        "manifest",
        type=Path,
        nargs="?",
        default=Path("benchmarks/soccertrack-117093-window.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/soccertrack-117093-yolo"),
    )
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--confidence", type=float, default=0.1)
    parser.add_argument("--image-size", type=int, default=960)
    parser.add_argument("--device", default=None)
    parser.add_argument("--stride", type=int, default=2)
    parser.add_argument("--tile-width", type=int, default=1280)
    parser.add_argument(
        "--tile-height",
        type=int,
        default=None,
        help="Optional tile height; omit to retain full-height horizontal tiles.",
    )
    parser.add_argument("--overlap", type=float, default=0.2)
    parser.add_argument("--nms-iou", type=float, default=0.5)
    parser.add_argument(
        "--frame-batch-size",
        type=int,
        default=4,
        help="Decode and infer this many sampled panoramic frames per batch.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Process at most this many new frames, preserving them for resume.",
    )
    parser.add_argument(
        "--reuse-cache",
        action="store_true",
        help=(
            "Resume a matching detection cache. Omit for a cold raw-video "
            "benchmark that replaces prior detections."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_detection_cache(
        manifest_path=args.manifest,
        output=args.output,
        model_name=args.model,
        confidence=args.confidence,
        image_size=args.image_size,
        device=args.device,
        stride=args.stride,
        tile_width=args.tile_width,
        tile_height=args.tile_height,
        overlap=args.overlap,
        nms_iou=args.nms_iou,
        max_frames=args.max_frames,
        frame_batch_size=args.frame_batch_size,
        reuse_cache=args.reuse_cache,
    )


if __name__ == "__main__":
    main()
