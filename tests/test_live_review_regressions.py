from __future__ import annotations

import json
from pathlib import Path

import pytest

from football_poc.event_comparison import compare_manual_events


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALFHEIM_ROOT = PROJECT_ROOT / "benchmarks" / "alfheim"
REGISTRY = ALFHEIM_ROOT / "live-regressions.json"


def registered_segments() -> list[str]:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert payload["workflow"] == "live_iteration_25"
    return [entry["segment"] for entry in payload["segments"]]


@pytest.mark.parametrize("segment", registered_segments())
def test_published_live_segment_matches_current_engine(segment: str) -> None:
    root = ALFHEIM_ROOT / "generated" / segment
    prepared = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    forbidden = {
        "annotations",
        "ball_ground_truth",
        "events",
        "ground_truth",
        "labels",
        "manual_reference",
    }
    assert forbidden.isdisjoint(prepared)

    live = root / "live"
    ball_tracks = json.loads(
        (live / "analytics-cache" / "ball-tracks.json").read_text(
            encoding="utf-8"
        )
    )
    source = json.dumps(ball_tracks.get("source", {})).lower()
    assert "bac" not in source
    assert "ground_truth" not in source
    assert "provider_coordinates" not in source

    manual = json.loads(
        (live / "manual-reference.json").read_text(encoding="utf-8")
    )["events"]
    predicted = json.loads(
        (live / "analytics-data" / "predicted-events.json").read_text(
            encoding="utf-8"
        )
    )
    report = compare_manual_events(manual, predicted, tolerance_seconds=1.0)

    assert len(predicted) == len(manual) == report["matched_event_count"]
    assert report["unmatched_manual"] == []
    assert report["unmatched_predicted"] == []
