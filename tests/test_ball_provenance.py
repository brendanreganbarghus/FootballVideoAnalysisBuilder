import json
from pathlib import Path

import pytest

from football_poc.ball_provenance import validate_ball_provenance


def write_ball_artifacts(
    tmp_path: Path,
    *,
    direct_frames: int,
    total_frames: int = 10,
) -> tuple[Path, Path, Path]:
    manifest = tmp_path / "runtime-manifest.json"
    manifest.write_text("{}")
    tracks = tmp_path / "ball-tracks.json"
    tracks.write_text(
        json.dumps(
            {
                "manifest": str(manifest),
                "tracks": [{"track_id": 1, "points": []}],
            }
        )
    )
    states = tmp_path / "ball-state-estimates.json"
    states.write_text(
        json.dumps(
            {
                "manifest": str(manifest),
                "states": [
                    {
                        "source_frame": frame * 5,
                        "state": (
                            "observed"
                            if frame < direct_frames
                            else "trajectory_estimated_bidirectional"
                        ),
                        "event_evidence_eligible": frame < direct_frames,
                    }
                    for frame in range(total_frames)
                ],
            }
        )
    )
    return tracks, states, tmp_path / "ball-provenance.json"


def test_ball_provenance_gate_passes_at_ninety_percent(
    tmp_path: Path,
) -> None:
    tracks, states, output = write_ball_artifacts(
        tmp_path,
        direct_frames=9,
    )

    report = validate_ball_provenance(tracks, states, output=output)

    assert report["status"] == "passed"
    assert report["direct_provenance"] == 0.9
    assert json.loads(output.read_text())["estimated_frames"] == [45]


def test_ball_provenance_gate_requires_review_below_ninety_percent(
    tmp_path: Path,
) -> None:
    tracks, states, output = write_ball_artifacts(
        tmp_path,
        direct_frames=8,
    )

    with pytest.raises(ValueError, match="8/10 direct frames"):
        validate_ball_provenance(tracks, states, output=output)

    assert json.loads(output.read_text())["status"] == "review_required"


def test_ball_provenance_reports_but_does_not_block_production(
    tmp_path: Path,
) -> None:
    tracks, states, output = write_ball_artifacts(
        tmp_path,
        direct_frames=8,
    )

    report = validate_ball_provenance(
        tracks,
        states,
        output=output,
        enforce_threshold=False,
    )

    assert report["status"] == "review_required"
    assert report["threshold_enforcement"] == "report_only"
    assert report["pipeline_action"] == "continue"
