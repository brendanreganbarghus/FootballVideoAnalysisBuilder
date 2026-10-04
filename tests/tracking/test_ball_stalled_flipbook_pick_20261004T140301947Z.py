"""Timestamped rule test: a flipbook pick that stalls between fast steps."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking

FLIPBOOK = ball_tracking._withdraw_stalled_flipbook_picks.__globals__["FLIPBOOK_MODULE"]


def _ledger(positions: dict[int, tuple[float, str]]) -> ball_tracking.FrameLedger:
    ledger = ball_tracking.FrameLedger([(frame, frame / 25) for frame in positions])
    for frame, (x, module) in positions.items():
        ledger.confirm(
            frame,
            x=x,
            y=100.0,
            confirming_module=module,
            evidence={},
            confidence=0.2,
            clip_seconds=frame / 25,
            box_diagonal=6.0,
        )
    return ledger


def test_flipbook_pick_that_stalls_between_fast_steps_is_withdrawn_20261004T140301947Z() -> None:
    ledger = _ledger(
        {
            0: (100.0, "01_confirm_yolo"),
            5: (150.0, "01_confirm_yolo"),
            10: (155.0, FLIPBOOK),
            15: (215.0, "01_confirm_yolo"),
        }
    )
    ball_tracking._withdraw_stalled_flipbook_picks(ledger, 5)
    assert ledger.confirmed(10) is None
    assert ledger.confirmed(5) is not None


def test_flipbook_pick_on_a_slowing_ball_is_kept_20261004T140301947Z() -> None:
    ledger = _ledger(
        {
            0: (100.0, "01_confirm_yolo"),
            5: (150.0, "01_confirm_yolo"),
            10: (155.0, FLIPBOOK),
            15: (158.0, "01_confirm_yolo"),
        }
    )
    ball_tracking._withdraw_stalled_flipbook_picks(ledger, 5)
    assert ledger.confirmed(10) is not None


def test_other_modules_are_not_withdrawn_by_the_stall_rule_20261004T140301947Z() -> None:
    ledger = _ledger(
        {
            0: (100.0, "01_confirm_yolo"),
            5: (150.0, "01_confirm_yolo"),
            10: (155.0, "01_confirm_yolo"),
            15: (215.0, "01_confirm_yolo"),
        }
    )
    ball_tracking._withdraw_stalled_flipbook_picks(ledger, 5)
    assert ledger.confirmed(10) is not None
