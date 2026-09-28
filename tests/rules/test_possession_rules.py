"""Timestamped possession rule unit tests (one test per implemented rule)."""

from rule_builders import observation, transfer_events


def test_same_team_control_transfer_is_pass_20260928T191735915Z() -> None:
    """Rule: controlled transfer between same-team players is a pass."""
    events = transfer_events([
        observation(0.0, "blue", 1, 100, 100),
        observation(0.1, "blue", 1, 102, 102),
        observation(1.0, "blue", 2, 300, 300),
        observation(1.1, "blue", 2, 302, 302),
    ])

    assert [event.event_type for event in events] == ["pass_candidate"]


def test_turnover_belongs_to_team_losing_control_20260928T191735965Z() -> None:
    """Rule: a turnover is attributed to the team that loses control."""
    events = transfer_events(
        [
            observation(1.0, "black", 1, 100, 100),
            observation(1.2, "black", 1, 101, 100),
            observation(1.8, "red", 2, 102, 100),
            observation(2.0, "red", 2, 103, 100),
            observation(2.2, "red", 2, 104, 100),
            observation(2.4, "red", 2, 105, 100),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
        maximum_transfer_seconds=1.0,
    )

    assert [(event.event_type, event.team) for event in events] == [
        ("turnover_candidate", "black")
    ]
