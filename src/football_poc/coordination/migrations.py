from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

MIGRATION_FILE = re.compile(r"^(?P<version>[0-9]{4})_(?P<name>[a-z0-9_]+)\.sql$")
MIGRATION_LOCK_ID = 7_031_924_611


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str
    sql: str


@dataclass(frozen=True)
class MigrationResult:
    applied_versions: tuple[int, ...]
    newly_applied_versions: tuple[int, ...]


@dataclass(frozen=True)
class IndexRequirement:
    table: str
    columns: tuple[str, ...]
    predicate: str | None = None
    unique: bool = False


REQUIRED_INDEXES = {
    "segments_workflow_segment_idx": IndexRequirement(
        "segments", ("workflow_id", "segment_id")
    ),
    "editing_leases_active_scope_idx": IndexRequirement(
        "editing_leases", ("workflow_id", "segment_id", "expires_at")
    ),
    "editing_leases_expiry_cleanup_idx": IndexRequirement(
        "editing_leases", ("expires_at", "workflow_id", "segment_id")
    ),
    "jobs_claimable_idx": IndexRequirement(
        "jobs",
        ("priority DESC", "available_at", "created_at", "job_id"),
        "status = 'queued'",
    ),
    "event_revisions_chronology_idx": IndexRequirement(
        "event_revisions",
        (
            "workflow_id",
            "segment_id",
            "stream",
            "event_key",
            "created_at",
            "event_revision_id",
        ),
    ),
    "state_snapshots_current_version_idx": IndexRequirement(
        "state_snapshots", ("workflow_id", "segment_id", "version DESC")
    ),
    "review_decisions_event_time_idx": IndexRequirement(
        "review_decisions",
        (
            "workflow_id",
            "segment_id",
            "proposal_key",
            "created_at DESC",
            "decision_id",
        ),
    ),
    "artifacts_provider_logical_hash_idx": IndexRequirement(
        "artifacts", ("provider_id", "logical_key", "content_hash")
    ),
    "artifacts_content_hash_idx": IndexRequirement(
        "artifacts", ("content_hash", "provider_id", "logical_key")
    ),
    "regression_runs_status_hash_idx": IndexRequirement(
        "regression_runs",
        ("workflow_id", "status", "engine_source_hash", "started_at DESC"),
    ),
    "regression_results_hash_idx": IndexRequirement(
        "regression_results",
        ("workflow_id", "output_hash", "created_at DESC"),
        "output_hash IS NOT NULL",
    ),
    "publications_workflow_segment_time_idx": IndexRequirement(
        "publication_history",
        ("workflow_id", "segment_id", "created_at DESC", "publication_id"),
    ),
    "audit_actor_machine_time_idx": IndexRequirement(
        "audit_ledger",
        ("actor_id", "machine_id", "created_at DESC", "sequence"),
    ),
    "audit_workflow_segment_time_idx": IndexRequirement(
        "audit_ledger",
        ("workflow_id", "segment_id", "created_at DESC", "sequence"),
        "workflow_id IS NOT NULL",
    ),
}

REQUIRED_IMPORT_INDEXES = {
    "historical_import_segment_idx": IndexRequirement(
        "historical_review_imports",
        ("workflow_id", "segment_id", "imported_at DESC"),
    ),
}

REQUIRED_MANUAL_REFERENCE_INDEXES = {
    "manual_reference_sets_latest_idx": IndexRequirement(
        "manual_reference_set_revisions",
        ("workflow_id", "segment_id", "revision DESC"),
    ),
    "manual_reference_members_order_idx": IndexRequirement(
        "manual_reference_memberships",
        ("workflow_id", "segment_id", "set_revision", "ordinal"),
    ),
}


def default_migration_directory() -> Path:
    return Path(__file__).resolve().parents[3] / "migrations" / "coordination"


def discover_migrations(directory: Path | None = None) -> tuple[Migration, ...]:
    root = directory or default_migration_directory()
    if not root.is_dir():
        raise MigrationError(f"Migration directory does not exist: {root}")
    migrations: list[Migration] = []
    seen_versions: set[int] = set()
    for path in sorted(root.glob("*.sql")):
        match = MIGRATION_FILE.fullmatch(path.name)
        if match is None:
            raise MigrationError(f"Invalid migration filename: {path.name}")
        version = int(match.group("version"))
        if version in seen_versions:
            raise MigrationError(f"Duplicate migration version: {version:04d}")
        seen_versions.add(version)
        content = path.read_bytes()
        canonical_content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        try:
            sql = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise MigrationError(f"Migration is not UTF-8: {path}") from error
        migrations.append(
            Migration(
                version=version,
                name=match.group("name"),
                path=path,
                checksum=hashlib.sha256(canonical_content).hexdigest(),
                sql=sql,
            )
        )
    if not migrations:
        raise MigrationError(f"No migrations found in: {root}")
    versions = [migration.version for migration in migrations]
    if versions != sorted(versions):
        raise MigrationError("Migration versions are not ordered")
    return tuple(migrations)


def validate_migration_ledger(
    migrations: Iterable[Migration],
    ledger_rows: Iterable[tuple[int, str, str]],
) -> None:
    local_migrations = tuple(migrations)
    stored_rows = tuple(ledger_rows)
    local = {
        migration.version: migration for migration in local_migrations
    }
    for version, name, checksum in stored_rows:
        migration = local.get(version)
        if migration is None:
            raise MigrationError(
                f"Database contains unknown/newer migration {version:04d}_{name}"
            )
        if migration.name != name:
            raise MigrationError(
                f"Migration {version:04d} name differs from the ledger"
            )
        if migration.checksum != checksum:
            raise MigrationError(
                f"Migration {version:04d}_{name} checksum mismatch"
            )
    stored_versions = tuple(row[0] for row in stored_rows)
    expected_prefix = tuple(
        migration.version for migration in local_migrations[: len(stored_rows)]
    )
    if stored_versions != expected_prefix:
        raise MigrationError(
            "Migration ledger is not a forward-only prefix of local migrations"
        )


def apply_migrations(
    connection: Any, directory: Path | None = None
) -> MigrationResult:
    migrations = discover_migrations(directory)
    newly_applied: list[int] = []
    previous_autocommit = connection.autocommit
    connection.autocommit = True
    try:
        connection.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_ID,))
        _create_ledger(connection)
        rows = connection.execute(
            "SELECT version, name, checksum "
            "FROM coordination_schema_migrations ORDER BY version"
        ).fetchall()
        validate_migration_ledger(migrations, rows)
        applied = {row[0] for row in rows}
        for migration in migrations:
            if migration.version in applied:
                continue
            with connection.transaction():
                connection.execute(migration.sql)
                connection.execute(
                    "INSERT INTO coordination_schema_migrations "
                    "(version, name, checksum) VALUES (%s, %s, %s)",
                    (migration.version, migration.name, migration.checksum),
                )
            newly_applied.append(migration.version)
        verify_schema(connection)
        return MigrationResult(
            applied_versions=tuple(
                migration.version for migration in migrations
            ),
            newly_applied_versions=tuple(newly_applied),
        )
    finally:
        try:
            connection.execute(
                "SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_ID,)
            )
        finally:
            connection.autocommit = previous_autocommit


def _create_ledger(connection: Any) -> None:
    with connection.transaction():
        connection.execute(
            "CREATE TABLE IF NOT EXISTS coordination_schema_migrations ("
            "version integer PRIMARY KEY, "
            "name text NOT NULL, "
            "checksum char(64) NOT NULL, "
            "applied_at timestamptz NOT NULL DEFAULT clock_timestamp()"
            ")"
        )


def verify_schema(connection: Any) -> None:
    required_constraints = (
        ("segments", "segments_pkey"),
        ("artifacts", "artifacts_provider_id_logical_key_content_hash_key"),
        ("editing_leases", "editing_leases_pkey"),
        ("editing_leases", "editing_lease_segment_fk"),
        ("editing_leases", "editing_lease_machine_fk"),
        ("editing_leases", "editing_lease_stage_nonempty"),
        ("state_snapshots", "state_snapshots_pkey"),
        ("state_snapshots", "state_snapshot_segment_fk"),
        ("event_revisions", "event_revision_segment_fk"),
        ("jobs", "jobs_status_check"),
        ("jobs", "job_segment_fk"),
        ("job_attempts", "job_attempt_job_fk"),
        ("worker_leases", "worker_lease_attempt_fk"),
        ("job_stages", "job_stage_attempt_fk"),
        ("job_results", "job_result_attempt_fk"),
        ("publication_history", "publication_receipt_scope_fk"),
        (
            "historical_review_imports",
            "historical_review_imports_pkey",
        ),
        (
            "manual_reference_set_revisions",
            "manual_reference_set_approval_check",
        ),
        (
            "manual_reference_memberships",
            "manual_reference_membership_event_fk",
        ),
        (
            "manual_event_mappings",
            "manual_event_mapping_member_fk",
        ),
    )
    index_rows = connection.execute(
        "SELECT ix.relname, tbl.relname, i.indisvalid, i.indisready, "
        "i.indisunique, am.amname, "
        "ARRAY(SELECT pg_get_indexdef(i.indexrelid, position, true) "
        "FROM generate_series(1, i.indnkeyatts) position "
        "ORDER BY position), "
        "ARRAY(SELECT i.indoption[position - 1]::integer "
        "FROM generate_series(1, i.indnkeyatts) position "
        "ORDER BY position), "
        "pg_get_expr(i.indpred, i.indrelid) "
        "FROM pg_index i "
        "JOIN pg_class ix ON ix.oid = i.indexrelid "
        "JOIN pg_class tbl ON tbl.oid = i.indrelid "
        "JOIN pg_am am ON am.oid = ix.relam "
        "JOIN pg_namespace ns ON ns.oid = ix.relnamespace "
        "WHERE ns.nspname = current_schema() AND ix.relname = ANY(%s)",
        (
            list(
                REQUIRED_INDEXES
                | REQUIRED_IMPORT_INDEXES
                | REQUIRED_MANUAL_REFERENCE_INDEXES
            ),
        ),
    ).fetchall()
    validate_required_index_metadata(
        [row for row in index_rows if row[0] in REQUIRED_INDEXES]
    )
    validate_import_index_metadata(
        [row for row in index_rows if row[0] in REQUIRED_IMPORT_INDEXES]
    )
    _validate_index_requirements(
        [
            row
            for row in index_rows
            if row[0] in REQUIRED_MANUAL_REFERENCE_INDEXES
        ],
        REQUIRED_MANUAL_REFERENCE_INDEXES,
    )
    missing_constraints = [
        f"{table}.{name}"
        for table, name in required_constraints
        if connection.execute(
            "SELECT 1 FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "JOIN pg_namespace ns ON ns.oid = t.relnamespace "
            "WHERE ns.nspname = current_schema() "
            "AND t.relname = %s AND c.conname = %s",
            (table, name),
        ).fetchone()
        is None
    ]
    if missing_constraints:
        details = ", ".join(missing_constraints)
        raise MigrationError(f"Required schema objects are missing: {details}")


def validate_required_index_metadata(
    rows: Iterable[
        tuple[
            str,
            str,
            bool,
            bool,
            bool,
            str,
            list[str] | tuple[str, ...],
            list[int] | tuple[int, ...],
            str | None,
        ]
    ],
) -> None:
    actual = {row[0]: row[1:] for row in rows}
    problems: list[str] = []
    for name, requirement in REQUIRED_INDEXES.items():
        metadata = actual.get(name)
        if metadata is None:
            problems.append(f"{name} missing")
            continue
        (
            table,
            valid,
            ready,
            unique,
            access_method,
            columns,
            sort_options,
            predicate,
        ) = metadata
        normalized_columns = tuple(_normalize_sql(item) for item in columns)
        expected_columns, expected_descending = _expected_index_columns(
            requirement.columns
        )
        if table != requirement.table:
            problems.append(f"{name} table")
        if not valid or not ready:
            problems.append(f"{name} invalid")
        if unique != requirement.unique:
            problems.append(f"{name} uniqueness")
        if access_method != "btree":
            problems.append(f"{name} access method")
        if normalized_columns != expected_columns:
            problems.append(f"{name} columns")
        actual_descending = tuple(
            bool(option & 1) for option in sort_options
        )
        if actual_descending != expected_descending:
            problems.append(f"{name} sort direction")
        if _normalize_predicate(predicate) != _normalize_predicate(
            requirement.predicate
        ):
            problems.append(f"{name} predicate")
    if problems:
        raise MigrationError(
            "Required index definitions are missing or modified: "
            + ", ".join(problems)
        )


def validate_import_index_metadata(rows: Iterable[tuple[Any, ...]]) -> None:
    _validate_index_requirements(rows, REQUIRED_IMPORT_INDEXES)


def _validate_index_requirements(
    rows: Iterable[tuple[Any, ...]],
    requirements: Mapping[str, IndexRequirement],
) -> None:
    actual = {row[0]: row[1:] for row in rows}
    problems: list[str] = []
    for name, requirement in requirements.items():
        metadata = actual.get(name)
        if metadata is None:
            problems.append(f"{name} missing")
            continue
        (
            table,
            valid,
            ready,
            unique,
            method,
            columns,
            sort_options,
            predicate,
        ) = metadata
        if table != requirement.table:
            problems.append(f"{name} table")
        if not valid or not ready:
            problems.append(f"{name} invalid")
        if unique != requirement.unique:
            problems.append(f"{name} uniqueness")
        if method != "btree":
            problems.append(f"{name} access method")
        expected_columns, expected_descending = _expected_index_columns(
            requirement.columns
        )
        if tuple(map(_normalize_sql, columns)) != expected_columns:
            problems.append(f"{name} columns")
        if tuple(bool(option & 1) for option in sort_options) != (
            expected_descending
        ):
            problems.append(f"{name} sort direction")
        if _normalize_predicate(predicate) != _normalize_predicate(
            requirement.predicate
        ):
            problems.append(f"{name} predicate")
    if problems:
        raise MigrationError(
            "Required import index definitions are missing or modified: "
            + ", ".join(problems)
        )


def _normalize_sql(value: str) -> str:
    return " ".join(value.casefold().split())


def _expected_index_columns(
    columns: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[bool, ...]]:
    normalized: list[str] = []
    descending: list[bool] = []
    for column in columns:
        value = _normalize_sql(column)
        is_descending = value.endswith(" desc")
        normalized.append(value[:-5].strip() if is_descending else value)
        descending.append(is_descending)
    return tuple(normalized), tuple(descending)


def _normalize_predicate(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _normalize_sql(value).replace("::text", "")
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1].strip()
    return normalized
