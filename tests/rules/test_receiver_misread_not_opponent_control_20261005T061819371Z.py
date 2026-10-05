"""Rule: a pass is not cancelled as "crossing opponent control" by the
receiver's own track reading the other kit colour, when that reading runs
continuously (steps of at most 0.4 s) into the completion: it is the reception
itself. The same reading separated from the completion by a gap is still
treated as opponent control."""

from football_poc.engine.common import PossessionObservation, PredictedEvent
from football_poc.engine.pass_reconciliation import (
    suppress_passes_crossing_opponent_control,
)


def _observation(seconds, team, track, ratio):
    return PossessionObservation(
        int(seconds * 5), seconds, team, track, 0, 0, 100, 0, 0, ratio,
    )


def _pass():
    return PredictedEvent(
        "pass_candidate", 2.0, "black", 50, 94, 0.8, "transfer", 4.0
    )


def test_receiver_colour_misread_into_completion_keeps_pass_20261005T061819371Z():
    observations = [
        _observation(3.6, "red", 94, 0.15),
        _observation(3.8, "red", 94, 0.30),
        _observation(4.0, "black", 94, 0.12),
    ]
    assert suppress_passes_crossing_opponent_control(
        [_pass()], observations
    ) == [_pass()]


def test_receiver_misread_with_gap_before_completion_drops_pass_20261005T061819372Z():
    observations = [
        _observation(2.4, "red", 94, 0.15),
        _observation(2.6, "red", 94, 0.30),
        _observation(4.0, "black", 94, 0.12),
    ]
    assert suppress_passes_crossing_opponent_control(
        [_pass()], observations
    ) == []
