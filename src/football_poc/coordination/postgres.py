from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, NoReturn, Sequence

from football_poc.coordination.config import CoordinationConfig
from football_poc.coordination.migrations import MigrationResult, apply_migrations
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
    Segment,
    StateSnapshot,
)
from football_poc.coordination.repository import (
    AuthorityRetiredError,
    CoordinationRepository,
    DatabaseUnavailableError,
    LEASE_EXPIRY_SECONDS,
    LeaseConflictError,
    LeaseTokenError,
    ManualReferenceConflictError,
    StateVersionConflictError,
)


class _InactiveRepository:
    def __init__(self, mode: DatabaseMode, detail: str) -> None:
        self._health = DatabaseHealth(mode, detail)

    @property
    def mode(self) -> DatabaseMode:
        return self._health.mode

    def health(self) -> DatabaseHealth:
        return self._health

    def close(self) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._unavailable

    def _unavailable(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        raise DatabaseUnavailableError(self._health.detail)


@dataclass(frozen=True)
class ReconciliationResult:
    status: str
    detail: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status in {"completed", "not_requested"}


@dataclass(frozen=True)
class BootstrapResult:
    repository: CoordinationRepository
    health: DatabaseHealth
    migrations: MigrationResult | None
    reconciliation: ReconciliationResult

    @property
    def writable(self) -> bool:
        return (
            self.health.mode is DatabaseMode.AVAILABLE
            and self.reconciliation.succeeded
        )


ReconciliationHook = Callable[
    [CoordinationRepository],
    ReconciliationResult | Mapping[str, Any] | None,
]

WORKFLOW_SEEDS = (
    (
        "football_review",
        "Football review",
        "",
    ),
)


class PostgresCoordinationRepository:
    def __init__(
        self,
        connection: Any,
        environment: EnvironmentIdentity,
        reconnect: Callable[[], Any] | None = None,
    ) -> None:
        self._active_connection = connection
        self._environment = environment
        self._reconnect = reconnect

    @property
    def _connection(self) -> Any:
        # The server keeps one long-lived connection, and the database host
        # closes idle ones; open a new one instead of failing every request.
        if self._reconnect is not None and getattr(
            self._active_connection, "closed", False
        ):
            self._active_connection = self._reconnect()
        return self._active_connection

    @property
    def mode(self) -> DatabaseMode:
        return self.health().mode

    def health(self) -> DatabaseHealth:
        try:
            self._connection.execute("SELECT 1").fetchone()
        except Exception as error:
            return DatabaseHealth(
                DatabaseMode.UNAVAILABLE,
                f"PostgreSQL health check failed: {type(error).__name__}",
                self._environment,
            )
        return DatabaseHealth(
            DatabaseMode.AVAILABLE,
            "PostgreSQL coordination is available",
            self._environment,
        )

    def environment_identity(self) -> EnvironmentIdentity:
        row = self._connection.execute(
            "SELECT deployment_id, authority_id, authority_epoch, retired "
            "FROM coordination_environments WHERE deployment_id = %s",
            (self._environment.deployment_id,),
        ).fetchone()
        if row is None:
            raise AuthorityRetiredError("Deployment identity no longer exists")
        return EnvironmentIdentity(row[0], row[1], row[2], row[3])

    def assert_authority(
        self, authority_id: str, minimum_epoch: int = 1
    ) -> EnvironmentIdentity:
        identity = self.environment_identity()
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
        with self._connection.transaction():
            self._connection.execute(
                "INSERT INTO developers "
                "(developer_id, domain_name, username) VALUES (%s, %s, %s) "
                "ON CONFLICT (developer_id) DO UPDATE SET "
                "domain_name = EXCLUDED.domain_name, "
                "username = EXCLUDED.username, "
                "last_seen_at = clock_timestamp()",
                (identity.developer_id, identity.domain, identity.username),
            )
            self._connection.execute(
                "INSERT INTO machines "
                "(machine_id, developer_id, hostname, ip_address) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (machine_id) DO UPDATE SET "
                "developer_id = EXCLUDED.developer_id, "
                "hostname = EXCLUDED.hostname, "
                "ip_address = EXCLUDED.ip_address, "
                "last_seen_at = clock_timestamp()",
                (
                    identity.machine_id,
                    identity.developer_id,
                    identity.hostname,
                    identity.ip_address,
                ),
            )

    def upsert_segment(self, segment: Segment) -> Segment:
        row = self._connection.execute(
            "INSERT INTO segments "
            "(workflow_id, segment_id, logical_key, metadata) "
            "VALUES (%s, %s, %s, %s::jsonb) "
            "ON CONFLICT (workflow_id, segment_id) DO UPDATE SET "
            "logical_key = EXCLUDED.logical_key, "
            "metadata = EXCLUDED.metadata, "
            "updated_at = clock_timestamp() "
            "RETURNING workflow_id, segment_id, logical_key, metadata, "
            "created_at, updated_at",
            (
                segment.workflow_id,
                segment.segment_id,
                segment.logical_key,
                _json(segment.metadata),
            ),
        ).fetchone()
        self._connection.commit()
        return _segment(row)

    def get_segment(
        self, workflow_id: str, segment_id: str
    ) -> Segment | None:
        row = self._connection.execute(
            "SELECT workflow_id, segment_id, logical_key, metadata, "
            "created_at, updated_at FROM segments "
            "WHERE workflow_id = %s AND segment_id = %s",
            (workflow_id, segment_id),
        ).fetchone()
        return _segment(row) if row else None

    def list_segments(self, workflow_id: str) -> tuple[Segment, ...]:
        rows = self._connection.execute(
            "SELECT workflow_id, segment_id, logical_key, metadata, "
            "created_at, updated_at FROM segments WHERE workflow_id = %s "
            "ORDER BY segment_id",
            (workflow_id,),
        ).fetchall()
        return tuple(_segment(row) for row in rows)

    @staticmethod
    def _validate_ball_source(ball_source: str) -> str:
        if ball_source not in {"bac", "detected"}:
            raise ValueError("ball_source must be 'bac' or 'detected'")
        return ball_source

    def get_segment_ball_source(
        self, workflow_id: str, segment_id: str
    ) -> str | None:
        row = self._connection.execute(
            "SELECT ball_source FROM segments "
            "WHERE workflow_id = %s AND segment_id = %s",
            (workflow_id, segment_id),
        ).fetchone()
        return row[0] if row else None

    def set_segment_ball_source(
        self,
        workflow_id: str,
        segment_id: str,
        ball_source: str,
        *,
        logical_key: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        source = self._validate_ball_source(ball_source)
        with self._connection.transaction():
            self._connection.execute(
                "INSERT INTO segments "
                "(workflow_id, segment_id, logical_key, metadata, ball_source) "
                "VALUES (%s, %s, %s, %s::jsonb, %s) "
                "ON CONFLICT (workflow_id, segment_id) DO UPDATE SET "
                "ball_source = EXCLUDED.ball_source, "
                "updated_at = clock_timestamp()",
                (
                    workflow_id,
                    segment_id,
                    logical_key or segment_id,
                    _json(metadata or {}),
                    source,
                ),
            )

    def record_segment_outputs(
        self,
        workflow_id: str,
        segment_id: str,
        *,
        ball_source: str,
        engine_sha256: str,
        output_sha256: str,
        files: Mapping[str, Any],
        actor_id: str,
    ) -> int:
        source = self._validate_ball_source(ball_source)
        with self._connection.transaction():
            self._connection.execute(
                "INSERT INTO segments "
                "(workflow_id, segment_id, logical_key, metadata, ball_source) "
                "VALUES (%s, %s, %s, %s::jsonb, %s) "
                "ON CONFLICT (workflow_id, segment_id) DO UPDATE SET "
                "ball_source = EXCLUDED.ball_source, "
                "updated_at = clock_timestamp()",
                (workflow_id, segment_id, segment_id, "{}", source),
            )
            self._connection.execute(
                "SELECT 1 FROM segments WHERE workflow_id = %s "
                "AND segment_id = %s FOR UPDATE",
                (workflow_id, segment_id),
            )
            row = self._connection.execute(
                "SELECT COALESCE(MAX(revision), 0) + 1 "
                "FROM segment_outputs "
                "WHERE workflow_id = %s AND segment_id = %s",
                (workflow_id, segment_id),
            ).fetchone()
            revision = int(row[0])
            self._connection.execute(
                "INSERT INTO segment_outputs "
                "(workflow_id, segment_id, revision, ball_source, "
                "engine_sha256, output_sha256, files, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)",
                (
                    workflow_id,
                    segment_id,
                    revision,
                    source,
                    engine_sha256,
                    output_sha256,
                    _json(files),
                    actor_id,
                ),
            )
        return revision

    def get_segment_outputs(
        self, workflow_id: str, segment_id: str
    ) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT revision, ball_source, engine_sha256, output_sha256, "
            "files, created_by, created_at "
            "FROM segment_outputs "
            "WHERE workflow_id = %s AND segment_id = %s "
            "ORDER BY revision DESC LIMIT 1",
            (workflow_id, segment_id),
        ).fetchone()
        if row is None:
            return None
        return {
            "revision": int(row[0]),
            "ballSource": row[1],
            "engineSha256": row[2],
            "outputSha256": row[3],
            "files": dict(row[4]),
            "createdBy": row[5],
            "createdAt": row[6].isoformat() if hasattr(row[6], "isoformat") else row[6],
        }

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
        current = self.get_lease(workflow_id, segment_id)
        if (
            current
            and current.owner_id == owner_id
            and current.machine_id == machine_id
        ):
            return self.heartbeat_lease(current.token)
        token = str(uuid.uuid4())
        row = self._connection.execute(
            "INSERT INTO editing_leases "
            "(workflow_id, segment_id, owner_id, machine_id, stage, "
            "lease_token, acquired_at, heartbeat_at, expires_at) VALUES "
            "(%s, %s, %s, %s, %s, %s, clock_timestamp(), clock_timestamp(), "
            "clock_timestamp() + make_interval(secs => %s)) "
            "ON CONFLICT (workflow_id, segment_id) DO UPDATE SET "
            "owner_id = EXCLUDED.owner_id, machine_id = EXCLUDED.machine_id, "
            "stage = EXCLUDED.stage, lease_token = EXCLUDED.lease_token, "
            "acquired_at = EXCLUDED.acquired_at, "
            "heartbeat_at = EXCLUDED.heartbeat_at, "
            "expires_at = EXCLUDED.expires_at "
            "WHERE editing_leases.expires_at <= clock_timestamp() "
            "RETURNING workflow_id, segment_id, owner_id, machine_id::text, "
            "stage, lease_token::text, acquired_at, heartbeat_at, expires_at",
            (
                workflow_id,
                segment_id,
                owner_id,
                machine_id,
                stage,
                token,
                LEASE_EXPIRY_SECONDS,
            ),
        ).fetchone()
        self._connection.commit()
        if row is None:
            raise LeaseConflictError(
                f"{workflow_id}/{segment_id} already has an active lease"
            )
        return EditingLease(*row)

    def get_lease(
        self, workflow_id: str, segment_id: str
    ) -> EditingLease | None:
        row = self._connection.execute(
            "DELETE FROM editing_leases WHERE workflow_id = %s "
            "AND segment_id = %s AND expires_at <= clock_timestamp() "
            "RETURNING lease_token",
            (workflow_id, segment_id),
        ).fetchone()
        if row:
            self._connection.commit()
            return None
        row = self._connection.execute(
            "SELECT workflow_id, segment_id, owner_id, machine_id::text, "
            "stage, lease_token::text, acquired_at, heartbeat_at, expires_at "
            "FROM editing_leases WHERE workflow_id = %s AND segment_id = %s "
            "AND expires_at > clock_timestamp()",
            (workflow_id, segment_id),
        ).fetchone()
        return EditingLease(*row) if row else None

    def list_active_leases(
        self, workflow_id: str
    ) -> tuple[EditingLease, ...]:
        with self._connection.transaction():
            self._connection.execute(
                "DELETE FROM editing_leases WHERE workflow_id = %s "
                "AND expires_at <= clock_timestamp()",
                (workflow_id,),
            )
            rows = self._connection.execute(
                "SELECT workflow_id, segment_id, owner_id, machine_id::text, "
                "stage, lease_token::text, acquired_at, heartbeat_at, "
                "expires_at FROM editing_leases WHERE workflow_id = %s "
                "AND expires_at > clock_timestamp() ORDER BY segment_id",
                (workflow_id,),
            ).fetchall()
        return tuple(EditingLease(*row) for row in rows)

    def heartbeat_lease(self, token: str) -> EditingLease:
        row = self._connection.execute(
            "UPDATE editing_leases SET "
            "heartbeat_at = clock_timestamp(), "
            "expires_at = clock_timestamp() + make_interval(secs => %s) "
            "WHERE lease_token = %s AND expires_at > clock_timestamp() "
            "RETURNING workflow_id, segment_id, owner_id, machine_id::text, "
            "stage, lease_token::text, acquired_at, heartbeat_at, expires_at",
            (LEASE_EXPIRY_SECONDS, token),
        ).fetchone()
        self._connection.commit()
        if row is None:
            raise LeaseTokenError("Unknown or expired editing lease token")
        return EditingLease(*row)

    def release_lease(self, token: str) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM editing_leases WHERE lease_token = %s", (token,)
        )
        self._connection.commit()
        return cursor.rowcount == 1

    def mutate_state(
        self,
        workflow_id: str,
        segment_id: str,
        expected_version: int,
        state: Mapping[str, Any],
        author_id: str,
        lease_token: str,
    ) -> StateSnapshot:
        with self._connection.transaction():
            lease = self._connection.execute(
                "SELECT 1 FROM editing_leases "
                "WHERE workflow_id = %s AND segment_id = %s "
                "AND lease_token = %s AND owner_id = %s "
                "AND expires_at > clock_timestamp() FOR UPDATE",
                (workflow_id, segment_id, lease_token, author_id),
            ).fetchone()
            if lease is None:
                raise LeaseTokenError(
                    "State mutation requires the active editing lease "
                    "owned by the author"
                )
            row = self._connection.execute(
                "SELECT version FROM state_snapshots "
                "WHERE workflow_id = %s AND segment_id = %s "
                "ORDER BY version DESC LIMIT 1",
                (workflow_id, segment_id),
            ).fetchone()
            current = row[0] if row else 0
            if current != expected_version:
                raise StateVersionConflictError(
                    f"Expected state version {expected_version}, found {current}"
                )
            result = self._connection.execute(
                "INSERT INTO state_snapshots "
                "(workflow_id, segment_id, version, state, author_id) "
                "VALUES (%s, %s, %s, %s::jsonb, %s) "
                "RETURNING workflow_id, segment_id, version, state, "
                "author_id, created_at",
                (
                    workflow_id,
                    segment_id,
                    current + 1,
                    _json(state),
                    author_id,
                ),
            ).fetchone()
        return StateSnapshot(*result)

    def get_state(
        self, workflow_id: str, segment_id: str
    ) -> StateSnapshot | None:
        row = self._connection.execute(
            "SELECT workflow_id, segment_id, version, state, author_id, "
            "created_at FROM state_snapshots "
            "WHERE workflow_id = %s AND segment_id = %s "
            "ORDER BY version DESC LIMIT 1",
            (workflow_id, segment_id),
        ).fetchone()
        return StateSnapshot(*row) if row else None

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
        _validate_manual_position(timestamp_ms, source_frame)
        if not event_key:
            raise ValueError("event_key must not be empty")
        event_payload = {
            **dict(payload),
            "event_key": event_key,
            "timestamp_ms": timestamp_ms,
            "source_frame": source_frame,
        }
        with self._connection.transaction():
            self._require_manual_lease(
                workflow_id, segment_id, actor_id, lease_token
            )
            self._connection.execute(
                "SELECT 1 FROM segments WHERE workflow_id = %s "
                "AND segment_id = %s FOR UPDATE",
                (workflow_id, segment_id),
            )
            next_row = self._connection.execute(
                "SELECT COALESCE(MAX(revision), 0) + 1 "
                "FROM event_revisions WHERE workflow_id = %s "
                "AND segment_id = %s AND stream = 'M' AND event_key = %s",
                (workflow_id, segment_id, event_key),
            ).fetchone()
            row = self._connection.execute(
                "INSERT INTO event_revisions "
                "(workflow_id, segment_id, stream, event_key, revision, "
                "payload, actor_id) VALUES (%s, %s, 'M', %s, %s, %s::jsonb, %s) "
                "RETURNING created_at",
                (
                    workflow_id,
                    segment_id,
                    event_key,
                    next_row[0],
                    _json(event_payload),
                    actor_id,
                ),
            ).fetchone()
            self._insert_audit(
                "manual_event.revised",
                actor_id,
                workflow_id,
                segment_id,
                {"event_key": event_key, "revision": next_row[0]},
            )
        return ManualEventRevision(
            workflow_id,
            segment_id,
            event_key,
            next_row[0],
            timestamp_ms,
            source_frame,
            event_payload,
            actor_id,
            row[0],
        )

    def create_manual_reference_draft(
        self,
        workflow_id: str,
        segment_id: str,
        actor_id: str,
        lease_token: str,
    ) -> ManualReferenceSetRevision:
        with self._connection.transaction():
            self._require_manual_lease(
                workflow_id, segment_id, actor_id, lease_token
            )
            self._connection.execute(
                "SELECT 1 FROM segments WHERE workflow_id = %s "
                "AND segment_id = %s FOR UPDATE",
                (workflow_id, segment_id),
            )
            previous = self._connection.execute(
                "SELECT revision FROM manual_reference_set_revisions "
                "WHERE workflow_id = %s AND segment_id = %s "
                "ORDER BY revision DESC LIMIT 1",
                (workflow_id, segment_id),
            ).fetchone()
            based_on = previous[0] if previous else None
            revision = (based_on or 0) + 1
            self._connection.execute(
                "INSERT INTO manual_reference_set_revisions "
                "(workflow_id, segment_id, revision, based_on_revision, created_by) "
                "VALUES (%s, %s, %s, %s, %s)",
                (workflow_id, segment_id, revision, based_on, actor_id),
            )
            if based_on is not None:
                self._connection.execute(
                    "INSERT INTO manual_reference_memberships "
                    "(workflow_id, segment_id, set_revision, ordinal, stream, "
                    "event_key, event_revision) "
                    "SELECT workflow_id, segment_id, %s, ordinal, stream, "
                    "event_key, event_revision FROM manual_reference_memberships "
                    "WHERE workflow_id = %s AND segment_id = %s "
                    "AND set_revision = %s ORDER BY ordinal",
                    (revision, workflow_id, segment_id, based_on),
                )
                self._connection.execute(
                    "INSERT INTO manual_event_mappings "
                    "(workflow_id, segment_id, set_revision, manual_event_key, "
                    "engine_event_key) SELECT workflow_id, segment_id, %s, "
                    "manual_event_key, engine_event_key FROM manual_event_mappings "
                    "WHERE workflow_id = %s AND segment_id = %s "
                    "AND set_revision = %s",
                    (revision, workflow_id, segment_id, based_on),
                )
            self._insert_audit(
                "manual_reference.draft_created",
                actor_id,
                workflow_id,
                segment_id,
                {"revision": revision, "based_on_revision": based_on},
            )
        result = self.get_manual_reference_set(
            workflow_id, segment_id, revision
        )
        assert result is not None
        return result

    def get_manual_event_revision(
        self,
        workflow_id: str,
        segment_id: str,
        event_key: str,
        revision: int | None = None,
    ) -> ManualEventRevision | None:
        revision_clause = "AND revision = %s" if revision is not None else ""
        parameters: tuple[Any, ...] = (
            workflow_id,
            segment_id,
            event_key,
        ) + ((revision,) if revision is not None else ())
        row = self._connection.execute(
            "SELECT revision, payload, actor_id, created_at "
            "FROM event_revisions WHERE workflow_id = %s AND segment_id = %s "
            "AND stream = 'M' AND event_key = %s "
            f"{revision_clause} ORDER BY revision DESC LIMIT 1",
            parameters,
        ).fetchone()
        if row is None:
            return None
        payload = row[1]
        return ManualEventRevision(
            workflow_id,
            segment_id,
            event_key,
            row[0],
            int(payload["timestamp_ms"]),
            int(payload["source_frame"]),
            payload,
            row[2],
            row[3],
        )

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
        if tuple(item.ordinal for item in normalized) != tuple(
            range(len(normalized))
        ):
            raise ValueError("member ordinals must be contiguous from zero")
        if len({item.event_key for item in normalized}) != len(normalized):
            raise ManualReferenceConflictError(
                "manual events must be unique within a set revision"
            )
        with self._connection.transaction():
            self._require_editable_manual_reference(
                workflow_id,
                segment_id,
                revision,
                actor_id,
                lease_token,
            )
            for member in normalized:
                exists = self._connection.execute(
                    "SELECT 1 FROM event_revisions WHERE workflow_id = %s "
                    "AND segment_id = %s AND stream = 'M' AND event_key = %s "
                    "AND revision = %s",
                    (
                        workflow_id,
                        segment_id,
                        member.event_key,
                        member.event_revision,
                    ),
                ).fetchone()
                if exists is None:
                    raise ManualReferenceConflictError(
                        f"Unknown M event revision "
                        f"{member.event_key}/{member.event_revision}"
                    )
            self._connection.execute(
                "DELETE FROM manual_event_mappings WHERE workflow_id = %s "
                "AND segment_id = %s AND set_revision = %s",
                (workflow_id, segment_id, revision),
            )
            self._connection.execute(
                "DELETE FROM manual_reference_memberships WHERE workflow_id = %s "
                "AND segment_id = %s AND set_revision = %s",
                (workflow_id, segment_id, revision),
            )
            for member in normalized:
                self._connection.execute(
                    "INSERT INTO manual_reference_memberships "
                    "(workflow_id, segment_id, set_revision, ordinal, "
                    "event_key, event_revision) VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        workflow_id,
                        segment_id,
                        revision,
                        member.ordinal,
                        member.event_key,
                        member.event_revision,
                    ),
                )
            self._insert_audit(
                "manual_reference.membership_replaced",
                actor_id,
                workflow_id,
                segment_id,
                {"revision": revision, "event_count": len(normalized)},
            )
        result = self.get_manual_reference_set(
            workflow_id, segment_id, revision
        )
        assert result is not None
        return result

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
        with self._connection.transaction():
            self._require_editable_manual_reference(
                workflow_id,
                segment_id,
                revision,
                actor_id,
                lease_token,
            )
            member_rows = self._connection.execute(
                "SELECT event_key FROM manual_reference_memberships "
                "WHERE workflow_id = %s AND segment_id = %s "
                "AND set_revision = %s",
                (workflow_id, segment_id, revision),
            ).fetchall()
            member_keys = {row[0] for row in member_rows}
            unknown = set(manual_keys) - member_keys
            if unknown:
                raise ManualReferenceConflictError(
                    f"Mappings reference non-members: {sorted(unknown)}"
                )
            self._connection.execute(
                "DELETE FROM manual_event_mappings WHERE workflow_id = %s "
                "AND segment_id = %s AND set_revision = %s",
                (workflow_id, segment_id, revision),
            )
            for mapping in normalized:
                self._connection.execute(
                    "INSERT INTO manual_event_mappings "
                    "(workflow_id, segment_id, set_revision, manual_event_key, "
                    "engine_event_key) VALUES (%s, %s, %s, %s, %s)",
                    (
                        workflow_id,
                        segment_id,
                        revision,
                        mapping.manual_event_key,
                        mapping.engine_event_key,
                    ),
                )
            self._insert_audit(
                "manual_reference.mappings_replaced",
                actor_id,
                workflow_id,
                segment_id,
                {"revision": revision, "mapping_count": len(normalized)},
            )
        result = self.get_manual_reference_set(
            workflow_id, segment_id, revision
        )
        assert result is not None
        return result

    def approve_manual_reference_set(
        self,
        workflow_id: str,
        segment_id: str,
        revision: int,
        actor_id: str,
        lease_token: str,
    ) -> ManualReferenceSetRevision:
        with self._connection.transaction():
            self._require_editable_manual_reference(
                workflow_id,
                segment_id,
                revision,
                actor_id,
                lease_token,
            )
            self._connection.execute(
                "UPDATE manual_reference_set_revisions SET status = 'approved', "
                "approved_by = %s, approved_at = clock_timestamp() "
                "WHERE workflow_id = %s AND segment_id = %s AND revision = %s",
                (actor_id, workflow_id, segment_id, revision),
            )
            counts = self._connection.execute(
                "SELECT "
                "(SELECT COUNT(*) FROM manual_reference_memberships "
                " WHERE workflow_id = %s AND segment_id = %s AND set_revision = %s), "
                "(SELECT COUNT(*) FROM manual_event_mappings "
                " WHERE workflow_id = %s AND segment_id = %s AND set_revision = %s)",
                (
                    workflow_id,
                    segment_id,
                    revision,
                    workflow_id,
                    segment_id,
                    revision,
                ),
            ).fetchone()
            self._insert_audit(
                "manual_reference.approved",
                actor_id,
                workflow_id,
                segment_id,
                {
                    "revision": revision,
                    "event_count": counts[0],
                    "mapping_count": counts[1],
                },
            )
        result = self.get_manual_reference_set(
            workflow_id, segment_id, revision
        )
        assert result is not None
        return result

    def get_manual_reference_set(
        self,
        workflow_id: str,
        segment_id: str,
        revision: int | None = None,
    ) -> ManualReferenceSetRevision | None:
        revision_clause = "AND revision = %s" if revision is not None else ""
        order_clause = "" if revision is not None else "ORDER BY revision DESC LIMIT 1"
        parameters: tuple[Any, ...] = (workflow_id, segment_id) + (
            (revision,) if revision is not None else ()
        )
        row = self._connection.execute(
            "SELECT workflow_id, segment_id, revision, status, "
            "based_on_revision, created_by, created_at, approved_by, approved_at "
            "FROM manual_reference_set_revisions "
            "WHERE workflow_id = %s AND segment_id = %s "
            f"{revision_clause} {order_clause}",
            parameters,
        ).fetchone()
        if row is None:
            return None
        members = self._connection.execute(
            "SELECT ordinal, event_key, event_revision "
            "FROM manual_reference_memberships WHERE workflow_id = %s "
            "AND segment_id = %s AND set_revision = %s ORDER BY ordinal",
            (workflow_id, segment_id, row[2]),
        ).fetchall()
        mappings = self._connection.execute(
            "SELECT manual_event_key, engine_event_key "
            "FROM manual_event_mappings WHERE workflow_id = %s "
            "AND segment_id = %s AND set_revision = %s "
            "ORDER BY manual_event_key",
            (workflow_id, segment_id, row[2]),
        ).fetchall()
        return ManualReferenceSetRevision(
            workflow_id=row[0],
            segment_id=row[1],
            revision=row[2],
            status=row[3],
            based_on_revision=row[4],
            members=tuple(ManualReferenceMember(*item) for item in members),
            mappings=tuple(ManualEventMapping(*item) for item in mappings),
            created_by=row[5],
            created_at=row[6],
            approved_by=row[7],
            approved_at=row[8],
        )

    def get_approved_manual_reference_set(
        self,
        workflow_id: str,
        segment_id: str,
    ) -> ManualReferenceSetRevision | None:
        row = self._connection.execute(
            "SELECT revision FROM manual_reference_set_revisions "
            "WHERE workflow_id = %s AND segment_id = %s "
            "AND status = 'approved' ORDER BY revision DESC LIMIT 1",
            (workflow_id, segment_id),
        ).fetchone()
        if row is None:
            return None
        return self.get_manual_reference_set(
            workflow_id, segment_id, row[0]
        )

    def _require_manual_lease(
        self,
        workflow_id: str,
        segment_id: str,
        actor_id: str,
        lease_token: str,
    ) -> None:
        row = self._connection.execute(
            "SELECT 1 FROM editing_leases WHERE workflow_id = %s "
            "AND segment_id = %s AND lease_token = %s AND owner_id = %s "
            "AND expires_at > clock_timestamp() FOR UPDATE",
            (workflow_id, segment_id, lease_token, actor_id),
        ).fetchone()
        if row is None:
            raise LeaseTokenError(
                "Manual reference mutation requires the active editing lease "
                "owned by the actor"
            )

    def _require_editable_manual_reference(
        self,
        workflow_id: str,
        segment_id: str,
        revision: int,
        actor_id: str,
        lease_token: str,
    ) -> None:
        self._require_manual_lease(
            workflow_id, segment_id, actor_id, lease_token
        )
        row = self._connection.execute(
            "SELECT status FROM manual_reference_set_revisions "
            "WHERE workflow_id = %s AND segment_id = %s AND revision = %s "
            "FOR UPDATE",
            (workflow_id, segment_id, revision),
        ).fetchone()
        if row is None:
            raise ManualReferenceConflictError(
                f"Manual reference set revision {revision} does not exist"
            )
        if row[0] != "draft":
            raise ManualReferenceConflictError(
                "Approved manual reference set revisions are immutable"
            )

    def _insert_audit(
        self,
        action: str,
        actor_id: str,
        workflow_id: str,
        segment_id: str,
        payload: Mapping[str, Any],
    ) -> None:
        self._connection.execute(
            "INSERT INTO audit_ledger "
            "(action, actor_id, workflow_id, segment_id, payload) "
            "VALUES (%s, %s, %s, %s, %s::jsonb)",
            (
                action,
                actor_id,
                workflow_id,
                segment_id,
                _json(payload),
            ),
        )

    def register_artifact(
        self,
        provider: str,
        logical_key: str,
        content_hash: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> Artifact:
        artifact_id = str(uuid.uuid4())
        with self._connection.transaction():
            self._connection.execute(
                "INSERT INTO artifact_providers (provider_id) VALUES (%s) "
                "ON CONFLICT (provider_id) DO NOTHING",
                (provider,),
            )
            row = self._connection.execute(
                "INSERT INTO artifacts "
                "(artifact_id, provider_id, logical_key, content_hash, metadata) "
                "VALUES (%s, %s, %s, %s, %s::jsonb) "
                "ON CONFLICT (provider_id, logical_key, content_hash) "
                "DO UPDATE SET provider_id = EXCLUDED.provider_id "
                "RETURNING artifact_id::text, provider_id, logical_key, "
                "content_hash, metadata, created_at",
                (
                    artifact_id,
                    provider,
                    logical_key,
                    content_hash,
                    _json(metadata or {}),
                ),
            ).fetchone()
        return Artifact(*row)

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
        row = self._connection.execute(
            "INSERT INTO audit_ledger "
            "(action, actor_id, machine_id, workflow_id, segment_id, payload) "
            "VALUES (%s, %s, %s, %s, %s, %s::jsonb) "
            "RETURNING sequence, action, actor_id, workflow_id, segment_id, "
            "machine_id::text, payload, created_at",
            (
                action,
                actor_id,
                machine_id,
                workflow_id,
                segment_id,
                _json(payload or {}),
            ),
        ).fetchone()
        self._connection.commit()
        return AuditEntry(*row)

    def append_history(
        self,
        stream: str,
        workflow_id: str,
        segment_id: str,
        payload: Mapping[str, Any],
        actor_id: str,
    ) -> int:
        if stream not in {"C", "E", "M"}:
            return self._append_review_history(
                stream, workflow_id, segment_id, payload, actor_id
            )
        event_key = str(payload.get("event_key", "event"))
        with self._connection.transaction():
            self._connection.execute(
                "SELECT 1 FROM segments WHERE workflow_id = %s "
                "AND segment_id = %s FOR UPDATE",
                (workflow_id, segment_id),
            )
            row = self._connection.execute(
                "SELECT COALESCE(MAX(revision), 0) + 1 "
                "FROM event_revisions WHERE workflow_id = %s "
                "AND segment_id = %s AND stream = %s AND event_key = %s",
                (workflow_id, segment_id, stream, event_key),
            ).fetchone()
            revision = row[0]
            self._connection.execute(
                "INSERT INTO event_revisions "
                "(workflow_id, segment_id, stream, event_key, revision, "
                "payload, actor_id) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)",
                (
                    workflow_id,
                    segment_id,
                    stream,
                    event_key,
                    revision,
                    _json(payload),
                    actor_id,
                ),
            )
        return revision

    def _append_review_history(
        self,
        stream: str,
        workflow_id: str,
        segment_id: str,
        payload: Mapping[str, Any],
        actor_id: str,
    ) -> int:
        table_and_column = {
            "activity": ("review_activity", "activity_id", "activity_type"),
            "decision": ("review_decisions", "decision_id", "decision"),
            "verdict": ("engine_verdicts", "verdict_id", "verdict"),
        }.get(stream)
        if table_and_column is None:
            raise ValueError(f"Unsupported history stream: {stream}")
        table, id_column, type_column = table_and_column
        discriminator = str(payload.get("type", stream))
        extra_column = (
            ", proposal_key"
            if stream == "decision"
            else ", event_key"
            if stream == "verdict"
            else ""
        )
        extra_value = (
            str(payload.get("proposal_key", "proposal"))
            if stream == "decision"
            else str(payload.get("event_key", "event"))
            if stream == "verdict"
            else None
        )
        columns = (
            f"workflow_id, segment_id, {type_column}, payload, actor_id"
            f"{extra_column}"
        )
        placeholders = "%s, %s, %s, %s::jsonb, %s" + (
            ", %s" if extra_column else ""
        )
        parameters: tuple[Any, ...] = (
            workflow_id,
            segment_id,
            discriminator,
            _json(payload),
            actor_id,
        ) + ((extra_value,) if extra_column else ())
        row = self._connection.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
            f"RETURNING {id_column}",
            parameters,
        ).fetchone()
        self._connection.commit()
        return row[0]

    def enqueue_job(
        self,
        workflow_id: str,
        job_type: str,
        payload: Mapping[str, Any],
        *,
        segment_id: str | None = None,
        priority: int = 0,
    ) -> str:
        job_id = str(uuid.uuid4())
        self._connection.execute(
            "INSERT INTO jobs "
            "(job_id, workflow_id, segment_id, job_type, payload, priority) "
            "VALUES (%s, %s, %s, %s, %s::jsonb, %s)",
            (
                job_id,
                workflow_id,
                segment_id,
                job_type,
                _json(payload),
                priority,
            ),
        )
        self._connection.commit()
        return job_id

    def claim_job(
        self, worker_id: str, *, lease_seconds: int = LEASE_EXPIRY_SECONDS
    ) -> ClaimedJob | None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        attempt_id = str(uuid.uuid4())
        token = str(uuid.uuid4())
        with self._connection.transaction():
            row = self._connection.execute(
                "SELECT job_id::text, workflow_id, segment_id, job_type, payload "
                "FROM jobs WHERE status = 'queued' "
                "AND available_at <= clock_timestamp() "
                "ORDER BY priority DESC, available_at, created_at "
                "FOR UPDATE SKIP LOCKED LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            attempt_number = self._connection.execute(
                "SELECT COALESCE(MAX(attempt_number), 0) + 1 "
                "FROM job_attempts WHERE job_id = %s",
                (row[0],),
            ).fetchone()[0]
            self._connection.execute(
                "UPDATE jobs SET status = 'running', "
                "updated_at = clock_timestamp() WHERE job_id = %s",
                (row[0],),
            )
            self._connection.execute(
                "INSERT INTO job_attempts "
                "(attempt_id, workflow_id, job_id, attempt_number, worker_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (attempt_id, row[1], row[0], attempt_number, worker_id),
            )
            lease_row = self._connection.execute(
                "INSERT INTO worker_leases "
                "(attempt_id, workflow_id, worker_id, lease_token, "
                "heartbeat_at, expires_at) "
                "VALUES (%s, %s, %s, %s, clock_timestamp(), "
                "clock_timestamp() + make_interval(secs => %s)) "
                "RETURNING expires_at",
                (attempt_id, row[1], worker_id, token, lease_seconds),
            ).fetchone()
        return ClaimedJob(
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            attempt_id,
            worker_id,
            token,
            lease_row[0],
        )

    def heartbeat_job(
        self,
        lease_token: str,
        *,
        lease_seconds: int = LEASE_EXPIRY_SECONDS,
    ) -> ClaimedJob:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        row = self._connection.execute(
            "UPDATE worker_leases wl SET "
            "heartbeat_at = clock_timestamp(), "
            "expires_at = clock_timestamp() + make_interval(secs => %s) "
            "FROM job_attempts ja, jobs j "
            "WHERE j.job_id = ja.job_id "
            "AND j.workflow_id = ja.workflow_id "
            "AND wl.attempt_id = ja.attempt_id "
            "AND wl.workflow_id = ja.workflow_id AND wl.lease_token = %s "
            "AND wl.expires_at > clock_timestamp() "
            "AND ja.status = 'running' AND j.status = 'running' "
            "RETURNING j.job_id::text, j.workflow_id, j.segment_id, "
            "j.job_type, j.payload, ja.attempt_id::text, wl.worker_id, "
            "wl.lease_token::text, wl.expires_at",
            (lease_seconds, lease_token),
        ).fetchone()
        self._connection.commit()
        if row is None:
            raise LeaseTokenError("Unknown, expired, or completed worker lease")
        return ClaimedJob(*row)

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

    def _finish_job(
        self,
        lease_token: str,
        status: str,
        result: Mapping[str, Any],
        *,
        stages: tuple[Mapping[str, Any], ...],
    ) -> JobTerminalResult:
        with self._connection.transaction():
            row = self._connection.execute(
                "SELECT j.job_id::text, j.workflow_id, ja.attempt_id::text "
                "FROM worker_leases wl "
                "JOIN job_attempts ja ON ja.attempt_id = wl.attempt_id "
                "AND ja.workflow_id = wl.workflow_id "
                "JOIN jobs j ON j.job_id = ja.job_id "
                "AND j.workflow_id = ja.workflow_id "
                "WHERE wl.lease_token = %s "
                "AND wl.expires_at > clock_timestamp() "
                "AND ja.status = 'running' AND j.status = 'running' "
                "FOR UPDATE OF wl, ja, j",
                (lease_token,),
            ).fetchone()
            if row is None:
                raise LeaseTokenError(
                    "Unknown, expired, or completed worker lease"
                )
            job_id, workflow_id, attempt_id = row
            for stage in stages:
                stage_name = str(stage.get("stage_name", "")).strip()
                stage_status = str(stage.get("status", "")).strip()
                if not stage_name or not stage_status:
                    raise ValueError(
                        "Job stages require non-empty stage_name and status"
                    )
                self._connection.execute(
                    "INSERT INTO job_stages "
                    "(workflow_id, attempt_id, stage_name, status, payload) "
                    "VALUES (%s, %s, %s, %s, %s::jsonb)",
                    (
                        workflow_id,
                        attempt_id,
                        stage_name,
                        stage_status,
                        _json(stage.get("payload", {})),
                    ),
                )
            self._connection.execute(
                "INSERT INTO job_results "
                "(workflow_id, attempt_id, result_type, payload) "
                "VALUES (%s, %s, %s, %s::jsonb)",
                (workflow_id, attempt_id, status, _json(result)),
            )
            self._connection.execute(
                "UPDATE job_attempts SET status = %s, "
                "finished_at = clock_timestamp(), "
                "error = CASE WHEN %s = 'failed' THEN %s::jsonb ELSE NULL END "
                "WHERE workflow_id = %s AND attempt_id = %s",
                (
                    status,
                    status,
                    _json(result),
                    workflow_id,
                    attempt_id,
                ),
            )
            finished = self._connection.execute(
                "UPDATE jobs SET status = %s, updated_at = clock_timestamp() "
                "WHERE workflow_id = %s AND job_id = %s "
                "RETURNING updated_at",
                (status, workflow_id, job_id),
            ).fetchone()[0]
            self._connection.execute(
                "DELETE FROM worker_leases "
                "WHERE workflow_id = %s AND attempt_id = %s",
                (workflow_id, attempt_id),
            )
        return JobTerminalResult(
            job_id, attempt_id, status, dict(result), finished
        )

    def close(self) -> None:
        self._connection.close()


def create_coordination_repository(
    config: CoordinationConfig | None = None,
    *,
    migration_directory: Path | None = None,
) -> CoordinationRepository:
    return bootstrap_coordination(
        config, migration_directory=migration_directory
    ).repository


def bootstrap_coordination(
    config: CoordinationConfig | None = None,
    *,
    migration_directory: Path | None = None,
    reconciliation_hook: ReconciliationHook | None = None,
) -> BootstrapResult:
    """Run the complete startup gate without creating a PostgreSQL database."""

    settings = config or CoordinationConfig.from_environment()
    if settings.database_url is None:
        repository = _InactiveRepository(
            DatabaseMode.DISABLED,
            "FOOTBALL_DATABASE_URL is not configured",
        )
        return BootstrapResult(
            repository,
            repository.health(),
            None,
            ReconciliationResult(
                "not_requested", "Coordination is disabled"
            ),
        )
    try:
        import psycopg
    except ImportError:
        repository = _InactiveRepository(
            DatabaseMode.UNAVAILABLE,
            "FOOTBALL_DATABASE_URL is configured but the optional "
            "'coordination' dependency is not installed",
        )
        return BootstrapResult(
            repository,
            repository.health(),
            None,
            ReconciliationResult(
                "not_requested", "PostgreSQL is unavailable"
            ),
        )
    def connect() -> Any:
        return psycopg.connect(
            settings.database_url,
            connect_timeout=settings.connect_timeout_seconds,
            # The server keeps one long-lived connection; TCP keepalives stop
            # an idle Docker/WSL network path from silently dropping it.
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=3,
        )

    def reconnect() -> Any:
        connection = connect()
        connection.autocommit = True
        return connection

    try:
        connection = connect()
        migrations = apply_migrations(connection, migration_directory)
        connection.autocommit = True
        environment = _register_environment(connection, settings)
        _ensure_workflow_seeds(connection)
        repository = PostgresCoordinationRepository(
            connection, environment, reconnect
        )
        reconciliation = _run_reconciliation(
            repository, reconciliation_hook
        )
        if not reconciliation.succeeded:
            raise RuntimeError(
                f"Coordination reconciliation failed: {reconciliation.detail}"
            )
        health = repository.health()
        if health.mode is not DatabaseMode.AVAILABLE:
            raise RuntimeError(health.detail)
        return BootstrapResult(
            repository, health, migrations, reconciliation
        )
    except Exception as error:
        connection_to_close = locals().get("connection")
        if connection_to_close is not None:
            try:
                connection_to_close.close()
            except Exception:
                pass
        repository = _InactiveRepository(
            DatabaseMode.UNAVAILABLE,
            "FOOTBALL_DATABASE_URL is configured but PostgreSQL startup failed: "
            f"{type(error).__name__}: {error}",
        )
        return BootstrapResult(
            repository,
            repository.health(),
            locals().get("migrations"),
            locals().get(
                "reconciliation",
                ReconciliationResult(
                    "not_requested",
                    "Reconciliation did not run",
                ),
            ),
        )


def run_coordination_preflight(
    config: CoordinationConfig | None = None,
    *,
    migration_directory: Path | None = None,
    reconciliation_hook: ReconciliationHook | None = None,
) -> BootstrapResult:
    return bootstrap_coordination(
        config,
        migration_directory=migration_directory,
        reconciliation_hook=reconciliation_hook,
    )


def _register_environment(
    connection: Any, config: CoordinationConfig
) -> EnvironmentIdentity:
    with connection.transaction():
        connection.execute(
            "INSERT INTO coordination_environments "
            "(deployment_id, authority_id, authority_epoch) "
            "VALUES (%s, %s, %s) ON CONFLICT (deployment_id) DO NOTHING",
            (config.deployment_id, config.authority_id, config.authority_epoch),
        )
        row = connection.execute(
            "SELECT deployment_id, authority_id, authority_epoch, retired "
            "FROM coordination_environments WHERE deployment_id = %s",
            (config.deployment_id,),
        ).fetchone()
    identity = EnvironmentIdentity(*row)
    if (
        identity.retired
        or identity.authority_id != config.authority_id
        or identity.authority_epoch != config.authority_epoch
    ):
        raise AuthorityRetiredError(
            "Configured deployment does not match the active authority record"
        )
    return identity


def _ensure_workflow_seeds(connection: Any) -> None:
    with connection.transaction():
        for workflow_id, display_name, namespace in WORKFLOW_SEEDS:
            connection.execute(
                "INSERT INTO workflows "
                "(workflow_id, display_name, artifact_namespace) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (workflow_id) DO UPDATE SET "
                "display_name = EXCLUDED.display_name, "
                "artifact_namespace = EXCLUDED.artifact_namespace",
                (workflow_id, display_name, namespace),
            )
        rows = connection.execute(
            "SELECT workflow_id, display_name, artifact_namespace "
            "FROM workflows WHERE workflow_id = ANY(%s)",
            ([seed[0] for seed in WORKFLOW_SEEDS],),
        ).fetchall()
    actual = set(rows)
    expected = set(WORKFLOW_SEEDS)
    if actual != expected:
        raise RuntimeError(
            "Required workflow identities are missing after seed reconciliation"
        )


def _run_reconciliation(
    repository: CoordinationRepository,
    hook: ReconciliationHook | None,
) -> ReconciliationResult:
    if hook is None:
        return ReconciliationResult(
            "not_requested", "No reconciliation hook was supplied"
        )
    result = hook(repository)
    if isinstance(result, ReconciliationResult):
        return result
    if result is None:
        return ReconciliationResult("completed", "Reconciliation completed")
    return ReconciliationResult(
        "completed", "Reconciliation completed", dict(result)
    )


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _validate_manual_position(timestamp_ms: int, source_frame: int) -> None:
    if (
        isinstance(timestamp_ms, bool)
        or not isinstance(timestamp_ms, int)
        or timestamp_ms < 0
    ):
        raise ValueError("timestamp_ms must be a non-negative integer")
    if (
        isinstance(source_frame, bool)
        or not isinstance(source_frame, int)
        or source_frame < 0
    ):
        raise ValueError("source_frame must be a non-negative integer")


def _segment(row: tuple[Any, ...]) -> Segment:
    return Segment(row[0], row[1], row[2], row[3], row[4], row[5])
