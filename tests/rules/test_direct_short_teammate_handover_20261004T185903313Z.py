from football_poc.possession import (
    PossessionObservation,
    PossessionSegment,
    PredictedEvent,
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


def test_direct_short_handover_between_distinct_teammates_is_pass_20261004T185903302Z() -> None:
    incoming = PredictedEvent(
        event_type="pass_candidate",
        clip_seconds=0.2,
        team="black",
        from_player_track_id=3,
        to_player_track_id=1,
        confidence=0.8,
        details="Earlier pass to the sender.",
        completion_seconds=1.2,
    )
    events = infer_short_controlled_teammate_transfers(
        [incoming],
        _segments(),
        co_visible_track_pairs=[frozenset((1, 2))],
        minimum_transfer_heights=0.5,
    )
    passes = [event for event in events if event.from_player_track_id == 1]
    assert len(passes) == 1
    assert passes[0].to_player_track_id == 2
    assert passes[0].clip_seconds == 1.4
    assert passes[0].completion_seconds == 1.8


def test_direct_short_handover_needs_distinct_co_visible_players_20261004T185903310Z() -> None:
    events = infer_short_controlled_teammate_transfers(
        [],
        _segments(),
        co_visible_track_pairs=[],
        minimum_transfer_heights=0.5,
    )
    assert events == []
