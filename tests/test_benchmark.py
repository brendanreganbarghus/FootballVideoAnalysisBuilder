import json
from pathlib import Path

import pytest

from football_poc.actions import Detection
from football_poc.benchmark import (
    BenchmarkManifest,
    _prepare_cache,
    class_aware_nms,
    grid_tiles,
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


def test_grid_tiles_cover_panorama_in_both_dimensions() -> None:
    tiles = grid_tiles(
        4450,
        2000,
        tile_width=1484,
        tile_height=1200,
        overlap=0.1,
    )

    assert {tile.x1 for tile in tiles} == {0, 1336, 2672, 2966}
    assert {tile.y1 for tile in tiles} == {0, 800}
    assert max(tile.x2 for tile in tiles) == 4450
    assert max(tile.y2 for tile in tiles) == 2000


def test_grid_tiles_preserve_horizontal_mode_without_tile_height() -> None:
    assert grid_tiles(
        4096,
        1080,
        tile_width=1280,
        tile_height=None,
        overlap=0.2,
    ) == horizontal_tiles(4096, 1080, tile_width=1280, overlap=0.2)


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
            }
        ),
        encoding="utf-8",
    )

    manifest = BenchmarkManifest.load(path)

    assert manifest.source_frame_count == 100
    assert manifest.primary_camera_id == "primary"
    assert manifest.camera_streams[0].video == video.resolve()


def test_manifest_rejects_nonempty_evaluation_inputs(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.touch()
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "video": str(video),
                "fps": 25,
                "start_frame": 0,
                "end_frame": 100,
                "actions": [{"label": "pass", "clip_seconds": 12.0}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="evaluation inputs"):
        BenchmarkManifest.load(path)


def test_manifest_loads_synchronized_camera_streams(tmp_path: Path) -> None:
    left_video = tmp_path / "left.mp4"
    right_video = tmp_path / "right.mp4"
    left_calibration = tmp_path / "left-calibration.json"
    right_calibration = tmp_path / "right-calibration.json"
    for path in (
        left_video,
        right_video,
        left_calibration,
        right_calibration,
    ):
        path.touch()
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "camera_streams": [
                    {
                        "camera_id": "sideline-left",
                        "video": str(left_video),
                        "time_offset_seconds": 0.0,
                        "calibration": str(left_calibration),
                    },
                    {
                        "camera_id": "sideline-right",
                        "video": str(right_video),
                        "time_offset_seconds": 0.12,
                        "calibration": str(right_calibration),
                    },
                ],
                "primary_camera_id": "sideline-right",
                "fps": 25,
                "start_frame": 0,
                "end_frame": 1500,
            }
        ),
        encoding="utf-8",
    )

    manifest = BenchmarkManifest.load(path)

    assert manifest.primary_camera_id == "sideline-right"
    assert manifest.video == right_video.resolve()
    assert [stream.camera_id for stream in manifest.camera_streams] == [
        "sideline-left",
        "sideline-right",
    ]
    assert manifest.camera_streams[1].time_offset_seconds == 0.12
    assert manifest.camera_streams[0].calibration == left_calibration.resolve()


def test_manifest_rejects_duplicate_camera_ids(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.touch()
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "camera_streams": [
                    {"camera_id": "sideline", "video": str(video)},
                    {"camera_id": "sideline", "video": str(video)},
                ],
                "fps": 25,
                "start_frame": 0,
                "end_frame": 100,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate benchmark camera_id"):
        BenchmarkManifest.load(path)


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


def test_detection_cache_is_fresh_unless_reuse_is_explicit(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "detections.jsonl"
    metadata = {"type": "metadata", "stride": 5}
    cache.write_text(
        "\n".join(
            [
                json.dumps(metadata),
                json.dumps({"type": "frame", "source_frame": 0}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    processed = _prepare_cache(cache, metadata, reuse_cache=False)

    assert processed == set()
    assert cache.read_text(encoding="utf-8") == json.dumps(metadata) + "\n"


def test_detection_cache_reuse_requires_matching_metadata(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "detections.jsonl"
    metadata = {"type": "metadata", "stride": 5}
    cache.write_text(
        "\n".join(
            [
                json.dumps(metadata),
                json.dumps({"type": "frame", "source_frame": 10}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert _prepare_cache(cache, metadata, reuse_cache=True) == {10}
