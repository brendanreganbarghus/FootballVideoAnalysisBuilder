from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from football_poc.alfheim_profile import ALFHEIM_POSSESSION_ARGUMENTS
from football_poc.event_comparison import compare_manual_events
from football_poc.possession_cli import build_parser, run


ROOT = Path(__file__).parents[1] / "benchmarks" / "alfheim" / "generated"


@pytest.mark.parametrize(
    "segment",
    [
        "segment-0060-020",
        "segment-0180-020",
        "segment-0575-020",
        "segment-0595-020",
        "segment-0615-020",
    ],
)
def test_published_events_exactly_match_blind_manual_reference(
    segment: str,
) -> None:
    segment_root = ROOT / segment
    manual = json.loads(
        (segment_root / "manual-reference.json").read_text(encoding="utf-8")
    )["events"]
    predicted = json.loads(
        (segment_root / "analytics-data" / "predicted-events.json").read_text(
            encoding="utf-8"
        )
    )

    manual_counts = Counter(
        (event["team"], event["event_type"]) for event in manual
    )
    predicted_counts = Counter(
        (event.get("team"), _manual_event_type(event["event_type"]))
        for event in predicted
        if _manual_event_type(event["event_type"]) is not None
    )
    report = compare_manual_events(manual, predicted, tolerance_seconds=1.0)

    assert predicted_counts == manual_counts
    assert len(predicted) == len(manual)
    assert report["matched_event_count"] == len(manual)
    assert report["unmatched_manual"] == []
    assert report["unmatched_predicted"] == []


def _manual_event_type(event_type: str) -> str | None:
    return {
        "pass_candidate": "completed_pass",
        "restart_pass_candidate": "completed_pass",
        "turnover_candidate": "turnover",
    }.get(event_type)


def test_third_blind_minute_opens_with_three_black_passes() -> None:
    manual = json.loads(
        (ROOT / "segment-0615-020" / "manual-reference.json").read_text(
            encoding="utf-8"
        )
    )["events"]

    opening = [
        event
        for event in manual
        if event["clip_seconds"] <= 8
        and event["team"] == "black"
        and event["event_type"] == "completed_pass"
    ]

    assert [event["clip_seconds"] for event in opening] == [
        1.262,
        4.222,
        6.124,
    ]


@pytest.mark.parametrize(
    "segment",
    [
        "segment-0060-020",
        "segment-0180-020",
        "segment-0575-020",
        "segment-0595-020",
        "segment-0615-020",
    ],
)
def test_current_pipeline_exactly_matches_saved_blind_minutes(
    segment: str,
    tmp_path: Path,
) -> None:
    segment_root = ROOT / segment
    output = tmp_path / segment
    args = build_parser().parse_args(
        [
            str(segment_root / "manifest.json"),
            "--player-tracks",
            str(segment_root / "analytics-data" / "player-tracks.json"),
            "--ball-tracks",
            str(
                segment_root
                / "analytics-cache"
                / "ball-tracks.json"
            ),
            "--output",
            str(output),
            *ALFHEIM_POSSESSION_ARGUMENTS,
            "--boundary-events",
            str(segment_root / "boundary-events.json"),
        ]
    )

    run(args)

    manual = json.loads(
        (segment_root / "manual-reference.json").read_text(encoding="utf-8")
    )["events"]
    predicted = json.loads(
        (output / "predicted-events.json").read_text(encoding="utf-8")
    )
    report = compare_manual_events(manual, predicted, tolerance_seconds=1.0)

    assert len(predicted) == len(manual)
    assert report["matched_event_count"] == len(manual)
    assert report["unmatched_manual"] == []
    assert report["unmatched_predicted"] == []

    if segment == "segment-0615-020":
        early_events = [
            event
            for event in predicted
            if (event.get("completion_seconds") or event["clip_seconds"]) <= 12
        ]
        assert [event["team"] for event in early_events] == ["black"] * 5
        assert [event["event_type"] for event in early_events] == [
            "pass_candidate"
        ] * 5
        interception_events = [
            event
            for event in predicted
            if 14
            <= (event.get("completion_seconds") or event["clip_seconds"])
            <= 19
            and event["team"] == "black"
        ]
        assert [
            (event["team"], event["event_type"])
            for event in interception_events
        ] == [
            ("black", "pass_candidate"),
            ("black", "turnover_candidate"),
        ]
