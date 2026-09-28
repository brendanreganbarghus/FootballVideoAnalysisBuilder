from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_ROOT = Path(__file__).resolve().parent / "golden"


def _accepted_points_from_cached_tracks(segment: str) -> list[dict]:
    path = (
        PROJECT_ROOT
        / "benchmarks"
        / "alfheim"
        / "generated"
        / segment
        / "analytics-cache"
        / "ball-tracks.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    points: list[dict] = []
    for track in payload["tracks"]:
        for point in track["points"]:
            points.append(
                {
                    "source_frame": point["source_frame"],
                    "clip_seconds": point["clip_seconds"],
                    "confidence": point["confidence"],
                    "x": point["x"],
                    "y": point["y"],
                    "interpolated": point.get("interpolated", False),
                    "box_diagonal": point.get("box_diagonal", 0.0),
                    "evidence": point.get("evidence", "detector"),
                    "temporal_score": point.get("temporal_score"),
                    "source_attribution": point.get(
                        "source_attribution", "yolo26_observed"
                    ),
                }
            )
    return sorted(points, key=lambda item: item["source_frame"])


def test_cached_detected_ball_track_matches_post_recovery_golden() -> None:
    """Report the first stage golden that differs for local cached coverage."""
    segment = "segment-0540-020"
    actual = _accepted_points_from_cached_tracks(segment)
    stage_files = sorted((GOLDEN_ROOT / segment).glob("*.json"))
    assert stage_files, f"No ball-stage goldens found for {segment}"
    for stage_file in stage_files:
        expected = json.loads(stage_file.read_text(encoding="utf-8"))
        assert actual == expected, f"First differing ball stage: {stage_file.stem}"
