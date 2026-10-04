"""Timestamped rule: camera configuration is converted to the image size it is compared with."""

from __future__ import annotations

import json
from pathlib import Path

from football_poc.goal_calibration import load_goal_faces
from football_poc.image_space import (
    ball_coordinate_size,
    scale_goalkeeper_affiliations,
)


def test_goalkeeper_region_scales_to_video_size_20261004T194306489Z() -> None:
    config = {
        "image_width": 4450,
        "image_height": 2000,
        "affiliations": [
            {"team": "black", "region": {"x_min": 890, "x_max": 1780, "y_min": 400, "y_max": 1000}}
        ],
    }
    region = scale_goalkeeper_affiliations(config, (2225.0, 1000.0))[0]["region"]
    assert region == {"x_min": 445.0, "x_max": 890.0, "y_min": 200.0, "y_max": 500.0}

    undeclared = {"affiliations": config["affiliations"]}
    assert scale_goalkeeper_affiliations(undeclared, (2225.0, 1000.0))[0]["region"]["x_max"] == 1780.0


def test_goal_faces_scale_to_ball_coordinate_size_20261004T194306490Z(tmp_path: Path) -> None:
    features = {
        "left_goal_mouth": [[100, 500], [100, 300], [300, 300], [300, 500]],
        "left_goal_line": [[50, 500], [350, 500]],
        "right_goal_mouth": [[3700, 500], [3700, 300], [3900, 300], [3900, 500]],
        "right_goal_line": [[3650, 500], [3950, 500]],
    }
    path = tmp_path / "pitch-calibration.json"
    path.write_text(
        json.dumps({"image_width": 4000, "image_height": 1000, "features": features}),
        encoding="utf-8",
    )
    full, _ = load_goal_faces(path)
    half, provenance = load_goal_faces(path, (2000.0, 500.0))
    assert provenance["coordinate_scale"] == [0.5, 0.5]
    for side in ("left", "right"):
        for (fx, fy), (hx, hy) in zip(full[side].polygon, half[side].polygon):
            assert (hx, hy) == (fx / 2, fy / 2)

    # Provider coordinates stay in configuration space; our own tracker uses the video size.
    provider = {"source_kind": "evaluation_only_provider_coordinates"}
    assert ball_coordinate_size(provider, (2000.0, 500.0)) is None
    assert ball_coordinate_size({}, (2000.0, 500.0)) == (2000.0, 500.0)
