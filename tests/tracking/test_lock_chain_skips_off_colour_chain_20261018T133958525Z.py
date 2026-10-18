"""Rule: a moving YOLO chain whose colour is clearly not the ball's is not locked.

A boot moves with a running player and leaves a long moving chain of YOLO
boxes, just like a rolling ball. The permanent chain lock reads the stand-out
colour of each chain box and skips a chain whose typical colour is clearly
outside the ball colour learned from this video's confident detections. Its
frames are left to the later steps. A ball-coloured chain is still locked.
"""

from __future__ import annotations

from pathlib import Path

from football_poc.ball_tracking import (
    LOCK_YOLO_CHAIN_MODULE,
    _ledger_from_records,
    _lock_moving_yolo_chains,
)


def _records():
    records = []
    for index in range(16):
        frame = index * 5
        x, y = 1000.0 + 20.0 * index, 900.0
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


def _locked_frames(monkeypatch, chroma):
    namespace = _lock_moving_yolo_chains.__globals__

    def fake_read(video, points_by_frame):
        return {
            (frame, float(point.x), float(point.y)): chroma
            for frame, points in points_by_frame.items()
            for point in points
        }

    monkeypatch.setitem(namespace, "_read_standout_chroma", fake_read)
    records = _records()
    ledger = _lock_moving_yolo_chains(
        _ledger_from_records(records),
        records_by_frame={record["source_frame"]: record for record in records},
        fps=25.0,
        frame_step=5,
        video=Path("unused.mp4"),
        ball_colour_range=(129.0, 157.0),
    )
    return [
        entry.source_frame
        for entry in ledger.confirmed_entries()
        if entry.confirming_module == LOCK_YOLO_CHAIN_MODULE
    ]


def test_off_colour_moving_chain_is_not_locked_20261018T133958525Z(monkeypatch):
    assert _locked_frames(monkeypatch, 110.0) == []


def test_ball_coloured_moving_chain_is_still_locked_20261018T133958553Z(monkeypatch):
    assert len(_locked_frames(monkeypatch, 159.0)) == 16
