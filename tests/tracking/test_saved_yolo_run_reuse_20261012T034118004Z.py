"""Rule: a saved raw-video YOLO run is reused only for the identical video.

Preparing a window again must not rerun YOLO when a complete run with the live
detector profile already exists for a byte-identical copy of the same frames.
Any doubt (different video, incomplete run, other model or settings, other
frame window) refuses reuse, so YOLO runs from the raw video as normal.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from football_poc.detection_reuse import (
    LIVE_DETECTOR_PROFILE,
    reusable_detection_reason,
    reuse_saved_detections,
)

ROOT = Path(__file__).resolve().parents[2]


def _saved_run(root: Path, *, video: bytes = b"video", frames: int = 4,
               **overrides) -> Path:
    root.mkdir(parents=True)
    built_from = root / "built-from.mp4"
    built_from.write_bytes(video)
    (root / "segment.mp4").write_bytes(video)
    manifest = {"video": str(built_from), "start_frame": 100,
                "end_frame": 120, "fps": 25}
    manifest_path = root / "runtime-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n",
                             encoding="utf-8")
    header = {
        "type": "metadata",
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "video": str(built_from),
        "model": "C:\\models\\yolo26n.pt",
        "detection_scope": "person_and_ball",
        **{k: v for k, v in LIVE_DETECTOR_PROFILE.items() if k != "model"},
        **overrides,
    }
    rows = [json.dumps({"type": "frame", "source_frame": 100 + 5 * i,
                        "detections": []}) for i in range(frames)]
    cache = root / "analytics-cache"
    cache.mkdir()
    (cache / "detections.jsonl").write_text(
        "\n".join([json.dumps(header), *rows]) + "\n", encoding="utf-8")
    return root


def _target(root: Path, video: bytes = b"video") -> Path:
    root.mkdir(parents=True)
    (root / "segment.mp4").write_bytes(video)
    return root


def test_identical_video_reuses_and_restamps_the_saved_run_20261012T034118004Z(tmp_path):
    source = _saved_run(tmp_path / "source")
    target = _target(tmp_path / "target")

    receipt = reuse_saved_detections(source, target, LIVE_DETECTOR_PROFILE)

    lines = (target / "analytics-cache" / "detections.jsonl").read_text(
        encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    manifest_bytes = (target / "runtime-manifest.json").read_bytes()
    assert header["manifest_sha256"] == hashlib.sha256(manifest_bytes).hexdigest()
    assert header["video"] == str((target / "segment.mp4").resolve())
    assert header["reused_from"]["source_segment"] == str(source.resolve())
    assert "not a cold-path" in receipt["note"]
    assert len(lines) == 5


@pytest.mark.parametrize(
    ("kwargs", "target_video", "reason"),
    [
        ({}, b"other video", "not byte-identical"),
        ({"frames": 3}, b"video", "incomplete"),
        ({"model": "yolo11n.pt"}, b"video", "yolo11n.pt"),
        ({"confidence": 0.25}, b"video", "confidence"),
        ({"detection_scope": "ball_only"}, b"video", "players and ball"),
    ],
)
def test_any_doubt_refuses_reuse_20261012T034118004Z(tmp_path, kwargs, target_video, reason):
    source = _saved_run(tmp_path / "source", **kwargs)
    target = _target(tmp_path / "target", target_video)

    found = reusable_detection_reason(
        source, target / "segment.mp4", LIVE_DETECTOR_PROFILE)

    assert found is not None and reason in found
    with pytest.raises(ValueError):
        reuse_saved_detections(source, target, LIVE_DETECTOR_PROFILE)
    assert not (target / "analytics-cache").exists()


def test_other_frame_window_refuses_reuse_20261012T034118004Z(tmp_path):
    source = _saved_run(tmp_path / "source")
    manifest_path = source / "runtime-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["fps"] = 30
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n",
                             encoding="utf-8")

    found = reusable_detection_reason(
        source, source / "segment.mp4", LIVE_DETECTOR_PROFILE)

    assert found == "saved run belongs to a different frame window"


def test_profile_matches_the_live_detector_profile_of_the_pipeline_20261012T034118004Z():
    script = (ROOT / "scripts" / "process-alfheim-segment.py").read_text(
        encoding="utf-8")
    for node in ast.parse(script).body:
        if (isinstance(node, ast.Assign)
                and getattr(node.targets[0], "id", "") == "LIVE_DETECTOR_PROFILE"):
            pipeline = ast.literal_eval(node.value)
            break
    else:
        raise AssertionError("LIVE_DETECTOR_PROFILE not found")
    # Frame batching changes speed only, never the detections.
    pipeline.pop("frame_batch_size", None)
    assert pipeline == LIVE_DETECTOR_PROFILE
