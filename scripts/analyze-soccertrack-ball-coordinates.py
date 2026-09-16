from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SOURCE = PROJECT_ROOT / "src"
if str(LOCAL_SOURCE) not in sys.path:
    sys.path.insert(0, str(LOCAL_SOURCE))

from football_poc.ball_tracking import (  # noqa: E402
    SOCCERTRACK_DENSE_FLOW_PROFILE,
    SOCCERTRACK_KALMAN_REACQUISITION_PROFILE,
    SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE,
    SOCCERTRACK_PLAYER_ATTENTION_PROFILE,
    SOCCERTRACK_RAW_MOTION_PROFILE,
    track_cached_balls,
)


WINDOWS = (
    ("development-0-20", 0.0, 20.0),
    ("blind-20-40", 20.0, 40.0),
    ("blind-40-60", 40.0, 60.0),
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild SoccerTrack ball coordinates from a frozen detector "
            "cache and raw pixels. This is not a cold raw-video benchmark."
        )
    )
    parser.add_argument(
        "segment",
        type=Path,
        nargs="?",
        default=Path("benchmarks/soccertrack-117093-preview"),
    )
    args = parser.parse_args()
    segment = args.segment.resolve()
    manifest = segment / "manifest.json"
    cache = segment / "analytics-cache" / "detections.jsonl"
    output_root = segment / "analytics-cache"
    cache_hash_before = _sha256(cache)
    results: list[dict[str, object]] = []
    total_started = time.perf_counter()

    for name, start_seconds, end_seconds in WINDOWS:
        started = time.perf_counter()
        output = output_root / name
        track_cached_balls(
            manifest_path=manifest,
            cache_path=cache,
            output=output,
            analysis_start_seconds=start_seconds,
            analysis_end_seconds=end_seconds,
        )
        overlay = _render_raw_prediction_contact_sheet(
            video=Path(
                json.loads(manifest.read_text(encoding="utf-8"))["video"]
            ),
            cache=cache,
            tracks_path=output / "ball-tracks.json",
            output=output / "raw-prediction-contact-sheet.jpg",
            start_seconds=start_seconds,
            end_seconds=end_seconds,
        )
        results.append(
            _result(
                name,
                output,
                wall_seconds=time.perf_counter() - started,
                overlay_path=overlay,
            )
        )

    started = time.perf_counter()
    track_cached_balls(
        manifest_path=manifest,
        cache_path=cache,
        output=output_root,
    )
    overlay = _render_raw_prediction_contact_sheet(
        video=Path(json.loads(manifest.read_text(encoding="utf-8"))["video"]),
        cache=cache,
        tracks_path=output_root / "ball-tracks.json",
        output=output_root / "raw-prediction-contact-sheet.jpg",
    )
    results.append(
        _result(
            "full-minute",
            output_root,
            wall_seconds=time.perf_counter() - started,
            overlay_path=overlay,
        )
    )
    cache_hash_after = _sha256(cache)
    if cache_hash_after != cache_hash_before:
        raise RuntimeError("Frozen detector cache changed during ball analysis")

    report = {
        "benchmark_mode": "frozen_detector_cache_rebuild",
        "cold_raw_video_timing": False,
        "timing_label": (
            "Tracker/cache rebuild using frozen YOLO26 detections plus raw "
            "video pixels; YOLO inference is excluded."
        ),
        "detector_cache_sha256": cache_hash_after,
        "raw_motion_parameter_profile": SOCCERTRACK_RAW_MOTION_PROFILE,
        "micro_crop_verification_parameter_profile": (
            SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE
        ),
        "player_attention_parameter_profile": (
            SOCCERTRACK_PLAYER_ATTENTION_PROFILE
        ),
        "kalman_reacquisition_parameter_profile": (
            SOCCERTRACK_KALMAN_REACQUISITION_PROFILE
        ),
        "dense_optical_flow_parameter_profile": (
            SOCCERTRACK_DENSE_FLOW_PROFILE
        ),
        "sample_stride_frames": 5,
        "windows": results,
        "total_wall_seconds": round(time.perf_counter() - total_started, 3),
    }
    report_path = output_root / "ball-coordinate-cache-rebuild-report.json"
    report_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Ball coordinate report written to {report_path}")


def _result(
    name: str,
    output: Path,
    *,
    wall_seconds: float,
    overlay_path: Path | None = None,
) -> dict[str, object]:
    summary = json.loads(
        (output / "ball-tracking-summary.json").read_text(encoding="utf-8")
    )
    return {
        "name": name,
        "analysis_window": summary["analysis_window"],
        "processed_frames": summary["processed_frames"],
        "detector_backed_points": summary["observed_track_points"],
        "temporally_supported_points": (
            summary["temporally_supported_track_points"]
        ),
        "raw_motion_contributions": summary["raw_motion_proposals"]["accepted"],
        "raw_motion_verification": {
            "generated_by_mode": summary["raw_motion_proposals"][
                "generated_by_mode"
            ],
            "precision_rejections": summary["raw_motion_proposals"][
                "precision_rejections"
            ],
            "trajectory_margin": summary["raw_motion_proposals"][
                "trajectory_margin"
            ],
        },
        "candidate_conflicts": summary["candidate_conflicts"],
        "player_attention_search_prior": summary[
            "player_attention_search_prior"
        ],
        "kalman_guided_reacquisition": summary[
            "kalman_guided_reacquisition"
        ],
        "dense_optical_flow": summary["dense_optical_flow"],
        "tracked_frames": summary["tracked_frames"],
        "tracked_frame_coverage": summary["tracked_frame_coverage"],
        "unsupported_interpolation_points": (
            summary["interpolated_track_points"]
        ),
        "cache_rebuild_wall_seconds": round(wall_seconds, 3),
        "raw_prediction_contact_sheet": (
            str(overlay_path) if overlay_path is not None else None
        ),
    }


def _render_raw_prediction_contact_sheet(
    *,
    video: Path,
    cache: Path,
    tracks_path: Path,
    output: Path,
    start_seconds: float | None = None,
    end_seconds: float | None = None,
) -> Path:
    records = [
        json.loads(line)
        for line in cache.read_text(encoding="utf-8").splitlines()[1:]
    ]
    records = [
        record
        for record in records
        if record.get("type") == "frame"
        and (
            start_seconds is None
            or start_seconds <= float(record["clip_seconds"]) < end_seconds
        )
    ]
    tracks = json.loads(tracks_path.read_text(encoding="utf-8"))
    points = {
        int(point["source_frame"]): point
        for track in tracks.get("tracks", [])
        for point in track.get("points", [])
    }
    columns = 10
    tile_width = 360
    tile_height = 112
    rows = (len(records) + columns - 1) // columns
    sheet = np.zeros(
        (rows * tile_height, columns * tile_width, 3),
        dtype=np.uint8,
    )
    required = {int(record["source_frame"]) for record in records}
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open contact-sheet video: {video}")
        tile_index = 0
        for source_frame in range(max(required) + 1):
            if source_frame not in required:
                if not capture.grab():
                    raise RuntimeError(
                        f"Could not skip contact-sheet frame {source_frame}"
                    )
                continue
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(
                    f"Could not read contact-sheet frame {source_frame}"
                )
            resized = cv2.resize(frame, (tile_width, tile_height))
            point = points.get(source_frame)
            label = f"f{source_frame}"
            if point is not None:
                scale_x = tile_width / frame.shape[1]
                scale_y = tile_height / frame.shape[0]
                center = (
                    round(float(point["x"]) * scale_x),
                    round(float(point["y"]) * scale_y),
                )
                cv2.circle(resized, center, 5, (0, 255, 255), 2)
                label += f" {point['source_attribution']}"
            else:
                label += " ABSTAIN"
            cv2.putText(
                resized,
                label,
                (4, 14),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            row, column = divmod(tile_index, columns)
            sheet[
                row * tile_height : (row + 1) * tile_height,
                column * tile_width : (column + 1) * tile_width,
            ] = resized
            tile_index += 1
    finally:
        capture.release()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), sheet):
        raise RuntimeError(f"Could not write contact sheet: {output}")
    return output


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
