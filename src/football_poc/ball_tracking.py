from __future__ import annotations

import json
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


SOCCERTRACK_RAW_MOTION_PROFILE = {
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
}

SOCCERTRACK_KALMAN_REACQUISITION_PROFILE = {
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
}

SOCCERTRACK_DENSE_FLOW_PROFILE = {
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
}

LONG_STATIONARY_TEMPLATE_PROFILE = {
    "maximum_bridge_seconds": 3.0,
    "maximum_endpoint_distance_ball_diameters": 0.5,
    "maximum_history_radius_ball_diameters": 0.5,
    "minimum_history_points": 4,
    "minimum_history_seconds": 0.6,
    "maximum_history_gap_seconds": 2.4,
}

SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE = {
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
}

SOCCERTRACK_PLAYER_ATTENTION_PROFILE = {
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
}

SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE = {
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
}


@dataclass(frozen=True)
class BallPoint:
    source_frame: int
    clip_seconds: float
    confidence: float
    x: float
    y: float
    interpolated: bool = False
    box_diagonal: float = 0.0
    evidence: str = "detector"
    temporal_score: float | None = None
    source_attribution: str = "yolo26_observed"


@dataclass
class BallTrack:
    track_id: int
    points: list[BallPoint]

    @property
    def last(self) -> BallPoint:
        return self.points[-1]

    def predicted_center(self, clip_seconds: float) -> tuple[float, float]:
        if len(self.points) < 2:
            return self.last.x, self.last.y
        previous, current = self.points[-2:]
        elapsed = current.clip_seconds - previous.clip_seconds
        if elapsed <= 0:
            return current.x, current.y
        future = clip_seconds - current.clip_seconds
        return (
            current.x + (current.x - previous.x) / elapsed * future,
            current.y + (current.y - previous.y) / elapsed * future,
        )


@dataclass(frozen=True)
class _BallCandidate:
    point: BallPoint
    near_player_feet: bool


@dataclass(frozen=True)
class _UnanchoredStaticCluster:
    x: float
    y: float


@dataclass(frozen=True)
class _TemplateBridge:
    track_index: int
    first: BallPoint
    second: BallPoint
    target_frame: int
    template_points: tuple[BallPoint, ...]


@dataclass(frozen=True)
class _TemplateMatch:
    x: float
    y: float
    score: float


@dataclass(frozen=True)
class _CircleCandidate:
    x: float
    y: float
    radius: float


@dataclass(frozen=True)
class _BidirectionalTemplateBridge:
    track_index: int
    frame_step: int
    previous: BallPoint | None
    first: BallPoint
    second: BallPoint
    following: BallPoint | None
    bridge_kind: str = "short_motion"

    @property
    def frames(self) -> tuple[int, ...]:
        direction = 1 if self.second.source_frame > self.first.source_frame else -1
        return tuple(
            range(
                self.first.source_frame,
                self.second.source_frame + direction,
                direction * self.frame_step,
            )
        )


@dataclass(frozen=True)
class _MotionBridge:
    track_index: int
    first: BallPoint
    second: BallPoint

    @property
    def target_frame(self) -> int:
        return (self.first.source_frame + self.second.source_frame) // 2

    @property
    def frames(self) -> tuple[int, int, int]:
        return (
            self.first.source_frame,
            self.target_frame,
            self.second.source_frame,
        )


@dataclass(frozen=True)
class _ForwardTemplatePlan:
    track_index: int
    frame_step: int
    previous: BallPoint
    seed: BallPoint
    template_points: tuple[BallPoint, ...]
    target_frames: tuple[int, ...]

    @property
    def frames(self) -> tuple[int, ...]:
        return tuple(
            sorted(
                {
                    *(point.source_frame for point in self.template_points),
                    *self.target_frames,
                }
            )
        )


@dataclass(frozen=True)
class _RawMotionProposal:
    point: BallPoint
    mode: str
    appearance_score: float
    foreground_score: float = 0.0
    compactness_score: float = 0.0
    scale_score: float = 0.0
    appearance_consistency_score: float = 0.0
    verification_score: float = 0.0
    trajectory_score: float = 0.0
    attention_support: int = 0
    attention_score: float = 0.0


@dataclass(frozen=True)
class _RawMotionDiagnostics:
    generated: int = 0
    rejected_scale_or_shape: int = 0
    rejected_appearance: int = 0
    rejected_player_body: int = 0
    rejected_ambiguity: int = 0
    rejected_temporal_consistency: int = 0
    near_feet: int = 0
    trajectory_corridor: int = 0
    global_fallback: int = 0
    rejected_verification: int = 0
    rejected_path_plausibility: int = 0
    rejected_alternative_margin: int = 0
    near_feet_generated: int = 0
    trajectory_corridor_generated: int = 0
    global_fallback_generated: int = 0
    minimum_accepted_trajectory_margin: float | None = None
    mean_accepted_trajectory_margin: float | None = None
    attention_accepted: int = 0
    attention_rejected_visual_evidence: int = 0
    attention_rejected_convergence: int = 0
    attention_rejected_temporal_path: int = 0
    startup_points_rejected: int = 0


@dataclass(frozen=True)
class _PlayerAttentionCone:
    origin_x: float
    origin_y: float
    direction_x: float
    direction_y: float
    confidence: float
    player_height: float


@dataclass(frozen=True)
class _KalmanPrediction:
    source_frame: int
    x: float
    y: float
    covariance: np.ndarray


@dataclass(frozen=True)
class _KalmanReacquisitionDiagnostics:
    successes: int = 0
    yolo_candidates: int = 0
    raw_motion_candidates: int = 0
    near_feet: int = 0
    trajectory_corridor: int = 0
    global_fallback: int = 0
    expired_predictions: int = 0
    bidirectional_rejections: int = 0
    visual_evidence_misses: int = 0
    conflicts: int = 0


@dataclass(frozen=True)
class _DenseFlowSample:
    x: float
    y: float
    confidence: float


@dataclass(frozen=True)
class _DenseFlowDiagnostics:
    accepted_points: int = 0
    successful_bridges: int = 0
    rejected_drift: int = 0
    expired_bridges: int = 0
    endpoint_disagreement: int = 0
    insufficient_feature_support: int = 0
    appearance_rejections: int = 0
    player_upper_body_rejections: int = 0
    minimum_path_confidence: float | None = None
    mean_path_confidence: float | None = None


def track_cached_balls(
    *,
    manifest_path: Path,
    cache_path: Path,
    output: Path,
    static_cell_size: int = 20,
    static_occupancy: float = 0.25,
    max_gap_seconds: float = 0.56,
    max_speed_pixels_per_second: float = 1600.0,
    minimum_track_points: int = 3,
    analysis_start_seconds: float | None = None,
    analysis_end_seconds: float | None = None,
) -> Path:
    manifest = BenchmarkManifest.load(manifest_path)
    metadata, records = _load_cache(cache_path, manifest.sha256)
    records = _records_in_analysis_window(
        records,
        start_seconds=analysis_start_seconds,
        end_seconds=analysis_end_seconds,
    )
    _validate_options(
        static_cell_size=static_cell_size,
        static_occupancy=static_occupancy,
        max_gap_seconds=max_gap_seconds,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        minimum_track_points=minimum_track_points,
    )
    width, height = _video_dimensions(manifest.video)
    pitch_candidates = [
        (point, record)
        for record in records
        for point in _ball_points(record)
        if _inside_soccertrack_pitch(point, width, height)
    ]
    candidates = [
        _BallCandidate(
            point=point,
            near_player_feet=_near_player_feet(point, record),
        )
        for point, record in pitch_candidates
        if _player_context_allows_ball(point, record)
    ]
    static_cells = _static_cells(
        (candidate.point for candidate in candidates),
        frame_count=len(records),
        cell_size=static_cell_size,
        occupancy=static_occupancy,
    ) - _player_anchored_cells(candidates, cell_size=static_cell_size)
    unanchored_static_clusters = _unanchored_static_clusters(
        (
            candidate
            for candidate in candidates
            if not _near_static_cell(
                candidate.point,
                static_cells,
                static_cell_size,
            )
        ),
        cell_size=static_cell_size,
        maximum_continuous_gap_seconds=max_gap_seconds,
    )
    global_static_rejections = sum(
        _near_static_cell(
            candidate.point,
            static_cells,
            static_cell_size,
        )
        for candidate in candidates
    )
    unanchored_static_rejections = sum(
        not _near_static_cell(
            candidate.point,
            static_cells,
            static_cell_size,
        )
        and _near_unanchored_static_cluster(
            candidate.point,
            unanchored_static_clusters,
            cell_size=static_cell_size,
        )
        for candidate in candidates
    )
    filtered_candidate_objects = [
        candidate
        for candidate in candidates
        if not _near_static_cell(
            candidate.point,
            static_cells,
            static_cell_size,
        )
        and not _near_unanchored_static_cluster(
            candidate.point,
            unanchored_static_clusters,
            cell_size=static_cell_size,
        )
    ]
    filtered = [candidate.point for candidate in filtered_candidate_objects]
    filtered_candidate_counts = Counter(
        point.source_frame for point in filtered
    )
    associated_tracks = _associate_tracks(
        filtered,
        max_gap_seconds=max_gap_seconds,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    associated_tracks, discarded_static_fragments = (
        _discard_unanchored_static_fragments(
            associated_tracks,
            candidates,
        )
    )
    supported_tracks = _supported_ball_tracks(
        associated_tracks,
        minimum_track_points=minimum_track_points,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        foot_supported_points=frozenset(
            candidate.point
            for candidate in candidates
            if candidate.near_player_feet
        ),
    )
    frame_step = int(metadata["stride"])
    motion_supported_tracks = _add_motion_supported_points(
        supported_tracks,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
        maximum_gap_seconds=max_gap_seconds,
    )
    temporally_supported_tracks = _add_template_supported_points(
        motion_supported_tracks,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
        maximum_gap_seconds=max_gap_seconds,
    )
    accepted = select_single_ball_trajectory(
        temporally_supported_tracks,
        max_gap_seconds=max_gap_seconds,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    supported_foot_points = frozenset(
        point
        for track in supported_tracks
        for point in track.points
        if any(
            candidate.point == point
            and candidate.near_player_feet
            for candidate in candidates
        )
    )
    accepted = _resolve_detector_conflicts_by_attention(
        accepted,
        detector_candidates=filtered_candidate_objects,
        supported_foot_points=supported_foot_points,
        records=records,
        video=manifest.video,
        frame_step=frame_step,
    )
    accepted = _restore_plausible_detector_points(
        accepted,
        detector_candidates=filtered_candidate_objects,
        frame_step=frame_step,
        fps=manifest.fps,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        cell_size=static_cell_size,
        supported_foot_points=supported_foot_points,
    )
    accepted = _add_bidirectional_template_bridges(
        accepted,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
        maximum_gap_seconds=max_gap_seconds,
    )
    accepted = _add_terminal_template_bridges(
        accepted,
        candidates=filtered,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        maximum_gap_seconds=max_gap_seconds,
    )
    accepted = _add_forward_template_consensus(
        accepted,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
        maximum_gap_seconds=max_gap_seconds,
    )
    accepted, startup_attention_rejections = (
        _gate_unanchored_start_points_by_attention(
            accepted,
            records=records,
            video=manifest.video,
            width=width,
            height=height,
            fps=manifest.fps,
            frame_step=frame_step,
        )
    )
    accepted, raw_motion_diagnostics = _add_raw_motion_proposals(
        accepted,
        records=records,
        video=manifest.video,
        width=width,
        height=height,
        fps=manifest.fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        detector_candidates=filtered,
    )
    raw_motion_diagnostics = replace(
        raw_motion_diagnostics,
        startup_points_rejected=startup_attention_rejections,
    )
    accepted, kalman_reacquisition_diagnostics = (
        _add_kalman_guided_reacquisitions(
            accepted,
            detector_candidates=filtered,
            records=records,
            video=manifest.video,
            width=width,
            height=height,
            fps=manifest.fps,
            frame_step=frame_step,
        )
    )
    accepted, dense_flow_diagnostics = _add_dense_optical_flow_bridges(
        accepted,
        records=records,
        video=manifest.video,
        width=width,
        height=height,
        fps=manifest.fps,
        frame_step=frame_step,
    )
    accepted, rejected_outlier_frames = (
        _discard_unsupported_detector_outliers(
            accepted,
            records=records,
            video=manifest.video,
            fps=manifest.fps,
            frame_step=frame_step,
            max_gap_seconds=max_gap_seconds,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        )
    )
    accepted = _add_bracketed_outlier_motion_recoveries(
        accepted,
        records=records,
        video=manifest.video,
        width=width,
        height=height,
        fps=manifest.fps,
        frame_step=frame_step,
        rejected_frames=rejected_outlier_frames,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    accepted, discarded_temporal_upper_body_points = (
        _discard_temporal_upper_body_points(
            accepted,
            records_by_frame={
                int(record["source_frame"]): record for record in records
            },
        )
    )
    accepted = _deduplicate_track_frames(accepted)

    output.mkdir(parents=True, exist_ok=True)
    track_path = output / "ball-tracks.json"
    track_path.write_text(
        json.dumps(
            {
                "manifest": str(manifest.path),
                "cache": str(cache_path.resolve()),
                "cache_configuration": metadata,
                "analysis_window": _analysis_window(
                    analysis_start_seconds,
                    analysis_end_seconds,
                ),
                "static_cells": [
                    {"x": x * static_cell_size, "y": y * static_cell_size}
                    for x, y in sorted(static_cells)
                ],
                "unanchored_static_clusters": [
                    asdict(cluster)
                    for cluster in unanchored_static_clusters
                ],
                "tracks": [
                    {
                        "track_id": track.track_id,
                        "points": [asdict(point) for point in track.points],
                    }
                    for track in accepted
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_summary(
        output=output,
        records=records,
        raw_candidates=[candidate.point for candidate in candidates],
        pitch_candidate_count=len(pitch_candidates),
        filtered_candidates=filtered,
        candidate_conflict_frames=sum(
            count > 1 for count in filtered_candidate_counts.values()
        ),
        conflicting_candidates=sum(
            count - 1
            for count in filtered_candidate_counts.values()
            if count > 1
        ),
        upper_body_rejections=len(pitch_candidates) - len(candidates),
        global_static_rejections=global_static_rejections,
        unanchored_static_rejections=unanchored_static_rejections,
        tracks=accepted,
        unanchored_static_clusters=unanchored_static_clusters,
        associated_track_fragments=len(associated_tracks),
        supported_track_fragments=len(supported_tracks),
        discarded_static_fragments=discarded_static_fragments,
        discarded_temporal_upper_body_points=(
            discarded_temporal_upper_body_points
        ),
        raw_motion_diagnostics=raw_motion_diagnostics,
        kalman_reacquisition_diagnostics=(
            kalman_reacquisition_diagnostics
        ),
        dense_flow_diagnostics=dense_flow_diagnostics,
        analysis_start_seconds=analysis_start_seconds,
        analysis_end_seconds=analysis_end_seconds,
    )
    print(f"Ball tracks written to {track_path.resolve()}")
    return track_path


def _deduplicate_track_frames(
    tracks: Iterable[BallTrack],
) -> tuple[BallTrack, ...]:
    evidence_priority = {
        "detector": 6,
        "template_validated_detector": 5,
        "raw_motion_near_feet": 4,
        "raw_motion_trajectory_corridor": 4,
        "raw_motion_global_fallback": 4,
        "motion_circle": 4,
        "kalman_guided_yolo_candidate": 3,
        "kalman_guided_raw_motion_micro_crop": 3,
        "dense_bidirectional_optical_flow": 2,
        "bidirectional_template": 2,
        "partial_bidirectional_template": 2,
        "template_consensus": 2,
        "forward_template_consensus": 2,
        "stationary_bidirectional_template": 1,
    }
    deduplicated: list[BallTrack] = []
    for track in tracks:
        points_by_frame: dict[int, BallPoint] = {}
        for point in track.points:
            existing = points_by_frame.get(point.source_frame)
            if existing is None or (
                evidence_priority.get(point.evidence, 0),
                point.temporal_score or point.confidence,
            ) > (
                evidence_priority.get(existing.evidence, 0),
                existing.temporal_score or existing.confidence,
            ):
                points_by_frame[point.source_frame] = point
        deduplicated.append(
            BallTrack(
                track.track_id,
                sorted(
                    points_by_frame.values(),
                    key=lambda point: point.source_frame,
                ),
            )
        )
    return tuple(deduplicated)


def _supported_ball_tracks(
    tracks: Iterable[BallTrack],
    *,
    minimum_track_points: int,
    max_speed_pixels_per_second: float,
    minimum_short_fragment_confidence: float = 0.2,
    minimum_short_fragment_speed_ratio: float = 0.075,
    foot_supported_points: frozenset[BallPoint] = frozenset(),
) -> tuple[BallTrack, ...]:
    return tuple(
        track
        for track in tracks
        if len(track.points) >= minimum_track_points
        or (
            minimum_track_points == 3
            and _is_confident_moving_pair(
                track,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
                minimum_mean_confidence=minimum_short_fragment_confidence,
                minimum_speed_ratio=minimum_short_fragment_speed_ratio,
            )
            or (
                minimum_track_points == 3
                and any(
                    point in foot_supported_points
                    for point in track.points
                )
                and _is_confident_moving_pair(
                    track,
                    max_speed_pixels_per_second=(
                        max_speed_pixels_per_second
                    ),
                    minimum_mean_confidence=0.1,
                    minimum_speed_ratio=minimum_short_fragment_speed_ratio,
                )
            )
        )
    )


def _is_confident_moving_pair(
    track: BallTrack,
    *,
    max_speed_pixels_per_second: float,
    minimum_mean_confidence: float,
    minimum_speed_ratio: float,
) -> bool:
    if len(track.points) != 2:
        return False
    first, second = track.points
    elapsed = second.clip_seconds - first.clip_seconds
    if elapsed <= 0:
        return False
    mean_confidence = (first.confidence + second.confidence) / 2
    speed = hypot(second.x - first.x, second.y - first.y) / elapsed
    return (
        mean_confidence >= minimum_mean_confidence
        and speed >= max_speed_pixels_per_second * minimum_speed_ratio
    )


def select_single_ball_trajectory(
    tracks: Iterable[BallTrack],
    *,
    max_gap_seconds: float,
    max_speed_pixels_per_second: float,
    minimum_mean_confidence: float = 0.1,
) -> tuple[BallTrack, ...]:
    candidates = tuple(
        track
        for track in tracks
        if (
            sum(point.confidence for point in track.points)
            / len(track.points)
            >= minimum_mean_confidence
        )
    )
    if not candidates:
        return ()
    quality = {
        track.track_id: (
            sum(point.confidence for point in track.points) / len(track.points)
        )
        * len(track.points) ** 0.5
        for track in candidates
    }
    by_frame: dict[int, list[tuple[BallTrack, BallPoint]]] = {}
    for track in candidates:
        for point in track.points:
            by_frame.setdefault(point.source_frame, []).append((track, point))

    selected: list[BallPoint] = []
    current_track_id: int | None = None
    for frame in sorted(by_frame):
        frame_candidates = by_frame[frame]
        continuing = [
            candidate
            for candidate in frame_candidates
            if candidate[0].track_id == current_track_id
            and _point_transition_is_plausible(
                selected,
                candidate[1],
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            )
        ]
        if continuing:
            chosen_track, chosen_point = continuing[0]
        elif not selected or (
            frame_candidates[0][1].clip_seconds
            - selected[-1].clip_seconds
            > max_gap_seconds
        ):
            restart_candidates = (
                frame_candidates
                if not selected
                else [
                    candidate
                    for candidate in frame_candidates
                    if len(candidate[0].points) >= 3
                ]
            )
            if not restart_candidates:
                continue
            chosen_track, chosen_point = max(
                restart_candidates,
                key=lambda candidate: (
                quality[candidate[0].track_id],
                candidate[1].confidence,
                ),
            )
        else:
            reachable: list[tuple[float, BallTrack, BallPoint]] = []
            previous = selected[-1]
            for track, point in frame_candidates:
                elapsed = point.clip_seconds - previous.clip_seconds
                if elapsed <= 0:
                    continue
                maximum_distance = max(
                    35.0,
                    max_speed_pixels_per_second * elapsed,
                )
                distance = hypot(point.x - previous.x, point.y - previous.y)
                if (
                    distance <= maximum_distance
                    and _point_transition_is_plausible(
                        selected,
                        point,
                        max_speed_pixels_per_second=(
                            max_speed_pixels_per_second
                        ),
                    )
                ):
                    reachable.append(
                        (
                            quality[track.track_id]
                            - distance / maximum_distance,
                            track,
                            point,
                        )
                    )
            if not reachable:
                continue
            _, chosen_track, chosen_point = max(
                reachable,
                key=lambda candidate: (
                candidate[0],
                candidate[2].confidence,
                ),
            )
        selected.append(chosen_point)
        current_track_id = chosen_track.track_id
    return (BallTrack(track_id=1, points=selected),)


def _point_transition_is_plausible(
    selected: list[BallPoint],
    candidate: BallPoint,
    *,
    max_speed_pixels_per_second: float,
) -> bool:
    if not selected:
        return True
    previous = selected[-1]
    elapsed = candidate.clip_seconds - previous.clip_seconds
    if elapsed <= 0:
        return False
    outgoing_velocity = np.array(
        [candidate.x - previous.x, candidate.y - previous.y]
    ) / elapsed
    if np.linalg.norm(outgoing_velocity) > max_speed_pixels_per_second:
        return False
    if len(selected) < 2:
        return True
    earlier = selected[-2]
    incoming_seconds = previous.clip_seconds - earlier.clip_seconds
    if incoming_seconds <= 0:
        return False
    incoming_velocity = np.array(
        [previous.x - earlier.x, previous.y - earlier.y]
    ) / incoming_seconds
    acceleration_seconds = (incoming_seconds + elapsed) / 2
    return (
        np.linalg.norm(outgoing_velocity - incoming_velocity)
        / acceleration_seconds
        <= float(
            SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                "maximum_acceleration_pixels_per_second_squared"
            ]
        )
    )


def _resolve_detector_conflicts_by_attention(
    tracks: Iterable[BallTrack],
    *,
    detector_candidates: Iterable[_BallCandidate],
    supported_foot_points: frozenset[BallPoint],
    records: list[dict[str, Any]],
    video: Path,
    frame_step: int,
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    if not tracks or not supported_foot_points:
        return tracks
    candidates_by_frame: dict[int, list[_BallCandidate]] = defaultdict(list)
    for candidate in detector_candidates:
        candidates_by_frame[candidate.point.source_frame].append(candidate)
    selected_by_frame = {
        point.source_frame: point
        for track in tracks
        for point in track.points
    }
    records_by_frame = {
        int(record["source_frame"]): record for record in records
    }
    conflict_frames = [
        frame
        for frame, selected in selected_by_frame.items()
        if (
            len(candidates_by_frame[frame]) > 1
            and selected not in supported_foot_points
            and sum(
                candidate.point in supported_foot_points
                for candidate in candidates_by_frame[frame]
            )
            == 1
            and frame - frame_step in records_by_frame
            and frame + frame_step in records_by_frame
        )
    ]
    if not conflict_frames:
        return tracks
    required_frames = {
        frame + offset * frame_step
        for frame in conflict_frames
        for offset in (-1, 0, 1)
    }
    grayscale = _read_sampled_grayscale_frames(video, required_frames)
    replacements: dict[int, BallPoint] = {}
    for frame in conflict_frames:
        selected = selected_by_frame[frame]
        alternative = next(
            candidate.point
            for candidate in candidates_by_frame[frame]
            if candidate.point in supported_foot_points
        )
        cones = _player_attention_cones(
            grayscale[frame - frame_step],
            grayscale[frame],
            grayscale[frame + frame_step],
            records_by_frame[frame],
        )
        selected_support, selected_score = _attention_convergence(
            selected,
            cones,
        )
        alternative_support, alternative_score = _attention_convergence(
            alternative,
            cones,
        )
        if _attention_advantage_is_decisive(
            alternative_support=alternative_support,
            alternative_score=alternative_score,
            selected_support=selected_support,
            selected_score=selected_score,
        ):
            replacements[frame] = alternative
    if not replacements:
        return tracks
    return tuple(
        BallTrack(
            track.track_id,
            [
                replacements.get(point.source_frame, point)
                for point in track.points
            ],
        )
        for track in tracks
    )


def _attention_advantage_is_decisive(
    *,
    alternative_support: int,
    alternative_score: float,
    selected_support: int,
    selected_score: float,
) -> bool:
    return (
        alternative_support >= selected_support + 3
        and alternative_score >= selected_score + 0.75
    )


def _restore_plausible_detector_points(
    tracks: Iterable[BallTrack],
    *,
    detector_candidates: Iterable[_BallCandidate],
    frame_step: int,
    fps: float,
    max_speed_pixels_per_second: float,
    cell_size: int = 20,
    supported_foot_points: frozenset[BallPoint] = frozenset(),
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    if not tracks:
        return tracks
    detector_candidates = tuple(detector_candidates)
    anchored_cells = _player_anchored_cells(
        detector_candidates,
        cell_size=cell_size,
    )
    trusted = sorted(
        (point for track in tracks for point in track.points),
        key=lambda point: point.source_frame,
    )
    trusted_frames = {point.source_frame for point in trusted}
    trusted_cell_counts = Counter(
        _cell(point, cell_size)
        for point in trusted
        if point.source_attribution == "yolo26_observed"
    )
    confirmed_anchor_cells = {
        cell
        for cell, count in trusted_cell_counts.items()
        if count >= 3 and cell in anchored_cells
    }
    candidates_by_frame: dict[int, list[_BallCandidate]] = defaultdict(list)
    for candidate in detector_candidates:
        candidates_by_frame[candidate.point.source_frame].append(candidate)
    missing_anchored_frames: dict[tuple[int, int], set[int]] = defaultdict(set)
    for source_frame, candidates in candidates_by_frame.items():
        for candidate in candidates:
            cell = _cell(candidate.point, cell_size)
            if cell in anchored_cells:
                missing_anchored_frames[cell].add(source_frame)
    restored: list[BallPoint] = []
    for source_frame in sorted(candidates_by_frame):
        candidates = candidates_by_frame[source_frame]
        existing = next(
            (
                point
                for point in trusted
                if point.source_frame == source_frame
            ),
            None,
        )
        if existing is not None:
            continue
        repeated_anchored = [
            candidate
            for candidate in candidates
            if len(
                missing_anchored_frames[
                    _cell(candidate.point, cell_size)
                ]
            )
            >= 2
            and _cell(candidate.point, cell_size) in confirmed_anchor_cells
        ]
        if len(repeated_anchored) == 1:
            candidate = repeated_anchored[0].point
        elif len(candidates) == 1:
            candidate = candidates[0].point
            if not _has_local_restoration_support(
                candidate,
                trusted=trusted,
                frame_step=frame_step,
            ):
                continue
            bracketed_foot_contact = (
                candidate in supported_foot_points
                and _has_bracketed_restoration_support(
                    candidate,
                    trusted=trusted,
                    frame_step=frame_step,
                )
            )
            if not bracketed_foot_contact and not _point_path_is_plausible(
                candidate,
                trusted=trusted,
                frame_step=frame_step,
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            ):
                continue
        else:
            continue
        restored.append(candidate)
        trusted.append(candidate)
        trusted.sort(key=lambda point: point.source_frame)
    if not restored:
        return tracks
    return (
        BallTrack(
            tracks[0].track_id,
            sorted(
                [*tracks[0].points, *restored],
                key=lambda point: point.source_frame,
            ),
        ),
        *tracks[1:],
    )


def _has_local_restoration_support(
    point: BallPoint,
    *,
    trusted: list[BallPoint],
    frame_step: int,
) -> bool:
    if any(
        abs(candidate.source_frame - point.source_frame) <= frame_step
        for candidate in trusted
    ):
        return True
    has_previous = any(
        0 < point.source_frame - candidate.source_frame <= frame_step * 4
        for candidate in trusted
    )
    has_following = any(
        0 < candidate.source_frame - point.source_frame <= frame_step * 4
        for candidate in trusted
    )
    return has_previous and has_following


def _has_bracketed_restoration_support(
    point: BallPoint,
    *,
    trusted: list[BallPoint],
    frame_step: int,
) -> bool:
    return any(
        0 < point.source_frame - candidate.source_frame <= frame_step * 4
        for candidate in trusted
    ) and any(
        0 < candidate.source_frame - point.source_frame <= frame_step * 4
        for candidate in trusted
    )


def _associate_tracks(
    points: Iterable[BallPoint],
    *,
    max_gap_seconds: float,
    max_speed_pixels_per_second: float,
) -> tuple[BallTrack, ...]:
    by_frame: dict[int, list[BallPoint]] = {}
    for point in points:
        by_frame.setdefault(point.source_frame, []).append(point)

    tracks: list[BallTrack] = []
    next_track_id = 1
    for frame_points in by_frame.values():
        timestamp = frame_points[0].clip_seconds
        active = [
            track
            for track in tracks
            if timestamp - track.last.clip_seconds <= max_gap_seconds
        ]
        pairs: list[tuple[float, int, int]] = []
        for track_index, track in enumerate(active):
            predicted_x, predicted_y = track.predicted_center(timestamp)
            elapsed = timestamp - track.last.clip_seconds
            max_distance = max(35.0, max_speed_pixels_per_second * elapsed)
            for point_index, point in enumerate(frame_points):
                distance = hypot(point.x - predicted_x, point.y - predicted_y)
                if distance <= max_distance:
                    pairs.append((distance, track_index, point_index))

        assigned_tracks: set[int] = set()
        assigned_points: set[int] = set()
        for _, track_index, point_index in sorted(pairs):
            if track_index in assigned_tracks or point_index in assigned_points:
                continue
            active[track_index].points.append(frame_points[point_index])
            assigned_tracks.add(track_index)
            assigned_points.add(point_index)

        for point_index, point in enumerate(frame_points):
            if point_index not in assigned_points:
                tracks.append(BallTrack(next_track_id, [point]))
                next_track_id += 1
    return tuple(tracks)


def interpolate_track_gaps(
    track: BallTrack,
    *,
    frame_step: int,
    fps: float,
    maximum_gap_seconds: float,
) -> BallTrack:
    if frame_step < 1 or fps <= 0 or maximum_gap_seconds <= 0:
        raise ValueError("Interpolation frame step, FPS, and gap must be positive")
    ordered = sorted(track.points, key=lambda point: point.source_frame)
    if len(ordered) < 2:
        return BallTrack(track.track_id, ordered)
    points: list[BallPoint] = []
    for index, (first, second) in enumerate(zip(ordered, ordered[1:])):
        points.append(first)
        frame_gap = second.source_frame - first.source_frame
        time_gap = second.clip_seconds - first.clip_seconds
        if frame_gap <= frame_step or time_gap > maximum_gap_seconds + 1e-6:
            continue
        if index > 0:
            previous = ordered[index - 1]
            incoming_x = first.x - previous.x
            incoming_y = first.y - previous.y
            bridge_x = second.x - first.x
            bridge_y = second.y - first.y
            if incoming_x * bridge_x + incoming_y * bridge_y <= 0:
                continue
        for source_frame in range(
            first.source_frame + frame_step,
            second.source_frame,
            frame_step,
        ):
            alpha = (source_frame - first.source_frame) / frame_gap
            points.append(
                BallPoint(
                    source_frame=source_frame,
                    clip_seconds=round(
                        first.clip_seconds
                        + (source_frame - first.source_frame) / fps,
                        3,
                    ),
                    confidence=round(
                        min(first.confidence, second.confidence) * 0.75,
                        6,
                    ),
                    x=first.x + (second.x - first.x) * alpha,
                    y=first.y + (second.y - first.y) * alpha,
                    interpolated=True,
                    evidence="interpolated",
                    source_attribution="interpolated",
                )
            )
    points.append(ordered[-1])
    return BallTrack(track.track_id, sorted(points, key=lambda point: point.source_frame))


def _add_template_supported_points(
    tracks: Iterable[BallTrack],
    *,
    video: Path,
    fps: float,
    frame_step: int,
    maximum_gap_seconds: float,
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    plans = [
        plan
        for track_index, track in enumerate(tracks)
        for plan in _template_bridge_plans(
            track,
            track_index=track_index,
            fps=fps,
            frame_step=frame_step,
            maximum_gap_seconds=maximum_gap_seconds,
        )
    ]
    if not plans:
        return tracks

    plans_by_anchor_frame: dict[int, list[tuple[int, BallPoint]]] = defaultdict(
        list
    )
    plans_by_target_frame: dict[int, list[int]] = defaultdict(list)
    for plan_index, plan in enumerate(plans):
        for point in plan.template_points:
            plans_by_anchor_frame[point.source_frame].append(
                (plan_index, point)
            )
        plans_by_target_frame[plan.target_frame].append(plan_index)

    templates: dict[int, list[tuple[BallPoint, np.ndarray]]] = defaultdict(list)
    additions: dict[int, list[BallPoint]] = defaultdict(list)
    required_frames = set(plans_by_anchor_frame) | set(plans_by_target_frame)
    last_required_frame = max(required_frames)
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        for source_frame in range(last_required_frame + 1):
            if source_frame not in required_frames:
                if not capture.grab():
                    raise RuntimeError(
                        f"Could not skip to source frame {source_frame} in {video}"
                    )
                continue
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(
                    f"Could not read source frame {source_frame} from {video}"
                )
            grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            for plan_index, point in plans_by_anchor_frame.get(
                source_frame,
                [],
            ):
                template = _extract_ball_template(grayscale, point)
                if template is not None:
                    templates[plan_index].append((point, template))
            for plan_index in plans_by_target_frame.get(source_frame, []):
                point = _template_consensus_point(
                    plans[plan_index],
                    templates[plan_index],
                    grayscale,
                    fps=fps,
                )
                if point is not None:
                    additions[plans[plan_index].track_index].append(point)
    finally:
        capture.release()

    return tuple(
        BallTrack(
            track.track_id,
            sorted(
                [*track.points, *additions[track_index]],
                key=lambda point: point.source_frame,
            ),
        )
        for track_index, track in enumerate(tracks)
    )


def _template_bridge_plans(
    track: BallTrack,
    *,
    track_index: int,
    fps: float,
    frame_step: int,
    maximum_gap_seconds: float,
    maximum_template_history_points: int = 8,
) -> tuple[_TemplateBridge, ...]:
    if frame_step < 1 or fps <= 0 or maximum_gap_seconds <= 0:
        raise ValueError("Template bridge frame step, FPS, and gap must be positive")
    if maximum_template_history_points < 3:
        raise ValueError("Template bridge needs at least three history points")

    plans: list[_TemplateBridge] = []
    ordered = sorted(
        (
            point
            for point in track.points
            if point.evidence == "detector"
        ),
        key=lambda point: point.source_frame,
    )
    for index, (first, second) in enumerate(zip(ordered, ordered[1:])):
        frame_gap = second.source_frame - first.source_frame
        time_gap = second.clip_seconds - first.clip_seconds
        if (
            frame_gap <= frame_step
            or time_gap > maximum_gap_seconds + 1e-6
        ):
            continue
        if index > 0:
            previous = ordered[index - 1]
            incoming_x = first.x - previous.x
            incoming_y = first.y - previous.y
            bridge_x = second.x - first.x
            bridge_y = second.y - first.y
            if incoming_x * bridge_x + incoming_y * bridge_y <= 0:
                continue
        template_points = tuple(
            ordered[
                max(0, index - maximum_template_history_points + 1) : index + 1
            ]
        )
        if len(template_points) < 3:
            continue
        for target_frame in range(
            first.source_frame + frame_step,
            second.source_frame,
            frame_step,
        ):
            plans.append(
                _TemplateBridge(
                    track_index=track_index,
                    first=first,
                    second=second,
                    target_frame=target_frame,
                    template_points=template_points,
                )
            )
    return tuple(plans)


def _extract_ball_template(
    grayscale: np.ndarray,
    point: BallPoint,
    *,
    radius_scale: float = 1.0,
) -> np.ndarray | None:
    if radius_scale <= 0:
        raise ValueError("Template radius scale must be positive")
    radius = max(4, round(point.box_diagonal * radius_scale))
    center_x = round(point.x)
    center_y = round(point.y)
    left = center_x - radius
    right = center_x + radius + 1
    top = center_y - radius
    bottom = center_y + radius + 1
    if left < 0 or top < 0 or right > grayscale.shape[1] or bottom > grayscale.shape[0]:
        return None
    return grayscale[top:bottom, left:right]


def _template_consensus_point(
    plan: _TemplateBridge,
    templates: Iterable[tuple[BallPoint, np.ndarray]],
    target_grayscale: np.ndarray,
    *,
    fps: float,
    minimum_template_score: float = 0.45,
    minimum_consensus_templates: int = 3,
    search_radius_diameters: float = 4.0,
    consensus_radius_diameters: float = 1.0,
) -> BallPoint | None:
    if fps <= 0:
        raise ValueError("Template consensus FPS must be positive")
    if minimum_consensus_templates < 1:
        raise ValueError("Template consensus requires at least one template")
    if not 0 <= minimum_template_score <= 1:
        raise ValueError("Template score threshold must be between 0 and 1")
    if search_radius_diameters <= 0 or consensus_radius_diameters <= 0:
        raise ValueError("Template search and consensus radii must be positive")

    anchor_diameters = [
        point.box_diagonal
        for point in plan.template_points
        if point.box_diagonal > 0
    ]
    if not anchor_diameters:
        return None
    reference_diameter = median(anchor_diameters)
    alpha = (
        (plan.target_frame - plan.first.source_frame)
        / (plan.second.source_frame - plan.first.source_frame)
    )
    predicted_x = plan.first.x + (plan.second.x - plan.first.x) * alpha
    predicted_y = plan.first.y + (plan.second.y - plan.first.y) * alpha
    search_radius = max(
        16,
        round(reference_diameter * search_radius_diameters),
    )
    matches = [
        match
        for _, template in templates
        if (
            match := _template_match(
                target_grayscale,
                template,
                predicted_x=predicted_x,
                predicted_y=predicted_y,
                search_radius=search_radius,
            )
        ).score
        >= minimum_template_score
    ]
    consensus = _largest_template_consensus(
        matches,
        maximum_distance=reference_diameter * consensus_radius_diameters,
    )
    if len(consensus) < minimum_consensus_templates:
        return None

    total_score = sum(match.score for match in consensus)
    center_x = sum(match.x * match.score for match in consensus) / total_score
    center_y = sum(match.y * match.score for match in consensus) / total_score
    return BallPoint(
        source_frame=plan.target_frame,
        clip_seconds=round(
            plan.first.clip_seconds
            + (plan.target_frame - plan.first.source_frame) / fps,
            3,
        ),
        confidence=min(plan.first.confidence, plan.second.confidence),
        x=center_x,
        y=center_y,
        box_diagonal=reference_diameter,
        evidence="template_consensus",
        temporal_score=round(
            min(match.score for match in consensus),
            6,
        ),
        source_attribution="temporal_detector_observed",
    )


def _template_match(
    target_grayscale: np.ndarray,
    template: np.ndarray,
    *,
    predicted_x: float,
    predicted_y: float,
    search_radius: int,
) -> _TemplateMatch:
    template_height, template_width = template.shape
    center_x = round(predicted_x)
    center_y = round(predicted_y)
    left = max(0, center_x - search_radius - template_width)
    right = min(
        target_grayscale.shape[1],
        center_x + search_radius + template_width + 1,
    )
    top = max(0, center_y - search_radius - template_height)
    bottom = min(
        target_grayscale.shape[0],
        center_y + search_radius + template_height + 1,
    )
    search = target_grayscale[top:bottom, left:right]
    if (
        search.shape[0] < template_height
        or search.shape[1] < template_width
    ):
        return _TemplateMatch(
            x=predicted_x,
            y=predicted_y,
            score=-1.0,
        )
    scores = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(scores)
    return _TemplateMatch(
        x=left + location[0] + (template_width - 1) / 2,
        y=top + location[1] + (template_height - 1) / 2,
        score=float(score),
    )


def _largest_template_consensus(
    matches: Iterable[_TemplateMatch],
    *,
    maximum_distance: float,
) -> tuple[_TemplateMatch, ...]:
    groups: list[list[_TemplateMatch]] = []
    for match in sorted(
        matches,
        key=lambda item: (-item.score, item.x, item.y),
    ):
        for group in groups:
            total_score = sum(item.score for item in group)
            center_x = sum(item.x * item.score for item in group) / total_score
            center_y = sum(item.y * item.score for item in group) / total_score
            if hypot(match.x - center_x, match.y - center_y) <= maximum_distance:
                group.append(match)
                break
        else:
            groups.append([match])
    if not groups:
        return ()
    best = max(
        groups,
        key=lambda group: (
            len(group),
            sum(item.score for item in group),
        ),
    )
    return tuple(best)


def _add_bidirectional_template_bridges(
    tracks: Iterable[BallTrack],
    *,
    video: Path,
    fps: float,
    frame_step: int,
    maximum_gap_seconds: float,
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    plans = [
        plan
        for track_index, track in enumerate(tracks)
        for plan in _bidirectional_template_bridge_plans(
            track,
            track_index=track_index,
            fps=fps,
            frame_step=frame_step,
            maximum_gap_seconds=maximum_gap_seconds,
        )
    ]
    if not plans:
        return tracks

    frame_uses: dict[int, int] = defaultdict(int)
    plans_by_end_frame: dict[int, list[int]] = defaultdict(list)
    for plan_index, plan in enumerate(plans):
        for source_frame in plan.frames:
            frame_uses[source_frame] += 1
        plans_by_end_frame[plan.second.source_frame].append(plan_index)

    additions: dict[int, list[BallPoint]] = defaultdict(list)
    grayscale_frames: dict[int, np.ndarray] = {}
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        for source_frame in range(max(frame_uses) + 1):
            if source_frame not in frame_uses:
                if not capture.grab():
                    raise RuntimeError(
                        f"Could not skip to source frame {source_frame} in {video}"
                    )
                continue
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(
                    f"Could not read source frame {source_frame} from {video}"
                )
            grayscale_frames[source_frame] = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2GRAY,
            )
            for plan_index in plans_by_end_frame.get(source_frame, []):
                plan = plans[plan_index]
                additions[plan.track_index].extend(
                    _bidirectional_template_points(
                        plan,
                        {
                            frame: grayscale_frames[frame]
                            for frame in plan.frames
                        },
                        fps=fps,
                    )
                )
                for frame in plan.frames:
                    frame_uses[frame] -= 1
                    if frame_uses[frame] == 0:
                        del grayscale_frames[frame]
    finally:
        capture.release()

    return tuple(
        BallTrack(
            track.track_id,
            sorted(
                [*track.points, *additions[track_index]],
                key=lambda point: point.source_frame,
            ),
        )
        for track_index, track in enumerate(tracks)
    )


def _bidirectional_template_bridge_plans(
    track: BallTrack,
    *,
    track_index: int,
    fps: float,
    frame_step: int,
    maximum_gap_seconds: float,
) -> tuple[_BidirectionalTemplateBridge, ...]:
    if frame_step < 1 or fps <= 0 or maximum_gap_seconds <= 0:
        raise ValueError("Bidirectional bridge frame step, FPS, and gap must be positive")
    points = sorted(
        (
            point
            for point in track.points
            if point.evidence == "detector"
        ),
        key=lambda point: point.source_frame,
    )
    maximum_bridge_seconds = maximum_gap_seconds + frame_step / fps
    plans: list[_BidirectionalTemplateBridge] = []
    for index, (first, second) in enumerate(zip(points, points[1:])):
        time_gap = second.clip_seconds - first.clip_seconds
        is_stationary_bridge = _is_long_stationary_template_bridge(
            points,
            first_index=index,
            second=second,
            fps=fps,
        )
        if (
            second.source_frame - first.source_frame <= frame_step
            or (
                time_gap > maximum_bridge_seconds + 1e-6
                and not is_stationary_bridge
            )
            or first.box_diagonal <= 0
            or second.box_diagonal <= 0
        ):
            continue
        previous = points[index - 1] if index > 0 else None
        if (
            previous is not None
            and first.source_frame - previous.source_frame != frame_step
        ):
            previous = None
        following = points[index + 2] if index + 2 < len(points) else None
        if (
            following is not None
            and following.source_frame - second.source_frame != frame_step
        ):
            following = None
        plans.append(
            _BidirectionalTemplateBridge(
                track_index=track_index,
                frame_step=frame_step,
                previous=previous,
                first=first,
                second=second,
                following=following,
                bridge_kind=(
                    "long_stationary"
                    if (
                        time_gap > maximum_bridge_seconds + 1e-6
                        and is_stationary_bridge
                    )
                    else "short_motion"
                ),
            )
        )
    return tuple(plans)


def _is_long_stationary_template_bridge(
    points: list[BallPoint],
    *,
    first_index: int,
    second: BallPoint,
    fps: float,
) -> bool:
    profile = LONG_STATIONARY_TEMPLATE_PROFILE
    first = points[first_index]
    time_gap = second.clip_seconds - first.clip_seconds
    if (
        time_gap <= 0
        or time_gap > float(profile["maximum_bridge_seconds"]) + 1e-6
        or first.box_diagonal <= 0
        or second.box_diagonal <= 0
    ):
        return False

    minimum_history_points = int(profile["minimum_history_points"])
    history = points[
        max(0, first_index - minimum_history_points + 1) : first_index + 1
    ]
    if len(history) < minimum_history_points:
        return False
    maximum_history_gap = round(
        float(profile["maximum_history_gap_seconds"]) * fps
    )
    if any(
        current.source_frame - previous.source_frame > maximum_history_gap
        for previous, current in zip(history, history[1:])
    ):
        return False
    if (
        history[-1].clip_seconds - history[0].clip_seconds
        < float(profile["minimum_history_seconds"])
    ):
        return False

    reference_diameter = median(
        point.box_diagonal
        for point in (*history, second)
        if point.box_diagonal > 0
    )
    maximum_history_radius = (
        reference_diameter
        * float(profile["maximum_history_radius_ball_diameters"])
    )
    center_x = median(point.x for point in history)
    center_y = median(point.y for point in history)
    if any(
        hypot(point.x - center_x, point.y - center_y)
        > maximum_history_radius
        for point in history
    ):
        return False

    maximum_endpoint_distance = (
        reference_diameter
        * float(profile["maximum_endpoint_distance_ball_diameters"])
    )
    return (
        hypot(second.x - center_x, second.y - center_y)
        <= maximum_endpoint_distance
    )


def _bidirectional_template_points(
    plan: _BidirectionalTemplateBridge,
    grayscale_frames: dict[int, np.ndarray],
    *,
    fps: float,
    minimum_template_score: float = 0.65,
    maximum_agreement_diameters: float = 0.75,
) -> tuple[BallPoint, ...]:
    if fps <= 0:
        raise ValueError("Bidirectional template bridge FPS must be positive")
    if not 0 <= minimum_template_score <= 1:
        raise ValueError("Bidirectional template score must be between 0 and 1")
    if maximum_agreement_diameters <= 0:
        raise ValueError("Bidirectional template agreement must be positive")

    reference_diameter = median(
        (plan.first.box_diagonal, plan.second.box_diagonal)
    )
    search_radius = max(16, round(reference_diameter * 4))
    forward = _follow_template(
        plan,
        grayscale_frames,
        seed=plan.first,
        neighbor=plan.previous,
        direction=1,
        search_radius=search_radius,
    )
    backward = _follow_template(
        plan,
        grayscale_frames,
        seed=plan.second,
        neighbor=plan.following,
        direction=-1,
        search_radius=search_radius,
    )
    if not forward or not backward:
        return ()

    maximum_distance = reference_diameter * maximum_agreement_diameters
    first_frame = plan.first.source_frame
    second_frame = plan.second.source_frame
    if (
        forward[second_frame].score < minimum_template_score
        or backward[first_frame].score < minimum_template_score
        or _template_distance(forward[second_frame], plan.second)
        > maximum_distance
        or _template_distance(backward[first_frame], plan.first)
        > maximum_distance
    ):
        return ()

    points: list[BallPoint] = []
    for source_frame in plan.frames[1:-1]:
        forward_match = forward[source_frame]
        backward_match = backward[source_frame]
        if (
            forward_match.score < minimum_template_score
            or backward_match.score < minimum_template_score
            or hypot(
                forward_match.x - backward_match.x,
                forward_match.y - backward_match.y,
            )
            > maximum_distance
        ):
            return ()
        total_score = forward_match.score + backward_match.score
        points.append(
            BallPoint(
                source_frame=source_frame,
                clip_seconds=round(
                    plan.first.clip_seconds
                    + (source_frame - first_frame) / fps,
                    3,
                ),
                confidence=min(
                    plan.first.confidence,
                    plan.second.confidence,
                ),
                x=(
                    forward_match.x * forward_match.score
                    + backward_match.x * backward_match.score
                )
                / total_score,
                y=(
                    forward_match.y * forward_match.score
                    + backward_match.y * backward_match.score
                )
                / total_score,
                box_diagonal=reference_diameter,
                evidence=(
                    "stationary_bidirectional_template"
                    if plan.bridge_kind == "long_stationary"
                    else "bidirectional_template"
                ),
                temporal_score=round(
                    min(forward_match.score, backward_match.score),
                    6,
                ),
                source_attribution="temporal_detector_observed",
            )
        )
    return tuple(points)


def _follow_template(
    plan: _BidirectionalTemplateBridge,
    grayscale_frames: dict[int, np.ndarray],
    *,
    seed: BallPoint,
    neighbor: BallPoint | None,
    direction: int,
    search_radius: int,
    template_radius_scale: float = 1.0,
) -> dict[int, _TemplateMatch]:
    if direction not in {-1, 1}:
        raise ValueError("Template direction must be either -1 or 1")
    if template_radius_scale <= 0:
        raise ValueError("Template radius scale must be positive")
    template = _extract_ball_template(
        grayscale_frames[seed.source_frame],
        seed,
        radius_scale=template_radius_scale,
    )
    if template is None:
        return {}
    if neighbor is None:
        velocity_x = velocity_y = 0.0
    else:
        frame_span = abs(seed.source_frame - neighbor.source_frame)
        velocity_x = (
            seed.x - neighbor.x
        ) / (frame_span / plan.frame_step)
        velocity_y = (
            seed.y - neighbor.y
        ) / (frame_span / plan.frame_step)

    positions: dict[int, _TemplateMatch] = {
        seed.source_frame: _TemplateMatch(
            x=seed.x,
            y=seed.y,
            score=1.0,
        )
    }
    source_frames = (
        plan.frames
        if direction > 0
        else tuple(reversed(plan.frames))
    )
    previous = positions[seed.source_frame]
    for source_frame in source_frames[1:]:
        match = _template_match(
            grayscale_frames[source_frame],
            template,
            predicted_x=previous.x + velocity_x,
            predicted_y=previous.y + velocity_y,
            search_radius=search_radius,
        )
        velocity_x = match.x - previous.x
        velocity_y = match.y - previous.y
        positions[source_frame] = match
        previous = match
    return positions


def _template_distance(match: _TemplateMatch, point: BallPoint) -> float:
    return hypot(match.x - point.x, match.y - point.y)


def _add_terminal_template_bridges(
    tracks: Iterable[BallTrack],
    *,
    candidates: Iterable[BallPoint],
    video: Path,
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
    maximum_gap_seconds: float,
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    plans = _terminal_template_bridge_plans(
        tracks,
        candidates=candidates,
        fps=fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        maximum_gap_seconds=maximum_gap_seconds,
    )
    if not plans:
        return tracks

    frame_uses: dict[int, int] = defaultdict(int)
    plans_by_end_frame: dict[int, list[int]] = defaultdict(list)
    for plan_index, plan in enumerate(plans):
        for source_frame in plan.frames:
            frame_uses[source_frame] += 1
        plans_by_end_frame[plan.second.source_frame].append(plan_index)

    additions: dict[int, list[BallPoint]] = defaultdict(list)
    grayscale_frames: dict[int, np.ndarray] = {}
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        for source_frame in range(max(frame_uses) + 1):
            if source_frame not in frame_uses:
                if not capture.grab():
                    raise RuntimeError(
                        f"Could not skip to source frame {source_frame} in {video}"
                    )
                continue
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(
                    f"Could not read source frame {source_frame} from {video}"
                )
            grayscale_frames[source_frame] = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2GRAY,
            )
            for plan_index in plans_by_end_frame.get(source_frame, []):
                plan = plans[plan_index]
                additions[plan.track_index].extend(
                    _partial_bidirectional_template_points(
                        plan,
                        {
                            frame: grayscale_frames[frame]
                            for frame in plan.frames
                        },
                        fps=fps,
                    )
                )
                for frame in plan.frames:
                    frame_uses[frame] -= 1
                    if frame_uses[frame] == 0:
                        del grayscale_frames[frame]
    finally:
        capture.release()

    return tuple(
        BallTrack(
            track.track_id,
            sorted(
                [*track.points, *additions[track_index]],
                key=lambda point: point.source_frame,
            ),
        )
        for track_index, track in enumerate(tracks)
    )


def _terminal_template_bridge_plans(
    tracks: Iterable[BallTrack],
    *,
    candidates: Iterable[BallPoint],
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
    maximum_gap_seconds: float,
    maximum_bridge_sample_steps: int = 6,
    maximum_endpoint_scale_ratio: float = 2.0,
) -> tuple[_BidirectionalTemplateBridge, ...]:
    if (
        frame_step < 1
        or fps <= 0
        or max_speed_pixels_per_second <= 0
        or maximum_gap_seconds <= 0
    ):
        raise ValueError("Terminal template bridge settings must be positive")
    if maximum_bridge_sample_steps < 2:
        raise ValueError("Terminal template bridge needs at least two sampled steps")
    if maximum_endpoint_scale_ratio < 1:
        raise ValueError(
            "Terminal template bridge endpoint scale ratio must be at least one"
        )

    selected_frames = {
        point.source_frame
        for track in tracks
        for point in track.points
        if point.evidence == "detector"
    }
    candidates_by_frame: dict[int, list[BallPoint]] = defaultdict(list)
    for candidate in candidates:
        if candidate.source_frame not in selected_frames:
            candidates_by_frame[candidate.source_frame].append(candidate)

    maximum_bridge_seconds = maximum_bridge_sample_steps * frame_step / fps
    plans: list[_BidirectionalTemplateBridge] = []
    for track_index, track in enumerate(tracks):
        points = sorted(
            (
                point
                for point in track.points
                if point.evidence == "detector"
            ),
            key=lambda point: point.source_frame,
        )
        for index, first in enumerate(points[:-1]):
            if first.box_diagonal <= 0:
                continue
            following_selected = points[index + 1]
            if (
                following_selected.clip_seconds - first.clip_seconds
                <= maximum_gap_seconds
            ):
                continue
            previous = points[index - 1] if index > 0 else None
            if (
                previous is not None
                and first.source_frame - previous.source_frame != frame_step
            ):
                previous = None
            for second_frame in sorted(candidates_by_frame):
                frame_gap = second_frame - first.source_frame
                if (
                    frame_gap <= frame_step
                    or frame_gap % frame_step
                    or frame_gap / frame_step > maximum_bridge_sample_steps
                    or second_frame >= following_selected.source_frame
                ):
                    continue
                for second in candidates_by_frame[second_frame]:
                    if second.box_diagonal <= 0:
                        continue
                    time_gap = second.clip_seconds - first.clip_seconds
                    if time_gap > maximum_bridge_seconds + 1e-6:
                        continue
                    scale_ratio = max(
                        first.box_diagonal / second.box_diagonal,
                        second.box_diagonal / first.box_diagonal,
                    )
                    speed = hypot(second.x - first.x, second.y - first.y) / time_gap
                    if (
                        scale_ratio > maximum_endpoint_scale_ratio
                        or speed > max_speed_pixels_per_second
                    ):
                        continue
                    plans.append(
                        _BidirectionalTemplateBridge(
                            track_index=track_index,
                            frame_step=frame_step,
                            previous=previous,
                            first=first,
                            second=second,
                            following=None,
                        )
                    )
    return tuple(plans)


def _partial_bidirectional_template_points(
    plan: _BidirectionalTemplateBridge,
    grayscale_frames: dict[int, np.ndarray],
    *,
    fps: float,
    minimum_template_score: float = 0.55,
    minimum_endpoint_score: float = 0.65,
    maximum_agreement_diameters: float = 0.75,
) -> tuple[BallPoint, ...]:
    if fps <= 0:
        raise ValueError("Partial template bridge FPS must be positive")
    if not 0 <= minimum_template_score <= 1:
        raise ValueError("Partial template score must be between 0 and 1")
    if not 0 <= minimum_endpoint_score <= 1:
        raise ValueError("Partial template endpoint score must be between 0 and 1")
    if maximum_agreement_diameters <= 0:
        raise ValueError("Partial template agreement must be positive")

    reference_diameter = median(
        (plan.first.box_diagonal, plan.second.box_diagonal)
    )
    search_radius = max(16, round(reference_diameter * 6))
    forward = _follow_template(
        plan,
        grayscale_frames,
        seed=plan.first,
        neighbor=plan.previous,
        direction=1,
        search_radius=search_radius,
        template_radius_scale=0.75,
    )
    backward = _follow_template(
        plan,
        grayscale_frames,
        seed=plan.second,
        neighbor=plan.following,
        direction=-1,
        search_radius=search_radius,
        template_radius_scale=0.75,
    )
    if not forward or not backward:
        return ()

    maximum_distance = reference_diameter * maximum_agreement_diameters
    first_frame = plan.first.source_frame
    second_frame = plan.second.source_frame
    if (
        forward[second_frame].score < minimum_endpoint_score
        or backward[first_frame].score < minimum_endpoint_score
        or _template_distance(forward[second_frame], plan.second)
        > maximum_distance
        or _template_distance(backward[first_frame], plan.first)
        > maximum_distance
    ):
        return ()

    points: list[BallPoint] = []
    for source_frame in plan.frames[1:-1]:
        forward_match = forward[source_frame]
        backward_match = backward[source_frame]
        if (
            forward_match.score < minimum_template_score
            or backward_match.score < minimum_template_score
            or hypot(
                forward_match.x - backward_match.x,
                forward_match.y - backward_match.y,
            )
            > maximum_distance
        ):
            continue
        total_score = forward_match.score + backward_match.score
        points.append(
            BallPoint(
                source_frame=source_frame,
                clip_seconds=round(
                    plan.first.clip_seconds
                    + (source_frame - first_frame) / fps,
                    3,
                ),
                confidence=min(
                    plan.first.confidence,
                    plan.second.confidence,
                ),
                x=(
                    forward_match.x * forward_match.score
                    + backward_match.x * backward_match.score
                )
                / total_score,
                y=(
                    forward_match.y * forward_match.score
                    + backward_match.y * backward_match.score
                )
                / total_score,
                box_diagonal=reference_diameter,
                evidence="partial_bidirectional_template",
                temporal_score=round(
                    min(forward_match.score, backward_match.score),
                    6,
                ),
                source_attribution="temporal_detector_observed",
            )
        )
    if not points:
        return ()
    points.append(
        BallPoint(
            source_frame=second_frame,
            clip_seconds=plan.second.clip_seconds,
            confidence=plan.second.confidence,
            x=plan.second.x,
            y=plan.second.y,
            box_diagonal=plan.second.box_diagonal,
            evidence="template_validated_detector",
            temporal_score=round(
                min(
                    forward[second_frame].score,
                    backward[first_frame].score,
                ),
                6,
            ),
            source_attribution="temporal_detector_observed",
        )
    )
    return tuple(points)


def _add_forward_template_consensus(
    tracks: Iterable[BallTrack],
    *,
    video: Path,
    fps: float,
    frame_step: int,
    maximum_gap_seconds: float,
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    plans = [
        plan
        for track_index, track in enumerate(tracks)
        for plan in _forward_template_plans(
            track,
            track_index=track_index,
            fps=fps,
            frame_step=frame_step,
            maximum_gap_seconds=maximum_gap_seconds,
        )
    ]
    if not plans:
        return tracks

    frame_uses: dict[int, int] = defaultdict(int)
    plans_by_end_frame: dict[int, list[int]] = defaultdict(list)
    for plan_index, plan in enumerate(plans):
        for source_frame in plan.frames:
            frame_uses[source_frame] += 1
        plans_by_end_frame[plan.target_frames[-1]].append(plan_index)

    additions: dict[int, list[BallPoint]] = defaultdict(list)
    grayscale_frames: dict[int, np.ndarray] = {}
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        for source_frame in range(max(frame_uses) + 1):
            if source_frame not in frame_uses:
                if not capture.grab():
                    raise RuntimeError(
                        f"Could not skip to source frame {source_frame} in {video}"
                    )
                continue
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(
                    f"Could not read source frame {source_frame} from {video}"
                )
            grayscale_frames[source_frame] = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2GRAY,
            )
            for plan_index in plans_by_end_frame.get(source_frame, []):
                plan = plans[plan_index]
                additions[plan.track_index].extend(
                    _forward_template_consensus_points(
                        plan,
                        {
                            frame: grayscale_frames[frame]
                            for frame in plan.frames
                        },
                        fps=fps,
                    )
                )
                for frame in plan.frames:
                    frame_uses[frame] -= 1
                    if frame_uses[frame] == 0:
                        del grayscale_frames[frame]
    finally:
        capture.release()

    return tuple(
        BallTrack(
            track.track_id,
            sorted(
                [*track.points, *additions[track_index]],
                key=lambda point: point.source_frame,
            ),
        )
        for track_index, track in enumerate(tracks)
    )


def _forward_template_plans(
    track: BallTrack,
    *,
    track_index: int,
    fps: float,
    frame_step: int,
    maximum_gap_seconds: float,
    maximum_propagated_sample_steps: int = 7,
    maximum_template_history_points: int = 8,
    minimum_template_seed_score: float = 0.65,
) -> tuple[_ForwardTemplatePlan, ...]:
    if frame_step < 1 or fps <= 0 or maximum_gap_seconds <= 0:
        raise ValueError("Forward template frame step, FPS, and gap must be positive")
    if maximum_propagated_sample_steps < 1:
        raise ValueError("Forward template propagation needs at least one step")
    if maximum_template_history_points < 3:
        raise ValueError("Forward template propagation needs three history points")
    if not 0 <= minimum_template_seed_score <= 1:
        raise ValueError("Forward template seed score must be between 0 and 1")

    ordered = sorted(track.points, key=lambda point: point.source_frame)
    plans: list[_ForwardTemplatePlan] = []
    for index, seed in enumerate(ordered[:-1]):
        if seed.evidence != "template_validated_detector":
            continue
        following = ordered[index + 1]
        if (
            following.source_frame - seed.source_frame <= frame_step
            or following.clip_seconds - seed.clip_seconds
            <= maximum_gap_seconds
        ):
            continue
        previous = ordered[index - 1] if index > 0 else None
        if previous is None:
            continue
        template_points = tuple(
            point
            for point in ordered[
                max(0, index - maximum_template_history_points + 1) : index + 1
            ]
            if _is_reliable_template_seed(
                point,
                minimum_template_seed_score=minimum_template_seed_score,
            )
        )
        if len(template_points) < 3:
            continue
        end_frame = min(
            following.source_frame,
            seed.source_frame
            + frame_step * (maximum_propagated_sample_steps + 1),
        )
        target_frames = tuple(
            range(
                seed.source_frame + frame_step,
                end_frame,
                frame_step,
            )
        )
        if not target_frames:
            continue
        plans.append(
            _ForwardTemplatePlan(
                track_index=track_index,
                frame_step=frame_step,
                previous=previous,
                seed=seed,
                template_points=template_points,
                target_frames=target_frames,
            )
        )
    return tuple(plans)


def _is_reliable_template_seed(
    point: BallPoint,
    *,
    minimum_template_seed_score: float,
) -> bool:
    return (
        point.source_attribution == "yolo26_observed"
        or (
            point.evidence
            in {
                "bidirectional_template",
                "stationary_bidirectional_template",
                "partial_bidirectional_template",
                "template_validated_detector",
            }
            and point.temporal_score is not None
            and point.temporal_score >= minimum_template_seed_score
        )
    )


def _forward_template_consensus_points(
    plan: _ForwardTemplatePlan,
    grayscale_frames: dict[int, np.ndarray],
    *,
    fps: float,
    minimum_template_score: float = 0.55,
    minimum_consensus_templates: int = 3,
    consensus_radius_diameters: float = 1.0,
    search_radius_diameters: float = 4.5,
) -> tuple[BallPoint, ...]:
    if fps <= 0:
        raise ValueError("Forward template FPS must be positive")
    if (
        not 0 <= minimum_template_score <= 1
        or minimum_consensus_templates < 1
        or consensus_radius_diameters <= 0
        or search_radius_diameters <= 0
    ):
        raise ValueError("Forward template thresholds are invalid")

    templates = [
        (point, _extract_ball_template(grayscale_frames[point.source_frame], point, radius_scale=0.75))
        for point in plan.template_points
    ]
    templates = [
        (point, template)
        for point, template in templates
        if template is not None
    ]
    if len(templates) < minimum_consensus_templates:
        return ()

    reference_diameter = median(
        point.box_diagonal
        for point in plan.template_points
        if point.box_diagonal > 0
    )
    search_radius = max(
        16,
        round(reference_diameter * search_radius_diameters),
    )
    position_x = plan.seed.x
    position_y = plan.seed.y
    velocity_x = plan.seed.x - plan.previous.x
    velocity_y = plan.seed.y - plan.previous.y
    points: list[BallPoint] = []
    for source_frame in plan.target_frames:
        predicted_x = position_x + velocity_x
        predicted_y = position_y + velocity_y
        matches = [
            match
            for _, template in templates
            if (
                match := _template_match(
                    grayscale_frames[source_frame],
                    template,
                    predicted_x=predicted_x,
                    predicted_y=predicted_y,
                    search_radius=search_radius,
                )
            ).score
            >= minimum_template_score
        ]
        consensus = _largest_template_consensus(
            matches,
            maximum_distance=reference_diameter * consensus_radius_diameters,
        )
        if len(consensus) < minimum_consensus_templates:
            break
        total_score = sum(match.score for match in consensus)
        next_x = sum(match.x * match.score for match in consensus) / total_score
        next_y = sum(match.y * match.score for match in consensus) / total_score
        velocity_x = next_x - position_x
        velocity_y = next_y - position_y
        position_x = next_x
        position_y = next_y
        points.append(
            BallPoint(
                source_frame=source_frame,
                clip_seconds=round(
                    plan.seed.clip_seconds
                    + (source_frame - plan.seed.source_frame) / fps,
                    3,
                ),
                confidence=plan.seed.confidence,
                x=position_x,
                y=position_y,
                box_diagonal=reference_diameter,
                evidence="forward_template_consensus",
                temporal_score=round(
                    min(match.score for match in consensus),
                    6,
                ),
                source_attribution="temporal_detector_observed",
            )
        )
    return tuple(points)


def _gate_unanchored_start_points_by_attention(
    tracks: Iterable[BallTrack],
    *,
    records: list[dict[str, Any]],
    video: Path,
    width: int,
    height: int,
    fps: float,
    frame_step: int,
) -> tuple[tuple[BallTrack, ...], int]:
    tracks = tuple(tracks)
    if not tracks or len(records) < 3:
        return tracks, 0
    ordered_frames = sorted(int(record["source_frame"]) for record in records)
    records_by_frame = {
        int(record["source_frame"]): record for record in records
    }
    frame_index = {
        source_frame: index
        for index, source_frame in enumerate(ordered_frames)
    }
    grayscale = _read_sampled_grayscale_frames(video, ordered_frames)
    start_seconds = min(float(record["clip_seconds"]) for record in records)
    startup_end = start_seconds + float(
        SOCCERTRACK_PLAYER_ATTENTION_PROFILE["startup_seconds"]
    )
    rejected = 0
    filtered_tracks: list[BallTrack] = []
    for track in tracks:
        ordered_points = sorted(
            track.points,
            key=lambda point: point.source_frame,
        )
        retained: list[BallPoint] = []
        anchored = False
        for point_index, point in enumerate(ordered_points):
            if anchored or point.clip_seconds > startup_end:
                retained.append(point)
                anchored = True
                continue
            if _has_sustained_detector_confirmation(
                ordered_points,
                point_index=point_index,
                frame_step=frame_step,
            ):
                retained.append(point)
                anchored = True
                continue
            index = frame_index.get(point.source_frame)
            if index is None or index == 0 or index >= len(ordered_frames) - 1:
                rejected += 1
                continue
            cones = _player_attention_cones(
                grayscale[ordered_frames[index - 1]],
                grayscale[point.source_frame],
                grayscale[ordered_frames[index + 1]],
                records_by_frame[point.source_frame],
            )
            support, score = _attention_convergence(point, cones)
            appearance_score = _adjacent_appearance_consistency(
                grayscale[ordered_frames[index - 1]],
                grayscale[point.source_frame],
                grayscale[ordered_frames[index + 1]],
                point,
                reference_diameter=max(1.0, point.box_diagonal),
            )
            crop_radius = max(4, round(point.box_diagonal * 0.8))
            left = max(0, round(point.x) - crop_radius)
            right = min(width, round(point.x) + crop_radius + 1)
            top = max(0, round(point.y) - crop_radius)
            bottom = min(height, round(point.y) + crop_radius + 1)
            crop = grayscale[point.source_frame][top:bottom, left:right]
            contrast = (
                float(np.percentile(crop, 90) - np.percentile(crop, 10))
                if crop.size
                else 0.0
            )
            confirmation_count = int(
                SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                    "startup_forward_confirmation_frames"
                ]
            )
            following = ordered_points[
                point_index + 1 : point_index + 1 + confirmation_count
            ]
            forward_confirmed = (
                len(following) == confirmation_count
                and all(
                    candidate.source_frame
                    == point.source_frame + frame_step * offset
                    for offset, candidate in enumerate(following, start=1)
                )
                and all(
                    hypot(
                        second.x - first.x,
                        second.y - first.y,
                    )
                    / ((second.source_frame - first.source_frame) / fps)
                    <= 1600.0
                    for first, second in zip(
                        [point, *following[:-1]],
                        following,
                    )
                )
            )
            if (
                support
                >= int(
                    SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                        "startup_minimum_converging_players"
                    ]
                )
                and score
                >= float(
                    SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                        "startup_minimum_convergence_score"
                    ]
                )
                and appearance_score
                >= float(
                    SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                        "minimum_appearance_consistency_score"
                    ]
                )
                and contrast >= 24
                and forward_confirmed
                and not _inside_player_upper_body(
                    point,
                    records_by_frame[point.source_frame],
                )
            ):
                retained.append(point)
                anchored = True
            else:
                rejected += 1
        if retained:
            filtered_tracks.append(BallTrack(track.track_id, retained))
    return tuple(filtered_tracks), rejected


def _has_sustained_detector_confirmation(
    points: list[BallPoint],
    *,
    point_index: int,
    frame_step: int,
    minimum_points: int = 3,
) -> bool:
    sequence = points[point_index : point_index + minimum_points]
    return (
        len(sequence) == minimum_points
        and all(
            point.source_attribution == "yolo26_observed"
            and not point.interpolated
            for point in sequence
        )
        and all(
            second.source_frame - first.source_frame == frame_step
            for first, second in zip(sequence, sequence[1:])
        )
    )


def _add_raw_motion_proposals(
    tracks: Iterable[BallTrack],
    *,
    records: list[dict[str, Any]],
    video: Path,
    width: int,
    height: int,
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
    detector_candidates: Iterable[BallPoint] = (),
) -> tuple[tuple[BallTrack, ...], _RawMotionDiagnostics]:
    tracks = tuple(tracks)
    if not tracks or len(records) < 3:
        return tracks, _RawMotionDiagnostics()
    trusted = sorted(
        (point for track in tracks for point in track.points),
        key=lambda point: point.source_frame,
    )
    trusted_frames = {point.source_frame for point in trusted}
    detector_candidate_frames = {
        point.source_frame for point in detector_candidates
    }
    reference_diameter = median(
        point.box_diagonal
        for point in trusted
        if point.box_diagonal > 0
    )
    records_by_frame = {
        int(record["source_frame"]): record for record in records
    }
    ordered_frames = sorted(records_by_frame)
    grayscale = _read_sampled_grayscale_frames(video, ordered_frames)
    proposals_by_frame: dict[int, list[_RawMotionProposal]] = {}
    counters: Counter[str] = Counter()
    for previous_frame, source_frame, following_frame in zip(
        ordered_frames,
        ordered_frames[1:],
        ordered_frames[2:],
    ):
        if (
            source_frame in trusted_frames
            or source_frame in detector_candidate_frames
        ):
            continue
        proposals, rejected = _raw_motion_frame_proposals(
            previous=grayscale[previous_frame],
            current=grayscale[source_frame],
            following=grayscale[following_frame],
            record=records_by_frame[source_frame],
            source_frame=source_frame,
            clip_seconds=float(records_by_frame[source_frame]["clip_seconds"]),
            width=width,
            height=height,
            reference_diameter=reference_diameter,
            trusted=trusted,
            frame_step=frame_step,
        )
        proposals_by_frame[source_frame] = list(proposals)
        counters.update(rejected)
        counters["generated"] += len(proposals)

    selected, selection_rejections = _select_raw_motion_proposals(
        proposals_by_frame,
        trusted=trusted,
        frame_step=frame_step,
        fps=fps,
        reference_diameter=reference_diameter,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    counters.update(selection_rejections)
    selected = tuple(
        proposal
        for proposal in selected
        if _has_local_restoration_support(
            proposal.point,
            trusted=trusted,
            frame_step=frame_step,
        )
        and _point_path_is_plausible(
            proposal.point,
            trusted=[
                *trusted,
                *(
                    other.point
                    for other in selected
                    if other is not proposal
                ),
            ],
            frame_step=frame_step,
            fps=fps,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        )
    )
    if not selected:
        return tracks, _motion_diagnostics(counters)

    additions_by_track: dict[int, list[BallPoint]] = defaultdict(list)
    for proposal in selected:
        track_index = min(
            range(len(tracks)),
            key=lambda index: min(
                abs(proposal.point.source_frame - point.source_frame)
                for point in tracks[index].points
            ),
        )
        additions_by_track[track_index].append(proposal.point)
        counters[proposal.mode] += 1
    enriched = tuple(
        BallTrack(
            track.track_id,
            sorted(
                [*track.points, *additions_by_track[index]],
                key=lambda point: point.source_frame,
            ),
        )
        for index, track in enumerate(tracks)
    )
    return enriched, _motion_diagnostics(counters)


def _read_sampled_grayscale_frames(
    video: Path,
    source_frames: Iterable[int],
) -> dict[int, np.ndarray]:
    required = set(source_frames)
    if not required:
        return {}
    frames: dict[int, np.ndarray] = {}
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        for source_frame in range(max(required) + 1):
            if source_frame not in required:
                if not capture.grab():
                    raise RuntimeError(
                        f"Could not skip to source frame {source_frame} in {video}"
                    )
                continue
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(
                    f"Could not read source frame {source_frame} from {video}"
                )
            frames[source_frame] = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    finally:
        capture.release()
    return frames


def _raw_motion_frame_proposals(
    *,
    previous: np.ndarray,
    current: np.ndarray,
    following: np.ndarray,
    record: dict[str, Any],
    source_frame: int,
    clip_seconds: float,
    width: int,
    height: int,
    reference_diameter: float,
    trusted: list[BallPoint],
    frame_step: int,
    difference_threshold: int = SOCCERTRACK_RAW_MOTION_PROFILE[
        "difference_threshold"
    ],
    minimum_circularity: float = SOCCERTRACK_RAW_MOTION_PROFILE[
        "minimum_circularity"
    ],
    minimum_appearance_range: float = SOCCERTRACK_RAW_MOTION_PROFILE[
        "minimum_appearance_range"
    ],
) -> tuple[tuple[_RawMotionProposal, ...], Counter[str]]:
    previous_difference = cv2.absdiff(current, previous)
    following_difference = cv2.absdiff(current, following)
    motion = cv2.min(previous_difference, following_difference)
    _, mask = cv2.threshold(
        motion,
        difference_threshold,
        255,
        cv2.THRESH_BINARY,
    )
    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    minimum_extent = max(
        2.0,
        reference_diameter
        * SOCCERTRACK_RAW_MOTION_PROFILE[
            "minimum_extent_ball_diameters"
        ],
    )
    maximum_extent = max(
        8.0,
        reference_diameter
        * SOCCERTRACK_RAW_MOTION_PROFILE[
            "maximum_extent_ball_diameters"
        ],
    )
    minimum_area = max(
        3.0,
        reference_diameter**2
        * SOCCERTRACK_RAW_MOTION_PROFILE[
            "minimum_area_ball_diameters_squared"
        ],
    )
    maximum_area = max(
        40.0,
        reference_diameter**2
        * SOCCERTRACK_RAW_MOTION_PROFILE[
            "maximum_area_ball_diameters_squared"
        ],
    )
    counters: Counter[str] = Counter()
    proposals: list[_RawMotionProposal] = []
    attention_cones = _player_attention_cones(
        previous,
        current,
        following,
        record,
    )
    for contour in contours:
        x, y, blob_width, blob_height = cv2.boundingRect(contour)
        area = float(cv2.contourArea(contour))
        perimeter = float(cv2.arcLength(contour, True))
        circularity = (
            4 * np.pi * area / perimeter**2
            if perimeter > 0
            else 0.0
        )
        if (
            area < minimum_area
            or area > maximum_area
            or min(blob_width, blob_height) < minimum_extent
            or max(blob_width, blob_height) > maximum_extent
            or max(blob_width, blob_height)
            / max(1, min(blob_width, blob_height))
            > 2.2
            or circularity < minimum_circularity
        ):
            counters["rejected_scale_or_shape"] += 1
            continue
        moments = cv2.moments(contour)
        if moments["m00"] <= 0:
            counters["rejected_scale_or_shape"] += 1
            continue
        center_x = float(moments["m10"] / moments["m00"])
        center_y = float(moments["m01"] / moments["m00"])
        point = BallPoint(
            source_frame=source_frame,
            clip_seconds=clip_seconds,
            confidence=0.0,
            x=center_x,
            y=center_y,
            box_diagonal=hypot(blob_width, blob_height),
        )
        if not _inside_soccertrack_pitch(point, width, height):
            continue
        if _inside_player_upper_body(point, record):
            counters["rejected_player_body"] += 1
            continue
        radius = max(3, round(reference_diameter * 0.8))
        left = max(0, round(center_x) - radius)
        right = min(current.shape[1], round(center_x) + radius + 1)
        top = max(0, round(center_y) - radius)
        bottom = min(current.shape[0], round(center_y) + radius + 1)
        crop = current[top:bottom, left:right]
        appearance_range = float(
            np.percentile(crop, 90) - np.percentile(crop, 10)
        )
        if appearance_range < minimum_appearance_range:
            counters["rejected_appearance"] += 1
            continue
        mode = _motion_search_mode(
            point,
            record=record,
            trusted=trusted,
            frame_step=frame_step,
            reference_diameter=reference_diameter,
        )
        counters[f"{mode}_generated"] += 1
        contour_fill = area / max(1.0, blob_width * blob_height)
        foreground_mask = np.zeros_like(motion)
        cv2.drawContours(foreground_mask, [contour], -1, 255, -1)
        foreground_strength = float(
            cv2.mean(motion, mask=foreground_mask)[0]
        )
        foreground_score = min(1.0, foreground_strength / 64.0)
        compactness_score = min(
            1.0,
            (min(1.0, circularity / 0.8) + min(1.0, contour_fill))
            / 2,
        )
        scale_ratio = max(
            1e-6,
            hypot(blob_width, blob_height) / reference_diameter,
        )
        scale_score = float(np.exp(-abs(np.log(scale_ratio))))
        texture_score = min(1.0, appearance_range / 64.0)
        appearance_consistency_score = _adjacent_appearance_consistency(
            previous,
            current,
            following,
            point,
            reference_diameter=reference_diameter,
        )
        lower_body_penalty = (
            float(
                SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                    "lower_body_interior_penalty"
                ]
            )
            if _inside_player_lower_body(point, record)
            else 0.0
        )
        verification_score = max(
            0.0,
            min(
                1.0,
                foreground_score
                * float(
                    SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                        "foreground_weight"
                    ]
                )
                + compactness_score
                * float(
                    SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                        "compactness_weight"
                    ]
                )
                + scale_score
                * float(
                    SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                        "scale_weight"
                    ]
                )
                + texture_score
                * float(
                    SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                        "texture_weight"
                    ]
                )
                + appearance_consistency_score
                * float(
                    SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                        "appearance_consistency_weight"
                    ]
                )
                - lower_body_penalty,
            ),
        )
        trajectory_score = _proposal_trajectory_score(
            point,
            trusted=trusted,
            frame_step=frame_step,
            reference_diameter=reference_diameter,
        )
        attention_support, attention_score = _attention_convergence(
            point,
            attention_cones,
        )
        proposals.append(
            _RawMotionProposal(
                point=BallPoint(
                    source_frame=source_frame,
                    clip_seconds=clip_seconds,
                    confidence=round(
                        min(1.0, circularity * appearance_range / 64),
                        6,
                    ),
                    x=center_x,
                    y=center_y,
                    box_diagonal=hypot(blob_width, blob_height),
                    evidence=f"raw_motion_{mode}",
                    temporal_score=None,
                    source_attribution="raw_motion_micro_crop_supported",
                ),
                mode=mode,
                appearance_score=appearance_range,
                foreground_score=foreground_score,
                compactness_score=compactness_score,
                scale_score=scale_score,
                appearance_consistency_score=(
                    appearance_consistency_score
                ),
                verification_score=verification_score,
                trajectory_score=trajectory_score,
                attention_support=attention_support,
                attention_score=attention_score,
            )
        )
    return tuple(proposals), counters


def _adjacent_appearance_consistency(
    previous: np.ndarray,
    current: np.ndarray,
    following: np.ndarray,
    point: BallPoint,
    *,
    reference_diameter: float,
) -> float:
    template = _extract_ball_template(current, point, radius_scale=0.6)
    if template is None:
        return 0.0
    search_radius = max(8, round(reference_diameter * 2))
    previous_match = _template_match(
        previous,
        template,
        predicted_x=point.x,
        predicted_y=point.y,
        search_radius=search_radius,
    )
    following_match = _template_match(
        following,
        template,
        predicted_x=point.x,
        predicted_y=point.y,
        search_radius=search_radius,
    )
    minimum_score = float(
        SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
            "adjacent_template_minimum_score"
        ]
    )
    if (
        previous_match.score < minimum_score
        or following_match.score < minimum_score
    ):
        return 0.0
    midpoint_x = (previous_match.x + following_match.x) / 2
    midpoint_y = (previous_match.y + following_match.y) / 2
    maximum_path_error = reference_diameter * float(
        SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
            "adjacent_path_maximum_ball_diameters"
        ]
    )
    path_error = hypot(point.x - midpoint_x, point.y - midpoint_y)
    incoming = np.array(
        [point.x - previous_match.x, point.y - previous_match.y]
    )
    outgoing = np.array(
        [following_match.x - point.x, following_match.y - point.y]
    )
    if path_error > maximum_path_error or float(incoming @ outgoing) < 0:
        return 0.0
    correlation_score = min(
        1.0,
        (
            (previous_match.score - minimum_score)
            + (following_match.score - minimum_score)
        )
        / (2 * (1 - minimum_score)),
    )
    return max(
        0.0,
        correlation_score * (1 - path_error / maximum_path_error),
    )


def _player_attention_cones(
    previous: np.ndarray,
    current: np.ndarray,
    following: np.ndarray,
    record: dict[str, Any],
) -> tuple[_PlayerAttentionCone, ...]:
    cones: list[_PlayerAttentionCone] = []
    for detection in record.get("detections", []):
        if (
            detection.get("class_name") != "person"
            or float(detection["confidence"])
            < float(
                SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                    "minimum_person_confidence"
                ]
            )
        ):
            continue
        x1 = max(0, round(float(detection["x1"])))
        y1 = max(0, round(float(detection["y1"])))
        x2 = min(current.shape[1], round(float(detection["x2"])))
        y2 = min(current.shape[0], round(float(detection["y2"])))
        width = x2 - x1
        height = y2 - y1
        if (
            width < 4
            or height
            < float(
                SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                    "minimum_person_height_pixels"
                ]
            )
        ):
            continue
        crop = current[y1:y2, x1:x2]
        border = np.concatenate(
            [
                crop[0, :],
                crop[-1, :],
                crop[:, 0],
                crop[:, -1],
            ]
        )
        background = float(np.median(border))
        foreground = np.abs(crop.astype(np.float32) - background) >= 18
        head = foreground[: max(1, round(height * 0.35))]
        torso_top = round(height * 0.35)
        torso_bottom = max(torso_top + 1, round(height * 0.72))
        torso = foreground[torso_top:torso_bottom]
        appearance_direction: np.ndarray | None = None
        appearance_confidence = 0.0
        if int(head.sum()) >= 3 and int(torso.sum()) >= 5:
            head_x = float(np.argwhere(head)[:, 1].mean())
            torso_x = float(np.argwhere(torso)[:, 1].mean())
            normalized_offset = (head_x - torso_x) / max(1.0, width)
            if abs(normalized_offset) >= 0.04:
                appearance_direction = np.array(
                    [np.sign(normalized_offset), 0.22],
                    dtype=np.float64,
                )
                appearance_direction /= np.linalg.norm(
                    appearance_direction
                )
                appearance_confidence = min(
                    1.0,
                    abs(normalized_offset) / 0.18,
                )

        features = cv2.goodFeaturesToTrack(
            crop,
            maxCorners=12,
            qualityLevel=0.02,
            minDistance=2,
        )
        motion_direction: np.ndarray | None = None
        motion_confidence = 0.0
        if features is not None and len(features) >= 3:
            features[:, 0, 0] += x1
            features[:, 0, 1] += y1
            moved, status, _ = cv2.calcOpticalFlowPyrLK(
                current,
                following,
                features,
                None,
                winSize=(15, 15),
                maxLevel=2,
            )
            if moved is not None and status is not None:
                valid = status[:, 0].astype(bool)
                if int(valid.sum()) >= 3:
                    displacement = np.median(
                        moved[valid, 0, :] - features[valid, 0, :],
                        axis=0,
                    ).astype(np.float64)
                    magnitude = float(np.linalg.norm(displacement))
                    if magnitude >= max(0.75, height * 0.015):
                        motion_direction = displacement / magnitude
                        motion_confidence = min(
                            1.0,
                            magnitude / max(1.0, height * 0.08),
                        )

        direction: np.ndarray | None = None
        confidence = 0.0
        if appearance_direction is not None and motion_direction is not None:
            agreement = float(appearance_direction @ motion_direction)
            if agreement >= 0:
                direction = (
                    appearance_direction * appearance_confidence
                    + motion_direction * motion_confidence
                )
                confidence = (
                    appearance_confidence + motion_confidence
                ) / 2
            elif appearance_confidence >= motion_confidence:
                direction = appearance_direction
                confidence = appearance_confidence * 0.5
            else:
                direction = motion_direction
                confidence = motion_confidence * 0.5
        elif appearance_direction is not None:
            direction = appearance_direction
            confidence = appearance_confidence * 0.7
        elif motion_direction is not None:
            direction = motion_direction
            confidence = motion_confidence * 0.5
        if direction is None or confidence < float(
            SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                "minimum_orientation_confidence"
            ]
        ):
            continue
        direction /= np.linalg.norm(direction)
        cones.append(
            _PlayerAttentionCone(
                origin_x=(x1 + x2) / 2,
                origin_y=y1 + height * 0.55,
                direction_x=float(direction[0]),
                direction_y=float(direction[1]),
                confidence=confidence
                * min(1.0, float(detection["confidence"])),
                player_height=float(height),
            )
        )
    return tuple(cones)


def _attention_convergence(
    point: BallPoint,
    cones: Iterable[_PlayerAttentionCone],
) -> tuple[int, float]:
    maximum_angle = np.deg2rad(
        float(
            SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                "maximum_cone_half_angle_degrees"
            ]
        )
    )
    minimum_cosine = float(np.cos(maximum_angle))
    support = 0
    score = 0.0
    for cone in cones:
        offset = np.array(
            [point.x - cone.origin_x, point.y - cone.origin_y],
            dtype=np.float64,
        )
        distance = float(np.linalg.norm(offset))
        if distance <= 1:
            continue
        maximum_distance = max(
            float(
                SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                    "minimum_search_distance_pixels"
                ]
            ),
            cone.player_height
            * float(
                SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                    "maximum_distance_player_heights"
                ]
            ),
        )
        if distance > maximum_distance:
            continue
        cosine = float(
            offset
            @ np.array([cone.direction_x, cone.direction_y])
            / distance
        )
        if cosine < minimum_cosine:
            continue
        support += 1
        angular_score = (cosine - minimum_cosine) / (1 - minimum_cosine)
        score += (
            cone.confidence
            * angular_score
            * max(0.0, 1 - distance / maximum_distance)
        )
    return support, score


def _inside_player_lower_body(
    point: BallPoint,
    record: dict[str, Any],
    *,
    minimum_person_confidence: float = 0.25,
) -> bool:
    for detection in record.get("detections", []):
        if (
            detection.get("class_name") != "person"
            or float(detection["confidence"]) < minimum_person_confidence
        ):
            continue
        x1 = float(detection["x1"])
        y1 = float(detection["y1"])
        x2 = float(detection["x2"])
        y2 = float(detection["y2"])
        height = y2 - y1
        if x1 <= point.x <= x2 and y1 + height * 0.72 <= point.y <= y2:
            return True
    return False


def _proposal_trajectory_score(
    point: BallPoint,
    *,
    trusted: list[BallPoint],
    frame_step: int,
    reference_diameter: float,
) -> float:
    prediction = _trusted_trajectory_prediction(
        trusted,
        point.source_frame,
        frame_step=frame_step,
    )
    if prediction is None:
        return 0.0
    distance = hypot(point.x - prediction[0], point.y - prediction[1])
    return max(0.0, 1 - distance / max(12.0, reference_diameter * 6))


def _motion_search_mode(
    point: BallPoint,
    *,
    record: dict[str, Any],
    trusted: list[BallPoint],
    frame_step: int,
    reference_diameter: float,
) -> str:
    if _near_player_feet(point, record):
        return "near_feet"
    prediction = _trusted_trajectory_prediction(
        trusted,
        point.source_frame,
        frame_step=frame_step,
    )
    if prediction is not None:
        predicted_x, predicted_y = prediction
        corridor_radius = max(
            12.0,
            reference_diameter
            * SOCCERTRACK_RAW_MOTION_PROFILE[
                "trajectory_corridor_ball_diameters"
            ],
        )
        if hypot(point.x - predicted_x, point.y - predicted_y) <= corridor_radius:
            return "trajectory_corridor"
    return "global_fallback"


def _trusted_trajectory_prediction(
    trusted: list[BallPoint],
    source_frame: int,
    *,
    frame_step: int,
    maximum_sample_gap: int = SOCCERTRACK_RAW_MOTION_PROFILE[
        "trajectory_maximum_sample_gap"
    ],
) -> tuple[float, float] | None:
    previous = [point for point in trusted if point.source_frame < source_frame]
    following = [point for point in trusted if point.source_frame > source_frame]
    if previous and following:
        first = previous[-1]
        second = following[0]
        if (
            source_frame - first.source_frame <= frame_step * maximum_sample_gap
            and second.source_frame - source_frame
            <= frame_step * maximum_sample_gap
        ):
            alpha = (
                (source_frame - first.source_frame)
                / (second.source_frame - first.source_frame)
            )
            return (
                first.x + (second.x - first.x) * alpha,
                first.y + (second.y - first.y) * alpha,
            )
    if len(previous) >= 2:
        first, second = previous[-2:]
        if (
            second.source_frame - first.source_frame == frame_step
            and source_frame - second.source_frame
            <= frame_step * maximum_sample_gap
        ):
            steps = (source_frame - second.source_frame) / frame_step
            return (
                second.x + (second.x - first.x) * steps,
                second.y + (second.y - first.y) * steps,
            )
    return None


def _select_raw_motion_proposals(
    proposals_by_frame: dict[int, list[_RawMotionProposal]],
    *,
    trusted: list[BallPoint],
    frame_step: int,
    fps: float,
    reference_diameter: float,
    max_speed_pixels_per_second: float,
) -> tuple[tuple[_RawMotionProposal, ...], Counter[str]]:
    counters: Counter[str] = Counter()
    selected: list[_RawMotionProposal] = []
    accepted_margins: list[float] = []
    proposal_clip_start = min(
        (
            item.point.clip_seconds
            for values in proposals_by_frame.values()
            for item in values
        ),
        default=0.0,
    )
    for source_frame in sorted(proposals_by_frame):
        proposals = proposals_by_frame[source_frame]
        corridor = [
            proposal
            for proposal in proposals
            if proposal.mode == "trajectory_corridor"
            and proposal.verification_score
            >= float(
                SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                    "trajectory_corridor_minimum_score"
                ]
            )
            and _proposal_path_is_plausible(
                proposal,
                trusted=trusted,
                frame_step=frame_step,
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            )
        ]
        if len(corridor) == 1:
            selected.append(corridor[0])
            continue
        if len(corridor) > 1:
            counters["rejected_ambiguity"] += len(corridor)

        near_feet = [
            proposal for proposal in proposals if proposal.mode == "near_feet"
        ]
        supported_feet = [
            proposal
            for proposal in near_feet
            if proposal.verification_score
            >= float(
                SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                    "near_feet_minimum_score"
                ]
            )
            and _proposal_temporal_neighbor_count(
                proposal,
                proposals_by_frame=proposals_by_frame,
                trusted=trusted,
                frame_step=frame_step,
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
                allowed_modes={"near_feet", "trajectory_corridor"},
            )
            >= 1
            and _proposal_path_is_plausible(
                proposal,
                trusted=trusted,
                frame_step=frame_step,
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            )
        ]
        counters["rejected_temporal_consistency"] += (
            len(near_feet) - len(supported_feet)
        )
        if len(supported_feet) == 1:
            selected.append(supported_feet[0])
            continue
        if len(supported_feet) > 1:
            counters["rejected_ambiguity"] += len(supported_feet)

        fallback = [
            proposal
            for proposal in proposals
            if proposal.mode == "global_fallback"
            and _proposal_temporal_neighbor_count(
                proposal,
                proposals_by_frame=proposals_by_frame,
                trusted=trusted,
                frame_step=frame_step,
                fps=fps,
                max_speed_pixels_per_second=min(
                    max_speed_pixels_per_second,
                    reference_diameter * fps * 6,
                ),
                allowed_modes={"global_fallback", "trajectory_corridor"},
            )
            >= 2
            and _proposal_path_is_plausible(
                proposal,
                trusted=trusted,
                frame_step=frame_step,
                fps=fps,
                max_speed_pixels_per_second=min(
                    max_speed_pixels_per_second,
                    reference_diameter * fps * 6,
                ),
                allow_unanchored=True,
            )
        ]
        raw_fallback_count = sum(
            proposal.mode == "global_fallback" for proposal in proposals
        )
        counters["rejected_temporal_consistency"] += (
            raw_fallback_count - len(fallback)
        )
        if len(fallback) == 1:
            selected.append(fallback[0])
            continue
        if len(fallback) > 1:
            counters["rejected_ambiguity"] += len(fallback)

        attention_candidates: list[_RawMotionProposal] = []
        for proposal in proposals:
            has_prior_anchor = any(
                point.source_frame < proposal.point.source_frame
                for point in trusted
            )
            startup = (
                not has_prior_anchor
                and proposal.point.clip_seconds
                <= proposal_clip_start
                + float(
                    SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                        "startup_seconds"
                    ]
                )
            )
            minimum_support = int(
                SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                    "startup_minimum_converging_players"
                    if startup
                    else "minimum_converging_players"
                ]
            )
            minimum_attention_score = float(
                SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                    "startup_minimum_convergence_score"
                    if startup
                    else "minimum_convergence_score"
                ]
            )
            minimum_neighbors = (
                int(
                    SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                        "startup_forward_confirmation_frames"
                    ]
                )
                if startup
                else 1
            )
            if (
                proposal.attention_support < minimum_support
                or proposal.attention_score < minimum_attention_score
            ):
                counters["attention_rejected_convergence"] += 1
                continue
            if not (
                proposal.verification_score
                >= float(
                    SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                        "minimum_visual_verification_score"
                    ]
                )
                and proposal.appearance_consistency_score
                >= float(
                    SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                        "minimum_appearance_consistency_score"
                    ]
                )
                and proposal.compactness_score
                >= float(
                    SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                        "minimum_compactness_score"
                    ]
                )
                and proposal.scale_score
                >= float(
                    SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                        "minimum_scale_score"
                    ]
                )
                and proposal.foreground_score
                >= float(
                    SOCCERTRACK_PLAYER_ATTENTION_PROFILE[
                        "minimum_foreground_score"
                    ]
                )
            ):
                counters["attention_rejected_visual_evidence"] += 1
                continue
            neighbor_count = _proposal_temporal_neighbor_count(
                proposal,
                proposals_by_frame=proposals_by_frame,
                trusted=trusted,
                frame_step=frame_step,
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
                allowed_modes={
                    "near_feet",
                    "trajectory_corridor",
                    "global_fallback",
                },
            )
            if (
                neighbor_count < minimum_neighbors
                or not _proposal_path_is_plausible(
                    proposal,
                    trusted=trusted,
                    frame_step=frame_step,
                    fps=fps,
                    max_speed_pixels_per_second=(
                        max_speed_pixels_per_second
                    ),
                    allow_unanchored=startup,
                )
            ):
                counters["attention_rejected_temporal_path"] += 1
                continue
            attention_candidates.append(proposal)
        attention_candidates.sort(
            key=lambda proposal: (
                proposal.attention_score,
                proposal.verification_score,
                proposal.trajectory_score,
            ),
            reverse=True,
        )
        if len(attention_candidates) > 1:
            margin = (
                attention_candidates[0].attention_score
                - attention_candidates[1].attention_score
            )
            if margin < 0.08:
                counters["rejected_alternative_margin"] += len(
                    attention_candidates
                )
                continue
            accepted_margins.append(margin)
        if attention_candidates:
            chosen = attention_candidates[0]
            selected.append(
                replace(
                    chosen,
                    point=replace(
                        chosen.point,
                        evidence=(
                            "raw_motion_attention_convergence_"
                            f"{chosen.mode}"
                        ),
                    ),
                )
            )
            counters["attention_accepted"] += 1
    if accepted_margins:
        counters["accepted_margin_sum"] = sum(accepted_margins)
        counters["accepted_margin_count"] = len(accepted_margins)
        counters["accepted_margin_min"] = min(accepted_margins)
    return tuple(selected), counters


def _proposal_has_temporal_neighbor(
    proposal: _RawMotionProposal,
    *,
    proposals_by_frame: dict[int, list[_RawMotionProposal]],
    trusted: list[BallPoint],
    frame_step: int,
    fps: float,
    max_speed_pixels_per_second: float,
    allowed_modes: set[str],
    minimum_neighbors: int,
) -> bool:
    return (
        _proposal_temporal_neighbor_count(
            proposal,
            proposals_by_frame=proposals_by_frame,
            trusted=trusted,
            frame_step=frame_step,
            fps=fps,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
            allowed_modes=allowed_modes,
        )
        >= minimum_neighbors
    )


def _proposal_temporal_neighbor_count(
    proposal: _RawMotionProposal,
    *,
    proposals_by_frame: dict[int, list[_RawMotionProposal]],
    trusted: list[BallPoint],
    frame_step: int,
    fps: float,
    max_speed_pixels_per_second: float,
    allowed_modes: set[str],
) -> int:
    maximum_distance = max_speed_pixels_per_second * frame_step / fps
    neighbor_count = 0
    for direction in (-1, 1):
        neighbor_frame = proposal.point.source_frame + direction * frame_step
        candidates = [
            other.point
            for other in proposals_by_frame.get(neighbor_frame, [])
            if other.mode in allowed_modes
        ]
        candidates.extend(
            point
            for point in trusted
            if point.source_frame == neighbor_frame
        )
        if any(
            hypot(
                proposal.point.x - candidate.x,
                proposal.point.y - candidate.y,
            )
            <= maximum_distance
            for candidate in candidates
        ):
            neighbor_count += 1
    return neighbor_count


def _proposal_path_is_plausible(
    proposal: _RawMotionProposal,
    *,
    trusted: list[BallPoint],
    frame_step: int,
    fps: float,
    max_speed_pixels_per_second: float,
    allow_unanchored: bool = False,
) -> bool:
    has_local_anchor = any(
        0 < abs(point.source_frame - proposal.point.source_frame)
        <= frame_step * 4
        for point in trusted
    )
    if not has_local_anchor:
        return allow_unanchored
    return _point_path_is_plausible(
        proposal.point,
        trusted=trusted,
        frame_step=frame_step,
        fps=fps,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )


def _point_path_is_plausible(
    point: BallPoint,
    *,
    trusted: list[BallPoint],
    frame_step: int,
    fps: float,
    max_speed_pixels_per_second: float,
) -> bool:
    previous = [
        candidate
        for candidate in trusted
        if 0 < point.source_frame - candidate.source_frame
        <= frame_step * 4
    ]
    following = [
        candidate
        for candidate in trusted
        if 0 < candidate.source_frame - point.source_frame
        <= frame_step * 4
    ]
    if not previous and not following:
        return False
    ordered = [
        *previous[-2:],
        point,
        *following[:2],
    ]
    velocities: list[tuple[np.ndarray, float]] = []
    for first, second in zip(ordered, ordered[1:]):
        elapsed = (second.source_frame - first.source_frame) / fps
        if elapsed <= 0:
            return False
        velocity = np.array(
            [second.x - first.x, second.y - first.y]
        ) / elapsed
        if np.linalg.norm(velocity) > max_speed_pixels_per_second:
            return False
        velocities.append((velocity, elapsed))
    maximum_acceleration = float(
        SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
            "maximum_acceleration_pixels_per_second_squared"
        ]
    )
    return all(
        np.linalg.norm(second_velocity - first_velocity)
        / ((first_elapsed + second_elapsed) / 2)
        <= maximum_acceleration
        for (
            first_velocity,
            first_elapsed,
        ), (
            second_velocity,
            second_elapsed,
        ) in zip(velocities, velocities[1:])
    )


def _discard_unsupported_detector_outliers(
    tracks: Iterable[BallTrack],
    *,
    records: list[dict[str, Any]],
    video: Path,
    fps: float,
    frame_step: int,
    max_gap_seconds: float,
    max_speed_pixels_per_second: float,
) -> tuple[tuple[BallTrack, ...], frozenset[int]]:
    tracks = tuple(tracks)
    if not tracks:
        return tracks, frozenset()
    records_by_frame = {
        int(record["source_frame"]): record for record in records
    }
    grayscale = _read_sampled_grayscale_frames(
        video,
        sorted(records_by_frame),
    )
    maximum_gap = (
        frame_step
        * int(
            SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                "maximum_neighbor_gap_frames"
            ]
        )
    )
    filtered: list[BallTrack] = []
    rejected_frames: set[int] = set()
    for track in tracks:
        points = sorted(track.points, key=lambda point: point.source_frame)
        retained: list[BallPoint] = []
        for index, point in enumerate(points):
            if (
                index == 0
                or index == len(points) - 1
                or point.source_attribution != "yolo26_observed"
            ):
                retained.append(point)
                continue
            previous = points[index - 1]
            following = points[index + 1]
            if (
                point.source_frame - previous.source_frame > maximum_gap
                or following.source_frame - point.source_frame > maximum_gap
            ):
                retained.append(point)
                continue
            frame_span = following.source_frame - previous.source_frame
            if frame_span <= 0:
                retained.append(point)
                continue
            alpha = (
                point.source_frame - previous.source_frame
            ) / frame_span
            expected_x = previous.x + (following.x - previous.x) * alpha
            expected_y = previous.y + (following.y - previous.y) * alpha
            path_error = hypot(
                point.x - expected_x,
                point.y - expected_y,
            )
            minimum_error = max(
                float(
                    SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                        "minimum_path_error_pixels"
                    ]
                ),
                point.box_diagonal
                * float(
                    SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                        "minimum_path_error_ball_diameters"
                    ]
                ),
            )
            if path_error < minimum_error:
                retained.append(point)
                continue
            frame = records_by_frame.get(point.source_frame)
            before = grayscale.get(point.source_frame - frame_step)
            current = grayscale.get(point.source_frame)
            after = grayscale.get(point.source_frame + frame_step)
            if (
                frame is None
                or before is None
                or current is None
                or after is None
            ):
                retained.append(point)
                continue
            if _detector_point_visual_support(
                point,
                records_by_frame=records_by_frame,
                grayscale=grayscale,
                frame_step=frame_step,
            ) >= float(
                SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                    "minimum_outlier_visual_support"
                ]
            ):
                retained.append(point)
            else:
                rejected_frames.add(point.source_frame)
        changed = True
        while changed:
            changed = False
            for first, second in zip(retained, retained[1:]):
                elapsed = (
                    second.source_frame - first.source_frame
                ) / fps
                if elapsed <= 0:
                    continue
                speed = hypot(
                    second.x - first.x,
                    second.y - first.y,
                ) / elapsed
                if speed <= max_speed_pixels_per_second:
                    continue
                first_support = _detector_point_visual_support(
                    first,
                    records_by_frame=records_by_frame,
                    grayscale=grayscale,
                    frame_step=frame_step,
                )
                second_support = _detector_point_visual_support(
                    second,
                    records_by_frame=records_by_frame,
                    grayscale=grayscale,
                    frame_step=frame_step,
                )
                support_margin = abs(first_support - second_support)
                if support_margin < float(
                    SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                        "minimum_conflict_support_margin"
                    ]
                ):
                    continue
                rejected = (
                    first
                    if first_support < second_support
                    else second
                )
                retained.remove(rejected)
                rejected_frames.add(rejected.source_frame)
                changed = True
                break
        if len(retained) >= 2:
            terminal = retained[-1]
            previous = retained[-2]
            terminal_gap = (
                terminal.source_frame - previous.source_frame
            ) / fps
            if (
                terminal_gap > max_gap_seconds
                and _detector_point_visual_support(
                    terminal,
                    records_by_frame=records_by_frame,
                    grayscale=grayscale,
                    frame_step=frame_step,
                )
                < float(
                    SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                        "terminal_minimum_support"
                    ]
                )
            ):
                retained.pop()
                rejected_frames.add(terminal.source_frame)
        filtered.append(BallTrack(track.track_id, retained))
    return tuple(filtered), frozenset(rejected_frames)


def _detector_point_visual_support(
    point: BallPoint,
    *,
    records_by_frame: dict[int, dict[str, Any]],
    grayscale: dict[int, np.ndarray],
    frame_step: int,
) -> float:
    frame = records_by_frame.get(point.source_frame)
    before = grayscale.get(point.source_frame - frame_step)
    current = grayscale.get(point.source_frame)
    after = grayscale.get(point.source_frame + frame_step)
    if frame is None or before is None or current is None or after is None:
        return 0.0
    appearance_score = _adjacent_appearance_consistency(
        before,
        current,
        after,
        point,
        reference_diameter=max(1.0, point.box_diagonal),
    )
    cones = _player_attention_cones(
        before,
        current,
        after,
        frame,
    )
    _, attention_score = _attention_convergence(point, cones)
    return appearance_score + attention_score


def _add_bracketed_outlier_motion_recoveries(
    tracks: Iterable[BallTrack],
    *,
    records: list[dict[str, Any]],
    video: Path,
    width: int,
    height: int,
    fps: float,
    frame_step: int,
    rejected_frames: frozenset[int],
    max_speed_pixels_per_second: float,
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    if not tracks:
        return tracks
    trusted = sorted(
        (point for track in tracks for point in track.points),
        key=lambda point: point.source_frame,
    )
    trusted_by_frame = {
        point.source_frame: point for point in trusted
    }
    recoverable_frames = {
        source_frame
        for source_frame in rejected_frames
        if source_frame - frame_step in trusted_by_frame
        and source_frame + frame_step in trusted_by_frame
    }
    records_by_frame = {
        int(record["source_frame"]): record for record in records
    }
    grayscale = _read_sampled_grayscale_frames(
        video,
        sorted(records_by_frame),
    )
    additions: list[BallPoint] = []
    for source_frame in sorted(recoverable_frames):
        local_diameter = median(
            (
                trusted_by_frame[source_frame - frame_step].box_diagonal,
                trusted_by_frame[source_frame + frame_step].box_diagonal,
            )
        )
        record = records_by_frame[source_frame]
        proposals, _ = _raw_motion_frame_proposals(
            previous=grayscale[source_frame - frame_step],
            current=grayscale[source_frame],
            following=grayscale[source_frame + frame_step],
            record=record,
            source_frame=source_frame,
            clip_seconds=float(record["clip_seconds"]),
            width=width,
            height=height,
            reference_diameter=local_diameter,
            trusted=trusted,
            frame_step=frame_step,
        )
        corridor = [
            proposal
            for proposal in proposals
            if proposal.mode == "trajectory_corridor"
            and proposal.verification_score
            >= float(
                SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                    "trajectory_corridor_minimum_score"
                ]
            )
            and _point_path_is_plausible(
                proposal.point,
                trusted=trusted,
                frame_step=frame_step,
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            )
        ]
        if len(corridor) == 1:
            additions.append(corridor[0].point)
    if not additions:
        enriched = tracks
    else:
        enriched = (
            BallTrack(
                tracks[0].track_id,
                sorted(
                    [*tracks[0].points, *additions],
                    key=lambda point: point.source_frame,
                ),
            ),
            *tracks[1:],
        )
    return _add_endpoint_bounded_short_motion_bridges(
        enriched,
        records_by_frame=records_by_frame,
        grayscale=grayscale,
        width=width,
        height=height,
        fps=fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )


def _add_endpoint_bounded_short_motion_bridges(
    tracks: tuple[BallTrack, ...],
    *,
    records_by_frame: dict[int, dict[str, Any]],
    grayscale: dict[int, np.ndarray],
    width: int,
    height: int,
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
) -> tuple[BallTrack, ...]:
    trusted = sorted(
        (point for track in tracks for point in track.points),
        key=lambda point: point.source_frame,
    )
    additions: list[BallPoint] = []
    maximum_gap = int(
        SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
            "short_bridge_maximum_raw_frames"
        ]
    )
    for first, second in zip(trusted, trusted[1:]):
        frame_gap = second.source_frame - first.source_frame
        if frame_gap <= frame_step or frame_gap > maximum_gap:
            continue
        local_diameter = median(
            (first.box_diagonal, second.box_diagonal)
        )
        maximum_deviation = max(
            float(
                SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                    "short_bridge_corridor_pixels"
                ]
            ),
            local_diameter
            * float(
                SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                    "short_bridge_corridor_ball_diameters"
                ]
            ),
        )
        maximum_curved_deviation = max(
            float(
                SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                    "short_bridge_curved_corridor_pixels"
                ]
            ),
            local_diameter
            * float(
                SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                    "short_bridge_curved_corridor_ball_diameters"
                ]
            ),
        )
        proposals_by_frame: dict[int, list[_RawMotionProposal]] = {}
        for source_frame in range(
            first.source_frame + frame_step,
            second.source_frame,
            frame_step,
        ):
            record = records_by_frame.get(source_frame)
            before = grayscale.get(source_frame - frame_step)
            current = grayscale.get(source_frame)
            after = grayscale.get(source_frame + frame_step)
            if (
                record is None
                or before is None
                or current is None
                or after is None
            ):
                continue
            proposals, _ = _raw_motion_frame_proposals(
                previous=before,
                current=current,
                following=after,
                record=record,
                source_frame=source_frame,
                clip_seconds=float(record["clip_seconds"]),
                width=width,
                height=height,
                reference_diameter=local_diameter,
                trusted=trusted,
                frame_step=frame_step,
            )
            proposals_by_frame[source_frame] = list(proposals)
        gap_candidates: list[_RawMotionProposal] = []
        for source_frame, proposals in proposals_by_frame.items():
            alpha = (
                source_frame - first.source_frame
            ) / frame_gap
            expected_x = first.x + (second.x - first.x) * alpha
            expected_y = first.y + (second.y - first.y) * alpha
            viable = [
                proposal
                for proposal in proposals
                if proposal.verification_score
                >= float(
                    SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                        "short_bridge_minimum_verification_score"
                    ]
                )
                and (
                    hypot(
                        proposal.point.x - expected_x,
                        proposal.point.y - expected_y,
                    )
                    <= maximum_deviation
                    or (
                        hypot(
                            proposal.point.x - expected_x,
                            proposal.point.y - expected_y,
                        )
                        <= maximum_curved_deviation
                        and proposal.verification_score
                        >= float(
                            SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                                "complete_path_minimum_verification_score"
                            ]
                        )
                        and _proposal_temporal_neighbor_count(
                            proposal,
                            proposals_by_frame=proposals_by_frame,
                            trusted=trusted,
                            frame_step=frame_step,
                            fps=fps,
                            max_speed_pixels_per_second=(
                                max_speed_pixels_per_second
                            ),
                            allowed_modes={
                                "near_feet",
                                "trajectory_corridor",
                                "global_fallback",
                            },
                        )
                        >= int(
                            SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                                "short_bridge_curved_minimum_neighbors"
                            ]
                        )
                    )
                )
            ]
            if viable:
                gap_candidates.append(
                    max(
                        viable,
                        key=lambda proposal: (
                            -hypot(
                                proposal.point.x - expected_x,
                                proposal.point.y - expected_y,
                            ),
                            proposal.verification_score,
                        ),
                    )
                )
        provisional_path = [
            first,
            *(proposal.point for proposal in gap_candidates),
            second,
        ]
        coherent = all(
            _point_path_is_plausible(
                proposal.point,
                trusted=provisional_path,
                frame_step=frame_step,
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            )
            for proposal in gap_candidates
        )
        accepted: list[_RawMotionProposal] = []
        if coherent and len(gap_candidates) >= int(
            SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                "short_bridge_minimum_chain_points"
            ]
        ):
            accepted = gap_candidates
        elif coherent and len(gap_candidates) == 1:
            proposal = gap_candidates[0]
            if (
                proposal.mode == "trajectory_corridor"
                and proposal.verification_score
                >= float(
                    SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                        "isolated_corridor_minimum_verification_score"
                    ]
                )
                and proposal.trajectory_score
                >= float(
                    SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                        "isolated_corridor_minimum_trajectory_score"
                    ]
                )
            ):
                accepted = [proposal]
        if not accepted:
            accepted = list(
                _select_complete_short_motion_bridge(
                    first,
                    second,
                    proposals_by_frame=proposals_by_frame,
                    local_diameter=local_diameter,
                    fps=fps,
                    frame_step=frame_step,
                    max_speed_pixels_per_second=max_speed_pixels_per_second,
                )
            )
        additions.extend(proposal.point for proposal in accepted)
    if not additions:
        return tracks
    return (
        BallTrack(
            tracks[0].track_id,
            sorted(
                [*tracks[0].points, *additions],
                key=lambda point: point.source_frame,
            ),
        ),
        *tracks[1:],
    )


def _select_complete_short_motion_bridge(
    first: BallPoint,
    second: BallPoint,
    *,
    proposals_by_frame: dict[int, list[_RawMotionProposal]],
    local_diameter: float,
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
) -> tuple[_RawMotionProposal, ...]:
    frame_gap = second.source_frame - first.source_frame
    expected_frames = list(
        range(first.source_frame + frame_step, second.source_frame, frame_step)
    )
    if (
        frame_gap
        > int(
            SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                "complete_path_maximum_raw_frames"
            ]
        )
        or len(expected_frames)
        < int(
            SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                "complete_path_minimum_points"
            ]
        )
    ):
        return ()
    options: list[list[_RawMotionProposal]] = []
    for source_frame in expected_frames:
        candidates = sorted(
            (
                proposal
                for proposal in proposals_by_frame.get(source_frame, ())
                if proposal.verification_score
                >= float(
                    SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                        "complete_path_minimum_verification_score"
                    ]
                )
            ),
            key=lambda proposal: (
                proposal.verification_score
                + proposal.attention_score
                * float(
                    SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                        "complete_path_attention_weight"
                    ]
                )
            ),
            reverse=True,
        )
        deduplicated: list[_RawMotionProposal] = []
        deduplication_distance = (
            local_diameter
            * float(
                SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                    "complete_path_deduplication_ball_diameters"
                ]
            )
        )
        for candidate in candidates:
            if all(
                hypot(
                    candidate.point.x - retained.point.x,
                    candidate.point.y - retained.point.y,
                )
                > deduplication_distance
                for retained in deduplicated
            ):
                deduplicated.append(candidate)
            if len(deduplicated) >= int(
                SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                    "complete_path_candidate_limit"
                ]
            ):
                break
        if not deduplicated:
            return ()
        options.append(deduplicated)
    ranked: list[tuple[float, tuple[_RawMotionProposal, ...]]] = []
    for candidate_path in product(*options):
        path = [first, *(proposal.point for proposal in candidate_path), second]
        if not all(
            _point_path_is_plausible(
                proposal.point,
                trusted=path,
                frame_step=frame_step,
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            )
            for proposal in candidate_path
        ):
            continue
        mode_switches = sum(
            first_proposal.mode != second_proposal.mode
            for first_proposal, second_proposal in zip(
                candidate_path,
                candidate_path[1:],
            )
        )
        score = sum(
            proposal.verification_score
            + proposal.attention_score
            * float(
                SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                    "complete_path_attention_weight"
                ]
            )
            for proposal in candidate_path
        ) - mode_switches * float(
            SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                "complete_path_mode_switch_penalty"
            ]
        )
        ranked.append((score, candidate_path))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked:
        return ()
    if (
        len(ranked) > 1
        and ranked[0][0] - ranked[1][0]
        < float(
            SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                "complete_path_minimum_margin"
            ]
        )
    ):
        return ()
    return ranked[0][1]


def _motion_diagnostics(
    counters: Counter[str],
) -> _RawMotionDiagnostics:
    return _RawMotionDiagnostics(
        generated=counters["generated"],
        rejected_scale_or_shape=counters["rejected_scale_or_shape"],
        rejected_appearance=counters["rejected_appearance"],
        rejected_player_body=counters["rejected_player_body"],
        rejected_ambiguity=counters["rejected_ambiguity"],
        rejected_temporal_consistency=counters[
            "rejected_temporal_consistency"
        ],
        near_feet=counters["near_feet"],
        trajectory_corridor=counters["trajectory_corridor"],
        global_fallback=counters["global_fallback"],
        rejected_verification=counters["rejected_verification"],
        rejected_path_plausibility=counters[
            "rejected_path_plausibility"
        ],
        rejected_alternative_margin=counters[
            "rejected_alternative_margin"
        ],
        near_feet_generated=counters["near_feet_generated"],
        trajectory_corridor_generated=counters[
            "trajectory_corridor_generated"
        ],
        global_fallback_generated=counters[
            "global_fallback_generated"
        ],
        minimum_accepted_trajectory_margin=(
            round(counters["accepted_margin_min"], 6)
            if counters["accepted_margin_count"]
            else None
        ),
        mean_accepted_trajectory_margin=(
            round(
                counters["accepted_margin_sum"]
                / counters["accepted_margin_count"],
                6,
            )
            if counters["accepted_margin_count"]
            else None
        ),
        attention_accepted=counters["attention_accepted"],
        attention_rejected_visual_evidence=counters[
            "attention_rejected_visual_evidence"
        ],
        attention_rejected_convergence=counters[
            "attention_rejected_convergence"
        ],
        attention_rejected_temporal_path=counters[
            "attention_rejected_temporal_path"
        ],
    )


def _add_kalman_guided_reacquisitions(
    tracks: Iterable[BallTrack],
    *,
    detector_candidates: list[BallPoint],
    records: list[dict[str, Any]],
    video: Path,
    width: int,
    height: int,
    fps: float,
    frame_step: int,
) -> tuple[tuple[BallTrack, ...], _KalmanReacquisitionDiagnostics]:
    tracks = tuple(tracks)
    if not tracks or len(records) < 3:
        return tracks, _KalmanReacquisitionDiagnostics()
    trusted = sorted(
        (point for track in tracks for point in track.points),
        key=lambda point: point.source_frame,
    )
    reference_diameters = [
        point.box_diagonal for point in trusted if point.box_diagonal > 0
    ]
    if not reference_diameters:
        return tracks, _KalmanReacquisitionDiagnostics()
    reference_diameter = median(reference_diameters)
    records_by_frame = {
        int(record["source_frame"]): record for record in records
    }
    ordered_frames = sorted(records_by_frame)
    trusted_frames = {point.source_frame for point in trusted}
    missing_frames = [
        source_frame
        for source_frame in ordered_frames
        if source_frame not in trusted_frames
    ]
    if not missing_frames:
        return tracks, _KalmanReacquisitionDiagnostics()

    forward = _kalman_missing_frame_predictions(
        trusted,
        ordered_frames=ordered_frames,
        fps=fps,
    )
    backward = _kalman_missing_frame_predictions(
        trusted,
        ordered_frames=list(reversed(ordered_frames)),
        fps=fps,
    )
    grayscale = _read_sampled_grayscale_frames(video, ordered_frames)
    raw_by_frame: dict[int, list[_RawMotionProposal]] = defaultdict(list)
    for previous_frame, source_frame, following_frame in zip(
        ordered_frames,
        ordered_frames[1:],
        ordered_frames[2:],
    ):
        if source_frame not in missing_frames:
            continue
        proposals, _ = _raw_motion_frame_proposals(
            previous=grayscale[previous_frame],
            current=grayscale[source_frame],
            following=grayscale[following_frame],
            record=records_by_frame[source_frame],
            source_frame=source_frame,
            clip_seconds=float(records_by_frame[source_frame]["clip_seconds"]),
            width=width,
            height=height,
            reference_diameter=reference_diameter,
            trusted=trusted,
            frame_step=frame_step,
        )
        raw_by_frame[source_frame].extend(proposals)
    detector_by_frame: dict[int, list[BallPoint]] = defaultdict(list)
    for point in detector_candidates:
        if point.source_frame not in trusted_frames:
            detector_by_frame[point.source_frame].append(point)

    counters: Counter[str] = Counter()
    accepted: list[_RawMotionProposal] = []
    maximum_prediction_frames = int(
        SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
            "maximum_prediction_only_frames"
        ]
    )
    for source_frame in missing_frames:
        previous = [
            point for point in trusted if point.source_frame < source_frame
        ]
        following = [
            point for point in trusted if point.source_frame > source_frame
        ]
        if not previous or not following:
            continue
        first = previous[-1]
        second = following[0]
        missing_between = (
            (second.source_frame - first.source_frame) // frame_step - 1
        )
        if missing_between > maximum_prediction_frames:
            counters["expired_predictions"] += 1
            continue
        forward_prediction = forward.get(source_frame)
        backward_prediction = backward.get(source_frame)
        if forward_prediction is None or backward_prediction is None:
            counters["expired_predictions"] += 1
            continue
        forward_radius = _kalman_roi_radius(forward_prediction.covariance)
        backward_radius = _kalman_roi_radius(backward_prediction.covariance)
        disagreement = hypot(
            forward_prediction.x - backward_prediction.x,
            forward_prediction.y - backward_prediction.y,
        )
        maximum_disagreement = max(
            float(
                SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
                    "minimum_roi_radius_pixels"
                ]
            ),
            min(forward_radius, backward_radius)
            * float(
                SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
                    "maximum_bidirectional_disagreement_fraction"
                ]
            ),
        )
        if disagreement > maximum_disagreement:
            counters["bidirectional_rejections"] += 1
            continue

        candidates = list(raw_by_frame.get(source_frame, []))
        for point in detector_by_frame.get(source_frame, []):
            mode = _motion_search_mode(
                point,
                record=records_by_frame[source_frame],
                trusted=trusted,
                frame_step=frame_step,
                reference_diameter=reference_diameter,
            )
            candidates.append(
                _RawMotionProposal(
                    point=point,
                    mode=mode,
                    appearance_score=1.0,
                )
            )
        candidates = list(_deduplicate_reacquisition_candidates(candidates))
        supported = [
            candidate
            for candidate in candidates
            if hypot(
                candidate.point.x - forward_prediction.x,
                candidate.point.y - forward_prediction.y,
            )
            <= forward_radius
            and hypot(
                candidate.point.x - backward_prediction.x,
                candidate.point.y - backward_prediction.y,
            )
            <= backward_radius
        ]
        local = [
            candidate
            for candidate in supported
            if candidate.mode in {"near_feet", "trajectory_corridor"}
        ]
        eligible = local if local else [
            candidate
            for candidate in supported
            if candidate.mode == "global_fallback"
        ]
        if not eligible:
            counters["visual_evidence_misses"] += 1
            continue
        if len(eligible) != 1:
            counters["conflicts"] += len(eligible)
            continue
        candidate = eligible[0]
        visual_source = (
            "yolo"
            if candidate.point.evidence == "detector"
            else "raw_motion_micro_crop"
        )
        distance_fraction = max(
            hypot(
                candidate.point.x - forward_prediction.x,
                candidate.point.y - forward_prediction.y,
            )
            / forward_radius,
            hypot(
                candidate.point.x - backward_prediction.x,
                candidate.point.y - backward_prediction.y,
            )
            / backward_radius,
        )
        accepted.append(
            _RawMotionProposal(
                point=BallPoint(
                    source_frame=source_frame,
                    clip_seconds=candidate.point.clip_seconds,
                    confidence=candidate.point.confidence,
                    x=candidate.point.x,
                    y=candidate.point.y,
                    box_diagonal=candidate.point.box_diagonal,
                    evidence=(
                        f"kalman_guided_{visual_source}_{candidate.mode}"
                    ),
                    temporal_score=round(1 - distance_fraction, 6),
                    source_attribution="kalman_guided_visual_reacquired",
                ),
                mode=candidate.mode,
                appearance_score=candidate.appearance_score,
            )
        )
        counters["successes"] += 1
        counters[candidate.mode] += 1
        counters[
            "yolo_candidates"
            if visual_source == "yolo"
            else "raw_motion_candidates"
        ] += 1

    additions_by_track: dict[int, list[BallPoint]] = defaultdict(list)
    for proposal in accepted:
        track_index = min(
            range(len(tracks)),
            key=lambda index: min(
                abs(proposal.point.source_frame - point.source_frame)
                for point in tracks[index].points
            ),
        )
        additions_by_track[track_index].append(proposal.point)
    enriched = tuple(
        BallTrack(
            track.track_id,
            sorted(
                [*track.points, *additions_by_track[index]],
                key=lambda point: point.source_frame,
            ),
        )
        for index, track in enumerate(tracks)
    )
    return enriched, _kalman_diagnostics(counters)


def _kalman_missing_frame_predictions(
    trusted: list[BallPoint],
    *,
    ordered_frames: list[int],
    fps: float,
) -> dict[int, _KalmanPrediction]:
    measurements = {point.source_frame: point for point in trusted}
    state: np.ndarray | None = None
    covariance: np.ndarray | None = None
    previous_frame: int | None = None
    predictions: dict[int, _KalmanPrediction] = {}
    for source_frame in ordered_frames:
        measurement = measurements.get(source_frame)
        if state is None or covariance is None:
            if measurement is None:
                continue
            state = np.array(
                [measurement.x, measurement.y, 0.0, 0.0],
                dtype=np.float64,
            )
            covariance = np.diag(
                [
                    SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
                        "initial_position_variance"
                    ],
                    SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
                        "initial_position_variance"
                    ],
                    SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
                        "initial_velocity_variance"
                    ],
                    SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
                        "initial_velocity_variance"
                    ],
                ]
            )
            previous_frame = source_frame
            continue
        if previous_frame is None:
            raise AssertionError("Kalman state requires a previous frame")
        delta_seconds = abs(source_frame - previous_frame) / fps
        transition = np.array(
            [
                [1.0, 0.0, delta_seconds, 0.0],
                [0.0, 1.0, 0.0, delta_seconds],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )
        process_noise = np.diag(
            [
                SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
                    "process_position_variance"
                ],
                SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
                    "process_position_variance"
                ],
                SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
                    "process_velocity_variance"
                ],
                SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
                    "process_velocity_variance"
                ],
            ]
        )
        state = transition @ state
        covariance = transition @ covariance @ transition.T + process_noise
        if measurement is None:
            predictions[source_frame] = _KalmanPrediction(
                source_frame=source_frame,
                x=float(state[0]),
                y=float(state[1]),
                covariance=covariance[:2, :2].copy(),
            )
        else:
            observation = np.array([measurement.x, measurement.y])
            observation_model = np.array(
                [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]
            )
            measurement_noise = np.eye(2) * float(
                SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
                    "measurement_variance"
                ]
            )
            innovation = observation - observation_model @ state
            innovation_covariance = (
                observation_model @ covariance @ observation_model.T
                + measurement_noise
            )
            gain = (
                covariance
                @ observation_model.T
                @ np.linalg.inv(innovation_covariance)
            )
            state = state + gain @ innovation
            covariance = (
                np.eye(4) - gain @ observation_model
            ) @ covariance
        previous_frame = source_frame
    return predictions


def _kalman_roi_radius(covariance: np.ndarray) -> float:
    positional_sigma = float(
        np.sqrt(max(np.linalg.eigvalsh(covariance)))
    )
    return min(
        float(
            SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
                "maximum_roi_radius_pixels"
            ]
        ),
        max(
            float(
                SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
                    "minimum_roi_radius_pixels"
                ]
            ),
            positional_sigma
            * float(
                SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
                    "uncertainty_sigma"
                ]
            ),
        ),
    )


def _deduplicate_reacquisition_candidates(
    candidates: Iterable[_RawMotionProposal],
) -> tuple[_RawMotionProposal, ...]:
    retained: list[_RawMotionProposal] = []
    maximum_distance = float(
        SOCCERTRACK_KALMAN_REACQUISITION_PROFILE[
            "candidate_deduplication_pixels"
        ]
    )
    for candidate in sorted(
        candidates,
        key=lambda item: item.point.evidence != "detector",
    ):
        if any(
            hypot(
                candidate.point.x - existing.point.x,
                candidate.point.y - existing.point.y,
            )
            <= maximum_distance
            for existing in retained
        ):
            continue
        retained.append(candidate)
    return tuple(retained)


def _kalman_diagnostics(
    counters: Counter[str],
) -> _KalmanReacquisitionDiagnostics:
    return _KalmanReacquisitionDiagnostics(
        successes=counters["successes"],
        yolo_candidates=counters["yolo_candidates"],
        raw_motion_candidates=counters["raw_motion_candidates"],
        near_feet=counters["near_feet"],
        trajectory_corridor=counters["trajectory_corridor"],
        global_fallback=counters["global_fallback"],
        expired_predictions=counters["expired_predictions"],
        bidirectional_rejections=counters["bidirectional_rejections"],
        visual_evidence_misses=counters["visual_evidence_misses"],
        conflicts=counters["conflicts"],
    )


def _add_dense_optical_flow_bridges(
    tracks: Iterable[BallTrack],
    *,
    records: list[dict[str, Any]],
    video: Path,
    width: int,
    height: int,
    fps: float,
    frame_step: int,
) -> tuple[tuple[BallTrack, ...], _DenseFlowDiagnostics]:
    tracks = tuple(tracks)
    records_by_frame = {
        int(record["source_frame"]): record for record in records
    }
    allowed_sources = {
        "yolo26_observed",
        "temporal_detector_observed",
        "raw_motion_micro_crop_supported",
    }
    counters: Counter[str] = Counter()
    confidences: list[float] = []
    additions: dict[int, list[BallPoint]] = defaultdict(list)
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        for track_index, track in enumerate(tracks):
            trusted = sorted(
                (
                    point
                    for point in track.points
                    if point.source_attribution in allowed_sources
                ),
                key=lambda point: point.source_frame,
            )
            for first, second in zip(trusted, trusted[1:]):
                frame_gap = second.source_frame - first.source_frame
                if frame_gap <= frame_step:
                    continue
                if frame_gap > int(
                    SOCCERTRACK_DENSE_FLOW_PROFILE[
                        "maximum_bridge_raw_frames"
                    ]
                ):
                    counters["expired_bridges"] += 1
                    continue
                frames = _read_dense_grayscale_range(
                    capture,
                    first.source_frame,
                    second.source_frame,
                )
                forward, forward_rejection = _dense_optical_flow_path(
                    frames,
                    seed=first,
                    target_frame=second.source_frame,
                    fps=fps,
                    width=width,
                    height=height,
                )
                backward, backward_rejection = _dense_optical_flow_path(
                    frames,
                    seed=second,
                    target_frame=first.source_frame,
                    fps=fps,
                    width=width,
                    height=height,
                )
                rejection = forward_rejection or backward_rejection
                if rejection is not None:
                    counters[rejection] += 1
                    continue
                endpoint_limit = median(
                    (first.box_diagonal, second.box_diagonal)
                ) * float(
                    SOCCERTRACK_DENSE_FLOW_PROFILE[
                        "maximum_endpoint_error_ball_diameters"
                    ]
                )
                if (
                    hypot(
                        forward[second.source_frame].x - second.x,
                        forward[second.source_frame].y - second.y,
                    )
                    > endpoint_limit
                    or hypot(
                        backward[first.source_frame].x - first.x,
                        backward[first.source_frame].y - first.y,
                    )
                    > endpoint_limit
                ):
                    counters["endpoint_disagreement"] += 1
                    continue
                path_limit = median(
                    (first.box_diagonal, second.box_diagonal)
                ) * float(
                    SOCCERTRACK_DENSE_FLOW_PROFILE[
                        "maximum_path_disagreement_ball_diameters"
                    ]
                )
                common_frames = set(forward) & set(backward)
                if any(
                    hypot(
                        forward[source_frame].x - backward[source_frame].x,
                        forward[source_frame].y - backward[source_frame].y,
                    )
                    > path_limit
                    for source_frame in common_frames
                ):
                    counters["rejected_drift"] += 1
                    continue

                bridge_points: list[BallPoint] = []
                for source_frame in range(
                    first.source_frame + frame_step,
                    second.source_frame,
                    frame_step,
                ):
                    if source_frame not in records_by_frame:
                        counters["rejected_drift"] += 1
                        bridge_points = []
                        break
                    forward_sample = forward[source_frame]
                    backward_sample = backward[source_frame]
                    center_x = (
                        forward_sample.x + backward_sample.x
                    ) / 2
                    center_y = (
                        forward_sample.y + backward_sample.y
                    ) / 2
                    confidence = min(
                        forward_sample.confidence,
                        backward_sample.confidence,
                        1
                        - hypot(
                            forward_sample.x - backward_sample.x,
                            forward_sample.y - backward_sample.y,
                        )
                        / path_limit,
                    )
                    point = BallPoint(
                        source_frame=source_frame,
                        clip_seconds=float(
                            records_by_frame[source_frame]["clip_seconds"]
                        ),
                        confidence=round(confidence, 6),
                        x=center_x,
                        y=center_y,
                        box_diagonal=median(
                            (first.box_diagonal, second.box_diagonal)
                        ),
                        evidence="dense_bidirectional_optical_flow",
                        temporal_score=round(confidence, 6),
                        source_attribution="optical_flow_propagated",
                    )
                    if _inside_player_upper_body(
                        point,
                        records_by_frame[source_frame],
                    ):
                        counters["player_upper_body_rejections"] += 1
                        bridge_points = []
                        break
                    bridge_points.append(point)
                if not bridge_points:
                    continue
                additions[track_index].extend(bridge_points)
                confidences.extend(
                    point.temporal_score
                    for point in bridge_points
                    if point.temporal_score is not None
                )
                counters["successful_bridges"] += 1
                counters["accepted_points"] += len(bridge_points)
    finally:
        capture.release()

    enriched = tuple(
        BallTrack(
            track.track_id,
            sorted(
                [*track.points, *additions[index]],
                key=lambda point: point.source_frame,
            ),
        )
        for index, track in enumerate(tracks)
    )
    return enriched, _dense_flow_diagnostics(counters, confidences)


def _read_dense_grayscale_range(
    capture: cv2.VideoCapture,
    first_frame: int,
    last_frame: int,
) -> dict[int, np.ndarray]:
    capture.set(cv2.CAP_PROP_POS_FRAMES, first_frame)
    frames: dict[int, np.ndarray] = {}
    for source_frame in range(first_frame, last_frame + 1):
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError(
                f"Could not read source frame {source_frame} for dense flow"
            )
        frames[source_frame] = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return frames


def _dense_optical_flow_path(
    frames: dict[int, np.ndarray],
    *,
    seed: BallPoint,
    target_frame: int,
    fps: float,
    width: int,
    height: int,
) -> tuple[dict[int, _DenseFlowSample], str | None]:
    direction = 1 if target_frame > seed.source_frame else -1
    ordered_frames = list(
        range(seed.source_frame, target_frame + direction, direction)
    )
    seed_frame = frames[seed.source_frame]
    patch_radius = min(
        int(SOCCERTRACK_DENSE_FLOW_PROFILE["maximum_patch_radius_pixels"]),
        max(
            int(SOCCERTRACK_DENSE_FLOW_PROFILE["minimum_patch_radius_pixels"]),
            round(
                seed.box_diagonal
                * float(
                    SOCCERTRACK_DENSE_FLOW_PROFILE[
                        "patch_radius_ball_diameters"
                    ]
                )
            ),
        ),
    )
    left = max(0, round(seed.x) - patch_radius)
    right = min(seed_frame.shape[1], round(seed.x) + patch_radius + 1)
    top = max(0, round(seed.y) - patch_radius)
    bottom = min(seed_frame.shape[0], round(seed.y) + patch_radius + 1)
    patch = seed_frame[top:bottom, left:right]
    features = cv2.goodFeaturesToTrack(
        patch,
        maxCorners=20,
        qualityLevel=float(
            SOCCERTRACK_DENSE_FLOW_PROFILE["feature_quality_level"]
        ),
        minDistance=float(
            SOCCERTRACK_DENSE_FLOW_PROFILE[
                "feature_minimum_distance_pixels"
            ]
        ),
    )
    minimum_features = int(
        SOCCERTRACK_DENSE_FLOW_PROFILE["minimum_retained_features"]
    )
    if features is None or len(features) < minimum_features:
        return {}, "insufficient_feature_support"
    features[:, 0, 0] += left
    features[:, 0, 1] += top
    initial_center = np.median(features[:, 0, :], axis=0)
    initial_spread = float(
        np.median(
            np.linalg.norm(
                features[:, 0, :] - initial_center,
                axis=1,
            )
        )
    )
    if initial_spread <= 0:
        return {}, "insufficient_feature_support"
    template = _extract_ball_template(
        seed_frame,
        seed,
        radius_scale=0.6,
    )
    if template is None:
        return {}, "appearance_rejections"

    samples = {
        seed.source_frame: _DenseFlowSample(
            x=seed.x,
            y=seed.y,
            confidence=1.0,
        )
    }
    center = np.array([seed.x, seed.y], dtype=np.float64)
    previous_velocity: np.ndarray | None = None
    previous_frame = seed.source_frame
    previous_gray = seed_frame
    current_features = features.astype(np.float32)
    for source_frame in ordered_frames[1:]:
        current_gray = frames[source_frame]
        next_features, status, _ = cv2.calcOpticalFlowPyrLK(
            previous_gray,
            current_gray,
            current_features,
            None,
            winSize=(
                int(SOCCERTRACK_DENSE_FLOW_PROFILE["lk_window_pixels"]),
                int(SOCCERTRACK_DENSE_FLOW_PROFILE["lk_window_pixels"]),
            ),
            maxLevel=int(
                SOCCERTRACK_DENSE_FLOW_PROFILE["lk_pyramid_levels"]
            ),
        )
        if next_features is None or status is None:
            return {}, "insufficient_feature_support"
        reverse_features, reverse_status, _ = cv2.calcOpticalFlowPyrLK(
            current_gray,
            previous_gray,
            next_features,
            None,
            winSize=(
                int(SOCCERTRACK_DENSE_FLOW_PROFILE["lk_window_pixels"]),
                int(SOCCERTRACK_DENSE_FLOW_PROFILE["lk_window_pixels"]),
            ),
            maxLevel=int(
                SOCCERTRACK_DENSE_FLOW_PROFILE["lk_pyramid_levels"]
            ),
        )
        if reverse_features is None or reverse_status is None:
            return {}, "insufficient_feature_support"
        forward_backward_error = np.linalg.norm(
            reverse_features[:, 0, :] - current_features[:, 0, :],
            axis=1,
        )
        valid = (
            status[:, 0].astype(bool)
            & reverse_status[:, 0].astype(bool)
            & (
                forward_backward_error
                <= float(
                    SOCCERTRACK_DENSE_FLOW_PROFILE[
                        "maximum_forward_backward_error_pixels"
                    ]
                )
            )
        )
        if int(valid.sum()) < minimum_features:
            return {}, "insufficient_feature_support"
        retained_previous = current_features[valid, 0, :]
        retained_next = next_features[valid, 0, :]
        displacement = np.median(
            retained_next - retained_previous,
            axis=0,
        )
        predicted_center = center + displacement
        search_radius = min(
            int(
                SOCCERTRACK_DENSE_FLOW_PROFILE[
                    "maximum_local_search_pixels"
                ]
            ),
            max(
                4,
                round(
                    seed.box_diagonal
                    * float(
                        SOCCERTRACK_DENSE_FLOW_PROFILE[
                            "local_search_ball_diameters"
                        ]
                    )
                ),
            ),
        )
        match = _template_match(
            current_gray,
            template,
            predicted_x=float(predicted_center[0]),
            predicted_y=float(predicted_center[1]),
            search_radius=search_radius,
        )
        minimum_template_score = float(
            SOCCERTRACK_DENSE_FLOW_PROFILE["minimum_template_score"]
        )
        if match.score < minimum_template_score:
            return {}, "appearance_rejections"
        corrected_center = np.array([match.x, match.y], dtype=np.float64)
        correction = corrected_center - predicted_center
        retained_next = retained_next + correction
        feature_center = np.median(retained_next, axis=0)
        feature_spread = float(
            np.median(
                np.linalg.norm(
                    retained_next - feature_center,
                    axis=1,
                )
            )
        )
        scale_ratio = feature_spread / initial_spread
        if not (
            float(
                SOCCERTRACK_DENSE_FLOW_PROFILE[
                    "minimum_feature_scale_ratio"
                ]
            )
            <= scale_ratio
            <= float(
                SOCCERTRACK_DENSE_FLOW_PROFILE[
                    "maximum_feature_scale_ratio"
                ]
            )
        ):
            return {}, "rejected_drift"
        elapsed = abs(source_frame - previous_frame) / fps
        velocity = (corrected_center - center) / elapsed
        if np.linalg.norm(velocity) > float(
            SOCCERTRACK_DENSE_FLOW_PROFILE[
                "maximum_speed_pixels_per_second"
            ]
        ):
            return {}, "rejected_drift"
        if (
            previous_velocity is not None
            and np.linalg.norm(velocity - previous_velocity) / elapsed
            > float(
                SOCCERTRACK_DENSE_FLOW_PROFILE[
                    "maximum_acceleration_pixels_per_second_squared"
                ]
            )
        ):
            return {}, "rejected_drift"
        point = BallPoint(
            source_frame=source_frame,
            clip_seconds=0.0,
            confidence=0.0,
            x=float(corrected_center[0]),
            y=float(corrected_center[1]),
        )
        if not _inside_soccertrack_pitch(point, width, height):
            return {}, "rejected_drift"
        fb_confidence = 1 - float(
            np.median(forward_backward_error[valid])
        ) / float(
            SOCCERTRACK_DENSE_FLOW_PROFILE[
                "maximum_forward_backward_error_pixels"
            ]
        )
        appearance_confidence = (
            match.score - minimum_template_score
        ) / (1 - minimum_template_score)
        samples[source_frame] = _DenseFlowSample(
            x=float(corrected_center[0]),
            y=float(corrected_center[1]),
            confidence=max(
                0.0,
                min(1.0, fb_confidence, appearance_confidence),
            ),
        )
        center = corrected_center
        previous_velocity = velocity
        previous_frame = source_frame
        previous_gray = current_gray
        current_features = retained_next.reshape(-1, 1, 2).astype(
            np.float32
        )
    return samples, None


def _dense_flow_diagnostics(
    counters: Counter[str],
    confidences: list[float],
) -> _DenseFlowDiagnostics:
    return _DenseFlowDiagnostics(
        accepted_points=counters["accepted_points"],
        successful_bridges=counters["successful_bridges"],
        rejected_drift=counters["rejected_drift"],
        expired_bridges=counters["expired_bridges"],
        endpoint_disagreement=counters["endpoint_disagreement"],
        insufficient_feature_support=counters[
            "insufficient_feature_support"
        ],
        appearance_rejections=counters["appearance_rejections"],
        player_upper_body_rejections=counters[
            "player_upper_body_rejections"
        ],
        minimum_path_confidence=(
            round(min(confidences), 6) if confidences else None
        ),
        mean_path_confidence=(
            round(sum(confidences) / len(confidences), 6)
            if confidences
            else None
        ),
    )


def _add_motion_supported_points(
    tracks: Iterable[BallTrack],
    *,
    video: Path,
    fps: float,
    frame_step: int,
    maximum_gap_seconds: float,
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    plans = [
        plan
        for track_index, track in enumerate(tracks)
        for plan in _motion_bridge_plans(
            track,
            track_index=track_index,
            fps=fps,
            frame_step=frame_step,
            maximum_gap_seconds=maximum_gap_seconds,
        )
    ]
    if not plans:
        return tracks

    frame_uses: dict[int, int] = defaultdict(int)
    plans_by_end_frame: dict[int, list[int]] = defaultdict(list)
    for plan_index, plan in enumerate(plans):
        for source_frame in plan.frames:
            frame_uses[source_frame] += 1
        plans_by_end_frame[plan.second.source_frame].append(plan_index)

    additions: dict[int, list[BallPoint]] = defaultdict(list)
    grayscale_frames: dict[int, np.ndarray] = {}
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        for source_frame in range(max(frame_uses) + 1):
            if source_frame not in frame_uses:
                if not capture.grab():
                    raise RuntimeError(
                        f"Could not skip to source frame {source_frame} in {video}"
                    )
                continue
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(
                    f"Could not read source frame {source_frame} from {video}"
                )
            grayscale_frames[source_frame] = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2GRAY,
            )
            for plan_index in plans_by_end_frame.get(source_frame, []):
                plan = plans[plan_index]
                point = _motion_circle_bridge_point(
                    plan,
                    {
                        frame: grayscale_frames[frame]
                        for frame in plan.frames
                    },
                    fps=fps,
                )
                if point is not None:
                    additions[plan.track_index].append(point)
                for frame in plan.frames:
                    frame_uses[frame] -= 1
                    if frame_uses[frame] == 0:
                        del grayscale_frames[frame]
    finally:
        capture.release()

    return tuple(
        BallTrack(
            track.track_id,
            sorted(
                [*track.points, *additions[track_index]],
                key=lambda point: point.source_frame,
            ),
        )
        for track_index, track in enumerate(tracks)
    )


def _motion_bridge_plans(
    track: BallTrack,
    *,
    track_index: int,
    fps: float,
    frame_step: int,
    maximum_gap_seconds: float,
) -> tuple[_MotionBridge, ...]:
    if frame_step < 1 or fps <= 0 or maximum_gap_seconds <= 0:
        raise ValueError("Motion bridge frame step, FPS, and gap must be positive")
    points = sorted(
        (
            point
            for point in track.points
            if point.evidence == "detector"
        ),
        key=lambda point: point.source_frame,
    )
    plans: list[_MotionBridge] = []
    for index, (first, second) in enumerate(zip(points, points[1:])):
        if (
            second.source_frame - first.source_frame != frame_step * 2
            or second.clip_seconds - first.clip_seconds
            > maximum_gap_seconds + 1e-6
            or first.box_diagonal <= 0
            or second.box_diagonal <= 0
        ):
            continue
        if index > 0:
            previous = points[index - 1]
            incoming_x = first.x - previous.x
            incoming_y = first.y - previous.y
            bridge_x = second.x - first.x
            bridge_y = second.y - first.y
            if incoming_x * bridge_x + incoming_y * bridge_y <= 0:
                continue
        plans.append(
            _MotionBridge(
                track_index=track_index,
                first=first,
                second=second,
            )
        )
    return tuple(plans)


def _motion_circle_bridge_point(
    plan: _MotionBridge,
    grayscale_frames: dict[int, np.ndarray],
    *,
    fps: float,
    maximum_prediction_distance_diameters: float = 0.75,
    maximum_motion_distance_diameters: float = 0.75,
) -> BallPoint | None:
    if fps <= 0:
        raise ValueError("Motion bridge FPS must be positive")
    if (
        maximum_prediction_distance_diameters <= 0
        or maximum_motion_distance_diameters <= 0
    ):
        raise ValueError("Motion bridge distance limits must be positive")

    reference_diameter = median(
        (plan.first.box_diagonal, plan.second.box_diagonal)
    )
    target_frame = plan.target_frame
    alpha = (
        (target_frame - plan.first.source_frame)
        / (plan.second.source_frame - plan.first.source_frame)
    )
    predicted_x = plan.first.x + (plan.second.x - plan.first.x) * alpha
    predicted_y = plan.first.y + (plan.second.y - plan.first.y) * alpha
    search_radius = max(8, round(reference_diameter * 1.5))
    circles = _nearby_circles(
        grayscale_frames[target_frame],
        center_x=predicted_x,
        center_y=predicted_y,
        search_radius=search_radius,
        reference_diameter=reference_diameter,
    )
    maximum_prediction_distance = (
        reference_diameter * maximum_prediction_distance_diameters
    )
    previous_motion = _compact_motion_centers(
        cv2.absdiff(
            grayscale_frames[target_frame],
            grayscale_frames[plan.first.source_frame],
        ),
        center_x=predicted_x,
        center_y=predicted_y,
        search_radius=search_radius,
        reference_diameter=reference_diameter,
    )
    following_motion = _compact_motion_centers(
        cv2.absdiff(
            grayscale_frames[target_frame],
            grayscale_frames[plan.second.source_frame],
        ),
        center_x=predicted_x,
        center_y=predicted_y,
        search_radius=search_radius,
        reference_diameter=reference_diameter,
    )
    maximum_motion_distance = (
        reference_diameter * maximum_motion_distance_diameters
    )
    supported = [
        circle
        for circle in circles
        if hypot(circle.x - predicted_x, circle.y - predicted_y)
        <= maximum_prediction_distance
        and _nearest_motion_distance(circle, previous_motion)
        <= maximum_motion_distance
        and _nearest_motion_distance(circle, following_motion)
        <= maximum_motion_distance
    ]
    if len(supported) != 1:
        return None

    circle = supported[0]
    prediction_score = 1 - (
        hypot(circle.x - predicted_x, circle.y - predicted_y)
        / maximum_prediction_distance
    )
    motion_score = min(
        1
        - _nearest_motion_distance(circle, previous_motion)
        / maximum_motion_distance,
        1
        - _nearest_motion_distance(circle, following_motion)
        / maximum_motion_distance,
    )
    return BallPoint(
        source_frame=target_frame,
        clip_seconds=round(
            plan.first.clip_seconds
            + (target_frame - plan.first.source_frame) / fps,
            3,
        ),
        confidence=min(plan.first.confidence, plan.second.confidence),
        x=circle.x,
        y=circle.y,
        box_diagonal=reference_diameter,
        evidence="motion_circle",
        temporal_score=round(min(prediction_score, motion_score), 6),
        source_attribution="temporal_detector_observed",
    )


def _nearby_circles(
    grayscale: np.ndarray,
    *,
    center_x: float,
    center_y: float,
    search_radius: int,
    reference_diameter: float,
) -> tuple[_CircleCandidate, ...]:
    left = max(0, round(center_x) - search_radius)
    right = min(grayscale.shape[1], round(center_x) + search_radius + 1)
    top = max(0, round(center_y) - search_radius)
    bottom = min(grayscale.shape[0], round(center_y) + search_radius + 1)
    search = grayscale[top:bottom, left:right]
    minimum_radius = max(2, round(reference_diameter * 0.2))
    maximum_radius = max(
        minimum_radius + 1,
        round(reference_diameter * 0.7),
    )
    circles = cv2.HoughCircles(
        cv2.medianBlur(search, 5),
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=max(4, round(reference_diameter * 0.5)),
        param1=70,
        param2=max(6, round(reference_diameter * 0.6)),
        minRadius=minimum_radius,
        maxRadius=maximum_radius,
    )
    if circles is None:
        return ()
    return tuple(
        _CircleCandidate(
            x=float(x + left),
            y=float(y + top),
            radius=float(radius),
        )
        for x, y, radius in circles[0]
    )


def _compact_motion_centers(
    difference: np.ndarray,
    *,
    center_x: float,
    center_y: float,
    search_radius: int,
    reference_diameter: float,
) -> tuple[tuple[float, float], ...]:
    left = max(0, round(center_x) - search_radius)
    right = min(difference.shape[1], round(center_x) + search_radius + 1)
    top = max(0, round(center_y) - search_radius)
    bottom = min(difference.shape[0], round(center_y) + search_radius + 1)
    search = difference[top:bottom, left:right]
    threshold = max(16, round(float(np.percentile(search, 90))))
    _, mask = cv2.threshold(search, threshold, 255, cv2.THRESH_BINARY)
    count, labels, statistics, centroids = cv2.connectedComponentsWithStats(mask)
    maximum_area = reference_diameter**2 * 2
    maximum_extent = reference_diameter * 2
    return tuple(
        (float(centroids[index][0] + left), float(centroids[index][1] + top))
        for index in range(1, count)
        if (
            2 <= statistics[index, cv2.CC_STAT_AREA] <= maximum_area
            and statistics[index, cv2.CC_STAT_WIDTH] <= maximum_extent
            and statistics[index, cv2.CC_STAT_HEIGHT] <= maximum_extent
        )
    )


def _nearest_motion_distance(
    circle: _CircleCandidate,
    motion_centers: Iterable[tuple[float, float]],
) -> float:
    return min(
        (
            hypot(circle.x - center_x, circle.y - center_y)
            for center_x, center_y in motion_centers
        ),
        default=float("inf"),
    )


def _load_cache(
    cache_path: Path, expected_manifest_sha256: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not cache_path.is_file():
        raise FileNotFoundError(f"Detection cache does not exist: {cache_path}")
    lines = cache_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("Detection cache is empty")
    metadata = json.loads(lines[0])
    if metadata.get("manifest_sha256") != expected_manifest_sha256:
        raise ValueError("Detection cache was created for a different manifest")
    records = [json.loads(line) for line in lines[1:]]
    records = [record for record in records if record.get("type") == "frame"]
    if not records:
        raise ValueError("Detection cache contains no frames")
    records.sort(key=lambda record: int(record["source_frame"]))
    return metadata, records


def _records_in_analysis_window(
    records: list[dict[str, Any]],
    *,
    start_seconds: float | None,
    end_seconds: float | None,
) -> list[dict[str, Any]]:
    if (start_seconds is None) != (end_seconds is None):
        raise ValueError(
            "Analysis start and end seconds must be provided together"
        )
    if start_seconds is None or end_seconds is None:
        return records
    if start_seconds < 0 or end_seconds <= start_seconds:
        raise ValueError("Analysis window must have a non-negative start and end")
    windowed = [
        record
        for record in records
        if start_seconds <= float(record["clip_seconds"]) < end_seconds
    ]
    if not windowed:
        raise ValueError("Analysis window contains no cached frames")
    return windowed


def _analysis_window(
    start_seconds: float | None,
    end_seconds: float | None,
) -> dict[str, float] | None:
    if start_seconds is None or end_seconds is None:
        return None
    return {
        "start_seconds": start_seconds,
        "end_seconds": end_seconds,
    }


def _ball_points(record: dict[str, Any]) -> list[BallPoint]:
    points: list[BallPoint] = []
    for detection in record.get("detections", []):
        if detection.get("class_name") != "sports ball":
            continue
        points.append(
            BallPoint(
                source_frame=int(record["source_frame"]),
                clip_seconds=float(record["clip_seconds"]),
                confidence=float(detection["confidence"]),
                x=(float(detection["x1"]) + float(detection["x2"])) / 2,
                y=(float(detection["y1"]) + float(detection["y2"])) / 2,
                box_diagonal=hypot(
                    float(detection["x2"]) - float(detection["x1"]),
                    float(detection["y2"]) - float(detection["y1"]),
                ),
            )
        )
    return points


def _inside_player_upper_body(
    point: BallPoint,
    record: dict[str, Any],
    *,
    minimum_person_confidence: float = 0.25,
    upper_body_fraction: float = 0.75,
) -> bool:
    for detection in record.get("detections", []):
        if (
            detection.get("class_name") != "person"
            or float(detection["confidence"]) < minimum_person_confidence
        ):
            continue
        x1 = float(detection["x1"])
        y1 = float(detection["y1"])
        x2 = float(detection["x2"])
        y2 = float(detection["y2"])
        if x1 <= point.x <= x2 and y1 <= point.y <= (
            y1 + (y2 - y1) * upper_body_fraction
        ):
            return True
    return False


def _near_player_feet(
    point: BallPoint,
    record: dict[str, Any],
    *,
    minimum_person_confidence: float = 0.25,
) -> bool:
    for detection in record.get("detections", []):
        if (
            detection.get("class_name") != "person"
            or float(detection["confidence"]) < minimum_person_confidence
        ):
            continue
        x1 = float(detection["x1"])
        y1 = float(detection["y1"])
        x2 = float(detection["x2"])
        y2 = float(detection["y2"])
        width = x2 - x1
        height = y2 - y1
        if (
            x1 - width * 0.5 <= point.x <= x2 + width * 0.5
            and y1 + height * 0.55 <= point.y <= y2 + height * 0.35
        ):
            return True
    return False


def _player_context_allows_ball(
    point: BallPoint,
    record: dict[str, Any],
) -> bool:
    if not _inside_player_upper_body(point, record):
        return True
    if not _near_player_feet(point, record):
        return False
    return not any(
        _inside_person_upper_body(point, detection)
        and _near_person_feet(point, detection)
        for detection in record.get("detections", [])
        if (
            detection.get("class_name") == "person"
            and float(detection["confidence"]) >= 0.25
        )
    )


def _inside_person_upper_body(
    point: BallPoint,
    detection: dict[str, Any],
) -> bool:
    x1 = float(detection["x1"])
    y1 = float(detection["y1"])
    x2 = float(detection["x2"])
    y2 = float(detection["y2"])
    return (
        x1 <= point.x <= x2
        and y1 <= point.y <= y1 + (y2 - y1) * 0.75
    )


def _near_person_feet(
    point: BallPoint,
    detection: dict[str, Any],
) -> bool:
    x1 = float(detection["x1"])
    y1 = float(detection["y1"])
    x2 = float(detection["x2"])
    y2 = float(detection["y2"])
    width = x2 - x1
    height = y2 - y1
    return (
        x1 - width * 0.5 <= point.x <= x2 + width * 0.5
        and y1 + height * 0.55 <= point.y <= y2 + height * 0.35
    )


def _inside_soccertrack_pitch(
    point: BallPoint, width: int, height: int
) -> bool:
    normalized_x = abs(point.x - width / 2) / (width / 2)
    top = (150 + 150 * normalized_x**2) / 1080 * height
    bottom = (640 + 65 * (1 - normalized_x**2)) / 1080 * height
    return top <= point.y <= bottom


def _static_cells(
    points: Iterable[BallPoint],
    *,
    frame_count: int,
    cell_size: int,
    occupancy: float,
) -> frozenset[tuple[int, int]]:
    cells_by_frame: dict[tuple[int, int], set[int]] = {}
    for point in points:
        cells_by_frame.setdefault(_cell(point, cell_size), set()).add(
            point.source_frame
        )
    threshold = frame_count * occupancy
    return frozenset(
        cell
        for cell, frames in cells_by_frame.items()
        if len(frames) >= threshold
    )


def _cell(point: BallPoint, cell_size: int) -> tuple[int, int]:
    return round(point.x / cell_size), round(point.y / cell_size)


def _player_anchored_cells(
    candidates: Iterable[_BallCandidate],
    *,
    cell_size: int,
    minimum_distinct_frames: int = 2,
) -> frozenset[tuple[int, int]]:
    frames_by_cell: dict[tuple[int, int], set[int]] = defaultdict(set)
    for candidate in candidates:
        if candidate.near_player_feet:
            frames_by_cell[_cell(candidate.point, cell_size)].add(
                candidate.point.source_frame
            )
    return frozenset(
        cell
        for cell, frames in frames_by_cell.items()
        if len(frames) >= minimum_distinct_frames
    )


def _near_static_cell(
    point: BallPoint,
    static_cells: frozenset[tuple[int, int]],
    cell_size: int,
) -> bool:
    return any(
        hypot(point.x - cell_x * cell_size, point.y - cell_y * cell_size)
        <= cell_size
        for cell_x, cell_y in static_cells
    )


def _unanchored_static_clusters(
    candidates: Iterable[_BallCandidate],
    *,
    cell_size: int,
    maximum_continuous_gap_seconds: float = 0.56,
    minimum_distinct_frames: int = 3,
    maximum_cluster_radius_fraction: float = 0.25,
) -> tuple[_UnanchoredStaticCluster, ...]:
    if maximum_continuous_gap_seconds <= 0:
        raise ValueError("Maximum continuous gap must be greater than zero")
    candidates = tuple(candidates)
    anchored_cells = _player_anchored_cells(
        candidates,
        cell_size=cell_size,
    )
    by_cell: dict[tuple[int, int], list[BallPoint]] = {}
    for candidate in candidates:
        if (
            candidate.near_player_feet
            or _cell(candidate.point, cell_size) in anchored_cells
        ):
            continue
        by_cell.setdefault(_cell(candidate.point, cell_size), []).append(
            candidate.point
        )

    clusters: list[_UnanchoredStaticCluster] = []
    for points in by_cell.values():
        if len({point.source_frame for point in points}) < minimum_distinct_frames:
            continue
        ordered = sorted(points, key=lambda point: point.clip_seconds)
        if all(
            second.clip_seconds - first.clip_seconds
            <= maximum_continuous_gap_seconds
            for first, second in zip(ordered, ordered[1:])
        ):
            continue
        center_x = sum(point.x for point in points) / len(points)
        center_y = sum(point.y for point in points) / len(points)
        maximum_distance = max(
            hypot(point.x - center_x, point.y - center_y)
            for point in points
        )
        if maximum_distance <= cell_size * maximum_cluster_radius_fraction:
            clusters.append(
                _UnanchoredStaticCluster(x=center_x, y=center_y)
            )
    return tuple(clusters)


def _near_unanchored_static_cluster(
    point: BallPoint,
    clusters: Iterable[_UnanchoredStaticCluster],
    *,
    cell_size: int,
    maximum_cluster_radius_fraction: float = 0.25,
) -> bool:
    maximum_distance = cell_size * maximum_cluster_radius_fraction
    return any(
        hypot(point.x - cluster.x, point.y - cluster.y) <= maximum_distance
        for cluster in clusters
    )


def _discard_unanchored_static_fragments(
    tracks: Iterable[BallTrack],
    candidates: Iterable[_BallCandidate],
    *,
    maximum_travel_box_diameters: float = 0.5,
) -> tuple[tuple[BallTrack, ...], int]:
    foot_support = {
        candidate.point: candidate.near_player_feet
        for candidate in candidates
    }
    retained: list[BallTrack] = []
    discarded = 0
    for track in tracks:
        if _is_unanchored_static_fragment(
            track,
            foot_support=foot_support,
            maximum_travel_box_diameters=maximum_travel_box_diameters,
        ):
            discarded += 1
            continue
        retained.append(track)
    return tuple(retained), discarded


def _is_unanchored_static_fragment(
    track: BallTrack,
    *,
    foot_support: dict[BallPoint, bool],
    maximum_travel_box_diameters: float,
) -> bool:
    if len(track.points) < 3:
        return False
    if any(foot_support.get(point, False) for point in track.points):
        return False
    box_diameters = [
        point.box_diagonal
        for point in track.points
        if point.box_diagonal > 0
    ]
    if not box_diameters:
        return False
    travel = sum(
        hypot(second.x - first.x, second.y - first.y)
        for first, second in zip(track.points, track.points[1:])
    )
    return travel <= median(box_diameters) * maximum_travel_box_diameters


def _discard_temporal_upper_body_points(
    tracks: Iterable[BallTrack],
    *,
    records_by_frame: dict[int, dict[str, Any]],
) -> tuple[tuple[BallTrack, ...], int]:
    filtered_tracks: list[BallTrack] = []
    discarded = 0
    for track in tracks:
        points: list[BallPoint] = []
        for point in track.points:
            if point.evidence == "detector":
                points.append(point)
                continue
            record = records_by_frame.get(point.source_frame)
            if record is None:
                raise ValueError(
                    "Missing cached detector record for temporal ball point "
                    f"at source frame {point.source_frame}"
                )
            if _inside_player_upper_body(point, record):
                discarded += 1
                continue
            points.append(point)
        if points:
            filtered_tracks.append(BallTrack(track.track_id, points))
    return tuple(filtered_tracks), discarded


def _video_dimensions(video: Path) -> tuple[int, int]:
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        capture.release()
    if width <= 0 or height <= 0:
        raise ValueError("Benchmark video dimensions are invalid")
    return width, height


def _write_summary(
    *,
    output: Path,
    records: list[dict[str, Any]],
    raw_candidates: list[BallPoint],
    pitch_candidate_count: int,
    filtered_candidates: list[BallPoint],
    candidate_conflict_frames: int,
    conflicting_candidates: int,
    upper_body_rejections: int,
    global_static_rejections: int,
    unanchored_static_rejections: int,
    tracks: tuple[BallTrack, ...],
    unanchored_static_clusters: tuple[_UnanchoredStaticCluster, ...],
    associated_track_fragments: int,
    supported_track_fragments: int,
    discarded_static_fragments: int,
    discarded_temporal_upper_body_points: int,
    raw_motion_diagnostics: _RawMotionDiagnostics = _RawMotionDiagnostics(),
    kalman_reacquisition_diagnostics: _KalmanReacquisitionDiagnostics = (
        _KalmanReacquisitionDiagnostics()
    ),
    dense_flow_diagnostics: _DenseFlowDiagnostics = _DenseFlowDiagnostics(),
    analysis_start_seconds: float | None,
    analysis_end_seconds: float | None,
) -> None:
    tracked_points = [point for track in tracks for point in track.points]
    detector_points = [
        point
        for point in tracked_points
        if point.evidence == "detector"
    ]
    temporal_points = [
        point
        for point in tracked_points
        if point.evidence
        in {
            "template_consensus",
            "bidirectional_template",
            "stationary_bidirectional_template",
            "partial_bidirectional_template",
            "template_validated_detector",
            "forward_template_consensus",
            "motion_circle",
            "raw_motion_near_feet",
            "raw_motion_trajectory_corridor",
            "raw_motion_global_fallback",
            "dense_bidirectional_optical_flow",
        }
        or point.evidence.startswith("kalman_guided_")
        or point.evidence.startswith("raw_motion_attention_convergence_")
    ]
    interpolated_points = [
        point for point in tracked_points if point.interpolated
    ]
    supported_points = [*detector_points, *temporal_points]
    supported_frames = {point.source_frame for point in supported_points}
    source_attributions = Counter(
        point.source_attribution for point in tracked_points
    )
    summary = {
        "analysis_window": _analysis_window(
            analysis_start_seconds,
            analysis_end_seconds,
        ),
        "processed_frames": len(records),
        "raw_pitch_ball_candidates": len(raw_candidates),
        "pitch_ball_candidates_before_upper_body_rejection": (
            pitch_candidate_count
        ),
        "filtered_ball_candidates": len(filtered_candidates),
        "candidate_conflicts": {
            "frames_with_multiple_candidates": candidate_conflict_frames,
            "competing_candidates": conflicting_candidates,
        },
        "candidate_rejections": {
            "inside_player_upper_body": upper_body_rejections,
            "global_static_cells": global_static_rejections,
            "unanchored_static_clusters": unanchored_static_rejections,
            "unanchored_static_fragments": discarded_static_fragments,
            "temporal_points_inside_player_upper_body": (
                discarded_temporal_upper_body_points
            ),
            "raw_motion_scale_or_shape": (
                raw_motion_diagnostics.rejected_scale_or_shape
            ),
            "raw_motion_appearance": (
                raw_motion_diagnostics.rejected_appearance
            ),
            "raw_motion_player_body": (
                raw_motion_diagnostics.rejected_player_body
            ),
            "raw_motion_ambiguity": (
                raw_motion_diagnostics.rejected_ambiguity
            ),
            "raw_motion_temporal_consistency": (
                raw_motion_diagnostics.rejected_temporal_consistency
            ),
        },
        "raw_motion_proposals": {
            "parameter_profile": SOCCERTRACK_RAW_MOTION_PROFILE,
            "verification_profile": (
                SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE
            ),
            "generated": raw_motion_diagnostics.generated,
            "accepted": {
                "near_feet": raw_motion_diagnostics.near_feet,
                "trajectory_corridor": (
                    raw_motion_diagnostics.trajectory_corridor
                ),
                "global_fallback": raw_motion_diagnostics.global_fallback,
            },
            "generated_by_mode": {
                "near_feet": raw_motion_diagnostics.near_feet_generated,
                "trajectory_corridor": (
                    raw_motion_diagnostics.trajectory_corridor_generated
                ),
                "global_fallback": (
                    raw_motion_diagnostics.global_fallback_generated
                ),
            },
            "precision_rejections": {
                "verification_score": (
                    raw_motion_diagnostics.rejected_verification
                ),
                "path_plausibility": (
                    raw_motion_diagnostics.rejected_path_plausibility
                ),
                "alternative_margin": (
                    raw_motion_diagnostics.rejected_alternative_margin
                ),
                "ambiguity": raw_motion_diagnostics.rejected_ambiguity,
                "temporal_consistency": (
                    raw_motion_diagnostics.rejected_temporal_consistency
                ),
            },
            "trajectory_margin": {
                "minimum": (
                    raw_motion_diagnostics
                    .minimum_accepted_trajectory_margin
                ),
                "mean": (
                    raw_motion_diagnostics
                    .mean_accepted_trajectory_margin
                ),
            },
        },
        "player_attention_search_prior": {
            "parameter_profile": SOCCERTRACK_PLAYER_ATTENTION_PROFILE,
            "accepted_coordinates": raw_motion_diagnostics.attention_accepted,
            "startup_points_rejected": (
                raw_motion_diagnostics.startup_points_rejected
            ),
            "rejections": {
                "insufficient_convergence": (
                    raw_motion_diagnostics.attention_rejected_convergence
                ),
                "insufficient_visual_evidence": (
                    raw_motion_diagnostics
                    .attention_rejected_visual_evidence
                ),
                "temporal_path": (
                    raw_motion_diagnostics.attention_rejected_temporal_path
                ),
            },
            "precise_eye_gaze_claimed": False,
            "attention_only_coordinates_published": 0,
        },
        "kalman_guided_reacquisition": {
            "parameter_profile": SOCCERTRACK_KALMAN_REACQUISITION_PROFILE,
            "accepted": kalman_reacquisition_diagnostics.successes,
            "visual_source": {
                "yolo_candidate": (
                    kalman_reacquisition_diagnostics.yolo_candidates
                ),
                "raw_motion_micro_crop": (
                    kalman_reacquisition_diagnostics.raw_motion_candidates
                ),
            },
            "search_context": {
                "near_feet": kalman_reacquisition_diagnostics.near_feet,
                "trajectory_corridor": (
                    kalman_reacquisition_diagnostics.trajectory_corridor
                ),
                "global_fallback": (
                    kalman_reacquisition_diagnostics.global_fallback
                ),
            },
            "expired_predictions": (
                kalman_reacquisition_diagnostics.expired_predictions
            ),
            "bidirectional_rejections": (
                kalman_reacquisition_diagnostics.bidirectional_rejections
            ),
            "visual_evidence_misses": (
                kalman_reacquisition_diagnostics.visual_evidence_misses
            ),
            "conflicts": kalman_reacquisition_diagnostics.conflicts,
            "prediction_only_points_published": 0,
        },
        "dense_optical_flow": {
            "parameter_profile": SOCCERTRACK_DENSE_FLOW_PROFILE,
            "accepted_points": dense_flow_diagnostics.accepted_points,
            "successful_bridges": dense_flow_diagnostics.successful_bridges,
            "rejected_drift": dense_flow_diagnostics.rejected_drift,
            "expired_bridges": dense_flow_diagnostics.expired_bridges,
            "endpoint_disagreement": (
                dense_flow_diagnostics.endpoint_disagreement
            ),
            "insufficient_feature_support": (
                dense_flow_diagnostics.insufficient_feature_support
            ),
            "appearance_rejections": (
                dense_flow_diagnostics.appearance_rejections
            ),
            "player_upper_body_rejections": (
                dense_flow_diagnostics.player_upper_body_rejections
            ),
            "path_confidence": {
                "minimum": dense_flow_diagnostics.minimum_path_confidence,
                "mean": dense_flow_diagnostics.mean_path_confidence,
            },
            "unbounded_flow_points_published": 0,
        },
        "long_stationary_template": {
            "parameter_profile": LONG_STATIONARY_TEMPLATE_PROFILE,
            "accepted_points": sum(
                point.evidence == "stationary_bidirectional_template"
                for point in tracked_points
            ),
            "prediction_only_points_published": 0,
        },
        "unanchored_static_clusters": len(
            unanchored_static_clusters
        ),
        "associated_track_fragments": associated_track_fragments,
        "discarded_unanchored_static_fragments": (
            discarded_static_fragments
        ),
        "discarded_temporal_upper_body_points": (
            discarded_temporal_upper_body_points
        ),
        "supported_track_fragments": supported_track_fragments,
        "accepted_tracks": len(tracks),
        "accepted_track_points": len(tracked_points),
        "observed_track_points": len(detector_points),
        "temporally_supported_track_points": len(temporal_points),
        "interpolated_track_points": len(interpolated_points),
        "point_source_attribution": {
            "yolo26_observed": source_attributions["yolo26_observed"],
            "temporal_detector_observed": source_attributions[
                "temporal_detector_observed"
            ],
            "optical_flow_propagated": source_attributions[
                "optical_flow_propagated"
            ],
            "raw_motion_micro_crop_supported": source_attributions[
                "raw_motion_micro_crop_supported"
            ],
            "kalman_guided_visual_reacquired": source_attributions[
                "kalman_guided_visual_reacquired"
            ],
            "interpolated": source_attributions["interpolated"],
        },
        "tracked_frames": len(supported_frames),
        "tracked_frame_coverage": round(
            len(supported_frames) / len(records),
            4,
        ),
        "coordinate_correctness": {
            "trusted_reference_available": False,
            "measured": False,
            "reason": (
                "No per-frame coordinate reference is loaded. Template-based "
                    "raw-motion micro-crop, and bounded optical-flow evidence are "
                    "not correctness labels."
            ),
        },
        "coordinate_uncertainty": {
            "detector_backed_points": len(detector_points),
            "template_supported_points": source_attributions[
                "temporal_detector_observed"
            ],
            "raw_motion_micro_crop_points": source_attributions[
                "raw_motion_micro_crop_supported"
            ],
            "kalman_guided_visually_reacquired_points": source_attributions[
                "kalman_guided_visual_reacquired"
            ],
            "dense_optical_flow_points": source_attributions[
                "optical_flow_propagated"
            ],
            "raw_motion_modes": {
                "near_feet": raw_motion_diagnostics.near_feet,
                "trajectory_corridor": (
                    raw_motion_diagnostics.trajectory_corridor
                ),
                "global_fallback": raw_motion_diagnostics.global_fallback,
            },
            "manual_coordinate_validation_performed": False,
        },
        "interpretation": (
            "Coverage counts detector, template-consensus, raw-motion "
            "micro-crop, and endpoint-bounded optical-flow coordinates with "
            "raw visual evidence; interpolation is excluded."
        ),
    }
    (output / "ball-tracking-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


def _validate_options(
    *,
    static_cell_size: int,
    static_occupancy: float,
    max_gap_seconds: float,
    max_speed_pixels_per_second: float,
    minimum_track_points: int,
) -> None:
    if static_cell_size < 1:
        raise ValueError("Static cell size must be at least 1")
    if not 0 < static_occupancy <= 1:
        raise ValueError("Static occupancy must be greater than 0 and at most 1")
    if max_gap_seconds <= 0 or max_speed_pixels_per_second <= 0:
        raise ValueError("Track gap and speed limits must be greater than zero")
    if minimum_track_points < 2:
        raise ValueError("Minimum track points must be at least 2")
