"""Ball elimination check: a lone leftover is found and the path is continuous."""

import cv2
import numpy as np

from football_poc import ball_elimination_check as E


def _calibration(width, height):
    return {
        "image_width": width,
        "image_height": height,
        "boundary": [[0, 0], [width, 0], [width, height], [0, height]],
        "features": {"halfway_line": [[width // 2, 0], [width // 2, height]]},
    }


def test_elimination_finds_lone_ball_and_follows_continuous_path_20261016T081500000Z():
    height, width = 200, 300
    image = np.zeros((height, width, 3), np.uint8)
    image[:] = (40, 140, 40)
    cv2.circle(image, (80, 100), 5, (255, 255, 255), -1)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    pitch = E.pitch_mask(_calibration(width, height), width, height)
    lines = np.zeros_like(pitch)
    found = E.open_pitch_candidates(image, pitch, [], lines, hsv)
    assert len(found) == 1
    assert abs(found[0][0] - 80) < 2 and abs(found[0][1] - 100) < 2

    band = E.calibrated_line_map(_calibration(width, height), width, height)
    assert band[100, width // 2] == 255 and band[100, 80] == 0

    # A fixed false spot and a moving ball: the continuous moving path wins
    # over hopping, and a frame with nothing is left as hidden.
    frames = [
        (0, [{"stage": "open_pitch", "x": 10.0, "y": 10.0}, {"stage": "on_line", "x": 500.0, "y": 500.0}]),
        (5, [{"stage": "open_pitch", "x": 60.0, "y": 10.0}]),
        (10, []),
        (15, [{"stage": "open_pitch", "x": 160.0, "y": 10.0}]),
    ]
    picks = E.choose_path(frames)
    assert [p and (p["x"], p["y"]) for p in picks] == [(10.0, 10.0), (60.0, 10.0), None, (160.0, 10.0)]
