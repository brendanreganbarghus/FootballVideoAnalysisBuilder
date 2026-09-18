from __future__ import annotations

from pathlib import Path

import pytest

from football_poc.coordination import (
    InMemoryCoordinationRepository,
    ManualEventMapping,
    ManualReferenceConflictError,
    ManualReferenceMember,
)


MACHINE_ID = "79b0ab35-063c-44cb-b625-abdb062e7bb2"


def _repository_with_lease():
    repository = InMemoryCoordinationRepository()
    lease = repository.acquire_lease(
        "innovation_day_bac",
        "segment-1",
        "reviewer",
        MACHINE_ID,
        "manual-review",
    )
    return repository, lease


def test_manual_draft_uses_append_only_m_events_and_exact_positions() -> None:
    repository, lease = _repository_with_lease()
    first = repository.append_manual_event(
        "innovation_day_bac",
        "segment-1",
        "M1",
        60_000,
        1499,
        {"event_type": "completed_pass", "team": "red"},
        "reviewer",
        lease.token,
    )
    edited = repository.append_manual_event(
        "innovation_day_bac",
        "segment-1",
        "M1",
        59_875,
        1500,
        {"event_type": "shot", "team": "black"},
        "reviewer",
        lease.token,
    )
    draft = repository.create_manual_reference_draft(
        "innovation_day_bac", "segment-1", "reviewer", lease.token
    )
    draft = repository.replace_manual_reference_membership(
        "innovation_day_bac",
        "segment-1",
        draft.revision,
        (ManualReferenceMember(0, "M1", edited.revision),),
        "reviewer",
        lease.token,
    )

    assert first.revision == 1
    assert first.timestamp_ms == 60_000
    assert first.source_frame == 1499
    assert edited.revision == 2
    assert repository.get_manual_event_revision(
        "innovation_day_bac", "segment-1", "M1", 1
    ) == first
    assert draft.members == (ManualReferenceMember(0, "M1", 2),)
    with pytest.raises(ValueError, match="0 to 60000"):
        repository.append_manual_event(
            "innovation_day_bac",
            "segment-1",
            "M2",
            60_001,
            1500,
            {},
            "reviewer",
            lease.token,
        )


def test_approval_freezes_partial_and_unusual_reviewer_mappings() -> None:
    repository, lease = _repository_with_lease()
    events = tuple(
        repository.append_manual_event(
            "innovation_day_bac",
            "segment-1",
            f"M{index}",
            timestamp,
            frame,
            {"event_type": event_type, "team": team},
            "reviewer",
            lease.token,
        )
        for index, timestamp, frame, event_type, team in (
            (1, 1_000, 25, "completed_pass", "red"),
            (2, 58_000, 1451, "shot", "black"),
            (3, 60_000, 1499, "turnover", "red"),
        )
    )
    draft = repository.create_manual_reference_draft(
        "innovation_day_bac", "segment-1", "reviewer", lease.token
    )
    draft = repository.replace_manual_reference_membership(
        "innovation_day_bac",
        "segment-1",
        draft.revision,
        tuple(
            ManualReferenceMember(index, event.event_key, event.revision)
            for index, event in enumerate(events)
        ),
        "reviewer",
        lease.token,
    )
    unusual = ManualEventMapping("M1", "E-different-team-type-time")
    draft = repository.replace_manual_event_mappings(
        "innovation_day_bac",
        "segment-1",
        draft.revision,
        (unusual,),
        "reviewer",
        lease.token,
    )
    approved = repository.approve_manual_reference_set(
        "innovation_day_bac",
        "segment-1",
        draft.revision,
        "reviewer",
        lease.token,
    )

    assert approved.status == "approved"
    assert approved.mappings == (unusual,)
    assert len(approved.mappings) < len(approved.members)
    with pytest.raises(ManualReferenceConflictError, match="immutable"):
        repository.replace_manual_event_mappings(
            "innovation_day_bac",
            "segment-1",
            approved.revision,
            (),
            "reviewer",
            lease.token,
        )


def test_new_draft_copies_approval_without_mutating_golden_snapshot() -> None:
    repository, lease = _repository_with_lease()
    event = repository.append_manual_event(
        "innovation_day_bac",
        "segment-1",
        "M1",
        5_000,
        123,
        {"event_type": "completed_pass"},
        "reviewer",
        lease.token,
    )
    first = repository.create_manual_reference_draft(
        "innovation_day_bac", "segment-1", "reviewer", lease.token
    )
    first = repository.replace_manual_reference_membership(
        "innovation_day_bac",
        "segment-1",
        first.revision,
        (ManualReferenceMember(0, "M1", event.revision),),
        "reviewer",
        lease.token,
    )
    golden = repository.approve_manual_reference_set(
        "innovation_day_bac",
        "segment-1",
        first.revision,
        "reviewer",
        lease.token,
    )

    reopened = repository.create_manual_reference_draft(
        "innovation_day_bac", "segment-1", "reviewer", lease.token
    )
    reopened = repository.replace_manual_reference_membership(
        "innovation_day_bac",
        "segment-1",
        reopened.revision,
        (),
        "reviewer",
        lease.token,
    )

    assert reopened.status == "draft"
    assert reopened.based_on_revision == golden.revision
    assert reopened.members == ()
    assert repository.get_approved_manual_reference_set(
        "innovation_day_bac", "segment-1"
    ) == golden
    assert repository.get_manual_reference_set(
        "innovation_day_bac", "segment-1", golden.revision
    ) == golden


def test_mapping_uniqueness_is_one_to_one_within_each_revision() -> None:
    repository, lease = _repository_with_lease()
    events = [
        repository.append_manual_event(
            "innovation_day_bac",
            "segment-1",
            key,
            index * 1000,
            index * 25,
            {"event_type": "completed_pass"},
            "reviewer",
            lease.token,
        )
        for index, key in enumerate(("M1", "M2"), start=1)
    ]
    draft = repository.create_manual_reference_draft(
        "innovation_day_bac", "segment-1", "reviewer", lease.token
    )
    repository.replace_manual_reference_membership(
        "innovation_day_bac",
        "segment-1",
        draft.revision,
        tuple(
            ManualReferenceMember(index, event.event_key, event.revision)
            for index, event in enumerate(events)
        ),
        "reviewer",
        lease.token,
    )

    with pytest.raises(ManualReferenceConflictError, match="one-to-one"):
        repository.replace_manual_event_mappings(
            "innovation_day_bac",
            "segment-1",
            draft.revision,
            (
                ManualEventMapping("M1", "E1"),
                ManualEventMapping("M2", "E1"),
            ),
            "reviewer",
            lease.token,
        )


def test_manual_reference_migration_uses_m_stream_without_payload_copy() -> None:
    schema = (
        Path(__file__).parents[1]
        / "migrations"
        / "coordination"
        / "0004_manual_reference_sets.sql"
    ).read_text(encoding="utf-8")

    membership = schema.split(
        "CREATE TABLE manual_reference_memberships (", 1
    )[1].split("\n);", 1)[0]
    mapping = schema.split("CREATE TABLE manual_event_mappings (", 1)[1].split(
        "\n);", 1
    )[0]
    assert "stream char(1) NOT NULL DEFAULT 'M' CHECK (stream = 'M')" in membership
    assert "REFERENCES event_revisions(" in membership
    assert "payload jsonb" not in membership
    assert "payload jsonb" not in mapping
    assert "approved manual reference set revisions are immutable" in schema
    assert "BETWEEN 0 AND 60000" in schema
