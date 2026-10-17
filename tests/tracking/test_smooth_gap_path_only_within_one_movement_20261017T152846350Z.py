"""Rule: a smooth path is joined across a gap only when one ball movement
can span it (five seconds, the same bound as one flight)."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking
from football_poc.ball_tracking import BallPoint


def _ball(source_frame: int, x: float, y: float) -> BallPoint:
    return BallPoint(
        source_frame=source_frame,
        clip_seconds=source_frame / 25.0,
        confidence=0.5,
        x=x,
        y=y,
        box_diagonal=14.0,
    )


def test_smooth_gap_path_only_within_one_movement_20261017T152846350Z() -> None:
    """A gap of up to five seconds may be joined by one smooth path. A
    5.8-second gap is not: the ball was passed, kicked or lofted in between,
    so weak boxes on kit or scenery that line up with the two ends by chance
    are not a path.
    """
    previous = _ball(615, 1129, 605)
    assert ball_tracking._gap_fits_one_movement(previous, _ball(715, 300, 1050), 25.0)
    assert ball_tracking._gap_fits_one_movement(previous, _ball(740, 300, 1050), 25.0)
    assert not ball_tracking._gap_fits_one_movement(
        previous, _ball(760, 297, 1057), 25.0
    )
