from football_poc.engine.completed_pass import infer_deceleration_transfer_events
from football_poc.possession import PossessionObservation, PossessionSegment


def _obs(seconds, track, ball_x):
    return PossessionObservation(
        source_frame=round(seconds * 25),
        clip_seconds=seconds,
        team="black",
        player_track_id=track,
        player_x=ball_x,
        player_y=100,
        player_height=50,
        ball_x=ball_x,
        ball_y=100,
        control_ratio=0.3,
    )


def _balls():
    xs = {1.0: 0, 1.2: 100, 1.4: 200, 1.6: 205, 1.8: 210, 2.0: 212, 2.2: 260, 2.4: 310}
    return {
        round(s * 25): [
            {"track_id": 1, "source_frame": round(s * 25), "clip_seconds": s, "x": x, "y": 100}
        ]
        for s, x in xs.items()
    }


def _infer(receiver_x):
    segments = [
        PossessionSegment(team="black", player_track_id=1, observations=[_obs(0.8, 1, 0), _obs(1.0, 1, 0)]),
        PossessionSegment(team="black", player_track_id=2, observations=[_obs(2.4, 2, 310), _obs(2.6, 2, 320)]),
    ]
    box = {"track_id": 3, "team": "black", "x1": receiver_x - 10, "x2": receiver_x + 10, "y1": 50, "y2": 100}
    return infer_deceleration_transfer_events(
        _balls(),
        segments,
        minimum_incoming_speed_pixels_per_second=45,
        maximum_outgoing_speed_ratio=0.3,
        sender_lookback_seconds=2.0,
        receiver_window_seconds=2.0,
        minimum_transfer_heights=0.5,
        players={35: [box], 30: [box]},
    )


def test_deceleration_needs_receiving_teammate_within_reach_20261005T010452729Z() -> None:
    assert _infer(receiver_x=600) == []


def test_deceleration_with_teammate_at_ball_is_reception_20261005T010452769Z() -> None:
    assert [e.completion_seconds for e in _infer(receiver_x=205)] == [1.4]
