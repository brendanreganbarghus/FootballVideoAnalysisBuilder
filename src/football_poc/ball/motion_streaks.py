from __future__ import annotations

from .settings import *  # noqa: F401,F403

def _full_rate_motion_streak_candidates(
    *,
    previous: np.ndarray,
    current: np.ndarray,
    following: np.ndarray,
    source_frame: int,
    reference_diameter: float,
) -> tuple[_MotionStreakCandidate, ...]:
    profile = FULL_RATE_MOTION_STREAK_PROFILE
    motion = cv2.min(
        cv2.absdiff(current, previous),
        cv2.absdiff(current, following),
    )
    _, mask = cv2.threshold(
        motion,
        int(profile["difference_threshold"]),
        255,
        cv2.THRESH_BINARY,
    )
    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    maximum_extent = max(
        8.0,
        reference_diameter * float(profile["maximum_extent_ball_diameters"]),
    )
    candidates: list[_MotionStreakCandidate] = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = float(cv2.contourArea(contour))
        diagonal = hypot(width, height)
        if (
            area < 1
            or area > reference_diameter**2 * 1.8
            or min(width, height) < 2
            or diagonal > maximum_extent
            or max(width, height) / max(1, min(width, height))
            > float(profile["maximum_aspect_ratio"])
        ):
            continue
        moments = cv2.moments(contour)
        if moments["m00"] <= 0:
            continue
        foreground_mask = np.zeros_like(motion)
        cv2.drawContours(foreground_mask, [contour], -1, 255, -1)
        strength = float(cv2.mean(motion, mask=foreground_mask)[0])
        scale_score = float(
            np.exp(-abs(np.log(max(1.0, diagonal) / reference_diameter)))
        )
        area_score = float(
            np.exp(
                -abs(
                    np.log(
                        max(1.0, area)
                        / max(1.0, reference_diameter**2 * 0.125)
                    )
                )
            )
        )
        visual_score = (
            0.45 * min(1.0, strength / 50)
            + 0.30 * scale_score
            + 0.25 * area_score
        )
        candidates.append(
            _MotionStreakCandidate(
                source_frame=source_frame,
                x=float(moments["m10"] / moments["m00"]),
                y=float(moments["m01"] / moments["m00"]),
                width=width,
                height=height,
                area=area,
                visual_score=visual_score,
            )
        )
    return tuple(candidates)


def _full_rate_motion_streak_consensus(
    candidates_by_frame: dict[int, tuple[_MotionStreakCandidate, ...]],
    *,
    seed: BallPoint,
    history: Iterable[BallPoint] = (),
    fps: float,
    frame_step: int,
    reference_diameter: float,
    max_speed_pixels_per_second: float,
) -> tuple[BallPoint, ...]:
    profile = FULL_RATE_MOTION_STREAK_PROFILE
    launch_end = seed.source_frame + round(
        float(profile["maximum_launch_wait_seconds"]) * fps
    )
    minimum_separation = reference_diameter * float(
        profile["minimum_launch_separation_ball_diameters"]
    )
    history = tuple(history)
    paths: list[_MotionStreakPath] = []
    for source_frame in sorted(candidates_by_frame):
        if source_frame > launch_end:
            break
        elapsed = (source_frame - seed.source_frame) / fps
        predicted_x, predicted_y, search_radius = (
            _motion_streak_forward_search_prior(
                history or (seed,),
                target_frame=source_frame,
                fps=fps,
                reference_diameter=reference_diameter,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            )
        )
        for candidate in candidates_by_frame[source_frame]:
            launch_distance = hypot(candidate.x - seed.x, candidate.y - seed.y)
            prior_distance = hypot(
                candidate.x - predicted_x,
                candidate.y - predicted_y,
            )
            if (
                launch_distance >= minimum_separation
                and prior_distance <= search_radius
                and launch_distance
                <= max_speed_pixels_per_second * elapsed
            ):
                paths.append(
                    _MotionStreakPath(
                        (candidate,),
                        candidate.visual_score
                        - 0.03 * (source_frame - seed.source_frame - 1)
                        - prior_distance / max(1.0, search_radius),
                    )
                )
    if not paths:
        return ()

    maximum_gap_frames = max(
        1,
        round(float(profile["maximum_evidence_gap_seconds"]) * fps),
    )
    maximum_acceleration = float(
        profile["maximum_acceleration_pixels_per_second_squared"]
    ) / fps**2
    completed: list[_MotionStreakPath] = []
    for source_frame in sorted(candidates_by_frame):
        next_paths: list[_MotionStreakPath] = []
        for path in paths:
            last = path.points[-1]
            if last.source_frame >= source_frame:
                next_paths.append(path)
                continue
            gap = source_frame - last.source_frame
            if gap > maximum_gap_frames:
                completed.append(path)
                continue
            next_paths.append(path)
            for candidate in candidates_by_frame[source_frame]:
                distance = hypot(candidate.x - last.x, candidate.y - last.y)
                if distance > max_speed_pixels_per_second * gap / fps:
                    continue
                velocity_x = (candidate.x - last.x) / gap
                velocity_y = (candidate.y - last.y) / gap
                continuity = distance / max(
                    1.0,
                    max_speed_pixels_per_second * gap / fps,
                )
                if path.velocity_x is not None and path.velocity_y is not None:
                    acceleration = hypot(
                        velocity_x - path.velocity_x,
                        velocity_y - path.velocity_y,
                    ) / gap
                    if acceleration > maximum_acceleration:
                        continue
                    if (
                        hypot(velocity_x, velocity_y) > 4
                        and hypot(path.velocity_x, path.velocity_y) > 4
                        and velocity_x * path.velocity_x
                        + velocity_y * path.velocity_y
                        < 0
                    ):
                        continue
                next_paths.append(
                    _MotionStreakPath(
                        (*path.points, candidate),
                        path.score
                        + candidate.visual_score
                        - 0.8 * continuity
                        - 0.25 * (gap - 1),
                        velocity_x,
                        velocity_y,
                    )
                )
        deduplicated: dict[tuple[int, int, int, int, int], _MotionStreakPath] = {}
        for path in sorted(
            next_paths,
            key=lambda item: item.score,
            reverse=True,
        ):
            last = path.points[-1]
            key = (
                last.source_frame,
                round(last.x / 8),
                round(last.y / 8),
                round((path.velocity_x or 0) / 8),
                round((path.velocity_y or 0) / 8),
            )
            deduplicated.setdefault(key, path)
            if len(deduplicated) >= int(profile["maximum_paths"]):
                break
        paths = list(deduplicated.values())
    completed.extend(paths)

    minimum_points = max(
        3,
        round(float(profile["minimum_confirmed_flight_seconds"]) * fps),
    )
    eligible = [
        path
        for path in completed
        if len(path.points) >= minimum_points
        and path.points[-1].source_frame - path.points[0].source_frame
        >= minimum_points - 1
        and hypot(
            path.points[-1].x - path.points[0].x,
            path.points[-1].y - path.points[0].y,
        )
        / (
            (path.points[-1].source_frame - path.points[0].source_frame)
            / fps
        )
        >= reference_diameter
        * float(profile["minimum_progress_ball_diameters_per_second"])
    ]
    if not eligible:
        return ()
    latest_frame = max(path.points[-1].source_frame for path in eligible)
    latest = [
        path for path in eligible if path.points[-1].source_frame == latest_frame
    ]
    best_mean_score = max(path.score / len(path.points) for path in latest)
    near_best = sorted(
        (
            path
            for path in latest
            if path.score / len(path.points)
            >= best_mean_score
            - float(profile["near_best_mean_score_margin"])
        ),
        key=lambda path: path.score / len(path.points),
        reverse=True,
    )[:100]
    if not near_best:
        return ()

    additions: list[BallPoint] = []
    consensus_radius = reference_diameter * float(
        profile["consensus_radius_ball_diameters"]
    )
    minimum_visual_score = float(profile["minimum_visual_score"])
    for source_frame in sorted(candidates_by_frame):
        if source_frame % frame_step:
            continue
        candidates = [
            next(
                (
                    point
                    for point in path.points
                    if point.source_frame == source_frame
                ),
                None,
            )
            for path in near_best
        ]
        if any(candidate is None for candidate in candidates):
            continue
        agreed = [candidate for candidate in candidates if candidate is not None]
        first = agreed[0]
        if (
            first.visual_score < minimum_visual_score
            or any(
                hypot(candidate.x - first.x, candidate.y - first.y)
                > consensus_radius
                for candidate in agreed[1:]
            )
        ):
            continue
        additions.append(
            BallPoint(
                source_frame=source_frame,
                clip_seconds=source_frame / fps,
                confidence=round(first.visual_score, 6),
                x=first.x,
                y=first.y,
                box_diagonal=hypot(first.width, first.height),
                evidence="full_rate_motion_streak",
                temporal_score=round(best_mean_score, 6),
                source_attribution="raw_motion_micro_crop_supported",
            )
        )
    return tuple(additions)


def _motion_streak_forward_search_prior(
    history: Iterable[BallPoint],
    *,
    target_frame: int,
    fps: float,
    reference_diameter: float,
    max_speed_pixels_per_second: float,
) -> tuple[float, float, float]:
    profile = FULL_RATE_MOTION_STREAK_PROFILE
    ordered = sorted(history, key=lambda point: point.source_frame)
    seed = ordered[-1]
    history_frames = round(
        float(profile["motion_prior_history_seconds"]) * fps
    )
    recent = [
        point
        for point in ordered
        if seed.source_frame - point.source_frame <= history_frames
    ]
    velocities = [
        (
            (current.x - previous.x)
            * fps
            / (current.source_frame - previous.source_frame),
            (current.y - previous.y)
            * fps
            / (current.source_frame - previous.source_frame),
        )
        for previous, current in zip(recent, recent[1:])
        if current.source_frame > previous.source_frame
    ]
    velocity_x = median(value[0] for value in velocities) if velocities else 0.0
    velocity_y = median(value[1] for value in velocities) if velocities else 0.0
    speed = hypot(velocity_x, velocity_y)
    if speed > max_speed_pixels_per_second:
        scale = max_speed_pixels_per_second / speed
        velocity_x *= scale
        velocity_y *= scale

    elapsed = max(0.0, (target_frame - seed.source_frame) / fps)
    predicted_x = seed.x + velocity_x * elapsed
    predicted_y = seed.y + velocity_y * elapsed
    acceleration = (
        reference_diameter
        * float(
            profile[
                "maximum_launch_acceleration_ball_diameters_per_second_squared"
            ]
        )
    )
    search_radius = max(
        reference_diameter
        * float(profile["minimum_search_radius_ball_diameters"]),
        0.5 * acceleration * elapsed**2,
    )
    search_radius = min(
        search_radius,
        max_speed_pixels_per_second * elapsed
        + reference_diameter
        * float(profile["minimum_search_radius_ball_diameters"]),
    )
    return predicted_x, predicted_y, search_radius


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
