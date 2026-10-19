"""Rule: motion blobs do not vouch for each other.

A motion point is only a moving blob, often a boot. A second motion blob
beside it is no better evidence, so each is judged against its nearest
neighbours from other modules. When trusted detector runs within the bracket
reach show the ball on a different path, and the blobs are off both that path
and their other-module neighbours' path, they are taken back.
"""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking

MOTION = "03_motion_and_optical_flow"


def _ledger(blobs: dict[int, tuple[float, float]]) -> ball_tracking.FrameLedger:
    ledger = ball_tracking.FrameLedger([(f, f / 25) for f in range(0, 80, 5)])
    # The ball rolls 10 px per frame. Detector runs at 0-10 and 45-75; a
    # flipbook point at 40 sits on the path just before the second run.
    for frame in (0, 5, 10, 45, 50, 55, 60, 65, 70, 75):
        ledger.confirm(
            frame, x=10.0 * frame, y=100.0,
            confirming_module=ball_tracking.CONFIRM_YOLO_MODULE,
            evidence={}, confidence=0.8, box_diagonal=8.0,
        )
    ledger.confirm(
        40, x=400.0, y=100.0, confirming_module="02_flipbook_time_machine",
        evidence={}, confidence=0.5, box_diagonal=8.0,
    )
    for frame, (x, y) in blobs.items():
        ledger.confirm(
            frame, x=x, y=y, confirming_module=MOTION,
            evidence={}, confidence=1.0, box_diagonal=8.0,
        )
    return ledger


def test_motion_blobs_do_not_vouch_for_each_other_20261019T034533009Z() -> None:
    """Two boots side by side, far above the rolling ball, are both taken back."""
    ledger = _ledger({15: (150.0, -150.0), 20: (200.0, -300.0)})
    ball_tracking._withdraw_off_path_motion_points(ledger, MOTION, 5)
    assert ledger.confirmed(15) is None
    assert ledger.confirmed(20) is None


def test_motion_blobs_on_ball_path_kept_20261019T034533010Z() -> None:
    """Motion blobs on the ball's path are the ball: they stay."""
    ledger = _ledger({15: (150.0, 102.0), 20: (200.0, 98.0)})
    ball_tracking._withdraw_off_path_motion_points(ledger, MOTION, 5)
    assert ledger.confirmed(15) is not None
    assert ledger.confirmed(20) is not None
