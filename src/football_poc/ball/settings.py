from __future__ import annotations

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
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


def _timed_tracker_call(name: str, function: Any, /, *args: Any, **kwargs: Any):
    started = time.perf_counter()
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
