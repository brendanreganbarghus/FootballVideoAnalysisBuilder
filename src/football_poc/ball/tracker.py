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
    motion_supported_tracks = _timed_tracker_call(
        "motion_supported_points",
        _add_motion_supported_points,
        supported_tracks,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
        maximum_gap_seconds=max_gap_seconds,
    )
    temporally_supported_tracks = _timed_tracker_call(
        "template_supported_points",
        _add_template_supported_points,
        motion_supported_tracks,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
        maximum_gap_seconds=max_gap_seconds,
    )
    accepted = _timed_tracker_call(
        "select_single_ball_trajectory",
        select_single_ball_trajectory,
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
    accepted = _timed_tracker_call(
        "resolve_detector_conflicts",
        _resolve_detector_conflicts_by_attention,
        accepted,
        detector_candidates=filtered_candidate_objects,
        supported_foot_points=supported_foot_points,
        records=records,
        video=manifest.video,
        frame_step=frame_step,
    )
    accepted = _timed_tracker_call(
        "restore_plausible_detector_points",
        _restore_plausible_detector_points,
        accepted,
        detector_candidates=filtered_candidate_objects,
        frame_step=frame_step,
        fps=manifest.fps,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        cell_size=static_cell_size,
        supported_foot_points=foot_supported_points,
    )
    accepted = _timed_tracker_call(
        "bidirectional_template_bridges",
        _add_bidirectional_template_bridges,
        accepted,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
        maximum_gap_seconds=max_gap_seconds,
    )
    accepted = _timed_tracker_call(
        "terminal_template_bridges",
        _add_terminal_template_bridges,
        accepted,
        candidates=filtered,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        maximum_gap_seconds=max_gap_seconds,
    )
    accepted = _timed_tracker_call(
        "forward_template_consensus",
        _add_forward_template_consensus,
        accepted,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
        maximum_gap_seconds=max_gap_seconds,
    )
    accepted, startup_attention_rejections = (
        _timed_tracker_call(
            "startup_attention_gate",
            _gate_unanchored_start_points_by_attention,
            accepted,
            records=records,
            video=manifest.video,
            width=width,
            height=height,
            fps=manifest.fps,
            frame_step=frame_step,
        )
    )
    accepted, raw_motion_diagnostics = _timed_tracker_call(
        "raw_motion_proposals",
        _add_raw_motion_proposals,
        accepted,
        records=records,
        video=manifest.video,
        width=width,
        height=height,
        fps=manifest.fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        detector_candidates=filtered,
    )
    raw_motion_diagnostics = replace(
        raw_motion_diagnostics,
        startup_points_rejected=startup_attention_rejections,
    )
    accepted, kalman_reacquisition_diagnostics = (
        _timed_tracker_call(
            "kalman_guided_reacquisitions",
            _add_kalman_guided_reacquisitions,
            accepted,
            detector_candidates=filtered,
            records=records,
            video=manifest.video,
            width=width,
            height=height,
            fps=manifest.fps,
            frame_step=frame_step,
        )
    )
    accepted, dense_flow_diagnostics = _timed_tracker_call(
        "dense_optical_flow_bridges",
        _add_dense_optical_flow_bridges,
        accepted,
        records=records,
        video=manifest.video,
        width=width,
        height=height,
        fps=manifest.fps,
        frame_step=frame_step,
    )
    accepted, rejected_outlier_frames = (
        _timed_tracker_call(
            "discard_detector_outliers",
            _discard_unsupported_detector_outliers,
            accepted,
            records=records,
            video=manifest.video,
            fps=manifest.fps,
            frame_step=frame_step,
            max_gap_seconds=max_gap_seconds,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        )
    )
    accepted = _timed_tracker_call(
        "bracketed_outlier_recoveries",
        _add_bracketed_outlier_motion_recoveries,
        accepted,
        records=records,
        video=manifest.video,
        width=width,
        height=height,
        fps=manifest.fps,
        frame_step=frame_step,
        rejected_frames=rejected_outlier_frames,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    accepted = _timed_tracker_call(
        "full_rate_motion_streaks",
        _add_full_rate_motion_streaks,
        accepted,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    accepted = _timed_tracker_call(
        "full_rate_trajectory_corridors",
        _add_full_rate_trajectory_corridors,
        accepted,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
        analysis_end_frame=max(int(record["source_frame"]) for record in records),
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    accepted, discarded_temporal_upper_body_points = (
        _timed_tracker_call(
            "discard_temporal_upper_body_points",
            _discard_temporal_upper_body_points,
            accepted,
            records_by_frame={
                int(record["source_frame"]): record for record in records
            },
        )
    )
    accepted = _timed_tracker_call(
        "focused_multiscale_points",
        _recover_focused_multiscale_points,
        accepted,
        records=records,
        video=manifest.video,
        model_path=Path(str(metadata["model"])),
        fps=manifest.fps,
        frame_step=frame_step,
    )
    accepted = _deduplicate_track_frames(accepted)
    accepted, final_trajectory_rejections = _timed_tracker_call(
        "final_trajectory_integrity",
        _discard_final_trajectory_conflicts,
        accepted,
        fps=manifest.fps,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        max_acceleration_pixels_per_second_squared=float(
            SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                "maximum_acceleration_pixels_per_second_squared"
            ]
        ),
    )
    accepted = _timed_tracker_call(
        "short_stationary_template_recoveries",
        _add_short_stationary_template_recoveries,
        accepted,
        video=manifest.video,
        fps=manifest.fps,
        frame_step=frame_step,
    )
    accepted, post_recovery_rejections = _timed_tracker_call(
        "post_recovery_trajectory_integrity",
        _discard_final_trajectory_conflicts,
        accepted,
        fps=manifest.fps,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        max_acceleration_pixels_per_second_squared=float(
            SOCCERTRACK_MICRO_CROP_VERIFICATION_PROFILE[
                "maximum_acceleration_pixels_per_second_squared"
            ]
        ),
    )
    final_trajectory_rejections = frozenset(
        final_trajectory_rejections | post_recovery_rejections
    )

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
            kalman_reacquisition_diagnostics
        ),
        dense_flow_diagnostics=dense_flow_diagnostics,
        analysis_start_seconds=analysis_start_seconds,
        analysis_end_seconds=analysis_end_seconds,
    )
    print(f"Ball tracks written to {track_path.resolve()}")
    return track_path
