"""Rule: a turnover from a player track to the same track is a colour flicker
when that track showed the losing colour for at most 1 s. The turnover is
dropped and the delivery to that player is credited to the track's settled
team. A track that held the other colour for longer (an identity handoff in a
scramble) keeps its turnover."""

from football_poc.engine.common import PossessionSegment, PredictedEvent
from football_poc.engine.turnover_refinement import reconcile_self_track_turnovers
from rule_builders import observation


def _run(red_seconds):
    events = [
        PredictedEvent("pass_candidate", 2.0, "red", None, 94, 0.8, "", 3.8),
        PredictedEvent("turnover_candidate", 3.8, "red", 94, 94, 0.6, "", 4.0),
    ]
    black = [observation(s, "black", 94, 0, 0) for s in (4.0, 4.2, 4.4)]
    red = [observation(s, "red", 94, 0, 0) for s in red_seconds]
    return reconcile_self_track_turnovers(
        events, [PossessionSegment("black", 94, black)], [*red, *black]
    )


def test_brief_self_track_flicker_credits_delivery_to_settled_team_20261005T045507731Z():
    result = _run((3.6, 3.8))
    assert [(e.event_type, e.team) for e in result] == [("pass_candidate", "black")]


def test_long_other_colour_track_keeps_turnover_20261005T045507732Z():
    result = _run((1.8, 2.4, 3.0, 3.8))
    assert [e.event_type for e in result] == ["pass_candidate", "turnover_candidate"]
