from football_poc.possession import (
    PossessionObservation,
    PossessionSegment,
    infer_short_controlled_teammate_transfers,
)


def _obs(seconds, track, x, ball_x, control_ratio):
    return PossessionObservation(
        source_frame=round(seconds * 25),
        clip_seconds=seconds,
        team="black",
        player_track_id=track,
        player_x=x,
        player_y=100,
        player_height=50,
        ball_x=ball_x,
        ball_y=100,
        control_ratio=control_ratio,
    )


def _segments():
    sender = [
        _obs(1.0, 1, 100, 98, 0.3),
        _obs(1.2, 1, 100, 99, 0.3),
        _obs(1.4, 1, 100, 100, 0.4),
        _obs(1.6, 1, 104, 108, 0.9),
    ]
    receiver = [
        _obs(1.8, 2, 130, 120, 0.4),
        _obs(2.0, 2, 132, 128, 0.2),
        _obs(2.2, 2, 136, 134, 0.2),
    ]
    return [
        PossessionSegment(team="black", player_track_id=1, observations=sender),
        PossessionSegment(team="black", player_track_id=2, observations=receiver),
    ]


def _box(track, x):
    return {"track_id": track, "x1": x - 10, "x2": x + 10, "y1": 50, "y2": 100}


def _infer(receiver_x):
    reception_frame = round(1.8 * 25)
    players = {reception_frame: [_box(1, 125), _box(2, receiver_x)]}
    return infer_short_controlled_teammate_transfers(
        [],
        _segments(),
        co_visible_track_pairs=[frozenset((1, 2))],
        minimum_transfer_heights=0.5,
        players=players,
    )


def test_direct_handover_rejects_receiver_born_on_sender_20261004T213154205Z() -> None:
    assert _infer(receiver_x=135) == []


def test_direct_handover_keeps_separated_receiver_20261004T213154210Z() -> None:
    events = _infer(receiver_x=200)
    assert [(e.from_player_track_id, e.to_player_track_id) for e in events] == [(1, 2)]
