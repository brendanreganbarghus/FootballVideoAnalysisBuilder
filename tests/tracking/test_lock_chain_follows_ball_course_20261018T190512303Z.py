"""Rule: a locked chain follows the ball's course, not the nearest weak box.

The permanent chain lock links each YOLO box to the nearest box one sample
earlier within a fixed speed limit. A rolling ball that travels a little
faster than that limit for one sample would lose the link, and a weak boot
box beside the chain's last position would take the chain over. A box on the
chain's constant-velocity course, within one and a half link limits of the
last box, is the same ball and links first. A weak last box that leaves the
chain's course is not locked; later steps decide that frame.
"""

from __future__ import annotations

from football_poc.ball_tracking import (
    LOCK_YOLO_CHAIN_MODULE,
    _ledger_from_records,
    _lock_moving_yolo_chains,
)


def _box(x: float, y: float, confidence: float) -> dict:
    return {
        "class_name": "sports ball",
        "confidence": confidence,
        "x1": x - 7,
        "y1": y - 7,
        "x2": x + 7,
        "y2": y + 7,
    }


def _locked(boxes_by_index: dict[int, list[dict]]) -> dict[int, tuple[float, float]]:
    records = [
        {"source_frame": index * 5, "clip_seconds": index / 5, "detections": boxes}
        for index, boxes in sorted(boxes_by_index.items())
    ]
    ledger = _lock_moving_yolo_chains(
        _ledger_from_records(records),
        records_by_frame={record["source_frame"]: record for record in records},
        fps=25.0,
        frame_step=5,
    )
    return {
        entry.source_frame // 5: (entry.x, entry.y)
        for entry in ledger.confirmed_entries()
        if entry.confirming_module == LOCK_YOLO_CHAIN_MODULE
    }


def test_lock_chain_follows_ball_course_20261018T190512303Z() -> None:
    # The ball rolls 50 px per sample (link limit 60), then 64 px for one
    # sample. A weak boot box sits 30 px from the ball's last position.
    boxes = {index: [_box(1000.0 - 50.0 * index, 900.0, 0.6)] for index in range(9)}
    boxes[9] = [_box(536.0, 900.0, 0.5), _box(595.0, 920.0, 0.12)]
    for index in range(10, 13):
        boxes[index] = [_box(536.0 - 50.0 * (index - 9), 900.0, 0.6)]

    locked = _locked(boxes)

    assert locked[9] == (536.0, 900.0)
    assert set(locked) == set(range(13))


def test_weak_tail_off_course_is_not_locked_20261018T190512304Z() -> None:
    boxes = {index: [_box(1000.0 - 40.0 * index, 900.0, 0.6)] for index in range(9)}
    # A weak box 49 px from the last ball box but 75 px off its course.
    boxes[9] = [_box(700.0, 855.0, 0.3)]

    locked = _locked(boxes)

    assert 9 not in locked
    assert set(locked) == set(range(9))
