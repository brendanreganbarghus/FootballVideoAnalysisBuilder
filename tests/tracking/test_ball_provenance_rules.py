"""Timestamped ball-tracking rule unit tests."""

import json
from pathlib import Path

from football_poc.ball_provenance import (
    MINIMUM_DIRECT_BALL_PROVENANCE,
    validate_ball_provenance,
)


def _write(tmp_path: Path, direct: int, total: int) -> tuple[Path, Path]:
    manifest = tmp_path / "runtime-manifest.json"
    manifest.write_text("{}")
    tracks = tmp_path / "ball-tracks.json"
    tracks.write_text(json.dumps({"manifest": str(manifest), "tracks": []}))
    states = tmp_path / "ball-state-estimates.json"
    states.write_text(json.dumps({
        "manifest": str(manifest),
        "states": [
            {"source_frame": frame, "event_evidence_eligible": frame < direct}
            for frame in range(total)
        ],
    }))
    return tracks, states


def test_rules_engine_gate_requires_90pct_direct_ball_20260928T191735982Z(
    tmp_path: Path,
) -> None:
    """Rule: detected ball tracks reach the rules engine only at >=90% direct."""
    assert MINIMUM_DIRECT_BALL_PROVENANCE == 0.90
    tracks, states = _write(tmp_path, direct=89, total=100)
    below = validate_ball_provenance(
        tracks, states, output=tmp_path / "below.json", enforce_threshold=False
    )
    tracks, states = _write(tmp_path, direct=90, total=100)
    at_gate = validate_ball_provenance(
        tracks, states, output=tmp_path / "at.json", enforce_threshold=False
    )

    assert below["status"] == "review_required"
    assert at_gate["status"] == "passed"
