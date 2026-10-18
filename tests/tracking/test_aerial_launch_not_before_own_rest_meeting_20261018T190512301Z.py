"""Rule: a flight does not take off before its own track meets the rest spot.

Before a kick the ball rests at the launch spot, where small motion blobs
from the ball and the kicker's boots jitter around it. A curve that takes off
at the start of the gap can run through that jitter and so collect more
inliers than the flight that takes off where the flight track itself meets
the rest spot. The ball is still resting until that meeting time, so an
earlier take-off is not tried for that track.
"""

from __future__ import annotations

import math

import football_poc.ball_tracking as ball_tracking

REST_UNTIL = 6


def _gap():
    s = (0, 1000.0, 600.0)
    e = (25, 600.0, 600.0)
    blobs = {}
    for t in range(1, REST_UNTIL + 1):
        blobs[t] = [
            (1000.0 + 4.0 * math.cos(k * 2.1 + t), 600.0 + 4.0 * math.sin(k * 2.1 + t))
            for k in range(3)
        ]
    span = e[0] - REST_UNTIL
    for t in range(REST_UNTIL + 1, e[0]):
        u = (t - REST_UNTIL) / span
        blobs[t] = [(1000.0 - 400.0 * u, 600.0 - 160.0 * u * (1 - u))]
    return s, e, blobs


def test_aerial_launch_not_before_own_rest_meeting_20261018T190512301Z() -> None:
    s, e, blobs = _gap()

    best = ball_tracking._aerial_curve_path(s, e, blobs)

    assert best is not None
    _, model, _ = best
    assert model[0][0] == REST_UNTIL
    for t in range(1, REST_UNTIL + 1):
        assert ball_tracking._aerial_position(model, t) == (1000.0, 600.0)


def test_flight_without_rest_meeting_may_launch_at_gap_start_20261018T190512302Z() -> None:
    s = (0, 1000.0, 600.0)
    e = (25, 600.0, 600.0)
    blobs = {
        t: [(1000.0 - 400.0 * t / 25, 600.0 - 160.0 * (t / 25) * (1 - t / 25))]
        for t in range(2, 25)
    }

    best = ball_tracking._aerial_curve_path(s, e, blobs)

    assert best is not None
    assert best[1][0][0] in (0, 1)
