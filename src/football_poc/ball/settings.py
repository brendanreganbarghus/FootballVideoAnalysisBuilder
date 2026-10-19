from __future__ import annotations

from __future__ import annotations

import hashlib
import json
import os
import pickle
import sys
import threading
import time
from collections import Counter, defaultdict
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from itertools import product
from math import hypot
from pathlib import Path
from statistics import median
from typing import Any, Iterable

import cv2
import numpy as np

from football_poc.benchmark import BenchmarkManifest


class FrozenProfile(dict):
    def _blocked(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("ball-tracking settings are frozen")

    __setitem__ = _blocked
    __delitem__ = _blocked
    clear = _blocked
    pop = _blocked
    popitem = _blocked
    setdefault = _blocked
    update = _blocked



_ACTIVE_GRAYSCALE_FRAME_STORE: _SampledGrayscaleFrameStore | None = None


def _ball_worker_count() -> int:
    configured = os.environ.get("FOOTBALL_BALL_WORKERS")
    if configured:
        return max(1, int(configured))
    return max(1, min(8, (os.cpu_count() or 1) - 1))


def _ordered_parallel_map(function: Any, items: Iterable[Any]) -> list[Any]:
    """Apply a pure function to independent items on idle cores.

    Results keep the input order, so callers combine them exactly as a
    sequential loop would. OpenCV and NumPy release the GIL while working.
    """
    items = list(items)
    workers = min(_ball_worker_count(), len(items))
    if workers <= 1:
        return [function(item) for item in items]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(function, items))


def _ball_scratch_directory(output: Path) -> Path:
    """Local folder for large temporary ball-tracking files.

    FOOTBALL_LOCAL_SCRATCH keeps decoded frames and step-replay saves off a
    synced share (for example OneDrive); without it they stay in ``output``.
    """
    root = os.environ.get("FOOTBALL_LOCAL_SCRATCH")
    if not root:
        return output
    resolved = str(Path(output).resolve())
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]
    return Path(root) / "ball" / f"{Path(resolved).name}-{digest}"


# Step replay is an explicit opt-in diagnostic for cached reruns. Each tracker
# step's result is saved with a fingerprint of its code (every function it can
# reach plus upper-case constants) and of its inputs. A later run reuses a
# saved result only when both fingerprints are identical, so any code or
# upstream change makes that step, and every step whose input then changes,
# run again. A replayed run is never a raw-video processing benchmark.
STEP_REPLAY_SCHEMA = 1
_ACTIVE_STEP_REPLAY: "_StepReplay | None" = None


def _replay_bytes(value: Any, seen: set[int] | None = None) -> bytes:
    if seen is None:
        seen = set()
    if value is None or isinstance(value, (bool, int, str)):
        return repr((type(value).__name__, value)).encode("utf-8")
    if isinstance(value, float):
        return b"f" + value.hex().encode("ascii")
    if isinstance(value, bytes):
        return b"b" + hashlib.sha256(value).digest()
    if isinstance(value, Path):
        try:
            stat = value.stat()
            identity = f"{value}|{stat.st_size}|{stat.st_mtime_ns}" if value.is_file() else str(value)
        except OSError:
            identity = str(value)
        return b"p" + identity.encode("utf-8")
    if isinstance(value, np.ndarray):
        return (
            b"a" + repr((value.shape, str(value.dtype))).encode("ascii")
            + hashlib.sha256(np.ascontiguousarray(value).tobytes()).digest()
        )
    if isinstance(value, np.generic):
        return _replay_bytes(value.item(), seen)
    if id(value) in seen:
        return b"cycle"
    seen = seen | {id(value)}
    if isinstance(value, Mapping):
        items = sorted(
            _replay_bytes(key, seen) + b"=" + _replay_bytes(item, seen)
            for key, item in value.items()
        )
        return b"{" + b",".join(items) + b"}"
    if isinstance(value, (set, frozenset)):
        return b"s{" + b",".join(sorted(_replay_bytes(item, seen) for item in value)) + b"}"
    if isinstance(value, (list, tuple)):
        return b"[" + b",".join(_replay_bytes(item, seen) for item in value) + b"]"
    if hasattr(value, "__dataclass_fields__"):
        return type(value).__qualname__.encode("utf-8") + _replay_bytes(
            {name: getattr(value, name) for name in value.__dataclass_fields__},
            seen,
        )
    if hasattr(value, "__dict__") and not callable(value):
        return type(value).__qualname__.encode("utf-8") + _replay_bytes(
            vars(value), seen
        )
    return b"r" + type(value).__qualname__.encode("utf-8")


def _replay_code_bytes(code: Any) -> bytes:
    parts = [code.co_code, repr(code.co_names).encode("utf-8")]
    for constant in code.co_consts:
        if hasattr(constant, "co_code"):
            parts.append(_replay_code_bytes(constant))
        else:
            parts.append(_replay_bytes(constant))
    return b"|".join(parts)


def _replay_code_names(code: Any) -> set[str]:
    names = set(code.co_names)
    for constant in code.co_consts:
        if hasattr(constant, "co_code"):
            names |= _replay_code_names(constant)
    return names


def _step_code_fingerprint(function: Any) -> str:
    """Fingerprint a step's code and every function and constant it reaches."""
    digest = hashlib.sha256()
    pending = [function]
    visited: set[int] = set()
    constants: dict[str, bytes] = {}
    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        if isinstance(current, type):
            for member in vars(current).values():
                member = getattr(member, "__func__", member)
                if hasattr(member, "__code__"):
                    pending.append(member)
            continue
        code = getattr(current, "__code__", None)
        if code is None:
            continue
        digest.update(getattr(current, "__qualname__", "").encode("utf-8"))
        digest.update(_replay_code_bytes(code))
        digest.update(_replay_bytes(getattr(current, "__defaults__", None)))
        digest.update(_replay_bytes(getattr(current, "__kwdefaults__", None)))
        namespace = getattr(current, "__globals__", {})
        for name in _replay_code_names(code):
            if name not in namespace:
                continue
            value = namespace[name]
            if hasattr(value, "__code__") or (
                isinstance(value, type)
                and str(getattr(value, "__module__", "")).startswith("football_poc")
            ):
                pending.append(value)
            elif name.isupper() and name not in constants:
                constants[name] = _replay_bytes(value)
    for name in sorted(constants):
        digest.update(name.encode("utf-8") + b"=" + constants[name])
    return digest.hexdigest()


class _StepReplay:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.counts: Counter[str] = Counter()
        self.reused: list[str] = []
        self.rerun: list[str] = []
        self.environment = repr(
            (STEP_REPLAY_SCHEMA, sys.version, np.__version__, cv2.__version__)
        ).encode("utf-8")

    def call(self, name: str, function: Any, args: tuple, kwargs: dict) -> Any:
        self.counts[name] += 1
        label = name if self.counts[name] == 1 else f"{name}#{self.counts[name]}"
        safe = "".join(ch if ch.isalnum() or ch in "-_#" else "_" for ch in label)
        path = self.directory / f"{safe}.pkl"
        digest = hashlib.sha256(self.environment)
        digest.update(_step_code_fingerprint(function).encode("ascii"))
        digest.update(_replay_bytes((args, kwargs)))
        key = digest.hexdigest()
        if path.is_file():
            try:
                saved = pickle.loads(path.read_bytes())
            except Exception:
                saved = None
            if isinstance(saved, dict) and saved.get("key") == key:
                self.reused.append(label)
                return saved["result"]
        result = function(*args, **kwargs)
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(
            pickle.dumps({"key": key, "result": result}, protocol=pickle.HIGHEST_PROTOCOL)
        )
        temporary.replace(path)
        self.rerun.append(label)
        return result

    def report(self) -> dict[str, Any]:
        return {
            "schema_version": STEP_REPLAY_SCHEMA,
            "directory": str(self.directory),
            "reused_steps": list(self.reused),
            "rerun_steps": list(self.rerun),
            "note": (
                "Cached-rerun diagnostic: saved step results were reused only "
                "where code and inputs were identical. Not a raw-video "
                "processing benchmark."
            ),
        }


def _timed_tracker_call(name: str, function: Any, /, *args: Any, **kwargs: Any):
    started = time.perf_counter()
    if _ACTIVE_STEP_REPLAY is not None:
        result = _ACTIVE_STEP_REPLAY.call(name, function, args, kwargs)
    else:
        result = function(*args, **kwargs)
    if _ACTIVE_GRAYSCALE_FRAME_STORE is not None:
        timings = _ACTIVE_GRAYSCALE_FRAME_STORE.metrics.setdefault(
            "substage_seconds",
            {},
        )
        timings[name] = round(
            float(timings.get(name, 0.0)) + time.perf_counter() - started,
            3,
        )
    return result


SOCCERTRACK_RAW_MOTION_PROFILE = FrozenProfile({
    "difference_threshold": 18,
    "minimum_circularity": 0.32,
    "minimum_appearance_range": 24.0,
    "minimum_extent_ball_diameters": 0.18,
    "maximum_extent_ball_diameters": 1.8,
    "minimum_area_ball_diameters_squared": 0.025,
    "maximum_area_ball_diameters_squared": 1.8,
    "trajectory_corridor_ball_diameters": 2.5,
    "trajectory_maximum_sample_gap": 4,
    "global_fallback_minimum_temporal_neighbors": 2,
})

SOCCERTRACK_KALMAN_REACQUISITION_PROFILE = FrozenProfile({
    "process_position_variance": 4.0,
    "process_velocity_variance": 625.0,
    "measurement_variance": 16.0,
    "initial_position_variance": 16.0,
    "initial_velocity_variance": 40000.0,
    "uncertainty_sigma": 2.5,
    "minimum_roi_radius_pixels": 12.0,
    "maximum_roi_radius_pixels": 140.0,
    "maximum_prediction_only_frames": 3,
    "maximum_bidirectional_disagreement_fraction": 0.75,
    "candidate_deduplication_pixels": 4.0,
})

SOCCERTRACK_DENSE_FLOW_PROFILE = FrozenProfile({
    "maximum_bridge_raw_frames": 20,
    "patch_radius_ball_diameters": 1.0,
    "minimum_patch_radius_pixels": 5,
    "maximum_patch_radius_pixels": 18,
    "lk_window_pixels": 15,
    "lk_pyramid_levels": 2,
    "maximum_forward_backward_error_pixels": 1.5,
    "minimum_retained_features": 3,
    "feature_quality_level": 0.01,
    "feature_minimum_distance_pixels": 2.0,
    "minimum_template_score": 0.55,
    "local_search_ball_diameters": 1.5,
    "maximum_local_search_pixels": 24,
    "maximum_speed_pixels_per_second": 1600.0,
    "maximum_acceleration_pixels_per_second_squared": 12000.0,
    "minimum_feature_scale_ratio": 0.4,
    "maximum_feature_scale_ratio": 2.5,
    "maximum_endpoint_error_ball_diameters": 1.5,
    "maximum_path_disagreement_ball_diameters": 1.5,
})

LONG_STATIONARY_TEMPLATE_PROFILE = FrozenProfile({
    "maximum_bridge_seconds": 3.0,
    "maximum_endpoint_distance_ball_diameters": 0.5,
    "maximum_history_radius_ball_diameters": 0.5,
    "minimum_history_points": 4,
    "minimum_history_seconds": 0.6,
    "maximum_history_gap_seconds": 2.4,
    "maximum_forward_seconds": 0.8,
})

SHORT_STATIONARY_TEMPLATE_PROFILE = FrozenProfile({
    "maximum_endpoint_distance_ball_diameters": 0.25,
    "minimum_template_score": 0.9,
    "maximum_template_disagreement_ball_diameters": 0.25,
})

FULL_RATE_MOTION_STREAK_PROFILE = FrozenProfile({
    "maximum_launch_wait_seconds": 0.8,
    "minimum_launch_separation_ball_diameters": 4.0,
    "motion_prior_history_seconds": 0.8,
    "minimum_search_radius_ball_diameters": 2.0,
    "maximum_launch_acceleration_ball_diameters_per_second_squared": 80.0,
    "minimum_confirmed_flight_seconds": 0.4,
    "minimum_progress_ball_diameters_per_second": 8.0,
    "maximum_evidence_gap_seconds": 0.12,
    "difference_threshold": 18,
    "maximum_extent_ball_diameters": 3.0,
    "maximum_aspect_ratio": 4.0,
    "maximum_acceleration_pixels_per_second_squared": 6250.0,
    "minimum_visual_score": 0.45,
    "near_best_mean_score_margin": 0.03,
    "consensus_radius_ball_diameters": 0.75,
    "maximum_paths": 400,
})

FULL_RATE_TRAJECTORY_CORRIDOR_PROFILE = FrozenProfile({
    "maximum_gap_seconds": 0.8,
    "confirmation_seconds": 0.16,
    "minimum_history_points": 4,
    "history_seconds": 0.8,
    "minimum_history_speed_ball_diameters_per_second": 4.0,
    "maximum_acceleration_pixels_per_second_squared": 12000.0,
    "minimum_search_radius_ball_diameters": 2.0,
    "maximum_evidence_gap_seconds": 0.12,
    "minimum_path_points": 5,
    "minimum_visual_score": 0.45,
    "minimum_appearance_score": 0.40,
    "appearance_scale": 60.0,
    "near_best_mean_score_margin": 0.03,
    "consensus_radius_ball_diameters": 0.75,
    "maximum_paths": 400,
})

SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE = FrozenProfile({
    "experiment": "2-conservative-global-veto-and-ambiguity-ranking",
    "adjacent_template_minimum_score": 0.30,
    "adjacent_path_maximum_ball_diameters": 2.0,
    "foreground_weight": 0.20,
    "compactness_weight": 0.20,
    "scale_weight": 0.20,
    "texture_weight": 0.15,
    "appearance_consistency_weight": 0.25,
    "lower_body_interior_penalty": 0.15,
    "near_feet_minimum_score": 0.58,
    "trajectory_corridor_minimum_score": 0.58,
    "global_fallback_minimum_score": 0.60,
    "minimum_alternative_margin": 0.08,
    "continuity_weight": 0.35,
    "mode_switch_penalty": 0.08,
    "maximum_acceleration_pixels_per_second_squared": 12000.0,
})

SOCCERTRACK_PLAYER_ATTENTION_PROFILE = FrozenProfile({
    "experiment": "3-player-attention-convergence",
    "minimum_person_confidence": 0.35,
    "minimum_person_height_pixels": 15.0,
    "maximum_cone_half_angle_degrees": 40.0,
    "maximum_distance_player_heights": 12.0,
    "minimum_search_distance_pixels": 240.0,
    "minimum_orientation_confidence": 0.18,
    "minimum_converging_players": 2,
    "startup_minimum_converging_players": 3,
    "startup_seconds": 0.8,
    "minimum_convergence_score": 0.35,
    "startup_minimum_convergence_score": 0.65,
    "minimum_visual_verification_score": 0.58,
    "minimum_appearance_consistency_score": 0.10,
    "minimum_compactness_score": 0.40,
    "minimum_scale_score": 0.40,
    "minimum_foreground_score": 0.25,
    "startup_forward_confirmation_frames": 2,
})

SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE = FrozenProfile({
    "minimum_path_error_pixels": 35.0,
    "minimum_path_error_ball_diameters": 7.0,
    "maximum_neighbor_gap_frames": 2,
    "minimum_outlier_visual_support": 1.8,
    "minimum_conflict_support_margin": 0.75,
    "terminal_minimum_support": 2.0,
    "short_bridge_maximum_raw_frames": 35,
    "short_bridge_minimum_verification_score": 0.4,
    "short_bridge_corridor_pixels": 50.0,
    "short_bridge_corridor_ball_diameters": 3.0,
    "short_bridge_curved_corridor_pixels": 75.0,
    "short_bridge_curved_corridor_ball_diameters": 5.0,
    "short_bridge_curved_minimum_neighbors": 2,
    "short_bridge_minimum_chain_points": 2,
    "isolated_corridor_minimum_verification_score": 0.58,
    "isolated_corridor_minimum_trajectory_score": 0.5,
    "complete_path_maximum_raw_frames": 20,
    "complete_path_minimum_verification_score": 0.5,
    "complete_path_minimum_points": 3,
    "complete_path_candidate_limit": 6,
    "complete_path_deduplication_ball_diameters": 0.75,
    "complete_path_attention_weight": 0.05,
    "complete_path_mode_switch_penalty": 0.08,
    "complete_path_minimum_margin": 0.08,
    "global_fallback_outlier_maximum_confidence": 0.7,
    "global_fallback_outlier_minimum_path_error_ball_diameters": 4.0,
    "global_fallback_outlier_maximum_bracket_frames": 10,
    "return_excursion_maximum_span_seconds": 2.0,
    "return_excursion_stable_radius_ball_diameters": 3.0,
    "return_excursion_minimum_distance_pixels": 100.0,
    "return_excursion_minimum_distance_ball_diameters": 10.0,
    "curved_estimate_minimum_vertical_ball_diameters": 4.0,
    "curved_estimate_maximum_adjustment_ball_diameters": 0.75,
    "curved_estimate_maximum_velocity_difference_ratio": 0.5,
})

FOCUSED_MULTISCALE_REDETECTION_PROFILE = FrozenProfile({
    "minimum_detector_confidence": 0.01,
    "crop_radius_ball_diameters": (8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0),
    "minimum_crop_radius_pixels": 80,
    "inference_sizes": (640,),
    "minimum_consensus_variants": 3,
    "consensus_radius_ball_diameters": 1.5,
    "maximum_trajectory_distance_ball_diameters": 7.0,
    "maximum_path_error_ratio": 0.8,
    "maximum_recovery_iterations": 3,
    "weak_detector_maximum_confidence": 0.15,
    "weak_detector_minimum_path_error_ball_diameters": 1.5,
    "missing_point_maximum_path_error_ball_diameters": 3.0,
    "missing_pair_maximum_separation_ball_diameters": 1.5,
    "terminal_maximum_step_ball_diameters": 2.0,
    "terminal_minimum_confirmation_frames": 3,
})
