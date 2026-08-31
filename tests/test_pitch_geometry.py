import json
from pathlib import Path

from football_poc.pitch_geometry import (
    PitchCalibration,
    detect_boundary_intervals,
    project_pitch_points,
    signed_pitch_distance,
)


BOUNDARY = ((0, 0), (100, 0), (100, 100), (0, 100))


def test_signed_pitch_distance_distinguishes_inside_and_outside() -> None:
    assert signed_pitch_distance((50, 50), BOUNDARY) > 0
    assert signed_pitch_distance((120, 50), BOUNDARY) < 0


def test_boundary_intervals_require_sustained_exit_and_report_resume() -> None:
    points = [
        {"frame": 0, "seconds": 0.0, "x": 50, "y": 50},
        {"frame": 1, "seconds": 0.2, "x": 120, "y": 50},
        {"frame": 2, "seconds": 0.4, "x": 125, "y": 50},
        {"frame": 3, "seconds": 0.6, "x": 130, "y": 50},
        {"frame": 4, "seconds": 0.8, "x": 50, "y": 50},
    ]

    intervals = detect_boundary_intervals(
        points,
        boundary=BOUNDARY,
        outside_margin_px=5,
        minimum_outside_seconds=0.4,
    )

    assert len(intervals) == 1
    assert intervals[0].start_seconds == 0.2
    assert intervals[0].end_seconds == 0.6
    assert intervals[0].resumed_seconds == 0.8


def test_homography_projects_image_corners_to_pitch_metres() -> None:
    calibration = PitchCalibration(
        image_points=((10, 10), (110, 10), (110, 60), (10, 60)),
        pitch_points_metres=((0, 0), (100, 0), (100, 50), (0, 50)),
        length_metres=100,
        width_metres=50,
    )

    projected = project_pitch_points([(60, 35)], calibration)

    assert round(projected[0][0], 3) == 50
    assert round(projected[0][1], 3) == 25


def test_alfheim_calibration_names_pitch_edges_and_goal_mouths() -> None:
    path = (
        Path(__file__).parents[1]
        / "benchmarks"
        / "alfheim"
        / "window-555"
        / "pitch-calibration.json"
    )
    features = json.loads(path.read_text(encoding="utf-8"))["features"]

    assert len(features["near_touchline"]) >= 4
    assert len(features["far_touchline"]) >= 4
    assert len(features["left_goal_line"]) >= 2
    assert len(features["right_goal_line"]) >= 2
    assert len(features["left_goal_mouth"]) == 4
    assert len(features["right_goal_mouth"]) == 4
