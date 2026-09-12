from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import cv2
from ultralytics import YOLO

from football_poc.innovation_day_snapshot.benchmark import BenchmarkManifest


@dataclass(frozen=True)
class Detection:
    track_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class Tile:
    x1: int
    y1: int
    x2: int
    y2: int


def horizontal_tiles(
    width: int,
    height: int,
    *,
    tile_width: int,
    overlap: float,
) -> tuple[Tile, ...]:
    if width <= 0 or height <= 0:
        raise ValueError("Frame dimensions must be greater than zero")
    if tile_width <= 0:
        raise ValueError("Tile width must be greater than zero")
    if not 0 <= overlap < 0.9:
        raise ValueError("Tile overlap must be at least 0 and less than 0.9")
    if tile_width >= width:
        return (Tile(0, 0, width, height),)
    step = max(1, round(tile_width * (1 - overlap)))
    starts = list(range(0, width - tile_width + 1, step))
    final_start = width - tile_width
    if starts[-1] != final_start:
        starts.append(final_start)
    return tuple(Tile(x, 0, x + tile_width, height) for x in starts)


def class_aware_nms(
    detections: Iterable[Detection],
    *,
    iou_threshold: float = 0.5,
) -> list[Detection]:
    kept: list[Detection] = []
    by_class: dict[str, list[Detection]] = {}
    for detection in detections:
        by_class.setdefault(detection.class_name, []).append(detection)
    for candidates in by_class.values():
        pending = sorted(
            candidates,
            key=lambda item: item.confidence,
            reverse=True,
        )
        while pending:
            best = pending.pop(0)
            kept.append(best)
            pending = [
                candidate
                for candidate in pending
                if _intersection_over_union(best, candidate) < iou_threshold
            ]
    return sorted(kept, key=lambda item: item.confidence, reverse=True)


def run_detection_cache(
    *,
    manifest_path: Path,
    output: Path,
    model_name: str,
    confidence: float,
    image_size: int,
    device: str | None,
    stride: int,
    tile_width: int,
    overlap: float,
    nms_iou: float,
) -> Path:
    manifest = BenchmarkManifest.load(manifest_path)
    _validate_run_options(
        confidence=confidence,
        image_size=image_size,
        stride=stride,
        tile_width=tile_width,
        overlap=overlap,
        nms_iou=nms_iou,
    )
    output.mkdir(parents=True, exist_ok=True)
    cache_path = output / "detections.jsonl"
    metadata = {
        "type": "metadata",
        "manifest_sha256": manifest.sha256,
        "video": str(manifest.video),
        "model": model_name,
        "confidence": confidence,
        "image_size": image_size,
        "stride": stride,
        "tile_width": tile_width,
        "overlap": overlap,
        "nms_iou": nms_iou,
        "detector_implementation": "innovation_showcase_sequential_v1",
    }
    cache_path.write_text(json.dumps(metadata) + "\n", encoding="utf-8")
    pending_frames = list(
        range(manifest.start_frame, manifest.end_frame, stride)
    )
    print(
        f"Loading {model_name}. Caching {len(pending_frames)} new Innovation "
        f"frames with horizontal {tile_width}px tiles."
    )
    model = YOLO(model_name)
    class_ids = _wanted_class_ids(model.names)
    if not class_ids:
        raise ValueError("The model has no supported person or ball class")
    capture = cv2.VideoCapture(str(manifest.video))
    if not capture.isOpened():
        raise ValueError(f"Could not open benchmark video: {manifest.video}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    tiles = horizontal_tiles(
        width,
        height,
        tile_width=tile_width,
        overlap=overlap,
    )
    capture.set(cv2.CAP_PROP_POS_FRAMES, pending_frames[0])
    next_source_frame = pending_frames[0]
    started_at = time.perf_counter()
    try:
        with cache_path.open("a", encoding="utf-8") as cache:
            for completed, source_frame in enumerate(pending_frames, start=1):
                while next_source_frame < source_frame:
                    if not capture.grab():
                        raise RuntimeError(
                            f"Could not skip to source frame {source_frame} "
                            f"in {manifest.video}"
                        )
                    next_source_frame += 1
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError(
                        f"Could not read source frame {source_frame} from "
                        f"{manifest.video}"
                    )
                next_source_frame = source_frame + 1
                crops = [
                    frame[tile.y1 : tile.y2, tile.x1 : tile.x2]
                    for tile in tiles
                ]
                options: dict[str, Any] = {
                    "source": crops,
                    "classes": class_ids,
                    "conf": confidence,
                    "imgsz": image_size,
                    "verbose": False,
                }
                if device:
                    options["device"] = device
                results = model.predict(**options)
                detections = class_aware_nms(
                    (
                        _offset_detection(detection, tile)
                        for tile, result in zip(tiles, results, strict=True)
                        for detection in _extract_detections(
                            result,
                            model.names,
                        )
                    ),
                    iou_threshold=nms_iou,
                )
                cache.write(
                    json.dumps(
                        {
                            "type": "frame",
                            "source_frame": source_frame,
                            "clip_seconds": round(
                                (source_frame - manifest.start_frame)
                                / manifest.fps,
                                3,
                            ),
                            "detections": [
                                asdict(detection)
                                for detection in detections
                            ],
                        }
                    )
                    + "\n"
                )
                cache.flush()
                _print_progress(
                    completed,
                    len(pending_frames),
                    started_at,
                )
    finally:
        capture.release()
    _write_summary(output, manifest, metadata, cache_path)
    print(f"Detection cache written to {cache_path.resolve()}")
    return cache_path


def _normalized_class_name(class_name: str) -> str:
    if class_name == "ball":
        return "sports ball"
    if class_name in {"player", "goalkeeper", "referee"}:
        return "person"
    return class_name


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


def _extract_detections(
    result: Any,
    names: dict[int, str],
) -> list[Detection]:
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
            coordinates,
            confidences,
            class_ids,
            track_ids,
            strict=True,
        )
    ]


def _offset_detection(detection: Detection, tile: Tile) -> Detection:
    return Detection(
        track_id=-1,
        class_name=detection.class_name,
        confidence=detection.confidence,
        x1=detection.x1 + tile.x1,
        y1=detection.y1 + tile.y1,
        x2=detection.x2 + tile.x1,
        y2=detection.y2 + tile.y1,
    )


def _intersection_over_union(
    first: Detection,
    second: Detection,
) -> float:
    intersection_width = max(
        0.0,
        min(first.x2, second.x2) - max(first.x1, second.x1),
    )
    intersection_height = max(
        0.0,
        min(first.y2, second.y2) - max(first.y1, second.y1),
    )
    intersection = intersection_width * intersection_height
    first_area = max(0.0, first.x2 - first.x1) * max(
        0.0,
        first.y2 - first.y1,
    )
    second_area = max(0.0, second.x2 - second.x1) * max(
        0.0,
        second.y2 - second.y1,
    )
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def _print_progress(
    current: int,
    total: int,
    started_at: float,
) -> None:
    elapsed = time.perf_counter() - started_at
    rate = current / elapsed if elapsed > 0 else 0
    remaining = (total - current) / rate if rate > 0 else 0
    print(
        f"\rFrames {current}/{total} ({current / total:.0%}) | "
        f"{rate:.1f} FPS | elapsed {elapsed:.0f}s | ETA {remaining:.0f}s",
        end="\n" if current == total else "",
        flush=True,
    )


def _write_summary(
    output: Path,
    manifest: BenchmarkManifest,
    metadata: dict[str, Any],
    cache_path: Path,
) -> None:
    frame_count = 0
    frames_with_ball = 0
    frames_with_people = 0
    detection_counts: Counter[str] = Counter()
    for line in cache_path.read_text(encoding="utf-8").splitlines()[1:]:
        record = json.loads(line)
        if record.get("type") != "frame":
            continue
        frame_count += 1
        classes = [
            str(detection["class_name"])
            for detection in record.get("detections", [])
        ]
        detection_counts.update(classes)
        frames_with_ball += "sports ball" in classes
        frames_with_people += "person" in classes
    expected_frames = math.ceil(
        manifest.source_frame_count / int(metadata["stride"])
    )
    summary = {
        "manifest": str(manifest.path),
        "cache": str(cache_path.resolve()),
        "configuration": metadata,
        "expected_frames": expected_frames,
        "processed_frames": frame_count,
        "complete": frame_count == expected_frames,
        "detection_counts": dict(sorted(detection_counts.items())),
        "frames_with_people": frames_with_people,
        "frames_with_ball": frames_with_ball,
        "ball_frame_coverage": (
            round(frames_with_ball / frame_count, 4) if frame_count else 0.0
        ),
        "next_stage": (
            "Innovation player tracking and event inference consume this "
            "cache without evaluation labels."
        ),
    }
    (output / "detection-summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )


def _validate_run_options(
    *,
    confidence: float,
    image_size: int,
    stride: int,
    tile_width: int,
    overlap: float,
    nms_iou: float,
) -> None:
    if not 0 < confidence <= 1:
        raise ValueError("--confidence must be greater than 0 and at most 1")
    if image_size < 32:
        raise ValueError("--image-size must be at least 32")
    if stride < 1:
        raise ValueError("--stride must be at least 1")
    horizontal_tiles(1, 1, tile_width=tile_width, overlap=overlap)
    if not 0 <= nms_iou <= 1:
        raise ValueError("--nms-iou must be between 0 and 1")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the frozen sequential Innovation detector."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--confidence", type=float, required=True)
    parser.add_argument("--image-size", type=int, required=True)
    parser.add_argument("--device", default=None)
    parser.add_argument("--stride", type=int, required=True)
    parser.add_argument("--tile-width", type=int, required=True)
    parser.add_argument("--overlap", type=float, required=True)
    parser.add_argument("--nms-iou", type=float, default=0.5)
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
        overlap=args.overlap,
        nms_iou=args.nms_iou,
    )


if __name__ == "__main__":
    main()
