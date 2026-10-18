"""A step-01 boot pick is withdrawn once the locked free ball's course shows it is off."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking

PLAYER = {
    "class_name": "person",
    "confidence": 0.8,
    "x1": 680.0,
    "y1": 600.0,
    "x2": 720.0,
    "y2": 700.0,
}


def _ledger(boot_frame: int, boot_x: float, boot_y: float) -> ball_tracking.FrameLedger:
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in range(5))
    # A locked chain: the free ball rolls slowly left along y = 500.
    for frame, x in ((2, 870.0), (3, 860.0), (4, 850.0)):
        ledger.confirm(
            frame,
            x=x,
            y=500.0,
            confirming_module=ball_tracking.LOCK_YOLO_CHAIN_MODULE,
            evidence={},
            confidence=0.6,
        )
    ledger.confirm(
        boot_frame,
        x=boot_x,
        y=boot_y,
        confirming_module=ball_tracking.CONFIRM_YOLO_MODULE,
        evidence={"near_player_feet": True},
        confidence=0.22,
    )
    return ledger


def _records() -> dict[int, dict]:
    return {frame: {"source_frame": frame, "detections": [PLAYER]} for frame in range(5)}


def test_boot_withdrawn_beside_locked_chain_20261018T174654870Z() -> None:
    ledger = _ledger(1, 700.0, 690.0)

    withdrawn = ball_tracking._withdraw_boots_off_free_ball_course(
        ledger, records_by_frame=_records(), frame_step=1
    )

    assert withdrawn == [1]
    assert ledger.confirmed(1) is None


def test_ball_on_course_kept_beside_locked_chain_20261018T174654871Z() -> None:
    ledger = _ledger(1, 880.0, 500.0)

    withdrawn = ball_tracking._withdraw_boots_off_free_ball_course(
        ledger, records_by_frame=_records(), frame_step=1
    )

    assert withdrawn == []
    assert ledger.confirmed(1) is not None
