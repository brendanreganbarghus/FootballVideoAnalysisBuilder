from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from football_poc.coordination.models import (
    Artifact,
    AuditEntry,
    ClaimedJob,
    DatabaseHealth,
    DatabaseMode,
    EditingLease,
    EnvironmentIdentity,
    Identity,
    JobTerminalResult,
    ManualEventMapping,
    ManualEventRevision,
    ManualReferenceMember,
    ManualReferenceSetRevision,
    HistoricalImportOutcome,
    HistoricalImportSource,
    Segment,
    StateSnapshot,
)

LEASE_HEARTBEAT_SECONDS = 30
LEASE_EXPIRY_SECONDS = 5 * 60


class CoordinationError(RuntimeError):
    pass


class DatabaseUnavailableError(CoordinationError):
    pass


class AuthorityRetiredError(CoordinationError):
    pass


class LeaseConflictError(CoordinationError):
    pass


class LeaseTokenError(CoordinationError):
    pass


class StateVersionConflictError(CoordinationError):
    pass


class ManualReferenceConflictError(CoordinationError):
    pass


class CoordinationRepository(Protocol):
    @property
    def mode(self) -> DatabaseMode: ...

    def health(self) -> DatabaseHealth: ...

    def environment_identity(self) -> EnvironmentIdentity: ...

    def assert_authority(
        self, authority_id: str, minimum_epoch: int = 1
    ) -> EnvironmentIdentity: ...

    def register_identity(self, identity: Identity) -> None: ...

    def upsert_segment(self, segment: Segment) -> Segment: ...

    def get_segment(
        self, workflow_id: str, segment_id: str
    ) -> Segment | None: ...

    def list_segments(self, workflow_id: str) -> tuple[Segment, ...]: ...

    def acquire_lease(
        self,
        workflow_id: str,
        segment_id: str,
        owner_id: str,
        machine_id: str,
        stage: str,
    ) -> EditingLease: ...

    def get_lease(
        self, workflow_id: str, segment_id: str
    ) -> EditingLease | None: ...

    def list_active_leases(
        self, workflow_id: str
    ) -> tuple[EditingLease, ...]: ...

    def heartbeat_lease(self, token: str) -> EditingLease: ...

    def release_lease(self, token: str) -> bool: ...

    def mutate_state(
        self,
        workflow_id: str,
        segment_id: str,
        expected_version: int,
        state: Mapping[str, Any],
        author_id: str,
        lease_token: str,
    ) -> StateSnapshot: ...

    def get_state(
        self, workflow_id: str, segment_id: str
    ) -> StateSnapshot | None: ...

    def append_manual_event(
        self,
        workflow_id: str,
        segment_id: str,
        event_key: str,
        timestamp_ms: int,
        source_frame: int,
        payload: Mapping[str, Any],
        actor_id: str,
        lease_token: str,
    ) -> ManualEventRevision: ...

    def create_manual_reference_draft(
        self,
        workflow_id: str,
        segment_id: str,
        actor_id: str,
        lease_token: str,
    ) -> ManualReferenceSetRevision: ...

    def get_manual_event_revision(
        self,
        workflow_id: str,
        segment_id: str,
        event_key: str,
        revision: int | None = None,
    ) -> ManualEventRevision | None: ...

    def replace_manual_reference_membership(
        self,
        workflow_id: str,
        segment_id: str,
        revision: int,
        members: Sequence[ManualReferenceMember],
        actor_id: str,
        lease_token: str,
    ) -> ManualReferenceSetRevision: ...

    def replace_manual_event_mappings(
        self,
        workflow_id: str,
        segment_id: str,
        revision: int,
        mappings: Sequence[ManualEventMapping],
        actor_id: str,
        lease_token: str,
    ) -> ManualReferenceSetRevision: ...

    def approve_manual_reference_set(
        self,
        workflow_id: str,
        segment_id: str,
        revision: int,
        actor_id: str,
        lease_token: str,
    ) -> ManualReferenceSetRevision: ...

    def get_manual_reference_set(
        self,
        workflow_id: str,
        segment_id: str,
        revision: int | None = None,
    ) -> ManualReferenceSetRevision | None: ...

    def get_approved_manual_reference_set(
        self,
        workflow_id: str,
        segment_id: str,
    ) -> ManualReferenceSetRevision | None: ...

    def import_historical_state(
        self,
        source: HistoricalImportSource,
        *,
        apply: bool,
    ) -> HistoricalImportOutcome: ...

    def import_historical_states(
        self,
        sources: Sequence[HistoricalImportSource],
        *,
        apply: bool,
    ) -> tuple[HistoricalImportOutcome, ...]: ...

    def record_historical_import_outcome(
        self,
        outcome: HistoricalImportOutcome,
        *,
        source_size: int = 0,
        state_sha256: str | None = None,
    ) -> None: ...

    def get_historical_import_outcome(
        self,
        workflow_id: str,
        provider: str,
        logical_key: str,
        source_sha256: str,
    ) -> HistoricalImportOutcome | None: ...

    def register_artifact(
        self,
        provider: str,
        logical_key: str,
        content_hash: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> Artifact: ...

    def append_audit(
        self,
        action: str,
        actor_id: str,
        *,
        workflow_id: str | None = None,
        segment_id: str | None = None,
        machine_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> AuditEntry: ...

    def append_history(
        self,
        stream: str,
        workflow_id: str,
        segment_id: str,
        payload: Mapping[str, Any],
        actor_id: str,
    ) -> int: ...

    def enqueue_job(
        self,
        workflow_id: str,
        job_type: str,
        payload: Mapping[str, Any],
        *,
        segment_id: str | None = None,
        priority: int = 0,
    ) -> str: ...

    def claim_job(
        self, worker_id: str, *, lease_seconds: int = LEASE_EXPIRY_SECONDS
    ) -> ClaimedJob | None: ...

    def heartbeat_job(
        self,
        lease_token: str,
        *,
        lease_seconds: int = LEASE_EXPIRY_SECONDS,
    ) -> ClaimedJob: ...

    def complete_job(
        self,
        lease_token: str,
        result: Mapping[str, Any],
        *,
        stages: tuple[Mapping[str, Any], ...] = (),
    ) -> JobTerminalResult: ...

    def fail_job(
        self,
        lease_token: str,
        error: Mapping[str, Any],
        *,
        stages: tuple[Mapping[str, Any], ...] = (),
    ) -> JobTerminalResult: ...

    def close(self) -> None: ...
