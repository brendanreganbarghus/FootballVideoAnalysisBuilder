"""Rule: a thin motion streak of a hard-kicked ball is kept as a flight blob."""

from __future__ import annotations

import numpy as np

import football_poc.ball_tracking as ball_tracking

MAX_STEP = 64.0
START = (0, 500.0, 300.0)
END = (20, 500.0, 300.0)


def _blobs_for(width: int, height: int) -> list[tuple[float, float]]:
    still = np.zeros((600, 1000), dtype=np.uint8)
    current = still.copy()
    current[300 : 300 + height, 500 : 500 + width] = 200
    return ball_tracking._aerial_frame_blobs(
        still, current, still, 10, lambda t: [], START, END, MAX_STEP
    )


def test_aerial_fast_streak_blob_20261015T174448804Z() -> None:
    """A fast ball smears into a long thin streak that is still the ball.

    A ball kicked hard moves further in one frame than the compact blob size
    allows, so its motion difference is longer than the 40 pixel side limit.
    Such a streak is kept when it is no longer than one frame of the fastest
    ball travel plus the ball itself, and thin. A patch of the same length but
    as thick as a moving player is still dropped, as is a thin line longer
    than any ball can travel in one frame.
    """
    assert len(_blobs_for(12, 12)) == 1
    assert len(_blobs_for(55, 10)) == 1
    assert _blobs_for(55, 30) == []
    assert _blobs_for(120, 6) == []
