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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SOURCE = PROJECT_ROOT / "src"
if str(LOCAL_SOURCE) not in sys.path:
    sys.path.insert(0, str(LOCAL_SOURCE))

from football_poc.artifact_store import resolve_detector_model
from football_poc.run_performance import build_performance_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one custom-camera sample through the cold pipeline."
    )
    parser.add_argument("segment", type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    args = parser.parse_args()
    segment = args.segment.resolve()
    source_root = args.source_root.resolve()
    camera = json.loads(
        (source_root / "camera.json").read_text(encoding="utf-8")
    )
    video = source_root / str(camera["video_filename"])
    calibration = source_root / "pitch-calibration.json"
    manifest = segment / "runtime-manifest.json"
    cache = segment / "analytics-cache"
    results = segment / "analytics-data"
    model = resolve_detector_model(PROJECT_ROOT)
    status_path = segment / "analysis-status.json"
    run_id = str(uuid4())
    started_at_utc = datetime.now(timezone.utc)
    segment.mkdir(parents=True, exist_ok=True)

    if not video.is_file():
        raise FileNotFoundError(f"Custom camera sample not found: {video}")
    if not calibration.is_file():
        raise FileNotFoundError("Custom camera pitch calibration is required")
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open custom camera sample: {video}")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    manifest.write_text(
        json.dumps(
            {
                "dataset": camera["camera_name"],
                "fps": fps,
                "video": str(video),
                "start_frame": 0,
                "end_frame": frame_count,
                "starts_at_kickoff": False,
                "camera_streams": [
                    {
                        "camera_id": camera["camera_id"],
                        "video": str(video),
                        "time_offset_seconds": 0,
                        "calibration": str(calibration),
                    }
                ],
                "primary_camera_id": camera["camera_id"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    def status(stage: str, message: str) -> None:
        status_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "stage": stage,
                    "message": message,
                    "mode": "cold_raw_video",
                    "cache_reuse": False,
                    "prior_artifacts_used": False,
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
        for path in (
            cache / "detections.jsonl",
            cache / "detection-summary.json",
            cache / "ball-tracks.json",
            results / "player-tracks.json",
            results / "match-initialization.json",
            results / "possession.json",
            results / "predicted-events.json",
            results / "chunk-simulation.json",
            results / "performance-report.json",
        ):
            path.unlink(missing_ok=True)
        status(
            "detecting",
            "Cold raw-video run: no prior detections, tracks, events, review "
            "labels, or provider annotations are being used.",
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
            "0.01",
            "--frame-batch-size",
            "4",
        )
        status("ball_track", "Building ball tracks from raw-video detections.")
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
        status("tracking", "Associating players and inferring visible kits.")
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
            "--team-profile",
            "auto",
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
        status("publishing", "Preparing live event chunks.")
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
        results.mkdir(parents=True, exist_ok=True)
        (results / "performance-report.json").write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )
        status(
            "ready",
            f"Cold raw-video run completed in {elapsed:.1f}s on the current CPU.",
        )
    except Exception as error:
        status("failed", str(error))
        raise


if __name__ == "__main__":
    main()
