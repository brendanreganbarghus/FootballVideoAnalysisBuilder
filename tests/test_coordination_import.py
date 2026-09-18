from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from football_poc.coordination import (
    HistoricalImportSource,
    InMemoryCoordinationRepository,
    Segment,
)
from football_poc.coordination.history_import import (
    apply_import,
    build_reconciliation_hook,
    dry_run_import,
)
from football_poc.coordination.migrations import (
    REQUIRED_IMPORT_INDEXES,
    discover_migrations,
)


def _write_state(
    root: Path,
    *,
    directory: str = "event-review-state-innovation",
    workflow: str = "innovation_day_bac",
    canvas: str = "football-event-review",
    segment: str = "segment-0001-030",
    value: str = "reviewed",
    checksum: bool = True,
    include_identity: bool = True,
    state_segment: str | None = None,
    extra_state: dict[str, object] | None = None,
) -> Path:
    path = (
        root
        / "30-shared-baselines"
        / directory
        / f"{segment}-review-state.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "schemaVersion": 1,
        "segment": state_segment or segment,
        "value": value,
        "additionalProposals": [
            {"event_type": "completed_pass", "seconds": 4.2}
        ],
        "decisions": {"0": {"status": "accepted", "reason": "visible"}},
        "conversation": [{"role": "user", "content": "review"}],
    }
    if include_identity:
        state.update({"workflowId": workflow, "canvasId": canvas})
    if extra_state:
        state.update(extra_state)
    content = json.dumps(state, sort_keys=True).encode()
    path.write_bytes(content)
    if checksum:
        manifest = root / "00-governance" / "checksums.sha256"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        relative = path.relative_to(root).as_posix()
        with manifest.open("a", encoding="utf-8") as handle:
            handle.write(f"{hashlib.sha256(content).hexdigest()}  {relative}\n")
    return path


def test_import_ledger_migration_has_required_schema_and_index() -> None:
    migration = next(
        item
        for item in discover_migrations()
        if item.name == "historical_review_imports"
    )

    assert migration.name == "historical_review_imports"
    assert "CREATE TABLE historical_review_imports" in migration.sql
    assert (
        "PRIMARY KEY (workflow_id, provider_id, logical_key, source_sha256)"
        in migration.sql
    )
    for index in REQUIRED_IMPORT_INDEXES:
        assert f"CREATE INDEX {index}" in migration.sql


def test_checksum_failure_is_rejected_before_json_parsing(tmp_path: Path) -> None:
    path = _write_state(tmp_path)
    path.write_text("{not-json", encoding="utf-8")

    report = apply_import(InMemoryCoordinationRepository(), tmp_path)

    assert report.counts == {
        "inserted": 0,
        "unchanged": 0,
        "conflicting": 0,
        "rejected": 1,
    }
    assert "checksum mismatch" in report.outcomes[0].details["reason"]


@pytest.mark.parametrize(
    ("overrides", "expected_field"),
    (
        ({"workflow": "live_iteration_25"}, "workflowId"),
        ({"canvas": "football-event-review-live"}, "canvasId"),
        ({"state_segment": "segment-other"}, "segment"),
    ),
)
def test_nonempty_identity_mismatch_is_rejected(
    tmp_path: Path,
    overrides: dict[str, str],
    expected_field: str,
) -> None:
    _write_state(tmp_path, **overrides)

    report = dry_run_import(InMemoryCoordinationRepository(), tmp_path)

    assert report.counts["rejected"] == 1
    assert expected_field in report.outcomes[0].details["reason"]


@pytest.mark.parametrize(
    ("directory", "workflow", "canvas"),
    (
        (
            "event-review-state-innovation",
            "innovation_day_bac",
            "football-event-review",
        ),
        (
            "event-review-state-live",
            "live_iteration_25",
            "football-event-review-live",
        ),
    ),
)
def test_legacy_missing_identity_is_canonicalized_from_trusted_directory(
    tmp_path: Path,
    directory: str,
    workflow: str,
    canvas: str,
) -> None:
    _write_state(
        tmp_path,
        directory=directory,
        workflow=workflow,
        canvas=canvas,
        include_identity=False,
    )
    repository = InMemoryCoordinationRepository()

    report = apply_import(repository, tmp_path)
    rerun = apply_import(repository, tmp_path)

    assert report.counts["inserted"] == 1
    assert report.outcomes[0].details["canonicalized_fields"] == [
        "workflowId",
        "canvasId",
    ]
    assert rerun.outcomes[0].details["canonicalized_fields"] == [
        "workflowId",
        "canvasId",
    ]
    assert "workflowId" not in report.outcomes[0].details["source_state"]
    assert "canvasId" not in report.outcomes[0].details["source_state"]
    state = repository.get_state(workflow, "segment-0001-030").state
    assert state["workflowId"] == workflow
    assert state["canvasId"] == canvas


def test_dry_run_does_not_mutate_repository(tmp_path: Path) -> None:
    _write_state(tmp_path)
    repository = InMemoryCoordinationRepository()

    report = dry_run_import(repository, tmp_path)

    assert report.counts["inserted"] == 1
    assert repository.list_segments("innovation_day_bac") == ()
    assert repository.get_state(
        "innovation_day_bac", "segment-0001-030"
    ) is None


def test_apply_is_lossless_and_idempotent(tmp_path: Path) -> None:
    path = _write_state(tmp_path)
    expected = json.loads(path.read_text(encoding="utf-8"))
    repository = InMemoryCoordinationRepository()

    first = apply_import(repository, tmp_path)
    second = apply_import(repository, tmp_path)

    assert first.counts["inserted"] == 1
    assert second.counts["unchanged"] == 1
    assert repository.get_state(
        "innovation_day_bac", "segment-0001-030"
    ).state == expected
    assert (
        "C",
        "innovation_day_bac",
        "segment-0001-030",
    ) not in repository._history
    assert len(
        repository._history[
            ("activity", "innovation_day_bac", "segment-0001-030")
        ]
    ) == 1
    decision = repository._history[
        ("decision", "innovation_day_bac", "segment-0001-030")
    ][0][1]
    assert decision["proposal_key"] == "decision-index:0"
    assert decision["status"] == "accepted"


def test_keyless_real_state_shape_skips_event_history_in_preview_and_apply(
    tmp_path: Path,
) -> None:
    path = _write_state(
        tmp_path,
        extra_state={
            "engineBefore": {
                "predictions": [
                    {
                        "event_type": "completed_pass",
                        "seconds": 4.2,
                    }
                ]
            }
        },
    )
    expected = json.loads(path.read_text(encoding="utf-8"))
    repository = InMemoryCoordinationRepository()

    preview = dry_run_import(repository, tmp_path)
    applied = apply_import(repository, tmp_path)

    assert preview.outcomes[0].details["history_records"] == 2
    assert applied.outcomes[0].details["history_records"] == 2
    assert repository.get_state(
        "innovation_day_bac", "segment-0001-030"
    ).state == expected
    assert not any(
        key[0] in {"C", "E", "M"} for key in repository._history
    )
    assert repository._history[
        ("decision", "innovation_day_bac", "segment-0001-030")
    ][0][1]["proposal_key"] == "decision-index:0"


def test_explicit_event_keys_are_imported_without_positional_synthesis(
    tmp_path: Path,
) -> None:
    _write_state(
        tmp_path,
        extra_state={
            "additionalProposals": [
                {
                    "event_key": "C7",
                    "event_type": "completed_pass",
                    "seconds": 4.2,
                }
            ],
            "engineBefore": {
                "predictions": [
                    {
                        "event_key": "E3",
                        "event_type": "completed_pass",
                        "seconds": 4.2,
                    }
                ]
            },
        },
    )
    repository = InMemoryCoordinationRepository()

    report = apply_import(repository, tmp_path)

    assert report.outcomes[0].details["history_records"] == 4
    assert repository._history[
        ("C", "innovation_day_bac", "segment-0001-030")
    ][0][1]["event_key"] == "C7"
    assert repository._history[
        ("E", "innovation_day_bac", "segment-0001-030")
    ][0][1]["event_key"] == "E3"


def test_memory_import_batch_rolls_back_every_source_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = InMemoryCoordinationRepository()
    sources = tuple(
        HistoricalImportSource(
            "innovation_day_bac",
            "test-provider",
            f"state-{index}.json",
            str(index) * 64,
            f"segment-{index}",
            {"segment": f"segment-{index}"},
            10,
        )
        for index in (1, 2)
    )
    from football_poc.coordination import history_import

    def derive(state: dict[str, object]):
        if state["segment"] == "segment-2":
            raise ValueError("synthetic second-source failure")
        return ()

    monkeypatch.setattr(history_import, "derive_history_records", derive)

    with pytest.raises(ValueError, match="second-source"):
        repository.import_historical_states(sources, apply=True)

    assert repository.list_segments("innovation_day_bac") == ()


def test_existing_different_authoritative_state_conflicts(
    tmp_path: Path,
) -> None:
    _write_state(tmp_path)
    repository = InMemoryCoordinationRepository()
    repository.upsert_segment(
        Segment(
            "innovation_day_bac",
            "segment-0001-030",
            (
                "30-shared-baselines/event-review-state-innovation/"
                "segment-0001-030-review-state.json"
            ),
            {},
        )
    )
    lease = repository.acquire_lease(
        "innovation_day_bac",
        "segment-0001-030",
        "owner",
        "79b0ab35-063c-44cb-b625-abdb062e7bb2",
        "review",
    )
    repository.mutate_state(
        "innovation_day_bac",
        "segment-0001-030",
        0,
        {"different": True},
        "owner",
        lease.token,
    )

    report = apply_import(repository, tmp_path)
    hook_result = build_reconciliation_hook(tmp_path)(repository)

    assert report.counts["conflicting"] == 1
    assert repository.get_state(
        "innovation_day_bac", "segment-0001-030"
    ).state == {"different": True}
    assert hook_result.status == "conflict"
    assert not hook_result.succeeded


def test_same_segment_is_isolated_by_workflow(tmp_path: Path) -> None:
    _write_state(tmp_path)
    _write_state(
        tmp_path,
        directory="event-review-state-live",
        workflow="live_iteration_25",
        canvas="football-event-review-live",
    )
    repository = InMemoryCoordinationRepository()

    report = apply_import(repository, tmp_path)

    assert report.counts["inserted"] == 2
    assert repository.get_state(
        "innovation_day_bac", "segment-0001-030"
    ).state["workflowId"] == "innovation_day_bac"
    assert repository.get_state(
        "live_iteration_25", "segment-0001-030"
    ).state["workflowId"] == "live_iteration_25"


def test_explicit_regression_registry_is_imported_idempotently(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "00-governance" / "checksums.sha256"
    governance.parent.mkdir(parents=True)
    governance.write_text("", encoding="utf-8")
    registry = tmp_path.parent / f"{tmp_path.name}-innovation-regressions.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "workflow": "innovation_day_bac",
                "segments": [],
            }
        ),
        encoding="utf-8",
    )
    repository = InMemoryCoordinationRepository()
    options = {"innovation_day_bac": registry}

    first = apply_import(repository, tmp_path, regression_paths=options)
    second = apply_import(repository, tmp_path, regression_paths=options)

    assert first.counts["inserted"] == 1
    assert first.outcomes[0].details["kind"] == "regression_registry"
    assert second.counts["unchanged"] == 1
