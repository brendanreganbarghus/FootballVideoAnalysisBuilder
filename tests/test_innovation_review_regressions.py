from __future__ import annotations

import json
from pathlib import Path

import pytest

from football_poc.event_comparison import compare_manual_events


ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "alfheim" / "generated"
FIRST_MANUAL_BASELINE = "segment-0080-020"


def test_first_manual_innovation_baseline_matches_published_reference() -> None:
    root = ROOT / FIRST_MANUAL_BASELINE
    innovation = root / "innovation"
    manual_path = innovation / "manual-reference.json"
    predicted_path = innovation / "analytics-data" / "predicted-events.json"
    if not manual_path.is_file():
        pytest.skip(
            "04:00–05:00 M# review is not published as baseline one yet"
        )

    prepared = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert "innovation_day_bac" in prepared.get("review_workflows", [])
    assert {
        "annotations",
        "ball_ground_truth",
        "events",
        "labels",
        "manual_reference",
    }.isdisjoint(prepared)

    ball_tracks = json.loads(
        (innovation / "analytics-cache" / "ball-tracks.json").read_text(
            encoding="utf-8"
        )
    )
    assert ball_tracks["source_kind"] == "evaluation_only_provider_coordinates"
    assert ball_tracks["pipeline_mode"] == "innovation_day_bac_assisted"

    manual = json.loads(manual_path.read_text(encoding="utf-8"))["events"]
    predicted = json.loads(predicted_path.read_text(encoding="utf-8"))
    report = compare_manual_events(manual, predicted, tolerance_seconds=1.0)

    assert len(predicted) == len(manual) == report["matched_event_count"]
    assert report["unmatched_manual"] == []
    assert report["unmatched_predicted"] == []
