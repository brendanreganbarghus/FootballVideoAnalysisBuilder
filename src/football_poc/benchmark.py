from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import cv2
from ultralytics import YOLO

from football_poc.actions import Detection
from football_poc.cli import _extract_detections, _print_progress, _wanted_class_ids


@dataclass(frozen=True)
class CameraStream:
    camera_id: str
    video: Path
    time_offset_seconds: float
    calibration: Path | None


@dataclass(frozen=True)
class BenchmarkManifest:
    path: Path
    video: Path
    fps: float
    start_frame: int
    end_frame: int
    camera_streams: tuple[CameraStream, ...]
    primary_camera_id: str
    half: int | None
    source_start_seconds: float
    starts_at_kickoff: bool

    @classmethod
    def load(cls, path: str | Path) -> BenchmarkManifest:
        manifest_path = Path(path)
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Benchmark manifest does not exist: {manifest_path}")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Benchmark manifest must be a JSON object")
        _reject_evaluation_inputs(payload)

        camera_streams, primary_camera_id = _load_camera_streams(payload)
        video = next(
            stream.video
            for stream in camera_streams
            if stream.camera_id == primary_camera_id
        )
        fps = float(payload.get("fps", 0))
        start_frame = int(payload.get("start_frame", -1))
        end_frame = int(payload.get("end_frame", -1))
        if fps <= 0:
            raise ValueError("Benchmark FPS must be greater than zero")
        if start_frame < 0 or end_frame <= start_frame:
            raise ValueError("Benchmark frame range is invalid")

        return cls(
            path=manifest_path.resolve(),
            video=video.resolve(),
            fps=fps,
            start_frame=start_frame,
            end_frame=end_frame,
            camera_streams=camera_streams,
            primary_camera_id=primary_camera_id,
            half=(
                int(payload["half"])
                if payload.get("half") is not None
                else None
            ),
            source_start_seconds=float(
                payload.get("start_seconds", start_frame / fps)
            ),
            starts_at_kickoff=bool(
                payload.get(
                    "starts_at_kickoff",
                    float(payload.get("start_seconds", start_frame / fps))
                    <= 5.0,
                )
            ),
        )

    @property
    def source_frame_count(self) -> int:
        return self.end_frame - self.start_frame

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


def _reject_evaluation_inputs(payload: dict[str, Any]) -> None:
    fields = (
        "actions",
        "action_counts",
        "annotations",
        "events",
        "labels",
        "ball_ground_truth",
        "manual_reference",
    )
    present = [
        field
        for field in fields
        if payload.get(field) not in (None, "", [], {})
    ]
    if present:
        raise ValueError(
            "Runtime manifest must not contain evaluation inputs: "
            + ", ".join(present)
        )


def _load_camera_streams(
    payload: dict[str, Any],
) -> tuple[tuple[CameraStream, ...], str]:
    stream_payloads = payload.get("camera_streams")
    if stream_payloads is None:
        stream_payloads = [
            {
                "camera_id": "primary",
                "video": payload.get("video", ""),
                "time_offset_seconds": 0,
            }
        ]
    if not isinstance(stream_payloads, list) or not stream_payloads:
        raise ValueError("Benchmark camera_streams must be a non-empty list")

    streams: list[CameraStream] = []
    camera_ids: set[str] = set()
    for raw_stream in stream_payloads:
        if not isinstance(raw_stream, dict):
            raise ValueError("Each benchmark camera stream must be a JSON object")
        camera_id = str(raw_stream.get("camera_id", "")).strip()
        if not camera_id:
            raise ValueError("Each benchmark camera stream needs a camera_id")
        if camera_id in camera_ids:
            raise ValueError(f"Duplicate benchmark camera_id: {camera_id}")
        video = Path(str(raw_stream.get("video", "")))
        if not video.is_file():
            raise FileNotFoundError(f"Benchmark video does not exist: {video}")
        offset = float(raw_stream.get("time_offset_seconds", 0))
        if not math.isfinite(offset):
            raise ValueError("Camera time_offset_seconds must be finite")
        calibration_value = raw_stream.get("calibration")
        calibration = Path(str(calibration_value)) if calibration_value else None
        if calibration is not None and not calibration.is_file():
            raise FileNotFoundError(
                f"Camera calibration does not exist: {calibration}"
            )
        streams.append(
            CameraStream(
                camera_id=camera_id,
                video=video.resolve(),
                time_offset_seconds=offset,
                calibration=calibration.resolve() if calibration else None,
            )
        )
        camera_ids.add(camera_id)

    primary_camera_id = str(
        payload.get("primary_camera_id", streams[0].camera_id)
    ).strip()
    if primary_camera_id not in camera_ids:
        raise ValueError(
            f"Primary camera is not declared in camera_streams: {primary_camera_id}"
        )
    return tuple(streams), primary_camera_id


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


def grid_tiles(
    width: int,
    height: int,
    *,
    tile_width: int,
    tile_height: int | None,
    overlap: float,
) -> tuple[Tile, ...]:
    if tile_height is None or tile_height >= height:
        return horizontal_tiles(
            width,
            height,
            tile_width=tile_width,
            overlap=overlap,
        )
    if tile_height <= 0:
        raise ValueError("Tile height must be greater than zero")
    horizontal = horizontal_tiles(
        width,
        height,
        tile_width=tile_width,
        overlap=overlap,
    )
    step = max(1, round(tile_height * (1 - overlap)))
    starts = list(range(0, height - tile_height + 1, step))
    final_start = height - tile_height
    if starts[-1] != final_start:
        starts.append(final_start)
    return tuple(
        Tile(tile.x1, y, tile.x2, y + tile_height)
        for y in starts
        for tile in horizontal
    )


def class_aware_nms(
    detections: Iterable[Detection], *, iou_threshold: float = 0.5
) -> list[Detection]:
    if not 0 <= iou_threshold <= 1:
        raise ValueError("NMS IoU threshold must be between 0 and 1")
    kept: list[Detection] = []
    by_class: dict[str, list[Detection]] = {}
    for detection in detections:
        by_class.setdefault(detection.class_name, []).append(detection)

    for candidates in by_class.values():
        pending = sorted(candidates, key=lambda item: item.confidence, reverse=True)
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
    tile_height: int | None,
    overlap: float,
    nms_iou: float,
    max_frames: int | None,
    frame_batch_size: int = 4,
    reuse_cache: bool = False,
) -> Path:
    manifest = BenchmarkManifest.load(manifest_path)
    _validate_run_options(
        confidence=confidence,
        image_size=image_size,
        stride=stride,
        tile_width=tile_width,
        tile_height=tile_height,
        overlap=overlap,
        nms_iou=nms_iou,
        max_frames=max_frames,
        frame_batch_size=frame_batch_size,
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
        "tile_height": tile_height,
        "overlap": overlap,
        "nms_iou": nms_iou,
    }
    processed = _prepare_cache(
        cache_path,
        metadata,
        reuse_cache=reuse_cache,
    )
    expected_frames = math.ceil(manifest.source_frame_count / stride)
    remaining_frames = max(0, expected_frames - len(processed))
    if max_frames is not None:
        remaining_frames = min(remaining_frames, max_frames)
    if remaining_frames == 0:
        _write_summary(output, manifest, metadata, cache_path)
        print(f"Detection cache is already complete: {cache_path.resolve()}")
        return cache_path

    print(
        f"Loading {model_name}. Caching {remaining_frames} new benchmark frames "
        f"with {tile_width}x{tile_height or 'full-height'}px tiles."
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
    tiles = grid_tiles(
        width,
        height,
        tile_width=tile_width,
        tile_height=tile_height,
        overlap=overlap,
    )
    pending_frames = [
        frame
        for frame in range(manifest.start_frame, manifest.end_frame, stride)
        if frame not in processed
    ][:remaining_frames]
    capture.set(cv2.CAP_PROP_POS_FRAMES, pending_frames[0])
    next_source_frame = pending_frames[0]
    started_at = time.perf_counter()
    completed = 0

    try:
        with cache_path.open("a", encoding="utf-8") as cache:
            for offset in range(0, len(pending_frames), frame_batch_size):
                source_frames = pending_frames[offset : offset + frame_batch_size]
                frames: list[tuple[int, np.ndarray]] = []
                for source_frame in source_frames:
                    while next_source_frame < source_frame:
                        if not capture.grab():
                            raise RuntimeError(
                                f"Could not skip to source frame {source_frame} in "
                                f"{manifest.video}"
                            )
                        next_source_frame += 1
                    ok, frame = capture.read()
                    if not ok:
                        raise RuntimeError(
                            f"Could not read source frame {source_frame} from "
                            f"{manifest.video}"
                        )
                    next_source_frame = source_frame + 1
                    frames.append((source_frame, frame))
                crops = [
                    frame[tile.y1 : tile.y2, tile.x1 : tile.x2]
                    for _, frame in frames
                    for tile in tiles
                ]
                options: dict[str, Any] = {
                    "source": crops,
                    "classes": class_ids,
                    "conf": confidence,
                    "imgsz": image_size,
                    "verbose": False,
                    "batch": len(crops),
                }
                if device:
                    options["device"] = device
                results = model.predict(**options)
                detections_by_frame: dict[int, list[Detection]] = defaultdict(list)
                owners = [
                    (source_frame, tile)
                    for source_frame, _ in frames
                    for tile in tiles
                ]
                for (source_frame, tile), result in zip(
                    owners, results, strict=True
                ):
                    detections_by_frame[source_frame].extend(
                        _offset_detection(detection, tile)
                        for detection in _extract_detections(result, model.names)
                    )
                for source_frame, _ in frames:
                    detections = class_aware_nms(
                        detections_by_frame[source_frame],
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
                                    asdict(detection) for detection in detections
                                ],
                            }
                        )
                        + "\n"
                    )
                    completed += 1
                    _print_progress(
                        completed,
                        remaining_frames,
                        started_at,
                        completed=completed == remaining_frames,
                    )
                cache.flush()
    except KeyboardInterrupt:
        print("\nStopped by user; cached frames have been preserved.")
    finally:
        capture.release()

    elapsed_seconds = time.perf_counter() - started_at
    _write_summary(
        output,
        manifest,
        metadata,
        cache_path,
        run_metrics={
            "processed_frames": completed,
            "elapsed_seconds": round(elapsed_seconds, 3),
            "frames_per_second": round(completed / elapsed_seconds, 3)
            if elapsed_seconds > 0
            else None,
            "cold_path": len(processed) == 0,
        },
    )
    print(f"Detection cache written to {cache_path.resolve()}")
    return cache_path


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


def _intersection_over_union(first: Detection, second: Detection) -> float:
    intersection_width = max(0.0, min(first.x2, second.x2) - max(first.x1, second.x1))
    intersection_height = max(
        0.0, min(first.y2, second.y2) - max(first.y1, second.y1)
    )
    intersection = intersection_width * intersection_height
    first_area = max(0.0, first.x2 - first.x1) * max(0.0, first.y2 - first.y1)
    second_area = max(0.0, second.x2 - second.x1) * max(
        0.0, second.y2 - second.y1
    )
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def _prepare_cache(
    cache_path: Path,
    metadata: dict[str, Any],
    *,
    reuse_cache: bool,
) -> set[int]:
    if not cache_path.exists() or not reuse_cache:
        cache_path.write_text(json.dumps(metadata) + "\n", encoding="utf-8")
        return set()

    lines = cache_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"Detection cache is empty: {cache_path}")
    existing_metadata = json.loads(lines[0])
    if existing_metadata != metadata:
        raise ValueError(
            "Detection cache settings differ from this run. Use a new output "
            "directory or restore the original settings."
        )
    processed: set[int] = set()
    for line in lines[1:]:
        record = json.loads(line)
        if record.get("type") == "frame":
            processed.add(int(record["source_frame"]))
    return processed


def _write_summary(
    output: Path,
    manifest: BenchmarkManifest,
    metadata: dict[str, Any],
    cache_path: Path,
    run_metrics: dict[str, Any] | None = None,
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

    expected_frames = math.ceil(manifest.source_frame_count / int(metadata["stride"]))
    summary = {
        "manifest": str(manifest.path),
        "cache": str(cache_path.resolve()),
        "configuration": metadata,
        "last_run": run_metrics,
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
            "Tracking and event inference consume this cache without "
            "evaluation labels."
        ),
    }
    (output / "detection-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


def _validate_run_options(
    *,
    confidence: float,
    image_size: int,
    stride: int,
    tile_width: int,
    tile_height: int | None,
    overlap: float,
    nms_iou: float,
    max_frames: int | None,
    frame_batch_size: int,
) -> None:
    if not 0 < confidence <= 1:
        raise ValueError("--confidence must be greater than 0 and at most 1")
    if image_size < 32:
        raise ValueError("--image-size must be at least 32")
    if stride < 1:
        raise ValueError("--stride must be at least 1")
    grid_tiles(
        1,
        1,
        tile_width=tile_width,
        tile_height=tile_height,
        overlap=overlap,
    )
    if not 0 <= nms_iou <= 1:
        raise ValueError("--nms-iou must be between 0 and 1")
    if max_frames is not None and max_frames < 1:
        raise ValueError("--max-frames must be at least 1")
    if frame_batch_size < 1:
        raise ValueError("--frame-batch-size must be at least 1")
