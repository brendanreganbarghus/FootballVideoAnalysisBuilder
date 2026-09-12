from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SOURCE = PROJECT_ROOT / "src"
if str(LOCAL_SOURCE) not in sys.path:
    sys.path.insert(0, str(LOCAL_SOURCE))

from football_poc.alfheim_segments import resolve_alfheim_pano
from football_poc.artifact_store import resolve_detector_model
from football_poc.innovation_day_snapshot.alfheim_profile import (
    ALFHEIM_POSSESSION_ARGUMENTS,
)
from football_poc.innovation_day_snapshot.bac_ball_tracks import (
    write_bac_ball_tracks,
)


SNAPSHOT_ROOT = (
    PROJECT_ROOT / "src" / "football_poc" / "innovation_day_snapshot"
)
INNOVATION_DETECTOR_MODEL_SHA256 = (
    "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"
)
INNOVATION_DETECTOR_PROFILE = {
    "model": "yolo11n.pt",
    "confidence": 0.12,
    "image_size": 960,
    "stride": 5,
    "tile_width": 1484,
    "tile_height": None,
    "overlap": 0.1,
    "nms_iou": 0.5,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_innovation_detector_model(model: Path) -> None:
    model_hash = sha256(model)
    if (
        model.name.lower() != INNOVATION_DETECTOR_PROFILE["model"]
        or model_hash != INNOVATION_DETECTOR_MODEL_SHA256
    ):
        raise ValueError(
            "Innovation Day detection requires the frozen YOLO11n checkpoint "
            f"{INNOVATION_DETECTOR_MODEL_SHA256}; got {model.name} "
            f"with SHA-256 {model_hash}. Refusing detector configuration drift."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen Innovation Day engine with evaluation-only "
            "Alfheim BAC coordinates."
        )
    )
    parser.add_argument("segment", type=Path)
    parser.add_argument("--events-only", action="store_true")
    parser.add_argument(
        "--pano",
        type=Path,
        default=resolve_alfheim_pano(PROJECT_ROOT),
    )
    args = parser.parse_args()
    segment = args.segment.resolve()
    prepared_manifest = segment / "manifest.json"
    run_root = segment / "innovation"
    run_root.mkdir(parents=True, exist_ok=True)
    runtime_manifest = run_root / "runtime-manifest.json"
    cache = run_root / "analytics-cache"
    results = run_root / "analytics-data"
    status_path = run_root / "analysis-status.json"
    ball_tracks = cache / "ball-tracks.json"
    run_id = str(uuid4())

    prepared = json.loads(prepared_manifest.read_text(encoding="utf-8"))
    forbidden = {
        "actions",
        "action_counts",
        "annotations",
        "events",
        "labels",
        "ball_ground_truth",
        "manual_reference",
    }
    leaked = sorted(
        field
        for field in forbidden
        if prepared.get(field) not in (None, "", [], {})
    )
    if leaked:
        raise ValueError(
            "Shared prepared manifest contains evaluation inputs: "
            + ", ".join(leaked)
        )
    video = Path(
        str(prepared.get("innovation_video", prepared["video"]))
    ).resolve()
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open Alfheim clip: {video}")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    duration = float(prepared["duration_seconds"])
    declared_start_frame = int(prepared.get("start_frame", 0))
    declared_end_frame = int(prepared.get("end_frame", frame_count))
    declared_frame_count = declared_end_frame - declared_start_frame
    duration_frame_count = round(duration * fps)
    if (
        declared_start_frame < 0
        or declared_frame_count <= 0
        or declared_end_frame > frame_count
        or declared_frame_count != duration_frame_count
    ):
        raise ValueError(
            "Prepared Innovation media does not match its raw-only manifest: "
            f"video has {frame_count} frames at {fps:.3f} fps, while the "
            f"manifest declares frames {declared_start_frame}:"
            f"{declared_end_frame} ({declared_frame_count} frames) and "
            f"{duration:.3f} seconds ({duration_frame_count} frames). "
            "Refusing to build mixed-duration Innovation artifacts."
        )
    source_start = float(prepared["source_start_seconds"])
    runtime_manifest.write_text(
        json.dumps(
            {
                "dataset": "Simula Alfheim Camera Setting 2",
                "usage": "non-commercial research only",
                "video": str(video),
                "fps": fps,
                "start_frame": declared_start_frame,
                "end_frame": declared_end_frame,
                "start_seconds": source_start,
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
                    "mode": "innovation_day_bac_assisted",
                    "workflow": "innovation_day",
                    "artifact_namespace": "innovation",
                    "bac_assisted": True,
                    "raw_video_ball_inference": False,
                    "performance_benchmark_valid": False,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def run(*arguments: str) -> None:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(
            part
            for part in (
                str(LOCAL_SOURCE),
                environment.get("PYTHONPATH", ""),
            )
            if part
        )
        subprocess.run(
            [sys.executable, *arguments],
            cwd=PROJECT_ROOT,
            env=environment,
            check=True,
        )

    try:
        cache.mkdir(parents=True, exist_ok=True)
        results.mkdir(parents=True, exist_ok=True)
        status(
            "bac_ball_track",
            "BAC-assisted diagnostic: provider coordinates isolate the frozen "
            "downstream football engine.",
        )
        write_bac_ball_tracks(
            runtime_manifest=runtime_manifest,
            pano=args.pano.resolve(),
            output=ball_tracks,
            source_start_seconds=source_start,
            duration_seconds=duration,
        )
        if not args.events_only:
            model = resolve_detector_model(PROJECT_ROOT)
            validate_innovation_detector_model(model)
            run(
                "-m",
                "football_poc.innovation_day_detector",
                str(runtime_manifest),
                "--output",
                str(cache),
                "--model",
                str(model),
                "--confidence",
                str(INNOVATION_DETECTOR_PROFILE["confidence"]),
                "--image-size",
                str(INNOVATION_DETECTOR_PROFILE["image_size"]),
                "--stride",
                str(INNOVATION_DETECTOR_PROFILE["stride"]),
                "--tile-width",
                str(INNOVATION_DETECTOR_PROFILE["tile_width"]),
                "--overlap",
                str(INNOVATION_DETECTOR_PROFILE["overlap"]),
            )
            write_bac_ball_tracks(
                runtime_manifest=runtime_manifest,
                pano=args.pano.resolve(),
                output=ball_tracks,
                source_start_seconds=source_start,
                duration_seconds=duration,
            )
            run(
                "-m",
                "football_poc.innovation_day_snapshot.player_tracking_cli",
                str(runtime_manifest),
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
        status("events", "Running the frozen Innovation Day event engine.")
        boundary_events = run_root / "boundary-events.json"
        boundary_arguments = (
            ["--boundary-events", str(boundary_events)]
            if boundary_events.is_file()
            else []
        )
        run(
            "-m",
            "football_poc.innovation_day_snapshot.possession_cli",
            str(runtime_manifest),
            "--player-tracks",
            str(results / "player-tracks.json"),
            "--ball-tracks",
            str(ball_tracks),
            "--output",
            str(results),
            *ALFHEIM_POSSESSION_ARGUMENTS,
            *boundary_arguments,
        )
        run(
            "-m",
            "football_poc.chunk_simulator_cli",
            str(runtime_manifest),
            "--events",
            str(results / "predicted-events.json"),
            "--output",
            str(results / "chunk-simulation.json"),
        )
        provenance = {
            "schema_version": 1,
            "mode": "innovation_day_bac_assisted",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "runtime_manifest_sha256": sha256(runtime_manifest),
            "bac_source_root": str((args.pano.resolve() / "track")),
            "snapshot_manifest_sha256": sha256(
                SNAPSHOT_ROOT / "snapshot-manifest.json"
            ),
            "detector_profile": INNOVATION_DETECTOR_PROFILE,
            "detector_model_sha256": INNOVATION_DETECTOR_MODEL_SHA256,
            "detector_implementation_sha256": sha256(
                PROJECT_ROOT
                / "src"
                / "football_poc"
                / "innovation_day_detector.py"
            ),
            "ball_tracks_sha256": sha256(ball_tracks),
            "events_sha256": sha256(results / "predicted-events.json"),
            "performance_benchmark_valid": False,
        }
        (results / "run-provenance.json").write_text(
            json.dumps(provenance, indent=2) + "\n",
            encoding="utf-8",
        )
        status("ready", "BAC-assisted Innovation Day analysis is ready.")
    except Exception as error:
        status("failed", str(error))
        raise


if __name__ == "__main__":
    main()
