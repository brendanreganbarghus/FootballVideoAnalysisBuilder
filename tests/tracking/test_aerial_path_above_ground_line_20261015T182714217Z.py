"""Rule: a two-sided flight must bend upwards away from its ground line."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking

START = (0, 1000.0, 600.0)
END = (20, 1200.0, 640.0)


def _line(t: int) -> tuple[float, float]:
    u = t / 20
    return 1000.0 + 200.0 * u, 600.0 + 40.0 * u


def test_aerial_path_above_ground_line_20261015T182714217Z() -> None:
    """A lofted ball is drawn above the line between launch and landing.

    A path that bends well away from that line sideways or downwards is a
    foot or shadow next to the ball, so it is refused. A path that stays
    close to the line, or rises above it, is kept.
    """
    lofted = {t: (_line(t)[0], _line(t)[1] - 80.0) for t in range(5, 16)}
    sideways = {t: (_line(t)[0] + 40.0, _line(t)[1] + 12.0) for t in range(5, 16)}
    flat = {t: (_line(t)[0] + 6.0, _line(t)[1] + 6.0) for t in range(5, 16)}
    assert ball_tracking._aerial_rises_above_ground_line(START, END, lofted)
    assert ball_tracking._aerial_rises_above_ground_line(START, END, flat)
    assert not ball_tracking._aerial_rises_above_ground_line(START, END, sideways)
