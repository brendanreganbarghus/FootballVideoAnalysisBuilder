from __future__ import annotations

from .settings import *  # noqa: F401,F403

def _discard_unsupported_detector_outliers(
    tracks: Iterable[BallTrack],
    *,
    records: list[dict[str, Any]],
    video: Path,
    fps: float,
    frame_step: int,
    max_gap_seconds: float,
    max_speed_pixels_per_second: float,
) -> tuple[tuple[BallTrack, ...], frozenset[int]]:
    tracks = tuple(tracks)
    if not tracks:
        return tracks, frozenset()
    records_by_frame = {
        int(record["source_frame"]): record for record in records
    }
    grayscale = _read_sampled_grayscale_frames(
        video,
        sorted(records_by_frame),
    )
    maximum_gap = (
        frame_step
        * int(
            SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                "maximum_neighbor_gap_frames"
            ]
        )
    )
    filtered: list[BallTrack] = []
    rejected_frames: set[int] = set()
    for track in tracks:
        points = sorted(track.points, key=lambda point: point.source_frame)
        retained: list[BallPoint] = []
        for index, point in enumerate(points):
            if (
                index == 0
                or index == len(points) - 1
                or point.source_attribution != "yolo26_observed"
            ):
                retained.append(point)
                continue
            previous = points[index - 1]
            following = points[index + 1]
            if (
                point.source_frame - previous.source_frame > maximum_gap
                or following.source_frame - point.source_frame > maximum_gap
            ):
                retained.append(point)
                continue
            frame_span = following.source_frame - previous.source_frame
            if frame_span <= 0:
                retained.append(point)
                continue
            alpha = (
                point.source_frame - previous.source_frame
            ) / frame_span
            expected_x = previous.x + (following.x - previous.x) * alpha
            expected_y = previous.y + (following.y - previous.y) * alpha
            path_error = hypot(
                point.x - expected_x,
                point.y - expected_y,
            )
            minimum_error = max(
                float(
                    SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                        "minimum_path_error_pixels"
                    ]
                ),
                point.box_diagonal
                * float(
                    SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                        "minimum_path_error_ball_diameters"
                    ]
                ),
            )
            if path_error < minimum_error:
                retained.append(point)
                continue
            frame = records_by_frame.get(point.source_frame)
            before = grayscale.get(point.source_frame - frame_step)
            current = grayscale.get(point.source_frame)
            after = grayscale.get(point.source_frame + frame_step)
            if (
                frame is None
                or before is None
                or current is None
                or after is None
            ):
                retained.append(point)
                continue
            if _detector_point_visual_support(
                point,
                records_by_frame=records_by_frame,
                grayscale=grayscale,
                frame_step=frame_step,
            ) >= float(
                SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                    "minimum_outlier_visual_support"
                ]
            ):
                retained.append(point)
            else:
                rejected_frames.add(point.source_frame)
        changed = True
        while changed:
            changed = False
            for first, second in zip(retained, retained[1:]):
                elapsed = (
                    second.source_frame - first.source_frame
                ) / fps
                if elapsed <= 0:
                    continue
                speed = hypot(
                    second.x - first.x,
                    second.y - first.y,
                ) / elapsed
                if speed <= max_speed_pixels_per_second:
                    continue
                first_support = _detector_point_visual_support(
                    first,
                    records_by_frame=records_by_frame,
                    grayscale=grayscale,
                    frame_step=frame_step,
                )
                second_support = _detector_point_visual_support(
                    second,
                    records_by_frame=records_by_frame,
                    grayscale=grayscale,
                    frame_step=frame_step,
                )
                support_margin = abs(first_support - second_support)
                if support_margin < float(
                    SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                        "minimum_conflict_support_margin"
                    ]
                ):
                    continue
                rejected = (
                    first
                    if first_support < second_support
                    else second
                )
                retained.remove(rejected)
                rejected_frames.add(rejected.source_frame)
                changed = True
                break
        if len(retained) >= 2:
            terminal = retained[-1]
            previous = retained[-2]
            terminal_gap = (
                terminal.source_frame - previous.source_frame
            ) / fps
            if (
                terminal_gap > max_gap_seconds
                and _detector_point_visual_support(
                    terminal,
                    records_by_frame=records_by_frame,
                    grayscale=grayscale,
                    frame_step=frame_step,
                )
                < float(
                    SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
                        "terminal_minimum_support"
                    ]
                )
            ):
                retained.pop()
                rejected_frames.add(terminal.source_frame)
        filtered.append(BallTrack(track.track_id, retained))
    return tuple(filtered), frozenset(rejected_frames)


def _detector_point_visual_support(
    point: BallPoint,
    *,
    records_by_frame: dict[int, dict[str, Any]],
    grayscale: dict[int, np.ndarray],
    frame_step: int,
) -> float:
    frame = records_by_frame.get(point.source_frame)
    before = grayscale.get(point.source_frame - frame_step)
    current = grayscale.get(point.source_frame)
    after = grayscale.get(point.source_frame + frame_step)
    if frame is None or before is None or current is None or after is None:
        return 0.0
    appearance_score = _adjacent_appearance_consistency(
        before,
        current,
        after,
        point,
        reference_diameter=max(1.0, point.box_diagonal),
    )
    cones = _player_attention_cones(
        before,
        current,
        after,
        frame,
    )
    _, attention_score = _attention_convergence(point, cones)
    return appearance_score + attention_score


def _add_bracketed_outlier_motion_recoveries(
    tracks: Iterable[BallTrack],
    *,
    records: list[dict[str, Any]],
    video: Path,
    width: int,
    height: int,
    fps: float,
    frame_step: int,
    rejected_frames: frozenset[int],
    max_speed_pixels_per_second: float,
) -> tuple[BallTrack, ...]:
    tracks = tuple(tracks)
    if not tracks:
        return tracks
    trusted = sorted(
        (point for track in tracks for point in track.points),
        key=lambda point: point.source_frame,
    )
    trusted_by_frame = {
        point.source_frame: point for point in trusted
    }
    recoverable_frames = {
        source_frame
        for source_frame in rejected_frames
        if source_frame - frame_step in trusted_by_frame
        and source_frame + frame_step in trusted_by_frame
    }
    records_by_frame = {
        int(record["source_frame"]): record for record in records
    }
    grayscale = _read_sampled_grayscale_frames(
        video,
        sorted(records_by_frame),
    )
    additions: list[BallPoint] = []
    for source_frame in sorted(recoverable_frames):
        local_diameter = median(
            (
                trusted_by_frame[source_frame - frame_step].box_diagonal,
                trusted_by_frame[source_frame + frame_step].box_diagonal,
            )
        )
        record = records_by_frame[source_frame]
        proposals, _ = _raw_motion_frame_proposals(
            previous=grayscale[source_frame - frame_step],
            current=grayscale[source_frame],
            following=grayscale[source_frame + frame_step],
            record=record,
            source_frame=source_frame,
            clip_seconds=float(record["clip_seconds"]),
            width=width,
            height=height,
            reference_diameter=local_diameter,
            trusted=trusted,
            frame_step=frame_step,
        )
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
            and _point_path_is_plausible(
                proposal.point,
                trusted=trusted,
                frame_step=frame_step,
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            )
        ]
        if len(corridor) == 1:
            additions.append(corridor[0].point)
    if not additions:
        enriched = tracks
    else:
        enriched = (
            BallTrack(
                tracks[0].track_id,
                sorted(
                    [*tracks[0].points, *additions],
                    key=lambda point: point.source_frame,
                ),
            ),
            *tracks[1:],
        )
    return _add_endpoint_bounded_short_motion_bridges(
        enriched,
        records_by_frame=records_by_frame,
        grayscale=grayscale,
        width=width,
        height=height,
        fps=fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )


def _replace_low_confidence_global_fallback_outliers(
    tracks: Iterable[BallTrack],
    *,
    video: Path,
    model_path: Path | None = None,
    model: Any | None = None,
) -> tuple[BallTrack, ...]:
    maximum_confidence = float(
        SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
            "global_fallback_outlier_maximum_confidence"
        ]
    )
    minimum_path_error_diameters = float(
        SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
            "global_fallback_outlier_minimum_path_error_ball_diameters"
        ]
    )
    weak_detector_maximum_confidence = float(
        FOCUSED_MULTISCALE_REDETECTION_PROFILE[
            "weak_detector_maximum_confidence"
        ]
    )
    weak_detector_minimum_path_error_diameters = float(
        FOCUSED_MULTISCALE_REDETECTION_PROFILE[
            "weak_detector_minimum_path_error_ball_diameters"
        ]
    )
    suspect_frames: set[int] = set()
    for track in tracks:
        points = sorted(track.points, key=lambda point: point.source_frame)
        for index, point in enumerate(points):
            if index == 0 or index == len(points) - 1:
                continue
            previous = points[index - 1]
            following = points[index + 1]
            frame_span = following.source_frame - previous.source_frame
            if frame_span <= 0:
                continue
            alpha = (
                point.source_frame - previous.source_frame
            ) / frame_span
            expected_x = previous.x + (following.x - previous.x) * alpha
            expected_y = previous.y + (following.y - previous.y) * alpha
            reference_diameter = max(point.box_diagonal, 1.0)
            path_error_diameters = (
                hypot(point.x - expected_x, point.y - expected_y)
                / reference_diameter
            )
            unstable_global_fallback = (
                point.evidence == "raw_motion_global_fallback"
                and point.confidence < maximum_confidence
                and path_error_diameters > minimum_path_error_diameters
            )
            unstable_weak_detector = (
                point.evidence == "detector"
                and point.confidence < weak_detector_maximum_confidence
                and path_error_diameters
                > weak_detector_minimum_path_error_diameters
            )
            if unstable_global_fallback or unstable_weak_detector:
                suspect_frames.add(point.source_frame)
    if not suspect_frames or (model is None and model_path is None):
        return tuple(tracks)

    required_frames = set(suspect_frames)
    for track in tracks:
        points = sorted(track.points, key=lambda point: point.source_frame)
        for point in points:
            if point.source_frame in suspect_frames:
                continue
            if any(
                abs(point.source_frame - target_frame) <= 25
                for target_frame in suspect_frames
            ):
                required_frames.add(point.source_frame)
    color_frames = _read_sampled_color_frames(video, sorted(required_frames))
    if model is None:
        from ultralytics import YOLO

        model = YOLO(str(model_path))
    replaced: list[BallTrack] = []
    for track in tracks:
        points = sorted(track.points, key=lambda point: point.source_frame)
        reliable = [
            point for point in points if point.source_frame not in suspect_frames
        ]
        output: list[BallPoint] = []
        for point in points:
            if point.source_frame not in suspect_frames:
                output.append(point)
                continue
            previous = [
                candidate
                for candidate in reliable
                if candidate.source_frame < point.source_frame
            ]
            following = [
                candidate
                for candidate in reliable
                if candidate.source_frame > point.source_frame
            ]
            if not previous or not following:
                continue
            first = previous[-1]
            second = following[0]
            alpha = (
                point.source_frame - first.source_frame
            ) / (second.source_frame - first.source_frame)
            expected_x = first.x + (second.x - first.x) * alpha
            expected_y = first.y + (second.y - first.y) * alpha
            reference_diameters = [
                candidate.box_diagonal
                for candidate in reliable
                if candidate.box_diagonal > 0
                and abs(candidate.source_frame - point.source_frame) <= 25
            ]
            replacement = _focused_multiscale_ball_reacquisition(
                model=model,
                frame=color_frames.get(point.source_frame),
                source_frame=point.source_frame,
                clip_seconds=point.clip_seconds,
                expected_x=expected_x,
                expected_y=expected_y,
                reference_diameter=(
                    median(reference_diameters)
                    if reference_diameters
                    else 0.0
                ),
            )
            original_path_error = hypot(
                point.x - expected_x,
                point.y - expected_y,
            )
            replacement_path_error = (
                hypot(
                    replacement.x - expected_x,
                    replacement.y - expected_y,
                )
                if replacement is not None
                else float("inf")
            )
            if (
                replacement is not None
                and replacement_path_error
                <= original_path_error
                * float(
                    FOCUSED_MULTISCALE_REDETECTION_PROFILE[
                        "maximum_path_error_ratio"
                    ]
                )
            ):
                output.append(replacement)
            else:
                output.append(point)
        replaced.append(
            BallTrack(
                track.track_id,
                sorted(output, key=lambda candidate: candidate.source_frame),
            )
        )
    return tuple(replaced)


def _recover_focused_multiscale_points(
    tracks: Iterable[BallTrack],
    *,
    records: Iterable[dict[str, Any]],
    video: Path,
    model_path: Path,
    fps: float,
    frame_step: int,
) -> tuple[BallTrack, ...]:
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    recovered = tuple(tracks)
    for _ in range(
        int(
            FOCUSED_MULTISCALE_REDETECTION_PROFILE[
                "maximum_recovery_iterations"
            ]
        )
    ):
        updated = _replace_low_confidence_global_fallback_outliers(
            recovered,
            video=video,
            model=model,
        )
        if _track_point_signatures(updated) == _track_point_signatures(recovered):
            break
        recovered = updated
    recovered = _add_focused_multiscale_missing_points(
        recovered,
        records=records,
        video=video,
        model=model,
        fps=fps,
        frame_step=frame_step,
    )
    return _add_focused_multiscale_terminal_points(
        recovered,
        records=records,
        video=video,
        model=model,
        fps=fps,
    )
