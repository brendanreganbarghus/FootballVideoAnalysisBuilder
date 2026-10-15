"""Rule: an unbroken motion track joining both confirmed ends is the flight."""

from __future__ import annotations

from math import pi, sin

import football_poc.ball_tracking as ball_tracking


def _flight(offset: float = 0.0) -> list[tuple[int, float, float]]:
    # A high flight warped by the lens: no simple curve fits it closely.
    points = []
    for t in range(1, 40):
        u = t / 40
        points.append((t, 1000.0 - 25.0 * t, 600.0 - 480.0 * sin(pi * u) ** 3 + offset))
    return points


def test_aerial_end_to_end_tracklet_20261015T163003708Z() -> None:
    """A track linked frame by frame from launch to landing is the ball.

    When a high flight does not follow the fitted curve, the module accepts
    one motion track that starts beside the left confirmed end and finishes
    beside the right one. Every frame takes its own measured blob. A second
    track joining the same ends makes the flight ambiguous and nothing is
    accepted.
    """
    s = (0, 1000.0, 600.0)
    e = (40, 0.0, 600.0)
    noise = {t: [(2000.0 + 3 * t, 900.0)] for t in range(1, 40)}
    blobs = {t: [(x, y), *noise[t]] for t, x, y in _flight()}

    assert ball_tracking._aerial_curve_path(s, e, blobs) is None
    best = ball_tracking._aerial_best_path(s, e, blobs)
    assert best is not None
    count, _, inliers = best
    assert count == 39
    assert inliers[20] == (500.0, 120.0)

    rival = {t: [*blobs[t], (x, y)] for t, x, y in _flight(offset=25.0)}
    assert ball_tracking._aerial_best_path(s, e, rival) is None
