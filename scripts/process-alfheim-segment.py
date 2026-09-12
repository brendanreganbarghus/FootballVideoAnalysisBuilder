from __future__ import annotations

import argparse
import hashlib
import json
import os
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

from football_poc.alfheim_profile import ALFHEIM_POSSESSION_ARGUMENTS
from football_poc.run_performance import build_performance_report


LIVE_DETECTOR_MODEL_SHA256 = (
    "9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef"
)
LIVE_DETECTOR_PROFILE = {
    "model": "yolo26n.pt",
    "confidence": 0.10,
    "image_size": 960,
    "stride": 5,
    "tile_width": 960,
    "tile_height": 960,
    "overlap": 0.2,
    "nms_iou": 0.5,
    "frame_batch_size": 2,
}


def resolve_live_detector_model(project_root: Path) -> Path:
    configured = os.environ.get("FOOTBALL_YOLO26_MODEL", "").strip()
    model = (
        Path(configured).expanduser().resolve()
        if configured
        else (project_root / "yolo26n.pt").resolve()
    )
    if not model.is_file():
        raise FileNotFoundError(
            "The pinned YOLO26 live detector is unavailable. Set "
            f"FOOTBALL_YOLO26_MODEL or provide {model}."
        )
    if model.name.lower() != LIVE_DETECTOR_PROFILE["model"]:
        raise ValueError(
            "Live processing requires yolo26n.pt, "
            f"got {model.name!r}."
        )
    model_hash = hashlib.sha256(model.read_bytes()).hexdigest()
    if model_hash != LIVE_DETECTOR_MODEL_SHA256:
        raise ValueError(
            "Live YOLO26 checkpoint hash does not match the approved model: "
            f"{model_hash}"
        )
    return model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build cached player tracking and events for an Alfheim segment."
    )
    parser.add_argument("segment", type=Path)
    parser.add_argument(
        "--events-only",
        action="store_true",
        help="Rerun possession and event inference from existing tracking data.",
    )
    parser.add_argument(
        "--artifact-namespace",
        choices=("live",),
        default=None,
        help="Write runtime artifacts below the selected segment namespace.",
    )
    args = parser.parse_args()
    segment = args.segment.resolve()
    prepared_manifest = segment / "manifest.json"
    run_root = (
        segment / args.artifact_namespace
        if args.artifact_namespace
        else segment
    )
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = run_root / "runtime-manifest.json"
    cache = run_root / "analytics-cache"
    results = run_root / "analytics-data"
    ball_tracks = cache / "ball-tracks.json"
    status_path = run_root / "analysis-status.json"
    workspace = PROJECT_ROOT
    model = resolve_live_detector_model(workspace)
    run_id = str(uuid4())
    started_at_utc = datetime.now(timezone.utc)

    prepared = json.loads(prepared_manifest.read_text(encoding="utf-8"))
    forbidden_manifest_fields = {
        "annotations",
        "ball_ground_truth",
        "events",
        "ground_truth",
        "labels",
        "manual_reference",
    }
    leaked_fields = sorted(forbidden_manifest_fields.intersection(prepared))
    if leaked_fields:
        raise ValueError(
            "Live raw-video manifest contains evaluation fields: "
            + ", ".join(leaked_fields)
        )
    video = Path(str(prepared.get("live_video", prepared["video"]))).resolve()
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open Alfheim clip: {video}")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    declared_start_frame = int(prepared.get("start_frame", 0))
    declared_end_frame = int(prepared.get("end_frame", frame_count))
    declared_frame_count = declared_end_frame - declared_start_frame
    declared_duration = float(
        prepared.get(
            "duration_seconds",
            declared_frame_count / fps if fps else 0.0,
        )
    )
    duration_frame_count = round(declared_duration * fps)
    if (
        declared_start_frame < 0
        or declared_frame_count <= 0
        or declared_end_frame > frame_count
        or declared_frame_count != duration_frame_count
    ):
        raise ValueError(
            "Prepared live media does not match its raw-only manifest: "
            f"video has {frame_count} frames at {fps:.3f} fps, while the "
            f"manifest declares frames {declared_start_frame}:"
            f"{declared_end_frame} ({declared_frame_count} frames) and "
            f"{declared_duration:.3f} seconds "
            f"({duration_frame_count} frames). Refusing to process an "
            "ambiguous segment."
        )
    manifest.write_text(
        json.dumps(
            {
                "dataset": "Simula Alfheim Camera Setting 2",
                "usage": "non-commercial research only",
                "video": str(video),
                "fps": fps,
                "start_frame": declared_start_frame,
                "end_frame": declared_end_frame,
                "starts_at_kickoff": False,
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
                    "mode": (
                        "cached_event_rebuild"
                        if args.events_only
                        else "cold_raw_video"
                    ),
                    "workflow": (
                        "live_iteration_25"
                        if args.artifact_namespace == "live"
                        else "legacy"
                    ),
                    "artifact_namespace": args.artifact_namespace,
                    "cache_reuse": args.events_only,
                    "prior_artifacts_used": args.events_only,
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
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(
            filter(
                None,
                (
                    str(LOCAL_SOURCE),
                    environment.get("PYTHONPATH"),
                ),
            )
        )
        subprocess.run(
            [sys.executable, *arguments],
            cwd=workspace,
            env=environment,
            check=True,
        )
        stage_seconds[stage] = round(time.perf_counter() - started, 3)

    pipeline_started = time.perf_counter()
    try:
        if args.events_only:
            required = [
                results / "player-tracks.json",
                ball_tracks,
            ]
            missing = [path.name for path in required if not path.is_file()]
            if missing:
                raise FileNotFoundError(
                    "Cannot rerun event logic without " + ", ".join(missing)
                )
            ball_track_payload = json.loads(ball_tracks.read_text(encoding="utf-8"))
            ball_track_source = json.dumps(
                ball_track_payload.get("source", {}),
                sort_keys=True,
            ).lower()
            if any(
                marker in ball_track_source
                for marker in ("bac", "ground_truth", "provider_coordinates")
            ):
                raise ValueError(
                    "Live event rebuild rejected BAC/evaluation-derived ball tracks"
                )
        else:
            for path in (
                cache / "detections.jsonl",
                cache / "detection-summary.json",
                ball_tracks,
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
                "Cold raw-video run: no prior detections, tracks, events, "
                "supplied ball labels, or review labels are being used.",
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
                "--confidence",
                str(LIVE_DETECTOR_PROFILE["confidence"]),
                "--image-size",
                str(LIVE_DETECTOR_PROFILE["image_size"]),
                "--stride",
                str(LIVE_DETECTOR_PROFILE["stride"]),
                "--tile-width",
                str(LIVE_DETECTOR_PROFILE["tile_width"]),
                "--tile-height",
                str(LIVE_DETECTOR_PROFILE["tile_height"]),
                "--overlap",
                str(LIVE_DETECTOR_PROFILE["overlap"]),
                "--nms-iou",
                str(LIVE_DETECTOR_PROFILE["nms_iou"]),
                "--frame-batch-size",
                str(LIVE_DETECTOR_PROFILE["frame_batch_size"]),
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
            status(
                "tracking",
                "Associating players and inferring teams from visible kits.",
            )
            run(
                "player_tracking",
                "-m",
                "football_poc.player_tracking_cli",
                str(manifest),
                "--player-cache",
                str(cache / "detections.jsonl"),
                "--ball-tracks",
                str(ball_tracks),
                "--output",
                str(results),
                "--confidence",
                "0.2",
                "--max-gap",
                "0.5",
                "--max-speed",
                "700",
                "--minimum-track-points",
                "3",
                "--team-profile",
                "red-black",
                "--goalkeeper-affiliations",
                str(
                    PROJECT_ROOT
                    / "benchmarks"
                    / "alfheim"
                    / "window-555"
                    / "goalkeeper-affiliations.json"
                ),
                "--no-video",
            )
        status(
            "events",
            "Inferring match state, possession, passes, and turnovers.",
        )
        run(
            "event_inference",
            "-m",
            "football_poc.possession_cli",
            str(manifest),
            "--player-tracks",
            str(results / "player-tracks.json"),
            "--ball-tracks",
            str(ball_tracks),
            "--output",
            str(results),
            *ALFHEIM_POSSESSION_ARGUMENTS,
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
        if not args.events_only:
            elapsed = time.perf_counter() - pipeline_started
            report = build_performance_report(
                run_id=run_id,
                video=video,
                manifest=manifest,
                model=model,
                source_duration_seconds=declared_duration,
                source_fps=fps,
                sampled_frames=(declared_frame_count + 4) // 5,
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
        else:
            status("ready", "Cached event logic rebuild completed.")
    except Exception as error:
        status("failed", str(error))
        raise


if __name__ == "__main__":
    main()
