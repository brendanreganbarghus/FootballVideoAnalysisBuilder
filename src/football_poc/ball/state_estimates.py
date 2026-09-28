from __future__ import annotations

from .settings import *  # noqa: F401,F403

def _sampled_ball_state_estimates(
    tracks: Iterable[BallTrack],
    *,
    records: Iterable[dict[str, Any]],
    fps: float,
    frame_step: int,
    width: int,
    height: int,
    max_speed_pixels_per_second: float,
    ledger: FrameLedger | None = None,
) -> list[dict[str, Any]]:
    if fps <= 0 or frame_step < 1 or width < 1 or height < 1:
        raise ValueError("Ball-state estimate dimensions and timing must be positive")
    observed = sorted(
        (point for track in tracks for point in track.points),
        key=lambda point: point.source_frame,
    )
    observed_by_frame = {point.source_frame: point for point in observed}
    sampled_frames = sorted({int(record["source_frame"]) for record in records})
    states: list[dict[str, Any]] = []
    for source_frame in sampled_frames:
        point = observed_by_frame.get(source_frame)
        if point is not None:
            is_direct = (
                True
                if ledger is None
                else point.confirming_module == "01_confirm_yolo"
                if point.confirming_module is not None
                else point.source_attribution == "yolo26_observed"
            )
            states.append(
                {
                    **asdict(point),
                    "state": (
                        "observed"
                        if point.source_attribution == "yolo26_observed"
                        else "visually_reacquired"
                    ),
                    "uncertainty_radius_pixels": round(
                        max(1.0, point.box_diagonal / 2),
                        3,
                    ),
                    "event_evidence_eligible": is_direct,
                }
            )
            continue
        if ledger is not None and ledger.confirmed(source_frame) is None:
            reasons = ledger.entries[source_frame].rejection_reasons
            states.append(
                {
                    "source_frame": source_frame,
                    "clip_seconds": round(source_frame / fps, 3),
                    "confidence": None,
                    "x": None,
                    "y": None,
                    "interpolated": False,
                    "box_diagonal": None,
                    "evidence": "unresolved",
                    "temporal_score": None,
                    "source_attribution": "unresolved",
                    "state": "unresolved",
                    "uncertainty_radius_pixels": None,
                    "event_evidence_eligible": False,
                    "confirming_module": None,
                    "rejection_reasons": list(reasons),
                }
            )
            continue

        previous = next(
            (
                candidate
                for candidate in reversed(observed)
                if candidate.source_frame < source_frame
            ),
            None,
        )
        following = next(
            (
                candidate
                for candidate in observed
                if candidate.source_frame > source_frame
            ),
            None,
        )
        if previous is not None and following is not None:
            alpha = (
                (source_frame - previous.source_frame)
                / (following.source_frame - previous.source_frame)
            )
            x = previous.x + (following.x - previous.x) * alpha
            y = previous.y + (following.y - previous.y) * alpha
            state = "trajectory_estimated_bidirectional"
            curved_y = _bounded_vertical_curve_estimate(
                observed,
                previous=previous,
                following=following,
                source_frame=source_frame,
            )
            if curved_y is not None:
                y = curved_y
                state = "trajectory_estimated_bidirectional_curved"
            anchor_confidence = min(previous.confidence, following.confidence)
            nearest_gap = min(
                source_frame - previous.source_frame,
                following.source_frame - source_frame,
            )
            reference_diameter = median(
                diameter
                for diameter in (
                    previous.box_diagonal,
                    following.box_diagonal,
                )
                if diameter > 0
            )
        else:
            anchor = previous or following
            if anchor is None:
                continue
            same_side = (
                [
                    candidate
                    for candidate in observed
                    if candidate.source_frame < source_frame
                ][-4:]
                if previous is not None
                else [
                    candidate
                    for candidate in observed
                    if candidate.source_frame > source_frame
                ][:4]
            )
            velocity_x, velocity_y = _recent_ball_velocity_per_frame(
                same_side,
                fps=fps,
            )
            if previous is None:
                velocity_x *= -1
                velocity_y *= -1
            delta = source_frame - anchor.source_frame
            maximum_displacement = (
                max_speed_pixels_per_second * abs(delta) / fps
            )
            displacement_x = velocity_x * delta
            displacement_y = velocity_y * delta
            displacement = hypot(displacement_x, displacement_y)
            if displacement > maximum_displacement > 0:
                scale = maximum_displacement / displacement
                displacement_x *= scale
                displacement_y *= scale
            x = anchor.x + displacement_x
            y = anchor.y + displacement_y
            state = (
                "trajectory_estimated_forward"
                if previous is not None
                else "trajectory_estimated_backward"
            )
            anchor_confidence = anchor.confidence
            nearest_gap = abs(delta)
            reference_diameter = max(1.0, anchor.box_diagonal)

        gap_steps = nearest_gap / frame_step
        states.append(
            {
                "source_frame": source_frame,
                "clip_seconds": round(source_frame / fps, 3),
                "confidence": round(
                    min(0.49, anchor_confidence * (0.8**gap_steps)),
                    6,
                ),
                "x": min(float(width - 1), max(0.0, x)),
                "y": min(float(height - 1), max(0.0, y)),
                "interpolated": False,
                "box_diagonal": reference_diameter,
                "evidence": state,
                "temporal_score": None,
                "source_attribution": "trajectory_estimated",
                "state": state,
                "uncertainty_radius_pixels": round(
                    reference_diameter * (1 + gap_steps),
                    3,
                ),
                "event_evidence_eligible": False,
            }
        )
    return states


def _discard_final_trajectory_conflicts(
    tracks: Iterable[BallTrack],
    *,
    fps: float,
    max_speed_pixels_per_second: float,
    max_acceleration_pixels_per_second_squared: float,
) -> tuple[tuple[BallTrack, ...], frozenset[int]]:
    if (
        fps <= 0
        or max_speed_pixels_per_second <= 0
        or max_acceleration_pixels_per_second_squared <= 0
    ):
        raise ValueError("Final trajectory limits and timing must be positive")

    rejected_frames: set[int] = set()
    filtered: list[BallTrack] = []
    for track in tracks:
        retained = sorted(track.points, key=lambda point: point.source_frame)
        while len(retained) >= 2:
            conflict = _first_final_trajectory_conflict(
                retained,
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
                max_acceleration_pixels_per_second_squared=(
                    max_acceleration_pixels_per_second_squared
                ),
            )
            if conflict is None:
                break
            rejection_index = _final_trajectory_rejection_index(
                retained,
                conflict,
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            )
            rejected_frames.add(retained[rejection_index].source_frame)
            retained.pop(rejection_index)
        filtered.append(BallTrack(track.track_id, retained))
    return tuple(filtered), frozenset(rejected_frames)


def _first_final_trajectory_conflict(
    points: list[BallPoint],
    *,
    fps: float,
    max_speed_pixels_per_second: float,
    max_acceleration_pixels_per_second_squared: float,
) -> tuple[int, ...] | None:
    return_excursion = _first_recovered_return_excursion(points)
    if return_excursion is not None:
        return return_excursion

    velocities: list[tuple[np.ndarray, float]] = []
    for index, (first, second) in enumerate(zip(points, points[1:])):
        elapsed = (second.source_frame - first.source_frame) / fps
        if elapsed <= 0:
            return (index, index + 1)
        velocity = np.array([second.x - first.x, second.y - first.y]) / elapsed
        if np.linalg.norm(velocity) > max_speed_pixels_per_second:
            return (index, index + 1)
        velocities.append((velocity, elapsed))
    for index, (
        (first_velocity, first_elapsed),
        (second_velocity, second_elapsed),
    ) in enumerate(zip(velocities, velocities[1:])):
        acceleration = np.linalg.norm(second_velocity - first_velocity) / (
            (first_elapsed + second_elapsed) / 2
        )
        if acceleration > max_acceleration_pixels_per_second_squared:
            return (index, index + 1, index + 2)
    return None


def _first_recovered_return_excursion(
    points: list[BallPoint],
) -> tuple[int, int, int] | None:
    if len(points) < 5:
        return None
    for middle in range(2, len(points) - 2):
        support_before = points[middle - 2]
        previous = points[middle - 1]
        candidate = points[middle]
        following = points[middle + 1]
        support_after = points[middle + 2]
        if candidate.source_attribution == "yolo26_observed":
            continue
        if (
            following.clip_seconds - previous.clip_seconds
            > float(
                SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                    "return_excursion_maximum_span_seconds"
                ]
            )
        ):
            continue
        diameters = [
            diameter
            for diameter in (
                support_before.box_diagonal,
                previous.box_diagonal,
                candidate.box_diagonal,
                following.box_diagonal,
                support_after.box_diagonal,
            )
            if diameter > 0
        ]
        reference_diameter = median(diameters) if diameters else 1.0
        stable_radius = max(
            15.0,
            reference_diameter
            * float(
                SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                    "return_excursion_stable_radius_ball_diameters"
                ]
            ),
        )
        if any(
            hypot(first.x - second.x, first.y - second.y) > stable_radius
            for first, second in (
                (support_before, previous),
                (previous, following),
                (following, support_after),
            )
        ):
            continue
        frame_span = following.source_frame - previous.source_frame
        if frame_span <= 0:
            continue
        alpha = (
            candidate.source_frame - previous.source_frame
        ) / frame_span
        expected_x = previous.x + (following.x - previous.x) * alpha
        expected_y = previous.y + (following.y - previous.y) * alpha
        excursion = hypot(
            candidate.x - expected_x,
            candidate.y - expected_y,
        )
        minimum_excursion = max(
            float(
                SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                    "return_excursion_minimum_distance_pixels"
                ]
            ),
            reference_diameter
            * float(
                SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                    "return_excursion_minimum_distance_ball_diameters"
                ]
            ),
        )
        if excursion >= minimum_excursion:
            return middle - 1, middle, middle + 1
    return None


def _bounded_vertical_curve_estimate(
    observed: list[BallPoint],
    *,
    previous: BallPoint,
    following: BallPoint,
    source_frame: int,
) -> float | None:
    frame_span = following.source_frame - previous.source_frame
    offset = source_frame - previous.source_frame
    if frame_span <= 0 or offset <= 0 or offset >= frame_span:
        return None
    reference_diameter = median(
        diameter
        for diameter in (previous.box_diagonal, following.box_diagonal)
        if diameter > 0
    )
    vertical_displacement = following.y - previous.y
    if abs(vertical_displacement) < max(
        10.0,
        reference_diameter
        * float(
            SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                "curved_estimate_minimum_vertical_ball_diameters"
            ]
        ),
    ):
        return None

    bridge_velocity = vertical_displacement / frame_span
    boundary_velocities: list[tuple[float, str]] = []
    earlier = next(
        (
            point
            for point in reversed(observed)
            if point.source_frame < previous.source_frame
        ),
        None,
    )
    if earlier is not None:
        elapsed = previous.source_frame - earlier.source_frame
        if elapsed > 0:
            boundary_velocities.append(
                ((previous.y - earlier.y) / elapsed, "start")
            )
    later = next(
        (
            point
            for point in observed
            if point.source_frame > following.source_frame
        ),
        None,
    )
    if later is not None:
        elapsed = later.source_frame - following.source_frame
        if elapsed > 0:
            boundary_velocities.append(
                ((later.y - following.y) / elapsed, "end")
            )
    aligned = [
        (velocity, boundary)
        for velocity, boundary in boundary_velocities
        if velocity * bridge_velocity > 0
    ]
    if not aligned:
        return None
    boundary_velocity, boundary = min(
        aligned,
        key=lambda item: abs(item[0] - bridge_velocity),
    )
    maximum_velocity_difference = max(
        1.0,
        abs(bridge_velocity)
        * float(
            SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                "curved_estimate_maximum_velocity_difference_ratio"
            ]
        ),
    )
    if abs(boundary_velocity - bridge_velocity) > maximum_velocity_difference:
        return None

    if boundary == "start":
        acceleration = (
            2 * (vertical_displacement - boundary_velocity * frame_span)
            / (frame_span**2)
        )
        curved_y = (
            previous.y
            + boundary_velocity * offset
            + 0.5 * acceleration * (offset**2)
        )
    else:
        start_velocity = 2 * bridge_velocity - boundary_velocity
        acceleration = (
            boundary_velocity - start_velocity
        ) / frame_span
        curved_y = (
            previous.y
            + start_velocity * offset
            + 0.5 * acceleration * (offset**2)
        )
    linear_y = previous.y + vertical_displacement * offset / frame_span
    maximum_adjustment = max(
        2.0,
        reference_diameter
        * float(
            SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                "curved_estimate_maximum_adjustment_ball_diameters"
            ]
        ),
    )
    if abs(curved_y - linear_y) > maximum_adjustment:
        return None
    return curved_y


def _final_trajectory_rejection_index(
    points: list[BallPoint],
    conflict: tuple[int, ...],
    *,
    fps: float,
    max_speed_pixels_per_second: float,
) -> int:
    if len(conflict) == 3:
        middle = conflict[1]
        if _transition_within_speed_limit(
            points[middle - 1],
            points[middle + 1],
            fps=fps,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        ):
            return middle

    candidates = list(conflict)
    locally_valid = [
        index
        for index in candidates
        if _trajectory_is_speed_valid_without(
            points,
            index,
            fps=fps,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        )
    ]
    if len(locally_valid) == 1:
        return locally_valid[0]
    if locally_valid:
        candidates = locally_valid
    return min(
        candidates,
        key=lambda index: (
            points[index].confidence,
            points[index].temporal_score or 0.0,
        ),
    )


def _trajectory_is_speed_valid_without(
    points: list[BallPoint],
    index: int,
    *,
    fps: float,
    max_speed_pixels_per_second: float,
) -> bool:
    if index == 0 or index == len(points) - 1:
        return True
    return _transition_within_speed_limit(
        points[index - 1],
        points[index + 1],
        fps=fps,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )


def _transition_within_speed_limit(
    first: BallPoint,
    second: BallPoint,
    *,
    fps: float,
    max_speed_pixels_per_second: float,
) -> bool:
    elapsed = (second.source_frame - first.source_frame) / fps
    return (
        elapsed > 0
        and hypot(second.x - first.x, second.y - first.y) / elapsed
        <= max_speed_pixels_per_second
    )


def _deduplicate_track_frames(
    tracks: Iterable[BallTrack],
) -> tuple[BallTrack, ...]:
    evidence_priority = {
        "template_validated_detector": 9,
        "focused_multiscale_detector": 9,
        "trajectory_validated_detector": 8,
        "full_rate_motion_streak": 8,
        "full_rate_trajectory_corridor": 8,
        "detector": 6,
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
