from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np


def _format_timestamp(seconds: float) -> str:
    total_milliseconds = round(seconds * 1000)
    minutes, remainder = divmod(total_milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _render_tile(
    frame: np.ndarray,
    *,
    frame_index: int,
    fps: float,
    tile_width: int,
    ball_coordinate: tuple[float, float] | None = None,
    coordinate_size: tuple[int, int] | None = None,
    show_ball_zoom: bool = False,
) -> np.ndarray:
    source_height, source_width = frame.shape[:2]
    image_height = max(1, round(source_height * tile_width / source_width))
    resized = cv2.resize(
        frame,
        (tile_width, image_height),
        interpolation=cv2.INTER_AREA,
    )
    label_height = 24
    zoom_height = image_height if show_ball_zoom else 0
    tile = np.zeros(
        (image_height + label_height + zoom_height, tile_width, 3),
        dtype=np.uint8,
    )
    tile[label_height : label_height + image_height] = resized
    timestamp = _format_timestamp(frame_index / fps)
    cv2.putText(
        tile,
        f"f{frame_index:06d}  {timestamp}",
        (5, 17),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    if show_ball_zoom:
        if coordinate_size is None:
            raise ValueError(
                "coordinate_size is required when ball coordinates are supplied"
            )
        if ball_coordinate is None:
            cv2.putText(
                tile,
                "BAC coordinate unavailable",
                (8, label_height + image_height + zoom_height // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            return tile
        coordinate_width, coordinate_height = coordinate_size
        center_x = round(ball_coordinate[0] * source_width / coordinate_width)
        center_y = round(ball_coordinate[1] * source_height / coordinate_height)
        crop_width = min(source_width, max(64, round(source_width * 0.25)))
        crop_height = min(
            source_height,
            max(36, round(crop_width * source_height / source_width)),
        )
        x1 = max(0, min(source_width - crop_width, center_x - crop_width // 2))
        y1 = max(0, min(source_height - crop_height, center_y - crop_height // 2))
        crop = frame[y1 : y1 + crop_height, x1 : x1 + crop_width].copy()
        marker_x = center_x - x1
        marker_y = center_y - y1
        cv2.circle(crop, (marker_x, marker_y), 7, (0, 255, 255), 2)
        zoom = cv2.resize(
            crop,
            (tile_width, zoom_height),
            interpolation=cv2.INTER_CUBIC,
        )
        tile[label_height + image_height :] = zoom
    return tile


def export_video_review(
    *,
    video: Path,
    output_dir: Path,
    frames_per_sheet: int = 25,
    columns: int = 5,
    tile_width: int = 256,
    jpeg_quality: int = 88,
    ball_coordinates: dict[int, tuple[float, float]] | None = None,
    coordinate_size: tuple[int, int] | None = None,
) -> Path:
    if frames_per_sheet < 1:
        raise ValueError("frames_per_sheet must be at least 1")
    if columns < 1:
        raise ValueError("columns must be at least 1")
    if tile_width < 64:
        raise ValueError("tile_width must be at least 64")
    if not 1 <= jpeg_quality <= 100:
        raise ValueError("jpeg_quality must be between 1 and 100")
    if ball_coordinates is not None and coordinate_size is None:
        raise ValueError(
            "coordinate_size is required when ball_coordinates are supplied"
        )

    cv2.setNumThreads(1)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {video}")

    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if fps <= 0:
        capture.release()
        raise ValueError(f"Video reports an invalid frame rate: {fps}")

    declared_frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    source_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    source_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output_dir.mkdir(parents=True, exist_ok=True)
    sheets: list[dict[str, object]] = []
    pending_tiles: list[np.ndarray] = []
    pending_indices: list[int] = []
    decoded_frame_count = 0

    def write_sheet() -> None:
        if not pending_tiles:
            return
        rows = (len(pending_tiles) + columns - 1) // columns
        tile_height = pending_tiles[0].shape[0]
        sheet = np.zeros(
            (rows * tile_height, columns * tile_width, 3),
            dtype=np.uint8,
        )
        for tile_index, tile in enumerate(pending_tiles):
            row, column = divmod(tile_index, columns)
            y1 = row * tile_height
            x1 = column * tile_width
            sheet[y1 : y1 + tile_height, x1 : x1 + tile_width] = tile

        first_frame = pending_indices[0]
        last_frame = pending_indices[-1]
        filename = f"frames-{first_frame:06d}-{last_frame:06d}.jpg"
        path = output_dir / filename
        written = cv2.imwrite(
            str(path),
            sheet,
            [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality],
        )
        if not written:
            raise RuntimeError(f"Could not write frame sheet: {path}")
        sheets.append(
            {
                "file": filename,
                "first_frame": first_frame,
                "last_frame": last_frame,
                "frame_count": len(pending_indices),
                "start_seconds": first_frame / fps,
                "end_seconds_exclusive": (last_frame + 1) / fps,
            }
        )
        pending_tiles.clear()
        pending_indices.clear()

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frame_index = decoded_frame_count
            pending_tiles.append(
                _render_tile(
                    frame,
                    frame_index=frame_index,
                    fps=fps,
                    tile_width=tile_width,
                    ball_coordinate=(
                        ball_coordinates.get(frame_index)
                        if ball_coordinates is not None
                        else None
                    ),
                    coordinate_size=coordinate_size,
                    show_ball_zoom=ball_coordinates is not None,
                )
            )
            pending_indices.append(frame_index)
            decoded_frame_count += 1
            if len(pending_tiles) == frames_per_sheet:
                write_sheet()
        write_sheet()
    finally:
        capture.release()

    covered_frames = sum(int(sheet["frame_count"]) for sheet in sheets)
    if covered_frames != decoded_frame_count:
        raise RuntimeError(
            f"Frame coverage mismatch: decoded {decoded_frame_count}, "
            f"exported {covered_frames}"
        )
    if declared_frame_count > 0 and decoded_frame_count != declared_frame_count:
        raise RuntimeError(
            f"Video declared {declared_frame_count} frames but decoded "
            f"{decoded_frame_count}"
        )

    manifest = {
        "schema_version": 1,
        "source_video": str(video.resolve()),
        "source_video_sha256": _sha256(video),
        "fps": fps,
        "source_width": source_width,
        "source_height": source_height,
        "declared_frame_count": declared_frame_count,
        "decoded_frame_count": decoded_frame_count,
        "exported_frame_count": covered_frames,
        "complete_coverage": covered_frames == decoded_frame_count,
        "frames_per_sheet": frames_per_sheet,
        "columns": columns,
        "tile_width": tile_width,
        "ball_zoom_frame_count": (
            sum(
                1
                for frame_index in range(decoded_frame_count)
                if frame_index in ball_coordinates
            )
            if ball_coordinates is not None
            else 0
        ),
        "sheets": sheets,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export every local video frame into ordered timestamped sheets "
            "with an exact coverage manifest."
        )
    )
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--frames-per-sheet", type=int, default=25)
    parser.add_argument("--columns", type=int, default=5)
    parser.add_argument("--tile-width", type=int, default=256)
    parser.add_argument("--jpeg-quality", type=int, default=88)
    parser.add_argument(
        "--bac-pano",
        type=Path,
        help="Optional Alfheim pano root containing frozen BAC coordinates.",
    )
    parser.add_argument(
        "--source-start-seconds",
        type=float,
        help="Source-video offset required with --bac-pano.",
    )
    parser.add_argument("--coordinate-width", type=int, default=4450)
    parser.add_argument("--coordinate-height", type=int, default=2000)
    args = parser.parse_args()
    ball_coordinates = None
    coordinate_size = None
    if args.bac_pano is not None:
        if args.source_start_seconds is None:
            parser.error("--source-start-seconds is required with --bac-pano")
        source_root = Path(__file__).resolve().parents[1] / "src"
        if str(source_root) not in sys.path:
            sys.path.insert(0, str(source_root))
        from football_poc.innovation_day_snapshot.bac_ball_tracks import (
            load_alfheim_bac_coordinates,
        )

        capture = cv2.VideoCapture(str(args.video))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        capture.release()
        if frame_count < 1 or fps <= 0:
            parser.error("Could not read video duration for BAC coordinates")
        ball_coordinates = load_alfheim_bac_coordinates(
            args.bac_pano,
            source_start_seconds=args.source_start_seconds,
            duration_seconds=frame_count / fps,
            fps=round(fps),
        )
        coordinate_size = (args.coordinate_width, args.coordinate_height)

    manifest = export_video_review(
        video=args.video,
        output_dir=args.output_dir,
        frames_per_sheet=args.frames_per_sheet,
        columns=args.columns,
        tile_width=args.tile_width,
        jpeg_quality=args.jpeg_quality,
        ball_coordinates=ball_coordinates,
        coordinate_size=coordinate_size,
    )
    result = json.loads(manifest.read_text(encoding="utf-8"))
    print(
        f"Exported {result['exported_frame_count']} frames into "
        f"{len(result['sheets'])} sheets: {manifest.resolve()}"
    )


if __name__ == "__main__":
    main()
