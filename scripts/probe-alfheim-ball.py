from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test a ball detector on crops centred on Alfheim ground truth."
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
        "--model",
        type=Path,
        default=Path("models/football-players-ball-yolov8.pt"),
    )
    parser.add_argument("--sample-stride", type=int, default=25)
    parser.add_argument("--crop-size", type=int, default=512)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--confidence", type=float, default=0.01)
    parser.add_argument("--max-distance", type=float, default=32.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/alfheim/window-555/oracle-ball-probe"),
    )
    return parser


def load_ground_truth(path: Path) -> dict[int, tuple[int, int]]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        return {
            int(row["frame"]): (int(row["ball_x"]), int(row["ball_y"]))
            for row in csv.DictReader(csv_file)
        }


def crop_bounds(
    x: int, y: int, width: int, height: int, size: int
) -> tuple[int, int, int, int]:
    half = size // 2
    x1 = min(max(0, x - half), max(0, width - size))
    y1 = min(max(0, y - half), max(0, height - size))
    return x1, y1, min(width, x1 + size), min(height, y1 + size)


def ball_class_ids(names: dict[int, str]) -> list[int]:
    return [
        class_id
        for class_id, name in names.items()
        if str(name).strip().lower() in {"ball", "sports ball"}
    ]


def main() -> None:
    args = build_parser().parse_args()
    if args.sample_stride < 1 or args.crop_size < 64:
        raise ValueError("Sample stride must be positive and crop size at least 64")
    args.output.mkdir(parents=True, exist_ok=True)
    ground_truth = load_ground_truth(args.ground_truth)
    model = YOLO(args.model)
    classes = ball_class_ids(model.names)
    if not classes:
        raise ValueError("Model does not contain a ball class")

    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {args.video}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_index = 0
    samples: list[dict[str, object]] = []
    thumbnails: list[np.ndarray] = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index not in ground_truth or frame_index % args.sample_stride:
                frame_index += 1
                continue
            truth_x, truth_y = ground_truth[frame_index]
            x1, y1, x2, y2 = crop_bounds(
                truth_x, truth_y, width, height, args.crop_size
            )
            crop = frame[y1:y2, x1:x2]
            result = model.predict(
                source=crop,
                classes=classes,
                conf=args.confidence,
                imgsz=args.image_size,
                verbose=False,
            )[0]
            candidates: list[dict[str, float]] = []
            for box in result.boxes:
                bx1, by1, bx2, by2 = map(float, box.xyxy[0].tolist())
                center_x = x1 + (bx1 + bx2) / 2
                center_y = y1 + (by1 + by2) / 2
                candidates.append(
                    {
                        "confidence": float(box.conf[0]),
                        "center_x": center_x,
                        "center_y": center_y,
                        "distance_px": math.hypot(
                            center_x - truth_x, center_y - truth_y
                        ),
                    }
                )
            nearest = min(candidates, key=lambda item: item["distance_px"], default=None)
            matched = bool(
                nearest and nearest["distance_px"] <= args.max_distance
            )
            samples.append(
                {
                    "frame": frame_index,
                    "truth_x": truth_x,
                    "truth_y": truth_y,
                    "detections": len(candidates),
                    "matched": matched,
                    "nearest_distance_px": (
                        nearest["distance_px"] if nearest else None
                    ),
                    "nearest_confidence": (
                        nearest["confidence"] if nearest else None
                    ),
                }
            )
            if len(thumbnails) < 12:
                display = crop.copy()
                cv2.circle(
                    display,
                    (truth_x - x1, truth_y - y1),
                    18,
                    (0, 0, 255),
                    4,
                )
                for candidate in candidates:
                    color = (0, 255, 0) if candidate is nearest else (255, 160, 0)
                    cv2.circle(
                        display,
                        (
                            round(candidate["center_x"] - x1),
                            round(candidate["center_y"] - y1),
                        ),
                        12,
                        color,
                        3,
                    )
                cv2.putText(
                    display,
                    f"frame {frame_index} {'MATCH' if matched else 'MISS'}",
                    (12, 34),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                thumbnails.append(
                    cv2.resize(display, (256, 256), interpolation=cv2.INTER_AREA)
                )
            frame_index += 1
    finally:
        capture.release()

    matches = [sample for sample in samples if sample["matched"]]
    distances = [
        float(sample["nearest_distance_px"])
        for sample in matches
        if sample["nearest_distance_px"] is not None
    ]
    summary = {
        "video": str(args.video.resolve()),
        "model": str(args.model.resolve()),
        "sample_stride": args.sample_stride,
        "crop_size": args.crop_size,
        "image_size": args.image_size,
        "confidence": args.confidence,
        "max_distance_px": args.max_distance,
        "sampled_frames": len(samples),
        "matched_frames": len(matches),
        "oracle_crop_recall": len(matches) / len(samples) if samples else 0.0,
        "mean_matched_distance_px": (
            sum(distances) / len(distances) if distances else 0.0
        ),
        "samples": samples,
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    if thumbnails:
        rows = [
            np.hstack(thumbnails[index : index + 4])
            for index in range(0, len(thumbnails), 4)
        ]
        cv2.imwrite(str(args.output / "ball-crops.jpg"), np.vstack(rows))
    print(json.dumps({key: value for key, value in summary.items() if key != "samples"}, indent=2))


if __name__ == "__main__":
    main()
