from __future__ import annotations

import json
from pathlib import Path

import pytest

from football_poc.event_comparison import compare_manual_events


ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "alfheim" / "generated"
SEGMENTS = [
    "segment-0060-020",
    "segment-0300-020",
    "segment-0540-060",
    "segment-0575-020",
    "segment-0595-020",
    "segment-0615-020",
]


def _load_innovation_json(segment: str, relative_path: str):
    path = ROOT / segment / "innovation" / relative_path
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("segment", SEGMENTS)
def test_innovation_output_matches_accepted_reference(segment: str) -> None:
    root = ROOT / segment
    prepared = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert {
        "annotations",
        "ball_ground_truth",
        "events",
        "labels",
        "manual_reference",
    }.isdisjoint(prepared)

    innovation = root / "innovation"
    ball_tracks = json.loads(
        (innovation / "analytics-cache" / "ball-tracks.json").read_text(
            encoding="utf-8"
        )
    )
    assert ball_tracks["source_kind"] == "evaluation_only_provider_coordinates"
    assert ball_tracks["pipeline_mode"] == "innovation_day_bac_assisted"

    manual = json.loads(
        (innovation / "manual-reference.json").read_text(encoding="utf-8")
    )["events"]
    predicted = json.loads(
        (innovation / "analytics-data" / "predicted-events.json").read_text(
            encoding="utf-8"
        )
    )
    report = compare_manual_events(manual, predicted, tolerance_seconds=1.0)

    assert len(predicted) == len(manual) == report["matched_event_count"]
    assert report["unmatched_manual"] == []
    assert report["unmatched_predicted"] == []


def test_twenty_second_scissors_cut_preserves_minute_event_prefix() -> None:
    short_events = _load_innovation_json(
        "segment-0540-020",
        "analytics-data/predicted-events.json",
    )
    minute_events = _load_innovation_json(
        "segment-0540-060",
        "analytics-data/predicted-events.json",
    )
    minute_prefix = [
        event
        for event in minute_events
        if (event.get("completion_seconds") or event["clip_seconds"]) < 20.0
    ]

    def event_identity(event: dict) -> tuple:
        return (
            event["event_type"],
            event["team"],
            event["clip_seconds"],
            event.get("completion_seconds"),
            event.get("from_player_track_id"),
            event.get("to_player_track_id"),
        )

    assert [event_identity(event) for event in short_events] == [
        event_identity(event) for event in minute_prefix
    ]
    assert [
        (event["event_type"], event["team"], event["completion_seconds"])
        for event in short_events
    ] == [
        ("pass_candidate", "black", 12.0),
        ("turnover_candidate", "black", 13.6),
        ("pass_candidate", "red", 16.0),
        ("pass_candidate", "red", 16.8),
        ("pass_candidate", "red", 18.4),
    ]

    short_tracks = _load_innovation_json(
        "segment-0540-020",
        "analytics-data/player-tracks.json",
    )
    minute_tracks = _load_innovation_json(
        "segment-0540-060",
        "analytics-data/player-tracks.json",
    )
    minute_points = {
        (track["track_id"], point["source_frame"]): point
        for track in minute_tracks["tracks"]
        for point in track["points"]
        if point["source_frame"] < 500
    }
    short_points = {
        (track["track_id"], point["source_frame"]): point
        for track in short_tracks["tracks"]
        for point in track["points"]
    }

    assert short_points.keys() <= minute_points.keys()
    geometry_fields = (
        "source_frame",
        "clip_seconds",
        "confidence",
        "x1",
        "y1",
        "x2",
        "y2",
    )
    assert all(
        tuple(point[field] for field in geometry_fields)
        == tuple(minute_points[key][field] for field in geometry_fields)
        for key, point in short_points.items()
    )
    assert short_points[(75, 300)]["team"] == "black"
