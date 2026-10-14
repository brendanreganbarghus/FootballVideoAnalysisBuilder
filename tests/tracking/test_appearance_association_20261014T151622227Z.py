"""Rule: a player keeps looking like himself from one box to the next.

Each track keeps a running look of its boxes' kit colours. When the kit of a
box is too unclear to name a team, a box whose colours differ from the
track's look is still less likely to be that player, so a nearby box that
looks like him wins over a slightly nearer box that does not.
"""

from __future__ import annotations

from football_poc.player_tracking import (
    COLOR_VECTOR_NAMES,
    PlayerPoint,
    _associate_players,
)

DARK = {"shirt_dark": 0.6, "shorts_dark": 0.8}
WHITE = {"shirt_white": 0.6, "shorts_white": 0.8}
SPREAD = [0.1] * len(COLOR_VECTOR_NAMES)


def _point(frame, x, colors):
    return PlayerPoint(
        frame, frame / 25, 0.8, x - 20.0, 100.0, x + 20.0, 180.0,
        team="unknown", color_scores=dict(colors),
    )


def _points():
    points = [_point(frame, 100.0, DARK) for frame in (0, 5, 10)]
    # Next sample: a different-looking box right at his feet, his own look a
    # little further on.
    points += [_point(15, 102.0, WHITE), _point(15, 112.0, DARK)]
    return points


def _run(color_spread):
    tracks = _associate_players(
        _points(),
        max_gap_seconds=0.4,
        max_speed_pixels_per_second=100.0,
        player_teams=frozenset({"red", "black"}),
        color_spread=color_spread,
    )
    return next(track for track in tracks if track.track_id == 1)


def test_track_follows_its_own_look_20261014T151622227Z():
    assert _run(SPREAD).last.foot[0] == 112.0


def test_without_colours_the_nearest_box_wins_20261014T151622228Z():
    assert _run(None).last.foot[0] == 102.0
