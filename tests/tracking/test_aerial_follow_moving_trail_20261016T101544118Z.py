"""Rule: a flight is followed through moving blobs only, and dead-end rivals do not count."""

from __future__ import annotations

from math import sin

import football_poc.ball_tracking as ball_tracking
from football_poc.ball import aerial

ANCHOR = (0, 1000.0, 600.0)
HIDDEN = range(21, 25)
STILL = (785.0, 594.0)


def _ball(t: int) -> tuple[float, float]:
    return 1000.0 - 10.0 * t + 1.5 * sin(t * 2.3), 600.0 - 0.3 * t + 0.002 * t * t


def _blobs(*, dead_end: bool = False) -> dict[int, list[tuple[float, float]]]:
    blobs = {}
    for t in range(1, 71):
        # Scenery beside the flight stays at one spot in every frame.
        points = [STILL]
        if t not in HIDDEN:
            points.append(_ball(t))
        if dead_end and t <= 22:
            # A second fast trail leaves the anchor and is soon lost.
            points.append((1000.0 + 6.0 * t, 600.0 + 7.0 * t))
        blobs[t] = points
    return blobs


def test_aerial_follow_moving_trail_20261016T101544118Z() -> None:
    """The follower ignores still blobs and crosses a dropout in a line.

    A ball in flight cannot sit at the same spot in nearby frames, so a blob
    that stays put is scenery or a player and is never followed. Across a
    dropout a curve bent by a noisy point overshoots, so a straight line
    through the recent points is the last prediction tried. A rival trail
    lost while the best flight is followed for at least another whole flight
    is clutter, and a rival apart from the best path for one frame only is
    the same ball.
    """
    moving = aerial._aerial_moving_blobs(_blobs())
    assert all(STILL not in points for points in moving.values())
    assert moving[30] == [_ball(30)]

    track = ball_tracking._aerial_one_sided_track(ANCHOR, _blobs(), 25.0)
    assert track is not None
    assert track[-1][0] == 70
    assert all((x, y) != STILL for _, x, y in track)

    track = ball_tracking._aerial_one_sided_track(ANCHOR, _blobs(dead_end=True), 25.0)
    assert track is not None
    assert track[-1][0] == 70

    best_at = {t: _ball(t) for t in range(1, 40)}
    blip = [(1, 1100.0, 600.0)] + [(t, *_ball(t)) for t in range(2, 40)]
    assert not aerial._aerial_runs_apart(best_at, blip, 30.0)
    apart = [(t, x, y + 40.0) for t, x, y in blip]
    assert aerial._aerial_runs_apart(best_at, apart, 30.0)
