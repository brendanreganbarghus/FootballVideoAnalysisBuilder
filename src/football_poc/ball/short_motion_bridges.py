from __future__ import annotations

from .settings import *  # noqa: F401,F403

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
