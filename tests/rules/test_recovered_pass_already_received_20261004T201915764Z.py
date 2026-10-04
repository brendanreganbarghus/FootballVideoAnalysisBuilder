"""Rule: the pass-recovery step must not invent a teammate pass into a receiver
whose reception is already explained by an earlier event (pass or turnover)
into that same receiver inside the sender-to-receiver window. Without such an
event the recovered pass is still added."""

from football_poc.engine.common import PredictedEvent
from football_poc.possession import PossessionObservation, infer_pre_release_flight_receptions


def _obs(seconds, team, player_id, x, ratio):
    return PossessionObservation(
        source_frame=round(seconds * 25), clip_seconds=seconds, team=team,
        player_track_id=player_id, player_x=x, player_y=100, player_height=50,
        ball_x=x, ball_y=100, control_ratio=ratio,
    )


def _run(events):
    return infer_pre_release_flight_receptions(
        events,
        [_obs(0.0, "black", 1, 0, 0.8), _obs(1.0, "black", 2, 200, 0.2)],
        {
            0: [{"track_id": 1, "source_frame": 0, "clip_seconds": 0.0, "x": 0, "y": 0}],
            5: [{"track_id": 1, "source_frame": 5, "clip_seconds": 0.2, "x": 20, "y": 0}],
            25: [{"track_id": 1, "source_frame": 25, "clip_seconds": 1.0, "x": 200, "y": 0}],
        },
        co_visible_track_pairs=set(),
        minimum_speed_pixels_per_second=45,
        maximum_sender_lookback_seconds=3,
    )


OUTGOING = PredictedEvent("pass_candidate", 1.0, "black", 2, 3, 0.8, "outgoing", 2.0)


def test_turnover_into_receiver_blocks_recovered_pass_20261004T201915764Z():
    turnover = PredictedEvent("turnover_candidate", 0.1, "red", 9, 2, 0.7, "", 0.4)
    events = _run([turnover, OUTGOING])
    assert not [e for e in events if e.event_type == "pass_candidate" and e.to_player_track_id == 2]


def test_unexplained_reception_is_still_recovered_20261004T201915765Z():
    events = _run([OUTGOING])
    assert [(e.from_player_track_id, e.to_player_track_id) for e in events if e.to_player_track_id == 2] == [(1, 2)]