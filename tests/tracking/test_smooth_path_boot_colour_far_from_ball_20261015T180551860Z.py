"""Rule: a smooth-path proposal at a player's feet is dropped when its colour is far from the ball."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking

PLAYER = {
    "detections": [
        {
            "class_name": "person",
            "confidence": 0.9,
            "x1": 90.0,
            "y1": 60.0,
            "x2": 110.0,
            "y2": 110.0,
        }
    ]
}


def _colour_check(far: bool):
    def matches(point) -> bool:
        return False

    matches.far_from_ball = lambda point: far
    return matches


def _run(*, smooth: bool, far: bool) -> ball_tracking.FrameLedgerEntry:
    ledger = ball_tracking.FrameLedger([(0, 0.0), (5, 0.2), (10, 0.4)])
    for frame, x in ((0, 98.0), (10, 102.0)):
        ledger.confirm(
            frame,
            x=x,
            y=100.0,
            confirming_module="01_confirm_yolo",
            evidence={"kind": "anchor"},
            confidence=0.8,
            box_diagonal=12,
        )
    proposal = ball_tracking.BallPoint(
        5, 0.2, 0.05, 100.0, 100.0, box_diagonal=12, smooth_gap_path=smooth
    )
    ball_tracking._confirm_track_points_from_module(
        ledger,
        "04_focused_multiscale",
        [ball_tracking.BallTrack(1, [proposal])],
        records_by_frame={5: PLAYER},
        fps=25.0,
        max_speed_pixels_per_second=1600.0,
        ball_colour_matches=_colour_check(far),
    )
    return ledger.entries[5]


def test_smooth_path_boot_colour_far_from_ball_20261015T180551860Z() -> None:
    """A smooth path does not excuse a boot whose colour is far from the ball.

    When one player passes and later receives the ball, the boot moves
    smoothly between the two sightings, so a weak redetection on the boot
    lies on a smooth path too. A smooth path still excuses a mildly off
    colour (motion blur), but a colour far outside the ball's learned range
    is the boot, and the proposal is dropped.
    """
    entry = _run(smooth=True, far=True)
    assert entry.status != "confirmed"
    assert entry.rejection_reasons[-1]["reason"] == "colour_far_from_ball"

    assert _run(smooth=True, far=False).status == "confirmed"

    entry = _run(smooth=False, far=False)
    assert entry.status != "confirmed"
    assert entry.rejection_reasons[-1]["reason"] == "colour_differs_from_ball"
