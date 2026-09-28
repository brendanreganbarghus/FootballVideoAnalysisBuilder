import json
from pathlib import Path

import pytest

from football_poc.artifact_store import (
    discover_artifact_root,
    discover_prepared_segments,
    find_prepared_segment,
    publish_prepared_segment,
    resolve_detector_model,
    verify_prepared_segment,
)


def test_explicit_artifact_root_must_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setenv("FOOTBALL_ARTIFACT_ROOT", str(missing))

    with pytest.raises(FileNotFoundError, match="does not exist"):
        discover_artifact_root()


def test_detector_uses_shared_approved_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    model = (
        artifact_root
        / "20-approved-models"
        / "internal-poc-only"
        / "ultralytics-yolo11n"
        / "yolo11n.pt"
    )
    model.parent.mkdir(parents=True)
    model.touch()
    monkeypatch.setenv("FOOTBALL_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.delenv("FOOTBALL_DETECTOR_MODEL", raising=False)

    assert resolve_detector_model(tmp_path / "repo") == model.resolve()


def test_explicit_detector_override_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "authorized.pt"
    model.touch()
    monkeypatch.setenv("FOOTBALL_DETECTOR_MODEL", str(model))

    assert resolve_detector_model(tmp_path / "repo") == model.resolve()


def _write_publishable_segment(source: Path, ball_source: str = "bac") -> None:
    source.mkdir(parents=True)
    (source / "alfheim-window-playable.mp4").write_bytes(b"video")
    (source / "alfheim-window.mp4").write_bytes(b"duplicate-video")
    (source / "copilot-review.json").write_text("{}", encoding="utf-8")
    (source / "manual-reference.json").write_text(
        '{"events":[]}',
        encoding="utf-8",
    )
    (source / "analysis-status.json").write_text(
        json.dumps({"stage": "ready", "ball_source": ball_source}),
        encoding="utf-8",
    )
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "video": "alfheim-window-playable.mp4",
                "playable_video": "alfheim-window-playable.mp4",
                "source_start_seconds": 360.0,
                "duration_seconds": 60.0,
            }
        ),
        encoding="utf-8",
    )


def test_published_prepared_segment_is_discoverable_and_checksummed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "generated" / "segment-0120-020"
    _write_publishable_segment(source)
    artifact_root = tmp_path / "artifacts"

    published = publish_prepared_segment(
        source,
        artifact_root=artifact_root,
        source_metadata={
            "camera_id": "camera-1",
            "recording_id": "recording-1",
        },
    )

    verify_prepared_segment(published)
    assert published.video.read_bytes() == b"video"
    assert not (published.root / "alfheim-window.mp4").exists()
    assert json.loads(published.manifest.read_text(encoding="utf-8"))[
        "video"
    ] == "segment.mp4"
    assert published.ball_source == "bac"
    assert discover_prepared_segments(artifact_root) == (published,)
    assert find_prepared_segment(
        "segment-0120-020",
        artifact_root,
    ) == published

    republished = publish_prepared_segment(
        published.root,
        artifact_root=artifact_root,
        source_metadata={
            "camera_id": "camera-1",
            "recording_id": "recording-1",
        },
    )
    verify_prepared_segment(republished)
    assert republished.video.read_bytes() == b"video"


def test_publishing_flat_segment_replaces_previous_bundle(
    tmp_path: Path,
) -> None:
    source = tmp_path / "generated" / "segment-0540-060"
    _write_publishable_segment(source, "live")
    (source / "analytics-data").mkdir()
    (source / "analytics-data" / "predicted-events.json").write_text(
        "[]",
        encoding="utf-8",
    )
    artifact_root = tmp_path / "artifacts"
    metadata = {"camera_id": "camera-1", "recording_id": "recording-1"}

    published = publish_prepared_segment(
        source,
        artifact_root=artifact_root,
        source_metadata=metadata,
    )

    verify_prepared_segment(published)
    assert (published.root / "analytics-data" / "predicted-events.json").is_file()
    assert published.ball_source == "live"
    assert json.loads((published.root / "segment.json").read_text(encoding="utf-8"))[
        "ball_source"
    ] == "live"


def test_publication_rejects_unsafe_catalog_identifiers(
    tmp_path: Path,
) -> None:
    source = tmp_path / "segment-0120-020"
    _write_publishable_segment(source)

    with pytest.raises(ValueError, match="safe path identifiers"):
        publish_prepared_segment(
            source,
            artifact_root=tmp_path / "artifacts",
            source_metadata={
                "camera_id": "../another-camera",
                "recording_id": "recording-1",
            },
        )
