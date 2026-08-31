from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
from ultralytics import YOLO

from football_poc.actions import ActionEngine, Detection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detect, track, and infer simple actions in a football video."
    )
    parser.add_argument("video", type=Path, help="Input video file")
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--confidence", type=float, default=0.2)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--device", default=None)
    parser.add_argument("--tracker", default="bytetrack.yaml")
    parser.add_argument(
        "--stride",
        type=int,
        default=2,
        help="Process every Nth frame; use 1 for maximum accuracy.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Stop after this many processed frames for a quick trial.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run(
        video=args.video,
        output=args.output,
        model_name=args.model,
        confidence=args.confidence,
        image_size=args.image_size,
        device=args.device,
        tracker=args.tracker,
        stride=args.stride,
        max_frames=args.max_frames,
    )


def run(
    *,
    video: Path,
    output: Path,
    model_name: str,
    confidence: float,
    image_size: int,
    device: str | None,
    tracker: str,
    stride: int,
    max_frames: int | None,
) -> None:
    if not video.is_file():
        raise FileNotFoundError(f"Input video does not exist: {video}")
    if not 0 < confidence <= 1:
        raise ValueError("--confidence must be greater than 0 and at most 1")
    if stride < 1:
        raise ValueError("--stride must be at least 1")
    if max_frames is not None and max_frames < 1:
        raise ValueError("--max-frames must be at least 1")

    output.mkdir(parents=True, exist_ok=True)
    fps, width, height, source_frames = _video_metadata(video)
    effective_fps = fps / stride
    expected_frames = math.ceil(source_frames / stride)
    if max_frames is not None:
        expected_frames = min(expected_frames, max_frames)
    print(
        f"Loading {model_name}. Processing about {expected_frames} frames "
        f"at {image_size}px on {device or 'automatic device selection'}."
    )
    model = YOLO(model_name)
    class_ids = _wanted_class_ids(model.names)
    if not class_ids:
        raise ValueError(
            "The model has no supported person or ball class"
        )

    writer = cv2.VideoWriter(
        str(output / "annotated.mp4"),
        cv2.VideoWriter_fourcc(*"mp4v"),
        effective_fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError("Could not open the annotated video writer")

    engine = ActionEngine()
    all_events: list[dict[str, object]] = []
    object_counts: Counter[str] = Counter()
    frame_count = 0
    interrupted = False
    started_at = time.perf_counter()
    last_progress_at = 0.0

    inference_options: dict[str, Any] = {
        "source": str(video),
        "stream": True,
        "persist": True,
        "tracker": tracker,
        "classes": class_ids,
        "conf": confidence,
        "imgsz": image_size,
        "vid_stride": stride,
        "verbose": False,
    }
    if device:
        inference_options["device"] = device

    csv_path = output / "objects.csv"
    try:
        with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            csv_writer = csv.DictWriter(
                csv_file,
                fieldnames=[
                    "frame",
                    "timestamp_seconds",
                    "track_id",
                    "class_name",
                    "confidence",
                    "x1",
                    "y1",
                    "x2",
                    "y2",
                    "action",
                ],
            )
            csv_writer.writeheader()

            try:
                for result in model.track(**inference_options):
                    timestamp = frame_count / effective_fps
                    detections = _extract_detections(result, model.names)
                    motion_states, events = engine.update(timestamp, detections)
                    all_events.extend(event.to_dict() for event in events)

                    frame = result.orig_img.copy()
                    for detection in detections:
                        object_counts[detection.class_name] += 1
                        action = motion_states.get(detection.track_id, "")
                        _draw_detection(frame, detection, action)
                        csv_writer.writerow(
                            {
                                "frame": frame_count,
                                "timestamp_seconds": f"{timestamp:.3f}",
                                "track_id": detection.track_id,
                                "class_name": detection.class_name,
                                "confidence": f"{detection.confidence:.4f}",
                                "x1": f"{detection.x1:.1f}",
                                "y1": f"{detection.y1:.1f}",
                                "x2": f"{detection.x2:.1f}",
                                "y2": f"{detection.y2:.1f}",
                                "action": action,
                            }
                        )
                    writer.write(frame)
                    frame_count += 1
                    now = time.perf_counter()
                    if now - last_progress_at >= 0.5 or frame_count == expected_frames:
                        _print_progress(
                            frame_count,
                            expected_frames,
                            started_at,
                            completed=frame_count == expected_frames,
                        )
                        last_progress_at = now
                    if max_frames is not None and frame_count >= max_frames:
                        break
            except KeyboardInterrupt:
                interrupted = True
                print("\nStopped by user; preserving partial results.")
    finally:
        writer.release()

    (output / "events.json").write_text(
        json.dumps(all_events, indent=2), encoding="utf-8"
    )
    summary = {
        "input": str(video.resolve()),
        "model": model_name,
        "frames_processed": frame_count,
        "source_fps": fps,
        "source_frames": source_frames,
        "processing_stride": stride,
        "interrupted": interrupted,
        "detection_rows": dict(object_counts),
        "event_counts": dict(Counter(event["event_type"] for event in all_events)),
        "limitations": [
            "Actions are image-space heuristic candidates, not confirmed football events.",
            "Generic weights often miss the small football in a wide-area recording.",
            "Pitch calibration and team classification are not included.",
        ],
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    if frame_count and frame_count < expected_frames and not interrupted:
        _print_progress(frame_count, frame_count, started_at, completed=True)
    print(f"Results written to {output.resolve()}")


def _video_metadata(video: Path) -> tuple[float, int, int, int]:
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open input video: {video}")
        fps = capture.get(cv2.CAP_PROP_FPS)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    if fps <= 0 or width <= 0 or height <= 0:
        raise ValueError("Input video has invalid FPS or dimensions")
    return fps, width, height, frame_count


def _print_progress(
    current: int, total: int, started_at: float, *, completed: bool
) -> None:
    elapsed = time.perf_counter() - started_at
    rate = current / elapsed if elapsed > 0 else 0
    remaining = (total - current) / rate if rate > 0 else 0
    print(
        f"\rFrames {current}/{total} ({current / total:.0%}) | "
        f"{rate:.1f} FPS | elapsed {elapsed:.0f}s | ETA {remaining:.0f}s",
        end="\n" if completed else "",
        flush=True,
    )


def _wanted_class_ids(names: dict[int, str]) -> list[int]:
    return [
        class_id
        for class_id, name in names.items()
        if name
        in {
            "person",
            "player",
            "goalkeeper",
            "referee",
            "sports ball",
            "ball",
        }
    ]


def _extract_detections(result: Any, names: dict[int, str]) -> list[Detection]:
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return []

    coordinates = boxes.xyxy.cpu().tolist()
    confidences = boxes.conf.cpu().tolist()
    class_ids = boxes.cls.int().cpu().tolist()
    track_ids = (
        boxes.id.int().cpu().tolist()
        if boxes.id is not None
        else [-1] * len(coordinates)
    )

    return [
        Detection(
            track_id=track_id,
            class_name=_normalized_class_name(names[class_id]),
            confidence=box_confidence,
            x1=box[0],
            y1=box[1],
            x2=box[2],
            y2=box[3],
        )
        for box, box_confidence, class_id, track_id in zip(
            coordinates, confidences, class_ids, track_ids, strict=True
        )
    ]


def _normalized_class_name(class_name: str) -> str:
    if class_name == "ball":
        return "sports ball"
    if class_name in {"player", "goalkeeper", "referee"}:
        return "person"
    return class_name


def _draw_detection(frame: Any, detection: Detection, action: str) -> None:
    color = (30, 200, 30) if detection.class_name == "person" else (30, 180, 255)
    top_left = (int(detection.x1), int(detection.y1))
    bottom_right = (int(detection.x2), int(detection.y2))
    cv2.rectangle(frame, top_left, bottom_right, color, 2)
    track = f" #{detection.track_id}" if detection.track_id >= 0 else ""
    label = f"{detection.class_name}{track} {detection.confidence:.2f}"
    if action:
        label += f" {action}"
    cv2.putText(
        frame,
        label,
        (top_left[0], max(20, top_left[1] - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        color,
        2,
        cv2.LINE_AA,
    )


if __name__ == "__main__":
    main()
