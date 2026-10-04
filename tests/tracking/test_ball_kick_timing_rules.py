"""Timestamped rule tests for kick timing inside straight-line gap fills."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

import football_poc.ball_tracking as ball_tracking

BALL_BGR = (40, 40, 220)
GRASS_BGR = (40, 140, 40)
DIAMETER = 6.0


def _ledger_with_kick() -> ball_tracking.FrameLedger:
    """Ball held at x=100 for frames 0-2, gap 3-4, then kicked fast."""
    ledger = ball_tracking.FrameLedger([(frame, frame / 25) for frame in range(7)])
    anchors = {0: 100.0, 1: 100.0, 2: 100.0, 5: 160.0, 6: 190.0}
    for frame, x in anchors.items():
        ledger.confirm(
            frame,
            x=x,
            y=100.0,
            confirming_module="01_confirm_yolo",
            evidence={},
            confidence=0.8,
            clip_seconds=frame / 25,
            box_diagonal=DIAMETER,
        )
    return ledger


def _frame_with_ball(x: float) -> np.ndarray:
    image = np.full((200, 300, 3), GRASS_BGR, dtype=np.uint8)
    cv2.circle(image, (round(x), 100), 3, BALL_BGR, -1)
    return image


def _run(monkeypatch: pytest.MonkeyPatch, images, records_by_frame=None):
    namespace = ball_tracking._confirm_time_machine_estimates.__globals__
    monkeypatch.setitem(
        namespace,
        "_read_sampled_color_frames",
        lambda video, frames: {frame: images[frame] for frame in frames},
    )
    chroma = ball_tracking._standout_chroma(
        _frame_with_ball(102.0), 102.0, 100.0, DIAMETER
    )
    ledger = _ledger_with_kick()
    return ball_tracking._confirm_time_machine_estimates(
        ledger,
        fps=25,
        frame_step=1,
        width=300,
        height=200,
        max_speed_pixels_per_second=4000,
        place_possible_regions=False,
        video=Path("unused.mp4"),
        colour_range=(chroma - 5, chroma + 5),
        records_by_frame=records_by_frame,
    )


def test_gap_fill_moves_to_ball_coloured_spot_before_kick_20261003T101500000Z(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty straight-line fill moves along the line to the held ball."""
    images = {3: _frame_with_ball(102.0), 4: _frame_with_ball(130.0)}

    ledger = _run(monkeypatch, images)

    held = ledger.confirmed(3)
    assert held.x == pytest.approx(102.0, abs=2.5)
    assert held.evidence["kick_timing_moved_from"] == [120.0, 100.0]
    assert ledger.confirmed(4).x == pytest.approx(140.0, abs=0.01)
    assert "kick_timing_moved_from" not in ledger.confirmed(4).evidence


def test_gap_fill_ignores_ball_coloured_upper_body_20261003T101500001Z(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ball-coloured spot on a player's upper body never moves the fill."""
    images = {3: _frame_with_ball(102.0), 4: _frame_with_ball(130.0)}
    person = {"class_name": "person", "x1": 90, "y1": 90, "x2": 110, "y2": 130}

    ledger = _run(
        monkeypatch,
        images,
        records_by_frame={3: {"source_frame": 3, "detections": [person]}},
    )

    assert ledger.confirmed(3).x == pytest.approx(120.0, abs=0.01)


def test_gap_fill_ignores_spot_needing_impossible_speed_20261003T101500002Z(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ball-coloured spot is ignored when reaching it needs a sudden burst."""
    images = {3: _frame_with_ball(150.0), 4: _frame_with_ball(130.0)}

    ledger = _run(monkeypatch, images)

    assert ledger.confirmed(3).x == pytest.approx(120.0, abs=0.01)
