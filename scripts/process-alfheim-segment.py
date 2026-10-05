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
from football_poc.alfheim_segments import resolve_alfheim_pano
from football_poc.artifact_store import (
    BALL_SOURCES,
    discover_artifact_root,
)
from football_poc.ball_provenance import validate_ball_provenance
from football_poc.bac_ball_tracks import write_bac_ball_tracks
from football_poc.engine_fingerprint import engine_fingerprint
from football_poc.run_performance import build_performance_report
from football_poc.shots_on_target import (
    EVIDENCE_FILE_NAME as SHOT_EVIDENCE_FILE_NAME,
    SUMMARY_FILE_NAME as SHOTS_SUMMARY_FILE_NAME,
)

# Both ball sources run the same YOLO26n detector for players; they differ
# only in where the ball coordinates come from.
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
# YOLO26n scores half-hidden players at 0.10-0.19; player tracking keeps every
# box the detector keeps so those players stay visible to the rules engine.
PLAYER_TRACKING_CONFIDENCE = LIVE_DETECTOR_PROFILE["confidence"]
BAC_SOURCE_KINDS = frozenset(
    {
        "evaluation_only_provider_coordinates",
        "reviewer_corrected_innovation_coordinates",
    }
)
FORBIDDEN_MANIFEST_FIELDS = frozenset(
    {
        "actions",
        "action_counts",
        "annotations",
        "ball_ground_truth",
        "events",
        "ground_truth",
        "labels",
        "manual_reference",
    }
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def alfheim_config_path(name: str) -> Path:
    local_path = PROJECT_ROOT / "benchmarks" / "alfheim" / "window-555" / name
    if local_path.is_file():
        return local_path
    artifact_root = discover_artifact_root()
    if artifact_root is not None:
        candidates = sorted(
            (artifact_root / "30-shared-baselines").glob(
                f"*/alfheim-config/{name}"
            )
        )
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise FileNotFoundError(
                f"Multiple shared {name} configurations found; "
                "select one explicitly."
            )
    raise FileNotFoundError(
        f"Alfheim configuration {name} was not found locally or in the "
        "shared artifact store."
    )


def live_detection_arguments(model: Path, cache: Path, manifest: Path) -> list[str]:
    return [
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
    ]


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
            f"Live ball tracking requires yolo26n.pt, got {model.name!r}."
        )
    model_hash = sha256(model)
    if model_hash != LIVE_DETECTOR_MODEL_SHA256:
        raise ValueError(
            "Live YOLO26 checkpoint hash does not match the approved model: "
            f"{model_hash}"
        )
    return model


def require_yolo26_detection_cache(detections: Path) -> None:
    with detections.open(encoding="utf-8") as handle:
        first_line = handle.readline()
    try:
        metadata = json.loads(first_line) if first_line.strip() else {}
    except json.JSONDecodeError:
        metadata = {}
    model = str(metadata.get("model") or "")
    model_name = model.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if model_name != LIVE_DETECTOR_PROFILE["model"]:
        raise ValueError(
            "Cached detections were not produced by yolo26n.pt "
            f"(found {model_name or 'unknown model'!r}). Rerun the segment "
            "from raw video with the pinned YOLO26 detector."
        )


def recorded_ball_source(run_root: Path) -> str | None:
    for path in (
        run_root / "analytics-data" / "run-provenance.json",
        run_root / "analysis-status.json",
    ):
        if path.is_file():
            value = json.loads(path.read_text(encoding="utf-8")).get(
                "ball_source"
            )
            if value in BALL_SOURCES:
                return str(value)
    return None


def ball_track_source_kind(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload.get("source_kind") or "")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build ball coordinates, player tracks, and football events for a "
            "prepared Alfheim segment."
        )
    )
    parser.add_argument("segment", type=Path)
    parser.add_argument(
        "--ball-source",
        choices=sorted(BALL_SOURCES),
        help=(
            "bac imports frozen Alfheim BAC coordinates (evaluation-only "
            "provider coordinates; diagnostic, never a raw-video benchmark). "
            "live runs the raw-video ball tracker. Required for full runs; "
            "cached modes default to the recorded source."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--events-only",
        action="store_true",
        help="Rerun possession and event inference from cached tracking data.",
    )
    mode.add_argument(
        "--evidence-only",
        action="store_true",
        help="BAC only: prepare ball coordinates and player context, no events.",
    )
    mode.add_argument(
        "--coordinates-updated",
        action="store_true",
        help="BAC only: rebuild from the approved reviewer-coordinate layer.",
    )
    mode.add_argument(
        "--resume-after-detection",
        action="store_true",
        help=(
            "Detected ball source only: recover an interrupted run from its completed "
            "raw-video detection cache. Not a cold-path benchmark."
        ),
    )
    mode.add_argument(
        "--focused-recovery",
        action="store_true",
        help=(
            "Detected ball source only: apply bounded focused ball-coordinate recovery to the "
            "persisted runtime track. Not a cold-path benchmark."
        ),
    )
    mode.add_argument(
        "--detection-only",
        action="store_true",
        help=(
            "Detected ball source only: run the raw-video YOLO detection pass "
            "once and cache it, without ball tracking. Ball coordinates are "
            "built later from this cache with --resume-after-detection."
        ),
    )
    parser.add_argument("--skip-events", action="store_true")
    parser.add_argument(
        "--runtime-mode",
        choices=("review", "production", "validation"),
        default="review",
        help=(
            "Detected ball source only: review (default) stops after ball "
            "tracking so the reviewer can check the ball-coordinate frames and "
            "then continue to the rules engine with --events-only; production "
            "reports the ball-provenance coverage and continues straight to "
            "the rules engine; validation blocks below the threshold."
        ),
    )
    parser.add_argument("--pano", type=Path, default=None)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.skip_events and not args.coordinates_updated:
        parser.error("--skip-events requires --coordinates-updated")
    segment = args.segment.resolve()
    run_root = segment
    cached_mode = args.events_only or args.coordinates_updated
    ball_source = args.ball_source or (
        recorded_ball_source(run_root) if cached_mode else None
    )
    if ball_source is None:
        parser.error(
            "--ball-source is required (no recorded ball source to reuse)"
        )
    if cached_mode and args.ball_source:
        recorded = recorded_ball_source(run_root)
        if recorded is not None and recorded != ball_source:
            parser.error(
                f"Cached artifacts were built with ball source {recorded!r}; "
                f"run a full {ball_source!r} analysis instead."
            )
    if ball_source == "detected" and (
        args.evidence_only or args.coordinates_updated
    ):
        parser.error(
            "--evidence-only and --coordinates-updated require --ball-source bac"
        )
    if ball_source == "bac" and (
        args.resume_after_detection
        or args.focused_recovery
        or args.detection_only
    ):
        parser.error(
            "--resume-after-detection, --focused-recovery and "
            "--detection-only require --ball-source detected"
        )

    prepared_manifest = segment / "manifest.json"
    runtime_manifest = run_root / "runtime-manifest.json"
    cache = run_root / "analytics-cache"
    results = run_root / "analytics-data"
    status_path = run_root / "analysis-status.json"
    ball_tracks = cache / "ball-tracks.json"
    ball_state_estimates = cache / "ball-state-estimates.json"
    reviewer_ball_tracks = run_root / "reviewer-coordinate-layer.json"
    player_tracks = results / "player-tracks.json"
    run_id = str(uuid4())
    started_at_utc = datetime.now(timezone.utc)

    prepared = json.loads(prepared_manifest.read_text(encoding="utf-8"))
    leaked = sorted(
        field
        for field in FORBIDDEN_MANIFEST_FIELDS
        if prepared.get(field) not in (None, "", [], {})
    )
    if leaked:
        raise ValueError(
            "Prepared manifest contains evaluation inputs: " + ", ".join(leaked)
        )
    video = Path(str(prepared["video"]))
    if not video.is_absolute():
        video = segment / video
    video = video.resolve()
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
    duration = float(
        prepared.get(
            "duration_seconds",
            declared_frame_count / fps if fps else 0.0,
        )
    )
    duration_frame_count = round(duration * fps)
    if (
        declared_start_frame < 0
        or declared_frame_count <= 0
        or declared_end_frame > frame_count
        or declared_frame_count != duration_frame_count
    ):
        raise ValueError(
            "Prepared media does not match its raw-only manifest: "
            f"video has {frame_count} frames at {fps:.3f} fps, while the "
            f"manifest declares frames {declared_start_frame}:"
            f"{declared_end_frame} ({declared_frame_count} frames) and "
            f"{duration:.3f} seconds ({duration_frame_count} frames). "
            "Refusing to process an ambiguous segment."
        )
    source_start = float(prepared.get("source_start_seconds", 0.0))
    run_root.mkdir(parents=True, exist_ok=True)
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

    run_mode = (
        "cached_event_rebuild"
        if args.events_only
        else "reviewer_coordinate_rebuild"
        if args.coordinates_updated
        else "evidence_preparation"
        if args.evidence_only
        else "focused_interrupted_run_recovery"
        if args.focused_recovery
        else "interrupted_run_recovery"
        if args.resume_after_detection
        else "detection_preparation"
        if args.detection_only
        else "full_run"
    )
    cache_reuse = run_mode not in {
        "full_run",
        "evidence_preparation",
        "detection_preparation",
    }

    def status(stage: str, message: str) -> None:
        temporary = status_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "started_at_utc": started_at_utc.isoformat(),
                    "stage": stage,
                    "message": message,
                    "mode": run_mode,
                    "workflow": "football_review",
                    "ball_source": ball_source,
                    "bac_assisted": ball_source == "bac",
                    "raw_video_ball_inference": ball_source == "detected",
                    "performance_benchmark_valid": (
                        ball_source == "detected" and run_mode == "full_run"
                    ),
                    "cache_reuse": cache_reuse,
                    "elapsed_seconds": round(
                        (
                            datetime.now(timezone.utc) - started_at_utc
                        ).total_seconds(),
                        3,
                    ),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(status_path)

    stage_seconds: dict[str, float] = {}

    def run(stage: str, *arguments: str) -> None:
        started = time.perf_counter()
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(
            part
            for part in (str(LOCAL_SOURCE), environment.get("PYTHONPATH", ""))
            if part
        )
        try:
            subprocess.run(
                [sys.executable, *arguments],
                cwd=PROJECT_ROOT,
                env=environment,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            label = stage.replace("_", " ").capitalize()
            raise RuntimeError(
                f"{label} failed with exit code {error.returncode}. "
                "See analysis.log for technical details."
            ) from error
        stage_seconds[stage] = round(time.perf_counter() - started, 3)

    def track_players(active_ball_tracks: Path) -> None:
        run(
            "player_tracking",
            "-m",
            "football_poc.player_tracking_cli",
            str(runtime_manifest),
            "--player-cache",
            str(cache / "detections.jsonl"),
            "--ball-tracks",
            str(active_ball_tracks),
            "--output",
            str(results),
            "--confidence",
            str(PLAYER_TRACKING_CONFIDENCE),
            "--max-gap",
            "0.5",
            "--max-speed",
            "700",
            "--minimum-track-points",
            "3",
            "--team-profile",
            "red-black",
            "--goalkeeper-affiliations",
            str(alfheim_config_path("goalkeeper-affiliations.json")),
            "--no-video",
        )

    downstream = (
        player_tracks,
        results / "match-initialization.json",
        results / "ball-provenance.json",
        results / "possession.json",
        results / "match-state-events.json",
        results / "predicted-events.json",
        results / "chunk-simulation.json",
        results / "chunk-simulation-state.json",
        results / "run-provenance.json",
        results / "performance-report.json",
    )
    live_model: Path | None = None
    pipeline_started = time.perf_counter()
    try:
        cache.mkdir(parents=True, exist_ok=True)
        results.mkdir(parents=True, exist_ok=True)
        active_ball_tracks = (
            reviewer_ball_tracks
            if ball_source == "bac" and reviewer_ball_tracks.is_file()
            else ball_tracks
        )
        if cached_mode:
            required = [active_ball_tracks, cache / "detections.jsonl"]
            if args.events_only:
                required.append(player_tracks)
            if ball_source == "detected":
                required.append(ball_state_estimates)
            missing = [path.name for path in required if not path.is_file()]
            if missing:
                raise FileNotFoundError(
                    "Cannot rebuild from cached artifacts without "
                    + ", ".join(missing)
                )
            require_yolo26_detection_cache(cache / "detections.jsonl")
            kind =  ball_track_source_kind(active_ball_tracks)
            if ball_source == "detected" and kind in BAC_SOURCE_KINDS:
                raise ValueError(
                    "Detected-ball event rebuild rejected BAC/evaluation-derived "
                    "ball tracks"
                )
            if ball_source == "bac" and kind not in BAC_SOURCE_KINDS:
                raise ValueError(
                    "BAC event rebuild requires BAC-derived ball tracks"
                )
            if args.coordinates_updated:
                reviewer_payload = json.loads(
                    reviewer_ball_tracks.read_text(encoding="utf-8")
                )
                if (
                    reviewer_payload.get("source_kind")
                    != "reviewer_corrected_innovation_coordinates"
                    or reviewer_payload.get("base_source_kind")
                    != "evaluation_only_provider_coordinates"
                ):
                    raise ValueError(
                        "The approved reviewer-coordinate layer has invalid "
                        "BAC provenance."
                    )
                status(
                    "player_tracking",
                    "Rebuilding player context from approved reviewer "
                    "coordinates while reusing cached YOLO detections.",
                )
                track_players(active_ball_tracks)
                if args.skip_events:
                    status(
                        "evidence_ready",
                        "Approved reviewer coordinates and dependent player "
                        "tracking are ready. Events have not been rebuilt.",
                    )
                    return
        elif ball_source == "bac":
            for path in downstream:
                path.unlink(missing_ok=True)
            status("bac_coordinates", "Importing frozen BAC ball coordinates.")
            pano = (args.pano or resolve_alfheim_pano(PROJECT_ROOT)).resolve()
            write_bac_ball_tracks(
                runtime_manifest=runtime_manifest,
                pano=pano,
                output=ball_tracks,
                source_start_seconds=source_start,
                duration_seconds=duration,
            )
            active_ball_tracks = (
                reviewer_ball_tracks
                if reviewer_ball_tracks.is_file()
                else ball_tracks
            )
            live_model = resolve_live_detector_model(PROJECT_ROOT)
            status(
                "player_detection",
                "Running YOLO26n player detection from the prepared video.",
            )
            run(
                "detection",
                *live_detection_arguments(live_model, cache, runtime_manifest),
            )
            status(
                "player_tracking",
                "Building player tracks against the frozen BAC ball path.",
            )
            track_players(active_ball_tracks)
            if args.evidence_only:
                status(
                    "evidence_ready",
                    "Frozen BAC coordinates and YOLO player context are "
                    "ready. No football events have been generated.",
                )
                return
        else:
            live_model = resolve_live_detector_model(PROJECT_ROOT)
            if args.focused_recovery:
                required = [
                    cache / "detections.jsonl",
                    ball_tracks,
                    cache / "ball-tracking-summary.json",
                ]
                missing = [path.name for path in required if not path.is_file()]
                if missing:
                    raise FileNotFoundError(
                        "Cannot run focused recovery without "
                        + ", ".join(missing)
                    )
                for path in downstream:
                    path.unlink(missing_ok=True)
                status(
                    "focused_ball_recovery",
                    "Applying bounded focused YOLO recovery to unresolved "
                    "ball-coordinate frames.",
                )
                run(
                    "focused_ball_recovery",
                    str(
                        PROJECT_ROOT
                        / "scripts"
                        / "recover-focused-ball-coordinates.py"
                    ),
                    str(run_root),
                )
            elif args.resume_after_detection:
                if not (cache / "detections.jsonl").is_file():
                    raise FileNotFoundError(
                        "Cannot resume without completed raw-video detections"
                    )
                require_yolo26_detection_cache(cache / "detections.jsonl")
                for path in (ball_tracks, ball_state_estimates, *downstream):
                    path.unlink(missing_ok=True)
                status(
                    "ball_track",
                    "Interrupted-run recovery: reusing completed raw-video "
                    "detections and rebuilding all downstream artifacts.",
                )
            else:
                for path in (
                    cache / "detections.jsonl",
                    cache / "detection-summary.json",
                    ball_tracks,
                    ball_state_estimates,
                    *downstream,
                ):
                    path.unlink(missing_ok=True)
                status(
                    "detecting",
                    "Cold raw-video run: no prior detections, tracks, events, "
                    "supplied ball labels, or review labels are being used.",
                )
                run(
                    "detection",
                    *live_detection_arguments(
                        live_model, cache, runtime_manifest
                    ),
                )
                if args.detection_only:
                    status(
                        "detections_cached",
                        "Raw-video YOLO detections are cached. Ball "
                        "coordinates have not been built yet.",
                    )
                    return
                status(
                    "ball_track",
                    "Building ball tracks from raw-video detections.",
                )
            if not args.focused_recovery:
                run(
                    "ball_tracking",
                    "-m",
                    "football_poc.ball_tracking_cli",
                    str(runtime_manifest),
                    "--cache",
                    str(cache / "detections.jsonl"),
                    "--output",
                    str(cache),
                    *(
                        ["--reuse-decoded-frame-cache"]
                        if args.resume_after_detection
                        else []
                    ),
                )
            status(
                "tracking",
                "Associating players and inferring teams from visible kits.",
            )
            track_players(ball_tracks)

        if ball_source == "detected":
            status(
                "provenance_gate",
                "Validating direct ball-evidence coverage before event "
                "inference.",
            )
            provenance_report = validate_ball_provenance(
                ball_tracks,
                ball_state_estimates,
                output=results / "ball-provenance.json",
                enforce_threshold=args.runtime_mode == "validation",
            )
            if args.runtime_mode == "review" and not args.events_only:
                raise ValueError(
                    "Ball provenance review required before rules-engine "
                    "inference: "
                    f"{provenance_report['direct_frame_count']}/"
                    f"{provenance_report['sampled_frame_count']} direct "
                    f"frames ({float(provenance_report['direct_provenance']):.1%}). "
                    "Check the ball coordinate frames, then choose Continue "
                    "to rules engine."
                )
        status(
            "events",
            "Inferring match state, possession, passes, turnovers, and shots.",
        )
        boundary_events = run_root / "boundary-events.json"
        shot_evidence = run_root / SHOT_EVIDENCE_FILE_NAME
        run(
            "event_inference",
            "-m",
            "football_poc.possession_cli",
            str(runtime_manifest),
            "--player-tracks",
            str(player_tracks),
            "--ball-tracks",
            str(active_ball_tracks),
            "--output",
            str(results),
            *ALFHEIM_POSSESSION_ARGUMENTS,
            *(
                ["--boundary-events", str(boundary_events)]
                if boundary_events.is_file()
                else []
            ),
            "--shot-evidence",
            str(shot_evidence),
            "--pitch-calibration",
            str(alfheim_config_path("pitch-calibration.json")),
            "--shot-goal-calibration",
            str(alfheim_config_path("pitch-calibration.json")),
            "--shot-goalkeeper-affiliations",
            str(alfheim_config_path("goalkeeper-affiliations.json")),
        )
        chunk_state = results / "chunk-simulation-state.json"
        if args.events_only:
            chunk_state.unlink(missing_ok=True)
        status("publishing", "Preparing event chunks.")
        run(
            "chunk_publication",
            "-m",
            "football_poc.chunk_simulator_cli",
            str(runtime_manifest),
            "--events",
            str(results / "predicted-events.json"),
            "--output",
            str(results / "chunk-simulation.json"),
            "--state",
            str(chunk_state),
        )
        provenance: dict[str, object] = {
            "schema_version": 2,
            "workflow": "football_review",
            "ball_source": ball_source,
            "mode": run_mode,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "runtime_manifest_sha256": sha256(runtime_manifest),
            "engine_sha256": engine_fingerprint(PROJECT_ROOT),
            "ball_tracks_sha256": sha256(active_ball_tracks),
            "ball_track_source_kind": ball_track_source_kind(
                active_ball_tracks
            ),
            "events_sha256": sha256(results / "predicted-events.json"),
            "performance_benchmark_valid": (
                ball_source == "detected" and run_mode == "full_run"
            ),
            "shots_on_target": {
                "evidence_sha256": (
                    sha256(shot_evidence) if shot_evidence.is_file() else None
                ),
                "summary_sha256": (
                    sha256(results / SHOTS_SUMMARY_FILE_NAME)
                    if (results / SHOTS_SUMMARY_FILE_NAME).is_file()
                    else None
                ),
            },
        }
        provenance["detector_profile"] = LIVE_DETECTOR_PROFILE
        provenance["detector_model_sha256"] = LIVE_DETECTOR_MODEL_SHA256
        (results / "run-provenance.json").write_text(
            json.dumps(provenance, indent=2) + "\n",
            encoding="utf-8",
        )
        if ball_source == "detected" and run_mode == "full_run" and live_model:
            elapsed = time.perf_counter() - pipeline_started
            report = build_performance_report(
                run_id=run_id,
                video=video,
                manifest=runtime_manifest,
                model=live_model,
                source_duration_seconds=duration,
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
        elif cached_mode:
            status("ready", "Cached event rebuild completed.")
        elif ball_source == "bac":
            status(
                "ready",
                "BAC-assisted analysis is ready (diagnostic; not raw-video "
                "ball inference).",
            )
        else:
            status(
                "ready",
                "Recovery completed from preserved raw-video detections. "
                "No cold-path performance claim was produced.",
            )
    except Exception as error:
        status("failed", str(error))
        raise


if __name__ == "__main__":
    main()
