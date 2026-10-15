"""Rule: a two-sided flight stays between its ends and on or above their line."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking

START = (0, 1000.0, 600.0)
END = (20, 1200.0, 640.0)


def _line(t: int) -> tuple[float, float]:
    u = t / 20
    return 1000.0 + 200.0 * u, 600.0 + 40.0 * u


def test_aerial_path_above_ground_line_20261015T182714217Z() -> None:
    """Height lifts the ball straight up in the image.

    A lofted ball, a ball kicked late along the ground and a flat pass are
    kept. A path that leaves the sideways span of the two ends, or sinks
    below their line, is a foot or shadow next to the ball and is refused.
    """
    lofted = {t: (_line(t)[0], _line(t)[1] - 80.0) for t in range(5, 16)}
    late_kick = {t: _line(max(0, 2 * t - 20)) for t in range(5, 16)}
    flat = {t: (_line(t)[0] + 6.0, _line(t)[1] + 6.0) for t in range(5, 16)}
    overshoot = {t: (_line(t)[0] + 90.0, _line(t)[1] - 10.0) for t in range(5, 16)}
    below = {t: (_line(t)[0], _line(t)[1] + 40.0) for t in range(5, 16)}
    for path in (lofted, late_kick, flat):
        assert ball_tracking._aerial_rises_above_ground_line(START, END, path)
    for path in (overshoot, below):
        assert not ball_tracking._aerial_rises_above_ground_line(START, END, path)
