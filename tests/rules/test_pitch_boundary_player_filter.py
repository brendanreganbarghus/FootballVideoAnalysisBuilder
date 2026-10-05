"""Event rules only see players whose feet are inside the calibrated pitch."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from football_poc.engine.common import (
    exclude_players_outside_pitch,
    scaled_pitch_boundary,
)

SQUARE_BOUNDARY = ((100.0, 100.0), (900.0, 100.0), (900.0, 900.0), (100.0, 900.0))


def _player(x1: float, y1: float, x2: float, y2: float) -> dict[str, object]:
    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "team": "black",
        "track_id": 1,
        "clip_seconds": 0.0,
    }


def test_player_with_feet_outside_pitch_is_excluded_20261005T095952716Z() -> None:
    outside = _player(40.0, 40.0, 60.0, 80.0)
    players = {0: [outside]}
    assert exclude_players_outside_pitch(players, SQUARE_BOUNDARY) == {0: []}


def test_player_with_feet_inside_pitch_is_kept_20261005T095952717Z() -> None:
    # Torso above the line but feet (centre-x, y2) inside: the player counts.
    inside = _player(480.0, 60.0, 520.0, 150.0)
    players = {0: [inside]}
    assert exclude_players_outside_pitch(players, SQUARE_BOUNDARY) == {
        0: [inside]
    }


def _write_video(path: Path, width: int, height: int) -> None:
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (width, height)
    )
    try:
        writer.write(np.zeros((height, width, 3), dtype=np.uint8))
    finally:
        writer.release()


def test_boundary_is_scaled_to_runtime_coordinate_space_20261005T095952718Z(
    tmp_path: Path,
) -> None:
    calibration = tmp_path / "pitch-calibration.json"
    calibration.write_text(
        json.dumps(
            {
                "image_width": 2000,
                "image_height": 1000,
                "boundary": [[200, 100], [1800, 100], [1800, 900], [200, 900]],
            }
        ),
        encoding="utf-8",
    )
    video = tmp_path / "segment.mp4"
    _write_video(video, 1000, 500)

    detected = tmp_path / "ball-detected.json"
    detected.write_text(json.dumps({"source_kind": "detected"}), encoding="utf-8")
    assert scaled_pitch_boundary(calibration, detected, video) == (
        (100.0, 50.0),
        (900.0, 50.0),
        (900.0, 450.0),
        (100.0, 450.0),
    )

    provider = tmp_path / "ball-bac.json"
    provider.write_text(
        json.dumps({"source_kind": "evaluation_only_provider_coordinates"}),
        encoding="utf-8",
    )
    assert scaled_pitch_boundary(calibration, provider, video) == (
        (200.0, 100.0),
        (1800.0, 100.0),
        (1800.0, 900.0),
        (200.0, 900.0),
    )
