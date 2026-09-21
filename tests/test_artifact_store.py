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


def test_published_prepared_segment_is_discoverable_and_checksummed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "generated" / "segment-0120-020"
    workflow = source / "innovation"
    workflow.mkdir(parents=True)
    (source / "alfheim-window-playable.mp4").write_bytes(b"video")
    (source / "alfheim-window.mp4").write_bytes(b"duplicate-video")
    (source / "copilot-review.json").write_text("{}", encoding="utf-8")
    (workflow / "manual-reference.json").write_text(
        '{"events":[]}',
        encoding="utf-8",
    )
    (source / "manifest.json").write_text(
        (
            '{"video":"absolute-original.mp4",'
            '"playable_video":"absolute-playable.mp4",'
            '"source_start_seconds":360.0,"duration_seconds":60.0,'
            '"review_workflows":["innovation_day_bac"]}'
        ),
        encoding="utf-8",
    )
    artifact_root = tmp_path / "artifacts"

    published = publish_prepared_segment(
        source,
        workflow_id="innovation_day_bac",
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
    assert discover_prepared_segments(artifact_root) == (published,)
    assert find_prepared_segment(
        "segment-0120-020",
        artifact_root,
    ) == published

    republished = publish_prepared_segment(
        published.root,
        workflow_id="innovation_day_bac",
        artifact_root=artifact_root,
        source_metadata={
            "camera_id": "camera-1",
            "recording_id": "recording-1",
        },
    )
    verify_prepared_segment(republished)
    assert republished.video.read_bytes() == b"video"


def test_publishing_second_workflow_preserves_first_workflow(
    tmp_path: Path,
) -> None:
    source = tmp_path / "generated" / "segment-0540-060"
    source.mkdir(parents=True)
    (source / "alfheim-window-playable.mp4").write_bytes(b"video")
    manifest_path = source / "manifest.json"
    manifest = {
        "video": "alfheim-window-playable.mp4",
        "source_start_seconds": 1620.0,
        "duration_seconds": 60.0,
        "review_workflows": ["innovation_day_bac", "live_iteration_25"],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (source / "innovation").mkdir()
    (source / "innovation" / "output.json").write_text(
        '{"innovation":true}',
        encoding="utf-8",
    )
    (source / "live").mkdir()
    (source / "live" / "output.json").write_text(
        '{"live":true}',
        encoding="utf-8",
    )
    artifact_root = tmp_path / "artifacts"
    metadata = {"camera_id": "camera-1", "recording_id": "recording-1"}

    publish_prepared_segment(
        source,
        workflow_id="innovation_day_bac",
        artifact_root=artifact_root,
        source_metadata=metadata,
    )
    published = publish_prepared_segment(
        source,
        workflow_id="live_iteration_25",
        artifact_root=artifact_root,
        source_metadata=metadata,
    )

    verify_prepared_segment(published)
    assert (published.root / "innovation" / "output.json").is_file()
    assert (published.root / "live" / "output.json").is_file()
    assert published.workflows == (
        "innovation_day_bac",
        "live_iteration_25",
    )
    assert json.loads(published.manifest.read_text(encoding="utf-8"))[
        "review_workflows"
    ] == ["innovation_day_bac", "live_iteration_25"]


def test_publication_rejects_unsafe_catalog_identifiers(
    tmp_path: Path,
) -> None:
    source = tmp_path / "segment-0120-020"
    (source / "innovation").mkdir(parents=True)
    (source / "alfheim-window-playable.mp4").write_bytes(b"video")
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "source_start_seconds": 360.0,
                "duration_seconds": 60.0,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="safe path identifiers"):
        publish_prepared_segment(
            source,
            workflow_id="innovation_day_bac",
            artifact_root=tmp_path / "artifacts",
            source_metadata={
                "camera_id": "../another-camera",
                "recording_id": "recording-1",
            },
        )
