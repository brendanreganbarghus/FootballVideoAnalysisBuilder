"""Rule: an attention point that detours out and back is withdrawn across a
wider gap than a plain off-path point."""

from __future__ import annotations

from football_poc import ball_tracking

MODULE = "03_motion_and_optical_flow"


def _ledger(point_x: float, point_y: float):
    ledger = ball_tracking.FrameLedger(
        (frame, frame / 25) for frame in range(0, 16)
    )
    ledger.confirm(
        0, x=1129, y=605, confirming_module="01_confirm_yolo", evidence={},
        confidence=0.6, clip_seconds=0.0, box_diagonal=12,
    )
    ledger.confirm(
        5, x=point_x, y=point_y, confirming_module=MODULE, evidence={},
        confidence=0.85, clip_seconds=0.2, box_diagonal=12,
        point_evidence="raw_motion_attention_convergence_global_fallback",
    )
    ledger.confirm(
        15, x=1067, y=624, confirming_module="04_focused_multiscale",
        evidence={}, confidence=0.5, clip_seconds=0.6, box_diagonal=12,
    )
    return ledger


def test_attention_detour_withdrawn_wider_gap_20261017T140211452Z() -> None:
    """Neighbours 15 frames apart are beyond the plain 10-frame bracket.

    A point far from both of them (farther than they are from each other) is
    an out-and-back detour toward the players and is withdrawn. A point that
    is off the straight line but still between them is kept, because over a
    wider gap the ball may have curved.
    """
    detour = _ledger(1428, 493)
    ball_tracking._withdraw_off_path_attention_fallbacks(detour, MODULE)
    assert detour.confirmed(5) is None

    between = _ledger(1115, 662)
    ball_tracking._withdraw_off_path_attention_fallbacks(between, MODULE)
    assert between.confirmed(5) is not None
