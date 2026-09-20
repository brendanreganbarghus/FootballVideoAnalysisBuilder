import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "export_local_video_review",
    ROOT / "scripts" / "export-local-video-review.py",
)
assert SPEC and SPEC.loader
EXPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORTER)


def test_exports_every_video_frame_with_exact_coverage(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    writer = cv2.VideoWriter(
        str(source),
        cv2.VideoWriter_fourcc(*"mp4v"),
        5,
        (80, 40),
    )
    assert writer.isOpened()
    for frame_index in range(12):
        writer.write(
            np.full(
                (40, 80, 3),
                frame_index * 20,
                dtype=np.uint8,
            )
        )
    writer.release()

    output_dir = tmp_path / "review"
    manifest_path = EXPORTER.export_video_review(
        video=source,
        output_dir=output_dir,
        frames_per_sheet=5,
        columns=5,
        tile_width=80,
        ball_coordinates={frame: (40.0, 20.0) for frame in range(12)},
        coordinate_size=(80, 40),
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["fps"] == 5.0
    assert manifest["declared_frame_count"] == 12
    assert manifest["decoded_frame_count"] == 12
    assert manifest["exported_frame_count"] == 12
    assert manifest["complete_coverage"] is True
    assert len(manifest["source_video_sha256"]) == 64
    assert manifest["ball_zoom_frame_count"] == 12
    assert [
        (
            sheet["first_frame"],
            sheet["last_frame"],
            sheet["frame_count"],
        )
        for sheet in manifest["sheets"]
    ] == [(0, 4, 5), (5, 9, 5), (10, 11, 2)]
    assert all((output_dir / sheet["file"]).is_file() for sheet in manifest["sheets"])
