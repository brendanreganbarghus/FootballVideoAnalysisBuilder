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


def _confirm_track_points_from_module(
    ledger: FrameLedger,
    module: str,
    tracks: Iterable[BallTrack],
    *,
    records_by_frame: dict[int, dict[str, Any]],
    fps: float,
    max_speed_pixels_per_second: float,
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
        if _inside_player_upper_body(point, record):
            ledger.reject(frame, module, "candidate_inside_player_upper_body")
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
    candidates = [
        _BallCandidate(
            point=point,
            near_player_feet=_near_player_feet(point, record),
        )
        for point, record in pitch_candidates
        if _player_context_allows_ball(point, record)
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
        "01_confirm_yolo",
        _confirm_yolo_detections,
        ledger,
        selected_detector_points,
        candidates_by_frame=candidates_by_frame,
        records_by_frame=records_by_frame,
        fps=manifest.fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    ledger = _timed_tracker_call(
        "02_time_machine",
        _confirm_time_machine_estimates,
        ledger,
        fps=manifest.fps,
        frame_step=frame_step,
        width=width,
        height=height,
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
    ledger = _timed_tracker_call(
        "04_focused_multiscale",
        _confirm_track_points_from_module,
        ledger,
        "04_focused_multiscale",
        focused_tracks,
        records_by_frame=records_by_frame,
        fps=manifest.fps,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
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
                        "01_confirm_yolo",
                        "02_time_machine",
                        "03_motion_and_optical_flow",
                        "04_focused_multiscale",
                        "05_short_stationary",
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
