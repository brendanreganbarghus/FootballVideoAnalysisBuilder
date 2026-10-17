"""Rule: with a calibrated pitch outline, a ball candidate is kept when it is
on the pitch or just beyond a line, and dropped when it is well off the
pitch."""

from __future__ import annotations

import numpy as np

import football_poc.ball_tracking as ball_tracking
from football_poc.ball_tracking import BallPoint

HEIGHT = 1728
BOUNDARY = np.array(
    [[200, 500], [3600, 500], [3600, 1500], [200, 1500]], dtype=np.float32
)


def _ball(x: float, y: float) -> BallPoint:
    return BallPoint(
        source_frame=760,
        clip_seconds=30.4,
        confidence=0.23,
        x=x,
        y=y,
        box_diagonal=14.7,
    )


def test_ball_inside_calibrated_pitch_20261017T152846338Z() -> None:
    """The calibrated outline, not a fixed curve, decides where the pitch is.

    A ball near the bottom-left of the pitch is kept. A ball 20 px past the
    touchline is kept, because one that has just crossed is needed to see it
    go out. A ball 200 px off the pitch, in the stands, is dropped.
    """
    assert ball_tracking._inside_calibrated_pitch(_ball(300, 1450), BOUNDARY, HEIGHT)
    assert ball_tracking._inside_calibrated_pitch(_ball(180, 1000), BOUNDARY, HEIGHT)
    assert not ball_tracking._inside_calibrated_pitch(
        _ball(1500, 300), BOUNDARY, HEIGHT
    )
