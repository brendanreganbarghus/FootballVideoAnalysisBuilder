"""Decide whether a cached detector output belongs to a runtime manifest.

A cache records the SHA-256 of the manifest file it was built from and the
video path it read. A copy of a segment (for example its BAC copy) has a
manifest that differs only in that video path. The cache still belongs to it
when the two video files are byte-identical and substituting the cached video
path back into the manifest reproduces the recorded manifest hash exactly.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def cache_matches_manifest(
    metadata: dict[str, Any], manifest_path: Path
) -> bool:
    manifest_bytes = Path(manifest_path).read_bytes()
    cached_sha256 = metadata.get("manifest_sha256")
    if cached_sha256 == hashlib.sha256(manifest_bytes).hexdigest():
        return True
    cached_video = metadata.get("video")
    if not cached_sha256 or not cached_video:
        return False
    manifest_video = json.loads(manifest_bytes.decode("utf-8")).get("video")
    if not manifest_video or manifest_video == cached_video:
        return False
    manifest_video_path = Path(manifest_video)
    cached_video_path = Path(cached_video)
    if not (manifest_video_path.is_file() and cached_video_path.is_file()):
        return False
    old = json.dumps(manifest_video)[1:-1].encode("utf-8")
    new = json.dumps(cached_video)[1:-1].encode("utf-8")
    if manifest_bytes.count(old) != 1:
        return False
    substituted = manifest_bytes.replace(old, new)
    if hashlib.sha256(substituted).hexdigest() != cached_sha256:
        return False
    if manifest_video_path.stat().st_size != cached_video_path.stat().st_size:
        return False
    return _file_sha256(manifest_video_path) == _file_sha256(cached_video_path)
