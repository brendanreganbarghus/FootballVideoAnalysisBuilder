from __future__ import annotations

import os
from pathlib import Path


def discover_artifact_root() -> Path | None:
    configured = os.environ.get("FOOTBALL_ARTIFACT_ROOT", "").strip()
    if configured:
        root = Path(configured).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(
                f"FOOTBALL_ARTIFACT_ROOT does not exist: {root}"
            )
        return root

    one_drive = (
        os.environ.get("ONEDRIVECOMMERCIAL")
        or os.environ.get("ONEDRIVE")
        or ""
    ).strip()
    if not one_drive:
        return None
    candidate = Path(one_drive) / "Innovationday Artifacts"
    return candidate.resolve() if candidate.is_dir() else None


def resolve_detector_model(project_root: Path) -> Path:
    configured = os.environ.get("FOOTBALL_DETECTOR_MODEL", "").strip()
    if configured:
        model = Path(configured).expanduser().resolve()
        if not model.is_file():
            raise FileNotFoundError(
                f"FOOTBALL_DETECTOR_MODEL does not exist: {model}"
            )
        return model

    artifact_root = discover_artifact_root()
    approved_model = (
        artifact_root
        / "20-approved-models"
        / "internal-poc-only"
        / "ultralytics-yolo11n"
        / "yolo11n.pt"
        if artifact_root
        else None
    )
    if approved_model and approved_model.is_file():
        return approved_model.resolve()

    local_generic_model = project_root / "yolo11n.pt"
    if local_generic_model.is_file():
        return local_generic_model.resolve()

    raise FileNotFoundError(
        "No detector model is available. Set FOOTBALL_DETECTOR_MODEL to an "
        "authorized checkpoint or synchronize the approved internal POC model. "
        "The local football-specific checkpoint is not selected implicitly "
        "because its training-data and licence provenance are unresolved."
    )
