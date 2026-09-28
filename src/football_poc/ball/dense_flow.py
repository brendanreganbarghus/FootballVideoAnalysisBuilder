from __future__ import annotations

from .settings import *  # noqa: F401,F403

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
