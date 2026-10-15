"""Rule: a detector cache with a stale manifest hash is proven by its frames.

A cache's recorded manifest hash can go stale while its frames stay the
same (an older manifest serialisation). The player tracker then still accepts
the cache when its video is the same file and its own frame records reproduce
the manifest's fps and exact frame window at the recorded stride. A different
video, fps, window or a partial cache is still rejected.
"""

from __future__ import annotations

import json

import pytest

from football_poc.cache_identity import cache_matches_manifest
from football_poc.player_tracking import _load_player_cache


def _setup(tmp_path, *, cache_fps=25.0, cache_start=0, cache_end=50):
    video = tmp_path / "segment.mp4"
    video.write_bytes(b"video-bytes")
    manifest = tmp_path / "runtime-manifest.json"
    manifest.write_text(
        json.dumps(
            {"video": str(video), "fps": 25.0, "start_frame": 0, "end_frame": 50},
            indent=2,
        )
    )
    metadata = {
        "type": "metadata",
        "manifest_sha256": "0" * 64,
        "video": str(video),
        "stride": 5,
        "target_source_frames": None,
    }
    cache = tmp_path / "detections.jsonl"
    lines = [json.dumps(metadata)] + [
        json.dumps(
            {
                "type": "frame",
                "source_frame": frame,
                "clip_seconds": round((frame - cache_start) / cache_fps, 3),
                "detections": [],
            }
        )
        for frame in range(cache_start, cache_end, 5)
    ]
    cache.write_text("\n".join(lines) + "\n")
    return metadata, manifest, cache


def test_stale_hash_cache_accepted_when_frames_prove_window_20261015T060817428Z(
    tmp_path,
):
    metadata, manifest, cache = _setup(tmp_path)
    assert cache_matches_manifest(metadata, manifest, cache)
    loaded, records = _load_player_cache(cache, "f" * 64, manifest)
    assert loaded["video"] == metadata["video"] and len(records) == 10
    assert not cache_matches_manifest(metadata, manifest)


@pytest.mark.parametrize(
    "kwargs",
    [{"cache_fps": 30.0}, {"cache_end": 45}, {"cache_start": 5, "cache_end": 55}],
)
def test_stale_hash_cache_rejected_for_other_frames_20261015T060817429Z(
    tmp_path, kwargs
):
    metadata, manifest, cache = _setup(tmp_path, **kwargs)
    assert not cache_matches_manifest(metadata, manifest, cache)
    with pytest.raises(ValueError, match="different manifest"):
        _load_player_cache(cache, "f" * 64, manifest)


def test_stale_hash_cache_rejected_for_different_video_20261015T060817430Z(
    tmp_path,
):
    metadata, manifest, cache = _setup(tmp_path)
    other = tmp_path / "other.mp4"
    other.write_bytes(b"other-bytes")
    payload = json.loads(manifest.read_text())
    manifest.write_text(json.dumps({**payload, "video": str(other)}))
    assert not cache_matches_manifest(metadata, manifest, cache)
