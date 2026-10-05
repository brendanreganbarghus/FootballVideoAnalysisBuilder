"""Rule: a pre-release flight reception is not inferred when the receiver
already controlled the ball after the sender's sample; that is the receiver
dribbling, and the sender sample is a proximity flicker."""

from football_poc.engine.common import PredictedEvent
from football_poc.engine.pass_recovery import infer_pre_release_flight_receptions
from rule_builders import observation


def _balls():
    return {
        frame: [
            {
                "track_id": 1,
                "source_frame": frame,
                "clip_seconds": frame / 25,
                "x": frame * 8,
                "y": 0,
            }
        ]
        for frame in range(0, 30, 5)
    }


def _events(receiver_between_ratio):
    outgoing = PredictedEvent(
        "pass_candidate", 1.0, "black", 2, 3, 0.8, "outgoing", 2.0
    )
    return infer_pre_release_flight_receptions(
        [outgoing],
        [
            observation(0.0, "black", 1, 0, 0, control_ratio=0.8),
            observation(0.4, "black", 2, 80, 80, control_ratio=receiver_between_ratio),
            observation(1.0, "black", 2, 200, 200, control_ratio=0.2),
        ],
        _balls(),
        co_visible_track_pairs={frozenset((1, 2))},
        minimum_speed_pixels_per_second=45,
        maximum_sender_lookback_seconds=3,
    )


def test_receiver_control_after_sender_blocks_reception_20261005T041341425Z():
    assert [event.from_player_track_id for event in _events(0.4)] == [2]


def test_receiver_weak_proximity_still_allows_reception_20261005T041341426Z():
    assert [event.from_player_track_id for event in _events(0.9)] == [1, 2]
