from football_poc.possession import (
    PossessionObservation,
    build_possession_segments,
    collapse_transient_opponent_segments,
)


def _obs(seconds, team, track, x, control_ratio=0.3):
    return PossessionObservation(
        source_frame=round(seconds * 25),
        clip_seconds=seconds,
        team=team,
        player_track_id=track,
        player_x=x,
        player_y=100,
        player_height=50,
        ball_x=x,
        ball_y=100,
        control_ratio=control_ratio,
    )


def _collapse(observations):
    segments = build_possession_segments(
        observations, segment_gap_seconds=0.5, identity_switch_radius_heights=0
    )
    return collapse_transient_opponent_segments(
        segments, maximum_transient_seconds=1.2, maximum_occlusion_seconds=2.0
    )


def test_short_owner_return_cannot_erase_coherent_opponent_control_20261004T184854649Z() -> None:
    collapsed = _collapse(
        [
            _obs(16.0, "black", 12, 100),
            _obs(16.2, "black", 12, 102),
            _obs(16.4, "black", 12, 104),
            _obs(16.6, "red", 10, 106),
            _obs(16.8, "red", 10, 108),
            _obs(17.0, "red", 10, 110),
            _obs(17.2, "red", 10, 112),
            _obs(17.4, "black", 12, 114),
            _obs(17.6, "black", 12, 116),
            _obs(17.8, "red", 2, 160),
            _obs(18.0, "red", 2, 162),
            _obs(18.2, "red", 2, 164),
        ]
    )

    assert [segment.team for segment in collapsed][:2] == ["black", "red"]
    assert collapsed[1].player_track_id == 10


def test_same_track_team_label_flicker_is_owner_continuity_20261004T184854671Z() -> None:
    collapsed = _collapse(
        [
            _obs(46.6, "red", 8, 100),
            _obs(46.8, "red", 8, 102),
            _obs(47.0, "red", 8, 104),
            _obs(47.8, "black", 767, 106),
            _obs(48.0, "black", 767, 108),
            _obs(48.2, "black", 767, 110),
            _obs(48.4, "black", 767, 112),
            _obs(48.6, "red", 767, 114),
            _obs(48.8, "red", 767, 116),
        ]
    )

    assert [segment.team for segment in collapsed] == ["red", "red"]
