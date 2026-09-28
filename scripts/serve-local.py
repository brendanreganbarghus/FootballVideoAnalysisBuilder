from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import BinaryIO
from urllib.parse import parse_qs, urlparse

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SOURCE = PROJECT_ROOT / "src"
if str(LOCAL_SOURCE) not in sys.path:
    sys.path.insert(0, str(LOCAL_SOURCE))


def review_launcher_registry_paths() -> tuple[Path, ...]:
    legacy = (
        PROJECT_ROOT
        / "benchmarks"
        / "alfheim"
        / "generated"
        / ".football-event-review-urls.json"
    )
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        common = Path(result.stdout.strip())
        if not common.is_absolute():
            common = PROJECT_ROOT / common
        shared = common.resolve() / ".football-event-review-urls.json"
        return (shared, legacy)
    except (OSError, subprocess.SubprocessError):
        return (legacy,)

from football_poc.alfheim_segments import (
    alfheim_source_info,
    plan_alfheim_segment,
    resolve_alfheim_pano,
)
from football_poc.event_comparison import compare_manual_events
from football_poc.artifact_store import (
    discover_prepared_segments,
    find_prepared_segment,
)
from football_poc.coordination import (
    CoordinationConfig,
    DatabaseHealth,
    DatabaseMode,
    DatabaseUnavailableError,
    Identity,
    LeaseConflictError,
    LeaseTokenError,
    ManualEventMapping,
    ManualReferenceMember,
    Segment,
    StateVersionConflictError,
    bootstrap_coordination,
    load_or_create_machine_identity,
)
from football_poc.coordination.history_import import build_reconciliation_hook


WORKFLOW_IDS = frozenset({"innovation_day_bac", "live_iteration_25"})
RETIRED_INNOVATION_SEGMENTS = frozenset(
    {
        "segment-0060-020",
        "segment-0300-020",
        "segment-0540-020",
        "segment-0540-060",
        "segment-0575-020",
        "segment-0595-020",
        "segment-0615-020",
    }
)


def _iso(value: object) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


class UnavailableCoordinationRepository:
    def __init__(self, detail: str) -> None:
        self._health = DatabaseHealth(DatabaseMode.UNAVAILABLE, detail)

    def health(self) -> object:
        return self._health

    def close(self) -> None:
        pass


class CoordinationService:
    """HTTP-safe facade over the finalized coordination repository API."""

    def __init__(
        self,
        repository: object,
        *,
        identity: object | None = None,
        health: object | None = None,
    ) -> None:
        self.repository = repository
        self.identity = identity
        self._health = health or repository.health()
        self._repository_lock = threading.RLock()

    @classmethod
    def bootstrap(cls) -> "CoordinationService":
        try:
            config = CoordinationConfig.from_environment()
            artifact_root = shared_artifact_root()
            reconciliation_hook = (
                build_reconciliation_hook(
                    artifact_root,
                    regression_paths={
                        "live_iteration_25": (
                            PROJECT_ROOT
                            / "benchmarks"
                            / "alfheim"
                            / "live-regressions.json"
                        )
                    },
                )
                if artifact_root
                else None
            )
            result = bootstrap_coordination(
                config,
                reconciliation_hook=reconciliation_hook,
            )
        except Exception as error:
            repository = UnavailableCoordinationRepository(
                "Coordination startup configuration failed: "
                f"{type(error).__name__}"
            )
            return cls(repository)
        identity = None
        health = result.health
        if health.mode is DatabaseMode.AVAILABLE:
            try:
                identity = load_or_create_machine_identity(
                    config.machine_id_path
                )
                result.repository.register_identity(
                    Identity(
                        identity.developer_id,
                        identity.machine_id,
                        identity.domain,
                        identity.username,
                        identity.hostname,
                        identity.ip_address,
                    )
                )
            except Exception as error:
                health = type(health)(
                    DatabaseMode.UNAVAILABLE,
                    "Coordination identity registration failed: "
                    f"{type(error).__name__}",
                    health.deployment,
                )
        elif health.mode is DatabaseMode.UNAVAILABLE:
            health = type(health)(
                DatabaseMode.UNAVAILABLE,
                "PostgreSQL coordination is unavailable",
                health.deployment,
            )
        return cls(result.repository, identity=identity, health=health)

    @property
    def mode(self) -> DatabaseMode:
        return self._health.mode

    def health_payload(self) -> dict[str, object]:
        deployment = self._health.deployment
        return {
            "mode": self.mode.value,
            "detail": self._health.detail,
            "deployment": (
                {
                    "deploymentId": deployment.deployment_id,
                    "authorityId": deployment.authority_id,
                    "authorityEpoch": deployment.authority_epoch,
                    "retired": deployment.retired,
                }
                if deployment
                else None
            ),
        }

    def identity_payload(self) -> dict[str, object]:
        identity = self.identity
        return {
            "mode": self.mode.value,
            "identity": (
                {
                    "developerId": identity.developer_id,
                    "displayName": (
                        f"{identity.domain}\\{identity.username}"
                        if identity.domain
                        else identity.username
                    ),
                    "machineId": identity.machine_id,
                    "machineLabel": identity.hostname,
                }
                if identity
                else None
            ),
        }

    def require_available(self) -> None:
        if self.mode is not DatabaseMode.AVAILABLE or self.identity is None:
            raise DatabaseUnavailableError(self._health.detail)

    @staticmethod
    def validate_key(workflow: object, segment: object) -> tuple[str, str]:
        workflow_id = str(workflow or "").strip()
        segment_id = str(segment or "").strip()
        if workflow_id not in WORKFLOW_IDS:
            raise ValueError("Unknown coordination workflow")
        if not re.fullmatch(r"(?:segment-\d{4}-\d{3}|alfheim-window-555)", segment_id):
            raise ValueError("Invalid coordination segment")
        return workflow_id, segment_id

    @staticmethod
    def lease_payload(lease: object | None, *, token: str | None = None) -> object:
        if lease is None:
            return None
        return {
            "workflow": lease.workflow_id,
            "segment": lease.segment_id,
            "holderId": lease.owner_id,
            "holderName": lease.owner_id,
            "machineId": lease.machine_id,
            "machineLabel": lease.machine_id,
            "stage": lease.stage,
            "acquiredAt": _iso(lease.acquired_at),
            "heartbeatAt": _iso(lease.heartbeat_at),
            "expiresAt": _iso(lease.expires_at),
            **({"leaseToken": lease.token} if token == lease.token else {}),
        }

    def list_segments(self, workflow: str) -> dict[str, object]:
        workflow_id, _ = self.validate_key(workflow, "segment-0000-001")
        self.require_available()
        with self._repository_lock:
            leases = {
                lease.segment_id: lease
                for lease in self.repository.list_active_leases(workflow_id)
            }
            segments = self.repository.list_segments(workflow_id)
        return {
            "workflow": workflow_id,
            "segments": [
                {
                    "workflow": item.workflow_id,
                    "segment": item.segment_id,
                    "logicalKey": item.logical_key,
                    "metadata": dict(item.metadata),
                    "createdAt": _iso(item.created_at),
                    "updatedAt": _iso(item.updated_at),
                    "coordinationLease": self.lease_payload(
                        leases.get(item.segment_id)
                    ),
                }
                for item in segments
            ],
        }

    def active_leases(self, workflow: str) -> dict[str, object]:
        workflow_id, _ = self.validate_key(workflow, "segment-0000-001")
        self.require_available()
        with self._repository_lock:
            leases = self.repository.list_active_leases(workflow_id)
        return {
            "workflow": workflow_id,
            "leases": [
                self.lease_payload(lease)
                for lease in leases
            ],
        }

    def read_state(self, workflow: str, segment: str) -> dict[str, object]:
        workflow_id, segment_id = self.validate_key(workflow, segment)
        self.require_available()
        with self._repository_lock:
            snapshot = self.repository.get_state(workflow_id, segment_id)
            lease = self.repository.get_lease(workflow_id, segment_id)
        return {
            "workflow": workflow_id,
            "segment": segment_id,
            "version": snapshot.version if snapshot else 0,
            "state": dict(snapshot.state) if snapshot else None,
            "authorId": snapshot.author_id if snapshot else None,
            "createdAt": _iso(snapshot.created_at) if snapshot else None,
            "coordinationLease": self.lease_payload(lease),
        }

    def acquire(self, body: dict[str, object]) -> dict[str, object]:
        self.require_available()
        workflow, segment = self.validate_key(
            body.get("workflow"), body.get("segment")
        )
        stage = str(body.get("stage") or "event-review").strip()
        if not stage:
            raise ValueError("stage must not be empty")
        with self._repository_lock:
            self.repository.upsert_segment(
                Segment(workflow, segment, segment, {"source": "local-canvas"})
            )
            lease = self.repository.acquire_lease(
                workflow,
                segment,
                self.identity.developer_id,
                self.identity.machine_id,
                stage,
            )
            snapshot = self.repository.get_state(workflow, segment)
        return {
            "lease": self.lease_payload(lease, token=lease.token),
            "version": snapshot.version if snapshot else 0,
        }

    def heartbeat(self, body: dict[str, object]) -> dict[str, object]:
        self.require_available()
        token = str(body.get("leaseToken") or "").strip()
        if not token:
            raise ValueError("leaseToken is required")
        with self._repository_lock:
            lease = self.repository.heartbeat_lease(token)
        return {"lease": self.lease_payload(lease, token=token)}

    def release(self, body: dict[str, object]) -> dict[str, object]:
        self.require_available()
        token = str(body.get("leaseToken") or "").strip()
        if not token:
            raise ValueError("leaseToken is required")
        with self._repository_lock:
            if not self.repository.release_lease(token):
                raise LeaseTokenError("Unknown editing lease token")
        return {"released": True}

    def mutate_state(self, body: dict[str, object]) -> dict[str, object]:
        self.require_available()
        workflow, segment = self.validate_key(
            body.get("workflow"), body.get("segment")
        )
        token = str(body.get("leaseToken") or "").strip()
        version = body.get("expectedVersion")
        state = body.get("state")
        if not token:
            raise ValueError("leaseToken is required")
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise ValueError("expectedVersion must be a non-negative integer")
        if not isinstance(state, dict):
            raise ValueError("state must be a JSON object")
        with self._repository_lock:
            snapshot = self.repository.mutate_state(
                workflow,
                segment,
                version,
                state,
                self.identity.developer_id,
                token,
            )
        return {
            "workflow": workflow,
            "segment": segment,
            "version": snapshot.version,
            "state": dict(snapshot.state),
            "authorId": snapshot.author_id,
            "createdAt": _iso(snapshot.created_at),
        }

    def _manual_reference_payload(
        self,
        workflow: str,
        segment: str,
        reference: object | None,
    ) -> object | None:
        if reference is None:
            return None
        events = []
        for member in reference.members:
            event = self.repository.get_manual_event_revision(
                workflow,
                segment,
                member.event_key,
                member.event_revision,
            )
            if event is None:
                continue
            events.append(
                {
                    "key": event.event_key,
                    "revision": event.revision,
                    "timestampMs": event.timestamp_ms,
                    "seconds": event.timestamp_ms / 1000,
                    "sourceFrame": event.source_frame,
                    **dict(event.payload),
                }
            )
        return {
            "revision": reference.revision,
            "status": reference.status,
            "basedOnRevision": reference.based_on_revision,
            "events": events,
            "mappings": {
                mapping.manual_event_key: mapping.engine_event_key
                for mapping in reference.mappings
            },
            "createdBy": reference.created_by,
            "createdAt": _iso(reference.created_at),
            "approvedBy": reference.approved_by,
            "approvedAt": _iso(reference.approved_at),
        }

    def read_manual_reference(
        self, workflow: str, segment: str
    ) -> dict[str, object]:
        workflow_id, segment_id = self.validate_key(workflow, segment)
        if workflow_id != "innovation_day_bac":
            raise ValueError("Manual references are available only for Innovation")
        self.require_available()
        with self._repository_lock:
            draft = self.repository.get_manual_reference_set(
                workflow_id, segment_id
            )
            approved = self.repository.get_approved_manual_reference_set(
                workflow_id, segment_id
            )
        return {
            "workflow": workflow_id,
            "segment": segment_id,
            "draft": self._manual_reference_payload(
                workflow_id, segment_id, draft
            ) if draft and draft.status == "draft" else None,
            "approved": self._manual_reference_payload(
                workflow_id, segment_id, approved
            ),
        }

    def mutate_manual_reference(
        self, body: dict[str, object]
    ) -> dict[str, object]:
        self.require_available()
        workflow, segment = self.validate_key(
            body.get("workflow"), body.get("segment")
        )
        if workflow != "innovation_day_bac":
            raise ValueError("Manual references are available only for Innovation")
        token = str(body.get("leaseToken") or "").strip()
        events = body.get("events")
        mappings = body.get("mappings", {})
        approve = body.get("approve", False)
        if not token:
            raise ValueError("leaseToken is required")
        if not isinstance(events, list) or not isinstance(mappings, dict):
            raise ValueError("events and mappings must be JSON collections")
        if not isinstance(approve, bool):
            raise ValueError("approve must be a boolean")
        prepared_events = []
        seen_keys: set[str] = set()
        for ordinal, item in enumerate(events):
            if not isinstance(item, dict):
                raise ValueError("Each manual event must be a JSON object")
            key = str(item.get("key") or "").strip()
            timestamp_ms = item.get("timestampMs")
            team = str(item.get("team") or "")
            event_type = str(item.get("type") or "")
            if not re.fullmatch(r"M[1-9]\d*", key) or key in seen_keys:
                raise ValueError("Manual event keys must be unique M# values")
            if (
                isinstance(timestamp_ms, bool)
                or not isinstance(timestamp_ms, int)
                or timestamp_ms < 0
                or timestamp_ms > 60_000
            ):
                raise ValueError("timestampMs must be an integer from 0 to 60000")
            if team not in {"black", "red"}:
                raise ValueError("Unknown manual event team")
            if event_type not in {"completed_pass", "turnover", "shot_on_target"}:
                raise ValueError("Unknown manual event type")
            seen_keys.add(key)
            prepared_events.append(
                (
                    ordinal,
                    key,
                    timestamp_ms,
                    min(1499, round(timestamp_ms * 25 / 1000)),
                    {
                        "team": team,
                        "type": event_type,
                        "active": True,
                        "deleted": False,
                    },
                )
            )
        normalized_mappings = []
        seen_engine_keys: set[str] = set()
        for manual_key, engine_key_value in mappings.items():
            engine_key = str(engine_key_value)
            if manual_key not in seen_keys:
                raise ValueError("Mapping references a non-member M#")
            if not re.fullmatch(r"E[1-9]\d*", engine_key):
                raise ValueError("Mapping engine key must be an E#")
            if engine_key in seen_engine_keys:
                raise ValueError("Each E# may map to only one M#")
            seen_engine_keys.add(engine_key)
            normalized_mappings.append(
                ManualEventMapping(manual_key, engine_key)
            )
        with self._repository_lock:
            reference = self.repository.get_manual_reference_set(
                workflow, segment
            )
            if reference is None or reference.status != "draft":
                reference = self.repository.create_manual_reference_draft(
                    workflow,
                    segment,
                    self.identity.developer_id,
                    token,
                )
            members = []
            for (
                ordinal,
                key,
                timestamp_ms,
                source_frame,
                payload,
            ) in prepared_events:
                current = self.repository.get_manual_event_revision(
                    workflow, segment, key
                )
                if (
                    current is None
                    or current.timestamp_ms != timestamp_ms
                    or current.source_frame != source_frame
                    or any(current.payload.get(name) != value
                           for name, value in payload.items())
                ):
                    current = self.repository.append_manual_event(
                        workflow,
                        segment,
                        key,
                        timestamp_ms,
                        source_frame,
                        payload,
                        self.identity.developer_id,
                        token,
                    )
                members.append(
                    ManualReferenceMember(ordinal, key, current.revision)
                )
            reference = self.repository.replace_manual_reference_membership(
                workflow,
                segment,
                reference.revision,
                members,
                self.identity.developer_id,
                token,
            )
            reference = self.repository.replace_manual_event_mappings(
                workflow,
                segment,
                reference.revision,
                normalized_mappings,
                self.identity.developer_id,
                token,
            )
            if approve:
                reference = self.repository.approve_manual_reference_set(
                    workflow,
                    segment,
                    reference.revision,
                    self.identity.developer_id,
                    token,
                )
        return {
            "workflow": workflow,
            "segment": segment,
            "reference": self._manual_reference_payload(
                workflow, segment, reference
            ),
        }

    def close(self) -> None:
        with self._repository_lock:
            self.repository.close()


def shared_artifact_root() -> Path | None:
    configured = os.environ.get("FOOTBALL_ARTIFACT_ROOT", "").strip()
    if configured:
        return Path(configured).resolve()
    one_drive = (
        os.environ.get("ONEDRIVECOMMERCIAL")
        or os.environ.get("ONEDRIVE")
        or ""
    ).strip()
    candidate = Path(one_drive) / "Innovationday Artifacts" if one_drive else None
    if candidate and (candidate / "00-governance" / "checksums.sha256").is_file():
        return candidate.resolve()
    return None


SHARED_ARTIFACT_ROOT = shared_artifact_root()
CUSTOM_CAMERA_SOURCE_ROOT: Path | None = (
    SHARED_ARTIFACT_ROOT / "10-master-data" / "custom-cameras"
    if SHARED_ARTIFACT_ROOT
    else None
)
CUSTOM_CAMERA_RUN_ROOT = PROJECT_ROOT / "benchmarks" / "custom-cameras"
ALLOWED_REVIEW_DURATIONS = frozenset({20, 30, 60})

ALFHEIM_SOURCE = {
    "club_id": "simula-alfheim-test-dataset",
    "club_name": "Simula Alfheim test dataset",
    "venue_id": "alfheim-stadium",
    "venue_name": "Alfheim Stadium",
    "camera_id": "f7a5f35d-9c61-5e9c-b6f3-795742c2c8f1",
    "camera_name": "Camera Setting 2",
    "camera_position": "main_panorama",
    "serial_number": "TESTDATA-ALFHEIM-CAMERA-SETTING-2",
    "serial_source": "assigned_test_identifier",
    "recording_id": "alfheim-pano-camera-setting-2",
}
SOCCERTRACK_SOURCE = {
    "club_id": "soccertrack-v2-test-dataset",
    "club_name": "SoccerTrack v2 test dataset",
    "venue_id": "soccertrack-recording-117093-venue",
    "venue_name": "Dataset venue for recording 117093",
    "camera_id": "6bf49dd4-eac0-57f3-9005-3020789c3a84",
    "camera_name": "Panorama",
    "camera_position": "main_panorama",
    "serial_number": "TESTDATA-SOCCERTRACK-117093-PANORAMA",
    "serial_source": "assigned_test_identifier",
    "recording_id": "soccertrack-117093-first-half",
}


def is_review_duration(duration_seconds: object) -> bool:
    if not isinstance(duration_seconds, (int, float)):
        return False
    if not math.isfinite(duration_seconds):
        return False
    rounded = round(duration_seconds)
    return (
        abs(duration_seconds - rounded) <= 0.25
        and rounded in ALLOWED_REVIEW_DURATIONS
    )


def require_review_duration(duration_seconds: float) -> int:
    if not is_review_duration(duration_seconds):
        raise ValueError(
            "AI execution requires an exact 30- or 60-second prepared segment"
        )
    return round(duration_seconds)


def workspace_environment(workspace: Path) -> dict[str, str]:
    environment = os.environ.copy()
    source = str((workspace / "src").resolve())
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        os.pathsep.join((source, existing)) if existing else source
    )
    return environment


class RangeRequestHandler(SimpleHTTPRequestHandler):
    range_to_send: tuple[int, int] | None = None
    analysis_processes: dict[str, subprocess.Popen[bytes]] = {}

    @property
    def coordination(self) -> CoordinationService:
        service = getattr(self, "coordination_service", None)
        if service is not None:
            return service
        return self.server.coordination_service

    def translate_path(self, path: str) -> str:
        request_path = urlparse(path).path
        shared_match = re.fullmatch(
            r"/shared-prepared/(segment-\d{4}-\d{3})/"
            r"((?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+)",
            request_path,
        )
        if shared_match and SHARED_ARTIFACT_ROOT:
            segment_id, filename = shared_match.groups()
            segment = find_prepared_segment(
                segment_id,
                SHARED_ARTIFACT_ROOT,
            )
            if segment is None:
                return str(SHARED_ARTIFACT_ROOT / "__invalid__")
            resolved = (segment.root / filename).resolve()
            if not resolved.is_relative_to(segment.root):
                return str(SHARED_ARTIFACT_ROOT / "__invalid__")
            return str(resolved)
        match = re.fullmatch(
            r"/shared-custom/(custom-[a-z0-9-]+)/"
            r"((?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+)",
            request_path,
        )
        if match and CUSTOM_CAMERA_SOURCE_ROOT:
            camera, filename = match.groups()
            camera_root = (CUSTOM_CAMERA_SOURCE_ROOT / camera).resolve()
            resolved = (
                CUSTOM_CAMERA_SOURCE_ROOT / camera / filename
            ).resolve()
            if not resolved.is_relative_to(camera_root):
                return str(CUSTOM_CAMERA_SOURCE_ROOT / "__invalid__")
            return str(resolved)
        return super().translate_path(path)

    def do_GET(self) -> None:
        request = urlparse(self.path)
        if request.path.startswith("/api/coordination/"):
            self._coordination_get(request)
            return
        if request.path == "/review-canvas":
            theme = parse_qs(request.query).get("theme", ["default"])[0]
            if theme not in {"default", "innovation"}:
                self.send_error(400, "Invalid review theme")
                return
            try:
                target = next(
                    str(
                        json.loads(path.read_text(encoding="utf-8"))[theme]
                    )
                    for path in review_launcher_registry_paths()
                    if path.is_file()
                )
                parsed_target = urlparse(target)
                if (
                    parsed_target.scheme != "http"
                    or parsed_target.hostname != "127.0.0.1"
                    or not parsed_target.port
                ):
                    raise ValueError("Invalid registered Canvas URL")
            except (
                FileNotFoundError,
                KeyError,
                StopIteration,
                TypeError,
                ValueError,
            ):
                self.send_error(
                    503,
                    "Open Football Event Review in Copilot once, then retry.",
                )
                return
            self.send_response(302)
            self.send_header("Location", target)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if request.path == "/api/alfheim/info":
            try:
                self._send_json(
                    200,
                    alfheim_source_info(resolve_alfheim_pano(Path.cwd())),
                )
            except (FileNotFoundError, ValueError) as error:
                self._send_json(400, {"error": str(error)})
            return
        if request.path == "/api/alfheim/segments":
            try:
                workflow = parse_qs(request.query).get("workflow", [""])[0]
                if workflow not in {"", "innovation", "live"}:
                    raise ValueError("Invalid Alfheim workflow")
                self._send_json(
                    200,
                    {
                        "segments": self._alfheim_review_segments(
                            namespace=workflow or None
                        )
                    },
                )
            except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
                self._send_json(400, {"error": str(error)})
            return
        if request.path == "/api/football/segments":
            try:
                self._send_json(200, {"segments": self._review_segments()})
            except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
                self._send_json(400, {"error": str(error)})
            return
        if request.path in {
            "/api/alfheim/status",
            "/api/alfheim/innovation/status",
            "/api/alfheim/live/status",
        }:
            try:
                cache_key = parse_qs(request.query).get("cache_key", [""])[0]
                if not re.fullmatch(r"segment-\d{4}-\d{3}", cache_key):
                    raise ValueError("Invalid segment cache key")
                namespace = {
                    "/api/alfheim/innovation/status": "innovation",
                    "/api/alfheim/live/status": "live",
                }.get(request.path)
                local_root = (
                    Path.cwd()
                    / "benchmarks"
                    / "alfheim"
                    / "generated"
                    / cache_key
                )
                prepared_root = None
                url_root = None
                if not local_root.is_dir():
                    shared = find_prepared_segment(
                        cache_key,
                        SHARED_ARTIFACT_ROOT,
                    )
                    workflow_id = {
                        "innovation": "innovation_day_bac",
                        "live": "live_iteration_25",
                    }.get(namespace)
                    if (
                        shared is not None
                        and (
                            workflow_id is None
                            or workflow_id in shared.workflows
                        )
                    ):
                        prepared_root = shared.root
                        url_root = f"/shared-prepared/{cache_key}"
                self._send_json(
                    200,
                    self._segment_status(
                        cache_key,
                        namespace=namespace,
                        prepared_root=prepared_root,
                        url_root=url_root,
                    ),
                )
            except (FileNotFoundError, ValueError) as error:
                self._send_json(400, {"error": str(error)})
            return
        super().do_GET()

    def do_POST(self) -> None:
        request_path = urlparse(self.path).path
        if request_path.startswith("/api/coordination/"):
            self._coordination_post(request_path)
            return
        if request_path == "/api/alfheim/analyze":
            self._start_segment_analysis()
            return
        if request_path == "/api/alfheim/innovation/analyze":
            self._start_segment_analysis(workflow="innovation")
            return
        if request_path == "/api/alfheim/live/analyze":
            self._start_segment_analysis(workflow="live")
            return
        if request_path == "/api/soccertrack/analyze":
            self._start_soccertrack_analysis()
            return
        if request_path == "/api/custom/analyze":
            self._start_custom_analysis()
            return
        if request_path != "/api/alfheim/segment":
            self.send_error(404)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 4096:
                raise ValueError("Request body must contain a small JSON object")
            payload = json.loads(self.rfile.read(content_length))
            if payload.get("source_id") not in {None, "alfheim"}:
                raise ValueError("This endpoint prepares only the Alfheim source")
            workflow_id = payload.get("workflow_id")
            if workflow_id not in {
                None,
                "innovation_day_bac",
                "live_iteration_25",
            }:
                raise ValueError("Unknown review workflow")
            duration_seconds = require_review_duration(
                float(payload["duration_seconds"])
            )
            pano = resolve_alfheim_pano(Path.cwd())
            plan = plan_alfheim_segment(
                pano,
                start_seconds=float(payload["start_seconds"]),
                duration_seconds=duration_seconds,
            )
            if plan.duration_seconds != duration_seconds:
                raise ValueError(
                    "The recording does not contain the full requested "
                    f"{duration_seconds}-second segment"
                )
            output = (
                Path.cwd()
                / "benchmarks"
                / "alfheim"
                / "generated"
                / (
                    f"segment-{plan.first_segment:04d}-"
                    f"{plan.segment_count:03d}"
                )
            )
            playable = output / "alfheim-window-playable.mp4"
            manifest_path = output / "manifest.json"
            prepared_manifest = (
                json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest_path.is_file()
                else {}
            )
            raw_only = (
                "ball_ground_truth" not in prepared_manifest
                and prepared_manifest.get("duration_seconds")
                == duration_seconds
                and prepared_manifest.get("source_start_seconds")
                == float(payload["start_seconds"])
            )
            if not playable.is_file() or not raw_only:
                subprocess.run(
                    [
                        sys.executable,
                        str(Path.cwd() / "scripts" / "prepare-alfheim-window.py"),
                        "--pano",
                        str(pano),
                        "--start-segment",
                        str(plan.first_segment),
                        "--segment-count",
                        str(plan.segment_count),
                        "--clip-start-seconds",
                        str(plan.clip_start_seconds),
                        "--duration-seconds",
                        str(duration_seconds),
                        "--output",
                        str(output),
                    ],
                    cwd=Path.cwd(),
                    check=True,
                )
            if workflow_id is not None:
                prepared_manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8")
                )
                registered_workflows = {
                    str(value)
                    for value in prepared_manifest.get(
                        "review_workflows",
                        [],
                    )
                }
                registered_workflows.add(str(workflow_id))
                prepared_manifest["review_workflows"] = sorted(
                    registered_workflows
                )
                temporary_manifest = manifest_path.with_suffix(".json.tmp")
                temporary_manifest.write_text(
                    f"{json.dumps(prepared_manifest, indent=2)}\n",
                    encoding="utf-8",
                )
                temporary_manifest.replace(manifest_path)
            relative = output.relative_to(Path.cwd()).as_posix()
            self._send_json(
                200,
                {
                    **plan.to_dict(),
                    "source_start_seconds": float(payload["start_seconds"]),
                    "duration_seconds": duration_seconds,
                    "video_url": f"/{relative}/alfheim-window-playable.mp4",
                    "cache_key": output.name,
                },
            )
        except (
            FileNotFoundError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            subprocess.CalledProcessError,
        ) as error:
            self._send_json(400, {"error": str(error)})

    def _start_segment_analysis(self, workflow: str = "legacy") -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 4096:
                raise ValueError("Request body must contain a small JSON object")
            payload = json.loads(self.rfile.read(content_length))
            cache_key = str(payload["cache_key"])
            events_only = payload.get("events_only", False)
            if not isinstance(events_only, bool):
                raise ValueError("events_only must be a boolean")
            evidence_only = payload.get("evidence_only", False)
            if not isinstance(evidence_only, bool):
                raise ValueError("evidence_only must be a boolean")
            resume_after_detection = payload.get("resume_after_detection", False)
            if not isinstance(resume_after_detection, bool):
                raise ValueError("resume_after_detection must be a boolean")
            focused_recovery = payload.get("focused_recovery", False)
            if not isinstance(focused_recovery, bool):
                raise ValueError("focused_recovery must be a boolean")
            coordinates_updated = payload.get("coordinates_updated", False)
            if not isinstance(coordinates_updated, bool):
                raise ValueError("coordinates_updated must be a boolean")
            rerun_events = payload.get("rerun_events", True)
            if not isinstance(rerun_events, bool):
                raise ValueError("rerun_events must be a boolean")
            if not coordinates_updated and not rerun_events:
                raise ValueError(
                    "rerun_events can be false only for a coordinate update"
                )
            if sum((
                events_only,
                evidence_only,
                resume_after_detection,
                focused_recovery,
                coordinates_updated,
            )) > 1:
                raise ValueError(
                    "events_only, evidence_only, resume_after_detection, and "
                    "focused_recovery, and coordinates_updated are exclusive"
                )
            if coordinates_updated and workflow != "innovation":
                raise ValueError(
                    "Reviewer coordinate updates are available only for Innovation"
                )
            if evidence_only and workflow != "innovation":
                raise ValueError(
                    "Evidence-only preparation is available only for Innovation"
                )
            if not re.fullmatch(r"segment-\d{4}-\d{3}", cache_key):
                raise ValueError("Invalid segment cache key")
            segment = (
                Path.cwd()
                / "benchmarks"
                / "alfheim"
                / "generated"
                / cache_key
            )
            if not (segment / "manifest.json").is_file():
                raise FileNotFoundError(f"Prepared segment not found: {cache_key}")
            prepared = json.loads(
                (segment / "manifest.json").read_text(encoding="utf-8")
            )
            if float(prepared.get("duration_seconds", 0)) not in {20, 30, 60}:
                raise ValueError(
                    "AI can run only on the prepared 20-, 30-, or 60-second "
                    "Alfheim review segments"
                )
            process_key = f"{workflow}:{cache_key}"
            current = self.analysis_processes.get(process_key)
            if current is not None and current.poll() is None:
                self._send_json(202, {"state": "processing"})
                return
            run_root = (
                segment / workflow
                if workflow in {"innovation", "live"}
                else segment
            )
            run_root.mkdir(parents=True, exist_ok=True)
            log_path = run_root / "analysis.log"
            log = log_path.open("ab")
            script_name = (
                "process-alfheim-innovation-segment.py"
                if workflow == "innovation"
                else "process-alfheim-segment.py"
            )
            arguments = [
                sys.executable,
                str(Path.cwd() / "scripts" / script_name),
                str(segment),
            ]
            if workflow == "live":
                arguments.extend(["--artifact-namespace", "live"])
            if events_only:
                arguments.append("--events-only")
            if evidence_only:
                arguments.append("--evidence-only")
            if resume_after_detection:
                arguments.append("--resume-after-detection")
            if focused_recovery:
                arguments.append("--focused-recovery")
            if coordinates_updated:
                arguments.append("--coordinates-updated")
                if not rerun_events:
                    arguments.append("--skip-events")
            process = subprocess.Popen(
                arguments,
                cwd=Path.cwd(),
                env=workspace_environment(Path.cwd()),
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            log.close()
            self.analysis_processes[process_key] = process
            self._send_json(202, {"state": "processing", "pid": process.pid})
        except (
            FileNotFoundError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            self._send_json(400, {"error": str(error)})

    def _start_soccertrack_analysis(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 4096:
                raise ValueError("Request body must contain a small JSON object")
            payload = json.loads(self.rfile.read(content_length))
            cache_key = str(payload["cache_key"])
            if cache_key != "soccertrack-117093-h1-1267-060":
                raise ValueError("Invalid SoccerTrack segment cache key")
            require_review_duration(60)
            segment = (
                Path.cwd()
                / "benchmarks"
                / "soccertrack-117093-preview"
            )
            if not (segment / "pitch-calibration.json").is_file():
                raise FileNotFoundError(
                    "Complete and save the SoccerTrack camera calibration first"
                )
            current = self.analysis_processes.get(cache_key)
            if current is not None and current.poll() is None:
                self._send_json(202, {"state": "processing"})
                return
            log = (segment / "analysis.log").open("ab")
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(
                        Path.cwd()
                        / "scripts"
                        / "process-soccertrack-segment.py"
                    ),
                    str(segment),
                ],
                cwd=Path.cwd(),
                env=workspace_environment(Path.cwd()),
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            log.close()
            self.analysis_processes[cache_key] = process
            self._send_json(202, {"state": "processing", "pid": process.pid})
        except (
            FileNotFoundError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            self._send_json(400, {"error": str(error)})

    def _start_custom_analysis(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 4096:
                raise ValueError("Request body must contain a small JSON object")
            payload = json.loads(self.rfile.read(content_length))
            cache_key = str(payload["cache_key"])
            if not re.fullmatch(r"custom-[a-z0-9-]+", cache_key):
                raise ValueError("Invalid custom camera key")
            if CUSTOM_CAMERA_SOURCE_ROOT is None:
                raise FileNotFoundError(
                    "Shared artifact storage is unavailable"
                )
            source = CUSTOM_CAMERA_SOURCE_ROOT / cache_key
            segment = CUSTOM_CAMERA_RUN_ROOT / cache_key
            if not (source / "camera.json").is_file():
                raise FileNotFoundError(f"Custom camera not found: {cache_key}")
            metadata = json.loads(
                (source / "camera.json").read_text(encoding="utf-8")
            )
            require_review_duration(float(metadata["duration_seconds"]))
            if not (source / "pitch-calibration.json").is_file():
                raise FileNotFoundError(
                    "Complete and save this camera calibration first"
                )
            segment.mkdir(parents=True, exist_ok=True)
            current = self.analysis_processes.get(cache_key)
            if current is not None and current.poll() is None:
                self._send_json(202, {"state": "processing"})
                return
            log = (segment / "analysis.log").open("ab")
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(Path.cwd() / "scripts" / "process-custom-segment.py"),
                    str(segment),
                    "--source-root",
                    str(source),
                ],
                cwd=Path.cwd(),
                env=workspace_environment(Path.cwd()),
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            log.close()
            self.analysis_processes[cache_key] = process
            self._send_json(202, {"state": "processing", "pid": process.pid})
        except (
            FileNotFoundError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            self._send_json(400, {"error": str(error)})

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _coordination_get(self, request: object) -> None:
        try:
            query = parse_qs(request.query)
            if request.path == "/api/coordination/health":
                payload = self.coordination.health_payload()
            elif request.path == "/api/coordination/identity":
                payload = self.coordination.identity_payload()
            elif request.path in {
                "/api/coordination/segments",
                "/api/coordination/catalogue",
            }:
                payload = self.coordination.list_segments(
                    query.get("workflow", [""])[0]
                )
            elif request.path in {
                "/api/coordination/leases",
                "/api/coordination/active-leases",
            }:
                payload = self.coordination.active_leases(
                    query.get("workflow", [""])[0]
                )
            elif request.path == "/api/coordination/state":
                payload = self.coordination.read_state(
                    query.get("workflow", [""])[0],
                    query.get("segment", [""])[0],
                )
            elif request.path == "/api/coordination/manual-reference":
                payload = self.coordination.read_manual_reference(
                    query.get("workflow", [""])[0],
                    query.get("segment", [""])[0],
                )
            else:
                self._send_json(404, {"error": "Coordination API not found"})
                return
            self._send_json(200, payload)
        except Exception as error:
            self._send_coordination_error(error)

    def _coordination_post(self, path: str) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 2 * 1024 * 1024:
                raise ValueError("Request body must contain a JSON object")
            body = json.loads(self.rfile.read(content_length))
            if not isinstance(body, dict):
                raise ValueError("Request body must be a JSON object")
            if path == "/api/coordination/acquire":
                payload = self.coordination.acquire(body)
            elif path == "/api/coordination/heartbeat":
                payload = self.coordination.heartbeat(body)
            elif path == "/api/coordination/release":
                payload = self.coordination.release(body)
            elif path == "/api/coordination/state":
                payload = self.coordination.mutate_state(body)
            elif path == "/api/coordination/manual-reference":
                payload = self.coordination.mutate_manual_reference(body)
            else:
                self._send_json(404, {"error": "Coordination API not found"})
                return
            self._send_json(200, payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            self._send_coordination_error(ValueError(f"Invalid JSON: {error}"))
        except Exception as error:
            self._send_coordination_error(error)

    def _send_coordination_error(self, error: Exception) -> None:
        status = (
            409
            if isinstance(error, StateVersionConflictError)
            else 423
            if isinstance(error, (LeaseConflictError, LeaseTokenError))
            else 503
            if isinstance(error, DatabaseUnavailableError)
            else 400
            if isinstance(error, ValueError)
            else 503
        )
        message = (
            "Coordination repository request failed"
            if status == 503 and not isinstance(error, DatabaseUnavailableError)
            else str(error)
        )
        self._send_json(
            status,
            {
                "error": message,
                "code": {
                    409: "state_version_conflict",
                    423: "lease_conflict",
                    503: "coordination_unavailable",
                }.get(status, "validation_error"),
            },
        )

    @staticmethod
    def _analysis_receipt(root: Path) -> tuple[dict[str, object], object | None]:
        status_path = root / "analysis-status.json"
        status = (
            json.loads(status_path.read_text(encoding="utf-8"))
            if status_path.is_file()
            else {}
        )
        started_at = status.get("started_at_utc")
        if started_at and status.get("stage") not in {"ready", "failed"}:
            started = datetime.fromisoformat(str(started_at))
            status["elapsed_seconds"] = round(
                (datetime.now(timezone.utc) - started).total_seconds(),
                3,
            )
        report_path = root / "analytics-data" / "performance-report.json"
        report = (
            json.loads(report_path.read_text(encoding="utf-8"))
            if report_path.is_file()
            else None
        )
        return status, report

    def _segment_status(
        self,
        cache_key: str,
        namespace: str | None = None,
        *,
        prepared_root: Path | None = None,
        url_root: str | None = None,
    ) -> dict[str, object]:
        segment_root = prepared_root or (
            Path.cwd()
            / "benchmarks"
            / "alfheim"
            / "generated"
            / cache_key
        )
        manifest_path = segment_root / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Prepared segment not found: {cache_key}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        root = segment_root / namespace if namespace else segment_root
        cache_path = root / "analytics-cache" / "detections.jsonl"
        processed_frames = 0
        expected_frames = 0
        if cache_path.is_file():
            with cache_path.open(encoding="utf-8") as cache:
                metadata = json.loads(cache.readline())
                processed_frames = sum(1 for line in cache if line.strip())
            frame_count = int(manifest["end_frame"]) - int(manifest["start_frame"])
            expected_frames = (
                frame_count + int(metadata["stride"]) - 1
            ) // int(metadata["stride"])
        events = root / "analytics-data" / "predicted-events.json"
        tracking = root / "analytics-data" / "tracking-verification.webm"
        analysis_status, performance = self._analysis_receipt(root)
        process_key = f"{namespace or 'legacy'}:{cache_key}"
        current_process = self.analysis_processes.get(process_key)
        relative = (
            f"{url_root.rstrip('/')}/{namespace}"
            if url_root and namespace
            else url_root.rstrip("/")
            if url_root
            else f"/{root.relative_to(Path.cwd()).as_posix()}"
        )
        if current_process is not None and current_process.poll() is None:
            state = (
                "processing"
                if analysis_status.get("stage") == "detecting"
                else "building"
            )
        elif analysis_status.get("stage") == "failed":
            state = "failed"
        elif events.is_file():
            state = "ready"
        elif analysis_status.get("stage") == "evidence_ready":
            state = "evidence_ready"
        elif analysis_status and expected_frames and processed_frames >= expected_frames:
            state = "building"
        elif expected_frames and processed_frames >= expected_frames:
            state = "detections_ready"
        elif processed_frames:
            state = "processing"
        else:
            state = "prepared"
        return {
            "cache_key": cache_key,
            "workflow": namespace or "legacy",
            "state": state,
            "processed_frames": processed_frames,
            "expected_frames": expected_frames,
            "stage": analysis_status.get("stage"),
            "message": analysis_status.get("message"),
            "run_provenance": analysis_status or None,
            "performance": performance,
            "events_url": (
                f"{relative}/analytics-data/predicted-events.json"
                if events.is_file()
                else None
            ),
            "tracking_url": (
                f"{relative}/analytics-data/tracking-verification.webm"
                if tracking.is_file()
                else None
            ),
        }

    def _shared_prepared_segments(
        self,
        namespace: str | None = None,
    ) -> list[dict[str, object]]:
        workflow_id = {
            "innovation": "innovation_day_bac",
            "live": "live_iteration_25",
        }.get(namespace)
        items: list[dict[str, object]] = []
        for shared in discover_prepared_segments(SHARED_ARTIFACT_ROOT):
            if workflow_id and workflow_id not in shared.workflows:
                continue
            metadata = dict(shared.metadata)
            manifest = json.loads(
                shared.manifest.read_text(encoding="utf-8")
            )
            first_segment, segment_count = map(
                int,
                shared.segment_id.removeprefix("segment-").split("-"),
            )
            run_root = shared.root / namespace if namespace else shared.root
            status = self._segment_status(
                shared.segment_id,
                namespace=namespace,
                prepared_root=shared.root,
                url_root=f"/shared-prepared/{shared.segment_id}",
            )
            manual_reference = run_root / "manual-reference.json"
            predicted_events = (
                run_root / "analytics-data" / "predicted-events.json"
            )
            validated = False
            if manual_reference.is_file() and predicted_events.is_file():
                manual = json.loads(
                    manual_reference.read_text(encoding="utf-8")
                )["events"]
                predicted = json.loads(
                    predicted_events.read_text(encoding="utf-8")
                )
                report = compare_manual_events(
                    manual,
                    predicted,
                    tolerance_seconds=1.0,
                    include_shots_on_target=namespace == "innovation",
                )
                validated = (
                    len(manual) == len(predicted)
                    == report["matched_event_count"]
                    and not report["unmatched_manual"]
                    and not report["unmatched_predicted"]
                )
            evidence_ready = (
                (run_root / "analytics-cache" / "ball-tracks.json").is_file()
                and (
                    run_root / "analytics-cache" / "detections.jsonl"
                ).is_file()
                and (
                    run_root / "analytics-data" / "player-tracks.json"
                ).is_file()
            )
            items.append(
                {
                    **status,
                    "cache_key": shared.segment_id,
                    "source_start_seconds": float(
                        metadata.get(
                            "source_start_seconds",
                            manifest.get(
                                "source_start_seconds",
                                first_segment * 3,
                            ),
                        )
                    ),
                    "duration_seconds": float(
                        metadata.get(
                            "duration_seconds",
                            manifest.get(
                                "duration_seconds",
                                segment_count * 3,
                            ),
                        )
                    ),
                    "raw_video_only": "ball_ground_truth" not in manifest,
                    "ball_track_available": (
                        run_root / "analytics-cache" / "ball-tracks.json"
                    ).is_file(),
                    "evidence_ready": evidence_ready,
                    "validated": validated,
                    "protected": False,
                    "video_url": (
                        f"/shared-prepared/{shared.segment_id}/"
                        f"{shared.video.relative_to(shared.root).as_posix()}"
                    ),
                    "prepared_root": str(shared.root),
                    "review_workflows": list(shared.workflows),
                    "labels_url": None,
                }
            )
        return items

    def _prepared_segments(
        self,
        namespace: str | None = None,
    ) -> list[dict[str, object]]:
        workspace = Path.cwd()
        items: list[dict[str, object]] = []
        baseline = workspace / "benchmarks" / "alfheim" / "window-555"
        baseline_video = baseline / "alfheim-window-playable.mp4"
        baseline_run_root = baseline / namespace if namespace else baseline
        baseline_events = (
            baseline_run_root / "analytics-data" / "predicted-events.json"
        )
        if baseline_video.is_file():
            baseline_manifest_path = baseline / "manifest.json"
            baseline_manifest = (
                json.loads(baseline_manifest_path.read_text(encoding="utf-8"))
                if baseline_manifest_path.is_file()
                else {}
            )
            baseline_raw_only = (
                "ball_ground_truth" not in baseline_manifest
                and is_review_duration(
                    baseline_manifest.get("duration_seconds")
                )
            )
            baseline_relative = baseline.relative_to(workspace).as_posix()
            baseline_ready = baseline_raw_only and baseline_events.is_file()
            items.append(
                {
                    "cache_key": "alfheim-window-555",
                    "source_start_seconds": 555 * 3,
                    "duration_seconds": 60,
                    "state": (
                        "ready"
                        if baseline_ready
                        else "invalid_input"
                        if not baseline_raw_only
                        else "prepared"
                    ),
                    "raw_video_only": baseline_raw_only,
                    "ball_track_available": (
                        baseline / "analytics-cache" / "ball-tracks.json"
                    ).is_file(),
                    "protected": False,
                    "video_url": (
                        f"/{baseline_relative}/alfheim-window-playable.mp4"
                    ),
                    "labels_url": None,
                }
            )

        generated = workspace / "benchmarks" / "alfheim" / "generated"
        for root in sorted(generated.iterdir()) if generated.is_dir() else ():
            match = re.fullmatch(r"segment-(\d{4})-(\d{3})", root.name)
            if not match or not root.is_dir():
                continue
            video = root / "alfheim-window-playable.mp4"
            if not video.is_file():
                continue
            first_segment, segment_count = map(int, match.groups())
            status = self._segment_status(root.name, namespace=namespace)
            manifest_path = root / "manifest.json"
            manifest = (
                json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest_path.is_file()
                else {}
            )
            raw_video_only = (
                "ball_ground_truth" not in manifest
                and float(manifest.get("duration_seconds", 0)) in {20, 30, 60}
                and Path(str(manifest.get("video", ""))).name
                in {"alfheim-window.mp4", "alfheim-window-playable.mp4"}
                and video.is_file()
            )
            run_root = root / namespace if namespace else root
            evidence_ready = (
                (run_root / "analytics-cache" / "ball-tracks.json").is_file()
                and (
                    run_root / "analytics-cache" / "detections.jsonl"
                ).is_file()
                and (
                    run_root / "analytics-data" / "player-tracks.json"
                ).is_file()
            )
            manual_reference = run_root / "manual-reference.json"
            predicted_events = (
                run_root / "analytics-data" / "predicted-events.json"
            )
            validated = False
            if (
                raw_video_only
                and manual_reference.is_file()
                and predicted_events.is_file()
            ):
                manual = json.loads(manual_reference.read_text(encoding="utf-8"))[
                    "events"
                ]
                predicted = json.loads(predicted_events.read_text(encoding="utf-8"))
                report = compare_manual_events(
                    manual,
                    predicted,
                    tolerance_seconds=1.0,
                    include_shots_on_target=namespace == "innovation",
                )
                validated = (
                    len(manual) == len(predicted) == report["matched_event_count"]
                    and not report["unmatched_manual"]
                    and not report["unmatched_predicted"]
                )
            relative = root.relative_to(workspace).as_posix()
            items.append(
                {
                    "cache_key": root.name,
                    "source_start_seconds": float(
                        manifest.get("source_start_seconds", first_segment * 3)
                    ),
                    "duration_seconds": float(
                        manifest.get("duration_seconds", segment_count * 3)
                    ),
                    "state": (
                        status["state"] if raw_video_only else "invalid_input"
                    ),
                    "raw_video_only": raw_video_only,
                    "ball_track_available": (
                        run_root / "analytics-cache" / "ball-tracks.json"
                    ).is_file(),
                    "evidence_ready": evidence_ready,
                    "validated": validated,
                    "protected": root.name
                    in {
                        "segment-0575-020",
                        "segment-0595-020",
                        "segment-0615-020",
                    },
                    "video_url": f"/{relative}/alfheim-window-playable.mp4",
                    "prepared_root": str(root.resolve()),
                    "review_workflows": [
                        str(value)
                        for value in manifest.get("review_workflows", [])
                    ],
                    "labels_url": None,
                }
            )
        local_keys = {str(item["cache_key"]) for item in items}
        items.extend(
            segment
            for segment in self._shared_prepared_segments(namespace=namespace)
            if str(segment["cache_key"]) not in local_keys
        )
        return sorted(items, key=lambda item: str(item["cache_key"]))

    def _alfheim_review_segments(
        self,
        namespace: str | None = None,
    ) -> list[dict[str, object]]:
        segments = self._prepared_segments(namespace=namespace)
        def registered_for_workflow(
            segment: dict[str, object],
            workflow_id: str,
        ) -> bool:
            return workflow_id in {
                str(value)
                for value in segment.get("review_workflows", [])
            }

        if namespace == "innovation":
            segments = [
                segment for segment in segments
                if segment.get("raw_video_only", False)
                and segment["cache_key"] not in RETIRED_INNOVATION_SEGMENTS
                and registered_for_workflow(
                    segment,
                    "innovation_day_bac",
                )
            ]
        elif namespace == "live":
            registry_path = (
                Path.cwd()
                / "benchmarks"
                / "alfheim"
                / "live-regressions.json"
            )
            registry = (
                json.loads(registry_path.read_text(encoding="utf-8"))
                if registry_path.is_file()
                else {"segments": []}
            )
            live_keys = {
                "segment-0540-020",
                "segment-0540-060",
                *(
                    str(entry["segment"])
                    for entry in registry.get("segments", [])
                ),
            }
            segments = [
                segment for segment in segments
                if (
                    segment["cache_key"] in live_keys
                    or registered_for_workflow(
                        segment,
                        "live_iteration_25",
                    )
                )
                and segment.get("raw_video_only", False)
            ]
        return [
            {
                **segment,
                **ALFHEIM_SOURCE,
                "dataset_id": "alfheim",
                "dataset_name": (
                    f"{ALFHEIM_SOURCE['club_name']} · "
                    f"{ALFHEIM_SOURCE['camera_name']}"
                ),
                "calibration_id": "alfheim-camera-setting-2",
                "calibration_status": "calibrated",
                "image_width": 4450,
                "image_height": 2000,
                "processing_supported": (
                    segment.get("raw_video_only", False)
                    and
                    segment["duration_seconds"] in {20, 30, 60}
                    and (
                        namespace != "innovation"
                        or segment.get("evidence_ready", False)
                    )
                ),
                "evidence_preparation_supported": (
                    namespace == "innovation"
                    and segment.get("raw_video_only", False)
                    and segment["duration_seconds"] in {20, 30, 60}
                ),
                "preparation_supported": True,
                "attribution": (
                    "Simula Alfheim · internal non-commercial research"
                ),
            }
            for segment in segments
        ]

    def _review_segments(self) -> list[dict[str, object]]:
        items = self._alfheim_review_segments()
        workspace = Path.cwd()
        soccertrack_video = (
            workspace
            / "benchmarks"
            / "soccertrack-117093-preview"
            / "soccertrack-117093-1267-1327-panorama.mp4"
        )
        if soccertrack_video.is_file():
            soccertrack_root = soccertrack_video.parent
            calibration_ready = (
                soccertrack_root / "pitch-calibration.json"
            ).is_file()
            events_ready = (
                soccertrack_root
                / "analytics-data"
                / "predicted-events.json"
            ).is_file()
            cache_path = (
                soccertrack_root / "analytics-cache" / "detections.jsonl"
            )
            processed_frames = 0
            if cache_path.is_file():
                with cache_path.open(encoding="utf-8") as cache:
                    next(cache, None)
                    processed_frames = sum(1 for line in cache if line.strip())
            tracking_webm = (
                soccertrack_root
                / "analytics-data"
                / "tracking-verification.webm"
            )
            tracking_mp4 = (
                soccertrack_root
                / "analytics-data"
                / "tracking-verification.mp4"
            )
            tracking = (
                tracking_webm if tracking_webm.is_file() else tracking_mp4
            )
            current = self.analysis_processes.get(
                "soccertrack-117093-h1-1267-060"
            )
            processing = current is not None and current.poll() is None
            analysis_status, performance = self._analysis_receipt(
                soccertrack_root
            )
            state = (
                "processing"
                if processing
                else "failed"
                if analysis_status.get("stage") == "failed"
                else "ready"
                if events_ready
                else "prepared"
            )
            relative = soccertrack_video.relative_to(workspace).as_posix()
            items.append(
                {
                    **SOCCERTRACK_SOURCE,
                    "cache_key": "soccertrack-117093-h1-1267-060",
                    "dataset_id": "soccertrack-v2",
                    "dataset_name": (
                        f"{SOCCERTRACK_SOURCE['club_name']} · "
                        f"{SOCCERTRACK_SOURCE['camera_name']}"
                    ),
                    "calibration_id": "soccertrack-117093-panorama",
                    "calibration_status": (
                        "calibrated" if calibration_ready else "not_calibrated"
                    ),
                    "image_width": 4096,
                    "image_height": 1080,
                    "source_start_seconds": 1267.04,
                    "duration_seconds": 60,
                    "state": state,
                    "raw_video_only": True,
                    "processed_frames": processed_frames,
                    "expected_frames": 300,
                    "stage": analysis_status.get("stage"),
                    "message": analysis_status.get("message"),
                    "run_provenance": analysis_status or None,
                    "performance": performance,
                    "ball_track_available": (
                        soccertrack_root
                        / "analytics-cache"
                        / "ball-tracks.json"
                    ).is_file(),
                    "validated": False,
                    "protected": False,
                    "processing_supported": calibration_ready,
                    "preparation_supported": False,
                    "video_url": f"/{relative}",
                    "labels_url": None,
                    "tracking_url": (
                        f"/{tracking.relative_to(workspace).as_posix()}"
                        if tracking.is_file()
                        else None
                    ),
                    "attribution": "SoccerTrack v2 · CC BY 4.0",
                }
            )
        custom_root = CUSTOM_CAMERA_SOURCE_ROOT
        if custom_root and custom_root.is_dir():
            for root in sorted(custom_root.iterdir()):
                metadata_path = root / "camera.json"
                if not root.is_dir() or not metadata_path.is_file():
                    continue
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                video = root / str(metadata["video_filename"])
                if not video.is_file():
                    continue
                capture = cv2.VideoCapture(str(video))
                try:
                    if not capture.isOpened():
                        continue
                    fps = float(capture.get(cv2.CAP_PROP_FPS))
                    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
                finally:
                    capture.release()
                if fps <= 0 or frame_count <= 0:
                    continue
                duration = frame_count / fps
                calibration_ready = (root / "pitch-calibration.json").is_file()
                run_root = CUSTOM_CAMERA_RUN_ROOT / root.name
                events = run_root / "analytics-data" / "predicted-events.json"
                tracking = (
                    run_root / "analytics-data" / "tracking-verification.webm"
                )
                current = self.analysis_processes.get(root.name)
                processing = current is not None and current.poll() is None
                analysis_status, performance = self._analysis_receipt(run_root)
                state = (
                    "processing"
                    if processing
                    else "failed"
                    if analysis_status.get("stage") == "failed"
                    else "ready"
                    if events.is_file()
                    else "prepared"
                )
                processed_frames = 0
                cache_path = (
                    run_root / "analytics-cache" / "detections.jsonl"
                )
                if cache_path.is_file():
                    with cache_path.open(encoding="utf-8") as cache:
                        next(cache, None)
                        processed_frames = sum(
                            1 for line in cache if line.strip()
                        )
                items.append(
                    {
                        "cache_key": root.name,
                        "dataset_id": root.name,
                        "club_id": str(
                            metadata.get("club_id", metadata["camera_id"])
                        ),
                        "club_name": str(
                            metadata.get("club_name", "Custom source")
                        ),
                        "venue_id": str(
                            metadata.get("venue_id", metadata["camera_id"])
                        ),
                        "venue_name": str(
                            metadata.get("venue_name", "Custom venue")
                        ),
                        "camera_id": str(metadata["camera_id"]),
                        "camera_name": str(metadata["camera_name"]),
                        "camera_position": str(
                            metadata.get("camera_position", "unspecified")
                        ),
                        "serial_number": metadata.get(
                            "manufacturer_serial_number"
                        ),
                        "serial_source": (
                            "manufacturer"
                            if metadata.get("manufacturer_serial_number")
                            else None
                        ),
                        "recording_id": str(
                            metadata.get("recording_id", root.name)
                        ),
                        "dataset_name": (
                            f"{metadata.get('club_name', 'Custom source')} · "
                            f"{metadata['camera_name']}"
                        ),
                        "calibration_id": str(metadata["camera_id"]),
                        "calibration_status": (
                            "calibrated"
                            if calibration_ready
                            else "not_calibrated"
                        ),
                        "image_width": int(metadata["image_width"]),
                        "image_height": int(metadata["image_height"]),
                        "source_start_seconds": 0,
                        "duration_seconds": duration,
                        "state": state,
                        "raw_video_only": is_review_duration(duration),
                        "processed_frames": processed_frames,
                        "expected_frames": (frame_count + 4) // 5,
                        "stage": analysis_status.get("stage"),
                        "message": analysis_status.get("message"),
                        "run_provenance": analysis_status or None,
                        "performance": performance,
                        "ball_track_available": (
                            run_root
                            / "analytics-cache"
                            / "ball-tracks.json"
                        ).is_file(),
                        "validated": False,
                        "protected": False,
                        "processing_supported": (
                            calibration_ready
                            and is_review_duration(duration)
                        ),
                        "preparation_supported": False,
                        "video_url": (
                            f"/shared-custom/{root.name}/"
                            f"{metadata['video_filename']}"
                        ),
                        "labels_url": None,
                        "tracking_url": (
                            f"/{tracking.relative_to(workspace).as_posix()}"
                            if tracking.is_file()
                            else None
                        ),
                        "attribution": (
                            "User-provided footage · isolated camera workspace"
                        ),
                    }
                )
        return items

    def send_head(self) -> BinaryIO | None:
        path = Path(self.translate_path(self.path))
        range_header = self.headers.get("Range")
        if not range_header or not path.is_file():
            self.range_to_send = None
            return super().send_head()

        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
        if not match:
            self.send_error(416, "Only a single byte range is supported")
            return None
        size = path.stat().st_size
        start_text, end_text = match.groups()
        if not start_text:
            length = int(end_text)
            start = max(0, size - length)
            end = size - 1
        else:
            start = int(start_text)
            end = min(int(end_text) if end_text else size - 1, size - 1)
        if start >= size or start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None

        file = path.open("rb")
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Last-Modified", self.date_time_string(path.stat().st_mtime))
        self.end_headers()
        self.range_to_send = (start, end)
        return file

    def copyfile(self, source: BinaryIO, outputfile: BinaryIO) -> None:
        if self.range_to_send is None:
            shutil.copyfileobj(source, outputfile)
            return
        start, end = self.range_to_send
        source.seek(start)
        remaining = end - start + 1
        while remaining:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            try:
                outputfile.write(chunk)
            except (
                BrokenPipeError,
                ConnectionAbortedError,
                ConnectionResetError,
            ):
                break
            remaining -= len(chunk)

    def end_headers(self) -> None:
        if "Range" not in self.headers:
            self.send_header("Accept-Ranges", "bytes")
        request_path = urlparse(self.path).path
        if request_path.endswith((".html", ".json")) or request_path.startswith(
            "/api/"
        ):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve local POC files with browser video range requests."
    )
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--directory", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()
    os.chdir(args.directory)
    coordination = CoordinationService.bootstrap()
    server = ThreadingHTTPServer((args.bind, args.port), RangeRequestHandler)
    server.coordination_service = coordination
    print(f"Serving {args.directory.resolve()} on http://{args.bind}:{args.port}")
    print(f"Coordination: {coordination.mode.value}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
        coordination.close()


if __name__ == "__main__":
    main()
