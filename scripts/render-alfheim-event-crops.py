from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render ball-centred crops for manual Alfheim events."
    )
    parser.add_argument(
        "--video",
        type=Path,
        default=Path("benchmarks/alfheim/window-555/alfheim-window.mp4"),
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path("benchmarks/alfheim/window-555/ball-ground-truth.csv"),
    )
    parser.add_argument(
        "--manual",
        type=Path,
        default=Path("benchmarks/alfheim/window-555/manual-events.json"),
    )
    parser.add_argument(
        "--comparison",
        type=Path,
        default=Path(
            "benchmarks/alfheim/window-555/analytics-data/manual-comparison.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "benchmarks/alfheim/window-555/analytics-data/manual-event-crops.jpg"
        ),
    )
    args = parser.parse_args()

    manual = json.loads(args.manual.read_text(encoding="utf-8"))["events"]
    comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
    matched_times = {
        float(match["manual"]["clip_seconds"]) for match in comparison["matches"]
    }
    nearby_times = {
        float(item["manual"]["clip_seconds"])
        for item in comparison["nearby_disagreements"]
    }
    with args.ground_truth.open(newline="", encoding="utf-8") as csv_file:
        labels = {
            int(row["frame"]): (int(row["ball_x"]), int(row["ball_y"]))
            for row in csv.DictReader(csv_file)
        }

    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {args.video}")
    tiles: list[np.ndarray] = []
    try:
        for event in manual:
            seconds = float(event["clip_seconds"])
            frame_index = round(seconds * 25)
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"Could not read frame {frame_index}")
            ball_x, ball_y = labels[frame_index]
            x1 = min(max(0, ball_x - 400), frame.shape[1] - 800)
            y1 = min(max(0, ball_y - 300), frame.shape[0] - 600)
            crop = frame[y1 : y1 + 600, x1 : x1 + 800].copy()
            cv2.circle(crop, (ball_x - x1, ball_y - y1), 18, (0, 0, 255), 4)
            status = (
                "MATCH"
                if seconds in matched_times
                else "WRONG CLASS"
                if seconds in nearby_times
                else "MISSED"
            )
            title = (
                f"{seconds:05.2f}s {event['team']} "
                f"{event['event_type'].replace('_', ' ')} - {status}"
            )
            cv2.rectangle(crop, (0, 0), (800, 45), (0, 0, 0), -1)
            cv2.putText(
                crop,
                title,
                (12, 31),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            tiles.append(cv2.resize(crop, (400, 300), interpolation=cv2.INTER_AREA))
    finally:
        capture.release()

    while len(tiles) % 4:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [
        np.hstack(tiles[index : index + 4])
        for index in range(0, len(tiles), 4)
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), np.vstack(rows))
    print(f"Rendered {len(manual)} event crops to {args.output.resolve()}")


if __name__ == "__main__":
    main()
