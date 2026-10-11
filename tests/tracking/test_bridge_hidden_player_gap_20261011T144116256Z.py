"""A player hidden behind another keeps his track."""

from football_poc.player_tracking import PlayerPoint, PlayerTrack, bridge_hidden_gaps

TEAMS = frozenset({"red", "black"})


def _point(frame: int, x: float, y: float, team: str) -> PlayerPoint:
    return PlayerPoint(
        source_frame=frame,
        clip_seconds=frame / 25,
        confidence=0.8,
        x1=x,
        y1=y,
        x2=x + 40,
        y2=y + 70,
        team=team,
    )


def _tracks(occluder_x: float) -> list[PlayerTrack]:
    runner = PlayerTrack(
        1, [_point(f, 1000 + f - 465, 650, "red") for f in (465, 470, 475)], "red"
    )
    reappears = PlayerTrack(
        2, [_point(f, 1000 + f - 465, 650, "red") for f in (490, 495, 500)], "red"
    )
    occluder = PlayerTrack(
        3,
        [_point(f, occluder_x + f - 465, 650, "black") for f in range(465, 505, 5)],
        "black",
    )
    return [runner, reappears, occluder]


def test_hidden_gap_is_joined_20261011T144116256Z() -> None:
    result = bridge_hidden_gaps(
        _tracks(occluder_x=1005), player_teams=TEAMS, max_speed_pixels_per_second=700
    )
    joined = next(track for track in result if track.track_id == 1)
    assert [track.track_id for track in result] == [1, 3]
    assert [point.source_frame for point in joined.points] == [
        465, 470, 475, 480, 485, 490, 495, 500,
    ]
    assert [point.hidden for point in joined.points[3:5]] == [True, True]
    assert all(point.team == "red" for point in joined.points)


def test_uncovered_gap_is_not_joined_20261011T144116257Z() -> None:
    result = bridge_hidden_gaps(
        _tracks(occluder_x=1600), player_teams=TEAMS, max_speed_pixels_per_second=700
    )
    assert [track.track_id for track in result] == [1, 2, 3]
