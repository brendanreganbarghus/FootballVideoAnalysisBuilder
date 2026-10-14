"""Rule: a player hidden for up to 0.8 s still gets his own track back.

A dribbler's box is lost for a moment and his track jumps onto a teammate's
box. The dribbler restarts as a new track on his own path up to 0.8 s after
his last box (twice the tracker's gap allowance): that new track continues
him and the jumped tail goes to the teammate. A restart later than that is
too far from the loss to be linked.
"""

from __future__ import annotations

from football_poc.player_tracking import PlayerPoint, PlayerTrack, relink_swapped_tracks

TEAMS = frozenset({"red", "black"})


def _point(seconds, x):
    frame = round(seconds * 25)
    return PlayerPoint(frame, seconds, 0.8, x - 20.0, 100.0, x + 20.0, 180.0, team="red")


def _beds(restart_seconds):
    runner = PlayerTrack(1, [_point(0.0, 100), _point(0.2, 110), _point(0.4, 120),
                             _point(0.8, 400), _point(1.0, 402), _point(1.2, 404)],
                         team="red")
    teammate = PlayerTrack(2, [_point(0.2, 390), _point(0.4, 394), _point(0.8, 398)],
                           team="red")
    restart_x = 120 + 50 * (restart_seconds - 0.4)
    restart = PlayerTrack(3, [_point(restart_seconds, restart_x),
                              _point(restart_seconds + 0.2, restart_x + 10)], team="red")
    return [runner, teammate, restart]


def test_restart_08_seconds_later_is_relinked_20261014T152306613Z():
    tracks = relink_swapped_tracks(_beds(1.2), player_teams=TEAMS)

    runner = next(track for track in tracks if track.track_id == 1)
    teammate = next(track for track in tracks if track.track_id == 2)
    assert [point.foot[0] for point in runner.points] == [100, 110, 120, 160, 170]
    assert [point.foot[0] for point in teammate.points] == [390, 394, 400, 402, 404]


def test_restart_later_than_08_seconds_is_not_relinked_20261014T152306614Z():
    tracks = relink_swapped_tracks(_beds(1.4), player_teams=TEAMS)

    runner = next(track for track in tracks if track.track_id == 1)
    assert [point.foot[0] for point in runner.points] == [100, 110, 120, 400, 402, 404]
