from __future__ import annotations

import argparse
import csv
from pathlib import Path

from football_poc.pitch_geometry import (
    detect_boundary_intervals,
    load_pitch_boundary,
    write_boundary_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Flag possible Alfheim out-of-bounds intervals."
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path("benchmarks/alfheim/window-555/ball-ground-truth.csv"),
    )
    parser.add_argument(
        "--calibration",
        type=Path,
        default=Path("benchmarks/alfheim/window-555/pitch-calibration.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/alfheim/window-555/boundary-events.json"),
    )
    parser.add_argument("--outside-margin", type=float, default=12.0)
    parser.add_argument("--minimum-duration", type=float, default=0.4)
    args = parser.parse_args()

    with args.ground_truth.open(newline="", encoding="utf-8") as csv_file:
        points = [
            {
                "frame": int(row["frame"]),
                "seconds": float(row["timestamp_seconds"]),
                "x": float(row["ball_x"]),
                "y": float(row["ball_y"]),
            }
            for row in csv.DictReader(csv_file)
        ]
    intervals = detect_boundary_intervals(
        points,
        boundary=load_pitch_boundary(args.calibration),
        outside_margin_px=args.outside_margin,
        minimum_outside_seconds=args.minimum_duration,
    )
    write_boundary_report(
        args.output,
        calibration_path=args.calibration,
        intervals=intervals,
        outside_margin_px=args.outside_margin,
        minimum_outside_seconds=args.minimum_duration,
    )
    print(f"Wrote {len(intervals)} possible boundary intervals to {args.output.resolve()}")


if __name__ == "__main__":
    main()
