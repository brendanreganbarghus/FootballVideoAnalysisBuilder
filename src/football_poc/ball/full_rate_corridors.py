from __future__ import annotations

from .settings import *  # noqa: F401,F403

def _add_full_rate_motion_streaks(
    tracks: Iterable[BallTrack],
    *,
    video: Path,
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    additions: dict[int, list[BallPoint]] = defaultdict(list)
    for track_index, track in enumerate(tracks):
        with _BoundedColorFrameReader(video) as frame_reader:
            ordered = sorted(track.points, key=lambda point: point.source_frame)
            for seed_index, (seed, following) in enumerate(
                zip(ordered, ordered[1:])
            ):
                if following.source_frame - seed.source_frame <= frame_step:
                    continue
                reference_diameter = median(
                    point.box_diagonal
                    for point in ordered[
                        max(0, seed_index - 7) : seed_index + 1
                    ]
                    if point.box_diagonal > 0
                )
                if not _has_stable_motion_streak_history(
                    ordered,
                    seed_index=seed_index,
                    fps=fps,
                    reference_diameter=reference_diameter,
                ):
                    continue
                color_frames = frame_reader.read_range(
                    seed.source_frame,
                    following.source_frame,
                )
                grayscale = {
                    source_frame: cv2.cvtColor(
                        frame,
                        cv2.COLOR_BGR2GRAY,
                    )
                    for source_frame, frame in color_frames.items()
                }
                candidates_by_frame = {
                    source_frame: _full_rate_motion_streak_candidates(
                        previous=grayscale[source_frame - 1],
                        current=grayscale[source_frame],
                        following=grayscale[source_frame + 1],
                        source_frame=source_frame,
                        reference_diameter=reference_diameter,
                    )
                    for source_frame in range(
                        seed.source_frame + 1,
                        following.source_frame,
                    )
                }
                consensus = _full_rate_motion_streak_consensus(
                    candidates_by_frame,
                    seed=seed,
                    history=ordered[: seed_index + 1],
                    fps=fps,
                    frame_step=frame_step,
                    reference_diameter=reference_diameter,
                    max_speed_pixels_per_second=max_speed_pixels_per_second,
                )
                additions[track_index].extend(consensus)
    return tuple(
        BallTrack(
            track.track_id,
            sorted(
                [*track.points, *additions[index]],
                key=lambda point: point.source_frame,
            ),
        )
        for index, track in enumerate(tracks)
    )


def _add_full_rate_trajectory_corridors(
    tracks: Iterable[BallTrack],
    *,
    video: Path,
    fps: float,
    frame_step: int,
    analysis_end_frame: int,
    max_speed_pixels_per_second: float,
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    if not tracks:
        return tracks
    additions_by_track: dict[int, list[BallPoint]] = defaultdict(list)
    for track_index, track in enumerate(tracks):
        with _BoundedColorFrameReader(video) as frame_reader:
            accepted = sorted(track.points, key=lambda point: point.source_frame)
            accepted_frames = {point.source_frame for point in accepted}
            for target_frame in range(
                frame_step,
                analysis_end_frame + 1,
                frame_step,
            ):
                if target_frame in accepted_frames:
                    continue
                current = sorted(
                    [*accepted, *additions_by_track[track_index]],
                    key=lambda point: point.source_frame,
                )
                history = [
                    point for point in current if point.source_frame < target_frame
                ]
                if not history:
                    continue
                seed = history[-1]
                if (
                    target_frame - seed.source_frame
                    > round(
                        float(
                            FULL_RATE_TRAJECTORY_CORRIDOR_PROFILE[
                                "maximum_gap_seconds"
                            ]
                        )
                        * fps
                    )
                ):
                    continue
                following = next(
                    (
                        point
                        for point in current
                        if point.source_frame > target_frame
                    ),
                    None,
                )
                confirmation_frames = round(
                    float(
                        FULL_RATE_TRAJECTORY_CORRIDOR_PROFILE[
                            "confirmation_seconds"
                        ]
                    )
                    * fps
                )
                end_frame = min(
                    analysis_end_frame,
                    target_frame + confirmation_frames,
                    (
                        following.source_frame - 1
                        if following is not None
                        else analysis_end_frame
                    ),
                )
                if end_frame <= target_frame:
                    end_frame = target_frame
                reference_diameter = median(
                    point.box_diagonal
                    for point in history[-8:]
                    if point.box_diagonal > 0
                )
                if not _trajectory_corridor_history_is_supported(
                    history,
                    fps=fps,
                    reference_diameter=reference_diameter,
                ):
                    continue
                color_frames = frame_reader.read_range(
                    seed.source_frame,
                    end_frame + 1,
                )
                grayscale = {
                    source_frame: cv2.cvtColor(
                        color_frames[source_frame],
                        cv2.COLOR_BGR2GRAY,
                    )
                    for source_frame in range(
                        seed.source_frame,
                        end_frame + 2,
                    )
                }
                candidates_by_frame = {
                    source_frame: _full_rate_motion_streak_candidates(
                        previous=grayscale[source_frame - 1],
                        current=grayscale[source_frame],
                        following=grayscale[source_frame + 1],
                        source_frame=source_frame,
                        reference_diameter=reference_diameter,
                    )
                    for source_frame in range(
                        seed.source_frame + 1,
                        end_frame + 1,
                    )
                }
                point = _full_rate_trajectory_corridor_point(
                    candidates_by_frame,
                    color_frames=color_frames,
                    history=history,
                    target_frame=target_frame,
                    fps=fps,
                    reference_diameter=reference_diameter,
                    max_speed_pixels_per_second=max_speed_pixels_per_second,
                )
                if point is not None:
                    additions_by_track[track_index].append(point)
    return tuple(
        BallTrack(
            track.track_id,
            sorted(
                [*track.points, *additions_by_track[index]],
                key=lambda point: point.source_frame,
            ),
        )
        for index, track in enumerate(tracks)
    )


class _BoundedColorFrameReader:
    def __init__(self, video: Path) -> None:
        self.video = video
        self.capture: cv2.VideoCapture | None = None
        self.frames: dict[int, np.ndarray] = {}
        self.next_frame = 0

    def __enter__(self) -> "_BoundedColorFrameReader":
        self.capture = cv2.VideoCapture(str(self.video))
        if not self.capture.isOpened():
            self.capture.release()
            self.capture = None
            raise ValueError(f"Could not open benchmark video: {self.video}")
        return self

    def __exit__(self, *_args: object) -> None:
        if self.capture is not None:
            self.capture.release()
        self.capture = None
        self.frames.clear()

    def read_range(self, first_frame: int, last_frame: int) -> dict[int, np.ndarray]:
        if self.capture is None:
            raise RuntimeError("Color frame reader is not open")
        if first_frame > last_frame:
            return {}
        if first_frame < self.next_frame and first_frame not in self.frames:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, first_frame)
            self.next_frame = first_frame
            self.frames.clear()
        for frame_number in tuple(self.frames):
            if frame_number < first_frame:
                del self.frames[frame_number]
        while self.next_frame <= last_frame:
            ok, frame = self.capture.read()
            if not ok:
                raise RuntimeError(
                    f"Could not read source frame {self.next_frame} "
                    f"from {self.video}"
                )
            if self.next_frame >= first_frame:
                self.frames[self.next_frame] = frame
            self.next_frame += 1
        return {
            frame_number: self.frames[frame_number]
            for frame_number in range(first_frame, last_frame + 1)
        }


def _read_sampled_color_frames(
    video: Path,
    source_frames: Iterable[int],
) -> dict[int, np.ndarray]:
    required = set(source_frames)
    if not required:
        return {}
    frames: dict[int, np.ndarray] = {}
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        for source_frame in range(max(required) + 1):
            if source_frame not in required:
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
            frames[source_frame] = frame
    finally:
        capture.release()
    return frames


def _trajectory_corridor_history_is_supported(
    history: list[BallPoint],
    *,
    fps: float,
    reference_diameter: float,
) -> bool:
    profile = FULL_RATE_TRAJECTORY_CORRIDOR_PROFILE
    if reference_diameter <= 0:
        return False
    seed = history[-1]
    history_frames = round(float(profile["history_seconds"]) * fps)
    recent = [
        point
        for point in history
        if seed.source_frame - point.source_frame <= history_frames
    ]
    if len(recent) < int(profile["minimum_history_points"]):
        return False
    velocity_x, velocity_y = _recent_ball_velocity_per_frame(recent, fps=fps)
    return (
        hypot(velocity_x, velocity_y) * fps
        >= reference_diameter
        * float(profile["minimum_history_speed_ball_diameters_per_second"])
    )


def _recent_ball_velocity_per_frame(
    history: Iterable[BallPoint],
    *,
    fps: float,
) -> tuple[float, float]:
    ordered = sorted(history, key=lambda point: point.source_frame)[-4:]
    velocities = [
        (
            (current.x - previous.x)
            / (current.source_frame - previous.source_frame),
            (current.y - previous.y)
            / (current.source_frame - previous.source_frame),
        )
        for previous, current in zip(ordered, ordered[1:])
        if current.source_frame > previous.source_frame
    ]
    if not velocities:
        return 0.0, 0.0
    return (
        median(velocity[0] for velocity in velocities),
        median(velocity[1] for velocity in velocities),
    )


def _full_rate_trajectory_corridor_point(
    candidates_by_frame: dict[int, tuple[_MotionStreakCandidate, ...]],
    *,
    color_frames: dict[int, np.ndarray],
    history: list[BallPoint],
    target_frame: int,
    fps: float,
    reference_diameter: float,
    max_speed_pixels_per_second: float,
) -> BallPoint | None:
    profile = FULL_RATE_TRAJECTORY_CORRIDOR_PROFILE
    seed = history[-1]
    velocity_x, velocity_y = _recent_ball_velocity_per_frame(
        history,
        fps=fps,
    )
    seed_appearance = _motion_point_lab_descriptor(
        color_frames[seed.source_frame],
        x=seed.x,
        y=seed.y,
    )
    maximum_acceleration = float(
        profile["maximum_acceleration_pixels_per_second_squared"]
    )
    minimum_search_radius = reference_diameter * float(
        profile["minimum_search_radius_ball_diameters"]
    )
    appearance_scale = float(profile["appearance_scale"])
    prepared: dict[int, tuple[tuple[_MotionStreakCandidate, float], ...]] = {}
    for source_frame, candidates in candidates_by_frame.items():
        elapsed = (source_frame - seed.source_frame) / fps
        predicted_x = seed.x + velocity_x * (source_frame - seed.source_frame)
        predicted_y = seed.y + velocity_y * (source_frame - seed.source_frame)
        search_radius = max(
            minimum_search_radius,
            0.5 * maximum_acceleration * elapsed**2,
        )
        search_radius = min(
            search_radius,
            max_speed_pixels_per_second * elapsed + minimum_search_radius,
        )
        supported: list[tuple[_MotionStreakCandidate, float]] = []
        for candidate in candidates:
            if (
                hypot(
                    candidate.x - predicted_x,
                    candidate.y - predicted_y,
                )
                > search_radius
            ):
                continue
            descriptor = _motion_point_lab_descriptor(
                color_frames[source_frame],
                x=candidate.x,
                y=candidate.y,
            )
            appearance_score = float(
                np.exp(
                    -float(np.linalg.norm(descriptor - seed_appearance))
                    / appearance_scale
                )
            )
            if appearance_score >= float(profile["minimum_appearance_score"]):
                supported.append((candidate, appearance_score))
        prepared[source_frame] = tuple(supported)

    paths = [
        _MotionStreakPath(
            (),
            0.0,
            velocity_x=velocity_x,
            velocity_y=velocity_y,
        )
    ]
    path_positions: dict[int, tuple[int, float, float]] = {
        id(paths[0]): (seed.source_frame, seed.x, seed.y)
    }
    completed: list[_MotionStreakPath] = []
    maximum_gap = max(
        1,
        round(float(profile["maximum_evidence_gap_seconds"]) * fps),
    )
    maximum_acceleration_per_frame = maximum_acceleration / fps**2
    for source_frame in sorted(prepared):
        next_paths: list[_MotionStreakPath] = []
        next_positions: dict[int, tuple[int, float, float]] = {}
        for path in paths:
            last_frame, last_x, last_y = path_positions[id(path)]
            gap = source_frame - last_frame
            if gap > maximum_gap:
                completed.append(path)
                continue
            next_paths.append(path)
            next_positions[id(path)] = (last_frame, last_x, last_y)
            predicted_x = last_x + (path.velocity_x or 0.0) * gap
            predicted_y = last_y + (path.velocity_y or 0.0) * gap
            transition_radius = max(
                reference_diameter * 1.5,
                0.5 * maximum_acceleration_per_frame * gap**2,
            )
            for candidate, appearance_score in prepared[source_frame]:
                prediction_error = hypot(
                    candidate.x - predicted_x,
                    candidate.y - predicted_y,
                )
                if prediction_error > transition_radius:
                    continue
                candidate_velocity_x = (candidate.x - last_x) / gap
                candidate_velocity_y = (candidate.y - last_y) / gap
                acceleration = hypot(
                    candidate_velocity_x - (path.velocity_x or 0.0),
                    candidate_velocity_y - (path.velocity_y or 0.0),
                ) / gap
                if acceleration > maximum_acceleration_per_frame:
                    continue
                candidate_path = _MotionStreakPath(
                    (*path.points, candidate),
                    path.score
                    + 0.7 * candidate.visual_score
                    + 0.3 * appearance_score
                    - 0.7 * prediction_error / transition_radius
                    - 0.15 * (gap - 1),
                    candidate_velocity_x,
                    candidate_velocity_y,
                )
                next_paths.append(candidate_path)
                next_positions[id(candidate_path)] = (
                    source_frame,
                    candidate.x,
                    candidate.y,
                )
        deduplicated: dict[tuple[int, int, int, int, int], _MotionStreakPath] = {}
        deduplicated_positions: dict[int, tuple[int, float, float]] = {}
        for path in sorted(next_paths, key=lambda item: item.score, reverse=True):
            last_frame, last_x, last_y = next_positions[id(path)]
            key = (
                last_frame,
                round(last_x / 6),
                round(last_y / 6),
                round((path.velocity_x or 0.0) / 6),
                round((path.velocity_y or 0.0) / 6),
            )
            if key in deduplicated:
                continue
            deduplicated[key] = path
            deduplicated_positions[id(path)] = (last_frame, last_x, last_y)
            if len(deduplicated) >= int(profile["maximum_paths"]):
                break
        paths = list(deduplicated.values())
        path_positions = deduplicated_positions
    completed.extend(paths)
    eligible = [
        path
        for path in completed
        if len(path.points) >= int(profile["minimum_path_points"])
    ]
    if not eligible:
        return None
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
    target_candidates = [
        next(
            (
                point
                for point in path.points
                if point.source_frame == target_frame
            ),
            None,
        )
        for path in near_best
    ]
    if not target_candidates or any(
        candidate is None for candidate in target_candidates
    ):
        return None
    agreed = [
        candidate
        for candidate in target_candidates
        if candidate is not None
    ]
    first = agreed[0]
    if (
        first.visual_score < float(profile["minimum_visual_score"])
        or any(
            hypot(candidate.x - first.x, candidate.y - first.y)
            > reference_diameter
            * float(profile["consensus_radius_ball_diameters"])
            for candidate in agreed[1:]
        )
    ):
        return None
    appearance_score = float(
        np.exp(
            -float(
                np.linalg.norm(
                    _motion_point_lab_descriptor(
                        color_frames[target_frame],
                        x=first.x,
                        y=first.y,
                    )
                    - seed_appearance
                )
            )
            / appearance_scale
        )
    )
    return BallPoint(
        source_frame=target_frame,
        clip_seconds=target_frame / fps,
        confidence=round(
            0.7 * first.visual_score + 0.3 * appearance_score,
            6,
        ),
        x=first.x,
        y=first.y,
        box_diagonal=hypot(first.width, first.height),
        evidence="full_rate_trajectory_corridor",
        temporal_score=round(best_mean_score, 6),
        source_attribution="raw_motion_micro_crop_supported",
    )


def _motion_point_lab_descriptor(
    frame: np.ndarray,
    *,
    x: float,
    y: float,
    radius: int = 3,
) -> np.ndarray:
    center_x = round(x)
    center_y = round(y)
    crop = frame[
        max(0, center_y - radius) : min(frame.shape[0], center_y + radius + 1),
        max(0, center_x - radius) : min(frame.shape[1], center_x + radius + 1),
    ]
    if not crop.size:
        return np.zeros(3, dtype=np.float64)
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
    return np.median(lab.reshape(-1, 3), axis=0).astype(np.float64)


def _has_stable_motion_streak_history(
    ordered: list[BallPoint],
    *,
    seed_index: int,
    fps: float,
    reference_diameter: float,
) -> bool:
    profile = FULL_RATE_MOTION_STREAK_PROFILE
    seed = ordered[seed_index]
    minimum_seconds = float(LONG_STATIONARY_TEMPLATE_PROFILE["minimum_history_seconds"])
    history = [
        point
        for point in ordered[: seed_index + 1]
        if seed.clip_seconds - point.clip_seconds <= minimum_seconds + 1e-6
    ]
    if (
        len(history) < int(LONG_STATIONARY_TEMPLATE_PROFILE["minimum_history_points"])
        or history[-1] != seed
        or history[-1].clip_seconds - history[0].clip_seconds
        < minimum_seconds - 1 / fps
        or reference_diameter <= 0
    ):
        return False
    center_x = median(point.x for point in history)
    center_y = median(point.y for point in history)
    maximum_radius = reference_diameter * float(
        LONG_STATIONARY_TEMPLATE_PROFILE["maximum_history_radius_ball_diameters"]
    )
    return all(
        hypot(point.x - center_x, point.y - center_y) <= maximum_radius
        for point in history
    )
