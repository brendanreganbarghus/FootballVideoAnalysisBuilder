from __future__ import annotations

from .settings import *  # noqa: F401,F403

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


def _add_short_stationary_template_recoveries(
    tracks: Iterable[BallTrack],
    *,
    video: Path,
    fps: float,
    frame_step: int,
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    if fps <= 0 or frame_step < 1:
        raise ValueError("Short stationary recovery timing must be positive")

    plans: list[_BidirectionalTemplateBridge] = []
    for track_index, track in enumerate(tracks):
        points = sorted(track.points, key=lambda point: point.source_frame)
        for first, second in zip(points, points[1:]):
            if second.source_frame - first.source_frame != frame_step * 2:
                continue
            if (
                first.source_attribution
                not in {"yolo26_observed", "yolo26_focused_multiscale"}
                or second.source_attribution
                not in {"yolo26_observed", "yolo26_focused_multiscale"}
            ):
                continue
            diameters = [
                diameter
                for diameter in (first.box_diagonal, second.box_diagonal)
                if diameter > 0
            ]
            if not diameters:
                continue
            reference_diameter = median(diameters)
            if hypot(first.x - second.x, first.y - second.y) > (
                reference_diameter
                * float(
                    SHORT_STATIONARY_TEMPLATE_PROFILE[
                        "maximum_endpoint_distance_ball_diameters"
                    ]
                )
            ):
                continue
            plans.append(
                _BidirectionalTemplateBridge(
                    track_index=track_index,
                    frame_step=frame_step,
                    previous=None,
                    first=first,
                    second=second,
                    following=None,
                    bridge_kind="long_stationary",
                )
            )
    if not plans:
        return tracks

    grayscale = _read_sampled_grayscale_frames(
        video,
        sorted(
            {
                source_frame
                for plan in plans
                for source_frame in plan.frames
            }
        ),
    )
    additions: dict[int, list[BallPoint]] = defaultdict(list)
    for plan in plans:
        additions[plan.track_index].extend(
            _bidirectional_template_points(
                plan,
                {
                    source_frame: grayscale[source_frame]
                    for source_frame in plan.frames
                },
                fps=fps,
                minimum_template_score=float(
                    SHORT_STATIONARY_TEMPLATE_PROFILE[
                        "minimum_template_score"
                    ]
                ),
                maximum_agreement_diameters=float(
                    SHORT_STATIONARY_TEMPLATE_PROFILE[
                        "maximum_template_disagreement_ball_diameters"
                    ]
                ),
            )
        )
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
