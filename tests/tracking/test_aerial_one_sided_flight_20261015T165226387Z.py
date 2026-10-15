"""Rule: a straight motion trail leaving a sighting is followed as the flight."""

from __future__ import annotations

from math import sin

import football_poc.ball_tracking as ball_tracking

ANCHOR = (0, 1000.0, 600.0)


def _ball(t: int, dx: float = -10.0) -> tuple[float, float]:
    return 1000.0 + dx * t, 600.0 - 2.0 * t + 0.08 * t * t


def _blobs(frames: int = 60) -> dict[int, list[tuple[float, float]]]:
    blobs = {}
    for t in range(1, frames + 1):
        # A player's feet beside the sighting jitter about for the whole gap.
        feet = (1015.0 + 6.0 * sin(t * 1.7), 610.0 + 5.0 * sin(t * 2.3) + 0.3 * t)
        ball = _ball(t)
        blobs[t] = [feet] if t == 20 else [ball, feet]
        if t == 20:
            # The ball drops out for a frame beside a stray blob.
            x, y = ball
            blobs[t].append((x + 9.0, y + 1.0))
    return blobs


def test_aerial_one_sided_flight_20261015T165226387Z() -> None:
    """A kicked ball is followed from the sighting it leaves.

    A long lofted ball may land far from the next confirmed position, so no
    flight joins both ends of the gap. The module starts from a fast, near
    straight trail beside the confirmed end and follows it with a curve fitted
    to its recent points, so a stray blob during a dropout does not pull it
    off the ball. Jittering feet never form a straight seed, a trail shorter
    than a second is not accepted, and two diverging straight trails make the
    flight ambiguous.
    """
    track = ball_tracking._aerial_one_sided_track(ANCHOR, _blobs(), 25.0)
    assert track is not None
    assert (track[0][0], track[-1][0]) == (1, 60)
    at = {t: (x, y) for t, x, y in track}
    assert 20 not in at
    assert at[40] == _ball(40)

    short = {t: b for t, b in _blobs().items() if t <= 20}
    assert ball_tracking._aerial_one_sided_track(ANCHOR, short, 25.0) is None

    feet_only = {t: [b[0] if t == 20 else b[1]] for t, b in _blobs().items()}
    assert ball_tracking._aerial_one_sided_track(ANCHOR, feet_only, 25.0) is None

    rival = {
        t: [*b, _ball(t, dx=-4.0)] for t, b in _blobs().items()
    }
    assert ball_tracking._aerial_one_sided_track(ANCHOR, rival, 25.0) is None
