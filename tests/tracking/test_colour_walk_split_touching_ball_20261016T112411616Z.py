"""Rule: a ball touching a ball-coloured region is split off it by one erosion."""

from __future__ import annotations

import cv2
import numpy as np

from football_poc.ball import colour_walk

ORANGE = (0, 120, 255)
GRASS = (40, 140, 40)
DIAGONAL = 16.0
RANGE = (140.0, 200.0)


def _image(*, joined: bool) -> np.ndarray:
    image = np.full((200, 200, 3), GRASS, dtype=np.uint8)
    cv2.rectangle(image, (60, 100), (110, 160), ORANGE, -1)
    cv2.circle(image, (130, 80), 6, ORANGE, -1)
    if joined:
        # A one-pixel edge (an arm or hand) joins the ball to the region.
        cv2.line(image, (110, 100), (125, 85), ORANGE, 1)
    return image


def test_colour_walk_split_touching_ball_20261016T112411616Z() -> None:
    """The ball and a large region of similar colour can touch through a thin
    edge, making one blob too large to be a ball. One erosion breaks the
    thin join and the ball-sized piece is still found; the large region and
    tiny scraps never count as the ball.
    """
    for joined in (False, True):
        blobs = colour_walk._colour_walk_blobs(
            _image(joined=joined), (100.0, 100.0), 90.0,
            colour_range=RANGE, ball_diagonal=DIAGONAL,
        )
        near = [b for b in blobs if abs(b[0] - 130) <= 2 and abs(b[1] - 80) <= 2]
        assert len(near) == 1, (joined, blobs)
        assert all(not (60 <= x <= 110 and 100 <= y <= 160) for x, y in blobs)
