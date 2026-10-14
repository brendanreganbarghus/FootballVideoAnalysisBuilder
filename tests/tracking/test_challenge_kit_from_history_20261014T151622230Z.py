"""Rule: two players of different teams in a challenge are not one person.

When a red player's box overlaps a black player's box, the overlap is a
challenge, not one person seen twice, also when the red player's latest box
is too unclear to read: his track has clearly worn red in its recent boxes.
So his track is not marked as a duplicate and can follow him when he runs
off.
"""

from __future__ import annotations

from football_poc.player_tracking import PlayerPoint, _associate_players

TEAMS = frozenset({"red", "black"})


def _point(frame, x, team, confidence=0.8):
    return PlayerPoint(
        frame, frame / 25, confidence, x - 20.0, 100.0, x + 20.0, 180.0, team=team
    )


def _points(last_red_kit):
    points = []
    for frame in range(0, 30, 5):
        points += [_point(frame, 100.0, "red"), _point(frame, 130.0, "black")]
    # The challenge: his kit cannot be read, the opponent's box covers his.
    points += [_point(30, 100.0, last_red_kit, 0.5), _point(30, 112.0, "black")]
    # He runs off quickly.
    points += [_point(35, 20.0, "red"), _point(35, 112.0, "black")]
    return points


def _red_track(last_red_kit):
    tracks = _associate_players(
        _points(last_red_kit),
        max_gap_seconds=0.4,
        max_speed_pixels_per_second=500.0,
        player_teams=TEAMS,
    )
    return next(track for track in tracks if track.track_id == 1)


def test_unclear_kit_in_challenge_uses_track_history_20261014T151622230Z():
    red = _red_track("unknown")
    assert red.last.foot[0] == 20.0
    assert len(red.points) == 8


def test_clear_kit_in_challenge_keeps_following_20261014T151622231Z():
    assert _red_track("red").last.foot[0] == 20.0
