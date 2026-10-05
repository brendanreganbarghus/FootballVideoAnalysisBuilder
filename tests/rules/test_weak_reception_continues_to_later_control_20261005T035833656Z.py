"""Rule: a pass credited on weak proximity alone completes at the receiver's
first clear touch, even when a brief same-team ownership flicker splits the
receiver's possession; an opponent in between stops the search."""

from football_poc.engine.common import PossessionSegment, PredictedEvent
from football_poc.engine.flight_receptions import (
    refine_weak_reception_completion_times,
)
from rule_builders import observation


def _refine(flicker_team):
    weak = PossessionSegment(
        "black",
        8,
        [
            observation(10.6, "black", 8, 0, 0, control_ratio=1.3),
            observation(10.8, "black", 8, 0, 0, control_ratio=0.9),
            observation(11.0, "black", 8, 0, 0, control_ratio=1.6),
        ],
    )
    flicker = PossessionSegment(
        flicker_team, 142, [observation(11.2, flicker_team, 142, 0, 0)]
    )
    control = PossessionSegment(
        "black",
        8,
        [
            observation(11.8, "black", 8, 0, 0, control_ratio=1.2),
            observation(12.4, "black", 8, 0, 0, control_ratio=0.6),
            observation(13.0, "black", 8, 0, 0, control_ratio=0.06),
            observation(13.2, "black", 8, 0, 0, control_ratio=0.3),
        ],
    )
    event = PredictedEvent(
        "pass_candidate", 10.4, "black", 9, 8, 0.8, "release", 10.6
    )
    return refine_weak_reception_completion_times(
        [event], [weak, flicker, control]
    )[0]


def test_weak_reception_continues_past_same_team_flicker_20261005T035833656Z():
    assert _refine("black").completion_seconds == 13.0


def test_opponent_ownership_stops_continuation_search_20261005T035833657Z():
    assert _refine("red").completion_seconds == 10.6
