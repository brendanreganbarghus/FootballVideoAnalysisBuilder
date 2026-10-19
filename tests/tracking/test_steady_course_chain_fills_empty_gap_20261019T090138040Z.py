"""Rule: weak boxes on one steady course fill a gap no other step could fill.

A fast ball blurs, so YOLO sees it only now and then, weakly, and each box on
its own fails the colour and contrast checks. Four or more boxes that line up
in one direction at a steady speed, inside a gap without any confirmed ball
and reachable from both confirmed ends of the gap, are the ball. Three boxes
can line up by chance in clutter, a course that turns sharply is not one
steady course, and a fixed spot never travels.
"""

from __future__ import annotations

import football_poc.ball as ball

FRAMES = range(0, 105, 5)
COURSE = {40: (900.0, 500.0), 55: (1200.0, 480.0), 60: (1300.0, 474.0),
          65: (1400.0, 468.0), 70: (1500.0, 462.0)}


def _box(x: float, y: float, confidence: float) -> dict:
    return {"class_name": "sports ball", "confidence": confidence,
            "x1": x - 10, "y1": y - 10, "x2": x + 10, "y2": y + 10}


def _confirmed_after(course: dict[int, tuple[float, float]]) -> dict[int, tuple]:
    records = {frame: {"detections": [_box(300.0, 300.0, 0.3)]} for frame in FRAMES}
    for frame, (x, y) in course.items():
        records[frame]["detections"].append(_box(x, y, 0.15))
    ledger = ball.FrameLedger((frame, frame / 25) for frame in FRAMES)
    for frame, x, y in ((0, 100.0, 500.0), (100, 2000.0, 400.0)):
        ledger.confirm(frame, x=x, y=y, confirming_module=ball.LOCK_YOLO_CHAIN_MODULE,
                       evidence={}, confidence=0.6)
    ball._confirm_steady_course_chains(
        ledger, records_by_frame=records, fps=25.0, frame_step=5,
        max_speed_pixels_per_second=1600.0,
    )
    return {
        frame: (round(entry.x), round(entry.y))
        for frame, entry in ledger.entries.items()
        if entry.status == "confirmed" and frame not in (0, 100)
    }


def test_steady_course_of_weak_boxes_fills_gap_20261019T090138040Z() -> None:
    assert _confirmed_after(COURSE) == {
        frame: (round(x), round(y)) for frame, (x, y) in COURSE.items()
    }


def test_three_boxes_are_not_enough_20261019T090138041Z() -> None:
    course = {frame: COURSE[frame] for frame in (55, 60, 65)}

    assert _confirmed_after(course) == {}


def test_sharp_turn_breaks_the_course_20261019T090138042Z() -> None:
    course = {55: (1200.0, 480.0), 60: (1300.0, 474.0), 65: (1300.0, 574.0),
              70: (1200.0, 574.0)}

    assert _confirmed_after(course) == {}
