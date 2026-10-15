"""Rule: a reused YOLO run is always in video pixels.

A saved run may have been stored with its boxes scaled to another image size
(header ``coordinate_scale``). The ball and player trackers read detections in
video pixels, so reuse divides every box by that uniform scale and drops the
field. A non-uniform or invalid scale refuses reuse.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from football_poc.detection_reuse import (
    LIVE_DETECTOR_PROFILE,
    reusable_detection_reason,
    reuse_saved_detections,
)


def _saved_run(root: Path, scale, box) -> Path:
    root.mkdir(parents=True)
    built_from = root / "built-from.mp4"
    built_from.write_bytes(b"video")
    (root / "segment.mp4").write_bytes(b"video")
    manifest_path = root / "runtime-manifest.json"
    manifest_path.write_text(
        json.dumps({"video": str(built_from), "start_frame": 0,
                    "end_frame": 10, "fps": 25}, indent=2) + "\n",
        encoding="utf-8")
    header = {
        "type": "metadata",
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "video": str(built_from),
        "model": "yolo26n.pt",
        "detection_scope": "person_and_ball",
        **{k: v for k, v in LIVE_DETECTOR_PROFILE.items() if k != "model"},
        "coordinate_scale": scale,
    }
    detection = {"class_name": "sports ball", "confidence": 0.5,
                 **dict(zip(("x1", "y1", "x2", "y2"), box))}
    rows = [json.dumps({"type": "frame", "source_frame": 5 * i,
                        "detections": [detection]}) for i in range(2)]
    (root / "analytics-cache").mkdir()
    (root / "analytics-cache" / "detections.jsonl").write_text(
        "\n".join([json.dumps(header), *rows]) + "\n", encoding="utf-8")
    return root


def _target(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "segment.mp4").write_bytes(b"video")
    return root


def test_scaled_saved_run_is_reused_in_video_pixels_20261015T082809224Z(tmp_path):
    source = _saved_run(tmp_path / "source", 1.25, (500.0, 250.0, 525.0, 275.0))
    target = _target(tmp_path / "target")

    receipt = reuse_saved_detections(source, target, LIVE_DETECTOR_PROFILE)

    lines = (target / "analytics-cache" / "detections.jsonl").read_text(
        encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    assert "coordinate_scale" not in header
    assert receipt["unscaled_coordinate_scale"] == 1.25
    box = json.loads(lines[1])["detections"][0]
    assert (box["x1"], box["y1"], box["x2"], box["y2"]) == pytest.approx(
        (400.0, 200.0, 420.0, 220.0))


@pytest.mark.parametrize("scale", [[1.2, 1.1], 0, -1.0])
def test_non_uniform_or_invalid_scale_refuses_reuse_20261015T082809225Z(tmp_path, scale):
    source = _saved_run(tmp_path / "source", scale, (1.0, 1.0, 2.0, 2.0))
    target = _target(tmp_path / "target")

    assert reusable_detection_reason(
        source, target / "segment.mp4", LIVE_DETECTOR_PROFILE) is not None
    with pytest.raises(ValueError):
        reuse_saved_detections(source, target, LIVE_DETECTOR_PROFILE)
