import json
from pathlib import Path

import pytest

from football_poc.actions import Detection
from football_poc.benchmark import (
    BenchmarkManifest,
    class_aware_nms,
    horizontal_tiles,
)
from football_poc.cli import _normalized_class_name, _wanted_class_ids


def detection(
    class_name: str,
    confidence: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> Detection:
    return Detection(-1, class_name, confidence, x1, y1, x2, y2)


def test_horizontal_tiles_cover_panorama_with_overlap() -> None:
    tiles = horizontal_tiles(4096, 1080, tile_width=1280, overlap=0.2)

    assert [tile.x1 for tile in tiles] == [0, 1024, 2048, 2816]
    assert tiles[-1].x2 == 4096
    assert all(tile.y2 == 1080 for tile in tiles)


def test_nms_removes_same_class_overlap_only() -> None:
    kept = class_aware_nms(
        [
            detection("person", 0.9, 10, 10, 30, 50),
            detection("person", 0.7, 11, 11, 31, 51),
            detection("sports ball", 0.8, 11, 11, 31, 51),
        ]
    )

    assert [(item.class_name, item.confidence) for item in kept] == [
        ("person", 0.9),
        ("sports ball", 0.8),
    ]


def test_manifest_validates_and_loads_frame_range(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.touch()
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "video": str(video),
                "fps": 25,
                "start_frame": 100,
                "end_frame": 200,
                "action_counts": {"pass": 3},
                "actions": [],
            }
        ),
        encoding="utf-8",
    )

    manifest = BenchmarkManifest.load(path)

    assert manifest.source_frame_count == 100
    assert manifest.action_counts == {"pass": 3}


def test_manifest_rejects_invalid_frame_range(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.touch()
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "video": str(video),
                "fps": 25,
                "start_frame": 200,
                "end_frame": 100,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="frame range"):
        BenchmarkManifest.load(path)


def test_ball_only_model_class_is_selected() -> None:
    assert _wanted_class_ids({0: "ball"}) == [0]


def test_football_model_classes_are_normalized() -> None:
    names = {0: "ball", 1: "goalkeeper", 2: "player", 3: "referee"}
    assert _wanted_class_ids(names) == [0, 1, 2, 3]
    assert [_normalized_class_name(name) for name in names.values()] == [
        "sports ball",
        "person",
        "person",
        "person",
    ]
