from __future__ import annotations

from .settings import *  # noqa: F401,F403

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
