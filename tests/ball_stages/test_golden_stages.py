from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

import football_poc.ball_tracking as ball_tracking


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_ROOT = Path(__file__).resolve().parent / "golden"
SEGMENT = "segment-0540-060"
SOURCE_SEGMENT_ROOT = (
    PROJECT_ROOT
    / "benchmarks"
    / "alfheim"
    / "generated"
    / "_local-copy-segment-0540-060-20260928"
)
STAGES = [
    "motion_supported_points",
    "template_supported_points",
    "select_single_ball_trajectory",
    "resolve_detector_conflicts",
    "restore_plausible_detector_points",
    "bidirectional_template_bridges",
    "terminal_template_bridges",
    "forward_template_consensus",
    "startup_attention_gate",
    "raw_motion_proposals",
    "kalman_guided_reacquisitions",
    "dense_optical_flow_bridges",
    "discard_detector_outliers",
    "bracketed_outlier_recoveries",
    "full_rate_motion_streaks",
    "full_rate_trajectory_corridors",
    "discard_temporal_upper_body_points",
    "focused_multiscale_points",
    "final_trajectory_integrity",
    "short_stationary_template_recoveries",
    "post_recovery_trajectory_integrity",
]


def _point_payload(point) -> dict:
    return {
        "source_frame": point.source_frame,
        "clip_seconds": point.clip_seconds,
        "confidence": point.confidence,
        "x": point.x,
        "y": point.y,
        "interpolated": point.interpolated,
        "box_diagonal": point.box_diagonal,
        "evidence": point.evidence,
        "temporal_score": point.temporal_score,
        "source_attribution": point.source_attribution,
    }


def _accepted_tracks(result) -> list:
    if isinstance(result, tuple) and (
        not result or not hasattr(result[0], "points")
    ):
        result = result[0]
    return list(result)


def _stage_payload(result) -> list[dict]:
    points = [
        _point_payload(point)
        for track in _accepted_tracks(result)
        for point in track.points
    ]
    return sorted(points, key=lambda item: item["source_frame"])


def _assert_cache_matches_manifest(segment_root: Path) -> None:
    cache = segment_root / "analytics-cache" / "detections.jsonl"
    metadata = json.loads(cache.open(encoding="utf-8").readline())
    manifest_hash = hashlib.sha256(
        (segment_root / "runtime-manifest.json").read_bytes()
    ).hexdigest()
    assert metadata["manifest_sha256"] == manifest_hash


def test_cached_detected_tracker_matches_stage_goldens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not SOURCE_SEGMENT_ROOT.is_dir():
        pytest.skip(f"{SOURCE_SEGMENT_ROOT} is not available")
    manifest = json.loads(
        (SOURCE_SEGMENT_ROOT / "runtime-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    if not Path(manifest["video"]).is_file():
        pytest.skip(f"Referenced video is not available: {manifest['video']}")

    segment_root = tmp_path / SEGMENT
    shutil.copytree(SOURCE_SEGMENT_ROOT, segment_root)
    _assert_cache_matches_manifest(segment_root)

    captured: dict[str, list[dict]] = {}
    original = ball_tracking._timed_tracker_call

    def capturing_timed(name, function, /, *args, **kwargs):
        result = original(name, function, *args, **kwargs)
        captured[name] = _stage_payload(result)
        return result

    monkeypatch.setattr(
        ball_tracking,
        "_timed_tracker_call",
        capturing_timed,
    )
    ball_tracking.track_cached_balls(
        manifest_path=segment_root / "runtime-manifest.json",
        cache_path=segment_root / "analytics-cache" / "detections.jsonl",
        output=segment_root / "analytics-cache",
        reuse_decoded_frame_cache=True,
    )

    for index, stage in enumerate(STAGES, start=1):
        golden = GOLDEN_ROOT / SEGMENT / f"{index:02d}_{stage}.json"
        expected = json.loads(golden.read_text(encoding="utf-8"))
        assert captured.get(stage) == expected, (
            f"First differing ball stage: {index:02d}_{stage}"
        )
