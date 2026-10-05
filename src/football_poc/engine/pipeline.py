from __future__ import annotations

from football_poc.engine.common import *

def infer_cached_possession(*, manifest_path: Path, player_tracks_path: Path, ball_tracks_path: Path, output: Path, ball_state_estimates_path: Path | None=None, control_radius_heights: float=1.2, smoothing_seconds: float=0.24, segment_gap_seconds: float=0.64, identity_switch_radius_heights: float=0.75, co_visible_track_return_seconds: float=0.0, minimum_segment_observations: int=2, maximum_transfer_seconds: float=3.0, minimum_transfer_heights: float=1.5, minimum_pass_speed_pixels_per_second: float=60.0, maximum_pass_step_seconds: float=0.24, pass_flight_debounce_seconds: float=1.2, pass_sender_lookback_seconds: float=1.0, pass_receiver_window_seconds: float=2.0, transfer_deduplication_seconds: float=0.8, minimum_shot_speed_pixels_per_second: float=200.0, minimum_shot_goal_cosine: float=0.92, infer_shots: bool=True, turnover_smoothing_seconds: float | None=None, turnover_control_radius_heights: float | None=None, maximum_flyby_speed_pixels_per_second: float | None=None, maximum_flyby_speed_heights_per_second: float | None=None, minimum_flyby_direction_cosine: float=0.85, maximum_ground_contact_height_ratio: float | None=None, maximum_aerial_contact_direction_cosine: float=0.5, future_control_confirmation_seconds: float=0.0, boundary_events_path: Path | None=None, initial_possession_team: str | None=None, startup_guard_seconds: float=4.0, startup_receiver_control_radius_heights: float=1.2, transient_opponent_max_seconds: float=1.2, occluded_owner_max_seconds: float | None=None, occluded_owner_max_speed_heights_per_second: float=3.0, occluded_owner_min_direction_cosine: float | None=None, minimum_restart_speed_pixels_per_second: float=200.0, boundary_ownership_lookback_seconds: float=2.0) -> Path:
    manifest = BenchmarkManifest.load(manifest_path)
    players = _load_player_points(player_tracks_path, manifest.path)
    goalkeeper_track_ids = {int(point['track_id']) for frame_points in players.values() for point in frame_points if point.get('role') == 'goalkeeper'}
    co_visible_track_pairs = _co_visible_track_pairs(players)
    balls = _load_ball_points(ball_tracks_path, manifest.path, state_estimates_path=ball_state_estimates_path)
    has_ball_state_estimates = any((not bool(point.get('event_evidence_eligible', True)) for frame_points in balls.values() for point in frame_points))
    smooth_teams_fn = _live__smooth_teams if has_ball_state_estimates else _smooth_teams
    build_segments_fn = _live_build_possession_segments if has_ball_state_estimates else build_possession_segments
    collapse_segments_fn = _live_collapse_transient_opponent_segments if has_ball_state_estimates else collapse_transient_opponent_segments
    infer_transfer_events_fn = _live_infer_transfer_events if has_ball_state_estimates else infer_transfer_events
    infer_direction_change_transfer_events_fn = _live_infer_direction_change_transfer_events if has_ball_state_estimates else infer_direction_change_transfer_events
    infer_flight_transfer_events_fn = _live_infer_flight_transfer_events if has_ball_state_estimates else infer_flight_transfer_events
    merge_transfer_events_fn = _live_merge_transfer_events if has_ball_state_estimates else merge_transfer_events
    filter_ambiguous_startup_transfers_fn = _live_filter_ambiguous_startup_transfers if has_ball_state_estimates else filter_ambiguous_startup_transfers
    reconcile_track_identity_team_switches_fn = _live_reconcile_track_identity_team_switches if has_ball_state_estimates else reconcile_track_identity_team_switches
    infer_deferred_contested_turnovers_fn = _live_infer_deferred_contested_turnovers if has_ball_state_estimates else infer_deferred_contested_turnovers
    infer_terminal_direct_reception_fn = _live_infer_terminal_direct_reception if has_ball_state_estimates else infer_terminal_direct_reception
    reconcile_delayed_turnover_chains_fn = _live_reconcile_delayed_turnover_chains if has_ball_state_estimates else reconcile_delayed_turnover_chains
    suppress_uncontrolled_opponent_turnovers_fn = _live_suppress_uncontrolled_opponent_turnovers if has_ball_state_estimates else suppress_uncontrolled_opponent_turnovers
    refine_weak_reception_completion_times_fn = _live_refine_weak_reception_completion_times if has_ball_state_estimates else refine_weak_reception_completion_times
    refine_delayed_turnovers_to_contested_decelerations_fn = _live_refine_delayed_turnovers_to_contested_decelerations if has_ball_state_estimates else refine_delayed_turnovers_to_contested_decelerations
    infer_ball_reentry_receptions_fn = _live_infer_ball_reentry_receptions if has_ball_state_estimates else infer_ball_reentry_receptions
    infer_unresolved_direction_change_receptions_fn = _live_infer_unresolved_direction_change_receptions if has_ball_state_estimates else infer_unresolved_direction_change_receptions
    infer_unobserved_chain_contacts_fn = _live_infer_unobserved_chain_contacts if has_ball_state_estimates else infer_unobserved_chain_contacts
    reconcile_intervening_opponent_aerial_contacts_fn = _live_reconcile_intervening_opponent_aerial_contacts if has_ball_state_estimates else reconcile_intervening_opponent_aerial_contacts
    raw_observations = _control_observations(players, balls, control_radius_heights=control_radius_heights, maximum_flyby_speed_pixels_per_second=maximum_flyby_speed_pixels_per_second, maximum_flyby_speed_heights_per_second=maximum_flyby_speed_heights_per_second, minimum_flyby_direction_cosine=minimum_flyby_direction_cosine, maximum_ground_contact_height_ratio=maximum_ground_contact_height_ratio, maximum_aerial_contact_direction_cosine=maximum_aerial_contact_direction_cosine, future_control_confirmation_seconds=future_control_confirmation_seconds)
    observations = smooth_teams_fn(raw_observations, smoothing_seconds)
    state_segments = build_segments_fn(observations, segment_gap_seconds=segment_gap_seconds, identity_switch_radius_heights=identity_switch_radius_heights, co_visible_track_return_seconds=co_visible_track_return_seconds, co_visible_track_pairs=co_visible_track_pairs)
    state_segments = collapse_segments_fn(state_segments, maximum_transient_seconds=transient_opponent_max_seconds, maximum_occlusion_seconds=occluded_owner_max_seconds, maximum_owner_speed_heights_per_second=occluded_owner_max_speed_heights_per_second, minimum_owner_direction_cosine=occluded_owner_min_direction_cosine)
    segments = build_segments_fn(observations, segment_gap_seconds=segment_gap_seconds, identity_switch_radius_heights=identity_switch_radius_heights, co_visible_track_return_seconds=co_visible_track_return_seconds, co_visible_track_pairs=co_visible_track_pairs)
    segments = collapse_segments_fn(segments, maximum_transient_seconds=transient_opponent_max_seconds, maximum_occlusion_seconds=occluded_owner_max_seconds, maximum_owner_speed_heights_per_second=occluded_owner_max_speed_heights_per_second, minimum_owner_direction_cosine=occluded_owner_min_direction_cosine)
    stable_segments = retain_stable_possession_segments(segments, minimum_observations=minimum_segment_observations, trusted_single_observation_track_ids=goalkeeper_track_ids)
    if has_ball_state_estimates:
        segment_transfer_events = infer_transfer_events_fn(stable_segments, maximum_transfer_seconds=maximum_transfer_seconds, minimum_transfer_heights=minimum_transfer_heights)
        direction_change_transfer_events = infer_direction_change_transfer_events_fn(balls, stable_segments, maximum_transfer_seconds=maximum_transfer_seconds, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        flight_transfer_events = infer_flight_transfer_events_fn(balls, state_segments, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second, maximum_step_seconds=maximum_pass_step_seconds, debounce_seconds=pass_flight_debounce_seconds, sender_lookback_seconds=pass_sender_lookback_seconds, receiver_window_seconds=pass_receiver_window_seconds, minimum_sender_observations=1, minimum_receiver_observations=minimum_segment_observations)
        deceleration_transfer_events = infer_deceleration_transfer_events(balls, stable_segments, minimum_incoming_speed_pixels_per_second=minimum_pass_speed_pixels_per_second, maximum_outgoing_speed_ratio=0.35, sender_lookback_seconds=pass_sender_lookback_seconds, receiver_window_seconds=pass_receiver_window_seconds, minimum_transfer_heights=minimum_transfer_heights, players=players)
        deceleration_transfer_events = [event for event in deceleration_transfer_events if not any((flight.team == event.team and flight.event_type == event.event_type and (flight.completion_seconds is not None) and (event.completion_seconds is not None) and (abs(flight.completion_seconds - event.completion_seconds) <= transfer_deduplication_seconds + 1e-09) for flight in flight_transfer_events))]
        transfer_events = merge_transfer_events_fn([*flight_transfer_events, *deceleration_transfer_events, *direction_change_transfer_events], segment_transfer_events, deduplication_seconds=transfer_deduplication_seconds)
    else:
        transfer_segments = include_supported_single_touch_senders(segments, stable_segments, co_visible_track_pairs=co_visible_track_pairs, maximum_transfer_seconds=maximum_transfer_seconds, minimum_transfer_heights=minimum_transfer_heights)
        segment_transfer_events = infer_transfer_events_fn(transfer_segments, maximum_transfer_seconds=maximum_transfer_seconds, minimum_transfer_heights=minimum_transfer_heights, control_observations=observations, co_visible_track_pairs=co_visible_track_pairs)
        direction_change_transfer_events = infer_direction_change_transfer_events_fn(balls, stable_segments, control_observations=observations, maximum_transfer_seconds=maximum_transfer_seconds, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        flight_transfer_events = infer_flight_transfer_events_fn(balls, state_segments, control_observations=observations, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second, maximum_step_seconds=maximum_pass_step_seconds, debounce_seconds=pass_flight_debounce_seconds, sender_lookback_seconds=pass_sender_lookback_seconds, receiver_window_seconds=pass_receiver_window_seconds, minimum_sender_observations=1, minimum_receiver_observations=minimum_segment_observations)
        deceleration_transfer_events = infer_deceleration_transfer_events(balls, stable_segments, minimum_incoming_speed_pixels_per_second=minimum_pass_speed_pixels_per_second, maximum_outgoing_speed_ratio=0.35, sender_lookback_seconds=pass_sender_lookback_seconds, receiver_window_seconds=pass_receiver_window_seconds, minimum_transfer_heights=minimum_transfer_heights, players=players)
        deceleration_transfer_events = [event for event in deceleration_transfer_events if not any((flight.team == event.team and flight.event_type == event.event_type and (flight.completion_seconds is not None) and (event.completion_seconds is not None) and (abs(flight.completion_seconds - event.completion_seconds) <= transfer_deduplication_seconds + 1e-09) for flight in flight_transfer_events))]
        transfer_events = merge_transfer_events_fn([*flight_transfer_events, *deceleration_transfer_events, *direction_change_transfer_events], segment_transfer_events, deduplication_seconds=transfer_deduplication_seconds)
        transfer_events = suppress_transient_proximity_receptions(transfer_events, state_segments, balls)
    if initial_possession_team is None:
        transfer_events = filter_ambiguous_startup_transfers_fn(transfer_events, observations, startup_guard_seconds=startup_guard_seconds, maximum_receiver_control_ratio=startup_receiver_control_radius_heights)
    initial_event = None
    if initial_possession_team is not None:
        initial_event = infer_initial_possession_transfer(initial_possession_team, stable_segments)
        if initial_event is not None:
            transfer_events = [initial_event, *transfer_events]
    clip_duration_seconds = manifest.source_frame_count / manifest.fps
    match_state_timeline = build_match_state_timeline([], duration_seconds=clip_duration_seconds)
    rejected_boundary_intervals: list[dict[str, Any]] = []
    aerial_boundary_intervals: list[dict[str, Any]] = []
    if boundary_events_path is not None:
        boundary_payload = json.loads(boundary_events_path.read_text(encoding='utf-8'))
        raw_boundary_intervals = boundary_payload.get('intervals', [])
        ball_points = [point for frame_points in balls.values() for point in frame_points]
        state_boundary_intervals, flight_rejections = partition_continuous_flight_candidates(raw_boundary_intervals, ball_points)
        boundary_intervals = filter_aerial_boundary_intervals(raw_boundary_intervals, stable_segments)
        accepted_boundary_starts = {float(interval['start_seconds']) for interval in boundary_intervals}
        aerial_boundary_intervals = [interval for interval in raw_boundary_intervals if float(interval['start_seconds']) not in accepted_boundary_starts]
        accepted_state_intervals = filter_aerial_boundary_intervals(state_boundary_intervals, stable_segments)
        accepted_state_starts = {float(interval['start_seconds']) for interval in accepted_state_intervals}
        state_possession_rejections = [interval for interval in state_boundary_intervals if float(interval['start_seconds']) not in accepted_state_starts]
        coalesced_state_intervals = coalesce_stoppage_candidates(accepted_state_intervals)
        accepted_state_intervals, fragmented_boundary_rejections = partition_fragmented_boundary_candidates(coalesced_state_intervals, ({'start_seconds': segment.start_seconds, 'end_seconds': segment.end_seconds} for segment in stable_segments))
        accepted_state_intervals = annotate_restart_releases(accepted_state_intervals, balls, minimum_speed_pixels_per_second=minimum_restart_speed_pixels_per_second)
        in_field_restart_intervals = detect_stationary_ball_restarts(ball_points, (point for frame_points in players.values() for point in frame_points))
        in_field_restart_intervals = extend_restarts_through_ball_setup(in_field_restart_intervals, stable_segments, ball_points)
        accepted_state_intervals = sorted([*accepted_state_intervals, *in_field_restart_intervals], key=lambda interval: float(interval['start_seconds']))
        rejected_boundary_intervals = [interval if 'reason' in interval else {**interval, 'reason': 'continuous_possession'} for interval in sorted([*flight_rejections, *state_possession_rejections, *fragmented_boundary_rejections], key=lambda item: float(item['start_seconds']))]
        match_state_timeline = build_match_state_timeline(accepted_state_intervals, duration_seconds=clip_duration_seconds)
        transfer_events = [event for event in transfer_events if match_state_timeline.allows_event(event.event_type, event.clip_seconds, event.completion_seconds)]
        boundary_turnovers = infer_boundary_turnovers(accepted_state_intervals, stable_segments, prior_events=transfer_events, ownership_lookback_seconds=boundary_ownership_lookback_seconds, startup_restart_max_seconds=startup_guard_seconds)
        transfer_events = sorted(transfer_events + boundary_turnovers + infer_restart_passes(accepted_state_intervals, stable_segments, prior_events=[*transfer_events, *boundary_turnovers], ownership_lookback_seconds=boundary_ownership_lookback_seconds, balls=balls, startup_restart_max_seconds=startup_guard_seconds, control_observations=raw_observations), key=lambda event: event.clip_seconds)
    effective_turnover_smoothing = smoothing_seconds if turnover_smoothing_seconds is None else turnover_smoothing_seconds
    effective_turnover_radius = control_radius_heights if turnover_control_radius_heights is None else turnover_control_radius_heights
    if effective_turnover_smoothing != smoothing_seconds or effective_turnover_radius != control_radius_heights:
        turnover_raw_observations = raw_observations if effective_turnover_radius == control_radius_heights else _control_observations(players, balls, control_radius_heights=effective_turnover_radius, maximum_flyby_speed_pixels_per_second=maximum_flyby_speed_pixels_per_second, maximum_flyby_speed_heights_per_second=maximum_flyby_speed_heights_per_second, minimum_flyby_direction_cosine=minimum_flyby_direction_cosine, maximum_ground_contact_height_ratio=maximum_ground_contact_height_ratio, maximum_aerial_contact_direction_cosine=maximum_aerial_contact_direction_cosine, future_control_confirmation_seconds=future_control_confirmation_seconds)
        turnover_observations = smooth_teams_fn(turnover_raw_observations, effective_turnover_smoothing)
        turnover_state_segments = build_segments_fn(turnover_observations, segment_gap_seconds=segment_gap_seconds, identity_switch_radius_heights=identity_switch_radius_heights, co_visible_track_return_seconds=co_visible_track_return_seconds, co_visible_track_pairs=co_visible_track_pairs)
        turnover_state_segments = collapse_segments_fn(turnover_state_segments, maximum_transient_seconds=transient_opponent_max_seconds, maximum_occlusion_seconds=occluded_owner_max_seconds, maximum_owner_speed_heights_per_second=occluded_owner_max_speed_heights_per_second, minimum_owner_direction_cosine=occluded_owner_min_direction_cosine)
        stable_turnover_state_segments = retain_stable_possession_segments(turnover_state_segments, minimum_observations=minimum_segment_observations, trusted_single_observation_track_ids=goalkeeper_track_ids)
        turnover_segments = build_segments_fn(turnover_observations, segment_gap_seconds=segment_gap_seconds, identity_switch_radius_heights=identity_switch_radius_heights, co_visible_track_return_seconds=co_visible_track_return_seconds, co_visible_track_pairs=co_visible_track_pairs)
        turnover_segments = collapse_segments_fn(turnover_segments, maximum_transient_seconds=transient_opponent_max_seconds, maximum_occlusion_seconds=occluded_owner_max_seconds, maximum_owner_speed_heights_per_second=occluded_owner_max_speed_heights_per_second, minimum_owner_direction_cosine=occluded_owner_min_direction_cosine)
        stable_turnover_segments = retain_stable_possession_segments(turnover_segments, minimum_observations=minimum_segment_observations, trusted_single_observation_track_ids=goalkeeper_track_ids)
        turnover_segment_events = infer_transfer_events_fn(stable_turnover_segments, maximum_transfer_seconds=maximum_transfer_seconds, minimum_transfer_heights=minimum_transfer_heights, control_observations=turnover_observations)
        turnover_flight_events = infer_flight_transfer_events_fn(balls, stable_turnover_state_segments, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second, maximum_step_seconds=maximum_pass_step_seconds, debounce_seconds=pass_flight_debounce_seconds, sender_lookback_seconds=pass_sender_lookback_seconds, receiver_window_seconds=pass_receiver_window_seconds, minimum_sender_observations=1, minimum_receiver_observations=minimum_segment_observations)
        turnover_events = [event for event in merge_transfer_events_fn(turnover_flight_events, turnover_segment_events, deduplication_seconds=transfer_deduplication_seconds) if event.event_type == 'turnover_candidate']
        if initial_event is not None:
            turnover_events = [initial_event, *turnover_events]
        transfer_events = sorted([event for event in transfer_events if event.event_type != 'turnover_candidate'] + turnover_events, key=lambda event: event.clip_seconds)
    if has_ball_state_estimates:
        transfer_events = reconcile_one_touch_team_transfers(transfer_events, raw_observations, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second, maximum_prior_reception_seconds=pass_receiver_window_seconds)
        transfer_events = reconcile_track_identity_team_switches_fn(transfer_events, players, maximum_chain_seconds=pass_receiver_window_seconds)
        transfer_events = infer_deferred_contested_turnovers_fn(transfer_events, players, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = infer_terminal_direct_reception_fn(transfer_events, players, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = reconcile_delayed_turnover_chains_fn(transfer_events, players, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = reconcile_unconfirmed_turnovers(transfer_events, state_segments)
        transfer_events = suppress_uncontrolled_opponent_turnovers_fn(transfer_events, players, balls)
        transfer_events = propagate_deferred_possession_chains(transfer_events, players, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = suppress_overlapping_opponent_handoffs(transfer_events, players, balls)
        transfer_events = refine_weak_reception_completion_times_fn(transfer_events, state_segments)
        transfer_events = refine_delayed_turnovers_to_contested_decelerations_fn(transfer_events, players, balls, raw_observations, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = refine_receptions_to_sharp_contacts(transfer_events, raw_observations, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = infer_short_exchange_receptions(transfer_events, raw_observations, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second, maximum_prior_reception_seconds=pass_receiver_window_seconds)
        transfer_events = infer_ball_reentry_receptions_fn(transfer_events, raw_observations, balls, players, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = refine_aerial_challenged_receiver_receptions(transfer_events, raw_observations, aerial_boundary_intervals, players, balls)
        transfer_events = infer_unresolved_direction_change_receptions_fn(transfer_events, raw_observations, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = infer_occluded_exchange_receptions(transfer_events, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = infer_unobserved_chain_contacts_fn(transfer_events, raw_observations, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second, segment_end_seconds=manifest.source_frame_count / manifest.fps)
        transfer_events = refine_one_touch_acceleration_receptions(transfer_events, players, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = suppress_redundant_retained_possession_links(transfer_events)
        transfer_events = filter_disconnected_low_confidence_startup(transfer_events)
        transfer_events = reconcile_deflected_turnover_sequences(transfer_events, state_segments)
        transfer_events = infer_opening_aerial_reception(transfer_events, raw_observations, rejected_boundary_intervals)
        transfer_events = reconcile_intervening_opponent_aerial_contacts_fn(transfer_events, raw_observations, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
    else:
        transfer_events = reconcile_one_touch_team_transfers(transfer_events, raw_observations, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second, maximum_prior_reception_seconds=pass_receiver_window_seconds)
        transfer_events = reconcile_track_identity_team_switches_fn(transfer_events, players, maximum_chain_seconds=pass_receiver_window_seconds, control_observations=raw_observations)
        transfer_events = infer_event_established_turnovers(transfer_events, state_segments, maximum_transfer_seconds=maximum_transfer_seconds)
        transfer_events = infer_deferred_contested_turnovers_fn(transfer_events, players, balls, raw_observations, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = infer_terminal_direct_reception_fn(transfer_events, players, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = reconcile_delayed_turnover_chains_fn(transfer_events, players, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = reconcile_unconfirmed_turnovers(transfer_events, state_segments)
        transfer_events = suppress_uncontrolled_opponent_turnovers_fn(transfer_events, players, balls, state_segments)
        transfer_events = propagate_deferred_possession_chains(transfer_events, players, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = suppress_overlapping_opponent_handoffs(transfer_events, players, balls)
        transfer_events = refine_weak_reception_completion_times_fn(transfer_events, state_segments, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = refine_delayed_turnovers_to_contested_decelerations_fn(transfer_events, players, balls, raw_observations, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = refine_receptions_to_sharp_contacts(transfer_events, raw_observations, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = infer_post_turnover_first_pass(transfer_events, raw_observations, co_visible_track_pairs=co_visible_track_pairs)
        transfer_events = infer_short_exchange_receptions(transfer_events, raw_observations, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second, maximum_prior_reception_seconds=pass_receiver_window_seconds)
        transfer_events = infer_pre_release_flight_receptions(transfer_events, raw_observations, balls, co_visible_track_pairs=co_visible_track_pairs, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second, maximum_sender_lookback_seconds=pass_receiver_window_seconds)
        transfer_events = infer_ball_reentry_receptions_fn(transfer_events, raw_observations, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = refine_aerial_challenged_receiver_receptions(transfer_events, raw_observations, aerial_boundary_intervals, players, balls)
        transfer_events = infer_unresolved_direction_change_receptions_fn(transfer_events, raw_observations, balls, players=players, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = suppress_transient_proximity_receptions(transfer_events, state_segments, balls)
        transfer_events = infer_occluded_exchange_receptions(transfer_events, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = infer_unobserved_chain_contacts_fn(transfer_events, raw_observations, balls, players=players, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second, segment_end_seconds=manifest.source_frame_count / manifest.fps)
        transfer_events = refine_one_touch_acceleration_receptions(transfer_events, players, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = suppress_redundant_retained_possession_links(transfer_events)
        transfer_events = filter_disconnected_low_confidence_startup(transfer_events)
        transfer_events = reconcile_deflected_turnover_sequences(transfer_events, state_segments)
        transfer_events = infer_opening_aerial_reception(transfer_events, raw_observations, rejected_boundary_intervals)
        transfer_events = infer_opening_live_reception(transfer_events, stable_segments, balls, match_state_timeline, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second, maximum_transfer_seconds=maximum_transfer_seconds, players=players)
        transfer_events = infer_sparse_control_transfer(transfer_events, raw_observations, balls, co_visible_track_pairs=co_visible_track_pairs, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = split_acceleration_confirmed_one_touch_passes(transfer_events, players, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = infer_terminal_brief_reception(transfer_events, raw_observations, players, balls, segment_end_seconds=manifest.source_frame_count / manifest.fps)
        transfer_events = collapse_competing_same_sender_receptions(transfer_events)
        transfer_events = suppress_duplicate_track_handoff_passes(transfer_events, players)
        transfer_events = suppress_sequential_track_split_passes(transfer_events, players)
        transfer_events = reconcile_late_strong_control_transfers(transfer_events, state_segments, raw_observations, balls, co_visible_track_pairs=co_visible_track_pairs, segment_end_seconds=manifest.source_frame_count / manifest.fps, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = suppress_noncausal_nonreturn_passes(transfer_events, observations=raw_observations)
        transfer_events = infer_pass_sender_established_turnovers(transfer_events, state_segments, raw_observations, maximum_transfer_seconds=maximum_transfer_seconds)
        transfer_events = reconcile_intervening_opponent_aerial_contacts_fn(transfer_events, raw_observations, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = suppress_passes_crossing_opponent_control(transfer_events, observations)
        transfer_events = infer_delayed_first_flight_reception(transfer_events, raw_observations, stable_segments, players, balls, match_state_timeline, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = infer_short_controlled_teammate_transfers(transfer_events, state_segments, co_visible_track_pairs=co_visible_track_pairs, minimum_transfer_heights=minimum_transfer_heights, players=players)
        transfer_events = reconcile_brief_opponent_turnover_pairs(transfer_events, raw_observations, players)
        transfer_events = split_sharp_direction_change_passes(transfer_events, players, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        transfer_events = backdate_unseen_carrier_dispossessions(transfer_events, players, balls, minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second)
        if initial_possession_team is None:
            transfer_events = filter_ambiguous_startup_transfers_fn(transfer_events, observations, startup_guard_seconds=startup_guard_seconds, maximum_receiver_control_ratio=startup_receiver_control_radius_heights)
    transfer_events = suppress_label_flicker_tackle_artifacts(transfer_events, players)
    transfer_events = collapse_simultaneous_releases_to_same_receiver(transfer_events)
    transfer_events = reconcile_self_track_turnovers(transfer_events, state_segments, raw_observations)
    transfer_events = suppress_unestablished_brief_opponent_turnovers(transfer_events, state_segments)
    width, height = _video_dimensions(manifest.video)
    shot_events = infer_shot_events(balls, stable_segments, width=width, height=height, minimum_speed_pixels_per_second=minimum_shot_speed_pixels_per_second, minimum_goal_cosine=minimum_shot_goal_cosine, prior_events=transfer_events) if infer_shots else []
    events = sorted([*transfer_events, *shot_events], key=lambda event: event.clip_seconds)
    events = gate_events_by_match_state(events, match_state_timeline)
    has_state_estimates = has_ball_state_estimates
    event_evidence_balls = {frame: [point for point in frame_points if bool(point.get('event_evidence_eligible', True))] for frame, frame_points in balls.items()}
    event_payloads = [{**asdict(event), 'ball_evidence': _event_ball_evidence(event, event_evidence_balls)} if has_state_estimates else asdict(event) for event in events]
    output.mkdir(parents=True, exist_ok=True)
    (output / 'event-evaluation.json').unlink(missing_ok=True)
    destination = output / 'possession.json'
    destination.write_text(json.dumps({**({'ball_evidence_summary': _ball_evidence_summary(balls)} if has_state_estimates else {}), 'observations': [asdict(item) for item in observations], 'segments': [{'team': segment.team, 'player_track_id': segment.player_track_id, 'start_seconds': segment.start_seconds, 'end_seconds': segment.end_seconds, 'observation_count': len(segment.observations)} for segment in stable_segments]}, indent=2), encoding='utf-8')
    (output / 'predicted-events.json').write_text(json.dumps(event_payloads, indent=2), encoding='utf-8')
    (output / 'match-state-events.json').write_text(json.dumps(match_state_timeline.to_dict(rejected_boundary_candidates=rejected_boundary_intervals), indent=2), encoding='utf-8')
    print(f'Possession and event outputs written to {output.resolve()}')
    return destination

from football_poc.engine.stage_pipeline import STAGES, collect_stage_results
