"""Decide whether a cached detector output belongs to a runtime manifest.

A cache records the SHA-256 of the manifest file it was built from and the
video path it read. A copy of a segment (for example its BAC copy) has a
manifest that differs only in that video path. The cache still belongs to it
when the two video files are byte-identical and substituting the cached video
path back into the manifest reproduces the recorded manifest hash exactly.

A recorded hash can also go stale while the frames stay identical (an older
manifest serialisation). Given the cache file, the cache is then accepted
only when its video is the same file or byte-identical and its own frame
records reproduce the manifest's fps and exact frame window.
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


def _same_video(manifest_video: Path, cached_video: Path) -> bool:
    if not (manifest_video.is_file() and cached_video.is_file()):
        return False
    if manifest_video.resolve() == cached_video.resolve():
        return True
    if manifest_video.stat().st_size != cached_video.stat().st_size:
        return False
    return _file_sha256(manifest_video) == _file_sha256(cached_video)


def _frames_match_manifest(
    metadata: dict[str, Any], manifest: dict[str, Any], cache_path: Path
) -> bool:
    """The cache's own frame records prove the manifest's fps and window.

    Every record stores its source frame and ``(frame - start_frame) / fps``.
    A full-stride cache whose records are exactly ``start..end`` at the
    recorded stride, with those clip times, was built for the same frames.
    """
    if metadata.get("target_source_frames"):
        return False
    try:
        stride = int(metadata["stride"])
        fps = float(manifest["fps"])
        start = int(manifest["start_frame"])
        end = int(manifest["end_frame"])
    except (KeyError, TypeError, ValueError):
        return False
    if stride <= 0 or fps <= 0 or end <= start:
        return False
    expected = list(range(start, end, stride))
    seen: list[int] = []
    with Path(cache_path).open(encoding="utf-8") as handle:
        handle.readline()
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("type") != "frame":
                continue
            frame = int(record["source_frame"])
            clip = record.get("clip_seconds")
            if clip is None or abs(float(clip) - (frame - start) / fps) > 0.0011:
                return False
            seen.append(frame)
    return seen == expected


def cache_matches_manifest(
    metadata: dict[str, Any],
    manifest_path: Path,
    cache_path: Path | None = None,
) -> bool:
    """Whether a detector cache belongs to ``manifest_path``.

    Without ``cache_path`` only the recorded manifest hash (optionally after a
    video-path swap) is accepted. With ``cache_path`` a cache whose recorded
    hash is stale is still accepted when its video is the same file or
    byte-identical and its frame records prove the manifest's fps and window.
    """
    manifest_bytes = Path(manifest_path).read_bytes()
    cached_sha256 = metadata.get("manifest_sha256")
    if cached_sha256 == hashlib.sha256(manifest_bytes).hexdigest():
        return True
    if _hash_after_video_swap(metadata, manifest_bytes):
        return True
    if cache_path is None or not metadata.get("video"):
        return False
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if not manifest.get("video"):
        return False
    if not _same_video(Path(manifest["video"]), Path(metadata["video"])):
        return False
    return _frames_match_manifest(metadata, manifest, cache_path)


def _hash_after_video_swap(
    metadata: dict[str, Any], manifest_bytes: bytes
) -> bool:
    cached_sha256 = metadata.get("manifest_sha256")
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
