"""Rule: two overlapping boxes in different team kits are two players.

In a challenge a black and a red player stand together and their boxes
overlap. They are not one person seen twice, so neither track is pushed to
the back of the queue, and another player's track cannot take the black
player's own box on the next sample.
"""

from __future__ import annotations

from football_poc.player_tracking import PlayerPoint, _associate_players

TEAMS = frozenset({"red", "black"})


def _point(frame, x1, team):
    return PlayerPoint(frame, frame / 25, 0.8, x1, 100.0, x1 + 40.0, 180.0, team=team)


def test_overlapping_boxes_of_different_kits_keep_their_own_tracks_20261012T091941123Z():
    teammate = [_point(0, 300, "black"), _point(5, 300, "black")]
    opponent = [_point(0, 195, "red"), _point(5, 195, "red"), _point(10, 190, "red")]
    # The black player arrives into the challenge and overlaps the red box.
    challenger = [_point(5, 200, "black"), _point(10, 205, "black")]

    tracks = _associate_players(
        [*teammate, *opponent, *challenger],
        max_gap_seconds=0.5,
        max_speed_pixels_per_second=500.0,
        player_teams=TEAMS,
    )

    owner = next(track for track in tracks if challenger[1] in track.points)
    assert challenger[0] in owner.points
    assert not any(point in owner.points for point in teammate)
