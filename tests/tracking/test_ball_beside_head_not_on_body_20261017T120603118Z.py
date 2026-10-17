"""Rule: a ball beyond a player shows beside the head, not on the body."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking
from football_poc.ball_tracking import BallPoint

PLAYER = {
    "class_name": "person",
    "confidence": 0.85,
    "x1": 288.0,
    "y1": 1011.0,
    "x2": 332.0,
    "y2": 1069.0,
}


def _ball(x: float, y: float) -> BallPoint:
    return BallPoint(
        source_frame=775,
        clip_seconds=31.0,
        confidence=0.11,
        x=x,
        y=y,
        box_diagonal=12.0,
    )


def test_ball_beside_head_not_on_body_20261017T120603118Z() -> None:
    """A weak ball box in the empty top corner of a person box is kept.

    Weak boxes on a player's upper body are kit or a head and are dropped. But
    above the shoulders a person fills only the middle of the box: a ball
    rolling on the grass beyond the player, further from the camera, appears
    in the top corner beside the head. That spot is not the player's body.
    """
    record = {"detections": [PLAYER]}
    beside_head = _ball(294.0, 1016.0)
    on_head = _ball(310.0, 1016.0)
    on_chest = _ball(294.0, 1030.0)

    assert ball_tracking._player_context_allows_ball(beside_head, record)
    assert not ball_tracking._player_context_allows_ball(on_head, record)
    assert not ball_tracking._player_context_allows_ball(on_chest, record)
