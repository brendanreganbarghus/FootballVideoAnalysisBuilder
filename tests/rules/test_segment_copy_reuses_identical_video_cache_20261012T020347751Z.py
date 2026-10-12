"""Rule: a segment copy reuses its sibling's YOLO cache only for identical video.

A cache records the manifest hash and video path it was built from. A segment
copy (such as its BAC copy) has a manifest that differs only in the video
path. Its player cache is accepted when restoring the cached video path
reproduces the recorded manifest hash exactly and both video files are
byte-identical; any other difference still rejects the cache.
"""

from __future__ import annotations

import hashlib
import json

from football_poc.cache_identity import cache_matches_manifest


def _setup(tmp_path, copy_video_bytes):
    original = tmp_path / "seg" / "segment.mp4"
    copy = tmp_path / "seg-bac" / "segment.mp4"
    original.parent.mkdir()
    copy.parent.mkdir()
    original.write_bytes(b"video-bytes")
    copy.write_bytes(copy_video_bytes)
    body = {"fps": 25.0, "start_frame": 0, "end_frame": 1500}
    cached_manifest = json.dumps({**body, "video": str(original)})
    manifest = tmp_path / "seg-bac" / "runtime-manifest.json"
    manifest.write_text(json.dumps({**body, "video": str(copy)}))
    metadata = {
        "manifest_sha256": hashlib.sha256(cached_manifest.encode()).hexdigest(),
        "video": str(original),
    }
    return metadata, manifest


def test_segment_copy_accepts_cache_for_identical_video_20261012T020347751Z(
    tmp_path,
):
    metadata, manifest = _setup(tmp_path, b"video-bytes")
    assert cache_matches_manifest(metadata, manifest)


def test_segment_copy_rejects_cache_for_different_video_or_settings_20261012T020347752Z(
    tmp_path,
):
    metadata, manifest = _setup(tmp_path, b"other-bytes")
    assert not cache_matches_manifest(metadata, manifest)
    other = tmp_path / "b"
    other.mkdir()
    metadata, manifest = _setup(other, b"video-bytes")
    payload = json.loads(manifest.read_text())
    manifest.write_text(json.dumps({**payload, "end_frame": 1499}))
    assert not cache_matches_manifest(metadata, manifest)
