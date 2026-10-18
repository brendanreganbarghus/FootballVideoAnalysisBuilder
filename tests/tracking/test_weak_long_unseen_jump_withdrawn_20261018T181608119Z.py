"""A weak lone 01 pick far beyond one top-speed sample from the locked ball is withdrawn."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking


def _setup(confidence: float):
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in range(6))
    # Locked ball rolling slowly; one top-speed sample is 1600 / 5 = 320 px.
    for frame, x in ((0, 520.0), (1, 510.0)):
        ledger.confirm(
            frame,
            x=x,
            y=500.0,
            confirming_module=ball_tracking.LOCK_YOLO_CHAIN_MODULE,
            evidence={},
            confidence=0.6,
        )
    ledger.confirm(
        4,
        x=1030.0,
        y=470.0,
        confirming_module=ball_tracking.CONFIRM_YOLO_MODULE,
        evidence={},
        confidence=confidence,
    )
    candidates = {
        4: [
            ball_tracking._BallCandidate(
                ball_tracking.BallPoint(4, 0.8, confidence, 1030.0, 470.0),
                near_player_feet=False,
            )
        ]
    }
    return ledger, candidates


def _withdraw(ledger, candidates):
    return ball_tracking._withdraw_weak_long_unseen_jumps(
        ledger,
        candidates_by_frame=candidates,
        fps=5,
        frame_step=1,
        max_speed_pixels_per_second=1600,
    )


def test_weak_long_unseen_jump_withdrawn_20261018T181608119Z() -> None:
    ledger, candidates = _setup(0.16)

    assert _withdraw(ledger, candidates) == [4]
    assert ledger.confirmed(4) is None


def test_strong_pick_after_jump_kept_20261018T181608120Z() -> None:
    ledger, candidates = _setup(0.6)

    assert _withdraw(ledger, candidates) == []
    assert ledger.confirmed(4) is not None
