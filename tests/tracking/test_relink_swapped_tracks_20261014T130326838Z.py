"""Rule: a track that jumped onto a teammate is given back to its own player.

A player's box is briefly lost. His track comes back after the missed sample
far off his own path, on a teammate whose track just ended there, while a new
same-team track starts right on his path. The new track continues the
player; the jumped tail continues the teammate. Without a new track on the
path, nothing is relinked.
"""

from __future__ import annotations

from football_poc.player_tracking import PlayerPoint, PlayerTrack, relink_swapped_tracks

TEAMS = frozenset({"red", "black"})


def _point(seconds, x):
    frame = round(seconds * 25)
    return PlayerPoint(frame, seconds, 0.8, x - 20.0, 100.0, x + 20.0, 180.0, team="red")


def _beds(with_restart):
    runner = PlayerTrack(1, [_point(0.0, 100), _point(0.2, 110), _point(0.4, 120),
                             _point(0.8, 400), _point(1.0, 405)], team="red")
    teammate = PlayerTrack(2, [_point(0.2, 390), _point(0.4, 393), _point(0.6, 396)],
                           team="red")
    tracks = [runner, teammate]
    if with_restart:
        tracks.append(PlayerTrack(3, [_point(0.8, 142), _point(1.0, 152)], team="red"))
    return tracks


def test_track_swapped_onto_teammate_is_relinked_20261014T130326838Z():
    tracks = relink_swapped_tracks(_beds(with_restart=True), player_teams=TEAMS)

    assert len(tracks) == 2
    runner = next(track for track in tracks if track.track_id == 1)
    teammate = next(track for track in tracks if track.track_id == 2)
    assert [point.foot[0] for point in runner.points] == [100, 110, 120, 142, 152]
    assert [point.foot[0] for point in teammate.points] == [390, 393, 396, 400, 405]


def test_no_relink_without_a_new_track_on_the_path_20261014T130326839Z():
    tracks = relink_swapped_tracks(_beds(with_restart=False), player_teams=TEAMS)

    runner = next(track for track in tracks if track.track_id == 1)
    assert [point.foot[0] for point in runner.points] == [100, 110, 120, 400, 405]
    assert len(tracks) == 2
