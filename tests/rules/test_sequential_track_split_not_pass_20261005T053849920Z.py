"""Rule: a same-team pass between two tracker fragments of one player is not a
pass. When the sender's track ends during the pass and the receiver's track
starts within 0.6 s at the same place (feet within 1.5 player heights), with
the two tracks never seen together, the player was split by the tracker (for
example while hidden behind an opponent) and kept the ball."""

from football_poc.engine.common import PredictedEvent
from football_poc.engine.pass_cleanup import suppress_sequential_track_split_passes


def _box(track, seconds, x):
    return {
        "track_id": track, "team": "black", "clip_seconds": seconds,
        "x1": x, "y1": 560, "x2": x + 25, "y2": 610,
    }


def _players(receiver_x):
    frames = {}
    for index, seconds in enumerate((34.0, 34.2, 34.4)):
        frames[index] = [_box(264, seconds, 1990 + 5 * index)]
    for index, seconds in enumerate((35.0, 35.2), start=10):
        frames[index] = [_box(727, seconds, receiver_x + 5 * (index - 10))]
    return frames


def _event():
    return PredictedEvent(
        "pass_candidate", 34.4, "black", 264, 727, 0.8, "transfer", 35.0
    )


def test_consecutive_fragments_of_one_player_not_a_pass_20261005T053849920Z():
    assert suppress_sequential_track_split_passes([_event()], _players(2025)) == []


def test_distant_receiver_track_start_is_a_pass_20261005T053849921Z():
    assert suppress_sequential_track_split_passes([_event()], _players(2300)) == [
        _event()
    ]
