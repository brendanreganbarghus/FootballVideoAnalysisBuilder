from football_poc.player_tracking import (
    PlayerTrack,
    PlayerPoint,
    _associate_players,
    _stabilize_track_team,
    apply_goalkeeper_affiliations,
    classify_color_scores,
    _jersey_crop,
)
import numpy as np


def point(frame: int, seconds: float, x: float) -> PlayerPoint:
    return PlayerPoint(frame, seconds, 0.9, x, 100, x + 20, 200)


def test_player_tracker_bridges_short_gap() -> None:
    tracks = _associate_players(
        [point(1, 0.0, 100), point(2, 0.08, 105), point(5, 0.32, 120)],
        max_gap_seconds=0.4,
        max_speed_pixels_per_second=500,
    )

    assert len(tracks) == 1
    assert len(tracks[0].points) == 3


def test_player_tracker_rejects_distant_detection() -> None:
    tracks = _associate_players(
        [point(1, 0.0, 100), point(2, 0.08, 1000)],
        max_gap_seconds=0.4,
        max_speed_pixels_per_second=500,
    )

    assert len(tracks) == 2


def test_color_scores_classify_main_kits_and_roles() -> None:
    assert classify_color_scores({"blue": 0.7, "white": 0.05}) == "blue"
    assert classify_color_scores({"blue": 0.05, "white": 0.7}) == "white"
    assert classify_color_scores({"warm": 0.7}) == "goalkeeper"
    assert classify_color_scores({"dark": 0.7}) == "official"
    assert (
        classify_color_scores({"blue": 0.5, "white": 0.35})
        == "unknown"
    )


def test_color_scores_classify_alfheim_kits() -> None:
    assert (
        classify_color_scores({"warm": 0.7}, team_profile="red-black")
        == "red"
    )
    assert (
        classify_color_scores({"dark": 0.7}, team_profile="red-black")
        == "black"
    )
    assert (
        classify_color_scores({"yellow": 0.7}, team_profile="red-black")
        == "official"
    )


def test_goalkeeper_affiliation_inherits_team() -> None:
    track = PlayerTrack(
        7,
        [PlayerPoint(1, 0.0, 0.9, 790, 850, 890, 1000)],
        team="unknown",
    )

    apply_goalkeeper_affiliations(
        [track],
        [
            {
                "team": "black",
                "eligible_teams": ["unknown"],
                "region": {
                    "x_min": 650,
                    "x_max": 1100,
                    "y_min": 800,
                    "y_max": 1150,
                },
            }
        ],
    )

    assert track.team == "black"
    assert track.role == "goalkeeper"
    assert track.points[0].team == "black"


def test_track_team_is_stable_across_all_points() -> None:
    track = PlayerTrack(
        9,
        [
            PlayerPoint(1, 0.0, 0.9, 100, 100, 120, 200, team="red"),
            PlayerPoint(2, 0.2, 0.9, 102, 100, 122, 200, team="black"),
            PlayerPoint(3, 0.4, 0.9, 104, 100, 124, 200, team="black"),
        ],
        team="black",
    )

    _stabilize_track_team(track, "black")

    assert track.team == "black"
    assert {item.team for item in track.points} == {"black"}


def test_jersey_crop_uses_upper_torso() -> None:
    frame = np.zeros((300, 300, 3), dtype=np.uint8)
    crop = _jersey_crop(
        frame, PlayerPoint(1, 0, 0.9, 100, 100, 200, 250)
    )

    assert crop is not None
    assert crop.shape[:2] == (69, 60)
