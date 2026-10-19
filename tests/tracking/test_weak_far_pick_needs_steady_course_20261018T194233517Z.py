"""Rule: a weak far pick needs a steady course, not just nearby clutter.

A weak 01 pick far from the locked ball can only be the ball if the ball
travelled there through unseen frames. Such a ball keeps its course between
sightings, so the pick must lie on the straight course between a detection
before it and one after it. Clutter boxes that merely lie within top speed of
each other, but wander about, do not keep the pick.
"""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking


def _candidate(frame: int, x: float, y: float, confidence: float):
    return ball_tracking._BallCandidate(
        ball_tracking.BallPoint(frame, frame / 5, confidence, x, y),
        near_player_feet=False,
    )


def _withdrawn(clutter: dict[int, tuple[float, float]]) -> list[int]:
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in range(9))
    for frame in (0, 1):
        ledger.confirm(
            frame,
            x=500.0,
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
        confidence=0.16,
    )
    candidates = {4: [_candidate(4, 1030.0, 470.0, 0.16)]}
    for frame, (x, y) in clutter.items():
        candidates[frame] = [_candidate(frame, x, y, 0.5)]
    return ball_tracking._withdraw_weak_long_unseen_jumps(
        ledger,
        candidates_by_frame=candidates,
        fps=5,
        frame_step=1,
        max_speed_pixels_per_second=1600,
    )


def test_wandering_clutter_does_not_keep_weak_far_pick_20261018T194233517Z() -> None:
    # Boxes within top speed of the pick, but the pick is far off their line.
    clutter = {3: (780.0, 550.0), 5: (720.0, 540.0), 6: (1000.0, 700.0)}

    assert _withdrawn(clutter) == [4]


def test_weak_far_pick_on_steady_course_is_kept_20261018T194233518Z() -> None:
    clutter = {3: (830.0, 480.0), 5: (1230.0, 460.0)}

    assert _withdrawn(clutter) == []
