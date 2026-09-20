from __future__ import annotations

import threading
import uuid
import copy
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

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
    HistoricalImportOutcome,
    HistoricalImportSource,
    ManualEventMapping,
    ManualEventRevision,
    ManualReferenceMember,
    ManualReferenceSetRevision,
    Segment,
    StateSnapshot,
)
from football_poc.coordination.repository import (
    AuthorityRetiredError,
    LEASE_EXPIRY_SECONDS,
    LeaseConflictError,
    LeaseTokenError,
    ManualReferenceConflictError,
    StateVersionConflictError,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryCoordinationRepository:
    """Thread-safe deterministic repository for tests and local unit work."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = _utc_now,
        environment: EnvironmentIdentity | None = None,
    ) -> None:
        self._clock = clock
        self._environment = environment or EnvironmentIdentity(
            "test", "test", 1
        )
        self._lock = threading.RLock()
        self._identities: dict[tuple[str, str], Identity] = {}
        self._segments: dict[tuple[str, str], Segment] = {}
        self._leases: dict[tuple[str, str], EditingLease] = {}
        self._lease_keys: dict[str, tuple[str, str]] = {}
        self._states: dict[tuple[str, str], list[StateSnapshot]] = {}
        self._artifacts: dict[tuple[str, str, str], Artifact] = {}
        self._audits: list[AuditEntry] = []
        self._history: dict[
            tuple[str, ...],
            list[tuple[int, Mapping[str, Any], str, datetime]],
        ] = {}
        self._manual_reference_sets: dict[
            tuple[str, str], list[ManualReferenceSetRevision]
        ] = {}
        self._jobs: dict[str, dict[str, Any]] = {}
        self._job_leases: dict[str, dict[str, Any]] = {}
        self._job_counter = 0
        self._historical_imports: dict[
            tuple[str, str, str, str], HistoricalImportOutcome
        ] = {}

    @property
    def mode(self) -> DatabaseMode:
        return DatabaseMode.AVAILABLE

    def health(self) -> DatabaseHealth:
        return DatabaseHealth(
            DatabaseMode.AVAILABLE,
            "in-memory coordination repository",
            self._environment,
        )

    def environment_identity(self) -> EnvironmentIdentity:
        return self._environment

    def assert_authority(
        self, authority_id: str, minimum_epoch: int = 1
    ) -> EnvironmentIdentity:
        identity = self._environment
        if (
            identity.retired
            or identity.authority_id != authority_id
            or identity.authority_epoch < minimum_epoch
        ):
            raise AuthorityRetiredError(
                "Coordination authority is retired or older than the client requires"
            )
        return identity

    def register_identity(self, identity: Identity) -> None:
        with self._lock:
            self._identities[
                (identity.developer_id, identity.machine_id)
            ] = identity

    def upsert_segment(self, segment: Segment) -> Segment:
        now = self._clock()
        key = (segment.workflow_id, segment.segment_id)
        with self._lock:
            existing = self._segments.get(key)
            stored = Segment(
                workflow_id=segment.workflow_id,
                segment_id=segment.segment_id,
                logical_key=segment.logical_key,
                metadata=dict(segment.metadata),
                created_at=existing.created_at if existing else now,
                updated_at=now,
            )
            self._segments[key] = stored
            return stored

    def get_segment(
        self, workflow_id: str, segment_id: str
    ) -> Segment | None:
        with self._lock:
            return self._segments.get((workflow_id, segment_id))

    def list_segments(self, workflow_id: str) -> tuple[Segment, ...]:
        with self._lock:
            return tuple(
                segment
                for key, segment in sorted(self._segments.items())
                if key[0] == workflow_id
            )

    def acquire_lease(
        self,
        workflow_id: str,
        segment_id: str,
        owner_id: str,
        machine_id: str,
        stage: str,
    ) -> EditingLease:
        if not stage.strip():
            raise ValueError("stage must not be empty")
        now = self._clock()
        key = (workflow_id, segment_id)
        with self._lock:
            current = self._leases.get(key)
            if current and current.expires_at > now:
                if (
                    current.owner_id == owner_id
                    and current.machine_id == machine_id
                ):
                    renewed = EditingLease(
                        workflow_id,
                        segment_id,
                        owner_id,
                        machine_id,
                        stage,
                        current.token,
                        current.acquired_at,
                        now,
                        now + timedelta(seconds=LEASE_EXPIRY_SECONDS),
                    )
                    self._leases[key] = renewed
                    return renewed
                raise LeaseConflictError(
                    f"{workflow_id}/{segment_id} is leased by {current.owner_id}"
                )
            if current:
                self._lease_keys.pop(current.token, None)
            token = str(uuid.uuid4())
            lease = EditingLease(
                workflow_id,
                segment_id,
                owner_id,
                machine_id,
                stage,
                token,
                now,
                now,
                now + timedelta(seconds=LEASE_EXPIRY_SECONDS),
            )
            self._leases[key] = lease
            self._lease_keys[token] = key
            return lease

    def get_lease(
        self, workflow_id: str, segment_id: str
    ) -> EditingLease | None:
        now = self._clock()
        key = (workflow_id, segment_id)
        with self._lock:
            lease = self._leases.get(key)
            if lease is None:
                return None
            if lease.expires_at <= now:
                self._leases.pop(key, None)
                self._lease_keys.pop(lease.token, None)
                return None
            return lease

    def list_active_leases(
        self, workflow_id: str
    ) -> tuple[EditingLease, ...]:
        with self._lock:
            keys = sorted(
                key for key in self._leases if key[0] == workflow_id
            )
            return tuple(
                lease
                for key in keys
                if (lease := self.get_lease(*key)) is not None
            )

    def heartbeat_lease(self, token: str) -> EditingLease:
        now = self._clock()
        with self._lock:
            key = self._lease_keys.get(token)
            current = self._leases.get(key) if key else None
            if current is None or current.token != token:
                raise LeaseTokenError("Unknown editing lease token")
            if current.expires_at <= now:
                self._leases.pop(key, None)
                self._lease_keys.pop(token, None)
                raise LeaseTokenError("Editing lease has expired")
            renewed = EditingLease(
                current.workflow_id,
                current.segment_id,
                current.owner_id,
                current.machine_id,
                current.stage,
                token,
                current.acquired_at,
                now,
                now + timedelta(seconds=LEASE_EXPIRY_SECONDS),
            )
            self._leases[key] = renewed
            return renewed

    def release_lease(self, token: str) -> bool:
        with self._lock:
            key = self._lease_keys.pop(token, None)
            if key is None:
                return False
            current = self._leases.get(key)
            if current is None or current.token != token:
                return False
            del self._leases[key]
            return True

    def mutate_state(
        self,
        workflow_id: str,
        segment_id: str,
        expected_version: int,
        state: Mapping[str, Any],
        author_id: str,
        lease_token: str,
    ) -> StateSnapshot:
        key = (workflow_id, segment_id)
        with self._lock:
            lease = self.get_lease(workflow_id, segment_id)
            if (
                lease is None
                or lease.token != lease_token
                or lease.owner_id != author_id
            ):
                raise LeaseTokenError(
                    "State mutation requires the active editing lease "
                    "owned by the author"
                )
            snapshots = self._states.setdefault(key, [])
            current_version = snapshots[-1].version if snapshots else 0
            if expected_version != current_version:
                raise StateVersionConflictError(
                    f"Expected state version {expected_version}, "
                    f"found {current_version}"
                )
            snapshot = StateSnapshot(
                workflow_id,
                segment_id,
                current_version + 1,
                dict(state),
                author_id,
                self._clock(),
            )
            snapshots.append(snapshot)
            return snapshot

    def get_state(
        self, workflow_id: str, segment_id: str
    ) -> StateSnapshot | None:
        with self._lock:
            snapshots = self._states.get((workflow_id, segment_id), ())
            return snapshots[-1] if snapshots else None

    def import_historical_state(
        self,
        source: HistoricalImportSource,
        *,
        apply: bool,
    ) -> HistoricalImportOutcome:
        from football_poc.coordination.history_import import (
            canonical_json_hash,
            derive_history_records,
        )

        ledger_key = (
            source.workflow_id,
            source.provider,
            source.logical_key,
            source.source_sha256,
        )
        segment_key = (source.workflow_id, source.segment_id)
        history_records = derive_history_records(source.state)
        with self._lock:
            prior = self._historical_imports.get(ledger_key)
            if prior and prior.status == "inserted":
                return HistoricalImportOutcome(
                    "unchanged",
                    source.workflow_id,
                    source.provider,
                    source.logical_key,
                    source.source_sha256,
                    source.segment_id,
                    {
                        **prior.details,
                        "reason": "source digest already imported",
                    },
                )
            existing_segment = self._segments.get(segment_key)
            existing_state = self.get_state(*segment_key)
            expected_hash = canonical_json_hash(source.state)
            source_details = {
                "state_sha256": expected_hash,
                "canonicalized_fields": list(source.canonicalized_fields),
                **(
                    {"source_state": copy.deepcopy(source.original_state)}
                    if source.canonicalized_fields
                    and source.original_state is not None
                    else {}
                ),
            }
            conflict = (
                existing_segment is not None
                and existing_segment.logical_key != source.logical_key
            ) or (
                existing_state is not None
                and canonical_json_hash(existing_state.state) != expected_hash
            )
            if conflict:
                outcome = HistoricalImportOutcome(
                    "conflicting",
                    source.workflow_id,
                    source.provider,
                    source.logical_key,
                    source.source_sha256,
                    source.segment_id,
                    {
                        **source_details,
                        "reason": "authoritative database state differs",
                    },
                )
                if apply:
                    self._historical_imports[ledger_key] = outcome
                return outcome

            if existing_state is not None:
                outcome = HistoricalImportOutcome(
                    "unchanged",
                    source.workflow_id,
                    source.provider,
                    source.logical_key,
                    source.source_sha256,
                    source.segment_id,
                    source_details,
                )
                if apply:
                    self._historical_imports[ledger_key] = outcome
                return outcome
            outcome = HistoricalImportOutcome(
                "inserted",
                source.workflow_id,
                source.provider,
                source.logical_key,
                source.source_sha256,
                source.segment_id,
                {
                    **source_details,
                    "history_records": len(history_records),
                    "dry_run": not apply,
                },
            )
            if not apply:
                return outcome
            backup = (
                copy.deepcopy(self._segments),
                copy.deepcopy(self._states),
                copy.deepcopy(self._history),
                copy.deepcopy(self._historical_imports),
            )
            try:
                self.upsert_segment(
                    Segment(
                        source.workflow_id,
                        source.segment_id,
                        source.logical_key,
                        {
                            "historical_source_sha256": source.source_sha256,
                            "historical_provider": source.provider,
                        },
                    )
                )
                self._states[segment_key] = [
                    StateSnapshot(
                        source.workflow_id,
                        source.segment_id,
                        1,
                        copy.deepcopy(dict(source.state)),
                        "historical-import",
                        self._clock(),
                    )
                ]
                for record in history_records:
                    key = (
                        record["stream"],
                        source.workflow_id,
                        source.segment_id,
                    )
                    entries = self._history.setdefault(key, [])
                    entries.append(
                        (
                            len(entries) + 1,
                            copy.deepcopy(record["payload"]),
                            "historical-import",
                            self._clock(),
                        )
                    )
                self._historical_imports[ledger_key] = outcome
            except Exception:
                (
                    self._segments,
                    self._states,
                    self._history,
                    self._historical_imports,
                ) = backup
                raise
            return outcome

    def import_historical_states(
        self,
        sources: Sequence[HistoricalImportSource],
        *,
        apply: bool,
    ) -> tuple[HistoricalImportOutcome, ...]:
        with self._lock:
            backup = (
                copy.deepcopy(self._segments),
                copy.deepcopy(self._states),
                copy.deepcopy(self._history),
                copy.deepcopy(self._historical_imports),
            )
            try:
                return tuple(
                    self.import_historical_state(source, apply=apply)
                    for source in sources
                )
            except Exception:
                (
                    self._segments,
                    self._states,
                    self._history,
                    self._historical_imports,
                ) = backup
                raise

    def record_historical_import_outcome(
        self,
        outcome: HistoricalImportOutcome,
        *,
        source_size: int = 0,
        state_sha256: str | None = None,
    ) -> None:
        del source_size, state_sha256
        with self._lock:
            self._historical_imports[
                (
                    outcome.workflow_id,
                    outcome.provider,
                    outcome.logical_key,
                    outcome.source_sha256,
                )
            ] = outcome

    def get_historical_import_outcome(
        self,
        workflow_id: str,
        provider: str,
        logical_key: str,
        source_sha256: str,
    ) -> HistoricalImportOutcome | None:
        with self._lock:
            return self._historical_imports.get(
                (workflow_id, provider, logical_key, source_sha256)
            )

    def register_artifact(
        self,
        provider: str,
        logical_key: str,
        content_hash: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> Artifact:
        key = (provider, logical_key, content_hash)
        with self._lock:
            current = self._artifacts.get(key)
            if current:
                return current
            artifact = Artifact(
                artifact_id=str(uuid.uuid4()),
                provider=provider,
                logical_key=logical_key,
                content_hash=content_hash,
                metadata=dict(metadata or {}),
                created_at=self._clock(),
            )
            self._artifacts[key] = artifact
            return artifact

    def append_audit(
        self,
        action: str,
        actor_id: str,
        *,
        workflow_id: str | None = None,
        segment_id: str | None = None,
        machine_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> AuditEntry:
        with self._lock:
            entry = AuditEntry(
                len(self._audits) + 1,
                action,
                actor_id,
                workflow_id,
                segment_id,
                machine_id,
                dict(payload or {}),
                self._clock(),
            )
            self._audits.append(entry)
            return entry

    def append_history(
        self,
        stream: str,
        workflow_id: str,
        segment_id: str,
        payload: Mapping[str, Any],
        actor_id: str,
    ) -> int:
        if stream not in {"C", "E", "M", "activity", "decision", "verdict"}:
            raise ValueError(f"Unsupported history stream: {stream}")
        key = (stream, workflow_id, segment_id)
        with self._lock:
            entries = self._history.setdefault(key, [])
            if stream in {"C", "E", "M"}:
                event_key = str(payload.get("event_key", "event"))
                revision = (
                    sum(
                        str(entry_payload.get("event_key", "event"))
                        == event_key
                        for _revision, entry_payload, _actor, _created in entries
                    )
                    + 1
                )
            else:
                revision = len(entries) + 1
            entries.append((revision, dict(payload), actor_id, self._clock()))
            return revision

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
    ) -> ManualEventRevision:
        self._validate_manual_position(timestamp_ms, source_frame)
        if not event_key:
            raise ValueError("event_key must not be empty")
        with self._lock:
            self._require_editing_lease(
                workflow_id, segment_id, actor_id, lease_token
            )
            event_payload = {
                **dict(payload),
                "event_key": event_key,
                "timestamp_ms": timestamp_ms,
                "source_frame": source_frame,
            }
            revision = self.append_history(
                "M", workflow_id, segment_id, event_payload, actor_id
            )
            created_at = self._history[
                ("M", workflow_id, segment_id)
            ][-1][3]
            result = ManualEventRevision(
                workflow_id,
                segment_id,
                event_key,
                revision,
                timestamp_ms,
                source_frame,
                event_payload,
                actor_id,
                created_at,
            )
            self.append_audit(
                "manual_event.revised",
                actor_id,
                workflow_id=workflow_id,
                segment_id=segment_id,
                payload={"event_key": event_key, "revision": revision},
            )
            return result

    def get_manual_event_revision(
        self,
        workflow_id: str,
        segment_id: str,
        event_key: str,
        revision: int | None = None,
    ) -> ManualEventRevision | None:
        with self._lock:
            entries = self._history.get(
                ("M", workflow_id, segment_id), ()
            )
            candidates = [
                item
                for item in entries
                if str(item[1].get("event_key")) == event_key
                and (revision is None or item[0] == revision)
            ]
            if not candidates:
                return None
            stored_revision, payload, actor_id, created_at = candidates[-1]
            return ManualEventRevision(
                workflow_id,
                segment_id,
                event_key,
                stored_revision,
                int(payload["timestamp_ms"]),
                int(payload["source_frame"]),
                dict(payload),
                actor_id,
                created_at,
            )

    def create_manual_reference_draft(
        self,
        workflow_id: str,
        segment_id: str,
        actor_id: str,
        lease_token: str,
    ) -> ManualReferenceSetRevision:
        with self._lock:
            self._require_editing_lease(
                workflow_id, segment_id, actor_id, lease_token
            )
            key = (workflow_id, segment_id)
            revisions = self._manual_reference_sets.setdefault(key, [])
            previous = revisions[-1] if revisions else None
            draft = ManualReferenceSetRevision(
                workflow_id=workflow_id,
                segment_id=segment_id,
                revision=len(revisions) + 1,
                status="draft",
                based_on_revision=previous.revision if previous else None,
                members=tuple(previous.members) if previous else (),
                mappings=tuple(previous.mappings) if previous else (),
                created_by=actor_id,
                created_at=self._clock(),
            )
            revisions.append(draft)
            self.append_audit(
                "manual_reference.draft_created",
                actor_id,
                workflow_id=workflow_id,
                segment_id=segment_id,
                payload={
                    "revision": draft.revision,
                    "based_on_revision": draft.based_on_revision,
                },
            )
            return draft

    def replace_manual_reference_membership(
        self,
        workflow_id: str,
        segment_id: str,
        revision: int,
        members: Sequence[ManualReferenceMember],
        actor_id: str,
        lease_token: str,
    ) -> ManualReferenceSetRevision:
        normalized = tuple(members)
        if tuple(member.ordinal for member in normalized) != tuple(
            range(len(normalized))
        ):
            raise ValueError("member ordinals must be contiguous from zero")
        if len({member.event_key for member in normalized}) != len(normalized):
            raise ManualReferenceConflictError(
                "manual events must be unique within a set revision"
            )
        with self._lock:
            current = self._editable_manual_reference(
                workflow_id,
                segment_id,
                revision,
                actor_id,
                lease_token,
            )
            for member in normalized:
                event_history = self._history.get(
                    ("M", workflow_id, segment_id), ()
                )
                if not any(
                    stored_revision == member.event_revision
                    and str(stored_payload.get("event_key")) == member.event_key
                    for (
                        stored_revision,
                        stored_payload,
                        _actor,
                        _created,
                    ) in event_history
                ):
                    raise ManualReferenceConflictError(
                        f"Unknown M event revision "
                        f"{member.event_key}/{member.event_revision}"
                    )
            updated = ManualReferenceSetRevision(
                **{
                    **current.__dict__,
                    "members": normalized,
                    "mappings": (),
                }
            )
            self._replace_manual_reference(updated)
            self.append_audit(
                "manual_reference.membership_replaced",
                actor_id,
                workflow_id=workflow_id,
                segment_id=segment_id,
                payload={"revision": revision, "event_count": len(normalized)},
            )
            return updated

    def replace_manual_event_mappings(
        self,
        workflow_id: str,
        segment_id: str,
        revision: int,
        mappings: Sequence[ManualEventMapping],
        actor_id: str,
        lease_token: str,
    ) -> ManualReferenceSetRevision:
        normalized = tuple(mappings)
        manual_keys = [item.manual_event_key for item in normalized]
        engine_keys = [item.engine_event_key for item in normalized]
        if (
            len(set(manual_keys)) != len(manual_keys)
            or len(set(engine_keys)) != len(engine_keys)
        ):
            raise ManualReferenceConflictError(
                "reviewer mappings must be one-to-one within a set revision"
            )
        with self._lock:
            current = self._editable_manual_reference(
                workflow_id,
                segment_id,
                revision,
                actor_id,
                lease_token,
            )
            member_keys = {member.event_key for member in current.members}
            unknown = set(manual_keys) - member_keys
            if unknown:
                raise ManualReferenceConflictError(
                    f"Mappings reference non-members: {sorted(unknown)}"
                )
            updated = ManualReferenceSetRevision(
                **{**current.__dict__, "mappings": normalized}
            )
            self._replace_manual_reference(updated)
            self.append_audit(
                "manual_reference.mappings_replaced",
                actor_id,
                workflow_id=workflow_id,
                segment_id=segment_id,
                payload={"revision": revision, "mapping_count": len(normalized)},
            )
            return updated

    def approve_manual_reference_set(
        self,
        workflow_id: str,
        segment_id: str,
        revision: int,
        actor_id: str,
        lease_token: str,
    ) -> ManualReferenceSetRevision:
        with self._lock:
            current = self._editable_manual_reference(
                workflow_id,
                segment_id,
                revision,
                actor_id,
                lease_token,
            )
            approved = ManualReferenceSetRevision(
                **{
                    **current.__dict__,
                    "status": "approved",
                    "approved_by": actor_id,
                    "approved_at": self._clock(),
                }
            )
            self._replace_manual_reference(approved)
            self.append_audit(
                "manual_reference.approved",
                actor_id,
                workflow_id=workflow_id,
                segment_id=segment_id,
                payload={
                    "revision": revision,
                    "event_count": len(approved.members),
                    "mapping_count": len(approved.mappings),
                },
            )
            return approved

    def get_manual_reference_set(
        self,
        workflow_id: str,
        segment_id: str,
        revision: int | None = None,
    ) -> ManualReferenceSetRevision | None:
        with self._lock:
            revisions = self._manual_reference_sets.get(
                (workflow_id, segment_id), ()
            )
            if revision is None:
                return revisions[-1] if revisions else None
            return next(
                (item for item in revisions if item.revision == revision),
                None,
            )

    def get_approved_manual_reference_set(
        self,
        workflow_id: str,
        segment_id: str,
    ) -> ManualReferenceSetRevision | None:
        with self._lock:
            return next(
                (
                    item
                    for item in reversed(
                        self._manual_reference_sets.get(
                            (workflow_id, segment_id), ()
                        )
                    )
                    if item.status == "approved"
                ),
                None,
            )

    @staticmethod
    def _validate_manual_position(
        timestamp_ms: int, source_frame: int
    ) -> None:
        if (
            isinstance(timestamp_ms, bool)
            or not isinstance(timestamp_ms, int)
            or not 0 <= timestamp_ms <= 60_000
        ):
            raise ValueError("timestamp_ms must be an integer from 0 to 60000")
        if (
            isinstance(source_frame, bool)
            or not isinstance(source_frame, int)
            or source_frame < 0
        ):
            raise ValueError("source_frame must be a non-negative integer")

    def _require_editing_lease(
        self,
        workflow_id: str,
        segment_id: str,
        actor_id: str,
        lease_token: str,
    ) -> None:
        lease = self.get_lease(workflow_id, segment_id)
        if (
            lease is None
            or lease.token != lease_token
            or lease.owner_id != actor_id
        ):
            raise LeaseTokenError(
                "Manual reference mutation requires the active editing lease "
                "owned by the actor"
            )

    def _editable_manual_reference(
        self,
        workflow_id: str,
        segment_id: str,
        revision: int,
        actor_id: str,
        lease_token: str,
    ) -> ManualReferenceSetRevision:
        self._require_editing_lease(
            workflow_id, segment_id, actor_id, lease_token
        )
        current = self.get_manual_reference_set(
            workflow_id, segment_id, revision
        )
        if current is None:
            raise ManualReferenceConflictError(
                f"Manual reference set revision {revision} does not exist"
            )
        if current.status != "draft":
            raise ManualReferenceConflictError(
                "Approved manual reference set revisions are immutable"
            )
        return current

    def _replace_manual_reference(
        self, replacement: ManualReferenceSetRevision
    ) -> None:
        revisions = self._manual_reference_sets[
            (replacement.workflow_id, replacement.segment_id)
        ]
        revisions[replacement.revision - 1] = replacement

    def enqueue_job(
        self,
        workflow_id: str,
        job_type: str,
        payload: Mapping[str, Any],
        *,
        segment_id: str | None = None,
        priority: int = 0,
    ) -> str:
        with self._lock:
            self._job_counter += 1
            job_id = str(uuid.uuid4())
            self._jobs[job_id] = {
                "job_id": job_id,
                "workflow_id": workflow_id,
                "segment_id": segment_id,
                "job_type": job_type,
                "payload": dict(payload),
                "priority": priority,
                "sequence": self._job_counter,
                "status": "queued",
            }
            return job_id

    def claim_job(
        self, worker_id: str, *, lease_seconds: int = LEASE_EXPIRY_SECONDS
    ) -> ClaimedJob | None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        with self._lock:
            queued = [
                job for job in self._jobs.values() if job["status"] == "queued"
            ]
            if not queued:
                return None
            job = min(queued, key=lambda item: (-item["priority"], item["sequence"]))
            job["status"] = "running"
            attempt_id = str(uuid.uuid4())
            token = str(uuid.uuid4())
            claimed = ClaimedJob(
                job["job_id"],
                job["workflow_id"],
                job["segment_id"],
                job["job_type"],
                job["payload"],
                attempt_id,
                worker_id,
                token,
                self._clock() + timedelta(seconds=lease_seconds),
            )
            self._job_leases[token] = {
                "claim": claimed,
                "status": "running",
            }
            return claimed

    def heartbeat_job(
        self,
        lease_token: str,
        *,
        lease_seconds: int = LEASE_EXPIRY_SECONDS,
    ) -> ClaimedJob:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        with self._lock:
            lease = self._active_job_lease(lease_token)
            claim = lease["claim"]
            renewed = ClaimedJob(
                claim.job_id,
                claim.workflow_id,
                claim.segment_id,
                claim.job_type,
                claim.payload,
                claim.attempt_id,
                claim.worker_id,
                claim.lease_token,
                self._clock() + timedelta(seconds=lease_seconds),
            )
            lease["claim"] = renewed
            return renewed

    def complete_job(
        self,
        lease_token: str,
        result: Mapping[str, Any],
        *,
        stages: tuple[Mapping[str, Any], ...] = (),
    ) -> JobTerminalResult:
        return self._finish_job(
            lease_token, "succeeded", result, stages=stages
        )

    def fail_job(
        self,
        lease_token: str,
        error: Mapping[str, Any],
        *,
        stages: tuple[Mapping[str, Any], ...] = (),
    ) -> JobTerminalResult:
        return self._finish_job(
            lease_token, "failed", error, stages=stages
        )

    def _active_job_lease(self, token: str) -> dict[str, Any]:
        lease = self._job_leases.get(token)
        if (
            lease is None
            or lease["status"] != "running"
            or lease["claim"].lease_expires_at <= self._clock()
        ):
            raise LeaseTokenError("Unknown, expired, or completed worker lease")
        return lease

    def _finish_job(
        self,
        token: str,
        status: str,
        result: Mapping[str, Any],
        *,
        stages: tuple[Mapping[str, Any], ...],
    ) -> JobTerminalResult:
        with self._lock:
            lease = self._active_job_lease(token)
            claim = lease["claim"]
            finished = self._clock()
            terminal = JobTerminalResult(
                claim.job_id,
                claim.attempt_id,
                status,
                dict(result),
                finished,
            )
            lease.update(
                status=status,
                terminal=terminal,
                stages=tuple(dict(stage) for stage in stages),
            )
            self._jobs[claim.job_id]["status"] = status
            return terminal

    def close(self) -> None:
        return None
