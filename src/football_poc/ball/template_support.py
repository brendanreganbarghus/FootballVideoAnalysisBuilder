from __future__ import annotations

from .settings import *  # noqa: F401,F403

def _add_template_supported_points(
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
        for plan in _template_bridge_plans(
            track,
            track_index=track_index,
            fps=fps,
            frame_step=frame_step,
            maximum_gap_seconds=maximum_gap_seconds,
        )
    ]
    if not plans:
        return tracks

    plans_by_anchor_frame: dict[int, list[tuple[int, BallPoint]]] = defaultdict(
        list
    )
    plans_by_target_frame: dict[int, list[int]] = defaultdict(list)
    for plan_index, plan in enumerate(plans):
        for point in plan.template_points:
            plans_by_anchor_frame[point.source_frame].append(
                (plan_index, point)
            )
        plans_by_target_frame[plan.target_frame].append(plan_index)

    templates: dict[int, list[tuple[BallPoint, np.ndarray]]] = defaultdict(list)
    additions: dict[int, list[BallPoint]] = defaultdict(list)
    required_frames = set(plans_by_anchor_frame) | set(plans_by_target_frame)
    last_required_frame = max(required_frames)
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        for source_frame in range(last_required_frame + 1):
            if source_frame not in required_frames:
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
            grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            for plan_index, point in plans_by_anchor_frame.get(
                source_frame,
                [],
            ):
                template = _extract_ball_template(grayscale, point)
                if template is not None:
                    templates[plan_index].append((point, template))
            for plan_index in plans_by_target_frame.get(source_frame, []):
                point = _template_consensus_point(
                    plans[plan_index],
                    templates[plan_index],
                    grayscale,
                    fps=fps,
                )
                if point is not None:
                    additions[plans[plan_index].track_index].append(point)
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


def _template_bridge_plans(
    track: BallTrack,
    *,
    track_index: int,
    fps: float,
    frame_step: int,
    maximum_gap_seconds: float,
    maximum_template_history_points: int = 8,
) -> tuple[_TemplateBridge, ...]:
    if frame_step < 1 or fps <= 0 or maximum_gap_seconds <= 0:
        raise ValueError("Template bridge frame step, FPS, and gap must be positive")
    if maximum_template_history_points < 3:
        raise ValueError("Template bridge needs at least three history points")

    plans: list[_TemplateBridge] = []
    ordered = sorted(
        (
            point
            for point in track.points
            if point.evidence == "detector"
        ),
        key=lambda point: point.source_frame,
    )
    for index, (first, second) in enumerate(zip(ordered, ordered[1:])):
        frame_gap = second.source_frame - first.source_frame
        time_gap = second.clip_seconds - first.clip_seconds
        if (
            frame_gap <= frame_step
            or time_gap > maximum_gap_seconds + 1e-6
        ):
            continue
        if index > 0:
            previous = ordered[index - 1]
            incoming_x = first.x - previous.x
            incoming_y = first.y - previous.y
            bridge_x = second.x - first.x
            bridge_y = second.y - first.y
            if incoming_x * bridge_x + incoming_y * bridge_y <= 0:
                continue
        template_points = tuple(
            ordered[
                max(0, index - maximum_template_history_points + 1) : index + 1
            ]
        )
        if len(template_points) < 3:
            continue
        for target_frame in range(
            first.source_frame + frame_step,
            second.source_frame,
            frame_step,
        ):
            plans.append(
                _TemplateBridge(
                    track_index=track_index,
                    first=first,
                    second=second,
                    target_frame=target_frame,
                    template_points=template_points,
                )
            )
    return tuple(plans)


def _extract_ball_template(
    grayscale: np.ndarray,
    point: BallPoint,
    *,
    radius_scale: float = 1.0,
) -> np.ndarray | None:
    if radius_scale <= 0:
        raise ValueError("Template radius scale must be positive")
    radius = max(4, round(point.box_diagonal * radius_scale))
    center_x = round(point.x)
    center_y = round(point.y)
    left = center_x - radius
    right = center_x + radius + 1
    top = center_y - radius
    bottom = center_y + radius + 1
    if left < 0 or top < 0 or right > grayscale.shape[1] or bottom > grayscale.shape[0]:
        return None
    return grayscale[top:bottom, left:right]


def _template_consensus_point(
    plan: _TemplateBridge,
    templates: Iterable[tuple[BallPoint, np.ndarray]],
    target_grayscale: np.ndarray,
    *,
    fps: float,
    minimum_template_score: float = 0.45,
    minimum_consensus_templates: int = 3,
    search_radius_diameters: float = 4.0,
    consensus_radius_diameters: float = 1.0,
) -> BallPoint | None:
    if fps <= 0:
        raise ValueError("Template consensus FPS must be positive")
    if minimum_consensus_templates < 1:
        raise ValueError("Template consensus requires at least one template")
    if not 0 <= minimum_template_score <= 1:
        raise ValueError("Template score threshold must be between 0 and 1")
    if search_radius_diameters <= 0 or consensus_radius_diameters <= 0:
        raise ValueError("Template search and consensus radii must be positive")

    anchor_diameters = [
        point.box_diagonal
        for point in plan.template_points
        if point.box_diagonal > 0
    ]
    if not anchor_diameters:
        return None
    reference_diameter = median(anchor_diameters)
    alpha = (
        (plan.target_frame - plan.first.source_frame)
        / (plan.second.source_frame - plan.first.source_frame)
    )
    predicted_x = plan.first.x + (plan.second.x - plan.first.x) * alpha
    predicted_y = plan.first.y + (plan.second.y - plan.first.y) * alpha
    search_radius = max(
        16,
        round(reference_diameter * search_radius_diameters),
    )
    matches = [
        match
        for _, template in templates
        if (
            match := _template_match(
                target_grayscale,
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
        return None

    total_score = sum(match.score for match in consensus)
    center_x = sum(match.x * match.score for match in consensus) / total_score
    center_y = sum(match.y * match.score for match in consensus) / total_score
    return BallPoint(
        source_frame=plan.target_frame,
        clip_seconds=round(
            plan.first.clip_seconds
            + (plan.target_frame - plan.first.source_frame) / fps,
            3,
        ),
        confidence=min(plan.first.confidence, plan.second.confidence),
        x=center_x,
        y=center_y,
        box_diagonal=reference_diameter,
        evidence="template_consensus",
        temporal_score=round(
            min(match.score for match in consensus),
            6,
        ),
        source_attribution="temporal_detector_observed",
    )


def _template_match(
    target_grayscale: np.ndarray,
    template: np.ndarray,
    *,
    predicted_x: float,
    predicted_y: float,
    search_radius: int,
) -> _TemplateMatch:
    template_height, template_width = template.shape
    center_x = round(predicted_x)
    center_y = round(predicted_y)
    left = max(0, center_x - search_radius - template_width)
    right = min(
        target_grayscale.shape[1],
        center_x + search_radius + template_width + 1,
    )
    top = max(0, center_y - search_radius - template_height)
    bottom = min(
        target_grayscale.shape[0],
        center_y + search_radius + template_height + 1,
    )
    search = target_grayscale[top:bottom, left:right]
    if (
        search.shape[0] < template_height
        or search.shape[1] < template_width
    ):
        return _TemplateMatch(
            x=predicted_x,
            y=predicted_y,
            score=-1.0,
        )
    scores = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(scores)
    return _TemplateMatch(
        x=left + location[0] + (template_width - 1) / 2,
        y=top + location[1] + (template_height - 1) / 2,
        score=float(score),
    )


def _largest_template_consensus(
    matches: Iterable[_TemplateMatch],
    *,
    maximum_distance: float,
) -> tuple[_TemplateMatch, ...]:
    groups: list[list[_TemplateMatch]] = []
    for match in sorted(
        matches,
        key=lambda item: (-item.score, item.x, item.y),
    ):
        for group in groups:
            total_score = sum(item.score for item in group)
            center_x = sum(item.x * item.score for item in group) / total_score
            center_y = sum(item.y * item.score for item in group) / total_score
            if hypot(match.x - center_x, match.y - center_y) <= maximum_distance:
                group.append(match)
                break
        else:
            groups.append([match])
    if not groups:
        return ()
    best = max(
        groups,
        key=lambda group: (
            len(group),
            sum(item.score for item in group),
        ),
    )
    return tuple(best)
