"""Rule: a sender who controlled the ball and then dribbles on with longer
touches (ball still within 1 control radius, but outside tight control) is
still the sender when an opponent then takes control. Without the earlier
controlled spell by the same player, a never-controlling nearest player is
not a sender."""

from football_poc.engine.common import PossessionSegment
from football_poc.possession import infer_transfer_events
from rule_builders import observation


def _segment(team, track, samples, x=0.0):
    return PossessionSegment(
        team,
        track,
        [observation(s, team, track, x, x, control_ratio=r) for s, r in samples],
    )


def _run(segments):
    return infer_transfer_events(
        segments, maximum_transfer_seconds=3.0, minimum_transfer_heights=1.0
    )


def _receiver():
    return _segment("red", 70, [(13.8, 0.3), (14.0, 0.4), (14.2, 0.3)], x=400.0)


def test_dribbling_sender_turnover_kept_20261005T051537051Z():
    events = _run(
        [
            _segment("black", 2, [(10.0, 0.4), (10.2, 0.3), (10.6, 0.3)]),
            _segment("black", 2, [(11.4, 1.0), (11.6, 1.0), (12.0, 0.77)]),
            _receiver(),
        ]
    )
    assert [(e.event_type, e.team, e.completion_seconds) for e in events] == [
        ("turnover_candidate", "black", 13.8)
    ]


def test_never_controlling_sender_no_turnover_20261005T051537052Z():
    events = _run(
        [
            _segment("black", 2, [(11.4, 1.0), (11.6, 1.0), (12.0, 0.77)]),
            _receiver(),
        ]
    )
    assert events == []
