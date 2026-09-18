from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class DatabaseMode(str, Enum):
    DISABLED = "disabled"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class DatabaseHealth:
    mode: DatabaseMode
    detail: str
    deployment: "EnvironmentIdentity | None" = None


@dataclass(frozen=True)
class EnvironmentIdentity:
    deployment_id: str
    authority_id: str
    authority_epoch: int
    retired: bool = False


@dataclass(frozen=True)
class Identity:
    developer_id: str
    machine_id: str
    domain: str
    username: str
    hostname: str
    ip_address: str | None = None


@dataclass(frozen=True)
class Segment:
    workflow_id: str
    segment_id: str
    logical_key: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class EditingLease:
    workflow_id: str
    segment_id: str
    owner_id: str
    machine_id: str
    stage: str
    token: str
    acquired_at: datetime
    heartbeat_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class StateSnapshot:
    workflow_id: str
    segment_id: str
    version: int
    state: Mapping[str, Any]
    author_id: str
    created_at: datetime


@dataclass(frozen=True)
class ManualEventRevision:
    workflow_id: str
    segment_id: str
    event_key: str
    revision: int
    timestamp_ms: int
    source_frame: int
    payload: Mapping[str, Any]
    actor_id: str
    created_at: datetime


@dataclass(frozen=True)
class ManualReferenceMember:
    ordinal: int
    event_key: str
    event_revision: int


@dataclass(frozen=True)
class ManualEventMapping:
    manual_event_key: str
    engine_event_key: str


@dataclass(frozen=True)
class ManualReferenceSetRevision:
    workflow_id: str
    segment_id: str
    revision: int
    status: str
    based_on_revision: int | None
    members: tuple[ManualReferenceMember, ...]
    mappings: tuple[ManualEventMapping, ...]
    created_by: str
    created_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    provider: str
    logical_key: str
    content_hash: str
    metadata: Mapping[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class AuditEntry:
    sequence: int
    action: str
    actor_id: str
    workflow_id: str | None
    segment_id: str | None
    machine_id: str | None
    payload: Mapping[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class ClaimedJob:
    job_id: str
    workflow_id: str
    segment_id: str | None
    job_type: str
    payload: Mapping[str, Any]
    attempt_id: str
    worker_id: str
    lease_token: str
    lease_expires_at: datetime


@dataclass(frozen=True)
class JobTerminalResult:
    job_id: str
    attempt_id: str
    status: str
    result: Mapping[str, Any]
    finished_at: datetime


@dataclass(frozen=True)
class HistoricalImportSource:
    workflow_id: str
    provider: str
    logical_key: str
    source_sha256: str
    segment_id: str
    state: Mapping[str, Any]
    source_size: int
    original_state: Mapping[str, Any] | None = None
    canonicalized_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoricalImportOutcome:
    status: str
    workflow_id: str
    provider: str
    logical_key: str
    source_sha256: str
    segment_id: str | None
    details: Mapping[str, Any] = field(default_factory=dict)
