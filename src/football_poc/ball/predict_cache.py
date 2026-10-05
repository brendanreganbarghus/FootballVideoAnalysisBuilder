"""Persistent cache for the ball tracker's close-up YOLO crop predictions.

The ball tracker runs YOLO on small crops around where it expects the ball.
Those crops depend only on the raw video and the tracker's own state, so a
rerun after a tracker change asks for many identical crops again. This cache
stores each predict batch under a hash of the exact crop pixels, inference
size, confidence, model file and ultralytics version. A hit returns the stored
boxes; a miss runs the model on the identical batch and stores the result.

The whole batch is the cache unit because YOLO letterboxes a batch
differently when its images have different shapes, so splitting a batch could
change detections. Output is therefore identical with or without the cache.
The cache holds raw-video detector output only; no labels or review data.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np

CROP_CACHE_FILE_NAME = "ball-crop-predictions.sqlite"

_active_directory: Path | None = None
_model_hashes: dict[str, str] = {}


def set_crop_cache_directory(directory: Path | None) -> None:
    global _active_directory
    _active_directory = Path(directory) if directory is not None else None


def _model_sha256(model_path: Path) -> str:
    key = str(Path(model_path).resolve())
    if key not in _model_hashes:
        digest = hashlib.sha256()
        with Path(model_path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        _model_hashes[key] = digest.hexdigest()
    return _model_hashes[key]


class _CachedBox:
    __slots__ = ("cls", "xyxy", "conf")

    def __init__(self, cls: int, xyxy: list[float], conf: float) -> None:
        self.cls = [cls]
        self.xyxy = [tuple(xyxy)]
        self.conf = [conf]


class _CachedResult:
    __slots__ = ("boxes", "names")

    def __init__(self, boxes: list[_CachedBox], names: dict[int, str]) -> None:
        self.boxes = boxes
        self.names = names


class CachedCropPredictor:
    """Wraps a YOLO model; ``predict`` matches the ball tracker's call shape."""

    def __init__(self, model: Any, model_path: Path, database: Path) -> None:
        import ultralytics

        self._model = model
        self._identity = (
            f"{_model_sha256(model_path)}|{ultralytics.__version__}"
        )
        self.names = dict(model.names)
        database.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(database))
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS predictions "
            "(key TEXT PRIMARY KEY, boxes TEXT NOT NULL)"
        )
        self._connection.commit()
        self.hits = 0
        self.misses = 0

    def _key(self, crops: list[np.ndarray], options: dict[str, Any]) -> str:
        digest = hashlib.sha256(self._identity.encode())
        digest.update(
            json.dumps(
                {k: v for k, v in sorted(options.items()) if k != "verbose"},
                sort_keys=True,
                default=str,
            ).encode()
        )
        for crop in crops:
            array = np.ascontiguousarray(crop)
            digest.update(f"{array.shape}|{array.dtype}".encode())
            digest.update(array.tobytes())
        return digest.hexdigest()

    def predict(self, source: Any, **options: Any) -> list[Any]:
        crops = list(source) if isinstance(source, (list, tuple)) else [source]
        key = self._key(crops, options)
        row = self._connection.execute(
            "SELECT boxes FROM predictions WHERE key = ?", (key,)
        ).fetchone()
        if row is not None:
            self.hits += 1
            return [
                _CachedResult(
                    [_CachedBox(int(c), list(b), float(f)) for c, b, f in boxes],
                    self.names,
                )
                for boxes in json.loads(row[0])
            ]
        self.misses += 1
        results = self._model.predict(source, **options)
        stored = [
            [
                [
                    int(box.cls[0]),
                    [float(value) for value in box.xyxy[0]],
                    float(box.conf[0]),
                ]
                for box in result.boxes
            ]
            for result in results
        ]
        self._connection.execute(
            "INSERT OR REPLACE INTO predictions (key, boxes) VALUES (?, ?)",
            (key, json.dumps(stored)),
        )
        self._connection.commit()
        return results


def load_ball_crop_model(model_path: Path) -> Any:
    """Load YOLO for crop checks, cached when a cache directory is active."""
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    if _active_directory is None:
        return model
    return CachedCropPredictor(
        model,
        Path(model_path),
        _active_directory / CROP_CACHE_FILE_NAME,
    )
