"""Rule: a ball box reaching past the side of a person box is beside the
player, not on the body."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking
from football_poc.ball_tracking import BallPoint

RECORD = {
    "detections": [
        {
            "class_name": "person",
            "confidence": 0.72,
            "x1": 262.0,
            "y1": 1040.0,
            "x2": 299.0,
            "y2": 1095.0,
        }
    ]
}


def _ball(x: float) -> BallPoint:
    return BallPoint(
        source_frame=760,
        clip_seconds=30.4,
        confidence=0.23,
        x=x,
        y=1057.0,
        box_diagonal=14.7,
    )


def test_ball_past_person_side_not_on_body_20261017T151834207Z() -> None:
    """A person box holds the whole body, hands included.

    A weak ball box whose centre is 2 px inside the box edge has about a third
    of its width outside the box, so it is beside the player and kept. The same
    box well inside the edge, at chest height, is on the body and dropped.
    """
    assert not ball_tracking._on_player_upper_body(_ball(297.0), RECORD)
    assert ball_tracking._on_player_upper_body(_ball(290.0), RECORD)
