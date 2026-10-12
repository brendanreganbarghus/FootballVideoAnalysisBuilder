"""Reuse a saved raw-video YOLO detection run for another copy of the same video.

A detection cache records the runtime manifest hash and video path it was
built from. A saved run may be reused by another segment folder only when it
is provably the same detector pass on the same frames:

* the cache is complete and was produced by the pinned live detector profile;
* the source runtime manifest reproduces the cached manifest hash once its
  video path is swapped for the cached video path (same frame window and fps);
* the target video is byte-identical to the video the cache was built from.

The reused cache is re-stamped for the target runtime manifest so the ball
tracker accepts it, and it records where it came from. This is cache reuse,
never a cold-path raw-video benchmark.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

PROFILE_KEYS = (
    "confidence",
    "image_size",
    "stride",
    "tile_width",
    "tile_height",
    "overlap",
    "nms_iou",
)
# Mirrors LIVE_DETECTOR_PROFILE in scripts/process-alfheim-segment.py; a unit
# test keeps the two identical.
LIVE_DETECTOR_PROFILE = {
    "model": "yolo26n.pt",
    "confidence": 0.10,
    "image_size": 960,
    "stride": 5,
    "tile_width": 960,
    "tile_height": 960,
    "overlap": 0.2,
    "nms_iou": 0.5,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_text(value: str) -> bytes:
    return json.dumps(value)[1:-1].encode("utf-8")


def _swap_video(manifest_bytes: bytes, old: str, new: str) -> bytes | None:
    old_bytes = _json_text(old)
    if manifest_bytes.count(old_bytes) != 1:
        return None
    return manifest_bytes.replace(old_bytes, _json_text(new))


def _model_name(metadata: Mapping[str, Any]) -> str:
    return str(metadata.get("model") or "").replace("\\", "/").rsplit("/", 1)[-1].lower()


def reusable_detection_reason(
    source_root: Path,
    target_video: Path,
    profile: Mapping[str, Any],
) -> str | None:
    """Return None when the saved run can be reused, otherwise the reason."""
    cache = source_root / "analytics-cache" / "detections.jsonl"
    runtime_manifest = source_root / "runtime-manifest.json"
    if not cache.is_file() or not runtime_manifest.is_file():
        return "no saved detection run"
    with cache.open(encoding="utf-8") as handle:
        metadata = json.loads(handle.readline() or "{}")
        frames = sum(
            1
            for line in handle
            if line.strip() and json.loads(line).get("type") == "frame"
        )
    if _model_name(metadata) != str(profile["model"]).lower():
        return f"saved run used {_model_name(metadata) or 'an unknown model'}"
    if metadata.get("detection_scope") != "person_and_ball":
        return "saved run did not detect both players and ball"
    for key in PROFILE_KEYS:
        if float(metadata.get(key, -1)) != float(profile[key]):
            return f"saved run used a different {key}"
    manifest_bytes = runtime_manifest.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    stride = int(metadata["stride"])
    expected = (
        int(manifest["end_frame"]) - int(manifest["start_frame"]) + stride - 1
    ) // stride
    if frames != expected:
        return f"saved run is incomplete ({frames} of {expected} frames)"
    cached_sha = metadata.get("manifest_sha256")
    cached_video = str(metadata.get("video") or "")
    manifest_video = str(manifest.get("video") or "")
    if cached_sha != hashlib.sha256(manifest_bytes).hexdigest():
        swapped = _swap_video(manifest_bytes, manifest_video, cached_video)
        if swapped is None or hashlib.sha256(swapped).hexdigest() != cached_sha:
            return "saved run belongs to a different frame window"
    built_from = Path(cached_video)
    if not built_from.is_file():
        return "the video the saved run was built from is no longer available"
    if _sha256(built_from) != _sha256(target_video):
        return "the video is not byte-identical to the saved run's video"
    return None


def reuse_saved_detections(
    source_root: Path,
    target_root: Path,
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Copy a proven-identical saved detection run into ``target_root``.

    ``target_root`` must already hold ``segment.mp4``. Returns the reuse
    receipt, or raises ValueError with the reason the run cannot be reused.
    """
    source_root = Path(source_root).resolve()
    target_root = Path(target_root).resolve()
    target_video = target_root / "segment.mp4"
    reason = reusable_detection_reason(source_root, target_video, profile)
    if reason is not None:
        raise ValueError(reason)
    source_cache = source_root / "analytics-cache" / "detections.jsonl"
    lines = source_cache.read_text(encoding="utf-8").splitlines()
    metadata = json.loads(lines[0])
    source_manifest = json.loads(
        (source_root / "runtime-manifest.json").read_text(encoding="utf-8")
    )
    target_manifest = dict(source_manifest)
    target_manifest["video"] = str(target_video)
    target_manifest_text = json.dumps(target_manifest, indent=2) + "\n"
    receipt = {
        "source_segment": str(source_root),
        "source_manifest_sha256": metadata.get("manifest_sha256"),
        "source_video": metadata.get("video"),
        "video_sha256": _sha256(target_video),
        "reused_at_utc": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Saved raw-video YOLO run reused for a byte-identical video. "
            "Cache reuse, not a cold-path raw-video benchmark."
        ),
    }
    cache_dir = target_root / "analytics-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Written exactly as process-alfheim-segment.py writes it, so a later run
    # reproduces the same bytes and hash.
    target_manifest_path = target_root / "runtime-manifest.json"
    target_manifest_path.write_text(target_manifest_text, encoding="utf-8")
    stamped = {
        **metadata,
        "manifest_sha256": hashlib.sha256(
            target_manifest_path.read_bytes()
        ).hexdigest(),
        "video": str(target_video),
        "reused_from": receipt,
    }
    temporary = cache_dir / "detections.jsonl.tmp"
    temporary.write_text(
        "\n".join([json.dumps(stamped), *lines[1:]]) + "\n", encoding="utf-8"
    )
    temporary.replace(cache_dir / "detections.jsonl")
    summary_path = source_root / "analytics-cache" / "detection-summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary.update(
            {
                "manifest": str(target_root / "runtime-manifest.json"),
                "cache": str(cache_dir / "detections.jsonl"),
                "configuration": stamped,
                "reused_from": receipt,
            }
        )
        (cache_dir / "detection-summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
    return receipt
