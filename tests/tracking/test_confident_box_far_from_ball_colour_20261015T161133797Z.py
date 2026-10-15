"""Rule: a confident box whose colour is far from the ball's is not the ball."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

import football_poc.ball_tracking as ball_tracking

GRASS = (40, 120, 40)
ORANGE = (0, 110, 255)
LIME = (40, 255, 170)


def _video(path: Path) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 25.0, (320, 240))
    for frame in range(8):
        image = np.full((240, 320, 3), GRASS, dtype=np.uint8)
        cv2.circle(image, (80, 120), 6, ORANGE, -1)
        if frame == 7:
            cv2.circle(image, (240, 120), 6, LIME, -1)
        writer.write(image)
    writer.release()
    return path


def _reason(point, colour) -> str | None:
    reason, _ = ball_tracking._candidate_rejection_reason(
        point,
        record={"source_frame": point.source_frame, "detections": []},
        candidates_by_frame={
            point.source_frame: [ball_tracking._BallCandidate(point, near_player_feet=True)]
        },
        fps=25.0,
        frame_step=1,
        max_speed_pixels_per_second=1600.0,
        minimum_confidence=0.10,
        require_moving_neighbour=False,
        ball_colour_matches=colour,
    )
    return reason


def test_confident_box_far_from_ball_colour_20261015T161133797Z(tmp_path: Path) -> None:
    """A brightly coloured boot can get a confident ball box.

    Its colour is then far outside the ball colour learned from the video's
    strong boxes, further than lighting and blur move a real ball, so the box
    is rejected whatever the detector confidence. A box with the ball's colour
    keeps being accepted.
    """
    video = _video(tmp_path / "clip.mp4")
    strong = [
        ball_tracking.BallPoint(frame, frame / 25, 0.8, 80.0, 120.0, box_diagonal=12.0)
        for frame in range(7)
    ]
    boot = ball_tracking.BallPoint(7, 7 / 25, 0.51, 240.0, 120.0, box_diagonal=12.0)
    ball = ball_tracking.BallPoint(7, 7 / 25, 0.51, 80.0, 120.0, box_diagonal=12.0)
    colour = ball_tracking._ball_colour_check(strong, [boot, ball], video)

    assert colour is not None
    assert _reason(boot, colour) == "colour_far_from_ball"
    assert _reason(ball, colour) != "colour_far_from_ball"
