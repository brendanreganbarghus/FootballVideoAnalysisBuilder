"""Rule: a turnover by a team that never gained possession is rejected when its
apparent control was brief (<= 1 s) and the ball returns to the team that
already had it, e.g. a defender shadowing a dribbler without touching the ball.
A turnover after a recorded gain, or after longer control, is kept."""

from football_poc.engine.common import PossessionSegment, PredictedEvent
from football_poc.engine.turnover_refinement import (
    suppress_unestablished_brief_opponent_turnovers,
)
from rule_builders import observation


def _pass(t, team, a, b):
    return PredictedEvent("pass_candidate", t - 1.0, team, a, b, 0.8, "", t)


def _turnover(t, team, a, b):
    return PredictedEvent("turnover_candidate", t - 0.4, team, a, b, 0.8, "", t)


def _red_segment(end):
    return PossessionSegment(
        "red",
        5,
        [observation(s, "red", 5, 0, 0, control_ratio=0.5) for s in (10.0, end)],
    )


def test_shadowing_defender_turnover_rejected_20261005T044704191Z():
    events = [_pass(9.0, "black", 1, 2), _turnover(10.6, "red", 5, 3)]
    result = suppress_unestablished_brief_opponent_turnovers(events, [_red_segment(10.6)])
    assert [e.event_type for e in result] == ["pass_candidate"]


def test_turnover_after_recorded_gain_kept_20261005T044704192Z():
    events = [_turnover(9.0, "black", 2, 5), _turnover(10.6, "red", 5, 3)]
    result = suppress_unestablished_brief_opponent_turnovers(events, [_red_segment(10.6)])
    assert len(result) == 2


def test_turnover_after_long_control_kept_20261005T044704193Z():
    events = [_pass(9.0, "black", 1, 2), _turnover(11.8, "red", 5, 3)]
    result = suppress_unestablished_brief_opponent_turnovers(events, [_red_segment(11.6)])
    assert len(result) == 2
