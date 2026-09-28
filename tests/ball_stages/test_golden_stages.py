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
    "01_confirm_yolo",
    "02_time_machine",
    "03_motion_and_optical_flow",
    "04_focused_multiscale",
    "05_short_stationary",
    "final",
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
        "confirming_module": point.confirming_module,
        "ledger_source_attribution": point.ledger_source_attribution,
    }


def _accepted_tracks(result) -> list:
    if hasattr(result, "to_tracks"):
        return list(result.to_tracks())
    if hasattr(result, "points"):
        return [result]
    if isinstance(result, tuple) and (
        not result or not hasattr(result[0], "points")
    ):
        result = result[0]
        if hasattr(result, "to_tracks"):
            return list(result.to_tracks())
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
    captured["final"] = _stage_payload(
        ball_tracking.BallTrack(
            1,
            [
                ball_tracking.BallPoint(
                    int(point["source_frame"]),
                    float(point["clip_seconds"]),
                    float(point["confidence"]),
                    float(point["x"]),
                    float(point["y"]),
                    bool(point.get("interpolated", False)),
                    float(point.get("box_diagonal", 0.0) or 0.0),
                    str(point.get("evidence", "detector")),
                    point.get("temporal_score"),
                    str(point.get("source_attribution", "yolo26_observed")),
                    point.get("confirming_module"),
                    tuple(point.get("rejection_reasons", ())),
                    str(point.get("ledger_source_attribution", "detected")),
                )
                for track in json.loads(
                    (segment_root / "analytics-cache" / "ball-tracks.json").read_text(
                        encoding="utf-8"
                    )
                ).get("tracks", [])
                for point in track.get("points", [])
            ],
        )
    )

    for index, stage in enumerate(STAGES, start=1):
        golden = GOLDEN_ROOT / SEGMENT / f"{index:02d}_{stage}.json"
        expected = json.loads(golden.read_text(encoding="utf-8"))
        assert captured.get(stage) == expected, (
            f"First differing ball stage: {index:02d}_{stage}"
        )
