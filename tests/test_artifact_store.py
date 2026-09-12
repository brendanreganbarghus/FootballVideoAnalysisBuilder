from pathlib import Path

import pytest

from football_poc.artifact_store import (
    discover_artifact_root,
    resolve_detector_model,
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
