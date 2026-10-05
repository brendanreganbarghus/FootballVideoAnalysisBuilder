"""Rule: the persistent crop-prediction cache returns identical boxes.

A rerun of the ball tracker on cached detections may reuse the close-up YOLO
crop predictions it already computed, but only for byte-identical crop
batches under the same model and options, so tracker output is unchanged.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np

from football_poc.ball import predict_cache


class _Box:
    def __init__(self, cls, xyxy, conf):
        self.cls = [cls]
        self.xyxy = [xyxy]
        self.conf = [conf]


class _Result:
    def __init__(self, boxes):
        self.boxes = boxes
        self.names = {32: "sports ball"}


class _FakeModel:
    names = {32: "sports ball"}

    def __init__(self):
        self.calls = 0

    def predict(self, source, **options):
        self.calls += 1
        return [
            _Result([_Box(32, [1.5, 2.25, 3.0, 4.75], 0.625 + index)])
            for index, _ in enumerate(source)
        ]


def _predictor(tmp_path: Path, monkeypatch) -> tuple[object, _FakeModel]:
    monkeypatch.setitem(
        sys.modules, "ultralytics", types.SimpleNamespace(__version__="test")
    )
    weights = tmp_path / "model.pt"
    weights.write_bytes(b"weights")
    fake = _FakeModel()
    predictor = predict_cache.CachedCropPredictor(
        fake, weights, tmp_path / predict_cache.CROP_CACHE_FILE_NAME
    )
    return predictor, fake


def _boxes(results):
    return [
        [
            (int(b.cls[0]), [float(v) for v in b.xyxy[0]], float(b.conf[0]))
            for b in r.boxes
        ]
        for r in results
    ]


def test_crop_prediction_cache_hit_returns_identical_boxes_20261005T171500000Z(
    tmp_path, monkeypatch
):
    predictor, fake = _predictor(tmp_path, monkeypatch)
    crops = [np.zeros((8, 8, 3), np.uint8), np.ones((6, 4, 3), np.uint8)]
    first = _boxes(predictor.predict(crops, imgsz=640, conf=0.05, verbose=False))
    second = predictor.predict(crops, imgsz=640, conf=0.05, verbose=True)
    assert fake.calls == 1
    assert _boxes(second) == first
    assert second[0].names[32] == "sports ball"


def test_crop_prediction_cache_misses_on_changed_pixels_or_options_20261005T171500000Z(
    tmp_path, monkeypatch
):
    predictor, fake = _predictor(tmp_path, monkeypatch)
    crops = [np.zeros((8, 8, 3), np.uint8)]
    predictor.predict(crops, imgsz=640, conf=0.05)
    changed = [np.zeros((8, 8, 3), np.uint8)]
    changed[0][0, 0, 0] = 1
    predictor.predict(changed, imgsz=640, conf=0.05)
    predictor.predict(crops, imgsz=1280, conf=0.05)
    assert fake.calls == 3


def test_crop_model_is_uncached_without_cache_directory_20261005T171500000Z(
    monkeypatch,
):
    sentinel = object()
    monkeypatch.setitem(
        sys.modules,
        "ultralytics",
        types.SimpleNamespace(YOLO=lambda path: sentinel, __version__="test"),
    )
    predict_cache.set_crop_cache_directory(None)
    assert predict_cache.load_ball_crop_model(Path("model.pt")) is sentinel
