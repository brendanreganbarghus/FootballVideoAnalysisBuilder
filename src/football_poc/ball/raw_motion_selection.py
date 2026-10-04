from __future__ import annotations

from .settings import *  # noqa: F401,F403

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
    players: list[tuple[Any, ...]] = []
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
        if features is not None and len(features) >= 3:
            features[:, 0, 0] += x1
            features[:, 0, 1] += y1
        else:
            features = None
        players.append(
            (
                detection,
                x1,
                x2,
                y1,
                width,
                height,
                appearance_direction,
                appearance_confidence,
                features,
            )
        )

    # Lucas-Kanade tracks every point independently, so one call over all
    # players' features gives the same per-point result as one call per
    # player while building the full-frame image pyramids only once.
    tracked = [player[8] for player in players if player[8] is not None]
    moved_all = status_all = None
    if tracked:
        moved_all, status_all, _ = cv2.calcOpticalFlowPyrLK(
            current,
            following,
            np.concatenate(tracked),
            None,
            winSize=(15, 15),
            maxLevel=2,
        )
    offset = 0
    cones: list[_PlayerAttentionCone] = []
    for (
        detection,
        x1,
        x2,
        y1,
        width,
        height,
        appearance_direction,
        appearance_confidence,
        features,
    ) in players:
        motion_direction: np.ndarray | None = None
        motion_confidence = 0.0
        if features is not None:
            count = len(features)
            moved = status = None
            if moved_all is not None and status_all is not None:
                moved = moved_all[offset : offset + count]
                status = status_all[offset : offset + count]
            offset += count
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
