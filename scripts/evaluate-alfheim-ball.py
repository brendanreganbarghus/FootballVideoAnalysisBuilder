from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score cached Alfheim ball detections against labelled coordinates."
    )
    parser.add_argument("detections", type=Path)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("--max-distance", type=float, default=32.0)
    return parser


def load_ground_truth(path: Path) -> dict[int, tuple[float, float]]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        return {
            int(row["frame"]): (float(row["ball_x"]), float(row["ball_y"]))
            for row in csv.DictReader(csv_file)
        }


def score(
    detections_path: Path,
    ground_truth_path: Path,
    max_distance: float,
) -> dict[str, float | int]:
    ground_truth = load_ground_truth(ground_truth_path)
    evaluated = matched = missed = false_positives = 0
    distances: list[float] = []
    for line in detections_path.read_text(encoding="utf-8").splitlines()[1:]:
        record = json.loads(line)
        if record.get("type") != "frame":
            continue
        frame = int(record["source_frame"])
        if frame not in ground_truth:
            continue
        evaluated += 1
        truth_x, truth_y = ground_truth[frame]
        candidates = [
            detection
            for detection in record.get("detections", [])
            if str(detection.get("class_name", "")).lower() in {"ball", "sports ball"}
        ]
        candidate_distances = [
            math.hypot(
                (float(item["x1"]) + float(item["x2"])) / 2 - truth_x,
                (float(item["y1"]) + float(item["y2"])) / 2 - truth_y,
            )
            for item in candidates
        ]
        if candidate_distances and min(candidate_distances) <= max_distance:
            matched += 1
            distances.append(min(candidate_distances))
            false_positives += max(0, len(candidates) - 1)
        else:
            missed += 1
            false_positives += len(candidates)
    precision_denominator = matched + false_positives
    return {
        "evaluated_frames": evaluated,
        "matched_frames": matched,
        "missed_frames": missed,
        "false_positive_detections": false_positives,
        "frame_recall": matched / evaluated if evaluated else 0.0,
        "precision": matched / precision_denominator if precision_denominator else 0.0,
        "mean_matched_distance_px": (
            sum(distances) / len(distances) if distances else 0.0
        ),
        "max_distance_px": max_distance,
    }


def main() -> None:
    args = build_parser().parse_args()
    if args.max_distance <= 0:
        raise ValueError("--max-distance must be positive")
    result = score(args.detections, args.ground_truth, args.max_distance)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
