"""Rule: a restart spot must be big enough to be a ball, not colour noise."""

from __future__ import annotations

import cv2
import numpy as np

import football_poc.ball_tracking as ball_tracking


def _blobs(spot_size: int, diagonal: float) -> list[tuple[float, float]]:
    corner = (100.0, 100.0)
    boundary = np.array([[0, 100], [100, 100], [100, 300], [0, 300]], dtype=np.float32)
    grass = np.full((81, 81, 3), (40, 120, 40), dtype=np.uint8)
    background = cv2.cvtColor(grass, cv2.COLOR_BGR2LAB).astype(np.float32)
    orange = np.array([[(20, 110, 235)]], dtype=np.uint8)
    orange_a = float(cv2.cvtColor(orange, cv2.COLOR_BGR2LAB)[0, 0, 1])
    image = grass.copy()
    image[34:34 + spot_size, 24:24 + spot_size] = orange[0, 0]
    return ball_tracking._restart_spot_blobs(
        image,
        background,
        origin=(60, 60),
        corner=corner,
        colour_range=(orange_a - 5.0, orange_a + 5.0),
        ball_diagonal=diagonal,
        boundary=boundary,
    )


def test_restart_spot_needs_a_tenth_of_ball_area_20261015T160129563Z() -> None:
    """A few ball-coloured pixels on a board edge are noise, not a placed ball.

    With the learned ball diagonal of 15 pixels a whole ball covers about 88
    pixels; a 2x2 speck that never moves must not become a corner restart
    (and with it a false out-of-play gap), while a 4x4 ball spot still does.
    """
    assert _blobs(2, 15.0) == []
    assert len(_blobs(4, 15.0)) == 1
