from __future__ import annotations

import hashlib
import os
import platform
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def host_specification() -> dict[str, Any]:
    processor = platform.processor().strip() or platform.uname().processor.strip()
    return {
        "processor": processor or "Unknown CPU",
        "logical_cores": os.cpu_count(),
        "operating_system": platform.platform(),
        "python": platform.python_version(),
    }


def gpu_planning_guidance(
    *,
    source_duration_seconds: float,
    wall_time_seconds: float,
    detection_seconds: float,
) -> dict[str, Any]:
    deadline = 30.0 if source_duration_seconds <= 30.0 else 60.0
    required_end_to_end_speedup = max(1.0, wall_time_seconds / deadline)
    non_detection_seconds = max(0.0, wall_time_seconds - detection_seconds)
    if wall_time_seconds <= deadline:
        required_detection_speedup: float | None = 1.0
    elif non_detection_seconds >= deadline:
        required_detection_speedup = None
    else:
        required_detection_speedup = detection_seconds / (
            deadline - non_detection_seconds
        )

    planning_speedup = required_detection_speedup or required_end_to_end_speedup
    if planning_speedup <= 2.0:
        tier = "Entry CUDA workstation"
        example = "NVIDIA GeForce RTX 4060-class or better"
        vram_gb = 8
    elif planning_speedup <= 4.0:
        tier = "Mid-range CUDA workstation"
        example = "NVIDIA GeForce RTX 4070 SUPER-class or better"
        vram_gb = 12
    elif planning_speedup <= 8.0:
        tier = "High-end CUDA workstation"
        example = "NVIDIA GeForce RTX 4080 SUPER-class or better"
        vram_gb = 16
    else:
        tier = "Maximum single-GPU workstation plus pipeline optimization"
        example = "NVIDIA GeForce RTX 4090-class or better"
        vram_gb = 24

    return {
        "deadline_seconds": deadline,
        "cpu_deadline_met": wall_time_seconds <= deadline,
        "required_measured_end_to_end_speedup": round(
            required_end_to_end_speedup, 3
        ),
        "required_detection_speedup": (
            round(required_detection_speedup, 3)
            if required_detection_speedup is not None
            else None
        ),
        "planning_tier": tier,
        "minimum_vram_gb": vram_gb,
        "example_gpu": example,
        "requirements": [
            "NVIDIA CUDA-capable GPU",
            f"At least {vram_gb} GB dedicated VRAM",
            "CUDA-compatible PyTorch installation",
            "SSD storage and enough system RAM for decoded frame batches",
        ],
        "qualification": (
            "Planning guidance only, not a throughput guarantee. Qualify the "
            "GPU by rerunning this exact cold raw-video pipeline with no reused "
            "detections, tracks, events, or provider annotations."
        ),
        "gpu_alone_can_meet_deadline": non_detection_seconds < deadline,
    }


def build_performance_report(
    *,
    run_id: str,
    video: Path,
    manifest: Path,
    model: Path,
    source_duration_seconds: float,
    source_fps: float,
    sampled_frames: int,
    wall_time_seconds: float,
    stage_seconds: dict[str, float],
) -> dict[str, Any]:
    detection_seconds = float(stage_seconds.get("detection", 0.0))
    deadline = 30.0 if source_duration_seconds <= 30.0 else 60.0
    return {
        "schema_version": 1,
        "run_id": run_id,
        "mode": "cold_raw_video",
        "cache_reuse": False,
        "input_provenance": {
            "raw_video": video.name,
            "raw_video_sha256": file_sha256(video),
            "runtime_manifest": manifest.name,
            "runtime_manifest_sha256": file_sha256(manifest),
            "model": model.name,
            "model_sha256": file_sha256(model),
            "allowed_inference_inputs": [
                "raw_video",
                "camera_calibration",
                "model_weights",
            ],
            "prior_artifacts_used": False,
            "excluded_inputs": [
                "prior detections",
                "prior ball tracks",
                "prior player tracks",
                "prior possession",
                "prior events",
                "manual review labels",
                "provider annotations",
            ],
        },
        "host": host_specification(),
        "source_duration_seconds": round(source_duration_seconds, 3),
        "wall_time_seconds": round(wall_time_seconds, 3),
        "real_time_factor": round(
            wall_time_seconds / source_duration_seconds, 3
        ),
        "sampled_frames": sampled_frames,
        "source_fps": source_fps,
        "stage_seconds": stage_seconds,
        "processing_rate": _processing_rate(
            source_duration_seconds=source_duration_seconds,
            source_fps=source_fps,
            sampled_frames=sampled_frames,
            wall_time_seconds=wall_time_seconds,
            deadline_seconds=deadline,
        ),
        "rules_engine_capacity": {
            "event_inference_seconds": stage_seconds.get("event_inference"),
            "complete_segments_per_hour": round(
                3600.0 / wall_time_seconds, 2
            ),
            "deadline_seconds": deadline,
            "deadline_headroom_seconds": round(
                deadline - wall_time_seconds, 3
            ),
        },
        "gpu_guidance": gpu_planning_guidance(
            source_duration_seconds=source_duration_seconds,
            wall_time_seconds=wall_time_seconds,
            detection_seconds=detection_seconds,
        ),
        "tracking_video_rendered_on_critical_path": False,
    }


def build_cache_rebuild_performance_report(
    *,
    run_id: str,
    video: Path,
    manifest: Path,
    detection_cache: Path,
    source_duration_seconds: float,
    source_fps: float,
    sampled_frames: int,
    wall_time_seconds: float,
    stage_seconds: dict[str, float],
) -> dict[str, Any]:
    deadline = 30.0 if source_duration_seconds <= 30.0 else 60.0
    return {
        "schema_version": 1,
        "run_id": run_id,
        "mode": "cache_rebuild",
        "cache_reuse": True,
        "timing_scope": (
            "Post-detection rebuild from a frozen detector cache; not a cold "
            "raw-video processing-speed result."
        ),
        "input_provenance": {
            "raw_video": video.name,
            "raw_video_sha256": file_sha256(video),
            "runtime_manifest": manifest.name,
            "runtime_manifest_sha256": file_sha256(manifest),
            "frozen_detection_cache": detection_cache.name,
            "frozen_detection_cache_sha256": file_sha256(detection_cache),
            "allowed_inference_inputs": [
                "raw_video",
                "camera_calibration",
                "frozen_detector_cache",
            ],
            "prior_artifacts_used": ["frozen detector cache"],
            "excluded_inputs": [
                "prior ball tracks",
                "prior player tracks",
                "prior possession",
                "prior events",
                "manual review labels",
                "provider annotations",
            ],
        },
        "host": host_specification(),
        "source_duration_seconds": round(source_duration_seconds, 3),
        "wall_time_seconds": round(wall_time_seconds, 3),
        "real_time_factor": round(
            wall_time_seconds / source_duration_seconds, 3
        ),
        "sampled_frames": sampled_frames,
        "source_fps": source_fps,
        "stage_seconds": stage_seconds,
        "processing_rate": _processing_rate(
            source_duration_seconds=source_duration_seconds,
            source_fps=source_fps,
            sampled_frames=sampled_frames,
            wall_time_seconds=wall_time_seconds,
            deadline_seconds=deadline,
        ),
        "rules_engine_capacity": {
            "event_inference_seconds": stage_seconds.get("event_inference"),
            "complete_segments_per_hour": round(
                3600.0 / wall_time_seconds, 2
            ),
            "deadline_seconds": deadline,
            "deadline_headroom_seconds": round(
                deadline - wall_time_seconds, 3
            ),
        },
        "tracking_video_rendered_on_critical_path": False,
    }


def _processing_rate(
    *,
    source_duration_seconds: float,
    source_fps: float,
    sampled_frames: int,
    wall_time_seconds: float,
    deadline_seconds: float,
) -> dict[str, float]:
    source_frames = source_duration_seconds * source_fps
    return {
        "achieved_source_frames_per_second": round(
            source_frames / wall_time_seconds,
            3,
        ),
        "achieved_sampled_frames_per_second": round(
            sampled_frames / wall_time_seconds,
            3,
        ),
        "acceleration_required_to_meet_deadline": round(
            max(1.0, wall_time_seconds / deadline_seconds),
            3,
        ),
    }
