from football_poc.possession import (
    PossessionObservation,
    build_possession_segments,
    infer_flight_transfer_events,
)


def _obs(seconds, track, x, control_ratio):
    return PossessionObservation(
        source_frame=round(seconds * 25),
        clip_seconds=seconds,
        team="black",
        player_track_id=track,
        player_x=x,
        player_y=100,
        player_height=50,
        ball_x=x,
        ball_y=100,
        control_ratio=control_ratio,
    )


def test_ball_rolling_straight_past_loose_teammate_is_not_received_20261004T185513602Z() -> None:
    segments = build_possession_segments(
        [
            _obs(0.6, 1, 100, 0.3),
            _obs(0.8, 1, 100, 0.2),
            _obs(1.0, 1, 100, 0.3),
            _obs(1.4, 2, 220, 1.15),
            _obs(1.6, 2, 270, 1.15),
            _obs(2.0, 3, 340, 0.2),
            _obs(2.2, 3, 350, 0.2),
            _obs(2.4, 3, 355, 0.2),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )
    path = [(1.0, 100), (1.2, 170), (1.4, 225), (1.6, 270), (1.8, 310), (2.0, 340), (2.2, 350), (2.4, 355)]
    balls = {
        round(t * 25): [
            {"track_id": 1, "clip_seconds": t, "source_frame": round(t * 25), "x": x, "y": 100}
        ]
        for t, x in path
    }

    events = infer_flight_transfer_events(
        balls,
        segments,
        minimum_speed_pixels_per_second=300,
        maximum_step_seconds=0.24,
        debounce_seconds=1.2,
        sender_lookback_seconds=1,
        receiver_window_seconds=2,
        minimum_receiver_observations=2,
    )

    assert [(e.from_player_track_id, e.to_player_track_id) for e in events] == [(1, 3)]
