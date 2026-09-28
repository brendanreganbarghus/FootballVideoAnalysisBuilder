from __future__ import annotations

from .settings import *  # noqa: F401,F403

def _supported_ball_tracks(
    tracks: Iterable[BallTrack],
    *,
    minimum_track_points: int,
    max_speed_pixels_per_second: float,
    minimum_short_fragment_confidence: float = 0.2,
    minimum_short_fragment_speed_ratio: float = 0.075,
    foot_supported_points: frozenset[BallPoint] = frozenset(),
) -> tuple[BallTrack, ...]:
    return tuple(
        track
        for track in tracks
        if len(track.points) >= minimum_track_points
        or (
            minimum_track_points == 3
            and _is_confident_moving_pair(
                track,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
                minimum_mean_confidence=minimum_short_fragment_confidence,
                minimum_speed_ratio=minimum_short_fragment_speed_ratio,
            )
            or (
                minimum_track_points == 3
                and any(
                    point in foot_supported_points
                    for point in track.points
                )
                and _is_confident_moving_pair(
                    track,
                    max_speed_pixels_per_second=(
                        max_speed_pixels_per_second
                    ),
                    minimum_mean_confidence=0.1,
                    minimum_speed_ratio=minimum_short_fragment_speed_ratio,
                )
            )
        )
    )


def _is_confident_moving_pair(
    track: BallTrack,
    *,
    max_speed_pixels_per_second: float,
    minimum_mean_confidence: float,
    minimum_speed_ratio: float,
) -> bool:
    if len(track.points) != 2:
        return False
    first, second = track.points
    elapsed = second.clip_seconds - first.clip_seconds
    if elapsed <= 0:
        return False
    mean_confidence = (first.confidence + second.confidence) / 2
    speed = hypot(second.x - first.x, second.y - first.y) / elapsed
    return (
        mean_confidence >= minimum_mean_confidence
        and speed >= max_speed_pixels_per_second * minimum_speed_ratio
    )


def select_single_ball_trajectory(
    tracks: Iterable[BallTrack],
    *,
    max_gap_seconds: float,
    max_speed_pixels_per_second: float,
    minimum_mean_confidence: float = 0.1,
) -> tuple[BallTrack, ...]:
    candidates = tuple(
        track
        for track in tracks
        if (
            sum(point.confidence for point in track.points)
            / len(track.points)
            >= minimum_mean_confidence
        )
    )
    if not candidates:
        return ()
    quality = {
        track.track_id: (
            sum(point.confidence for point in track.points) / len(track.points)
        )
        * len(track.points) ** 0.5
        for track in candidates
    }
    by_frame: dict[int, list[tuple[BallTrack, BallPoint]]] = {}
    for track in candidates:
        for point in track.points:
            by_frame.setdefault(point.source_frame, []).append((track, point))

    selected: list[BallPoint] = []
    current_track_id: int | None = None
    for frame in sorted(by_frame):
        frame_candidates = by_frame[frame]
        continuing = [
            candidate
            for candidate in frame_candidates
            if candidate[0].track_id == current_track_id
            and _point_transition_is_plausible(
                selected,
                candidate[1],
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            )
        ]
        if continuing:
            chosen_track, chosen_point = continuing[0]
        elif not selected or (
            frame_candidates[0][1].clip_seconds
            - selected[-1].clip_seconds
            > max_gap_seconds
        ):
            restart_candidates = (
                frame_candidates
                if not selected
                else [
                    candidate
                    for candidate in frame_candidates
                    if len(candidate[0].points) >= 3
                ]
            )
            if not restart_candidates:
                continue
            chosen_track, chosen_point = max(
                restart_candidates,
                key=lambda candidate: (
                quality[candidate[0].track_id],
                candidate[1].confidence,
                ),
            )
        else:
            reachable: list[tuple[float, BallTrack, BallPoint]] = []
            previous = selected[-1]
            for track, point in frame_candidates:
                elapsed = point.clip_seconds - previous.clip_seconds
                if elapsed <= 0:
                    continue
                maximum_distance = max(
                    35.0,
                    max_speed_pixels_per_second * elapsed,
                )
                distance = hypot(point.x - previous.x, point.y - previous.y)
                if (
                    distance <= maximum_distance
                    and _point_transition_is_plausible(
                        selected,
                        point,
                        max_speed_pixels_per_second=(
                            max_speed_pixels_per_second
                        ),
                    )
                ):
                    reachable.append(
                        (
                            quality[track.track_id]
                            - distance / maximum_distance,
                            track,
                            point,
                        )
                    )
            if not reachable:
                continue
            _, chosen_track, chosen_point = max(
                reachable,
                key=lambda candidate: (
                candidate[0],
                candidate[2].confidence,
                ),
            )
        selected.append(chosen_point)
        current_track_id = chosen_track.track_id
    return (BallTrack(track_id=1, points=selected),)


def _point_transition_is_plausible(
    selected: list[BallPoint],
    candidate: BallPoint,
    *,
    max_speed_pixels_per_second: float,
) -> bool:
    if not selected:
        return True
    previous = selected[-1]
    elapsed = candidate.clip_seconds - previous.clip_seconds
    if elapsed <= 0:
        return False
    outgoing_velocity = np.array(
        [candidate.x - previous.x, candidate.y - previous.y]
    ) / elapsed
    if np.linalg.norm(outgoing_velocity) > max_speed_pixels_per_second:
        return False
    if len(selected) < 2:
        return True
    earlier = selected[-2]
    incoming_seconds = previous.clip_seconds - earlier.clip_seconds
    if incoming_seconds <= 0:
        return False
    incoming_velocity = np.array(
        [previous.x - earlier.x, previous.y - earlier.y]
    ) / incoming_seconds
    acceleration_seconds = (incoming_seconds + elapsed) / 2
    return (
        np.linalg.norm(outgoing_velocity - incoming_velocity)
        / acceleration_seconds
        <= float(
            SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                "maximum_acceleration_pixels_per_second_squared"
            ]
        )
    )


def _resolve_detector_conflicts_by_attention(
    tracks: Iterable[BallTrack],
    *,
    detector_candidates: Iterable[_BallCandidate],
    supported_foot_points: frozenset[BallPoint],
    records: list[dict[str, Any]],
    video: Path,
    frame_step: int,
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    if not tracks or not supported_foot_points:
        return tracks
    candidates_by_frame: dict[int, list[_BallCandidate]] = defaultdict(list)
    for candidate in detector_candidates:
        candidates_by_frame[candidate.point.source_frame].append(candidate)
    selected_by_frame = {
        point.source_frame: point
        for track in tracks
        for point in track.points
    }
    records_by_frame = {
        int(record["source_frame"]): record for record in records
    }
    conflict_frames = [
        frame
        for frame, selected in selected_by_frame.items()
        if (
            len(candidates_by_frame[frame]) > 1
            and selected not in supported_foot_points
            and sum(
                candidate.point in supported_foot_points
                for candidate in candidates_by_frame[frame]
            )
            == 1
            and frame - frame_step in records_by_frame
            and frame + frame_step in records_by_frame
        )
    ]
    if not conflict_frames:
        return tracks
    required_frames = {
        frame + offset * frame_step
        for frame in conflict_frames
        for offset in (-1, 0, 1)
    }
    grayscale = _read_sampled_grayscale_frames(video, required_frames)
    replacements: dict[int, BallPoint] = {}
    for frame in conflict_frames:
        selected = selected_by_frame[frame]
        alternative = next(
            candidate.point
            for candidate in candidates_by_frame[frame]
            if candidate.point in supported_foot_points
        )
        cones = _player_attention_cones(
            grayscale[frame - frame_step],
            grayscale[frame],
            grayscale[frame + frame_step],
            records_by_frame[frame],
        )
        selected_support, selected_score = _attention_convergence(
            selected,
            cones,
        )
        alternative_support, alternative_score = _attention_convergence(
            alternative,
            cones,
        )
        if _attention_advantage_is_decisive(
            alternative_support=alternative_support,
            alternative_score=alternative_score,
            selected_support=selected_support,
            selected_score=selected_score,
        ):
            replacements[frame] = alternative
    if not replacements:
        return tracks
    return tuple(
        BallTrack(
            track.track_id,
            [
                replacements.get(point.source_frame, point)
                for point in track.points
            ],
        )
        for track in tracks
    )


def _attention_advantage_is_decisive(
    *,
    alternative_support: int,
    alternative_score: float,
    selected_support: int,
    selected_score: float,
) -> bool:
    return (
        alternative_support >= selected_support + 3
        and alternative_score >= selected_score + 0.75
    )


def _restore_plausible_detector_points(
    tracks: Iterable[BallTrack],
    *,
    detector_candidates: Iterable[_BallCandidate],
    frame_step: int,
    fps: float,
    max_speed_pixels_per_second: float,
    cell_size: int = 20,
    supported_foot_points: frozenset[BallPoint] = frozenset(),
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    if not tracks:
        return tracks
    detector_candidates = tuple(detector_candidates)
    anchored_cells = _player_anchored_cells(
        detector_candidates,
        cell_size=cell_size,
    )
    trusted = sorted(
        (point for track in tracks for point in track.points),
        key=lambda point: point.source_frame,
    )
    trusted_frames = {point.source_frame for point in trusted}
    trusted_cell_counts = Counter(
        _cell(point, cell_size)
        for point in trusted
        if point.source_attribution == "yolo26_observed"
    )
    confirmed_anchor_cells = {
        cell
        for cell, count in trusted_cell_counts.items()
        if count >= 3 and cell in anchored_cells
    }
    candidates_by_frame: dict[int, list[_BallCandidate]] = defaultdict(list)
    for candidate in detector_candidates:
        candidates_by_frame[candidate.point.source_frame].append(candidate)
    missing_anchored_frames: dict[tuple[int, int], set[int]] = defaultdict(set)
    for source_frame, candidates in candidates_by_frame.items():
        for candidate in candidates:
            cell = _cell(candidate.point, cell_size)
            if cell in anchored_cells:
                missing_anchored_frames[cell].add(source_frame)
    restored: list[BallPoint] = []
    for source_frame in sorted(candidates_by_frame):
        candidates = candidates_by_frame[source_frame]
        existing = next(
            (
                point
                for point in trusted
                if point.source_frame == source_frame
            ),
            None,
        )
        if existing is not None:
            continue
        repeated_anchored = [
            candidate
            for candidate in candidates
            if len(
                missing_anchored_frames[
                    _cell(candidate.point, cell_size)
                ]
            )
            >= 2
            and _cell(candidate.point, cell_size) in confirmed_anchor_cells
        ]
        if len(repeated_anchored) == 1:
            candidate = repeated_anchored[0].point
        elif len(candidates) == 1:
            candidate = candidates[0].point
            if not _has_local_restoration_support(
                candidate,
                trusted=trusted,
                frame_step=frame_step,
            ):
                continue
            if not _point_path_is_plausible(
                    candidate,
                    trusted=trusted,
                    frame_step=frame_step,
                    fps=fps,
                    max_speed_pixels_per_second=max_speed_pixels_per_second,
                ):
                continue
        else:
            continue
        candidate = replace(
            candidate,
            evidence="trajectory_validated_detector",
            source_attribution="temporal_detector_observed",
        )
        restored.append(candidate)
    if not restored:
        return tracks
    return (
        BallTrack(
            tracks[0].track_id,
            sorted(
                [*tracks[0].points, *restored],
                key=lambda point: point.source_frame,
            ),
        ),
        *tracks[1:],
    )


def _has_local_restoration_support(
    point: BallPoint,
    *,
    trusted: list[BallPoint],
    frame_step: int,
) -> bool:
    if any(
        abs(candidate.source_frame - point.source_frame) <= frame_step
        for candidate in trusted
    ):
        return True
    has_previous = any(
        0 < point.source_frame - candidate.source_frame <= frame_step * 4
        for candidate in trusted
    )
    has_following = any(
        0 < candidate.source_frame - point.source_frame <= frame_step * 4
        for candidate in trusted
    )
    return has_previous and has_following


def _has_bracketed_restoration_support(
    point: BallPoint,
    *,
    trusted: list[BallPoint],
    frame_step: int,
) -> bool:
    return any(
        0 < point.source_frame - candidate.source_frame <= frame_step * 4
        for candidate in trusted
    ) and any(
        0 < candidate.source_frame - point.source_frame <= frame_step * 4
        for candidate in trusted
    )


def _associate_tracks(
    points: Iterable[BallPoint],
    *,
    max_gap_seconds: float,
    max_speed_pixels_per_second: float,
) -> tuple[BallTrack, ...]:
    by_frame: dict[int, list[BallPoint]] = {}
    for point in points:
        by_frame.setdefault(point.source_frame, []).append(point)

    tracks: list[BallTrack] = []
    next_track_id = 1
    for frame_points in by_frame.values():
        timestamp = frame_points[0].clip_seconds
        active = [
            track
            for track in tracks
            if timestamp - track.last.clip_seconds <= max_gap_seconds
        ]
        pairs: list[tuple[float, int, int]] = []
        for track_index, track in enumerate(active):
            predicted_x, predicted_y = track.predicted_center(timestamp)
            elapsed = timestamp - track.last.clip_seconds
            max_distance = max(35.0, max_speed_pixels_per_second * elapsed)
            for point_index, point in enumerate(frame_points):
                distance = hypot(point.x - predicted_x, point.y - predicted_y)
                if distance <= max_distance:
                    pairs.append((distance, track_index, point_index))

        assigned_tracks: set[int] = set()
        assigned_points: set[int] = set()
        for _, track_index, point_index in sorted(pairs):
            if track_index in assigned_tracks or point_index in assigned_points:
                continue
            active[track_index].points.append(frame_points[point_index])
            assigned_tracks.add(track_index)
            assigned_points.add(point_index)

        for point_index, point in enumerate(frame_points):
            if point_index not in assigned_points:
                tracks.append(BallTrack(next_track_id, [point]))
                next_track_id += 1
    return tuple(tracks)


def interpolate_track_gaps(
    track: BallTrack,
    *,
    frame_step: int,
    fps: float,
    maximum_gap_seconds: float,
) -> BallTrack:
    if frame_step < 1 or fps <= 0 or maximum_gap_seconds <= 0:
        raise ValueError("Interpolation frame step, FPS, and gap must be positive")
    ordered = sorted(track.points, key=lambda point: point.source_frame)
    if len(ordered) < 2:
        return BallTrack(track.track_id, ordered)
    points: list[BallPoint] = []
    for index, (first, second) in enumerate(zip(ordered, ordered[1:])):
        points.append(first)
        frame_gap = second.source_frame - first.source_frame
        time_gap = second.clip_seconds - first.clip_seconds
        if frame_gap <= frame_step or time_gap > maximum_gap_seconds + 1e-6:
            continue
        if index > 0:
            previous = ordered[index - 1]
            incoming_x = first.x - previous.x
            incoming_y = first.y - previous.y
            bridge_x = second.x - first.x
            bridge_y = second.y - first.y
            if incoming_x * bridge_x + incoming_y * bridge_y <= 0:
                continue
        for source_frame in range(
            first.source_frame + frame_step,
            second.source_frame,
            frame_step,
        ):
            alpha = (source_frame - first.source_frame) / frame_gap
            points.append(
                BallPoint(
                    source_frame=source_frame,
                    clip_seconds=round(
                        first.clip_seconds
                        + (source_frame - first.source_frame) / fps,
                        3,
                    ),
                    confidence=round(
                        min(first.confidence, second.confidence) * 0.75,
                        6,
                    ),
                    x=first.x + (second.x - first.x) * alpha,
                    y=first.y + (second.y - first.y) * alpha,
                    interpolated=True,
                    evidence="interpolated",
                    source_attribution="interpolated",
                )
            )
    points.append(ordered[-1])
    return BallTrack(track.track_id, sorted(points, key=lambda point: point.source_frame))
