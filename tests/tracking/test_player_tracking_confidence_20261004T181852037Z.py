"""Timestamped player-tracking confidence rule tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import football_poc.player_tracking as player_tracking

ROOT = Path(__file__).resolve().parents[2]


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "process_alfheim_segment_for_confidence_rule",
        ROOT / "scripts" / "process-alfheim-segment.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_player_tracking_keeps_every_detector_box_20261004T181852037Z() -> None:
    runner = _load_runner()
    assert (
        runner.PLAYER_TRACKING_CONFIDENCE
        == runner.LIVE_DETECTOR_PROFILE["confidence"]
        == 0.10
    )
    source = (ROOT / "scripts" / "process-alfheim-segment.py").read_text(
        encoding="utf-8"
    )
    assert "str(PLAYER_TRACKING_CONFIDENCE)" in source


def test_half_hidden_player_box_reaches_tracking_20261004T181852038Z() -> None:
    record = {
        "source_frame": 10,
        "clip_seconds": 0.4,
        "detections": [
            {"class_name": "person", "confidence": 0.14,
             "x1": 100, "y1": 200, "x2": 130, "y2": 280},
            {"class_name": "person", "confidence": 0.05,
             "x1": 300, "y1": 200, "x2": 330, "y2": 280},
        ],
    }
    points = player_tracking._player_points(record, 0.10)
    assert [point.confidence for point in points] == [0.14]
