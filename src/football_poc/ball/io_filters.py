from __future__ import annotations

from .settings import *  # noqa: F401,F403

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


# In the camera's perspective a ball on the far side of a player overlaps the
# player's upper body. Heads and shirts produce only weak ball boxes, so a
# strong detector box there is kept as a ball passing behind the player.
BEHIND_PLAYER_MINIMUM_CONFIDENCE = 0.5


def _strong_ball_behind_player(point: BallPoint) -> bool:
    return (
        point.source_attribution == "yolo26_observed"
        and point.confidence >= BEHIND_PLAYER_MINIMUM_CONFIDENCE
    )


def _balls_continuing_behind_player(
    pitch_candidates: Iterable[tuple[BallPoint, dict[str, Any]]],
    *,
    fps: float,
    frame_step: int,
) -> set[BallPoint]:
    """Weak boxes over a player that continue a strong behind-player ball.

    A box one sampled frame from a strong ball box behind a player, and within
    ball-chain reach of it, is the same ball still passing that player.
    """
    if fps <= 0 or frame_step < 1:
        return set()
    hidden = [
        point
        for point, record in pitch_candidates
        if not _player_context_allows_ball(point, record)
    ]
    strong_by_frame: dict[int, list[BallPoint]] = defaultdict(list)
    for point, record in pitch_candidates:
        if _inside_player_upper_body(point, record) and _strong_ball_behind_player(
            point
        ):
            strong_by_frame[point.source_frame].append(point)
    reach = LOCK_CHAIN_MAX_SPEED_PIXELS_PER_SECOND * frame_step / fps
    return {
        point
        for point in hidden
        if any(
            hypot(strong.x - point.x, strong.y - point.y) <= reach
            for frame in (
                point.source_frame - frame_step,
                point.source_frame + frame_step,
            )
            for strong in strong_by_frame.get(frame, [])
        )
    }


def _player_context_allows_ball(
    point: BallPoint,
    record: dict[str, Any],
) -> bool:
    if not _inside_player_upper_body(point, record):
        return True
    if not _near_player_feet(point, record):
        return _strong_ball_behind_player(point)
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
            if _has_protected_direct_evidence(point):
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


def _has_protected_direct_evidence(point: BallPoint) -> bool:
    return point.evidence in {
        "detector",
        "template_validated_detector",
        "focused_multiscale_detector",
        "trajectory_validated_detector",
        "full_rate_motion_streak",
        "full_rate_trajectory_corridor",
    }


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
    ledger: FrameLedger | None = None,
    analysis_start_seconds: float | None = None,
    analysis_end_seconds: float | None = None,
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
            "full_rate_motion_streak",
            "full_rate_trajectory_corridor",
            "motion_circle",
            "raw_motion_near_feet",
            "raw_motion_trajectory_corridor",
            "raw_motion_global_fallback",
            "focused_multiscale_detector",
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
        "full_rate_motion_streak": {
            "parameter_profile": FULL_RATE_MOTION_STREAK_PROFILE,
            "accepted_points": sum(
                point.evidence == "full_rate_motion_streak"
                for point in tracked_points
            ),
            "coordinate_policy": (
                "Raw-motion component coordinates shared by all near-best "
                "temporally consistent paths; prediction-only samples are "
                "never published."
            ),
            "prediction_only_points_published": 0,
        },
        "full_rate_trajectory_corridor": {
            "parameter_profile": FULL_RATE_TRAJECTORY_CORRIDOR_PROFILE,
            "accepted_points": sum(
                point.evidence == "full_rate_trajectory_corridor"
                for point in tracked_points
            ),
            "coordinate_policy": (
                "Velocity and acceleration define only a bounded search prior; "
                "publication requires an observed full-rate motion component, "
                "appearance continuity, and near-best-path consensus."
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
        "confirmation_cascade": (
            {
                "lock_invariant": (
                    "A confirmed sampled frame cannot be changed or removed; "
                    "later modules can only append confirmations for "
                    "previously unresolved frames."
                ),
                "module_order": [
                    "01_confirm_yolo",
                    "03_motion_and_optical_flow",
                    "04_focused_multiscale",
                    "05_short_stationary",
                    "06_time_machine_region_search",
                    "02_time_machine",
                ],
                **ledger.module_summary(),
            }
            if ledger is not None
            else None
        ),
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
