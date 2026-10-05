"""Rule: a same-team transfer may take longer than the normal transfer window
(up to the uncontested limit) when no opponent owns the ball in between and the
receiver is a distinct, co-visible player. A track-ID handoff during a dribble
(not co-visible) or an opponent touch in between keeps the normal limit."""

from football_poc.engine.common import PossessionSegment
from football_poc.engine.completed_pass import infer_transfer_events
from rule_builders import observation


def _run(pairs, between=()):
    sender = [
        observation(0.0, "black", 1, 0, 0, control_ratio=0.3),
        observation(0.2, "black", 1, 0, 0, control_ratio=0.3),
        observation(0.4, "black", 1, 0, 0, control_ratio=0.3),
    ]
    receiver = [
        observation(5.0, "black", 2, 900, 900, control_ratio=0.3),
        observation(5.2, "black", 2, 900, 900, control_ratio=0.3),
    ]
    return infer_transfer_events(
        [PossessionSegment("black", 1, sender), PossessionSegment("black", 2, receiver)],
        maximum_transfer_seconds=3.0,
        minimum_transfer_heights=1.5,
        control_observations=[*sender, *between, *receiver],
        co_visible_track_pairs=pairs,
    )


def test_uncontested_long_pass_to_co_visible_teammate_20261005T043449715Z():
    events = _run({frozenset((1, 2))})
    assert [(e.event_type, e.from_player_track_id, e.to_player_track_id) for e in events] == [
        ("pass_candidate", 1, 2)
    ]


def test_long_gap_track_handoff_is_not_a_pass_20261005T043449716Z():
    assert _run(set()) == []


def test_long_gap_with_opponent_touch_is_not_a_pass_20261005T043449717Z():
    touch = [observation(2.5, "red", 9, 400, 400, control_ratio=0.6)]
    assert _run({frozenset((1, 2))}, touch) == []
