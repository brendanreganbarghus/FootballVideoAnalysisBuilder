from __future__ import annotations

import sys
from types import SimpleNamespace
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from football_poc.coordination import (
    AuthorityRetiredError,
    CoordinationConfig,
    DatabaseHealth,
    DatabaseMode,
    DatabaseUnavailableError,
    EnvironmentIdentity,
    Identity,
    InMemoryCoordinationRepository,
    LeaseConflictError,
    LeaseTokenError,
    Segment,
    StateVersionConflictError,
    ReconciliationResult,
    bootstrap_coordination,
    create_coordination_repository,
    load_or_create_machine_identity,
)
from football_poc.coordination.migrations import (
    MigrationResult,
    MigrationError,
    REQUIRED_INDEXES,
    discover_migrations,
    validate_required_index_metadata,
    validate_migration_ledger,
)
from football_poc.coordination import postgres as postgres_module
from football_poc import coordination_cli


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


MACHINE_A = "79b0ab35-063c-44cb-b625-abdb062e7bb2"
MACHINE_B = "fb698a52-63bb-490e-b99a-2afd2409988e"


def test_migration_discovery_is_versioned_and_checksummed(
    tmp_path: Path,
) -> None:
    first = tmp_path / "0001_initial.sql"
    second = tmp_path / "0002_seed.sql"
    first.write_text("SELECT 1;\n", encoding="utf-8")
    second.write_text("SELECT 2;\n", encoding="utf-8")

    migrations = discover_migrations(tmp_path)

    assert [item.version for item in migrations] == [1, 2]
    assert all(len(item.checksum) == 64 for item in migrations)
    validate_migration_ledger(
        migrations,
        [(1, "initial", migrations[0].checksum)],
    )
    with pytest.raises(MigrationError, match="checksum mismatch"):
        validate_migration_ledger(migrations, [(1, "initial", "0" * 64)])
    with pytest.raises(MigrationError, match="unknown/newer"):
        validate_migration_ledger(migrations, [(3, "future", "0" * 64)])
    with pytest.raises(MigrationError, match="forward-only prefix"):
        validate_migration_ledger(
            migrations,
            [(2, "seed", migrations[1].checksum)],
        )


def test_repository_migrations_cover_claim_lock_and_logical_artifacts() -> None:
    migrations = discover_migrations()
    schema = migrations[0].sql
    seeds = migrations[1].sql

    assert "FOR UPDATE SKIP LOCKED" in (
        Path(__file__).parents[1]
        / "src"
        / "football_poc"
        / "coordination"
        / "postgres.py"
    ).read_text(encoding="utf-8")
    assert "UNIQUE (provider_id, logical_key, content_hash)" in schema
    assert "content_hash text" in schema
    assert "bytea" not in schema.lower()
    editing_lease_schema = schema.split(
        "CREATE TABLE editing_leases (", 1
    )[1].split("\n);", 1)[0]
    assert "machine_id uuid NOT NULL" in editing_lease_schema
    assert "stage text NOT NULL" in editing_lease_schema
    assert "CONSTRAINT editing_lease_machine_fk" in editing_lease_schema
    assert "CONSTRAINT editing_lease_stage_nonempty" in editing_lease_schema
    assert "'innovation_day_bac'" in seeds
    assert "'live_iteration_25'" in seeds
    for table in (
        "segments",
        "segment_artifacts",
        "editing_leases",
        "assignments",
        "review_sessions",
        "state_snapshots",
        "event_revisions",
        "review_activity",
        "review_decisions",
        "engine_verdicts",
        "engine_confirmations",
        "jobs",
        "job_attempts",
        "worker_leases",
        "job_stages",
        "job_results",
        "regression_runs",
        "regression_results",
        "output_fingerprints",
        "receipts",
        "publication_history",
    ):
        declaration = schema.split(f"CREATE TABLE {table} (", 1)[1].split(
            "\n);", 1
        )[0]
        assert "workflow_id text NOT NULL" in declaration, table
    assert (
        "REFERENCES receipts(workflow_id, segment_id, receipt_id)"
        in schema
    )
    assert (
        "REFERENCES review_sessions(workflow_id, segment_id, review_session_id)"
        in schema
    )
    assert (
        "REFERENCES regression_runs(workflow_id, regression_run_id)"
        in schema
    )
    for index_name in REQUIRED_INDEXES:
        assert f"CREATE INDEX {index_name}" in schema


def test_required_index_verification_rejects_missing_or_modified_definitions() -> None:
    rows = [
        (
            name,
            requirement.table,
            True,
            True,
            requirement.unique,
            "btree",
            [
                column.removesuffix(" DESC")
                for column in requirement.columns
            ],
            [
                3 if column.endswith(" DESC") else 0
                for column in requirement.columns
            ],
            requirement.predicate,
        )
        for name, requirement in REQUIRED_INDEXES.items()
    ]
    validate_required_index_metadata(rows)

    modified = list(rows)
    job_position = next(
        index
        for index, row in enumerate(modified)
        if row[0] == "jobs_claimable_idx"
    )
    changed_job = list(modified[job_position])
    changed_job[6] = ["created_at"]
    modified[job_position] = tuple(changed_job)
    with pytest.raises(MigrationError, match="jobs_claimable_idx columns"):
        validate_required_index_metadata(modified)

    changed_sort = list(rows)
    state_position = next(
        index
        for index, row in enumerate(changed_sort)
        if row[0] == "state_snapshots_current_version_idx"
    )
    changed_state = list(changed_sort[state_position])
    changed_state[7] = [0, 0, 0]
    changed_sort[state_position] = tuple(changed_state)
    with pytest.raises(
        MigrationError,
        match="state_snapshots_current_version_idx sort direction",
    ):
        validate_required_index_metadata(changed_sort)

    without_publications = [
        row
        for row in rows
        if row[0] != "publications_workflow_segment_time_idx"
    ]
    with pytest.raises(
        MigrationError,
        match="publications_workflow_segment_time_idx missing",
    ):
        validate_required_index_metadata(without_publications)


def test_partial_index_predicates_are_verified() -> None:
    rows = [
        (
            name,
            requirement.table,
            True,
            True,
            requirement.unique,
            "btree",
            [
                column.removesuffix(" DESC")
                for column in requirement.columns
            ],
            [
                3 if column.endswith(" DESC") else 0
                for column in requirement.columns
            ],
            requirement.predicate,
        )
        for name, requirement in REQUIRED_INDEXES.items()
    ]
    regression_position = next(
        index
        for index, row in enumerate(rows)
        if row[0] == "regression_results_hash_idx"
    )
    modified = list(rows)
    changed = list(modified[regression_position])
    changed[8] = None
    modified[regression_position] = tuple(changed)

    with pytest.raises(MigrationError, match="predicate"):
        validate_required_index_metadata(modified)


def test_editing_lease_is_exclusive_and_can_be_reclaimed_after_expiry() -> None:
    clock = MutableClock()
    repository = InMemoryCoordinationRepository(clock=clock)

    first = repository.acquire_lease(
        "workflow-a", "segment-1", "alice", MACHINE_A, "review"
    )
    assert first.machine_id == MACHINE_A
    assert first.stage == "review"
    reattached = repository.acquire_lease(
        "workflow-a", "segment-1", "alice", MACHINE_A, "adjudication"
    )
    assert reattached.token == first.token
    assert reattached.stage == "adjudication"
    with pytest.raises(LeaseConflictError):
        repository.acquire_lease(
            "workflow-a", "segment-1", "bob", MACHINE_B, "review"
        )

    clock.advance(299)
    renewed = repository.heartbeat_lease(first.token)
    assert renewed.expires_at == clock.now + timedelta(minutes=5)
    clock.advance(301)
    with pytest.raises(LeaseTokenError):
        repository.heartbeat_lease(first.token)

    second = repository.acquire_lease(
        "workflow-a", "segment-1", "bob", MACHINE_B, "adjudication"
    )
    assert second.token != first.token
    assert repository.release_lease(second.token)
    assert not repository.release_lease(second.token)


def test_active_lease_lookup_is_workflow_scoped_and_cleans_expiry() -> None:
    clock = MutableClock()
    repository = InMemoryCoordinationRepository(clock=clock)
    innovation = repository.acquire_lease(
        "innovation_day_bac", "shared", "alice", MACHINE_A, "review"
    )
    live = repository.acquire_lease(
        "live_iteration_25", "shared", "bob", MACHINE_B, "publication"
    )

    assert repository.get_lease(
        "innovation_day_bac", "shared"
    ) == innovation
    assert repository.list_active_leases("innovation_day_bac") == (
        innovation,
    )
    assert repository.list_active_leases("live_iteration_25") == (live,)

    clock.advance(301)
    assert repository.get_lease("innovation_day_bac", "shared") is None
    assert repository.list_active_leases("innovation_day_bac") == ()


def test_state_mutation_requires_exact_active_owner_lease() -> None:
    clock = MutableClock()
    repository = InMemoryCoordinationRepository(clock=clock)
    lease = repository.acquire_lease(
        "workflow-a", "segment-1", "alice", MACHINE_A, "review"
    )

    for token, author, workflow in (
        ("", "alice", "workflow-a"),
        ("wrong", "alice", "workflow-a"),
        (lease.token, "bob", "workflow-a"),
        (lease.token, "alice", "workflow-b"),
    ):
        with pytest.raises(LeaseTokenError):
            repository.mutate_state(
                workflow,
                "segment-1",
                0,
                {},
                author,
                token,
            )

    clock.advance(301)
    with pytest.raises(LeaseTokenError):
        repository.mutate_state(
            "workflow-a",
            "segment-1",
            0,
            {},
            "alice",
            lease.token,
        )


def test_state_mutation_is_optimistic_and_workflow_scoped() -> None:
    repository = InMemoryCoordinationRepository()
    lease_a = repository.acquire_lease(
        "workflow-a", "segment-1", "alice", MACHINE_A, "review"
    )
    lease_b = repository.acquire_lease(
        "workflow-b", "segment-1", "alice", MACHINE_A, "review"
    )
    first = repository.mutate_state(
        "workflow-a",
        "segment-1",
        0,
        {"value": "a"},
        "alice",
        lease_a.token,
    )
    other = repository.mutate_state(
        "workflow-b",
        "segment-1",
        0,
        {"value": "b"},
        "alice",
        lease_b.token,
    )

    assert first.version == other.version == 1
    assert repository.get_state("workflow-a", "segment-1").state == {
        "value": "a"
    }
    with pytest.raises(StateVersionConflictError, match="found 1"):
        repository.mutate_state(
            "workflow-a",
            "segment-1",
            0,
            {"value": "stale"},
            "alice",
            lease_a.token,
        )


def test_same_segment_key_has_independent_workflow_coordination() -> None:
    repository = InMemoryCoordinationRepository()
    segment_key = "shared-segment-key"
    for workflow_id in ("innovation_day_bac", "live_iteration_25"):
        repository.upsert_segment(
            Segment(workflow_id, segment_key, "recording/segment", {})
        )

    innovation_lease = repository.acquire_lease(
        "innovation_day_bac",
        segment_key,
        "innovation-reviewer",
        MACHINE_A,
        "review",
    )
    live_lease = repository.acquire_lease(
        "live_iteration_25",
        segment_key,
        "live-reviewer",
        MACHINE_B,
        "review",
    )
    innovation_revision = repository.append_history(
        "C",
        "innovation_day_bac",
        segment_key,
        {"event_key": "C1"},
        "innovation-reviewer",
    )
    live_revision = repository.append_history(
        "C",
        "live_iteration_25",
        segment_key,
        {"event_key": "C1"},
        "live-reviewer",
    )
    repository.mutate_state(
        "innovation_day_bac",
        segment_key,
        0,
        {"review": "innovation"},
        "innovation-reviewer",
        innovation_lease.token,
    )
    repository.mutate_state(
        "live_iteration_25",
        segment_key,
        0,
        {"review": "live"},
        "live-reviewer",
        live_lease.token,
    )
    repository.enqueue_job(
        "innovation_day_bac",
        "review",
        {},
        segment_id=segment_key,
        priority=2,
    )
    repository.enqueue_job(
        "live_iteration_25",
        "review",
        {},
        segment_id=segment_key,
        priority=1,
    )
    innovation_job = repository.claim_job("worker-1")
    live_job = repository.claim_job("worker-2")

    assert innovation_lease.token != live_lease.token
    assert innovation_revision == live_revision == 1
    assert repository.get_state(
        "innovation_day_bac", segment_key
    ).state != repository.get_state("live_iteration_25", segment_key).state
    assert innovation_job is not None
    assert innovation_job.workflow_id == "innovation_day_bac"
    assert innovation_job.segment_id == segment_key
    assert live_job is not None
    assert live_job.workflow_id == "live_iteration_25"
    assert live_job.segment_id == segment_key
    assert repository.get_segment(
        "innovation_day_bac", segment_key
    ).workflow_id == "innovation_day_bac"
    assert repository.get_segment(
        "live_iteration_25", segment_key
    ).workflow_id == "live_iteration_25"


def test_segment_and_artifact_identity_are_deterministic() -> None:
    repository = InMemoryCoordinationRepository()
    segment = repository.upsert_segment(
        Segment("workflow-a", "segment-1", "clip/1", {"start": 12})
    )
    repository.upsert_segment(
        Segment("workflow-b", "segment-1", "clip/1", {"start": 99})
    )
    first = repository.register_artifact(
        "onedrive", "segments/one", "sha256:abc", {"path": "logical-only"}
    )
    same = repository.register_artifact(
        "onedrive", "segments/one", "sha256:abc", {"ignored": True}
    )
    changed = repository.register_artifact(
        "onedrive", "segments/one", "sha256:def"
    )

    assert repository.get_segment("workflow-a", "segment-1") == segment
    assert repository.get_segment("workflow-b", "segment-1").metadata["start"] == 99
    assert repository.list_segments("workflow-a") == (segment,)
    assert first.artifact_id == same.artifact_id
    assert changed.artifact_id != first.artifact_id


def test_job_claiming_is_exclusive_and_priority_ordered() -> None:
    repository = InMemoryCoordinationRepository()
    low = repository.enqueue_job("workflow-a", "build", {}, priority=1)
    high = repository.enqueue_job("workflow-b", "regression", {}, priority=5)

    first = repository.claim_job("worker-1")
    second = repository.claim_job("worker-2")

    assert first is not None and first.job_id == high
    assert second is not None and second.job_id == low
    assert first.workflow_id == "workflow-b"
    assert repository.claim_job("worker-3") is None


def test_worker_job_lease_is_independent_and_has_durable_terminal_result() -> None:
    clock = MutableClock()
    repository = InMemoryCoordinationRepository(clock=clock)
    repository.upsert_segment(
        Segment("workflow-a", "segment-1", "clip/1")
    )
    editing = repository.acquire_lease(
        "workflow-a", "segment-1", "alice", MACHINE_A, "review"
    )
    repository.enqueue_job(
        "workflow-a", "regression", {}, segment_id="segment-1"
    )
    claimed = repository.claim_job("worker-1", lease_seconds=60)
    assert claimed is not None

    assert repository.release_lease(editing.token)
    renewed = repository.heartbeat_job(
        claimed.lease_token, lease_seconds=120
    )
    assert renewed.lease_expires_at == clock.now + timedelta(seconds=120)
    terminal = repository.complete_job(
        claimed.lease_token,
        {"output_hash": "sha256:abc"},
        stages=(
            {
                "stage_name": "regression",
                "status": "succeeded",
                "payload": {"tests": 10},
            },
        ),
    )

    assert terminal.status == "succeeded"
    assert terminal.result["output_hash"] == "sha256:abc"
    with pytest.raises(LeaseTokenError):
        repository.heartbeat_job(claimed.lease_token)


def test_expired_worker_job_cannot_complete() -> None:
    clock = MutableClock()
    repository = InMemoryCoordinationRepository(clock=clock)
    repository.enqueue_job("workflow-a", "build", {})
    claimed = repository.claim_job("worker-1", lease_seconds=10)
    assert claimed is not None
    clock.advance(11)

    with pytest.raises(LeaseTokenError):
        repository.fail_job(claimed.lease_token, {"message": "late"})


def test_identity_is_persistent_without_using_real_user_directory(
    tmp_path: Path,
) -> None:
    path = tmp_path / "app-state" / "machine.json"
    environment = {"USERDOMAIN": "EXAMPLE", "USERNAME": "Developer"}

    first = load_or_create_machine_identity(path, environment=environment)
    second = load_or_create_machine_identity(path, environment=environment)

    assert first.machine_id == second.machine_id
    assert first.developer_id == "example\\developer"
    assert path.is_file()


def test_json_coordination_config_loads_secret_from_named_environment(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "coordination.json"
    config_path.write_text(
        json.dumps(
            {
                "database_url_env": "TEAM_DATABASE_URL",
                "settings": {
                    "deployment_id": "team-cloud",
                    "authority_id": "cloud-primary",
                    "authority_epoch": 2,
                    "connect_timeout_seconds": 7,
                    "machine_id_path": str(tmp_path / "machine.json"),
                    "lease_heartbeat_seconds": 30,
                    "lease_expiry_seconds": 300,
                },
            }
        ),
        encoding="utf-8",
    )
    secret = "postgresql://user:private-password@example.test/database"

    config = CoordinationConfig.from_environment(
        {
            "FOOTBALL_COORDINATION_CONFIG": str(config_path),
            "TEAM_DATABASE_URL": secret,
        }
    )

    assert config.database_url == secret
    assert config.deployment_id == "team-cloud"
    assert config.authority_id == "cloud-primary"
    assert config.authority_epoch == 2
    assert config.connect_timeout_seconds == 7
    assert secret not in config_path.read_text(encoding="utf-8")


def test_checked_in_coordination_example_matches_runtime_contract() -> None:
    example = (
        Path(__file__).parents[1]
        / "config"
        / "coordination.example.json"
    )
    secret = "postgresql://example:fake@example.test/football"

    config = CoordinationConfig.from_environment(
        {
            "FOOTBALL_COORDINATION_CONFIG": str(example),
            "FOOTBALL_DATABASE_URL": secret,
        }
    )

    assert config.database_url == secret
    assert config.mode == "postgresql"
    assert config.authority_id == "brendan-local-docker"
    assert config.lease_idle_warning_seconds == 1080
    assert config.lease_idle_release_seconds == 1200
    assert config.artifact_providers["xebia-shared"]["root_env"] == (
        "FOOTBALL_ARTIFACT_ROOT"
    )


def test_json_coordination_config_requires_secret_and_valid_contract(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "coordination.json"
    config_path.write_text(
        json.dumps({"database_url_env": "MISSING", "settings": {}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="MISSING"):
        CoordinationConfig.from_environment(
            {"FOOTBALL_COORDINATION_CONFIG": str(config_path)}
        )

    config_path.write_text(
        json.dumps(
            {
                "database_url_env": "DATABASE_URL",
                "settings": {"lease_expiry_seconds": 301},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="fixed repository contract"):
        CoordinationConfig.from_environment(
            {
                "FOOTBALL_COORDINATION_CONFIG": str(config_path),
                "DATABASE_URL": "postgresql://example.test/database",
            }
        )


def test_invalid_json_coordination_config_is_rejected(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "coordination.json"
    config_path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ValueError, match="Cannot read"):
        CoordinationConfig.from_environment(
            {"FOOTBALL_COORDINATION_CONFIG": str(config_path)}
        )


def test_authority_identity_can_reject_retired_local_environment() -> None:
    repository = InMemoryCoordinationRepository(
        environment=EnvironmentIdentity("local", "local", 1, retired=True)
    )

    with pytest.raises(AuthorityRetiredError, match="retired"):
        repository.assert_authority("local", 1)


def test_database_modes_are_disabled_or_explicitly_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disabled = create_coordination_repository(
        CoordinationConfig(database_url=None)
    )
    assert disabled.health().mode is DatabaseMode.DISABLED
    with pytest.raises(DatabaseUnavailableError, match="not configured"):
        disabled.get_segment("workflow", "segment")

    monkeypatch.setitem(sys.modules, "psycopg", None)
    unavailable = create_coordination_repository(
        CoordinationConfig(database_url="postgresql://configured-but-not-used")
    )
    assert unavailable.health().mode is DatabaseMode.UNAVAILABLE
    with pytest.raises(DatabaseUnavailableError, match="optional"):
        unavailable.get_segment("workflow", "segment")


def test_preflight_cli_json_exit_codes_and_never_prints_secret(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeRepository:
        def close(self) -> None:
            return None

    secret = "postgresql://user:do-not-print@example.test/database"
    config = CoordinationConfig(database_url=secret)
    unavailable_result = SimpleNamespace(
        repository=FakeRepository(),
        health=DatabaseHealth(
            DatabaseMode.UNAVAILABLE,
            f"connection failed for {secret}",
        ),
        writable=False,
        migrations=None,
        reconciliation=ReconciliationResult(
            "not_requested", "not run"
        ),
    )
    monkeypatch.setattr(
        coordination_cli.CoordinationConfig,
        "from_environment",
        classmethod(lambda _cls: config),
    )
    monkeypatch.setattr(
        coordination_cli,
        "run_coordination_preflight",
        lambda _config: unavailable_result,
    )

    assert coordination_cli.main(["--json"]) == 1
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["mode"] == "unavailable"
    assert payload["writable"] is False
    assert secret not in output

    disabled_config = CoordinationConfig(database_url=None)
    disabled_result = SimpleNamespace(
        repository=FakeRepository(),
        health=DatabaseHealth(DatabaseMode.DISABLED, "not configured"),
        writable=False,
        migrations=None,
        reconciliation=ReconciliationResult(
            "not_requested", "disabled"
        ),
    )
    monkeypatch.setattr(
        coordination_cli.CoordinationConfig,
        "from_environment",
        classmethod(lambda _cls: disabled_config),
    )
    monkeypatch.setattr(
        coordination_cli,
        "run_coordination_preflight",
        lambda _config: disabled_result,
    )
    assert coordination_cli.main(["--json"]) == 0


def test_preflight_cli_invalid_config_exits_nonzero_without_secret(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "postgresql://user:hidden@example.test/database"

    def invalid_config() -> CoordinationConfig:
        raise ValueError(f"invalid secret {secret}")

    monkeypatch.setattr(
        coordination_cli.CoordinationConfig,
        "from_environment",
        classmethod(lambda _cls: invalid_config()),
    )

    assert coordination_cli.main(["--json"]) == 2
    output = capsys.readouterr().out
    assert json.loads(output)["mode"] == "unavailable"
    assert secret not in output


def test_bootstrap_preflight_runs_migrations_seeds_and_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCursor:
        def fetchone(self) -> tuple[int]:
            return (1,)

    class FakeConnection:
        autocommit = False

        def __init__(self) -> None:
            self.closed = False

        def execute(self, _sql: str, _parameters: object = None) -> FakeCursor:
            return FakeCursor()

        def close(self) -> None:
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setitem(
        sys.modules,
        "psycopg",
        SimpleNamespace(connect=lambda *_args, **_kwargs: connection),
    )
    monkeypatch.setattr(
        postgres_module,
        "apply_migrations",
        lambda *_args, **_kwargs: MigrationResult((1, 2), (2,)),
    )
    monkeypatch.setattr(
        postgres_module,
        "_register_environment",
        lambda *_args: EnvironmentIdentity("test", "test", 1),
    )
    seeded: list[bool] = []
    monkeypatch.setattr(
        postgres_module,
        "_ensure_workflow_seeds",
        lambda *_args: seeded.append(True),
    )

    result = bootstrap_coordination(
        CoordinationConfig(
            database_url="postgresql://not-opened",
            deployment_id="test",
            authority_id="test",
        ),
        reconciliation_hook=lambda _repository: {
            "reconciled_segments": 2
        },
    )

    assert result.writable
    assert result.migrations == MigrationResult((1, 2), (2,))
    assert result.reconciliation.metadata["reconciled_segments"] == 2
    assert seeded == [True]
    assert not connection.closed


def test_failed_reconciliation_blocks_writable_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConnection:
        autocommit = False
        closed = False

        def close(self) -> None:
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setitem(
        sys.modules,
        "psycopg",
        SimpleNamespace(connect=lambda *_args, **_kwargs: connection),
    )
    monkeypatch.setattr(
        postgres_module,
        "apply_migrations",
        lambda *_args, **_kwargs: MigrationResult((1, 2), ()),
    )
    monkeypatch.setattr(
        postgres_module,
        "_register_environment",
        lambda *_args: EnvironmentIdentity("test", "test", 1),
    )
    monkeypatch.setattr(
        postgres_module,
        "_ensure_workflow_seeds",
        lambda *_args: None,
    )

    result = bootstrap_coordination(
        CoordinationConfig(
            database_url="postgresql://not-opened",
            deployment_id="test",
            authority_id="test",
        ),
        reconciliation_hook=lambda _repository: ReconciliationResult(
            "failed", "shared state differs"
        ),
    )

    assert not result.writable
    assert result.health.mode is DatabaseMode.UNAVAILABLE
    assert result.reconciliation.status == "failed"
    assert connection.closed


def test_identity_registration_is_workflow_independent() -> None:
    repository = InMemoryCoordinationRepository()
    identity = Identity(
        "example\\developer",
        "79b0ab35-063c-44cb-b625-abdb062e7bb2",
        "EXAMPLE",
        "Developer",
        "workstation",
        "192.0.2.1",
    )

    repository.register_identity(identity)
    audit = repository.append_audit(
        "identity.registered",
        identity.developer_id,
        workflow_id="innovation_day_bac",
        machine_id=identity.machine_id,
    )
    assert repository.health().mode is DatabaseMode.AVAILABLE
    assert audit.machine_id == identity.machine_id
