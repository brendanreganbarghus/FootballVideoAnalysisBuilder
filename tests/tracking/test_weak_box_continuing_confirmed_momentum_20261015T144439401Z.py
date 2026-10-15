"""Rule: a weak box that continues steady confirmed motion is backed by it."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking


def _chain_ledger(frames) -> ball_tracking.FrameLedger:
    ledger = ball_tracking.FrameLedger((frame, frame / 25) for frame in frames)
    for frame, x, y, confidence in (
        (0, 1247.0, 566.0, 0.48),
        (5, 1205.0, 579.0, 0.73),
        (10, 1165.0, 593.0, 0.20),
    ):
        ledger.confirm(
            frame, x=x, y=y, confirming_module="01_confirm_yolo",
            evidence={}, confidence=confidence, box_diagonal=10.0,
        )
    return ledger


def _contrast_reason(x: float, y: float) -> str | None:
    ledger = _chain_ledger(range(0, 20, 5))
    point = ball_tracking.BallPoint(15, 0.6, 0.165, x, y, box_diagonal=10.0)
    reason, _ = ball_tracking._candidate_rejection_reason(
        point,
        record={"source_frame": 15, "detections": []},
        candidates_by_frame={15: [ball_tracking._BallCandidate(point, near_player_feet=False)]},
        fps=25.0,
        frame_step=5,
        max_speed_pixels_per_second=1600.0,
        minimum_confidence=0.10,
        require_moving_neighbour=False,
        ledger=ledger,
        stands_out_from_grass=lambda _point: False,
    )
    return reason


def _detour_survivor(steady_chain: bool):
    ledger = _chain_ledger(range(0, 35, 5))
    if not steady_chain:
        ledger.withdraw(0, "01_confirm_yolo", "test_without_momentum")
    for frame, x, y, confidence in (
        (15, 1129.0, 605.0, 0.165),
        (20, 1226.0, 588.0, 0.242),
        (25, 1060.0, 620.0, 0.15),
    ):
        ledger.confirm(
            frame, x=x, y=y, confirming_module="01_confirm_yolo",
            evidence={}, confidence=confidence, box_diagonal=10.0,
        )
    ball_tracking._withdraw_one_frame_detours(
        ledger, fps=25.0, frame_step=5, max_speed_pixels_per_second=1600.0,
    )
    return ledger.confirmed(20)


def test_weak_box_continuing_confirmed_momentum_20261015T144439401Z() -> None:
    """Three steady confirmed samples predict where the rolling ball goes next.

    A weak, low-contrast box on that predicted spot is not vetoed for lacking
    grass contrast (blur washes out a moving ball), while one off the path
    still is. In the detour check such a box is not a doubtful neighbour, so
    a stronger single box that leaves and returns to the path is a detour.
    """
    assert _contrast_reason(1129.0, 605.0) != "no_contrast_with_grass"
    assert _contrast_reason(1226.0, 588.0) == "no_contrast_with_grass"

    assert _detour_survivor(steady_chain=True) is None
    assert _detour_survivor(steady_chain=False) is not None
