from __future__ import annotations

from .settings import *  # noqa: F401,F403

def _track_point_signatures(
    tracks: Iterable[BallTrack],
) -> tuple[tuple[int, float, float, str], ...]:
    return tuple(
        (
            point.source_frame,
            round(point.x, 6),
            round(point.y, 6),
            point.evidence,
        )
        for track in tracks
        for point in track.points
    )


def _add_focused_multiscale_missing_points(
    tracks: Iterable[BallTrack],
    *,
    records: Iterable[dict[str, Any]],
    video: Path,
    model: Any,
    fps: float,
    frame_step: int,
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    if not tracks:
        return tracks
    points = sorted(
        (point for track in tracks for point in track.points),
        key=lambda point: point.source_frame,
    )
    points_by_frame = {point.source_frame: point for point in points}
    records_by_frame = {
        int(record["source_frame"]): record for record in records
    }
    missing_frames = [
        source_frame
        for source_frame in sorted(records_by_frame)
        if source_frame not in points_by_frame
        and any(point.source_frame < source_frame for point in points)
        and any(point.source_frame > source_frame for point in points)
    ]
    if not missing_frames:
        return tracks

    color_frames = _read_sampled_color_frames(video, missing_frames)
    candidates: dict[int, tuple[BallPoint, float, float]] = {}
    for source_frame in missing_frames:
        previous = next(
            point
            for point in reversed(points)
            if point.source_frame < source_frame
        )
        following = next(
            point for point in points if point.source_frame > source_frame
        )
        alpha = (
            source_frame - previous.source_frame
        ) / (following.source_frame - previous.source_frame)
        expected_x = previous.x + (following.x - previous.x) * alpha
        expected_y = previous.y + (following.y - previous.y) * alpha
        nearby_diameters = [
            point.box_diagonal
            for point in sorted(
                points,
                key=lambda point: abs(point.source_frame - source_frame),
            )[:6]
            if point.box_diagonal > 0
        ]
        reference_diameter = (
            median(nearby_diameters)
            if nearby_diameters
            else median(
                diameter
                for diameter in (
                    previous.box_diagonal,
                    following.box_diagonal,
                )
                if diameter > 0
            )
        )
        candidate = _focused_multiscale_ball_reacquisition(
            model=model,
            frame=color_frames.get(source_frame),
            source_frame=source_frame,
            clip_seconds=float(
                records_by_frame[source_frame].get(
                    "clip_seconds",
                    source_frame / fps,
                )
            ),
            expected_x=expected_x,
            expected_y=expected_y,
            reference_diameter=reference_diameter,
        )
        if candidate is not None:
            path_error_diameters = (
                hypot(candidate.x - expected_x, candidate.y - expected_y)
                / max(reference_diameter, 1.0)
            )
            candidates[source_frame] = (
                candidate,
                path_error_diameters,
                reference_diameter,
            )

    maximum_path_error = float(
        FOCUSED_MULTISCALE_REDETECTION_PROFILE[
            "missing_point_maximum_path_error_ball_diameters"
        ]
    )
    accepted_frames = {
        source_frame
        for source_frame, (_, path_error, _) in candidates.items()
        if path_error <= maximum_path_error
    }
    maximum_pair_separation = float(
        FOCUSED_MULTISCALE_REDETECTION_PROFILE[
            "missing_pair_maximum_separation_ball_diameters"
        ]
    )
    for source_frame in sorted(accepted_frames):
        for adjacent_frame in (
            source_frame - frame_step,
            source_frame + frame_step,
        ):
            if adjacent_frame not in candidates:
                continue
            candidate, _, reference_diameter = candidates[source_frame]
            adjacent, _, adjacent_diameter = candidates[adjacent_frame]
            if hypot(candidate.x - adjacent.x, candidate.y - adjacent.y) <= (
                maximum_pair_separation
                * median((reference_diameter, adjacent_diameter))
            ):
                accepted_frames.add(adjacent_frame)

    additions = [
        candidates[source_frame][0]
        for source_frame in sorted(accepted_frames)
    ]
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


def _add_focused_multiscale_terminal_points(
    tracks: Iterable[BallTrack],
    *,
    records: Iterable[dict[str, Any]],
    video: Path,
    model: Any,
    fps: float,
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    if not tracks:
        return tracks
    points = sorted(
        (point for track in tracks for point in track.points),
        key=lambda point: point.source_frame,
    )
    records_by_frame = {
        int(record["source_frame"]): record for record in records
    }
    if not points or not records_by_frame:
        return tracks
    anchor = points[-1]
    last_sampled_frame = max(records_by_frame)
    if anchor.source_frame >= last_sampled_frame:
        return tracks

    full_rate_frames = list(
        range(anchor.source_frame + 1, last_sampled_frame + 1)
    )
    color_frames = _read_sampled_color_frames(video, full_rate_frames)
    chain: list[BallPoint] = []
    maximum_step_diameters = float(
        FOCUSED_MULTISCALE_REDETECTION_PROFILE[
            "terminal_maximum_step_ball_diameters"
        ]
    )
    for source_frame in full_rate_frames:
        history = [*points, *chain][-4:]
        velocity_x, velocity_y = _recent_ball_velocity_per_frame(
            history,
            fps=fps,
        )
        previous = history[-1]
        delta = source_frame - previous.source_frame
        expected_x = previous.x + velocity_x * delta
        expected_y = previous.y + velocity_y * delta
        reference_diameter = median(
            point.box_diagonal
            for point in history
            if point.box_diagonal > 0
        )
        candidate = _focused_multiscale_ball_reacquisition(
            model=model,
            frame=color_frames.get(source_frame),
            source_frame=source_frame,
            clip_seconds=source_frame / fps,
            expected_x=expected_x,
            expected_y=expected_y,
            reference_diameter=reference_diameter,
        )
        if candidate is None or hypot(
            candidate.x - previous.x,
            candidate.y - previous.y,
        ) > (
            maximum_step_diameters
            * max(reference_diameter, candidate.box_diagonal)
        ):
            break
        chain.append(candidate)

    minimum_confirmations = int(
        FOCUSED_MULTISCALE_REDETECTION_PROFILE[
            "terminal_minimum_confirmation_frames"
        ]
    )
    additions = [
        point
        for index, point in enumerate(chain, start=1)
        if index >= minimum_confirmations
        and point.source_frame in records_by_frame
    ]
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


def _focused_multiscale_ball_reacquisition(
    *,
    model: Any,
    frame: np.ndarray | None,
    source_frame: int,
    clip_seconds: float,
    expected_x: float,
    expected_y: float,
    reference_diameter: float,
) -> BallPoint | None:
    profile = FOCUSED_MULTISCALE_REDETECTION_PROFILE
    if frame is None or reference_diameter <= 0:
        return None
    detections: list[_FocusedBallDetection] = []
    crops_by_inference_size: dict[
        int,
        list[tuple[np.ndarray, int, int, int]],
    ] = defaultdict(list)
    for radius_scale in profile["crop_radius_ball_diameters"]:
        radius = max(
            int(profile["minimum_crop_radius_pixels"]),
            round(reference_diameter * float(radius_scale)),
        )
        left = max(0, round(expected_x) - radius)
        right = min(frame.shape[1], round(expected_x) + radius)
        top = max(0, round(expected_y) - radius)
        bottom = min(frame.shape[0], round(expected_y) + radius)
        crop = frame[top:bottom, left:right]
        if not crop.size:
            continue
        for inference_size in profile["inference_sizes"]:
            crops_by_inference_size[int(inference_size)].append(
                (crop, left, top, radius)
            )
    for inference_size, crop_entries in crops_by_inference_size.items():
        started = time.perf_counter()
        results = model.predict(
            [entry[0] for entry in crop_entries],
            imgsz=inference_size,
            conf=float(profile["minimum_detector_confidence"]),
            verbose=False,
        )
        if _ACTIVE_GRAYSCALE_FRAME_STORE is not None:
            metrics = _ACTIVE_GRAYSCALE_FRAME_STORE.metrics
            metrics["focused_predict_calls"] = (
                int(metrics.get("focused_predict_calls", 0)) + 1
            )
            metrics["focused_predict_images"] = (
                int(metrics.get("focused_predict_images", 0))
                + len(crop_entries)
            )
            metrics["focused_predict_seconds"] = round(
                float(metrics.get("focused_predict_seconds", 0.0))
                + time.perf_counter()
                - started,
                3,
            )
        for result, (_, left, top, radius) in zip(
            results,
            crop_entries,
            strict=True,
        ):
            for box in result.boxes:
                class_id = int(box.cls[0])
                if result.names[class_id] != "sports ball":
                    continue
                x1, y1, x2, y2 = (float(value) for value in box.xyxy[0])
                detections.append(
                    _FocusedBallDetection(
                        x=left + (x1 + x2) / 2,
                        y=top + (y1 + y2) / 2,
                        confidence=float(box.conf[0]),
                        variant=(radius, inference_size),
                        width=x2 - x1,
                        height=y2 - y1,
                    )
                )
    consensus = _multiscale_detection_consensus(
        detections,
        expected_x=expected_x,
        expected_y=expected_y,
        reference_diameter=reference_diameter,
    )
    if not consensus:
        return None
    total_weight = sum(
        max(detection.confidence, 1e-6) for detection in consensus
    )
    center_x = sum(
        detection.x * max(detection.confidence, 1e-6)
        for detection in consensus
    ) / total_weight
    center_y = sum(
        detection.y * max(detection.confidence, 1e-6)
        for detection in consensus
    ) / total_weight
    width = median(detection.width for detection in consensus)
    height = median(detection.height for detection in consensus)
    confidence = max(detection.confidence for detection in consensus)
    return BallPoint(
        source_frame=source_frame,
        clip_seconds=clip_seconds,
        confidence=round(confidence, 6),
        x=center_x,
        y=center_y,
        box_diagonal=hypot(width, height),
        evidence="focused_multiscale_detector",
        temporal_score=None,
        source_attribution="yolo26_focused_multiscale",
    )


def _multiscale_detection_consensus(
    detections: Iterable[_FocusedBallDetection],
    *,
    expected_x: float,
    expected_y: float,
    reference_diameter: float,
) -> tuple[_FocusedBallDetection, ...]:
    if reference_diameter <= 0:
        return ()
    profile = FOCUSED_MULTISCALE_REDETECTION_PROFILE
    maximum_trajectory_distance = reference_diameter * float(
        profile["maximum_trajectory_distance_ball_diameters"]
    )
    eligible = [
        detection
        for detection in detections
        if hypot(
            detection.x - expected_x,
            detection.y - expected_y,
        )
        <= maximum_trajectory_distance
    ]
    groups: list[list[_FocusedBallDetection]] = []
    maximum_consensus_distance = reference_diameter * float(
        profile["consensus_radius_ball_diameters"]
    )
    for detection in sorted(
        eligible,
        key=lambda candidate: (
            -candidate.confidence,
            candidate.x,
            candidate.y,
        ),
    ):
        for group in groups:
            center_x = sum(candidate.x for candidate in group) / len(group)
            center_y = sum(candidate.y for candidate in group) / len(group)
            if (
                hypot(
                    detection.x - center_x,
                    detection.y - center_y,
                )
                <= maximum_consensus_distance
            ):
                group.append(detection)
                break
        else:
            groups.append([detection])
    minimum_variants = int(profile["minimum_consensus_variants"])
    valid_groups = [
        group
        for group in groups
        if len({candidate.variant for candidate in group}) >= minimum_variants
    ]
    if not valid_groups:
        return ()
    return tuple(
        max(
            valid_groups,
            key=lambda group: (
                -hypot(
                    sum(candidate.x for candidate in group) / len(group)
                    - expected_x,
                    sum(candidate.y for candidate in group) / len(group)
                    - expected_y,
                ),
                len({candidate.variant for candidate in group}),
                sum(candidate.confidence for candidate in group),
            ),
        )
    )
