"""Cached detections must come from the pinned YOLO26n detector."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "process_alfheim_segment_for_yolo26_cache_rule",
        ROOT / "scripts" / "process-alfheim-segment.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _cache(tmp_path: Path, model: str) -> Path:
    path = tmp_path / "detections.jsonl"
    path.write_text(
        json.dumps({"type": "metadata", "model": model}) + "\n",
        encoding="utf-8",
    )
    return path


def test_yolo11_detection_cache_is_rejected_20261005T014345185Z(
    tmp_path: Path,
) -> None:
    runner = _load_runner()
    cache = _cache(tmp_path, r"C:\models\ultralytics-yolo11n\yolo11n.pt")
    with pytest.raises(ValueError, match="yolo26n"):
        runner.require_yolo26_detection_cache(cache)


def test_yolo26_detection_cache_is_accepted_20261005T014345186Z(
    tmp_path: Path,
) -> None:
    runner = _load_runner()
    runner.require_yolo26_detection_cache(
        _cache(tmp_path, r"D:\models\yolo26n.pt")
    )
