from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import cv2

from football_poc.artifact_store import resolve_detector_model
from football_poc.run_performance import (
    build_cache_rebuild_performance_report,
    build_performance_report,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SOURCE = PROJECT_ROOT / "src"
if str(LOCAL_SOURCE) not in sys.path:
    sys.path.insert(0, str(LOCAL_SOURCE))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process one SoccerTrack segment from raw video."
    )
    parser.add_argument("segment", type=Path)
    parser.add_argument(
        "--cache-rebuild",
        action="store_true",
        help=(
            "Rebuild tracking and events from the frozen detector cache. This "
            "is diagnostic work, not a cold raw-video benchmark."
        ),
    )
    args = parser.parse_args()
    segment = args.segment.resolve()
    video = segment / "soccertrack-117093-1267-1327-panorama.mp4"
    calibration = segment / "pitch-calibration.json"
    manifest = segment / "manifest.json"
    cache = segment / "analytics-cache"
    results = segment / "analytics-data"
    model = (
        None
        if args.cache_rebuild
        else resolve_detector_model(PROJECT_ROOT)
    )
    status_path = segment / "analysis-status.json"
    run_id = str(uuid4())
    started_at_utc = datetime.now(timezone.utc)

    if not video.is_file():
        raise FileNotFoundError(f"SoccerTrack clip not found: {video}")
    if not calibration.is_file():
        raise FileNotFoundError("SoccerTrack pitch calibration is required")
    if model is not None:
        _require_yolo26_model(model)
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open SoccerTrack clip: {video}")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    payload = {
        "dataset": "SoccerTrack v2",
        "match_id": "117093",
        "half": 1,
        "fps": fps,
        "video": str(video),
        "start_seconds": 1267.04,
        "duration_seconds": frame_count / fps,
        "start_frame": 0,
        "end_frame": frame_count,
        "starts_at_kickoff": False,
        "camera_streams": [
            {
                "camera_id": "soccertrack-117093-panorama",
                "video": str(video),
                "time_offset_seconds": 0,
                "calibration": str(calibration),
            }
        ],
        "primary_camera_id": "soccertrack-117093-panorama",
    }
    if args.cache_rebuild:
        if not manifest.is_file():
            raise FileNotFoundError(
                "Cache rebuild requires the runtime manifest used to create "
                "the frozen detector cache"
            )
        if not (cache / "detections.jsonl").is_file():
            raise FileNotFoundError(
                "Cache rebuild requires frozen detections.jsonl"
            )
        _require_yolo26_model(_cached_detector_model(cache / "detections.jsonl"))
    else:
        manifest.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

    def status(stage: str, message: str) -> None:
        status_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "stage": stage,
                    "message": message,
                    "mode": (
                        "cache_rebuild"
                        if args.cache_rebuild
                        else "cold_raw_video"
                    ),
                    "cache_reuse": args.cache_rebuild,
                    "prior_artifacts_used": args.cache_rebuild,
                    "started_at_utc": started_at_utc.isoformat(),
                    "elapsed_seconds": round(
                        (
                            datetime.now(timezone.utc) - started_at_utc
                        ).total_seconds(),
                        3,
                    ),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    stage_seconds: dict[str, float] = {}

    def run(stage: str, *arguments: str) -> None:
        started = time.perf_counter()
        subprocess.run(
            [sys.executable, *arguments],
            cwd=PROJECT_ROOT,
            check=True,
        )
        stage_seconds[stage] = round(time.perf_counter() - started, 3)

    pipeline_started = time.perf_counter()
    try:
        if args.cache_rebuild:
            for path in (
                cache / "ball-tracks.json",
                cache / "ball-tracking-summary.json",
                results / "player-tracks.json",
                results / "player-tracking-summary.json",
                results / "match-initialization.json",
                results / "possession.json",
                results / "predicted-events.json",
                results / "match-state-events.json",
                results / "event-evaluation.json",
                results / "chunk-simulation.json",
                results / "cache-rebuild-performance-report.json",
            ):
                path.unlink(missing_ok=True)
            status(
                "ball_track",
                "Cache rebuild from frozen YOLO26 detections; no labels or "
                "prior tracking, possession, or events are being used.",
            )
        else:
            for path in (
                cache / "detections.jsonl",
                cache / "detection-summary.json",
                cache / "ball-tracks.json",
                cache / "ball-tracking-summary.json",
                results / "player-tracks.json",
                results / "player-tracking-summary.json",
                results / "match-initialization.json",
                results / "possession.json",
                results / "predicted-events.json",
                results / "match-state-events.json",
                results / "event-evaluation.json",
                results / "chunk-simulation.json",
                results / "performance-report.json",
                results / "cache-rebuild-performance-report.json",
            ):
                path.unlink(missing_ok=True)
            status(
                "detecting",
                "Cold raw-video run: no prior detections, tracks, events, "
                "review labels, or provider annotations are being used.",
            )
            run(
                "detection",
                "-m",
                "football_poc.benchmark_cli",
                str(manifest),
                "--output",
                str(cache),
                "--model",
                str(model),
                "--device",
                "cpu",
                "--stride",
                "5",
                "--image-size",
                "960",
                "--confidence",
                "0.10",
                "--tile-width",
                "960",
                "--tile-height",
                "960",
                "--overlap",
                "0.2",
                "--nms-iou",
                "0.5",
                "--frame-batch-size",
                "2",
            )
            status("ball_track", "Building conservative ball tracks.")
        run(
            "ball_tracking",
            "-m",
            "football_poc.ball_tracking_cli",
            str(manifest),
            "--cache",
            str(cache / "detections.jsonl"),
            "--output",
            str(cache),
        )
        status("tracking", "Associating players and classifying visible kits.")
        run(
            "player_tracking",
            "-m",
            "football_poc.player_tracking_cli",
            str(manifest),
            "--player-cache",
            str(cache / "detections.jsonl"),
            "--ball-tracks",
            str(cache / "ball-tracks.json"),
            "--output",
            str(results),
            "--no-video",
        )
        status("events", "Inferring possession, passes, turnovers, and shots.")
        run(
            "event_inference",
            "-m",
            "football_poc.possession_cli",
            str(manifest),
            "--player-tracks",
            str(results / "player-tracks.json"),
            "--ball-tracks",
            str(cache / "ball-tracks.json"),
            "--output",
            str(results),
        )
        status("publishing", "Preparing live event chunks and review video.")
        run(
            "chunk_publication",
            "-m",
            "football_poc.chunk_simulator_cli",
            str(manifest),
            "--events",
            str(results / "predicted-events.json"),
            "--output",
            str(results / "chunk-simulation.json"),
        )
        elapsed = time.perf_counter() - pipeline_started
        source_duration = frame_count / fps
        if args.cache_rebuild:
            report = build_cache_rebuild_performance_report(
                run_id=run_id,
                video=video,
                manifest=manifest,
                detection_cache=cache / "detections.jsonl",
                source_duration_seconds=source_duration,
                source_fps=fps,
                sampled_frames=(frame_count + 4) // 5,
                wall_time_seconds=elapsed,
                stage_seconds=stage_seconds,
            )
            (results / "cache-rebuild-performance-report.json").write_text(
                json.dumps(report, indent=2),
                encoding="utf-8",
            )
            status(
                "ready",
                f"Cache rebuild completed in {elapsed:.1f}s; this is not "
                "cold raw-video speed.",
            )
        else:
            assert model is not None
            report = build_performance_report(
                run_id=run_id,
                video=video,
                manifest=manifest,
                model=model,
                source_duration_seconds=source_duration,
                source_fps=fps,
                sampled_frames=(frame_count + 4) // 5,
                wall_time_seconds=elapsed,
                stage_seconds=stage_seconds,
            )
            (results / "performance-report.json").write_text(
                json.dumps(report, indent=2),
                encoding="utf-8",
            )
            status(
                "ready",
                f"Cold raw-video run completed in {elapsed:.1f}s on the "
                "current CPU.",
            )
    except Exception as error:
        status("failed", str(error))
        raise


def _cached_detector_model(cache_path: Path) -> Path:
    metadata_line = cache_path.read_text(encoding="utf-8").splitlines()[0]
    metadata = json.loads(metadata_line)
    model = Path(str(metadata.get("model", "")))
    if not model.name:
        raise ValueError("Frozen detection cache does not identify its model")
    return model


def _require_yolo26_model(model: Path) -> None:
    if not model.name.lower().startswith("yolo26"):
        raise ValueError(
            "SoccerTrack development processing requires the selected YOLO26 "
            f"detector, got {model.name!r}"
        )


if __name__ == "__main__":
    main()
