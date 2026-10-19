"""Rule: a two-sided flight cannot rise higher than gravity allows.

A ball in the air for T seconds peaks at most g*T*T/8 metres above its ends.
The ball's own size at the ends turns metres into pixels. A short gap whose
fitted arc lifts the ball far above that is a player or noise, not a flight.
"""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking

START = (0, 1000.0, 600.0)
END = (15, 950.0, 602.0)
MODEL = (START, END, (0.0, 0.0, 0.0, 0.0))
BALL_PIXELS = 7.0


def _path(lift: float) -> dict[int, tuple[float, float]]:
    path = {}
    for t in range(1, 15):
        u = t / 15
        path[t] = (
            1000.0 - 50.0 * u,
            600.0 + 2.0 * u - 4.0 * lift * u * (1.0 - u),
        )
    return path


def test_aerial_lift_within_gravity_20261019T034533008Z() -> None:
    """0.6 s in the air lifts a 7 px ball at most ~14 px (x2 allowance)."""
    lift = ball_tracking._aerial_lift_within_gravity
    assert lift(START, END, MODEL, _path(10.0), BALL_PIXELS, 25.0)
    assert not lift(START, END, MODEL, _path(40.0), BALL_PIXELS, 25.0)

    # A long loft has the time to rise high.
    long_end = (65, 950.0, 602.0)
    long_model = (START, long_end, (0.0, 0.0, 0.0, 0.0))
    high = {t: (1000.0 - 50.0 * t / 65, 600.0 - 200.0) for t in range(20, 45)}
    assert lift(START, long_end, long_model, high, BALL_PIXELS, 25.0)

    # Without a known ball size the check stays out of the way.
    assert lift(START, END, MODEL, _path(40.0), 0.0, 25.0)
