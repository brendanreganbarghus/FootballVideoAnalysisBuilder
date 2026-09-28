from __future__ import annotations

from .settings import *  # noqa: F401,F403

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
        is_verified_terminal_seed = seed.evidence == "template_validated_detector"
        is_stable_detector_seed = _is_stable_direct_detector_seed(
            ordered,
            seed_index=index,
            frame_step=frame_step,
            minimum_template_seed_score=minimum_template_seed_score,
        )
        if not is_verified_terminal_seed and not is_stable_detector_seed:
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
        maximum_steps = (
            max(
                1,
                round(
                    float(
                        LONG_STATIONARY_TEMPLATE_PROFILE[
                            "maximum_forward_seconds"
                        ]
                    )
                    * fps
                    / frame_step
                ),
            )
            if is_stable_detector_seed
            else maximum_propagated_sample_steps
        )
        end_frame = min(
            following.source_frame,
            seed.source_frame
            + frame_step * (maximum_steps + 1),
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


def _is_stable_direct_detector_seed(
    ordered: list[BallPoint],
    *,
    seed_index: int,
    frame_step: int,
    minimum_template_seed_score: float,
) -> bool:
    seed = ordered[seed_index]
    if (
        seed.evidence != "detector"
        or seed.source_attribution != "yolo26_observed"
        or seed.box_diagonal <= 0
    ):
        return False

    profile = LONG_STATIONARY_TEMPLATE_PROFILE
    minimum_history_points = int(profile["minimum_history_points"])
    history = [
        point
        for point in ordered[: seed_index + 1]
        if _is_reliable_template_seed(
            point,
            minimum_template_seed_score=minimum_template_seed_score,
        )
    ][-minimum_history_points:]
    if (
        len(history) < minimum_history_points
        or history[-1] != seed
        or history[-1].clip_seconds - history[0].clip_seconds
        < float(profile["minimum_history_seconds"]) - 1e-6
        or any(
            current.source_frame - previous.source_frame != frame_step
            for previous, current in zip(history, history[1:])
        )
    ):
        return False

    reference_diameter = median(
        point.box_diagonal for point in history if point.box_diagonal > 0
    )
    if reference_diameter <= 0:
        return False
    center_x = median(point.x for point in history)
    center_y = median(point.y for point in history)
    maximum_radius = (
        reference_diameter
        * float(profile["maximum_history_radius_ball_diameters"])
    )
    return all(
        hypot(point.x - center_x, point.y - center_y) <= maximum_radius
        for point in history
    )


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
