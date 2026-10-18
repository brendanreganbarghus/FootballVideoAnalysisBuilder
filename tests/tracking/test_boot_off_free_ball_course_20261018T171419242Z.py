"""A weak box at a player's feet far off the free ball's course is a boot."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking

# Player standing at x 680..720, y 600..700 (80 px wide, 100 px tall); the
# feet zone covers the box's lower part and a little around it.
PLAYER = {
    "class_name": "person",
    "confidence": 0.8,
    "x1": 680.0,
    "y1": 600.0,
    "x2": 720.0,
    "y2": 700.0,
}


def _reason(candidate_x: float, candidate_y: float) -> str | None:
    frames = list(range(4))
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in frames)
    # The free ball rolls slowly left along y = 500.
    for frame, x in ((0, 880.0), (1, 870.0)):
        ledger.confirm(
            frame,
            x=x,
            y=500.0,
            confirming_module="test",
            evidence={},
            confidence=0.6,
        )
    point = ball_tracking.BallPoint(3, 3 / 5, 0.27, candidate_x, candidate_y)
    candidates = {
        3: [ball_tracking._BallCandidate(point, near_player_feet=True)],
    }
    reason, _ = ball_tracking._candidate_rejection_reason(
        point,
        record={"source_frame": 3, "detections": [PLAYER]},
        candidates_by_frame=candidates,
        fps=5,
        frame_step=1,
        max_speed_pixels_per_second=1600,
        minimum_confidence=0.1,
        require_moving_neighbour=False,
        ledger=ledger,
    )
    return reason


def test_boot_off_free_ball_course_20261018T171419242Z() -> None:
    """The boot sits ~230 px off the ball's course; the player is 100 px tall."""
    assert _reason(700.0, 690.0) == "boot_off_free_ball_course"


def test_ball_reaching_feet_on_its_course_20261018T171419243Z() -> None:
    """A ball arriving at the feet it is rolling towards is still the ball."""
    frames = list(range(4))
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in frames)
    for frame, x in ((0, 900.0), (1, 840.0)):
        ledger.confirm(
            frame,
            x=x,
            y=690.0,
            confirming_module="test",
            evidence={},
            confidence=0.6,
        )
    point = ball_tracking.BallPoint(3, 3 / 5, 0.27, 720.0, 690.0)
    reason, _ = ball_tracking._candidate_rejection_reason(
        point,
        record={"source_frame": 3, "detections": [PLAYER]},
        candidates_by_frame={
            3: [ball_tracking._BallCandidate(point, near_player_feet=True)]
        },
        fps=5,
        frame_step=1,
        max_speed_pixels_per_second=1600,
        minimum_confidence=0.1,
        require_moving_neighbour=False,
        ledger=ledger,
    )
    assert reason != "boot_off_free_ball_course"
