"""Rule: a weak box sending a rolling ball back needs a later sighting there."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking


def _reason(later_boxes) -> str | None:
    ledger = ball_tracking.FrameLedger((frame, frame / 25) for frame in range(0, 40, 5))
    for frame, x, y in ((0, 1205.0, 579.0), (5, 1165.0, 593.0), (10, 1129.0, 605.0)):
        ledger.confirm(
            frame, x=x, y=y, confirming_module="01_confirm_yolo",
            evidence={}, confidence=0.5, box_diagonal=10.0,
        )
    point = ball_tracking.BallPoint(15, 0.6, 0.242, 1226.0, 588.0, box_diagonal=10.0)
    candidates = {15: [ball_tracking._BallCandidate(point, near_player_feet=True)]}
    for frame, x, y in later_boxes:
        later = ball_tracking.BallPoint(frame, frame / 25, 0.2, x, y, box_diagonal=10.0)
        candidates[frame] = [ball_tracking._BallCandidate(later, near_player_feet=False)]
    reason, _ = ball_tracking._candidate_rejection_reason(
        point,
        record={"source_frame": 15, "detections": []},
        candidates_by_frame=candidates,
        fps=25.0,
        frame_step=5,
        max_speed_pixels_per_second=1600.0,
        minimum_confidence=0.10,
        require_moving_neighbour=False,
        ledger=ledger,
    )
    return reason


def test_weak_box_reversing_momentum_without_later_sighting_20261015T151455748Z() -> None:
    """A steadily rolling ball sent back by a weak box must be seen there again.

    Three steady confirmed samples show the ball rolling left. A weak box far
    behind the run is another object (a boot, a sock) unless a later sighting
    is nearer to it than to the ball's last spot; a real touch that sends the
    ball back leaves such a sighting.
    """
    rejected = "reverses_confirmed_momentum_without_later_sighting"
    assert _reason([(30, 1055.0, 627.0)]) == rejected
    assert _reason([(20, 1240.0, 580.0)]) != rejected
