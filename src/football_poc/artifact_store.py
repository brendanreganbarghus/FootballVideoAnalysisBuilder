from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


PREPARED_SEGMENT_SCHEMA_VERSION = 2
# A second copy of the same video window for the other ball source carries
# that source as a suffix, e.g. segment-0080-020-detected.
PREPARED_SEGMENT_ID = re.compile(r"segment-\d{4}-\d{3}(?:-(?:bac|detected))?")
PREPARED_SEGMENT_KEY = re.compile(
    r"segment-(?P<first>\d{4})-(?P<count>\d{3})(?:-(?P<source>bac|detected))?"
)


def segment_window_key(segment_id: str) -> str:
    """Return the shared video-window key without any ball-source suffix."""
    match = PREPARED_SEGMENT_KEY.fullmatch(segment_id)
    if match is None:
        raise ValueError("Invalid prepared segment ID")
    return f"segment-{match['first']}-{match['count']}"
PREPARED_SEGMENT_CATALOG = "15-prepared-segments"
REVIEW_WORKFLOW_ID = "football_review"
BALL_SOURCES = frozenset({"bac", "detected"})
# Reproducible or local-only files that are never published to the share.
UNPUBLISHED_FILE_PATTERNS = (
    re.compile(r"alfheim-window(?:-playable)?\.mp4"),
    re.compile(r"decoded-sampled-grayscale.*"),
    re.compile(r".*\.(?:tmp|lock)"),
)


@dataclass(frozen=True)
class SharedPreparedSegment:
    segment_id: str
    root: Path
    video: Path
    manifest: Path
    metadata: Mapping[str, object]

    @property
    def ball_source(self) -> str | None:
        value = self.metadata.get("ball_source")
        return str(value) if value in BALL_SOURCES else None


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


def _safe_relative_path(value: object, *, field: str) -> Path:
    path = Path(str(value or ""))
    if not str(path) or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} must be a safe relative path")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remove_tree(path: Path) -> None:
    def remove_readonly(
        operation: Callable[[str], object],
        item: str,
        _error: object,
    ) -> None:
        os.chmod(item, stat.S_IWRITE)
        operation(item)

    shutil.rmtree(path, onexc=remove_readonly)


def _load_shared_segment(path: Path) -> SharedPreparedSegment:
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if metadata.get("schema_version") != PREPARED_SEGMENT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported prepared-segment schema: {path}")
    segment_id = str(metadata.get("segment_id") or "")
    if PREPARED_SEGMENT_ID.fullmatch(segment_id) is None:
        raise ValueError(f"Invalid prepared segment ID in {path}")
    if path.parent.name != segment_id:
        raise ValueError(f"Prepared segment directory does not match {segment_id}")
    if metadata.get("ball_source") not in (None, *BALL_SOURCES):
        raise ValueError(f"Invalid prepared-segment ball source in {path}")
    root = path.parent.resolve()
    video = (
        root / _safe_relative_path(metadata.get("video"), field="video")
    ).resolve()
    manifest = (
        root / _safe_relative_path(metadata.get("manifest"), field="manifest")
    ).resolve()
    if not video.is_relative_to(root) or not manifest.is_relative_to(root):
        raise ValueError(f"Prepared-segment path escapes its bundle: {path}")
    if not video.is_file() or not manifest.is_file():
        raise FileNotFoundError(f"Prepared segment bundle is incomplete: {root}")
    return SharedPreparedSegment(
        segment_id=segment_id,
        root=root,
        video=video,
        manifest=manifest,
        metadata=metadata,
    )


def discover_prepared_segments(
    artifact_root: Path | None = None,
) -> tuple[SharedPreparedSegment, ...]:
    root = (artifact_root or discover_artifact_root())
    if root is None:
        return ()
    catalog = root / PREPARED_SEGMENT_CATALOG
    if not catalog.is_dir():
        return ()
    segments: dict[str, SharedPreparedSegment] = {}
    for manifest in sorted(catalog.glob("*/*/*/segment.json")):
        segment = _load_shared_segment(manifest)
        if segment.segment_id in segments:
            raise ValueError(
                f"Duplicate shared prepared segment: {segment.segment_id}"
            )
        segments[segment.segment_id] = segment
    return tuple(segments[key] for key in sorted(segments))


def find_prepared_segment(
    segment_id: str,
    artifact_root: Path | None = None,
) -> SharedPreparedSegment | None:
    if PREPARED_SEGMENT_ID.fullmatch(segment_id) is None:
        raise ValueError("Invalid prepared segment ID")
    return next(
        (
            segment
            for segment in discover_prepared_segments(artifact_root)
            if segment.segment_id == segment_id
        ),
        None,
    )


def _is_published_file(relative: Path) -> bool:
    return not any(
        pattern.fullmatch(relative.name) for pattern in UNPUBLISHED_FILE_PATTERNS
    )


def publish_prepared_segment(
    source: Path,
    *,
    artifact_root: Path | None = None,
    source_metadata: Mapping[str, str],
) -> SharedPreparedSegment:
    source = source.resolve()
    if PREPARED_SEGMENT_ID.fullmatch(source.name) is None:
        raise ValueError(f"Invalid prepared segment directory: {source.name}")
    root = artifact_root or discover_artifact_root()
    if root is None:
        raise FileNotFoundError("Set FOOTBALL_ARTIFACT_ROOT before publication")
    manifest_path = source / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Prepared segment is incomplete: {source}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    video_path = source / "alfheim-window-playable.mp4"
    if not video_path.is_file():
        video_path = (
            source
            / _safe_relative_path(
                manifest.get("playable_video", manifest.get("video")),
                field="video",
            )
        ).resolve()
    if not video_path.is_relative_to(source) or not video_path.is_file():
        raise FileNotFoundError(f"Prepared segment is incomplete: {source}")
    status_path = source / "analysis-status.json"
    status = (
        json.loads(status_path.read_text(encoding="utf-8"))
        if status_path.is_file()
        else {}
    )
    ball_source = status.get("ball_source")
    if ball_source not in BALL_SOURCES:
        raise ValueError(
            "Prepared segment has no completed run with a recorded ball source"
        )

    camera_id = str(source_metadata.get("camera_id") or "").strip()
    recording_id = str(source_metadata.get("recording_id") or "").strip()
    if (
        not re.fullmatch(r"[A-Za-z0-9._-]+", camera_id)
        or not re.fullmatch(r"[A-Za-z0-9._-]+", recording_id)
    ):
        raise ValueError(
            "camera_id and recording_id must be safe path identifiers"
        )
    destination = (
        root
        / PREPARED_SEGMENT_CATALOG
        / camera_id
        / recording_id
        / source.name
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{source.name}-", dir=destination.parent)
    )
    backup = destination.with_name(f".{destination.name}.previous")
    try:
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if (
                not path.is_file()
                or path == manifest_path
                or path == video_path
                or not _is_published_file(relative)
            ):
                continue
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        shutil.copy2(video_path, staging / "segment.mp4")
        copied_manifest = {
            key: value
            for key, value in manifest.items()
            if key != "review_workflows"
        }
        copied_manifest.update(
            {"video": "segment.mp4", "playable_video": "segment.mp4"}
        )
        (staging / "manifest.json").write_text(
            json.dumps(copied_manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        metadata = {
            "schema_version": PREPARED_SEGMENT_SCHEMA_VERSION,
            "segment_id": source.name,
            "dataset_id": "alfheim",
            "source_start_seconds": float(manifest["source_start_seconds"]),
            "duration_seconds": float(manifest["duration_seconds"]),
            "video": "segment.mp4",
            "manifest": "manifest.json",
            "ball_source": ball_source,
            **dict(source_metadata),
        }
        (staging / "segment.json").write_text(
            json.dumps(metadata, indent=2) + "\n",
            encoding="utf-8",
        )
        write_checksum_manifest(staging)
        if backup.exists():
            _remove_tree(backup)
        if destination.exists():
            destination.rename(backup)
        staging.rename(destination)
        if backup.exists():
            _remove_tree(backup)
    except Exception:
        if staging.exists():
            _remove_tree(staging)
        if backup.exists() and not destination.exists():
            backup.rename(destination)
        raise
    return _load_shared_segment(destination / "segment.json")


def create_ball_source_copy(
    base: SharedPreparedSegment,
    ball_source: str,
) -> SharedPreparedSegment:
    """Copy only the raw video window into a sibling bundle for another ball source.

    No derived artifact, cache, review label or coordinate is copied; the new
    bundle starts unprocessed so its ball source runs from its own inputs.
    """
    if ball_source not in BALL_SOURCES:
        raise ValueError("Invalid ball source")
    window_key = segment_window_key(base.segment_id)
    segment_id = f"{window_key}-{ball_source}"
    destination = base.root.parent / segment_id
    if destination.exists():
        return _load_shared_segment(destination / "segment.json")
    staging = Path(
        tempfile.mkdtemp(prefix=f".{segment_id}-", dir=base.root.parent)
    )
    try:
        shutil.copy2(base.video, staging / "segment.mp4")
        manifest = json.loads(base.manifest.read_text(encoding="utf-8"))
        manifest.pop("review_workflows", None)
        manifest.update({"video": "segment.mp4", "playable_video": "segment.mp4"})
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        metadata = {
            key: value
            for key, value in base.metadata.items()
            if key not in {"segment_id", "ball_source", "video", "manifest"}
        }
        metadata.update(
            {
                "schema_version": PREPARED_SEGMENT_SCHEMA_VERSION,
                "segment_id": segment_id,
                "video": "segment.mp4",
                "manifest": "manifest.json",
                "ball_source": ball_source,
            }
        )
        (staging / "segment.json").write_text(
            json.dumps(metadata, indent=2) + "\n",
            encoding="utf-8",
        )
        write_checksum_manifest(staging)
        staging.rename(destination)
    except Exception:
        if staging.exists():
            _remove_tree(staging)
        raise
    return _load_shared_segment(destination / "segment.json")


def write_checksum_manifest(bundle: Path) -> None:
    files = sorted(
        path for path in bundle.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    )
    (bundle / "checksums.sha256").write_text(
        "".join(
            f"{_sha256(path)} *{path.relative_to(bundle).as_posix()}\n"
            for path in files
        ),
        encoding="utf-8",
    )


def verify_prepared_segment(segment: SharedPreparedSegment) -> None:
    checksum_path = segment.root / "checksums.sha256"
    if not checksum_path.is_file():
        raise FileNotFoundError(
            f"Prepared segment checksum manifest is missing: {segment.root}"
        )
    expected: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        digest, marker, relative = line.partition(" *")
        if not marker or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"Invalid checksum entry in {checksum_path}")
        expected[relative] = digest
    actual_files = {
        path.relative_to(segment.root).as_posix(): path
        for path in segment.root.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    }
    if set(expected) != set(actual_files):
        raise ValueError(f"Prepared segment file inventory mismatch: {segment.root}")
    for relative, path in actual_files.items():
        if _sha256(path) != expected[relative]:
            raise ValueError(f"Prepared segment checksum mismatch: {relative}")


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
