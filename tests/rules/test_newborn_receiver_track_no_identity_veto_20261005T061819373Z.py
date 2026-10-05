"""Rule: a pass receiver's "stable earlier team" from the tracker may veto a
same-team pass only when the receiver's track already existed before the
0.8 s pre-contact window. A track born inside that window has no established
earlier identity; its first boxes often still include the opponent it emerged
from, so the frame-level kit evidence at the reception decides."""

from football_poc.engine.common import PredictedEvent
from football_poc.engine.pass_reconciliation import (
    reconcile_track_identity_team_switches,
)

UNCLEAR = {"blue": 0.0, "white": 0.11, "dark": 0.23, "warm": 0.0, "yellow": 0.2}
BLACK = {"blue": 0.02, "white": 0.01, "dark": 0.82, "warm": 0.0, "yellow": 0.02}


def _players(receiver_birth):
    frames = {}
    for index in range(30):
        seconds = round(index * 0.2, 1)
        boxes = []
        if seconds <= 2.0:
            boxes.append({
                "track_id": 50, "team": "black", "clip_seconds": seconds,
                "color_scores": BLACK, "x1": 0, "y1": 0, "x2": 40, "y2": 100,
            })
        if seconds >= receiver_birth:
            boxes.append({
                "track_id": 94, "team": "red" if seconds < 4.0 else "black",
                "clip_seconds": seconds,
                "color_scores": UNCLEAR if seconds < 3.8 else BLACK,
                "x1": 500, "y1": 0, "x2": 540, "y2": 100,
            })
        frames[index] = boxes
    return frames


def _pass():
    return PredictedEvent(
        "pass_candidate", 2.0, "black", 50, 94, 0.8, "transfer", 4.0
    )


def _run(receiver_birth):
    return reconcile_track_identity_team_switches(
        [_pass()], _players(receiver_birth), maximum_chain_seconds=2.0
    )


def test_newborn_receiver_track_cannot_veto_pass_20261005T061819373Z():
    assert [event.to_player_track_id for event in _run(3.2)] == [94]


def test_established_other_team_receiver_vetoes_pass_20261005T061819374Z():
    assert _run(2.4) == []
