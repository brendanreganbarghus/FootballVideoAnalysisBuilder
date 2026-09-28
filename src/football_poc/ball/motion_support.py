from __future__ import annotations

from .settings import *  # noqa: F401,F403

def _add_motion_supported_points(
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
        for plan in _motion_bridge_plans(
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
                point = _motion_circle_bridge_point(
                    plan,
                    {
                        frame: grayscale_frames[frame]
                        for frame in plan.frames
                    },
                    fps=fps,
                )
                if point is not None:
                    additions[plan.track_index].append(point)
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


def _motion_bridge_plans(
    track: BallTrack,
    *,
    track_index: int,
    fps: float,
    frame_step: int,
    maximum_gap_seconds: float,
) -> tuple[_MotionBridge, ...]:
    if frame_step < 1 or fps <= 0 or maximum_gap_seconds <= 0:
        raise ValueError("Motion bridge frame step, FPS, and gap must be positive")
    points = sorted(
        (
            point
            for point in track.points
            if point.evidence == "detector"
        ),
        key=lambda point: point.source_frame,
    )
    plans: list[_MotionBridge] = []
    for index, (first, second) in enumerate(zip(points, points[1:])):
        if (
            second.source_frame - first.source_frame != frame_step * 2
            or second.clip_seconds - first.clip_seconds
            > maximum_gap_seconds + 1e-6
            or first.box_diagonal <= 0
            or second.box_diagonal <= 0
        ):
            continue
        if index > 0:
            previous = points[index - 1]
            incoming_x = first.x - previous.x
            incoming_y = first.y - previous.y
            bridge_x = second.x - first.x
            bridge_y = second.y - first.y
            if incoming_x * bridge_x + incoming_y * bridge_y <= 0:
                continue
        plans.append(
            _MotionBridge(
                track_index=track_index,
                first=first,
                second=second,
            )
        )
    return tuple(plans)


def _motion_circle_bridge_point(
    plan: _MotionBridge,
    grayscale_frames: dict[int, np.ndarray],
    *,
    fps: float,
    maximum_prediction_distance_diameters: float = 0.75,
    maximum_motion_distance_diameters: float = 0.75,
) -> BallPoint | None:
    if fps <= 0:
        raise ValueError("Motion bridge FPS must be positive")
    if (
        maximum_prediction_distance_diameters <= 0
        or maximum_motion_distance_diameters <= 0
    ):
        raise ValueError("Motion bridge distance limits must be positive")

    reference_diameter = median(
        (plan.first.box_diagonal, plan.second.box_diagonal)
    )
    target_frame = plan.target_frame
    alpha = (
        (target_frame - plan.first.source_frame)
        / (plan.second.source_frame - plan.first.source_frame)
    )
    predicted_x = plan.first.x + (plan.second.x - plan.first.x) * alpha
    predicted_y = plan.first.y + (plan.second.y - plan.first.y) * alpha
    search_radius = max(8, round(reference_diameter * 1.5))
    circles = _nearby_circles(
        grayscale_frames[target_frame],
        center_x=predicted_x,
        center_y=predicted_y,
        search_radius=search_radius,
        reference_diameter=reference_diameter,
    )
    maximum_prediction_distance = (
        reference_diameter * maximum_prediction_distance_diameters
    )
    previous_motion = _compact_motion_centers(
        cv2.absdiff(
            grayscale_frames[target_frame],
            grayscale_frames[plan.first.source_frame],
        ),
        center_x=predicted_x,
        center_y=predicted_y,
        search_radius=search_radius,
        reference_diameter=reference_diameter,
    )
    following_motion = _compact_motion_centers(
        cv2.absdiff(
            grayscale_frames[target_frame],
            grayscale_frames[plan.second.source_frame],
        ),
        center_x=predicted_x,
        center_y=predicted_y,
        search_radius=search_radius,
        reference_diameter=reference_diameter,
    )
    maximum_motion_distance = (
        reference_diameter * maximum_motion_distance_diameters
    )
    supported = [
        circle
        for circle in circles
        if hypot(circle.x - predicted_x, circle.y - predicted_y)
        <= maximum_prediction_distance
        and _nearest_motion_distance(circle, previous_motion)
        <= maximum_motion_distance
        and _nearest_motion_distance(circle, following_motion)
        <= maximum_motion_distance
    ]
    if len(supported) != 1:
        return None

    circle = supported[0]
    prediction_score = 1 - (
        hypot(circle.x - predicted_x, circle.y - predicted_y)
        / maximum_prediction_distance
    )
    motion_score = min(
        1
        - _nearest_motion_distance(circle, previous_motion)
        / maximum_motion_distance,
        1
        - _nearest_motion_distance(circle, following_motion)
        / maximum_motion_distance,
    )
    return BallPoint(
        source_frame=target_frame,
        clip_seconds=round(
            plan.first.clip_seconds
            + (target_frame - plan.first.source_frame) / fps,
            3,
        ),
        confidence=min(plan.first.confidence, plan.second.confidence),
        x=circle.x,
        y=circle.y,
        box_diagonal=reference_diameter,
        evidence="motion_circle",
        temporal_score=round(min(prediction_score, motion_score), 6),
        source_attribution="temporal_detector_observed",
    )


def _nearby_circles(
    grayscale: np.ndarray,
    *,
    center_x: float,
    center_y: float,
    search_radius: int,
    reference_diameter: float,
) -> tuple[_CircleCandidate, ...]:
    left = max(0, round(center_x) - search_radius)
    right = min(grayscale.shape[1], round(center_x) + search_radius + 1)
    top = max(0, round(center_y) - search_radius)
    bottom = min(grayscale.shape[0], round(center_y) + search_radius + 1)
    search = grayscale[top:bottom, left:right]
    minimum_radius = max(2, round(reference_diameter * 0.2))
    maximum_radius = max(
        minimum_radius + 1,
        round(reference_diameter * 0.7),
    )
    circles = cv2.HoughCircles(
        cv2.medianBlur(search, 5),
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=max(4, round(reference_diameter * 0.5)),
        param1=70,
        param2=max(6, round(reference_diameter * 0.6)),
        minRadius=minimum_radius,
        maxRadius=maximum_radius,
    )
    if circles is None:
        return ()
    return tuple(
        _CircleCandidate(
            x=float(x + left),
            y=float(y + top),
            radius=float(radius),
        )
        for x, y, radius in circles[0]
    )


def _compact_motion_centers(
    difference: np.ndarray,
    *,
    center_x: float,
    center_y: float,
    search_radius: int,
    reference_diameter: float,
) -> tuple[tuple[float, float], ...]:
    left = max(0, round(center_x) - search_radius)
    right = min(difference.shape[1], round(center_x) + search_radius + 1)
    top = max(0, round(center_y) - search_radius)
    bottom = min(difference.shape[0], round(center_y) + search_radius + 1)
    search = difference[top:bottom, left:right]
    threshold = max(16, round(float(np.percentile(search, 90))))
    _, mask = cv2.threshold(search, threshold, 255, cv2.THRESH_BINARY)
    count, labels, statistics, centroids = cv2.connectedComponentsWithStats(mask)
    maximum_area = reference_diameter**2 * 2
    maximum_extent = reference_diameter * 2
    return tuple(
        (float(centroids[index][0] + left), float(centroids[index][1] + top))
        for index in range(1, count)
        if (
            2 <= statistics[index, cv2.CC_STAT_AREA] <= maximum_area
            and statistics[index, cv2.CC_STAT_WIDTH] <= maximum_extent
            and statistics[index, cv2.CC_STAT_HEIGHT] <= maximum_extent
        )
    )
