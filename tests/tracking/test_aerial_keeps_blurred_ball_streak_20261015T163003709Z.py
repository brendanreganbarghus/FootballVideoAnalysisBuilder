"""Rule: the aerial search keeps a motion-blurred ball streak."""

from __future__ import annotations

import cv2
import numpy as np

import football_poc.ball_tracking as ball_tracking


def _frame(x: int) -> np.ndarray:
    image = np.full((300, 400), 40, dtype=np.uint8)
    # A fast ball blurred into a diagonal streak about 37 by 29 pixels.
    cv2.line(image, (x, 150), (x + 24, 166), 200, 12)
    return image


def test_aerial_keeps_blurred_ball_streak_20261015T163003709Z() -> None:
    """A fast ball in the air is a streak, not a dot.

    Its blob can exceed 400 pixels while staying inside the 40-pixel side
    limit; the aerial search must still see it.
    """
    previous, current, following = _frame(40), _frame(150), _frame(260)
    found = ball_tracking._aerial_frame_blobs(
        previous,
        current,
        following,
        5,
        lambda t: [],
        (0, 52.0, 158.0),
        (10, 272.0, 158.0),
        64.0,
    )
    assert any(abs(x - 162.0) < 5 and abs(y - 158.0) < 5 for x, y in found)
