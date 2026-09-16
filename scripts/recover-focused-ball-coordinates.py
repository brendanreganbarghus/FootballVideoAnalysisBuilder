from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SOURCE = PROJECT_ROOT / "src"
if str(LOCAL_SOURCE) not in sys.path:
    sys.path.insert(0, str(LOCAL_SOURCE))

from football_poc.ball_tracking import (  # noqa: E402
    BallPoint,
    BallTrack,
    _load_cache,
    _recover_focused_multiscale_points,
    _sampled_ball_state_estimates,
    _video_dimensions,
)
from football_poc.benchmark import BenchmarkManifest  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_tracks(path: Path) -> tuple[dict, tuple[BallTrack, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tracks = tuple(
        BallTrack(
            int(track["track_id"]),
            [
                BallPoint(
                    **{
                        key: point[key]
                        for key in BallPoint.__dataclass_fields__
                        if key in point
                    }
                )
                for point in track["points"]
            ],
        )
        for track in payload["tracks"]
    )
    return payload, tracks


def _update_summary(path: Path, tracks: tuple[BallTrack, ...]) -> None:
    summary = json.loads(path.read_text(encoding="utf-8"))
    points = [point for track in tracks for point in track.points]
    evidence = Counter(point.evidence for point in points)
    attribution = Counter(point.source_attribution for point in points)
    summary["accepted_track_points"] = len(points)
    summary["tracked_frames"] = len({point.source_frame for point in points})
    summary["tracked_frame_coverage"] = round(
        summary["tracked_frames"] / summary["processed_frames"],
        4,
    )
    summary["observed_track_points"] = evidence["detector"]
    summary["temporally_supported_track_points"] = (
        len(points) - evidence["detector"] - evidence["interpolated"]
    )
    summary["interpolated_track_points"] = evidence["interpolated"]
    summary["point_source_attribution"] = dict(sorted(attribution.items()))
    summary["focused_interrupted_recovery"] = {
        "performed": True,
        "cold_path_benchmark": False,
    }
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run bounded focused YOLO recovery from a persisted raw-video "
            "tracker result without rerunning broad tracker stages."
        )
    )
    parser.add_argument("run_root", type=Path)
    args = parser.parse_args()

    run_root = args.run_root.resolve()
    manifest_path = run_root / "runtime-manifest.json"
    cache = run_root / "analytics-cache"
    results = run_root / "analytics-data"
    tracks_path = cache / "ball-tracks.json"
    states_path = cache / "ball-state-estimates.json"
    summary_path = cache / "ball-tracking-summary.json"
    detections_path = cache / "detections.jsonl"
    status_path = run_root / "analysis-status.json"
    receipt_path = results / "focused-recovery-receipt.json"
    required = (manifest_path, tracks_path, summary_path, detections_path)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Focused interrupted recovery requires " + ", ".join(missing)
        )

    run_id = str(uuid4())
    started_at = datetime.now(timezone.utc)

    def write_status(stage: str, message: str) -> None:
        status_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "stage": stage,
                    "message": message,
                    "mode": "focused_interrupted_run_recovery",
                    "workflow": "live_iteration_25",
                    "artifact_namespace": "live",
                    "cache_reuse": True,
                    "prior_artifacts_used": True,
                    "started_at_utc": started_at.isoformat(),
                    "elapsed_seconds": round(
                        (datetime.now(timezone.utc) - started_at).total_seconds(),
                        3,
                    ),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    write_status(
        "focused_ball_recovery",
        "Interrupted-run recovery: applying bounded focused YOLO only to "
        "missing ball-coordinate frames.",
    )

    manifest = BenchmarkManifest.load(manifest_path)
    metadata, records = _load_cache(detections_path, manifest.sha256)
    payload, tracks = _load_tracks(tracks_path)
    before_frames = {
        point.source_frame for track in tracks for point in track.points
    }
    before_hash = _sha256(tracks_path)
    recovery_source_hash = _sha256(
        PROJECT_ROOT / "src" / "football_poc" / "ball_tracking.py"
    )
    model_path = Path(str(metadata["model"]))
    input_fingerprint = {
        "ball_tracks_sha256": before_hash,
        "detections_sha256": _sha256(detections_path),
        "model_sha256": _sha256(model_path),
        "recovery_source_sha256": recovery_source_hash,
        "manifest_sha256": manifest.sha256,
    }
    if receipt_path.is_file() and states_path.is_file():
        previous_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (
            previous_receipt.get("after_sha256") == before_hash
            and previous_receipt.get("detections_sha256")
            == input_fingerprint["detections_sha256"]
            and previous_receipt.get("model_sha256")
            == input_fingerprint["model_sha256"]
            and previous_receipt.get("recovery_source_sha256")
            == recovery_source_hash
            and previous_receipt.get("manifest_sha256") == manifest.sha256
        ):
            write_status(
                "ready",
                "Verified focused interrupted-run recovery output reused. "
                "This is not a cold-path performance result.",
            )
            print(
                json.dumps(
                    {
                        "direct_frames": len(before_frames),
                        "added_frames": [],
                        "regressed_frames": [],
                        "reused_verified_output": True,
                    }
                )
            )
            return
    recovery_started = time.perf_counter()
    try:
        recovered = _recover_focused_multiscale_points(
            tracks,
            records=records,
            video=manifest.video,
            model_path=model_path,
            fps=manifest.fps,
            frame_step=int(metadata["stride"]),
        )
    except Exception as error:
        write_status("failed", f"Focused interrupted-run recovery failed: {error}")
        raise
    after_frames = {
        point.source_frame for track in recovered for point in track.points
    }
    regressions = sorted(before_frames - after_frames)
    if regressions:
        raise RuntimeError(
            "Focused recovery refused to publish regressions: "
            + ", ".join(map(str, regressions))
        )
    additions = sorted(after_frames - before_frames)
    payload["tracks"] = [
        {
            "track_id": track.track_id,
            "points": [asdict(point) for point in track.points],
        }
        for track in recovered
    ]
    payload["focused_interrupted_recovery"] = {
        "run_id": run_id,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "before_sha256": before_hash,
        "before_direct_frames": len(before_frames),
        "after_direct_frames": len(after_frames),
        "added_frames": additions,
        "regressed_frames": regressions,
        "detections_sha256": input_fingerprint["detections_sha256"],
        "model_sha256": input_fingerprint["model_sha256"],
        "recovery_source_sha256": recovery_source_hash,
        "manifest_sha256": manifest.sha256,
        "raw_video_used": True,
        "saved_detections_used": True,
        "cold_path_benchmark": False,
        "wall_seconds": round(time.perf_counter() - recovery_started, 3),
    }
    temporary = tracks_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, tracks_path)
    payload["focused_interrupted_recovery"]["after_sha256"] = _sha256(
        tracks_path
    )
    width, height = _video_dimensions(manifest.video)
    states_path.write_text(
        json.dumps(
            {
                "manifest": str(manifest.path),
                "cache": str(detections_path.resolve()),
                "policy": {
                    "observed_states_are_event_evidence": True,
                    "trajectory_estimates_are_event_evidence": False,
                    "trajectory_estimates_are_for_continuity_and_search_only": True,
                },
                "states": _sampled_ball_state_estimates(
                    recovered,
                    records=records,
                    fps=manifest.fps,
                    frame_step=int(metadata["stride"]),
                    width=width,
                    height=height,
                    max_speed_pixels_per_second=1600.0,
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _update_summary(summary_path, recovered)
    results.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(payload["focused_interrupted_recovery"], indent=2) + "\n",
        encoding="utf-8",
    )
    write_status(
        "ready",
        "Focused interrupted-run recovery completed from preserved detections. "
        "This is not a cold-path performance result.",
    )
    print(
        json.dumps(
            {
                "direct_frames": len(after_frames),
                "added_frames": additions,
                "regressed_frames": regressions,
            }
        )
    )


if __name__ == "__main__":
    main()
