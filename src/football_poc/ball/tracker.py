from __future__ import annotations

from .settings import *  # noqa: F401,F403

def track_cached_balls(
    *,
    manifest_path: Path,
    cache_path: Path,
    output: Path,
    static_cell_size: int = 20,
    static_occupancy: float = 0.25,
    max_gap_seconds: float = 0.56,
    max_speed_pixels_per_second: float = 1600.0,
    minimum_track_points: int = 3,
    analysis_start_seconds: float | None = None,
    analysis_end_seconds: float | None = None,
    reuse_decoded_frame_cache: bool = False,
) -> Path:
    manifest = BenchmarkManifest.load(manifest_path)
    metadata, records = _load_cache(cache_path, manifest.sha256)
    if metadata.get("detection_scope") == "ball_only":
        raise ValueError(
            "Ball-only detection caches cannot run the production ball tracker "
            "because player context is required. Rerun YOLO without --ball-only."
        )
    records = _records_in_analysis_window(
        records,
        start_seconds=analysis_start_seconds,
        end_seconds=analysis_end_seconds,
    )
    frame_store = _SampledGrayscaleFrameStore(
        video=manifest.video,
        source_frames=sorted(
            {int(record["source_frame"]) for record in records}
        ),
        output=output,
        reuse=reuse_decoded_frame_cache,
    )
    global _ACTIVE_GRAYSCALE_FRAME_STORE
    previous_store = _ACTIVE_GRAYSCALE_FRAME_STORE
    succeeded = False
    try:
        frame_store.open()
        _ACTIVE_GRAYSCALE_FRAME_STORE = frame_store
        result = _track_cached_balls_impl(
            manifest_path=manifest_path,
            cache_path=cache_path,
            output=output,
            static_cell_size=static_cell_size,
            static_occupancy=static_occupancy,
            max_gap_seconds=max_gap_seconds,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
            minimum_track_points=minimum_track_points,
            analysis_start_seconds=analysis_start_seconds,
            analysis_end_seconds=analysis_end_seconds,
        )
        succeeded = True
        return result
    finally:
        _ACTIVE_GRAYSCALE_FRAME_STORE = previous_store
        frame_store.close(delete_cache=succeeded)


def _ledger_from_records(records: Iterable[dict[str, Any]]) -> FrameLedger:
    return FrameLedger(
        (
            int(record["source_frame"]),
            float(record["clip_seconds"]),
        )
        for record in records
    )


def _single_track_from_ledger(ledger: FrameLedger) -> tuple[BallTrack, ...]:
    return ledger.to_tracks()


def _proposal_allowed_by_confirmed_neighbours(
    ledger: FrameLedger,
    point: BallPoint,
    *,
    fps: float,
    max_speed_pixels_per_second: float,
) -> bool:
    confirmed = sorted(
        ledger.confirmed_entries(),
        key=lambda entry: entry.source_frame,
    )
    previous = next(
        (
            entry
            for entry in reversed(confirmed)
            if entry.source_frame < point.source_frame
        ),
        None,
    )
    following = next(
        (
            entry
            for entry in confirmed
            if entry.source_frame > point.source_frame
        ),
        None,
    )
    if _leaves_resting_ball(
        point.x,
        point.y,
        point.source_frame,
        previous=previous,
        following=following,
        fps=fps,
    ):
        return False
    for anchor in (previous, following):
        if anchor is None:
            continue
        elapsed = abs(point.source_frame - anchor.source_frame) / fps
        if elapsed <= 0:
            return False
        speed = hypot(point.x - float(anchor.x), point.y - float(anchor.y)) / elapsed
        if speed > max_speed_pixels_per_second * 1.25:
            return False
    return previous is not None or following is not None


def _is_weak_feet_proposal(point: BallPoint, record: dict[str, Any]) -> bool:
    return point.confidence < BALL_COLOUR_WEAK_CONFIDENCE and _near_player_feet(
        point, record
    )


def _confirm_track_points_from_module(
    ledger: FrameLedger,
    module: str,
    tracks: Iterable[BallTrack],
    *,
    records_by_frame: dict[int, dict[str, Any]],
    fps: float,
    max_speed_pixels_per_second: float,
    ball_colour_matches: Any = None,
) -> FrameLedger:
    proposed_by_frame: dict[int, BallPoint] = {}
    for track in tracks:
        for point in track.points:
            if ledger.confirmed(point.source_frame) is not None:
                continue
            current = proposed_by_frame.get(point.source_frame)
            if current is None or point.confidence > current.confidence:
                proposed_by_frame[point.source_frame] = point
    for frame in ledger.unresolved_frames():
        point = proposed_by_frame.get(frame)
        if point is None:
            ledger.reject(frame, module, "module_found_no_candidate")
            continue
        record = records_by_frame.get(frame, {})
        if _inside_player_upper_body(point, record) and not point.smooth_gap_path:
            ledger.reject(frame, module, "candidate_inside_player_upper_body")
            continue
        if (
            ball_colour_matches is not None
            and not point.smooth_gap_path
            and _is_weak_feet_proposal(point, record)
            and not ball_colour_matches(point)
        ):
            ledger.reject(frame, module, "colour_differs_from_ball")
            continue
        if not _proposal_allowed_by_confirmed_neighbours(
            ledger,
            point,
            fps=fps,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        ):
            ledger.reject(frame, module, "candidate_fails_confirmed_neighbour_gate")
            continue
        ledger.confirm(
            frame,
            x=point.x,
            y=point.y,
            confirming_module=module,
            evidence={
                "proposal_evidence": point.evidence,
                "proposal_source_attribution": point.source_attribution,
            },
            confidence=point.confidence,
            clip_seconds=point.clip_seconds,
            box_diagonal=point.box_diagonal,
            point_evidence=point.evidence,
            point_source_attribution=point.source_attribution,
            temporal_score=point.temporal_score,
        )
    return ledger


def _withdraw_off_path_attention_fallbacks(ledger: FrameLedger, module: str) -> None:
    # Attention convergence points at the players, not the ball. When both
    # confirmed neighbours are close in time and the point sits far off the
    # straight path between them, the module takes it back so later steps
    # can fill the frame from the neighbours.
    maximum_bracket_frames = int(
        SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
            "global_fallback_outlier_maximum_bracket_frames"
        ]
    )
    minimum_path_error_diameters = float(
        SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
            "global_fallback_outlier_minimum_path_error_ball_diameters"
        ]
    )
    points = sorted(
        ledger.confirmed_points(), key=lambda point: point.source_frame
    )
    off_path: list[int] = []
    for index in range(1, len(points) - 1):
        point = points[index]
        if (
            point.confirming_module != module
            or point.evidence
            != "raw_motion_attention_convergence_global_fallback"
        ):
            continue
        previous = points[index - 1]
        following = points[index + 1]
        span = following.source_frame - previous.source_frame
        if span <= 0 or span > maximum_bracket_frames:
            continue
        alpha = (point.source_frame - previous.source_frame) / span
        expected_x = previous.x + (following.x - previous.x) * alpha
        expected_y = previous.y + (following.y - previous.y) * alpha
        path_error = hypot(point.x - expected_x, point.y - expected_y)
        if path_error / max(point.box_diagonal, 1.0) > minimum_path_error_diameters:
            off_path.append(point.source_frame)
    for frame in off_path:
        ledger.withdraw(frame, module, "attention_fallback_off_neighbour_path")


# A motion point is only a moving blob, often a player's boot. When trusted
# detector runs bracket it on both sides and it sits far off the straight path
# between them, the boot moved and the ball did not, so the module takes it
# back. The time machine then fills the frame from the detector sightings
# instead of anchoring the gap on the boot.
MOTION_OFF_PATH_BRACKET_STEPS = 16


def _withdraw_off_path_motion_points(
    ledger: FrameLedger, module: str, frame_step: int
) -> None:
    if frame_step < 1:
        return
    minimum_path_error_diameters = float(
        SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
            "global_fallback_outlier_minimum_path_error_ball_diameters"
        ]
    )
    maximum_span = MOTION_OFF_PATH_BRACKET_STEPS * frame_step
    points = sorted(
        ledger.confirmed_points(), key=lambda point: point.source_frame
    )
    by_frame = {point.source_frame: point for point in points}
    off_path: list[int] = []
    for index in range(1, len(points) - 1):
        point = points[index]
        if point.confirming_module != module:
            continue
        previous = points[index - 1]
        following = points[index + 1]
        span = following.source_frame - previous.source_frame
        if span <= 0 or span > maximum_span:
            continue
        if not (
            _detector_backed(
                by_frame, previous.source_frame,
                frame_step=frame_step, direction=-1,
            )
            and _detector_backed(
                by_frame, following.source_frame,
                frame_step=frame_step, direction=1,
            )
        ):
            continue
        alpha = (point.source_frame - previous.source_frame) / span
        expected_x = previous.x + (following.x - previous.x) * alpha
        expected_y = previous.y + (following.y - previous.y) * alpha
        path_error = hypot(point.x - expected_x, point.y - expected_y)
        if path_error / max(point.box_diagonal, 1.0) > minimum_path_error_diameters:
            off_path.append(point.source_frame)
    for frame in off_path:
        ledger.withdraw(frame, module, "motion_off_detector_neighbour_path")


# A short run of weak detector sightings (often a boot) is taken back when it
# sits far off both the straight path between trusted detector runs on either
# side and the path between its immediate confirmed neighbours, and a trusted
# run has a stronger sighting. Checking the immediate neighbours too keeps a
# ball that turned during a long gap between the trusted runs.
WEAK_DETECTOR_OFF_PATH_MAX_RUN = 2


def _withdraw_off_path_weak_detector_runs(
    ledger: FrameLedger, frame_step: int
) -> None:
    if frame_step < 1:
        return
    minimum_path_error_diameters = float(
        SOCCERTRACK_TRAJECTORY_OUTLIER_PROFILE[
            "global_fallback_outlier_minimum_path_error_ball_diameters"
        ]
    )
    detector_modules = {CONFIRM_YOLO_MODULE, LOCK_YOLO_CHAIN_MODULE}
    by_frame = {point.source_frame: point for point in ledger.confirmed_points()}

    def is_detector(frame: int) -> bool:
        point = by_frame.get(frame)
        return point is not None and point.confirming_module in detector_modules

    def anchor(frame: int, direction: int) -> int | None:
        for offset in range(1, MOTION_OFF_PATH_BRACKET_STEPS + 1):
            candidate = frame + direction * offset * frame_step
            if _detector_backed(
                by_frame, candidate, frame_step=frame_step, direction=direction
            ):
                return candidate
        return None

    def strongest_in_run(frame: int, direction: int) -> float:
        return max(
            float(by_frame[frame + direction * step * frame_step].confidence or 0.0)
            for step in range(DETECTOR_BACKED_RUN_LENGTH)
        )

    off_path: list[int] = []
    for frame in sorted(by_frame):
        point = by_frame[frame]
        if point.confirming_module != CONFIRM_YOLO_MODULE or is_detector(
            frame - frame_step
        ):
            continue
        run = [frame]
        while is_detector(run[-1] + frame_step):
            run.append(run[-1] + frame_step)
        if len(run) > WEAK_DETECTOR_OFF_PATH_MAX_RUN or any(
            by_frame[member].confirming_module != CONFIRM_YOLO_MODULE
            for member in run
        ):
            continue
        previous_frame = anchor(run[0], -1)
        following_frame = anchor(run[-1], 1)
        if previous_frame is None or following_frame is None:
            continue
        strongest_member = max(
            float(by_frame[member].confidence or 0.0) for member in run
        )
        if not (
            strongest_in_run(previous_frame, -1) > strongest_member
            or strongest_in_run(following_frame, 1) > strongest_member
        ):
            continue
        neighbours = sorted(by_frame)
        before = [f for f in neighbours if f < run[0]]
        after = [f for f in neighbours if f > run[-1]]
        if not before or not after:
            continue

        def path_errors(start: int, end: int) -> list[float]:
            first, last = by_frame[start], by_frame[end]
            errors = []
            for member in run:
                alpha = (member - start) / (end - start)
                expected_x = first.x + (last.x - first.x) * alpha
                expected_y = first.y + (last.y - first.y) * alpha
                errors.append(
                    hypot(by_frame[member].x - expected_x, by_frame[member].y - expected_y)
                    / max(by_frame[member].box_diagonal, 1.0)
                )
            return errors

        if min(
            path_errors(previous_frame, following_frame)
            + path_errors(before[-1], after[0])
        ) > minimum_path_error_diameters:
            off_path.extend(run)
    for frame in off_path:
        ledger.withdraw(frame, CONFIRM_YOLO_MODULE, "weak_detector_run_off_trusted_path")


# A short island of points cut off from the rest of the track by at least a
# second without any point (or by the clip edge) has nothing outside it to
# confirm it. Without a detector-backed run inside, its sightings are lone
# weak boxes (often a boot) plus searches seeded from them, so the island is
# taken back and the frames are left honestly empty.
ISOLATED_ISLAND_MINIMUM_GAP_SECONDS = 1.0


def _withdraw_isolated_unbacked_islands(
    ledger: FrameLedger, *, fps: float, frame_step: int
) -> None:
    if fps <= 0 or frame_step < 1:
        return
    minimum_gap_samples = max(
        1, int(-(-ISOLATED_ISLAND_MINIMUM_GAP_SECONDS * fps // frame_step))
    )
    by_frame = {point.source_frame: point for point in ledger.confirmed_points()}
    sampled = sorted(ledger.entries)
    islands: list[list[int]] = []
    current: list[int] = []
    empty_run = minimum_gap_samples
    for frame in sampled:
        if frame not in by_frame:
            empty_run += 1
            continue
        if current and empty_run >= minimum_gap_samples:
            islands.append(current)
            current = []
        current.append(frame)
        empty_run = 0
    if current:
        islands.append(current)
    for island in islands:
        if any(
            _detector_backed(by_frame, frame, frame_step=frame_step, direction=1)
            for frame in island
        ):
            continue
        for frame in island:
            ledger.withdraw(
                frame,
                by_frame[frame].confirming_module,
                "isolated_island_without_detector_run",
            )


# A moving ball cannot nearly stop for one sample and then speed off again in
# the next. A flipbook pick whose arrival step is far shorter than both the
# step before and the step after, while the ball moves fast on both sides,
# is a slower object (a boot) the ball passed, so the module takes it back.
STALL_STEP_FRACTION = 0.35
STALL_MINIMUM_NEIGHBOUR_SPEED_PIXELS_PER_FRAME = 6.0


def _withdraw_stalled_flipbook_picks(ledger: FrameLedger, frame_step: int) -> None:
    if frame_step < 1:
        return
    confirmed = {point.source_frame: point for point in ledger.confirmed_points()}

    def step(a: BallPoint, b: BallPoint) -> float:
        return hypot(b.x - a.x, b.y - a.y) / (b.source_frame - a.source_frame)

    stalled: list[int] = []
    for frame, point in confirmed.items():
        if point.confirming_module != FLIPBOOK_MODULE:
            continue
        previous = confirmed.get(frame - frame_step)
        earlier = confirmed.get(frame - 2 * frame_step)
        following = confirmed.get(frame + frame_step)
        if previous is None or earlier is None or following is None:
            continue
        neighbours = min(step(earlier, previous), step(point, following))
        if (
            neighbours >= STALL_MINIMUM_NEIGHBOUR_SPEED_PIXELS_PER_FRAME
            and step(previous, point) < STALL_STEP_FRACTION * neighbours
        ):
            stalled.append(frame)
    for frame in stalled:
        ledger.withdraw(frame, FLIPBOOK_MODULE, "stalled_between_fast_steps")


def _run_motion_and_optical_flow_module(
    ledger: FrameLedger,
    *,
    records: list[dict[str, Any]],
    video: Path,
    width: int,
    height: int,
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
    detector_candidates: list[BallPoint],
) -> tuple[FrameLedger, _RawMotionDiagnostics, _DenseFlowDiagnostics]:
    tracks = _single_track_from_ledger(ledger)
    tracks, raw_motion_diagnostics = _add_raw_motion_proposals(
        tracks,
        records=records,
        video=video,
        width=width,
        height=height,
        fps=fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        detector_candidates=detector_candidates,
    )
    tracks, kalman_diagnostics = _add_kalman_guided_reacquisitions(
        tracks,
        detector_candidates=detector_candidates,
        records=records,
        video=video,
        width=width,
        height=height,
        fps=fps,
        frame_step=frame_step,
    )
    tracks, dense_flow_diagnostics = _add_dense_optical_flow_bridges(
        tracks,
        records=records,
        video=video,
        width=width,
        height=height,
        fps=fps,
        frame_step=frame_step,
    )
    ledger = _confirm_track_points_from_module(
        ledger,
        "03_motion_and_optical_flow",
        tracks,
        records_by_frame={int(record["source_frame"]): record for record in records},
        fps=fps,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    _withdraw_off_path_attention_fallbacks(ledger, "03_motion_and_optical_flow")
    raw_motion_diagnostics = replace(
        raw_motion_diagnostics,
        attention_accepted=(
            raw_motion_diagnostics.attention_accepted
            + kalman_diagnostics.successes
        ),
    )
    return ledger, raw_motion_diagnostics, dense_flow_diagnostics


def _track_cached_balls_impl(
    *,
    manifest_path: Path,
    cache_path: Path,
    output: Path,
    static_cell_size: int = 20,
    static_occupancy: float = 0.25,
    max_gap_seconds: float = 0.56,
    max_speed_pixels_per_second: float = 1600.0,
    minimum_track_points: int = 3,
    analysis_start_seconds: float | None = None,
    analysis_end_seconds: float | None = None,
) -> Path:
    manifest = BenchmarkManifest.load(manifest_path)
    metadata, records = _load_cache(cache_path, manifest.sha256)
    if metadata.get("detection_scope") == "ball_only":
        raise ValueError(
            "Ball-only detection caches cannot run the production ball tracker "
            "because player context is required. Rerun YOLO without --ball-only."
        )
    records = _records_in_analysis_window(
        records,
        start_seconds=analysis_start_seconds,
        end_seconds=analysis_end_seconds,
    )
    _validate_options(
        static_cell_size=static_cell_size,
        static_occupancy=static_occupancy,
        max_gap_seconds=max_gap_seconds,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        minimum_track_points=minimum_track_points,
    )
    width, height = _video_dimensions(manifest.video)
    pitch_candidates = [
        (point, record)
        for record in records
        for point in _ball_points(record)
        if _inside_soccertrack_pitch(point, width, height)
    ]
    behind_player = _balls_continuing_behind_player(
        pitch_candidates,
        fps=manifest.fps,
        frame_step=int(metadata["stride"]),
    )
    candidates = [
        _BallCandidate(
            point=point,
            near_player_feet=_near_player_feet(point, record),
        )
        for point, record in pitch_candidates
        if point in behind_player or _player_context_allows_ball(point, record)
    ]
    static_cells = _static_cells(
        (candidate.point for candidate in candidates),
        frame_count=len(records),
        cell_size=static_cell_size,
        occupancy=static_occupancy,
    ) - _player_anchored_cells(candidates, cell_size=static_cell_size)
    unanchored_static_clusters = _unanchored_static_clusters(
        (
            candidate
            for candidate in candidates
            if not _near_static_cell(
                candidate.point,
                static_cells,
                static_cell_size,
            )
        ),
        cell_size=static_cell_size,
        maximum_continuous_gap_seconds=max_gap_seconds,
    )
    global_static_rejections = sum(
        _near_static_cell(
            candidate.point,
            static_cells,
            static_cell_size,
        )
        for candidate in candidates
    )
    unanchored_static_rejections = sum(
        not _near_static_cell(
            candidate.point,
            static_cells,
            static_cell_size,
        )
        and _near_unanchored_static_cluster(
            candidate.point,
            unanchored_static_clusters,
            cell_size=static_cell_size,
        )
        for candidate in candidates
    )
    filtered_candidate_objects = [
        candidate
        for candidate in candidates
        if not _near_static_cell(
            candidate.point,
            static_cells,
            static_cell_size,
        )
        and not _near_unanchored_static_cluster(
            candidate.point,
            unanchored_static_clusters,
            cell_size=static_cell_size,
        )
    ]
    filtered = [candidate.point for candidate in filtered_candidate_objects]
    filtered_candidate_counts = Counter(
        point.source_frame for point in filtered
    )
    associated_tracks = _associate_tracks(
        filtered,
        max_gap_seconds=max_gap_seconds,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    associated_tracks, discarded_static_fragments = (
        _discard_unanchored_static_fragments(
            associated_tracks,
            candidates,
        )
    )
    foot_supported_points = frozenset(
        candidate.point
        for candidate in candidates
        if candidate.near_player_feet
    )
    supported_tracks = _supported_ball_tracks(
        associated_tracks,
        minimum_track_points=minimum_track_points,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        foot_supported_points=foot_supported_points,
    )
    frame_step = int(metadata["stride"])
    motion_supported_tracks = _add_motion_supported_points(
        supported_tracks,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
        maximum_gap_seconds=max_gap_seconds,
    )
    temporally_supported_tracks = _add_template_supported_points(
        motion_supported_tracks,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
        maximum_gap_seconds=max_gap_seconds,
    )
    selected_tracks = select_single_ball_trajectory(
        temporally_supported_tracks,
        max_gap_seconds=max_gap_seconds,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    supported_foot_points = frozenset(
        point
        for track in supported_tracks
        for point in track.points
        if any(
            candidate.point == point
            and candidate.near_player_feet
            for candidate in candidates
        )
    )
    selected_tracks = _resolve_detector_conflicts_by_attention(
        selected_tracks,
        detector_candidates=filtered_candidate_objects,
        supported_foot_points=supported_foot_points,
        records=records,
        video=manifest.video,
        frame_step=frame_step,
    )
    selected_tracks = _restore_plausible_detector_points(
        selected_tracks,
        detector_candidates=filtered_candidate_objects,
        frame_step=frame_step,
        fps=manifest.fps,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        cell_size=static_cell_size,
        supported_foot_points=foot_supported_points,
    )

    ledger = _ledger_from_records(records)
    records_by_frame = {int(record["source_frame"]): record for record in records}
    candidates_by_frame: dict[int, list[_BallCandidate]] = defaultdict(list)
    for candidate in candidates:
        candidates_by_frame[candidate.point.source_frame].append(candidate)
    selected_detector_points = [
        point
        for track in selected_tracks
        for point in track.points
        if point.source_attribution == "yolo26_observed"
    ]
    ledger = _timed_tracker_call(
        LOCK_YOLO_CHAIN_MODULE,
        _lock_moving_yolo_chains,
        ledger,
        records_by_frame=records_by_frame,
        fps=manifest.fps,
        frame_step=frame_step,
    )
    # 01 decides on its own fresh ledger; its results fill only frames the
    # permanent locks left unresolved.
    yolo_ledger = _timed_tracker_call(
        "01_confirm_yolo",
        _confirm_yolo_detections,
        _ledger_from_records(records),
        selected_detector_points,
        candidates_by_frame=candidates_by_frame,
        records_by_frame=records_by_frame,
        fps=manifest.fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        video=manifest.video,
    )
    ledger = _merge_independent_module(ledger, yolo_ledger, "01_confirm_yolo")
    # 01 judged detours without the chain locks; recheck its merged points
    # now that locked chain neighbours are visible.
    _withdraw_one_frame_detours(
        ledger,
        fps=manifest.fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    ledger = _timed_tracker_call(
        FLIPBOOK_MODULE,
        _confirm_flipbook_time_machine,
        ledger,
        records_by_frame=records_by_frame,
        video=manifest.video,
        model_path=Path(str(metadata["model"])),
        fps=manifest.fps,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    ledger = _timed_tracker_call(
        AERIAL_MODULE,
        _confirm_aerial_flights,
        ledger,
        records_by_frame=records_by_frame,
        video=manifest.video,
        fps=manifest.fps,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    ledger, raw_motion_diagnostics, dense_flow_diagnostics = _timed_tracker_call(
        "03_motion_and_optical_flow",
        _run_motion_and_optical_flow_module,
        ledger,
        records=records,
        video=manifest.video,
        width=width,
        height=height,
        fps=manifest.fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        detector_candidates=filtered,
    )
    focused_tracks = _recover_focused_multiscale_points(
        _single_track_from_ledger(ledger),
        records=records,
        video=manifest.video,
        model_path=Path(str(metadata["model"])),
        fps=manifest.fps,
        frame_step=frame_step,
    )
    focused_proposals = [
        point
        for track in focused_tracks
        for point in track.points
        if ledger.confirmed(point.source_frame) is None
        and _is_weak_feet_proposal(
            point, records_by_frame.get(point.source_frame, {})
        )
    ]
    ledger = _timed_tracker_call(
        "04_focused_multiscale",
        _confirm_track_points_from_module,
        ledger,
        "04_focused_multiscale",
        focused_tracks,
        records_by_frame=records_by_frame,
        fps=manifest.fps,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        ball_colour_matches=(
            _ball_colour_check(
                selected_detector_points,
                focused_proposals,
                manifest.video,
            )
            if focused_proposals
            else None
        ),
    )
    stationary_tracks = _add_short_stationary_template_recoveries(
        _single_track_from_ledger(ledger),
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
    )
    ledger = _timed_tracker_call(
        "05_short_stationary",
        _confirm_track_points_from_module,
        ledger,
        "05_short_stationary",
        stationary_tracks,
        records_by_frame=records_by_frame,
        fps=manifest.fps,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    ledger = _timed_tracker_call(
        "06_time_machine_region_search",
        _confirm_time_machine_region_search,
        ledger,
        records_by_frame=records_by_frame,
        video=manifest.video,
        model_path=Path(str(metadata["model"])),
        fps=manifest.fps,
        width=width,
        height=height,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    # The scenery check needs the whole clip, so it runs after every visual
    # module and before the time machine re-estimates any frame it frees.
    ledger = _timed_tracker_call(
        SCENERY_MODULE,
        _confirm_scenery_check,
        ledger,
        video=manifest.video,
    )
    # Later modules may have filled the neighbours an attention fallback lacked
    # when step 03 judged it, so it is judged again against the final path.
    _withdraw_off_path_attention_fallbacks(ledger, "03_motion_and_optical_flow")
    _withdraw_off_path_motion_points(
        ledger, "03_motion_and_optical_flow", frame_step
    )
    _withdraw_off_path_weak_detector_runs(ledger, frame_step)
    _withdraw_stalled_flipbook_picks(ledger, frame_step)
    _withdraw_isolated_unbacked_islands(ledger, fps=manifest.fps, frame_step=frame_step)
    # The time machine runs last so visual recovery modules see every gap
    # first; it then gives each remaining frame an estimate or possible region.
    ledger = _timed_tracker_call(
        "02_time_machine",
        _confirm_time_machine_estimates,
        ledger,
        fps=manifest.fps,
        frame_step=frame_step,
        width=width,
        height=height,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        place_possible_regions=False,
        video=manifest.video,
        colour_range=_learned_ball_colour_range(
            [point for record in records for point in _ball_points(record)],
            manifest.video,
        ),
        records_by_frame=records_by_frame,
    )
    accepted = _single_track_from_ledger(ledger)
    discarded_temporal_upper_body_points = 0
    final_trajectory_rejections: frozenset[int] = frozenset()

    output.mkdir(parents=True, exist_ok=True)
    track_path = output / "ball-tracks.json"
    track_path.write_text(
        json.dumps(
            {
                "manifest": str(manifest.path),
                "cache": str(cache_path.resolve()),
                "cache_configuration": metadata,
                "analysis_window": _analysis_window(
                    analysis_start_seconds,
                    analysis_end_seconds,
                ),
                "static_cells": [
                    {"x": x * static_cell_size, "y": y * static_cell_size}
                    for x, y in sorted(static_cells)
                ],
                "unanchored_static_clusters": [
                    asdict(cluster)
                    for cluster in unanchored_static_clusters
                ],
                "final_trajectory_integrity": {
                    "rejected_frames": sorted(final_trajectory_rejections),
                    "maximum_speed_pixels_per_second": (
                        max_speed_pixels_per_second
                    ),
                    "maximum_acceleration_pixels_per_second_squared": float(
                        SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                            "maximum_acceleration_pixels_per_second_squared"
                        ]
                    ),
                },
                "confirmation_cascade": {
                    "invariant": (
                        "Confirmed frames are append-only locks; later "
                        "modules can only confirm unresolved frames."
                    ),
                    "modules": [
                        LOCK_YOLO_CHAIN_MODULE,
                        "01_confirm_yolo",
                        FLIPBOOK_MODULE,
                        AERIAL_MODULE,
                        "03_motion_and_optical_flow",
                        "04_focused_multiscale",
                        "05_short_stationary",
                        "06_time_machine_region_search",
                        "02_time_machine",
                    ],
                    "summary": ledger.module_summary(),
                },
                "tracks": [
                    {
                        "track_id": track.track_id,
                        "points": [asdict(point) for point in track.points],
                    }
                    for track in accepted
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    state_path = output / "ball-state-estimates.json"
    state_path.write_text(
        json.dumps(
            {
                "manifest": str(manifest.path),
                "cache": str(cache_path.resolve()),
                "policy": {
                    "observed_states_are_event_evidence": True,
                    "trajectory_estimates_are_event_evidence": False,
                    "trajectory_estimates_are_for_continuity_and_search_only": True,
                },
                "states": _sampled_ball_state_estimates(
                    accepted,
                    records=records,
                    fps=manifest.fps,
                    frame_step=frame_step,
                    width=width,
                    height=height,
                    max_speed_pixels_per_second=max_speed_pixels_per_second,
                    ledger=ledger,
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_summary(
        output=output,
        records=records,
        raw_candidates=[candidate.point for candidate in candidates],
        pitch_candidate_count=len(pitch_candidates),
        filtered_candidates=filtered,
        candidate_conflict_frames=sum(
            count > 1 for count in filtered_candidate_counts.values()
        ),
        conflicting_candidates=sum(
            count - 1
            for count in filtered_candidate_counts.values()
            if count > 1
        ),
        upper_body_rejections=len(pitch_candidates) - len(candidates),
        global_static_rejections=global_static_rejections,
        unanchored_static_rejections=unanchored_static_rejections,
        tracks=accepted,
        unanchored_static_clusters=unanchored_static_clusters,
        associated_track_fragments=len(associated_tracks),
        supported_track_fragments=len(supported_tracks),
        discarded_static_fragments=discarded_static_fragments,
        discarded_temporal_upper_body_points=(
            discarded_temporal_upper_body_points
        ),
        raw_motion_diagnostics=raw_motion_diagnostics,
        kalman_reacquisition_diagnostics=(
            _KalmanReacquisitionDiagnostics()
        ),
        dense_flow_diagnostics=dense_flow_diagnostics,
        ledger=ledger,
        analysis_start_seconds=analysis_start_seconds,
        analysis_end_seconds=analysis_end_seconds,
    )
    print(f"Ball tracks written to {track_path.resolve()}")
    return track_path
