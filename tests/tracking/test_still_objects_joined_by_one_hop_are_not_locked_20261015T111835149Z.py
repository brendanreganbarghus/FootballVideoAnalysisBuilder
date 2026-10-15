"""Rule: two still objects joined by one hop are not a locked moving ball.

The permanent chain lock accepts a long chain of YOLO boxes that travels a
clear distance. Two still objects a short hop apart (heads in a stand, cones)
can link into one chain whose ends are far apart. A ball travels over several
steps, so a chain whose travel is mostly one jump is not locked. A ball that
rolls steadily is still locked.
"""

from __future__ import annotations

from football_poc.ball_tracking import (
    LOCK_YOLO_CHAIN_MODULE,
    _ledger_from_records,
    _lock_moving_yolo_chains,
)


def _records(position_for):
    records = []
    for index in range(16):
        frame = index * 5
        x, y = position_for(index)
        records.append(
            {
                "source_frame": frame,
                "clip_seconds": frame / 25,
                "detections": [
                    {
                        "class_name": "sports ball",
                        "confidence": 0.3,
                        "x1": x - 7,
                        "y1": y - 7,
                        "x2": x + 7,
                        "y2": y + 7,
                    }
                ],
            }
        )
    return records


def _locked_frames(records):
    ledger = _lock_moving_yolo_chains(
        _ledger_from_records(records),
        records_by_frame={record["source_frame"]: record for record in records},
        fps=25.0,
        frame_step=5,
    )
    return [
        entry.source_frame
        for entry in ledger.confirmed_entries()
        if entry.confirming_module == LOCK_YOLO_CHAIN_MODULE
    ]


def test_still_objects_joined_by_one_hop_are_not_locked_20261015T111835149Z():
    records = _records(
        lambda index: (3706.0, 1364.0) if index < 6 else (3730.0, 1285.0)
    )

    assert _locked_frames(records) == []


def test_steadily_rolling_ball_is_still_locked_20261015T111835150Z():
    records = _records(lambda index: (1000.0 + 20.0 * index, 900.0))

    assert len(_locked_frames(records)) == 16
