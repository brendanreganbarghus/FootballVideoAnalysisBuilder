"""Rule: a fast flight is found from a line back to the kick, even in clutter."""

from __future__ import annotations

from math import sin

import football_poc.ball_tracking as ball_tracking

ANCHOR = (0, 1500.0, 1100.0)
KICK = 4


def _ball(t: int) -> tuple[float, float]:
    # Struck at frame 4 at about 60 px per frame, slowing and curving.
    u = t - KICK
    wobble = 4.0 * sin(t * 2.9)
    return 1500.0 + 60.0 * u - 0.6 * u * u + wobble, 1100.0 - 32.0 * u + 0.5 * u * u


def _blobs(ball=_ball) -> dict[int, list[tuple[float, float]]]:
    blobs = {}
    for t in range(1, 41):
        # Clutter at the kicker's feet never forms a long straight trail.
        feet = [
            (1490.0 + 15.0 * sin(t * 1.3 + k), 1110.0 + 12.0 * sin(t * 2.1 + k))
            for k in range(3)
        ]
        blobs[t] = feet + ([ball(t)] if t > KICK + 1 and t != 18 else [])
    return blobs


def test_aerial_kick_line_flight_20261016T083202437Z() -> None:
    """A lofted ball struck after resting at the anchor is followed.

    The ball can rest at the anchor before it is struck, and the kick is often
    lost in clutter at the player's feet, so no straight trail starts at the
    anchor. Two fast blobs whose line passes back through the anchor start the
    flight. A fast ball's streak wobbles a few pixels, so the catch radius
    grows with the ball's speed and the curve bends from four points. A fast
    trail whose line misses the anchor is not a flight from it.
    """
    track = ball_tracking._aerial_one_sided_track(ANCHOR, _blobs(), 25.0)
    assert track is not None
    assert track[0][0] <= KICK + 3
    assert track[-1][0] == 40
    at = {t: (x, y) for t, x, y in track}
    assert 18 not in at
    assert at[30] == _ball(30)

    def elsewhere(t: int) -> tuple[float, float]:
        x, y = _ball(t)
        return x, y + 200.0

    assert ball_tracking._aerial_one_sided_track(ANCHOR, _blobs(elsewhere), 25.0) is None
