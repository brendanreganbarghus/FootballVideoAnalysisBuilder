from __future__ import annotations

import json
from pathlib import Path

import pytest

from football_poc.event_comparison import compare_manual_events


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALFHEIM_ROOT = PROJECT_ROOT / "benchmarks" / "alfheim"
GENERATED = ALFHEIM_ROOT / "generated"
REGISTRY = ALFHEIM_ROOT / "review-regressions.json"
FORBIDDEN_MANIFEST_KEYS = {
    "annotations",
    "ball_ground_truth",
    "events",
    "ground_truth",
    "labels",
    "manual_reference",
}


def registered_segments() -> list[dict]:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert payload["workflow"] == "football_review"
    return payload["segments"]


def test_registry_entries_record_a_supported_ball_source() -> None:
    entries = registered_segments()
    assert entries
    assert len({entry["segment"] for entry in entries}) == len(entries)
    assert {entry["ball_source"] for entry in entries} <= {"bac", "live"}


def _segment_root(segment: str) -> Path:
    root = GENERATED / segment
    if not (root / "manual-reference.json").is_file():
        pytest.skip(f"{segment} is not prepared locally")
    return root


@pytest.mark.parametrize(
    "entry", registered_segments(), ids=lambda entry: entry["segment"]
)
def test_published_segment_matches_current_engine(entry: dict) -> None:
    root = _segment_root(entry["segment"])
    prepared = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert FORBIDDEN_MANIFEST_KEYS.isdisjoint(prepared)

    ball_tracks = json.loads(
        (root / "analytics-cache" / "ball-tracks.json").read_text(
            encoding="utf-8"
        )
    )
    if entry["ball_source"] == "bac":
        assert ball_tracks["source_kind"] == "evaluation_only_provider_coordinates"
        assert ball_tracks["pipeline_mode"] == "innovation_day_bac_assisted"
    else:
        source = json.dumps(ball_tracks.get("source", {})).lower()
        assert "bac" not in source
        assert "ground_truth" not in source
        assert "provider_coordinates" not in source

    manual = json.loads(
        (root / "manual-reference.json").read_text(encoding="utf-8")
    )["events"]
    predicted = json.loads(
        (root / "analytics-data" / "predicted-events.json").read_text(
            encoding="utf-8"
        )
    )
    report = compare_manual_events(
        manual,
        predicted,
        tolerance_seconds=1.0,
        include_shots_on_target=True,
    )

    assert len(report["unmatched_manual"]) == 0
    assert len(report["unmatched_predicted"]) == 0
    assert report["matched_event_count"] == entry["event_count"]
