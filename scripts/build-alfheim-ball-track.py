from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert Alfheim ball labels to the POC ball-track schema."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("benchmarks/alfheim/window-555/manifest.json"),
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path("benchmarks/alfheim/window-555/ball-ground-truth.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "benchmarks/alfheim/window-555/ground-truth-ball-tracks.json"
        ),
    )
    parser.add_argument("--stride", type=int, default=5)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.stride < 1:
        raise ValueError("--stride must be at least 1")
    points = []
    with args.ground_truth.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            frame = int(row["frame"])
            if frame % args.stride:
                continue
            points.append(
                {
                    "source_frame": frame,
                    "clip_seconds": float(row["timestamp_seconds"]),
                    "confidence": 1.0,
                    "x": float(row["ball_x"]),
                    "y": float(row["ball_y"]),
                    "interpolated": False,
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "manifest": str(args.manifest.resolve()),
                "source": str(args.ground_truth.resolve()),
                "source_kind": "dataset_ground_truth",
                "tracks": [{"track_id": 1, "points": points}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(points)} labelled ball points to {args.output.resolve()}")


if __name__ == "__main__":
    main()
