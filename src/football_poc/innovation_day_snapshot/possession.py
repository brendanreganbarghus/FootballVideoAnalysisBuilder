from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from math import hypot
from pathlib import Path
from typing import Any, Iterable

import cv2

from football_poc.innovation_day_snapshot.benchmark import BenchmarkManifest
from football_poc.innovation_day_snapshot.match_state import (
    MatchStateTimeline,
    build_match_state_timeline,
    coalesce_stoppage_candidates,
    detect_stationary_ball_restarts,
    partition_continuous_flight_candidates,
    partition_fragmented_boundary_candidates,
)
from football_poc.innovation_day_snapshot.player_tracking import (
    classify_color_scores,
)


@dataclass(frozen=True)
class PossessionObservation:
    source_frame: int
    clip_seconds: float
    team: str
    player_track_id: int
    player_x: float
    player_y: float
    player_height: float
    ball_x: float
    ball_y: float
    control_ratio: float
    ball_interpolated: bool = False


@dataclass
class PossessionSegment:
    team: str
    player_track_id: int
    observations: list[PossessionObservation]

    @property
    def start_seconds(self) -> float:
        return self.observations[0].clip_seconds

    @property
    def end_seconds(self) -> float:
        return self.observations[-1].clip_seconds


@dataclass(frozen=True)
class PredictedEvent:
    event_type: str
    clip_seconds: float
    team: str | None
    from_player_track_id: int | None
    to_player_track_id: int | None
    confidence: float
    details: str
    completion_seconds: float | None = None


def retain_stable_possession_segments(
    segments: Iterable[PossessionSegment],
    *,
    minimum_observations: int,
    trusted_single_observation_track_ids: set[int],
) -> list[PossessionSegment]:
    return [
        segment
        for segment in segments
        if len(segment.observations) >= minimum_observations
        or (
            len(segment.observations) == 1
            and segment.player_track_id in trusted_single_observation_track_ids
        )
    ]


def include_supported_single_touch_senders(
    segments: Iterable[PossessionSegment],
    stable_segments: Iterable[PossessionSegment],
    *,
    co_visible_track_pairs: Iterable[frozenset[int]],
    maximum_transfer_seconds: float,
    minimum_transfer_heights: float,
) -> list[PossessionSegment]:
    stable = list(stable_segments)
    stable_keys = {
        (segment.player_track_id, segment.start_seconds, segment.end_seconds)
        for segment in stable
    }
    distinct_pairs = set(co_visible_track_pairs)
    supported = list(stable)
    for sender in segments:
        sender_key = (
            sender.player_track_id,
            sender.start_seconds,
            sender.end_seconds,
        )
        if sender_key in stable_keys or len(sender.observations) != 1:
            continue
        touch = sender.observations[0]
        if touch.control_ratio > 0.35:
            continue
        receiver = next(
            (
                candidate
                for candidate in stable
                if candidate.team == sender.team
                and candidate.player_track_id != sender.player_track_id
                and frozenset(
                    (sender.player_track_id, candidate.player_track_id)
                ) in distinct_pairs
                and (
                    controlled := [
                        observation
                        for observation in candidate.observations
                        if observation.control_ratio <= 0.5
                    ]
                )
                and len(controlled) >= 2
                and 0
                <= controlled[0].clip_seconds - touch.clip_seconds
                <= maximum_transfer_seconds
                and hypot(
                    controlled[0].ball_x - touch.ball_x,
                    controlled[0].ball_y - touch.ball_y,
                )
                / max(
                    1.0,
                    (touch.player_height + controlled[0].player_height) / 2,
                )
                >= minimum_transfer_heights
            ),
            None,
        )
        if receiver is not None:
            supported.append(sender)
    return sorted(supported, key=lambda segment: segment.start_seconds)


def infer_cached_possession(
    *,
    manifest_path: Path,
    player_tracks_path: Path,
    ball_tracks_path: Path,
    output: Path,
    control_radius_heights: float = 1.2,
    smoothing_seconds: float = 0.24,
    segment_gap_seconds: float = 0.64,
    identity_switch_radius_heights: float = 0.75,
    co_visible_track_return_seconds: float = 0.0,
    minimum_segment_observations: int = 2,
    maximum_transfer_seconds: float = 3.0,
    minimum_transfer_heights: float = 1.5,
    minimum_pass_speed_pixels_per_second: float = 60.0,
    maximum_pass_step_seconds: float = 0.24,
    pass_flight_debounce_seconds: float = 1.2,
    pass_sender_lookback_seconds: float = 1.0,
    pass_receiver_window_seconds: float = 2.0,
    transfer_deduplication_seconds: float = 0.8,
    minimum_shot_speed_pixels_per_second: float = 200.0,
    minimum_shot_goal_cosine: float = 0.92,
    infer_shots: bool = True,
    turnover_smoothing_seconds: float | None = None,
    turnover_control_radius_heights: float | None = None,
    maximum_flyby_speed_pixels_per_second: float | None = None,
    maximum_flyby_speed_heights_per_second: float | None = None,
    minimum_flyby_direction_cosine: float = 0.85,
    maximum_ground_contact_height_ratio: float | None = None,
    maximum_aerial_contact_direction_cosine: float = 0.5,
    future_control_confirmation_seconds: float = 0.0,
    boundary_events_path: Path | None = None,
    initial_possession_team: str | None = None,
    startup_guard_seconds: float = 4.0,
    startup_receiver_control_radius_heights: float = 1.2,
    transient_opponent_max_seconds: float = 1.2,
    occluded_owner_max_seconds: float | None = None,
    occluded_owner_max_speed_heights_per_second: float = 3.0,
    occluded_owner_min_direction_cosine: float | None = None,
    minimum_restart_speed_pixels_per_second: float = 200.0,
    boundary_ownership_lookback_seconds: float = 2.0,
) -> Path:
    manifest = BenchmarkManifest.load(manifest_path)
    players = _load_player_points(player_tracks_path, manifest.path)
    goalkeeper_track_ids = {
        int(point["track_id"])
        for frame_points in players.values()
        for point in frame_points
        if point.get("role") == "goalkeeper"
    }
    co_visible_track_pairs = _co_visible_track_pairs(players)
    balls = _load_ball_points(ball_tracks_path, manifest.path)
    raw_observations = _control_observations(
        players,
        balls,
        control_radius_heights=control_radius_heights,
        maximum_flyby_speed_pixels_per_second=(
            maximum_flyby_speed_pixels_per_second
        ),
        maximum_flyby_speed_heights_per_second=(
            maximum_flyby_speed_heights_per_second
        ),
        minimum_flyby_direction_cosine=minimum_flyby_direction_cosine,
        maximum_ground_contact_height_ratio=maximum_ground_contact_height_ratio,
        maximum_aerial_contact_direction_cosine=(
            maximum_aerial_contact_direction_cosine
        ),
        future_control_confirmation_seconds=future_control_confirmation_seconds,
    )
    observations = _smooth_teams(raw_observations, smoothing_seconds)
    state_segments = build_possession_segments(
        observations,
        segment_gap_seconds=segment_gap_seconds,
        identity_switch_radius_heights=identity_switch_radius_heights,
        co_visible_track_return_seconds=co_visible_track_return_seconds,
        co_visible_track_pairs=co_visible_track_pairs,
    )
    state_segments = collapse_transient_opponent_segments(
        state_segments,
        maximum_transient_seconds=transient_opponent_max_seconds,
        maximum_occlusion_seconds=occluded_owner_max_seconds,
        maximum_owner_speed_heights_per_second=(
            occluded_owner_max_speed_heights_per_second
        ),
        minimum_owner_direction_cosine=occluded_owner_min_direction_cosine,
    )
    segments = build_possession_segments(
        observations,
        segment_gap_seconds=segment_gap_seconds,
        identity_switch_radius_heights=identity_switch_radius_heights,
        co_visible_track_return_seconds=co_visible_track_return_seconds,
        co_visible_track_pairs=co_visible_track_pairs,
    )
    segments = collapse_transient_opponent_segments(
        segments,
        maximum_transient_seconds=transient_opponent_max_seconds,
        maximum_occlusion_seconds=occluded_owner_max_seconds,
        maximum_owner_speed_heights_per_second=(
            occluded_owner_max_speed_heights_per_second
        ),
        minimum_owner_direction_cosine=occluded_owner_min_direction_cosine,
    )
    stable_segments = retain_stable_possession_segments(
        segments,
        minimum_observations=minimum_segment_observations,
        trusted_single_observation_track_ids=goalkeeper_track_ids,
    )
    transfer_segments = include_supported_single_touch_senders(
        segments,
        stable_segments,
        co_visible_track_pairs=co_visible_track_pairs,
        maximum_transfer_seconds=maximum_transfer_seconds,
        minimum_transfer_heights=minimum_transfer_heights,
    )
    segment_transfer_events = infer_transfer_events(
        transfer_segments,
        maximum_transfer_seconds=maximum_transfer_seconds,
        minimum_transfer_heights=minimum_transfer_heights,
        control_observations=observations,
    )
    direction_change_transfer_events = infer_direction_change_transfer_events(
        balls,
        stable_segments,
        control_observations=observations,
        maximum_transfer_seconds=maximum_transfer_seconds,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
    )
    flight_transfer_events = infer_flight_transfer_events(
        balls,
        state_segments,
        control_observations=observations,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
        maximum_step_seconds=maximum_pass_step_seconds,
        debounce_seconds=pass_flight_debounce_seconds,
        sender_lookback_seconds=pass_sender_lookback_seconds,
        receiver_window_seconds=pass_receiver_window_seconds,
        minimum_sender_observations=1,
        minimum_receiver_observations=minimum_segment_observations,
    )
    deceleration_transfer_events = infer_deceleration_transfer_events(
        balls,
        stable_segments,
        minimum_incoming_speed_pixels_per_second=(
            minimum_pass_speed_pixels_per_second
        ),
        maximum_outgoing_speed_ratio=0.35,
        sender_lookback_seconds=pass_sender_lookback_seconds,
        receiver_window_seconds=pass_receiver_window_seconds,
        minimum_transfer_heights=minimum_transfer_heights,
    )
    deceleration_transfer_events = [
        event
        for event in deceleration_transfer_events
        if not any(
            flight.team == event.team
            and flight.event_type == event.event_type
            and flight.completion_seconds is not None
            and event.completion_seconds is not None
            and abs(flight.completion_seconds - event.completion_seconds)
            <= transfer_deduplication_seconds + 1e-9
            for flight in flight_transfer_events
        )
    ]
    transfer_events = merge_transfer_events(
        [
            *flight_transfer_events,
            *deceleration_transfer_events,
            *direction_change_transfer_events,
        ],
        segment_transfer_events,
        deduplication_seconds=transfer_deduplication_seconds,
    )
    transfer_events = suppress_transient_proximity_receptions(
        transfer_events,
        state_segments,
        balls,
    )
    if initial_possession_team is None:
        transfer_events = filter_ambiguous_startup_transfers(
            transfer_events,
            observations,
            startup_guard_seconds=startup_guard_seconds,
            maximum_receiver_control_ratio=(
                startup_receiver_control_radius_heights
            ),
        )
    initial_event = None
    if initial_possession_team is not None:
        initial_event = infer_initial_possession_transfer(
            initial_possession_team, stable_segments
        )
        if initial_event is not None:
            transfer_events = [initial_event, *transfer_events]
    clip_duration_seconds = manifest.source_frame_count / manifest.fps
    match_state_timeline = build_match_state_timeline(
        [], duration_seconds=clip_duration_seconds
    )
    rejected_boundary_intervals: list[dict[str, Any]] = []
    aerial_boundary_intervals: list[dict[str, Any]] = []
    if boundary_events_path is not None:
        boundary_payload = json.loads(
            boundary_events_path.read_text(encoding="utf-8")
        )
        raw_boundary_intervals = boundary_payload.get("intervals", [])
        ball_points = [
            point for frame_points in balls.values() for point in frame_points
        ]
        state_boundary_intervals, flight_rejections = (
            partition_continuous_flight_candidates(
                raw_boundary_intervals,
                ball_points,
            )
        )
        boundary_intervals = filter_aerial_boundary_intervals(
            raw_boundary_intervals,
            stable_segments,
        )
        accepted_boundary_starts = {
            float(interval["start_seconds"]) for interval in boundary_intervals
        }
        aerial_boundary_intervals = [
            interval
            for interval in raw_boundary_intervals
            if float(interval["start_seconds"]) not in accepted_boundary_starts
        ]
        accepted_state_intervals = filter_aerial_boundary_intervals(
            state_boundary_intervals,
            stable_segments,
        )
        accepted_state_starts = {
            float(interval["start_seconds"])
            for interval in accepted_state_intervals
        }
        state_possession_rejections = [
            interval
            for interval in state_boundary_intervals
            if float(interval["start_seconds"]) not in accepted_state_starts
        ]
        coalesced_state_intervals = coalesce_stoppage_candidates(
            accepted_state_intervals
        )
        accepted_state_intervals, fragmented_boundary_rejections = (
            partition_fragmented_boundary_candidates(
                coalesced_state_intervals,
                (
                    {
                        "start_seconds": segment.start_seconds,
                        "end_seconds": segment.end_seconds,
                    }
                    for segment in stable_segments
                ),
            )
        )
        accepted_state_intervals = annotate_restart_releases(
            accepted_state_intervals,
            balls,
            minimum_speed_pixels_per_second=(
                minimum_restart_speed_pixels_per_second
            ),
        )
        in_field_restart_intervals = detect_stationary_ball_restarts(
            ball_points,
            (
                point
                for frame_points in players.values()
                for point in frame_points
            ),
        )
        in_field_restart_intervals = extend_restarts_through_ball_setup(
            in_field_restart_intervals,
            stable_segments,
            ball_points,
        )
        accepted_state_intervals = sorted(
            [*accepted_state_intervals, *in_field_restart_intervals],
            key=lambda interval: float(interval["start_seconds"]),
        )
        rejected_boundary_intervals = [
            (
                interval
                if "reason" in interval
                else {**interval, "reason": "continuous_possession"}
            )
            for interval in sorted(
                [
                    *flight_rejections,
                    *state_possession_rejections,
                    *fragmented_boundary_rejections,
                ],
                key=lambda item: float(item["start_seconds"]),
            )
        ]
        match_state_timeline = build_match_state_timeline(
            accepted_state_intervals,
            duration_seconds=clip_duration_seconds,
        )
        transfer_events = [
            event
            for event in transfer_events
            if match_state_timeline.allows_event(
                event.event_type,
                event.clip_seconds,
                event.completion_seconds,
            )
        ]
        boundary_turnovers = infer_boundary_turnovers(
            accepted_state_intervals,
            stable_segments,
            prior_events=transfer_events,
            ownership_lookback_seconds=boundary_ownership_lookback_seconds,
            startup_restart_max_seconds=startup_guard_seconds,
        )
        transfer_events = sorted(
            transfer_events
            + boundary_turnovers
            + infer_restart_passes(
                accepted_state_intervals,
                stable_segments,
                prior_events=[*transfer_events, *boundary_turnovers],
                ownership_lookback_seconds=boundary_ownership_lookback_seconds,
                balls=balls,
                startup_restart_max_seconds=startup_guard_seconds,
                control_observations=raw_observations,
            ),
            key=lambda event: event.clip_seconds,
        )
    effective_turnover_smoothing = (
        smoothing_seconds
        if turnover_smoothing_seconds is None
        else turnover_smoothing_seconds
    )
    effective_turnover_radius = (
        control_radius_heights
        if turnover_control_radius_heights is None
        else turnover_control_radius_heights
    )
    if (
        effective_turnover_smoothing != smoothing_seconds
        or effective_turnover_radius != control_radius_heights
    ):
        turnover_raw_observations = (
            raw_observations
            if effective_turnover_radius == control_radius_heights
            else _control_observations(
                players,
                balls,
                control_radius_heights=effective_turnover_radius,
                maximum_flyby_speed_pixels_per_second=(
                    maximum_flyby_speed_pixels_per_second
                ),
                maximum_flyby_speed_heights_per_second=(
                    maximum_flyby_speed_heights_per_second
                ),
                minimum_flyby_direction_cosine=(
                    minimum_flyby_direction_cosine
                ),
                maximum_ground_contact_height_ratio=(
                    maximum_ground_contact_height_ratio
                ),
                maximum_aerial_contact_direction_cosine=(
                    maximum_aerial_contact_direction_cosine
                ),
                future_control_confirmation_seconds=(
                    future_control_confirmation_seconds
                ),
            )
        )
        turnover_observations = _smooth_teams(
            turnover_raw_observations, effective_turnover_smoothing
        )
        turnover_state_segments = build_possession_segments(
            turnover_observations,
            segment_gap_seconds=segment_gap_seconds,
            identity_switch_radius_heights=identity_switch_radius_heights,
            co_visible_track_return_seconds=co_visible_track_return_seconds,
            co_visible_track_pairs=co_visible_track_pairs,
        )
        turnover_state_segments = collapse_transient_opponent_segments(
            turnover_state_segments,
            maximum_transient_seconds=transient_opponent_max_seconds,
            maximum_occlusion_seconds=occluded_owner_max_seconds,
            maximum_owner_speed_heights_per_second=(
                occluded_owner_max_speed_heights_per_second
            ),
            minimum_owner_direction_cosine=(
                occluded_owner_min_direction_cosine
            ),
        )
        stable_turnover_state_segments = retain_stable_possession_segments(
            turnover_state_segments,
            minimum_observations=minimum_segment_observations,
            trusted_single_observation_track_ids=goalkeeper_track_ids,
        )
        turnover_segments = build_possession_segments(
            turnover_observations,
            segment_gap_seconds=segment_gap_seconds,
            identity_switch_radius_heights=identity_switch_radius_heights,
            co_visible_track_return_seconds=co_visible_track_return_seconds,
            co_visible_track_pairs=co_visible_track_pairs,
        )
        turnover_segments = collapse_transient_opponent_segments(
            turnover_segments,
            maximum_transient_seconds=transient_opponent_max_seconds,
            maximum_occlusion_seconds=occluded_owner_max_seconds,
            maximum_owner_speed_heights_per_second=(
                occluded_owner_max_speed_heights_per_second
            ),
            minimum_owner_direction_cosine=(
                occluded_owner_min_direction_cosine
            ),
        )
        stable_turnover_segments = retain_stable_possession_segments(
            turnover_segments,
            minimum_observations=minimum_segment_observations,
            trusted_single_observation_track_ids=goalkeeper_track_ids,
        )
        turnover_segment_events = infer_transfer_events(
            stable_turnover_segments,
            maximum_transfer_seconds=maximum_transfer_seconds,
            minimum_transfer_heights=minimum_transfer_heights,
            control_observations=turnover_observations,
        )
        turnover_flight_events = infer_flight_transfer_events(
            balls,
            stable_turnover_state_segments,
            minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
            maximum_step_seconds=maximum_pass_step_seconds,
            debounce_seconds=pass_flight_debounce_seconds,
            sender_lookback_seconds=pass_sender_lookback_seconds,
            receiver_window_seconds=pass_receiver_window_seconds,
            minimum_sender_observations=1,
            minimum_receiver_observations=minimum_segment_observations,
        )
        turnover_events = [
            event
            for event in merge_transfer_events(
                turnover_flight_events,
                turnover_segment_events,
                deduplication_seconds=transfer_deduplication_seconds,
            )
            if event.event_type == "turnover_candidate"
        ]
        if initial_event is not None:
            turnover_events = [initial_event, *turnover_events]
        transfer_events = sorted(
            [
                event
                for event in transfer_events
                if event.event_type != "turnover_candidate"
            ]
            + turnover_events,
            key=lambda event: event.clip_seconds,
        )
    transfer_events = reconcile_one_touch_team_transfers(
        transfer_events,
        raw_observations,
        balls,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
        maximum_prior_reception_seconds=pass_receiver_window_seconds,
    )
    transfer_events = reconcile_track_identity_team_switches(
        transfer_events,
        players,
        maximum_chain_seconds=pass_receiver_window_seconds,
        control_observations=raw_observations,
    )
    transfer_events = infer_event_established_turnovers(
        transfer_events,
        state_segments,
        maximum_transfer_seconds=maximum_transfer_seconds,
    )
    transfer_events = infer_deferred_contested_turnovers(
        transfer_events,
        players,
        balls,
        raw_observations,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
    )
    transfer_events = reconcile_delayed_turnover_chains(
        transfer_events,
        players,
        balls,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
    )
    transfer_events = reconcile_unconfirmed_turnovers(
        transfer_events,
        state_segments,
    )
    transfer_events = suppress_uncontrolled_opponent_turnovers(
        transfer_events,
        players,
        balls,
        state_segments,
    )
    transfer_events = propagate_deferred_possession_chains(
        transfer_events,
        players,
        balls,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
    )
    transfer_events = suppress_overlapping_opponent_handoffs(
        transfer_events,
        players,
        balls,
    )
    transfer_events = refine_weak_reception_completion_times(
        transfer_events,
        state_segments,
        balls,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
    )
    transfer_events = refine_delayed_turnovers_to_contested_decelerations(
        transfer_events,
        players,
        balls,
        raw_observations,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
    )
    transfer_events = refine_receptions_to_sharp_contacts(
        transfer_events,
        raw_observations,
        balls,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
    )
    transfer_events = infer_post_turnover_first_pass(
        transfer_events,
        raw_observations,
        co_visible_track_pairs=co_visible_track_pairs,
    )
    transfer_events = infer_short_exchange_receptions(
        transfer_events,
        raw_observations,
        balls,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
        maximum_prior_reception_seconds=pass_receiver_window_seconds,
    )
    transfer_events = infer_pre_release_flight_receptions(
        transfer_events,
        raw_observations,
        balls,
        co_visible_track_pairs=co_visible_track_pairs,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
        maximum_sender_lookback_seconds=pass_receiver_window_seconds,
    )
    transfer_events = infer_ball_reentry_receptions(
        transfer_events,
        raw_observations,
        balls,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
    )
    transfer_events = refine_aerial_challenged_receiver_receptions(
        transfer_events,
        raw_observations,
        aerial_boundary_intervals,
        players,
        balls,
    )
    transfer_events = infer_unresolved_direction_change_receptions(
        transfer_events,
        raw_observations,
        balls,
        players=players,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
    )
    transfer_events = suppress_transient_proximity_receptions(
        transfer_events,
        state_segments,
        balls,
    )
    transfer_events = infer_occluded_exchange_receptions(
        transfer_events,
        balls,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
    )
    transfer_events = infer_unobserved_chain_contacts(
        transfer_events,
        raw_observations,
        balls,
        players=players,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
        segment_end_seconds=manifest.source_frame_count / manifest.fps,
    )
    transfer_events = refine_one_touch_acceleration_receptions(
        transfer_events,
        players,
        balls,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
    )
    transfer_events = suppress_redundant_retained_possession_links(
        transfer_events
    )
    transfer_events = filter_disconnected_low_confidence_startup(
        transfer_events
    )
    transfer_events = reconcile_deflected_turnover_sequences(
        transfer_events,
        state_segments,
    )
    transfer_events = infer_opening_aerial_reception(
        transfer_events,
        raw_observations,
        rejected_boundary_intervals,
    )
    transfer_events = reconcile_intervening_opponent_aerial_contacts(
        transfer_events,
        raw_observations,
        balls,
        minimum_speed_pixels_per_second=minimum_pass_speed_pixels_per_second,
    )
    transfer_events = suppress_passes_crossing_opponent_control(
        transfer_events,
        observations,
    )
    if initial_possession_team is None:
        transfer_events = filter_ambiguous_startup_transfers(
            transfer_events,
            observations,
            startup_guard_seconds=startup_guard_seconds,
            maximum_receiver_control_ratio=(
                startup_receiver_control_radius_heights
            ),
        )
    width, height = _video_dimensions(manifest.video)
    shot_events = (
        infer_shot_events(
            balls,
            stable_segments,
            width=width,
            height=height,
            minimum_speed_pixels_per_second=minimum_shot_speed_pixels_per_second,
            minimum_goal_cosine=minimum_shot_goal_cosine,
            prior_events=transfer_events,
        )
        if infer_shots
        else []
    )
    events = sorted(
        [*transfer_events, *shot_events],
        key=lambda event: event.clip_seconds,
    )
    events = gate_events_by_match_state(events, match_state_timeline)

    output.mkdir(parents=True, exist_ok=True)
    (output / "event-evaluation.json").unlink(missing_ok=True)
    destination = output / "possession.json"
    destination.write_text(
        json.dumps(
            {
                "observations": [asdict(item) for item in observations],
                "segments": [
                    {
                        "team": segment.team,
                        "player_track_id": segment.player_track_id,
                        "start_seconds": segment.start_seconds,
                        "end_seconds": segment.end_seconds,
                        "observation_count": len(segment.observations),
                    }
                    for segment in stable_segments
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (output / "predicted-events.json").write_text(
        json.dumps([asdict(event) for event in events], indent=2),
        encoding="utf-8",
    )
    (output / "match-state-events.json").write_text(
        json.dumps(
            match_state_timeline.to_dict(
                rejected_boundary_candidates=rejected_boundary_intervals
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Possession and event outputs written to {output.resolve()}")
    return destination


def gate_events_by_match_state(
    events: Iterable[PredictedEvent],
    timeline: MatchStateTimeline,
) -> list[PredictedEvent]:
    return [
        event
        for event in events
        if timeline.allows_event(
            event.event_type,
            event.clip_seconds,
            event.completion_seconds,
        )
    ]


def build_possession_segments(
    observations: Iterable[PossessionObservation],
    *,
    segment_gap_seconds: float,
    identity_switch_radius_heights: float,
    co_visible_track_return_seconds: float = 0.0,
    co_visible_track_pairs: Iterable[frozenset[int]] = (),
) -> list[PossessionSegment]:
    if co_visible_track_return_seconds < 0:
        raise ValueError("Co-visible track return duration cannot be negative")
    ordered = sorted(observations, key=lambda item: item.clip_seconds)
    incompatible_track_pairs = set(co_visible_track_pairs)
    if co_visible_track_return_seconds > 0:
        for index, first in enumerate(ordered):
            for middle_index in range(index + 1, len(ordered)):
                middle = ordered[middle_index]
                if (
                    middle.clip_seconds - first.clip_seconds
                    > co_visible_track_return_seconds
                ):
                    break
                if middle.player_track_id == first.player_track_id:
                    continue
                if any(
                    last.player_track_id == first.player_track_id
                    and last.clip_seconds - middle.clip_seconds
                    <= co_visible_track_return_seconds + 1e-9
                    for last in ordered[middle_index + 1 :]
                    if last.clip_seconds - middle.clip_seconds
                    <= co_visible_track_return_seconds + 1e-9
                ):
                    incompatible_track_pairs.add(
                        frozenset(
                            (first.player_track_id, middle.player_track_id)
                        )
                    )
    segments: list[PossessionSegment] = []
    for observation_index, observation in enumerate(ordered):
        if not segments:
            segments.append(
                PossessionSegment(
                    observation.team,
                    observation.player_track_id,
                    [observation],
                )
            )
            continue
        current = segments[-1]
        previous = current.observations[-1]
        gap = observation.clip_seconds - previous.clip_seconds
        player_distance = hypot(
            observation.player_x - previous.player_x,
            observation.player_y - previous.player_y,
        )
        player_scale = max(
            1.0, (observation.player_height + previous.player_height) / 2
        )
        same_physical_player = (
            observation.player_track_id == previous.player_track_id
            or player_distance / player_scale <= identity_switch_radius_heights
        )
        continuous_dribble = False
        if (
            len(current.observations) >= 2
            and previous.control_ratio <= 1.0
            and observation.control_ratio <= 1.0
            and gap > 0
        ):
            earlier = current.observations[-2]
            incoming = (
                previous.ball_x - earlier.ball_x,
                previous.ball_y - earlier.ball_y,
            )
            outgoing = (
                observation.ball_x - previous.ball_x,
                observation.ball_y - previous.ball_y,
            )
            incoming_distance = hypot(*incoming)
            outgoing_distance = hypot(*outgoing)
            direction_cosine = (
                (
                    incoming[0] * outgoing[0]
                    + incoming[1] * outgoing[1]
                )
                / (incoming_distance * outgoing_distance)
                if incoming_distance > 0 and outgoing_distance > 0
                else -1.0
            )
            ball_speed_heights = outgoing_distance / gap / player_scale
            continuous_dribble = (
                direction_cosine >= 0.9
                and ball_speed_heights <= 5.0
            )
        prior_track_returns = (
            observation.player_track_id != current.player_track_id
            and frozenset(
                (observation.player_track_id, current.player_track_id)
            )
            in incompatible_track_pairs
        )
        if (
            gap <= segment_gap_seconds
            and observation.team == current.team
            and (same_physical_player or continuous_dribble)
            and not prior_track_returns
        ):
            current.observations.append(observation)
            continue
        segments.append(
            PossessionSegment(
                observation.team,
                observation.player_track_id,
                [observation],
            )
        )
    return segments


def _co_visible_track_pairs(
    players: dict[int, list[dict[str, Any]]],
) -> set[frozenset[int]]:
    pairs: set[frozenset[int]] = set()
    for frame_players in players.values():
        track_ids = sorted(
            {
                int(player["track_id"])
                for player in frame_players
                if player.get("track_id") is not None
            }
        )
        for index, first in enumerate(track_ids):
            for second in track_ids[index + 1 :]:
                pairs.add(frozenset((first, second)))
    return pairs


def collapse_transient_opponent_segments(
    segments: Iterable[PossessionSegment],
    *,
    maximum_transient_seconds: float,
    maximum_occlusion_seconds: float | None = None,
    maximum_owner_speed_heights_per_second: float = 3.0,
    minimum_owner_direction_cosine: float | None = None,
) -> list[PossessionSegment]:
    if maximum_transient_seconds < 0:
        raise ValueError("Maximum transient opponent duration cannot be negative")
    if maximum_occlusion_seconds is not None and maximum_occlusion_seconds < 0:
        raise ValueError("Maximum occlusion duration cannot be negative")
    if maximum_owner_speed_heights_per_second <= 0:
        raise ValueError("Maximum owner speed must be positive")
    if (
        minimum_owner_direction_cosine is not None
        and not -1 <= minimum_owner_direction_cosine <= 1
    ):
        raise ValueError("Owner direction cosine must be between -1 and 1")
    source = list(segments)
    accepted: list[PossessionSegment] = []
    index = 0
    while index < len(source):
        current = source[index]
        if accepted and current.team != accepted[-1].team:
            prior_team = accepted[-1].team
            end = index
            while end < len(source) and source[end].team != prior_team:
                end += 1
            if end < len(source):
                transient_duration = (
                    source[end - 1].end_seconds - current.start_seconds
                )
                owner_continuity = _plausible_owner_continuity(
                    accepted[-1],
                    source[end],
                    maximum_seconds=maximum_occlusion_seconds,
                    maximum_speed_heights_per_second=(
                        maximum_owner_speed_heights_per_second
                    ),
                    minimum_direction_cosine=minimum_owner_direction_cosine,
                )
                following_gap = (
                    source[end].start_seconds - source[end - 1].end_seconds
                )
                continuity_window = (
                    maximum_occlusion_seconds
                    if maximum_occlusion_seconds is not None
                    else maximum_transient_seconds
                )
                coherent_opponent_control = any(
                    len(segment.observations) >= 3
                    and sum(
                        observation.control_ratio <= 0.5
                        for observation in segment.observations
                    )
                    >= 1
                    for segment in source[index:end]
                )
                if not coherent_opponent_control:
                    for opponent_index in range(index, end):
                        opponent = source[opponent_index]
                        if (
                            len(opponent.observations) < 2
                            or not any(
                                observation.control_ratio <= 0.5
                                for observation in opponent.observations
                            )
                        ):
                            continue
                        controlled_teammate_seen = False
                        for later in source[end + 1 :]:
                            if (
                                later.start_seconds - opponent.end_seconds
                                > maximum_transient_seconds + 1e-9
                            ):
                                break
                            if later.team != opponent.team:
                                continue
                            if (
                                later.player_track_id
                                == opponent.player_track_id
                                and controlled_teammate_seen
                            ):
                                coherent_opponent_control = True
                                break
                            if (
                                later.player_track_id
                                != opponent.player_track_id
                                and len(later.observations) >= 2
                                and any(
                                    observation.control_ratio <= 0.5
                                    for observation in later.observations
                                )
                            ):
                                controlled_teammate_seen = True
                        if coherent_opponent_control:
                            break
                transient_bridge = (
                    transient_duration <= maximum_transient_seconds
                    and following_gap <= continuity_window
                    and not coherent_opponent_control
                )
                owner_continuity_allowed = owner_continuity and (
                    len(source[end].observations) >= 2
                    or not coherent_opponent_control
                )
                if (
                    transient_bridge
                    or owner_continuity_allowed
                ):
                    following = source[end]
                    if (
                        accepted[-1].team == following.team
                        and accepted[-1].observations[-1].player_track_id
                        == following.observations[0].player_track_id
                    ):
                        accepted[-1].observations.extend(following.observations)
                        index = end + 1
                        continue
                    index = end
                    continue
        accepted.append(current)
        index += 1
    return accepted


def _plausible_owner_continuity(
    previous: PossessionSegment,
    following: PossessionSegment,
    *,
    maximum_seconds: float | None,
    maximum_speed_heights_per_second: float,
    minimum_direction_cosine: float | None = None,
) -> bool:
    if maximum_seconds is None or previous.team != following.team:
        return False
    start = previous.observations[-1]
    end = following.observations[0]
    elapsed = end.clip_seconds - start.clip_seconds
    if elapsed <= 0 or elapsed > maximum_seconds:
        return False
    scale = max(1.0, (start.player_height + end.player_height) / 2)
    distance_heights = hypot(
        end.player_x - start.player_x,
        end.player_y - start.player_y,
    ) / scale
    if distance_heights / elapsed > maximum_speed_heights_per_second:
        return False
    if minimum_direction_cosine is None:
        return True
    if len(previous.observations) < 2:
        return False
    prior = previous.observations[-2]
    owner_motion = (
        start.player_x - prior.player_x,
        start.player_y - prior.player_y,
    )
    continuation = (
        end.player_x - start.player_x,
        end.player_y - start.player_y,
    )
    owner_distance = hypot(*owner_motion)
    continuation_distance = hypot(*continuation)
    if owner_distance == 0 or continuation_distance == 0:
        return False
    direction_cosine = (
        owner_motion[0] * continuation[0]
        + owner_motion[1] * continuation[1]
    ) / (owner_distance * continuation_distance)
    return direction_cosine >= minimum_direction_cosine


def infer_transfer_events(
    segments: Iterable[PossessionSegment],
    *,
    maximum_transfer_seconds: float,
    minimum_transfer_heights: float,
    receiver_return_confirmation_seconds: float = 1.2,
    control_observations: Iterable[PossessionObservation] = (),
) -> list[PredictedEvent]:
    stable = list(segments)
    controls = list(control_observations)
    events: list[PredictedEvent] = []
    for current_index, (previous, current) in enumerate(
        zip(stable, stable[1:]),
        start=1,
    ):
        if previous.player_track_id == current.player_track_id:
            continue
        current_has_control = any(
            observation.control_ratio <= 0.5
            for observation in current.observations
        )
        if (
            previous.team == current.team
            and not current_has_control
            and current_index + 1 < len(stable)
        ):
            following = stable[current_index + 1]
            previous_controls = [
                observation
                for observation in previous.observations
                if observation.control_ratio <= 0.5
            ]
            following_controls = [
                observation
                for observation in following.observations
                if observation.control_ratio <= 0.5
            ]
            if (
                previous_controls
                and following.team != previous.team
                and len(following_controls) >= 2
                and following_controls[0].clip_seconds
                - previous_controls[-1].clip_seconds
                <= maximum_transfer_seconds
            ):
                current = following
                current_index += 1
        previous_last = previous.observations[-1]
        current_first = current.observations[0]
        previous_controls = [
            observation
            for observation in previous.observations
            if observation.control_ratio <= 0.5
        ]
        current_controls = [
            observation
            for observation in current.observations
            if observation.control_ratio <= 0.5
        ]
        if previous_controls and len(previous.observations) >= 3:
            previous_last = previous_controls[-1]
        if len(current_controls) >= 2:
            current_first = current_controls[0]
        gap = current_first.clip_seconds - previous_last.clip_seconds
        if gap < 0 or gap > maximum_transfer_seconds:
            continue
        scale = max(
            1.0,
            (previous_last.player_height + current_first.player_height) / 2,
        )
        travel = hypot(
            current_first.ball_x - previous_last.ball_x,
            current_first.ball_y - previous_last.ball_y,
        )
        travel_heights = travel / scale
        returning_receiver_control = False
        if previous.team != current.team and len(current.observations) >= 2:
            controlled_teammate_seen = False
            for later in stable[current_index + 1 :]:
                if (
                    later.start_seconds - current.end_seconds
                    > receiver_return_confirmation_seconds + 1e-9
                ):
                    break
                if later.team != current.team:
                    break
                if (
                    later.player_track_id == current.player_track_id
                    and controlled_teammate_seen
                ):
                    returning_receiver_control = True
                    break
                if (
                    later.player_track_id != current.player_track_id
                    and len(later.observations) >= 2
                    and any(
                        observation.control_ratio <= 0.5
                        for observation in later.observations
                    )
                ):
                    controlled_teammate_seen = True
        if (
            previous_last.control_ratio > 0.5
            or (
                current_first.control_ratio > 0.5
                and not returning_receiver_control
            )
        ):
            continue
        if (
            previous.team == current.team
            and travel_heights < minimum_transfer_heights
        ):
            continue
        if (
            previous.team != current.team
            and travel_heights < minimum_transfer_heights
            and not returning_receiver_control
            and (
                len(current.observations) < 4
                or sum(
                    observation.control_ratio <= 0.5
                    for observation in current.observations
                )
                < 2
            )
        ):
            continue

        event_type = (
            "pass_candidate"
            if previous.team == current.team
            else "turnover_candidate"
        )
        completion_seconds = current_first.clip_seconds
        release_seconds = previous_last.clip_seconds
        from_player_track_id = previous.player_track_id
        if returning_receiver_control:
            completion_seconds = next(
                observation.clip_seconds
                for observation in current.observations
                if observation.control_ratio <= 0.5
            )
            latest_owner = max(
                (
                    observation
                    for observation in controls
                    if observation.team == previous.team
                    and observation.control_ratio <= 0.5
                    and previous.end_seconds
                    <= observation.clip_seconds
                    < completion_seconds
                ),
                key=lambda observation: observation.clip_seconds,
                default=None,
            )
            if latest_owner is not None:
                release_seconds = latest_owner.clip_seconds
                from_player_track_id = latest_owner.player_track_id
        confidence = min(
            1.0,
            0.3
            + 0.05 * min(len(previous.observations), 3)
            + 0.05 * min(len(current.observations), 3)
            + 0.05 * min(travel_heights, 3),
        )
        events.append(
            PredictedEvent(
                event_type=event_type,
                clip_seconds=round(release_seconds, 3),
                team=previous.team,
                from_player_track_id=from_player_track_id,
                to_player_track_id=current.player_track_id,
                confidence=round(confidence, 4),
                details=(
                    (
                        "The receiver's controlled touch was corroborated by "
                        "continued team control and the receiver track returning."
                    )
                    if returning_receiver_control
                    else (
                        f"Control transferred after {gap:.2f}s and "
                        f"{travel_heights:.2f} player-heights of ball travel."
                    )
                ),
                completion_seconds=round(completion_seconds, 3),
            )
        )
    return events


def infer_event_established_turnovers(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    *,
    maximum_transfer_seconds: float,
) -> list[PredictedEvent]:
    source = list(events)
    segments = list(possession_segments)
    additions: list[PredictedEvent] = []
    for event in source:
        if (
            event.event_type != "pass_candidate"
            or event.team is None
            or event.to_player_track_id is None
            or event.completion_seconds is None
        ):
            continue
        owner = next(
            (
                segment
                for segment in segments
                if segment.team == event.team
                and segment.player_track_id == event.to_player_track_id
                and segment.start_seconds
                <= event.completion_seconds + 0.4
                and segment.end_seconds >= event.completion_seconds
            ),
            None,
        )
        if owner is None or _segment_has_strong_control_evidence(owner):
            continue
        opponent = next(
            (
                segment
                for segment in segments
                if segment.team != event.team
                and segment.start_seconds >= owner.end_seconds
                and segment.start_seconds - owner.end_seconds
                <= maximum_transfer_seconds
                and len(segment.observations) >= 2
                and any(
                    observation.control_ratio <= 0.5
                    for observation in segment.observations
                )
                and not any(
                    owner.end_seconds < candidate.start_seconds
                    < segment.start_seconds
                    and candidate.team == event.team
                    for candidate in segments
                )
            ),
            None,
        )
        if opponent is None:
            continue
        completion = next(
            observation.clip_seconds
            for observation in opponent.observations
            if observation.control_ratio <= 0.5
        )
        if any(
            candidate.event_type == "turnover_candidate"
            and candidate.team == event.team
            and candidate.completion_seconds is not None
            and abs(candidate.completion_seconds - completion) <= 0.4
            for candidate in [*source, *additions]
        ):
            continue
        additions.append(
            PredictedEvent(
                event_type="turnover_candidate",
                clip_seconds=round(owner.end_seconds, 3),
                team=event.team,
                from_player_track_id=owner.player_track_id,
                to_player_track_id=opponent.player_track_id,
                confidence=0.65,
                details=(
                    "The preceding completed pass established possession before "
                    "the opponent's subsequent controlled touch."
                ),
                completion_seconds=round(completion, 3),
            )
        )
    return sorted(
        [*source, *additions],
        key=lambda event: event.clip_seconds,
    )


def infer_direction_change_transfer_events(
    balls: dict[int, list[dict[str, Any]]],
    possession_segments: Iterable[PossessionSegment],
    *,
    control_observations: Iterable[PossessionObservation] | None = None,
    maximum_transfer_seconds: float,
    minimum_speed_pixels_per_second: float,
    maximum_direction_cosine: float = 0.25,
) -> list[PredictedEvent]:
    if not -1 <= maximum_direction_cosine <= 1:
        raise ValueError("Maximum direction cosine must be between -1 and 1")
    points = sorted(
        (
            point
            for frame_points in balls.values()
            for point in frame_points
            if not point.get("interpolated", False)
        ),
        key=lambda point: float(point["clip_seconds"]),
    )
    segments = list(possession_segments)
    controls = list(control_observations or [])
    events: list[PredictedEvent] = []
    for sender, receiver in zip(segments, segments[1:]):
        gap = receiver.start_seconds - sender.end_seconds
        if (
            sender.team != receiver.team
            or sender.player_track_id == receiver.player_track_id
            or gap < 0
            or gap > maximum_transfer_seconds
            or sender.observations[-1].control_ratio > 0.5
            or receiver.observations[0].control_ratio > 0.5
            or any(
                observation.team != sender.team
                and observation.control_ratio <= 0.5
                and sender.end_seconds < observation.clip_seconds
                < receiver.start_seconds
                for observation in controls
            )
        ):
            continue
        candidates: list[tuple[float, float]] = []
        for previous, current, following in zip(
            points,
            points[1:],
            points[2:],
        ):
            timestamp = float(current["clip_seconds"])
            if not sender.end_seconds <= timestamp <= receiver.start_seconds:
                continue
            incoming_seconds = timestamp - float(previous["clip_seconds"])
            outgoing_seconds = float(following["clip_seconds"]) - timestamp
            if incoming_seconds <= 0 or outgoing_seconds <= 0:
                continue
            incoming = (
                float(current["x"]) - float(previous["x"]),
                float(current["y"]) - float(previous["y"]),
            )
            outgoing = (
                float(following["x"]) - float(current["x"]),
                float(following["y"]) - float(current["y"]),
            )
            incoming_distance = hypot(*incoming)
            outgoing_distance = hypot(*outgoing)
            if incoming_distance == 0 or outgoing_distance == 0:
                continue
            incoming_speed = incoming_distance / incoming_seconds
            outgoing_speed = outgoing_distance / outgoing_seconds
            if min(incoming_speed, outgoing_speed) < minimum_speed_pixels_per_second:
                continue
            direction_cosine = (
                incoming[0] * outgoing[0] + incoming[1] * outgoing[1]
            ) / (incoming_distance * outgoing_distance)
            if direction_cosine <= maximum_direction_cosine:
                candidates.append((direction_cosine, timestamp))
        if not candidates:
            continue
        direction_cosine, _ = min(candidates)
        events.append(
            PredictedEvent(
                event_type="pass_candidate",
                clip_seconds=round(sender.end_seconds, 3),
                team=sender.team,
                from_player_track_id=sender.player_track_id,
                to_player_track_id=receiver.player_track_id,
                confidence=round(
                    min(0.8, 0.55 + (1 - direction_cosine) * 0.1),
                    4,
                ),
                details=(
                    "Ball direction changed sharply as same-team control "
                    "transferred."
                ),
                completion_seconds=round(receiver.start_seconds, 3),
            )
        )
    return _deduplicate_receptions(events)


def suppress_passes_crossing_opponent_control(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    *,
    maximum_control_ratio: float = 0.5,
    maximum_support_ratio: float = 1.0,
    maximum_support_step_seconds: float = 0.4,
) -> list[PredictedEvent]:
    controls = list(observations)
    retained: list[PredictedEvent] = []
    for event in events:
        if (
            event.event_type != "pass_candidate"
            or event.completion_seconds is None
        ):
            retained.append(event)
            continue
        intervening = [
            observation
            for observation in controls
            if observation.team != event.team
            and event.clip_seconds < observation.clip_seconds
            < event.completion_seconds
        ]
        opponent_control = any(
            observation.control_ratio <= maximum_control_ratio
            and any(
                support is not observation
                and support.team == observation.team
                and support.player_track_id == observation.player_track_id
                and support.control_ratio <= maximum_support_ratio
                and abs(support.clip_seconds - observation.clip_seconds)
                <= maximum_support_step_seconds
                for support in intervening
            )
            for observation in intervening
        )
        if not opponent_control:
            retained.append(event)
    return retained


def reconcile_one_touch_team_transfers(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    maximum_prior_reception_seconds: float,
    maximum_direction_cosine: float = 0.25,
    observation_tolerance_seconds: float = 0.04,
    receiver_tolerance_seconds: float = 0.25,
) -> list[PredictedEvent]:
    source = list(events)
    controls = list(observations)
    motion = _ball_motion_evidence(balls)
    reconciled: list[PredictedEvent] = []
    for outgoing in source:
        if outgoing.event_type != "pass_candidate":
            reconciled.append(outgoing)
            continue
        candidates: list[PossessionObservation] = []
        for observation in controls:
            if (
                observation.team == outgoing.team
                or abs(observation.clip_seconds - outgoing.clip_seconds)
                > observation_tolerance_seconds
            ):
                continue
            evidence = next(
                (
                    value
                    for (_, frame), value in motion.items()
                    if frame == observation.source_frame
                ),
                None,
            )
            if (
                evidence is not None
                and evidence[0] >= minimum_speed_pixels_per_second
                and evidence[1] <= maximum_direction_cosine
            ):
                candidates.append(observation)
        if not candidates:
            reconciled.append(outgoing)
            continue
        contact = min(candidates, key=lambda item: item.control_ratio)
        anchors = [
            event
            for event in source
            if event.team == contact.team
            and event.completion_seconds is not None
            and 0
            < outgoing.clip_seconds - event.completion_seconds
            <= maximum_prior_reception_seconds
        ]
        if not anchors:
            reconciled.append(outgoing)
            continue
        anchor = max(anchors, key=lambda event: event.completion_seconds or 0)
        reconciled.append(
            PredictedEvent(
                event_type="pass_candidate",
                clip_seconds=round(outgoing.clip_seconds, 3),
                team=contact.team,
                from_player_track_id=None,
                to_player_track_id=contact.player_track_id,
                confidence=0.6,
                details=(
                    "A sharp one-touch contact completed the incoming "
                    "same-team pass and immediately released the next pass."
                ),
                completion_seconds=round(outgoing.clip_seconds, 3),
            )
        )
        reconciled.append(
            replace(
                outgoing,
                team=contact.team,
                from_player_track_id=contact.player_track_id,
                details=(
                    "A sharp one-touch contact established the outgoing "
                    f"{contact.team} pass."
                ),
            )
        )
    chained: list[PredictedEvent] = []
    for event in sorted(reconciled, key=lambda item: item.clip_seconds):
        anchors = [
            prior
            for prior in chained
            if event.from_player_track_id is not None
            and (
                prior.details.startswith(
                    "A sharp one-touch contact established"
                )
                or prior.details.startswith(
                    "Possession-chain continuity preserved"
                )
            )
            and prior.to_player_track_id == event.from_player_track_id
            and prior.completion_seconds is not None
            and 0
            <= event.clip_seconds - prior.completion_seconds
            <= maximum_prior_reception_seconds
        ]
        if not anchors or event.team == anchors[-1].team:
            chained.append(event)
            continue
        anchor = max(anchors, key=lambda item: item.completion_seconds or 0)
        receiver_teams = [
            observation.team
            for observation in controls
            if event.to_player_track_id is not None
            and observation.player_track_id == event.to_player_track_id
            and event.completion_seconds is not None
            and abs(
                observation.clip_seconds - event.completion_seconds
            )
            <= receiver_tolerance_seconds
        ]
        if not receiver_teams:
            chained.append(event)
            continue
        receiver_team = Counter(receiver_teams).most_common(1)[0][0]
        chained.append(
            replace(
                event,
                event_type=(
                    "pass_candidate"
                    if receiver_team == anchor.team
                    else "turnover_candidate"
                ),
                team=anchor.team,
                details=(
                    "Possession-chain continuity preserved the corrected "
                    "sender team through the next release."
                ),
            )
        )
    return _deduplicate_receptions(chained)


def reconcile_intervening_opponent_aerial_contacts(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    maximum_direction_cosine: float = -0.75,
    maximum_control_ratio: float = 1.0,
    maximum_immediate_control_ratio: float = 0.5,
    minimum_weak_contact_duration_seconds: float = 0.4,
    maximum_sender_gap_seconds: float = 4.0,
    maximum_receiver_gap_seconds: float = 3.0,
) -> list[PredictedEvent]:
    """Split a same-team transfer when an opponent sharply redirects the flight."""
    source = list(events)
    controls = list(observations)
    motion = _ball_motion_evidence(balls)
    reconciled: list[PredictedEvent] = []
    for event in source:
        completion = event.completion_seconds
        if (
            event.event_type != "pass_candidate"
            or completion is None
            or event.to_player_track_id is None
        ):
            reconciled.append(event)
            continue
        candidates: list[
            tuple[float, PossessionObservation, PossessionObservation]
        ] = []
        for contact in controls:
            if (
                contact.team == event.team
                or contact.control_ratio > maximum_control_ratio
                or not 0 < completion - contact.clip_seconds
                <= maximum_receiver_gap_seconds
                or (
                    contact.control_ratio > maximum_immediate_control_ratio
                    and completion - contact.clip_seconds
                    < minimum_weak_contact_duration_seconds
                )
                or any(
                    peer is not contact
                    and peer.team == contact.team
                    and abs(peer.clip_seconds - contact.clip_seconds) <= 1.0
                    for peer in controls
                )
            ):
                continue
            evidence = next(
                (
                    value
                    for (_, frame), value in motion.items()
                    if frame == contact.source_frame
                ),
                None,
            )
            if (
                evidence is None
                or evidence[0] < minimum_speed_pixels_per_second
                or evidence[1] > maximum_direction_cosine
            ):
                continue
            sender_controls = [
                observation
                for observation in controls
                if observation.team == event.team
                and 0 < contact.clip_seconds - observation.clip_seconds
                <= maximum_sender_gap_seconds
            ]
            if not sender_controls:
                continue
            sender = max(
                sender_controls,
                key=lambda observation: observation.clip_seconds,
            )
            candidates.append((evidence[1], contact, sender))
        if not candidates:
            reconciled.append(event)
            continue
        _, contact, sender = min(candidates, key=lambda candidate: candidate[0])
        if any(
            prior.event_type == "turnover_candidate"
            and prior.team == event.team
            and prior.completion_seconds is not None
            and abs(prior.completion_seconds - contact.clip_seconds) <= 0.5
            for prior in source
        ):
            reconciled.append(event)
            continue
        reconciled.extend(
            [
                PredictedEvent(
                    event_type="turnover_candidate",
                    clip_seconds=round(sender.clip_seconds, 3),
                    team=event.team,
                    from_player_track_id=sender.player_track_id,
                    to_player_track_id=contact.player_track_id,
                    confidence=0.6,
                    details=(
                        "A sharp opponent aerial contact interrupted the "
                        "apparent same-team transfer and established control."
                    ),
                    completion_seconds=round(contact.clip_seconds, 3),
                ),
                PredictedEvent(
                    event_type="turnover_candidate",
                    clip_seconds=round(contact.clip_seconds, 3),
                    team=contact.team,
                    from_player_track_id=contact.player_track_id,
                    to_player_track_id=event.to_player_track_id,
                    confidence=event.confidence,
                    details=(
                        "The original team regained control after the "
                        "opponent's controlled aerial contact."
                    ),
                    completion_seconds=round(completion, 3),
                ),
            ]
        )
    return _deduplicate_receptions(reconciled)


def reconcile_track_identity_team_switches(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    *,
    maximum_chain_seconds: float,
    control_observations: Iterable[PossessionObservation] | None = None,
    sender_control_window_seconds: float = 0.4,
    evidence_window_seconds: float = 0.8,
    minimum_evidence_points: int = 3,
) -> list[PredictedEvent]:
    if maximum_chain_seconds < 0:
        raise ValueError("Maximum chain duration cannot be negative")
    if evidence_window_seconds <= 0:
        raise ValueError("Evidence window must be positive")
    if minimum_evidence_points <= 0:
        raise ValueError("Minimum evidence points must be positive")
    if sender_control_window_seconds < 0:
        raise ValueError("Sender control window cannot be negative")

    controls = (
        None
        if control_observations is None
        else list(control_observations)
    )
    teams = {
        str(player.get("team"))
        for frame_players in players.values()
        for player in frame_players
    }
    if teams & {"red", "black"}:
        team_pair = ("red", "black")
        team_profile = "red-black"
    elif teams & {"blue", "white"}:
        team_pair = ("blue", "white")
        team_profile = "blue-white"
    else:
        return list(events)

    points_by_track: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame_players in players.values():
        for player in frame_players:
            points_by_track[int(player["track_id"])].append(player)

    def local_team(track_id: int | None, timestamp: float | None) -> str | None:
        if track_id is None or timestamp is None:
            return None
        labels: list[str] = []
        for point in points_by_track.get(track_id, []):
            if (
                abs(float(point["clip_seconds"]) - timestamp)
                > evidence_window_seconds
            ):
                continue
            scores = point.get("color_scores")
            if not isinstance(scores, dict):
                continue
            label = classify_color_scores(scores, team_profile=team_profile)
            if label in team_pair:
                labels.append(label)
        if len(labels) < minimum_evidence_points:
            return None
        label, count = Counter(labels).most_common(1)[0]
        return label if count / len(labels) >= 0.6 else None

    def other_team(team: str | None) -> str | None:
        if team == team_pair[0]:
            return team_pair[1]
        if team == team_pair[1]:
            return team_pair[0]
        return None

    corrected: list[PredictedEvent] = []
    for event in sorted(events, key=lambda item: item.clip_seconds):
        sender_team = event.team
        chain_anchor = next(
            (
                prior
                for prior in reversed(corrected)
                if (
                    prior.details.startswith(
                        "Frame-level jersey evidence corrected"
                    )
                    or prior.details.startswith(
                        "Track-switch possession continuity preserved"
                    )
                )
                and event.from_player_track_id is not None
                and prior.to_player_track_id == event.from_player_track_id
                and prior.completion_seconds is not None
                and 0
                <= event.clip_seconds - prior.completion_seconds
                <= maximum_chain_seconds
            ),
            None,
        )
        if chain_anchor is not None:
            if controls is not None and not any(
                observation.player_track_id == event.from_player_track_id
                and observation.control_ratio <= 1.0
                and 0
                <= event.clip_seconds - observation.clip_seconds
                <= sender_control_window_seconds
                for observation in controls
            ):
                continue
            sender_team = (
                chain_anchor.team
                if chain_anchor.event_type
                in {"pass_candidate", "restart_pass_candidate"}
                else other_team(chain_anchor.team)
            )

        receiver_team = local_team(
            event.to_player_track_id,
            event.completion_seconds,
        )
        if receiver_team is None or sender_team not in team_pair:
            corrected.append(event)
            continue
        implied_receiver_team = (
            sender_team
            if event.event_type in {"pass_candidate", "restart_pass_candidate"}
            else other_team(sender_team)
        )
        if chain_anchor is None and receiver_team == implied_receiver_team:
            corrected.append(event)
            continue

        event_type = (
            "pass_candidate"
            if receiver_team == sender_team
            else "turnover_candidate"
        )
        corrected.append(
            replace(
                event,
                event_type=event_type,
                team=sender_team,
                details=(
                    "Track-switch possession continuity preserved using "
                    "frame-level jersey evidence."
                    if chain_anchor is not None
                    else (
                        "Frame-level jersey evidence corrected a cross-team "
                        "player-track identity switch."
                    )
                ),
            )
        )
    consistent: list[PredictedEvent] = []
    established_owner: str | None = None
    established_at: float | None = None
    for event in _deduplicate_receptions(corrected):
        within_chain = (
            established_owner is not None
            and established_at is not None
            and event.clip_seconds - established_at
            <= maximum_chain_seconds + 1e-9
        )
        if (
            within_chain
            and event.event_type == "turnover_candidate"
            and event.team != established_owner
        ):
            continue
        consistent.append(event)
        if event.event_type == "turnover_candidate":
            if (
                event.details.startswith(
                    "Frame-level jersey evidence corrected"
                )
                or (within_chain and event.team == established_owner)
            ):
                established_owner = other_team(event.team)
                established_at = event.completion_seconds
            else:
                established_owner = None
                established_at = None
        elif not within_chain:
            established_owner = None
            established_at = None
    return consistent


def infer_deferred_contested_turnovers(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    observations: Iterable[PossessionObservation] = (),
    *,
    minimum_speed_pixels_per_second: float,
    receiver_window_seconds: float = 0.4,
    contact_lookback_seconds: float = 6.0,
    control_window_seconds: float = 0.6,
) -> list[PredictedEvent]:
    source = list(events)
    controls = list(observations)
    motion = _ball_motion_evidence(balls)
    inferred: list[PredictedEvent] = []
    corrected_ids: set[int] = set()
    superseded_ids: set[int] = set()
    for event_index, event in enumerate(source):
        if event.event_type not in {
            "pass_candidate",
            "turnover_candidate",
        }:
            continue
        receiver_team, confidence, support = _receiver_team_evidence(
            players,
            balls,
            event.completion_seconds,
            window_seconds=receiver_window_seconds,
        )
        if (
            receiver_team is None
            or receiver_team == event.team
            or confidence < 0.8
            or support < 3.0
        ):
            continue
        completion = event.completion_seconds or event.clip_seconds
        contact_seconds = _contested_contact_seconds(
            players,
            balls,
            motion,
            first_seconds=completion - contact_lookback_seconds,
            last_seconds=event.clip_seconds,
            first_team=event.team,
            second_team=receiver_team,
            minimum_speed_pixels_per_second=(
                minimum_speed_pixels_per_second
            ),
        )
        if contact_seconds is None:
            continue
        losing_control = any(
            observation.team == event.team
            and observation.control_ratio <= 0.5
            and contact_seconds - control_window_seconds
            <= observation.clip_seconds
            <= contact_seconds
            for observation in controls
        )
        gaining_control = any(
            observation.team == receiver_team
            and observation.control_ratio <= 0.5
            and contact_seconds
            <= observation.clip_seconds
            <= completion + receiver_window_seconds
            for observation in controls
        )
        if not losing_control or not gaining_control:
            continue
        contact_receivers = {
            prior.to_player_track_id
            for prior in source
            if prior.event_type == "pass_candidate"
            and prior.team == event.team
            and prior.to_player_track_id is not None
            and abs(
                (prior.completion_seconds or prior.clip_seconds)
                - contact_seconds
            )
            <= 0.12
        }
        if contact_receivers and any(
            prior.event_type == "pass_candidate"
            and prior.team == event.team
            and prior.from_player_track_id in contact_receivers
            and contact_seconds
            < (prior.completion_seconds or prior.clip_seconds)
            <= event.clip_seconds
            for prior in source
        ):
            continue
        if any(
            prior.event_type == "turnover_candidate"
            and abs(
                (prior.completion_seconds or prior.clip_seconds)
                - contact_seconds
            )
            <= 1.0
            for prior in [*source, *inferred]
        ):
            continue
        inferred.append(
            PredictedEvent(
                event_type="turnover_candidate",
                clip_seconds=round(contact_seconds, 3),
                team=event.team,
                from_player_track_id=None,
                to_player_track_id=None,
                confidence=0.6,
                details=(
                    "A contested direction-changing contact was resolved "
                    "retrospectively by sustained opposing-team control."
                ),
                completion_seconds=round(contact_seconds, 3),
            )
        )
        spanning_events = [
            candidate
            for candidate in source
            if candidate.event_type == "pass_candidate"
            and candidate.completion_seconds is not None
            and candidate.clip_seconds
            < contact_seconds
            < candidate.completion_seconds
        ]
        for spanning in spanning_events:
            replacement_seconds = next(
                (
                    float(ball["clip_seconds"])
                    for source_frame, frame_balls in sorted(balls.items())
                    for ball in frame_balls
                    if spanning.clip_seconds
                    <= float(ball["clip_seconds"])
                    < contact_seconds
                    and spanning.team
                    in _nearby_ball_teams(
                        players.get(source_frame, []),
                        ball,
                        maximum_box_distance_heights=0.25,
                    )
                ),
                None,
            )
            if replacement_seconds is not None:
                inferred.append(
                    replace(
                        spanning,
                        to_player_track_id=None,
                        completion_seconds=round(replacement_seconds, 3),
                        details=(
                            "Receiver validation recovered the controlled "
                            "touch before a later contested turnover."
                        ),
                    )
                )
        if event.event_type == "pass_candidate":
            source[event_index] = replace(
                event,
                team=receiver_team,
                details=(
                    "Deferred receiver validation confirmed the new "
                    f"possession team. {event.details}"
                ),
            )
            corrected_ids.add(event_index)
        else:
            superseded_ids.add(event_index)
        prior_track_id: int | None = None
        prior_contact_seconds = contact_seconds
        for source_frame, frame_balls in sorted(balls.items()):
            for ball in frame_balls:
                timestamp = float(ball["clip_seconds"])
                if (
                    timestamp < contact_seconds + 0.8
                    or timestamp > completion - 0.8
                ):
                    continue
                receiver_track_id = _nearby_ball_team_track(
                    players.get(source_frame, []),
                    ball,
                    receiver_team,
                    maximum_box_distance_heights=0.25,
                )
                if (
                    receiver_track_id is None
                    or receiver_track_id == prior_track_id
                    or timestamp - prior_contact_seconds < 0.6
                ):
                    continue
                inferred.append(
                    PredictedEvent(
                        event_type="pass_candidate",
                        clip_seconds=round(timestamp, 3),
                        team=receiver_team,
                        from_player_track_id=prior_track_id,
                        to_player_track_id=receiver_track_id,
                        confidence=0.55,
                        details=(
                            "Deferred possession validation recovered an "
                            "intermediate same-team receiver contact."
                        ),
                        completion_seconds=round(timestamp, 3),
                    )
                )
                prior_track_id = receiver_track_id
                prior_contact_seconds = timestamp

    turnover_times = [
        event.completion_seconds or event.clip_seconds
        for event in inferred
        if event.event_type == "turnover_candidate"
    ]
    accepted = [
        event
        for index, event in enumerate(source)
        if index not in superseded_ids
        and (
            index in corrected_ids
            or not (
                event.event_type == "pass_candidate"
                and event.completion_seconds is not None
                and any(
                    event.clip_seconds < turnover < event.completion_seconds
                    for turnover in turnover_times
                )
            )
        )
    ]
    return _deduplicate_receptions([*accepted, *inferred])


def propagate_deferred_possession_chains(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
) -> list[PredictedEvent]:
    source = sorted(events, key=lambda event: event.clip_seconds)
    motion = _ball_motion_evidence(balls)
    additions: list[PredictedEvent] = []
    for anchor_index, anchor in enumerate(source):
        if not anchor.details.startswith("Deferred receiver validation"):
            continue
        possession_team = anchor.team
        previous = anchor
        for event_index in range(anchor_index + 1, len(source)):
            event = source[event_index]
            if event.event_type == "turnover_candidate":
                if event.team == possession_team:
                    break
                continue
            if event.event_type != "pass_candidate":
                continue
            chain_continues = (
                event.from_player_track_id is not None
                and (
                    event.from_player_track_id
                    == previous.to_player_track_id
                    or (
                        previous.to_player_track_id is None
                        and event.from_player_track_id
                        == previous.from_player_track_id
                    )
                )
            )
            if not chain_continues:
                break
            if event.team != possession_team:
                opposing_team = event.team
                contact_seconds = _contested_contact_seconds(
                    players,
                    balls,
                    motion,
                    first_seconds=(
                        (previous.completion_seconds or previous.clip_seconds)
                        - 1.0
                    ),
                    last_seconds=event.clip_seconds,
                    first_team=possession_team,
                    second_team=opposing_team,
                    minimum_speed_pixels_per_second=(
                        minimum_speed_pixels_per_second
                    ),
                )
                if contact_seconds is not None:
                    source[event_index] = replace(
                        event,
                        team=possession_team,
                        details=(
                            "The incoming pass completed before the linked "
                            f"contested turnover. {event.details}"
                        ),
                    )
                    additions.append(
                        PredictedEvent(
                            event_type="turnover_candidate",
                            clip_seconds=round(contact_seconds, 3),
                            team=possession_team,
                            from_player_track_id=(
                                previous.to_player_track_id
                            ),
                            to_player_track_id=event.from_player_track_id,
                            confidence=0.6,
                            details=(
                                "A linked possession chain ended at a "
                                "contested direction-changing contact."
                            ),
                            completion_seconds=round(contact_seconds, 3),
                        )
                    )
                    break
                source[event_index] = replace(
                    event,
                    team=possession_team,
                    details=(
                        "Possession-chain validation prevented a silent team "
                        f"change. {event.details}"
                    ),
                )
                event = source[event_index]
            previous = event
    return _deduplicate_receptions([*source, *additions])


def suppress_overlapping_opponent_handoffs(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    maximum_box_distance_heights: float = 1.2,
) -> list[PredictedEvent]:
    accepted: list[PredictedEvent] = []
    for event in events:
        completion = event.completion_seconds
        if (
            event.event_type != "pass_candidate"
            or completion is None
            or event.from_player_track_id is None
            or event.to_player_track_id is None
            or not event.details.startswith(
                "Possession-chain validation prevented a silent team change"
            )
        ):
            accepted.append(event)
            continue
        release_ball = min(
            (
                ball
                for frame_balls in balls.values()
                for ball in frame_balls
            ),
            key=lambda ball: abs(float(ball["clip_seconds"]) - event.clip_seconds),
        )
        completion_ball = min(
            (
                ball
                for frame_balls in balls.values()
                for ball in frame_balls
            ),
            key=lambda ball: abs(float(ball["clip_seconds"]) - completion),
        )
        sender_team = next(
            (
                str(player["team"])
                for player in players.get(
                    int(release_ball["source_frame"]), []
                )
                if int(player["track_id"]) == event.from_player_track_id
            ),
            None,
        )
        receiver_team = next(
            (
                str(player["team"])
                for player in players.get(
                    int(completion_ball["source_frame"]), []
                )
                if int(player["track_id"]) == event.to_player_track_id
            ),
            None,
        )
        nearby_team_tracks = [
            (
                hypot(
                    max(
                        float(player["x1"]) - float(completion_ball["x"]),
                        0.0,
                        float(completion_ball["x"]) - float(player["x2"]),
                    ),
                    max(
                        float(player["y1"]) - float(completion_ball["y"]),
                        0.0,
                        float(completion_ball["y"]) - float(player["y2"]),
                    ),
                )
                / max(1.0, float(player["y2"]) - float(player["y1"])),
                int(player["track_id"]),
            )
            for player in players.get(int(completion_ball["source_frame"]), [])
            if str(player.get("team")) == event.team
        ]
        nearby_team_track = next(
            (
                track_id
                for distance, track_id in sorted(nearby_team_tracks)
                if distance <= maximum_box_distance_heights
            ),
            None,
        )
        if (
            sender_team != event.team
            and receiver_team != event.team
            and nearby_team_track is not None
            and nearby_team_track != event.to_player_track_id
        ):
            continue
        accepted.append(event)
    return accepted


def reconcile_delayed_turnover_chains(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    maximum_lookback_seconds: float = 6.0,
    minimum_supported_intermediary_events: int = 1,
) -> list[PredictedEvent]:
    source = sorted(events, key=lambda event: event.clip_seconds)
    motion = _ball_motion_evidence(balls)
    teams = {
        str(player.get("team"))
        for frame_players in players.values()
        for player in frame_players
    }
    team_pair = (
        ("red", "black")
        if teams & {"red", "black"}
        else ("blue", "white")
    )

    def other_team(team: str | None) -> str | None:
        if team == team_pair[0]:
            return team_pair[1]
        if team == team_pair[1]:
            return team_pair[0]
        return None

    def local_track_team(track_id: int | None, timestamp: float | None) -> str | None:
        if track_id is None or timestamp is None:
            return None
        labels: list[str] = []
        profile = "red-black" if team_pair == ("red", "black") else "blue-white"
        for frame_players in players.values():
            for player in frame_players:
                if (
                    int(player["track_id"]) != track_id
                    or abs(float(player["clip_seconds"]) - timestamp) > 0.3
                ):
                    continue
                scores = player.get("color_scores")
                if not isinstance(scores, dict):
                    continue
                label = classify_color_scores(scores, team_profile=profile)
                if label in team_pair:
                    labels.append(label)
        if not labels:
            return None
        label, count = Counter(labels).most_common(1)[0]
        return label if count / len(labels) >= 0.6 else None

    for turnover_index, turnover in enumerate(source):
        if (
            turnover.event_type != "turnover_candidate"
            or turnover.team not in team_pair
            or turnover.to_player_track_id is None
            or turnover.completion_seconds is None
        ):
            continue
        winner = other_team(turnover.team)
        if winner is None:
            continue
        completion = turnover.completion_seconds
        intermediary_indices = [
            index
            for index, event in enumerate(source)
            if event.event_type == "pass_candidate"
            and event.team == turnover.team
            and event.completion_seconds is not None
            and completion - maximum_lookback_seconds
            <= event.clip_seconds
            < completion
        ]
        if not intermediary_indices:
            continue
        supported = 0
        for index in intermediary_indices:
            intermediary = source[index]
            endpoint_teams = {
                team
                for team in (
                    local_track_team(
                        intermediary.from_player_track_id,
                        intermediary.clip_seconds,
                    ),
                    local_track_team(
                        intermediary.to_player_track_id,
                        intermediary.completion_seconds,
                    ),
                )
                if team is not None
            }
            if winner in endpoint_teams and turnover.team not in endpoint_teams:
                supported += 1
        if supported < minimum_supported_intermediary_events:
            continue
        first_release = min(source[index].clip_seconds for index in intermediary_indices)
        contact_candidates: list[tuple[float, float]] = []
        for (ball_track_id, source_frame), (speed, direction_cosine) in motion.items():
            ball = next(
                (
                    point
                    for point in balls.get(source_frame, [])
                    if int(point["track_id"]) == ball_track_id
                ),
                None,
            )
            if ball is None:
                continue
            timestamp = float(ball["clip_seconds"])
            if (
                timestamp < completion - maximum_lookback_seconds
                or timestamp > first_release
                or speed < minimum_speed_pixels_per_second
                or direction_cosine > 0.5
                or winner
                not in _nearby_ball_teams(
                    players.get(source_frame, []),
                    ball,
                    maximum_box_distance_heights=0.25,
                )
            ):
                continue
            contact_candidates.append((timestamp, direction_cosine))
        if not contact_candidates:
            continue
        contact = min(contact_candidates)[0]
        source[turnover_index] = replace(
            turnover,
            clip_seconds=round(contact, 3),
            completion_seconds=round(contact, 3),
            details=(
                "Earlier direction-changing control resolved a delayed "
                f"possession-team transition. {turnover.details}"
            ),
        )
        for index in intermediary_indices:
            source[index] = replace(
                source[index],
                team=winner,
                details=(
                    "Possession-chain validation corrected a delayed team "
                    f"transition. {source[index].details}"
                ),
            )
    return _deduplicate_receptions(source)


def reconcile_unconfirmed_turnovers(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    *,
    maximum_receiver_control_ratio: float = 1.0,
    minimum_unconfirmed_seconds: float = 0.8,
) -> list[PredictedEvent]:
    """Keep possession with the releasing team until opponent control is clear."""
    segments = list(possession_segments)
    reconciled: list[PredictedEvent] = []
    for event in events:
        if (
            event.event_type != "turnover_candidate"
            or event.to_player_track_id is None
            or event.completion_seconds is None
        ):
            reconciled.append(event)
            continue
        receiver = next(
            (
                segment
                for segment in segments
                if (
                    segment.player_track_id == event.to_player_track_id
                    and segment.start_seconds
                    <= event.completion_seconds
                    <= segment.end_seconds
                )
            ),
            None,
        )
        if (
            receiver is None
            or receiver.end_seconds - receiver.start_seconds
            < minimum_unconfirmed_seconds - 1e-9
            or any(
                observation.control_ratio <= maximum_receiver_control_ratio
                for observation in receiver.observations
            )
        ):
            reconciled.append(event)
            continue
        reconciled.append(
            replace(
                event,
                event_type="pass_candidate",
                to_player_track_id=None,
                details=(
                    "Opponent proximity never became controlled possession; "
                    f"the releasing {event.team} team retained the ball. "
                    f"{event.details}"
                ),
            )
        )
    return _deduplicate_receptions(
        [
            event
            for event in reconciled
            if not (
                event.event_type == "pass_candidate"
                and event.to_player_track_id is not None
                and any(
                    retained.details.startswith(
                        "Opponent proximity never became controlled"
                    )
                    and retained.from_player_track_id
                    == event.to_player_track_id
                    and abs(retained.clip_seconds - (event.completion_seconds or -1))
                    <= 0.04
                    for retained in reconciled
                )
            )
        ]
    )


def reconcile_deflected_turnover_sequences(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    *,
    maximum_sequence_seconds: float = 1.8,
    maximum_control_ratio: float = 0.35,
) -> list[PredictedEvent]:
    """Move a premature contested turnover to the opponent's first clear control."""
    source = list(events)
    segments = list(possession_segments)
    removed: set[int] = set()
    replacements: dict[int, PredictedEvent] = {}

    for turnover_index, turnover in enumerate(source):
        turnover_time = turnover.completion_seconds
        if (
            turnover.event_type != "turnover_candidate"
            or turnover_time is None
        ):
            continue
        retained = next(
            (
                event
                for event in source
                if event.event_type == "pass_candidate"
                and event.team == turnover.team
                and event.completion_seconds is not None
                and turnover_time < event.completion_seconds
                <= turnover_time + maximum_sequence_seconds
            ),
            None,
        )
        if retained is None:
            continue
        retained_time = retained.completion_seconds
        gained_index = next(
            (
                index
                for index, event in enumerate(source)
                if event.event_type == "pass_candidate"
                and event.team != turnover.team
                and event.to_player_track_id is not None
                and event.completion_seconds is not None
                and retained_time <= event.completion_seconds
                <= turnover_time + maximum_sequence_seconds
                and event.from_player_track_id == retained.from_player_track_id
            ),
            None,
        )
        if gained_index is None:
            continue
        gained = source[gained_index]
        gained_time = gained.completion_seconds
        controlled = any(
            segment.team == gained.team
            and segment.player_track_id == gained.to_player_track_id
            and segment.start_seconds <= gained_time <= segment.end_seconds
            and any(
                observation.control_ratio <= maximum_control_ratio
                for observation in segment.observations
                if abs(observation.clip_seconds - gained_time) <= 0.2
            )
            for segment in segments
        )
        if not controlled:
            continue
        removed.add(turnover_index)
        replacements[gained_index] = replace(
            gained,
            event_type="turnover_candidate",
            clip_seconds=round(gained_time, 3),
            team=turnover.team,
            details=(
                "An initial opponent deflection did not end possession; "
                "the turnover occurred at the opponent's first controlled touch."
            ),
        )

    return [
        replacements.get(index, event)
        for index, event in enumerate(source)
        if index not in removed
    ]


def suppress_uncontrolled_opponent_turnovers(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    possession_segments: Iterable[PossessionSegment] = (),
    *,
    maximum_box_distance_heights: float = 0.25,
    maximum_continuity_seconds: float = 2.0,
) -> list[PredictedEvent]:
    """Reject turnovers where only the current team remains in direct contact."""
    segments = list(possession_segments)
    accepted: list[PredictedEvent] = []
    retained_team: str | None = None
    retained_at: float | None = None
    for event in events:
        completion = event.completion_seconds
        if (
            retained_team is not None
            and retained_at is not None
            and event.event_type == "pass_candidate"
            and event.team != retained_team
            and event.clip_seconds - retained_at <= maximum_continuity_seconds
        ):
            event = replace(
                event,
                team=retained_team,
                details=(
                    "Possession continuity prevented a silent team change after "
                    f"the prior turnover was rejected. {event.details}"
                ),
            )
            retained_team = None
            retained_at = None
        if (
            event.event_type != "turnover_candidate"
            or event.to_player_track_id is None
            or completion is None
        ):
            accepted.append(event)
            continue
        if event.details.startswith(
            "Frame-level jersey evidence corrected"
        ):
            accepted.append(event)
            continue
        retained_control = next(
            (
                segment
                for segment in segments
                if (
                    segment.team == event.team
                    and segment.start_seconds <= completion
                    and segment.end_seconds > completion + 0.04
                )
            ),
            None,
        )
        if retained_control is not None:
            retained_team = event.team
            retained_at = completion
            continue
        ball_and_players = next(
            (
                (ball, players.get(source_frame, []))
                for source_frame, frame_balls in balls.items()
                for ball in frame_balls
                if abs(float(ball["clip_seconds"]) - completion) <= 0.04
            ),
            None,
        )
        if ball_and_players is None:
            accepted.append(event)
            continue
        ball, frame_players = ball_and_players
        nearby_teams: set[str] = set()
        for player in frame_players:
            height = max(1.0, float(player["y2"]) - float(player["y1"]))
            horizontal = max(
                float(player["x1"]) - float(ball["x"]),
                0.0,
                float(ball["x"]) - float(player["x2"]),
            )
            vertical = max(
                float(player["y1"]) - float(ball["y"]),
                0.0,
                float(ball["y"]) - float(player["y2"]),
            )
            if hypot(horizontal, vertical) / height <= maximum_box_distance_heights:
                nearby_teams.add(str(player.get("team")))
        if nearby_teams == {event.team}:
            retained_team = event.team
            retained_at = completion
            continue
        accepted.append(event)
    return accepted


def _contested_contact_seconds(
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    motion: dict[tuple[int, int], tuple[float, float]],
    *,
    first_seconds: float,
    last_seconds: float,
    first_team: str,
    second_team: str,
    minimum_speed_pixels_per_second: float,
) -> float | None:
    candidates: list[tuple[float, float]] = []
    for (track_id, source_frame), (speed, direction_cosine) in motion.items():
        ball = next(
            (
                candidate
                for candidate in balls.get(source_frame, [])
                if int(candidate["track_id"]) == track_id
            ),
            None,
        )
        if ball is None:
            continue
        timestamp = float(ball["clip_seconds"])
        if (
            timestamp < first_seconds
            or timestamp > last_seconds
            or speed < minimum_speed_pixels_per_second
            or direction_cosine > 0.5
        ):
            continue
        nearby_teams = _nearby_ball_teams(
            players.get(source_frame, []),
            ball,
            maximum_box_distance_heights=0.25,
        )
        if first_team in nearby_teams and second_team in nearby_teams:
            candidates.append((direction_cosine, timestamp))
    return min(candidates)[1] if candidates else None


def _receiver_team_evidence(
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    timestamp: float | None,
    *,
    window_seconds: float,
) -> tuple[str | None, float, float]:
    if timestamp is None:
        return None, 0.0, 0.0
    teams = {
        str(player.get("team"))
        for frame_players in players.values()
        for player in frame_players
    }
    team_profile = (
        "red-black"
        if teams & {"red", "black"}
        else "blue-white"
    )
    eligible_teams = (
        {"red", "black"}
        if team_profile == "red-black"
        else {"blue", "white"}
    )
    scores: dict[str, float] = defaultdict(float)
    for source_frame, frame_balls in balls.items():
        for ball in frame_balls:
            if abs(float(ball["clip_seconds"]) - timestamp) > window_seconds:
                continue
            for player in players.get(source_frame, []):
                height = max(
                    1.0,
                    float(player["y2"]) - float(player["y1"]),
                )
                ratio = hypot(
                    (float(player["x1"]) + float(player["x2"])) / 2
                    - float(ball["x"]),
                    float(player["y2"]) - float(ball["y"]),
                ) / height
                if ratio > 1.8:
                    continue
                color_scores = player.get("color_scores")
                local_team = (
                    classify_color_scores(
                        color_scores,
                        team_profile=team_profile,
                    )
                    if isinstance(color_scores, dict)
                    else "unknown"
                )
                if local_team in eligible_teams:
                    scores[local_team] += 1 / max(0.25, ratio) ** 2
    if not scores:
        return None, 0.0, 0.0
    team = max(scores, key=scores.get)
    support = sum(scores.values())
    return team, scores[team] / support, support


def _nearby_ball_teams(
    players: Iterable[dict[str, Any]],
    ball: dict[str, Any],
    *,
    maximum_box_distance_heights: float,
) -> set[str]:
    source = list(players)
    teams = {str(player.get("team")) for player in source}
    team_profile = (
        "red-black"
        if teams & {"red", "black"}
        else "blue-white"
    )
    eligible_teams = (
        {"red", "black"}
        if team_profile == "red-black"
        else {"blue", "white"}
    )
    nearby: set[str] = set()
    for player in source:
        height = max(1.0, float(player["y2"]) - float(player["y1"]))
        horizontal = max(
            float(player["x1"]) - float(ball["x"]),
            0.0,
            float(ball["x"]) - float(player["x2"]),
        )
        vertical = max(
            float(player["y1"]) - float(ball["y"]),
            0.0,
            float(ball["y"]) - float(player["y2"]),
        )
        if hypot(horizontal, vertical) / height > maximum_box_distance_heights:
            continue
        color_scores = player.get("color_scores")
        local_team = (
            classify_color_scores(color_scores, team_profile=team_profile)
            if isinstance(color_scores, dict)
            else "unknown"
        )
        team = (
            local_team
            if local_team in eligible_teams
            else str(player.get("team"))
        )
        if team in eligible_teams:
            nearby.add(team)
    return nearby


def _nearby_ball_team_track(
    players: Iterable[dict[str, Any]],
    ball: dict[str, Any],
    team: str,
    *,
    maximum_box_distance_heights: float,
) -> int | None:
    team_profile = (
        "red-black"
        if team in {"red", "black"}
        else "blue-white"
    )
    candidates: list[tuple[float, int]] = []
    for player in players:
        color_scores = player.get("color_scores")
        local_team = (
            classify_color_scores(color_scores, team_profile=team_profile)
            if isinstance(color_scores, dict)
            else "unknown"
        )
        if local_team != team:
            continue
        height = max(1.0, float(player["y2"]) - float(player["y1"]))
        horizontal = max(
            float(player["x1"]) - float(ball["x"]),
            0.0,
            float(ball["x"]) - float(player["x2"]),
        )
        vertical = max(
            float(player["y1"]) - float(ball["y"]),
            0.0,
            float(ball["y"]) - float(player["y2"]),
        )
        distance = hypot(horizontal, vertical) / height
        if distance <= maximum_box_distance_heights:
            candidates.append((distance, int(player["track_id"])))
    return min(candidates)[1] if candidates else None


def infer_flight_transfer_events(
    balls: dict[int, list[dict[str, Any]]],
    possession_segments: Iterable[PossessionSegment],
    *,
    control_observations: Iterable[PossessionObservation] | None = None,
    minimum_speed_pixels_per_second: float,
    maximum_step_seconds: float,
    debounce_seconds: float,
    sender_lookback_seconds: float,
    receiver_window_seconds: float,
    minimum_sender_observations: int = 1,
    minimum_receiver_observations: int = 1,
    maximum_single_observation_loss_seconds: float = 1.2,
    maximum_intervening_opponent_seconds: float = 0.4,
) -> list[PredictedEvent]:
    tracks: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame_points in balls.values():
        for point in frame_points:
            tracks[int(point["track_id"])].append(point)

    releases: list[tuple[float, float]] = []
    for points in tracks.values():
        observed = sorted(
            (
                point
                for point in points
                if not point.get("interpolated", False)
            ),
            key=lambda point: float(point["clip_seconds"]),
        )
        for first, second in zip(observed, observed[1:]):
            elapsed = float(second["clip_seconds"]) - float(
                first["clip_seconds"]
            )
            if elapsed <= 0 or elapsed > maximum_step_seconds:
                continue
            speed = (
                hypot(
                    float(second["x"]) - float(first["x"]),
                    float(second["y"]) - float(first["y"]),
                )
                / elapsed
            )
            if speed >= minimum_speed_pixels_per_second:
                releases.append((float(first["clip_seconds"]), speed))

    grouped_releases: list[tuple[float, float]] = []
    for release in sorted(releases):
        if (
            grouped_releases
            and release[0] - grouped_releases[-1][0] < debounce_seconds
        ):
            if release[1] > grouped_releases[-1][1]:
                grouped_releases[-1] = release
            continue
        grouped_releases.append(release)

    segments = list(possession_segments)
    controls = list(control_observations or [])
    motion = _ball_motion_evidence(balls)
    events: list[PredictedEvent] = []
    for timestamp, speed in grouped_releases:
        senders = [
            segment
            for segment in segments
            if segment.start_seconds <= timestamp
            and segment.end_seconds >= timestamp - sender_lookback_seconds
            and timestamp - segment.end_seconds
            <= min(sender_lookback_seconds, debounce_seconds)
            and (
                timestamp - segment.end_seconds <= maximum_step_seconds
                or len(segment.observations) >= 2
            )
            and len(segment.observations) >= minimum_sender_observations
            and not any(
                observation.clip_seconds > timestamp + maximum_step_seconds
                and observation.control_ratio <= 1.0
                for observation in segment.observations
            )
            and not any(
                candidate.team != segment.team
                and max(
                    segment.end_seconds,
                    timestamp - maximum_intervening_opponent_seconds,
                )
                <= candidate.end_seconds
                and candidate.start_seconds <= timestamp
                and (
                    len(candidate.observations) >= 3
                    or candidate.end_seconds - candidate.start_seconds >= 0.4
                )
                for candidate in segments
            )
            and _segment_has_reception_evidence(
                segment, balls, motion_evidence=motion
            )
        ]
        if not senders:
            continue
        sender = max(senders, key=lambda segment: segment.end_seconds)

        def reception_time(segment: PossessionSegment) -> float | None:
            maximum_reception_ratio = 1.2 if speed >= 300.0 else 1.0
            observed = next(
                (
                    observation.clip_seconds
                    for observation in segment.observations
                    if observation.clip_seconds >= timestamp
                    and observation.control_ratio <= maximum_reception_ratio
                ),
                None,
            )
            if observed is not None:
                return observed
            if (
                segment.start_seconds >= timestamp
                and _segment_has_reception_evidence(
                    segment, balls, motion_evidence=motion
                )
            ):
                return segment.start_seconds
            return None

        receivers = [
            (segment, reception_seconds)
            for segment in segments
            if (
                reception_seconds := reception_time(segment)
            )
            is not None
            and timestamp <= reception_seconds
            <= timestamp + receiver_window_seconds
            and segment.player_track_id != sender.player_track_id
            and (
                len(segment.observations) >= minimum_receiver_observations
                or (
                    segment.team == sender.team
                    and (
                        _segment_has_strong_control_evidence(segment)
                        or (
                            speed >= 300.0
                            and len(segment.observations) >= 2
                        )
                    )
                    and not any(
                        candidate.team != segment.team
                        and segment.start_seconds
                        < candidate.start_seconds
                        <= (
                            segment.start_seconds
                            + maximum_single_observation_loss_seconds
                        )
                        for candidate in segments
                    )
                )
            )
        ]
        if not receivers:
            continue
        receiver, reception_seconds = min(
            receivers,
            key=lambda candidate: candidate[1],
        )
        if (
            sender.team == receiver.team
            and any(
                segment.team != sender.team
                and timestamp < segment.start_seconds < reception_seconds
                and (
                    len(segment.observations) >= 3
                    or segment.end_seconds - segment.start_seconds >= 0.4
                )
                for segment in segments
            )
        ):
            continue
        if (
            sender.team != receiver.team
            and sender.observations[-1].control_ratio > 0.5
        ):
            continue
        completion_seconds = _contact_onset_before_control(
            balls,
            release_seconds=timestamp,
            receiver=receiver,
            motion_evidence=motion,
        )
        if completion_seconds < receiver.start_seconds:
            reception_details = (
                f"Ball release at {speed:.2f} pixels/second reached a "
                f"direction-changing contact after "
                f"{completion_seconds - timestamp:.2f}s; {receiver.team} "
                f"control was independently established after "
                f"{receiver.start_seconds - timestamp:.2f}s."
            )
        else:
            reception_details = (
                f"Ball release at {speed:.2f} pixels/second followed by "
                f"{receiver.team} control after "
                f"{receiver.start_seconds - timestamp:.2f}s."
            )
        event_type = (
            "pass_candidate"
            if sender.team == receiver.team
            else "turnover_candidate"
        )
        events.append(
            PredictedEvent(
                event_type=event_type,
                clip_seconds=round(timestamp, 3),
                team=sender.team,
                from_player_track_id=sender.player_track_id,
                to_player_track_id=receiver.player_track_id,
                confidence=round(min(0.9, 0.45 + speed / 1000), 4),
                details=reception_details,
                completion_seconds=round(completion_seconds, 3),
            )
        )
    return _deduplicate_receptions(events)


def _segment_has_control_evidence(
    segment: PossessionSegment,
    *,
    maximum_control_ratio: float = 1.0,
) -> bool:
    return any(
        observation.control_ratio <= maximum_control_ratio
        for observation in segment.observations
    )


def _segment_has_strong_control_evidence(
    segment: PossessionSegment,
    *,
    maximum_control_ratio: float = 0.5,
) -> bool:
    return any(
        observation.control_ratio <= maximum_control_ratio
        for observation in segment.observations
    )


def _segment_has_reception_evidence(
    segment: PossessionSegment,
    balls: dict[int, list[dict[str, Any]]],
    *,
    maximum_contact_direction_cosine: float = -0.25,
    motion_evidence: dict[tuple[int, int], tuple[float, float]] | None = None,
) -> bool:
    if _segment_has_control_evidence(segment):
        return True
    observation_frames = {
        observation.source_frame for observation in segment.observations
    }
    motion = (
        _ball_motion_evidence(balls)
        if motion_evidence is None
        else motion_evidence
    )
    return any(
        source_frame in observation_frames
        and direction_cosine <= maximum_contact_direction_cosine
        for (_, source_frame), (_, direction_cosine) in motion.items()
    )


def suppress_transient_proximity_receptions(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    balls: dict[int, list[dict[str, Any]]],
) -> list[PredictedEvent]:
    segments = list(possession_segments)
    motion = _ball_motion_evidence(balls)
    return [
        event
        for event in events
        if not (
            event.completion_seconds is not None
            and event.to_player_track_id is not None
            and event.confidence < 0.75
            and any(
                segment.player_track_id == event.to_player_track_id
                and abs(segment.start_seconds - event.completion_seconds)
                <= 1e-9
                and not _segment_has_reception_evidence(
                    segment,
                    balls,
                    motion_evidence=motion,
                )
                for segment in segments
            )
        )
    ]


def _contact_onset_before_control(
    balls: dict[int, list[dict[str, Any]]],
    *,
    release_seconds: float,
    receiver: PossessionSegment,
    maximum_confirmation_lag_seconds: float = 0.4,
    maximum_direction_cosine: float = -0.8,
    motion_evidence: dict[tuple[int, int], tuple[float, float]] | None = None,
) -> float:
    if not _segment_has_strong_control_evidence(receiver):
        return receiver.start_seconds

    tracks: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame_points in balls.values():
        for point in frame_points:
            if not point.get("interpolated", False):
                tracks[int(point["track_id"])].append(point)
    motion = (
        _ball_motion_evidence(balls)
        if motion_evidence is None
        else motion_evidence
    )
    candidates: list[float] = []
    for track_id, points in tracks.items():
        ordered = sorted(points, key=lambda point: float(point["clip_seconds"]))
        for previous, current in zip(ordered, ordered[1:]):
            current_seconds = float(current["clip_seconds"])
            if (
                current_seconds <= release_seconds
                or current_seconds > receiver.start_seconds
                or receiver.start_seconds - current_seconds
                > maximum_confirmation_lag_seconds
                or "source_frame" not in current
            ):
                continue
            evidence = motion.get((track_id, int(current["source_frame"])))
            if evidence is None or evidence[1] > maximum_direction_cosine:
                continue
            previous_seconds = float(previous["clip_seconds"])
            if previous_seconds > release_seconds:
                candidates.append(previous_seconds)
    return max(candidates, default=receiver.start_seconds)


def refine_weak_reception_completion_times(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    balls: dict[int, list[dict[str, Any]]] | None = None,
    *,
    maximum_confirmation_seconds: float = 0.6,
    maximum_extended_confirmation_seconds: float = 2.5,
    maximum_turnover_confirmation_seconds: float = 1.2,
    maximum_strong_control_ratio: float = 0.1,
    minimum_speed_pixels_per_second: float = 60.0,
    maximum_contact_direction_cosine: float = -0.1,
) -> list[PredictedEvent]:
    source = list(events)
    segments = list(possession_segments)
    motion = _ball_motion_evidence(balls or {})
    refined: list[PredictedEvent] = []
    for event in source:
        segment = next(
            (
                candidate
                for candidate in segments
                if event.to_player_track_id == candidate.player_track_id
                and event.completion_seconds == candidate.start_seconds
                and candidate.observations[0].control_ratio > 1.0
            ),
            None,
        )
        if segment is None:
            refined.append(event)
            continue
        if event.event_type == "pass_candidate":
            extended_controls = [
                observation
                for observation in segment.observations
                if observation.clip_seconds
                <= (
                    segment.start_seconds
                    + maximum_extended_confirmation_seconds
                )
            ]
            independent_controls = [
                observation
                for observation in extended_controls
                if observation.control_ratio <= maximum_strong_control_ratio
            ]
            sharp_contacts = [
                observation
                for observation in extended_controls
                if observation.control_ratio <= 0.5
                and (
                    evidence := next(
                        (
                            value
                            for (track_id, frame), value in motion.items()
                            if frame == observation.source_frame
                        ),
                        None,
                    )
                )
                is not None
                and evidence[0] >= minimum_speed_pixels_per_second
                and evidence[1] <= maximum_contact_direction_cosine
            ]
            sustained_confirmations = [
                following
                for current, following in zip(
                    extended_controls,
                    extended_controls[1:],
                )
                if current.control_ratio <= 0.5
                and following.control_ratio <= 0.5
                and following.clip_seconds - current.clip_seconds <= 0.4
            ]
            verified_controls = sorted(
                [*independent_controls, *sharp_contacts],
                key=lambda observation: observation.clip_seconds,
            )
            strong_controls = verified_controls or sustained_confirmations
        else:
            strong_controls = [
                observation
                for observation in segment.observations
                if observation.clip_seconds
                <= (
                    segment.start_seconds
                    + maximum_turnover_confirmation_seconds
                )
                and observation.control_ratio <= 0.5
            ]
        if not strong_controls:
            refined.append(event)
            continue
        completion = strong_controls[0].clip_seconds
        if event.event_type == "turnover_candidate":
            outgoing = next(
                (
                    candidate
                    for candidate in source
                    if candidate.event_type == "pass_candidate"
                    and candidate.team == segment.team
                    and candidate.from_player_track_id == event.to_player_track_id
                    and completion < candidate.clip_seconds
                    <= completion + maximum_turnover_confirmation_seconds
                ),
                None,
            )
            definitive_control_before_release = any(
                observation.control_ratio <= 0.35
                and observation.clip_seconds <= outgoing.clip_seconds
                for observation in segment.observations
            ) if outgoing is not None else True
            if outgoing is not None and not definitive_control_before_release:
                completion = outgoing.clip_seconds
        refined.append(
            replace(
                event,
                completion_seconds=round(completion, 3),
                details=(
                    f"{event.details} Completion was refined from weak "
                    "proximity to the first clear controlled touch."
                ),
            )
        )
    return refined


def refine_delayed_turnovers_to_contested_decelerations(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    observations: Iterable[PossessionObservation],
    *,
    minimum_speed_pixels_per_second: float,
    maximum_lookback_seconds: float = 6.0,
    maximum_outgoing_speed_ratio: float = 0.35,
    nearby_window_seconds: float = 0.21,
    maximum_box_distance_heights: float = 1.5,
    losing_control_lookback_seconds: float = 0.6,
    maximum_control_ratio: float = 0.5,
) -> list[PredictedEvent]:
    """Move delayed turnovers back to an earlier contested ball-stopping touch."""
    source = sorted(events, key=lambda event: event.clip_seconds)
    possession_observations = list(observations)
    ball_points = sorted(
        (
            point
            for frame_points in balls.values()
            for point in frame_points
            if not point.get("interpolated", False)
        ),
        key=lambda point: float(point["clip_seconds"]),
    )
    refined: list[PredictedEvent] = []
    for event in source:
        completion = event.completion_seconds
        if (
            event.event_type != "turnover_candidate"
            or event.team not in {"red", "black", "blue", "white"}
            or completion is None
            or completion - event.clip_seconds < 1.0
        ):
            refined.append(event)
            continue
        winning_team = (
            "black"
            if event.team == "red"
            else "red"
            if event.team == "black"
            else "white"
            if event.team == "blue"
            else "blue"
        )
        prior_completions = [
            prior.completion_seconds or prior.clip_seconds
            for prior in source
            if prior.team == event.team
            and (prior.completion_seconds or prior.clip_seconds) < completion
        ]
        search_start = max(
            completion - maximum_lookback_seconds,
            max(prior_completions) if prior_completions else 0.0,
        )
        candidates: list[tuple[float, int]] = []
        for previous, current, following in zip(
            ball_points,
            ball_points[1:],
            ball_points[2:],
        ):
            timestamp = float(current["clip_seconds"])
            incoming_seconds = timestamp - float(previous["clip_seconds"])
            outgoing_seconds = float(following["clip_seconds"]) - timestamp
            if (
                timestamp < search_start
                or timestamp >= completion
                or incoming_seconds <= 0
                or outgoing_seconds <= 0
                or incoming_seconds > 0.3
                or outgoing_seconds > 0.3
            ):
                continue
            incoming_speed = hypot(
                float(current["x"]) - float(previous["x"]),
                float(current["y"]) - float(previous["y"]),
            ) / incoming_seconds
            outgoing_speed = hypot(
                float(following["x"]) - float(current["x"]),
                float(following["y"]) - float(current["y"]),
            ) / outgoing_seconds
            if (
                incoming_speed < minimum_speed_pixels_per_second * 2
                or outgoing_speed
                > incoming_speed * maximum_outgoing_speed_ratio
            ):
                continue
            nearby_teams: set[str] = set()
            for source_frame, frame_players in players.items():
                frame_balls = balls.get(source_frame, [])
                if not frame_balls or abs(
                    float(frame_balls[0]["clip_seconds"]) - timestamp
                ) > nearby_window_seconds:
                    continue
                nearby_teams.update(
                    _nearby_ball_teams(
                        frame_players,
                        frame_balls[0],
                        maximum_box_distance_heights=(
                            maximum_box_distance_heights
                        ),
                    )
                )
            losing_control = any(
                observation.team == event.team
                and observation.control_ratio <= maximum_control_ratio
                and 0
                <= timestamp - observation.clip_seconds
                <= losing_control_lookback_seconds
                for observation in possession_observations
            )
            winning_controls = [
                observation
                for observation in possession_observations
                if observation.team == winning_team
                and observation.control_ratio <= maximum_control_ratio
                and abs(observation.clip_seconds - timestamp)
                <= nearby_window_seconds
            ]
            if (
                event.team in nearby_teams
                and winning_team in nearby_teams
                and losing_control
                and winning_controls
            ):
                winner = min(
                    winning_controls,
                    key=lambda observation: (
                        abs(observation.clip_seconds - timestamp),
                        observation.control_ratio,
                    ),
                ).player_track_id
                candidates.append((timestamp, winner))
        if not candidates:
            refined.append(event)
            continue
        contact_seconds, receiver_track_id = min(candidates)
        refined.append(
            replace(
                event,
                clip_seconds=round(contact_seconds, 3),
                completion_seconds=round(contact_seconds, 3),
                to_player_track_id=receiver_track_id,
                details=(
                    "A contested ball deceleration coincided with the "
                    f"controlled {winning_team} touch that changed possession."
                ),
            )
        )
    return _deduplicate_receptions(refined)


def infer_opening_aerial_reception(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    rejected_boundary_intervals: Iterable[dict[str, Any]],
    *,
    maximum_reception_after_reentry_seconds: float = 1.0,
    maximum_following_turnover_seconds: float = 2.0,
    maximum_exchange_seconds: float = 3.0,
    maximum_exchange_control_ratio: float = 0.8,
) -> list[PredictedEvent]:
    """Recover a reception when a clip opens during an active aerial delivery."""
    source = list(events)
    opening_flight = next(
        (
            interval
            for interval in rejected_boundary_intervals
            if interval.get("starts_outside")
            and interval.get("reason") == "continuous_flight"
            and float(interval["start_seconds"]) <= 1e-9
            and interval.get("resumed_seconds") is not None
        ),
        None,
    )
    if opening_flight is None:
        return source
    resumed = float(opening_flight["resumed_seconds"])
    receivers = [
        observation
        for observation in observations
        if resumed
        <= observation.clip_seconds
        <= resumed + maximum_reception_after_reentry_seconds
    ]
    if not receivers:
        return source
    receiver = min(receivers, key=lambda observation: observation.clip_seconds)
    following_turnover = next(
        (
            event
            for event in sorted(source, key=lambda event: event.clip_seconds)
            if event.event_type == "turnover_candidate"
            and event.team == receiver.team
            and receiver.clip_seconds
            <= event.clip_seconds
            <= receiver.clip_seconds + maximum_following_turnover_seconds
        ),
        None,
    )
    if following_turnover is None:
        return source
    opponent_team = (
        "black"
        if receiver.team == "red"
        else "red"
        if receiver.team == "black"
        else "white"
        if receiver.team == "blue"
        else "blue"
    )
    opponent_controls = sorted(
        (
            observation
            for observation in observations
            if observation.team == opponent_team
            and receiver.clip_seconds < observation.clip_seconds
            <= receiver.clip_seconds + maximum_exchange_seconds
            and observation.control_ratio <= maximum_exchange_control_ratio
        ),
        key=lambda observation: observation.clip_seconds,
    )
    opponent_segments: list[list[PossessionObservation]] = []
    for observation in opponent_controls:
        if (
            opponent_segments
            and opponent_segments[-1][-1].player_track_id
            == observation.player_track_id
        ):
            opponent_segments[-1].append(observation)
        else:
            opponent_segments.append([observation])
    if (
        len(opponent_controls) < 3
        or len({item.player_track_id for item in opponent_controls}) < 2
        or len(opponent_segments) < 3
    ):
        return source
    first_opponent_control = opponent_segments[0][0]
    source = [
        (
            replace(
                event,
                completion_seconds=round(
                    first_opponent_control.clip_seconds, 3
                ),
                to_player_track_id=first_opponent_control.player_track_id,
                details=(
                    f"{event.details} Completion moved to the first "
                    "supported opponent control in the opening exchange."
                ),
            )
            if event is following_turnover
            else event
        )
        for event in source
    ]
    opening_pass = PredictedEvent(
        event_type="pass_candidate",
        clip_seconds=0.0,
        team=receiver.team,
        from_player_track_id=None,
        to_player_track_id=receiver.player_track_id,
        confidence=0.6,
        details=(
            "The clip opened during a continuous aerial delivery; the first "
            "controlled teammate contact completed the inherited pass."
        ),
        completion_seconds=round(receiver.clip_seconds, 3),
    )
    exchange_passes = [
        PredictedEvent(
            event_type="pass_candidate",
            clip_seconds=round(previous[-1].clip_seconds, 3),
            team=opponent_team,
            from_player_track_id=previous[-1].player_track_id,
            to_player_track_id=current[0].player_track_id,
            confidence=0.6,
            details=(
                "Consecutive direction-supported controls recovered a short "
                "same-team exchange after the opening aerial challenge."
            ),
            completion_seconds=round(current[0].clip_seconds, 3),
        )
        for previous, current in zip(
            opponent_segments,
            opponent_segments[1:],
        )
    ]
    return _deduplicate_receptions(
        [opening_pass, *source, *exchange_passes]
    )


def refine_one_touch_acceleration_receptions(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    minimum_transfer_seconds: float = 1.0,
    minimum_acceleration_ratio: float = 1.5,
    minimum_speed_multiplier: float = 2.0,
    minimum_speed_heights_per_second: float = 3.0,
    maximum_receiver_distance_heights: float = 1.5,
) -> list[PredictedEvent]:
    """Use an immediate receiver acceleration as a one-touch completion."""
    motion = _ball_motion_evidence(balls)
    ordered_frames = sorted(balls)
    prior_frame = {
        frame: ordered_frames[index - 1]
        for index, frame in enumerate(ordered_frames)
        if index
    }
    refined: list[PredictedEvent] = []
    for event in events:
        completion = event.completion_seconds
        if (
            event.event_type != "pass_candidate"
            or completion is None
            or event.to_player_track_id is None
            or completion - event.clip_seconds < minimum_transfer_seconds
        ):
            refined.append(event)
            continue
        contact = next(
            (
                (source_frame, ball, player)
                for source_frame, frame_balls in balls.items()
                for ball in frame_balls
                if abs(float(ball["clip_seconds"]) - event.clip_seconds) <= 0.04
                for player in players.get(source_frame, [])
                if int(player["track_id"]) == event.to_player_track_id
                and str(player.get("team")) == event.team
            ),
            None,
        )
        if contact is None:
            refined.append(event)
            continue
        source_frame, ball, player = contact
        previous_frame = prior_frame.get(source_frame)
        current_motion = motion.get((int(ball["track_id"]), source_frame))
        previous_motion = (
            next(
                (
                    value
                    for (_, frame), value in motion.items()
                    if frame == previous_frame
                ),
                None,
            )
            if previous_frame is not None
            else None
        )
        height = max(1.0, float(player["y2"]) - float(player["y1"]))
        receiver_distance = hypot(
            (float(player["x1"]) + float(player["x2"])) / 2
            - float(ball["x"]),
            float(player["y2"]) - float(ball["y"]),
        ) / height
        if (
            current_motion is None
            or previous_motion is None
            or current_motion[0]
            < minimum_speed_pixels_per_second * minimum_speed_multiplier
            or current_motion[0] / height
            < minimum_speed_heights_per_second
            or current_motion[0]
            < previous_motion[0] * minimum_acceleration_ratio
            or receiver_distance > maximum_receiver_distance_heights
        ):
            refined.append(event)
            continue
        refined.append(
            replace(
                event,
                completion_seconds=round(event.clip_seconds, 3),
                details=(
                    "A same-team receiver immediately accelerated the ball, "
                    "confirming a one-touch completion. "
                    f"{event.details}"
                ),
            )
        )
    return refined


def refine_receptions_to_sharp_contacts(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    maximum_delay_seconds: float = 1.2,
    maximum_direction_cosine: float = -0.8,
) -> list[PredictedEvent]:
    source = list(events)
    controls = list(observations)
    motion = _ball_motion_evidence(balls)
    motion_by_seconds = {
        round(float(point["clip_seconds"]), 3): motion.get(
            (int(point["track_id"]), int(point["source_frame"]))
        )
        for frame_points in balls.values()
        for point in frame_points
    }
    refined: list[PredictedEvent] = []
    for event in source:
        if (
            event.event_type != "pass_candidate"
            or event.completion_seconds is None
            or event.completion_seconds - event.clip_seconds > 0.6
            or "Control transferred after" not in event.details
        ):
            refined.append(event)
            continue
        completion_motion = motion_by_seconds.get(
            round(event.completion_seconds, 3)
        )
        if (
            completion_motion is not None
            and completion_motion[1] <= maximum_direction_cosine
        ):
            refined.append(event)
            continue
        candidates: list[PossessionObservation] = []
        for observation in controls:
            delay = observation.clip_seconds - event.completion_seconds
            if (
                observation.team != event.team
                or observation.player_track_id == event.to_player_track_id
                or delay < 0.2
                or delay > maximum_delay_seconds
                or observation.control_ratio > 1.2
            ):
                continue
            evidence = next(
                (
                    value
                    for (track_id, frame), value in motion.items()
                    if frame == observation.source_frame
                ),
                None,
            )
            if (
                evidence is not None
                and evidence[0] >= minimum_speed_pixels_per_second
                and evidence[1] <= maximum_direction_cosine
            ):
                candidates.append(observation)
        if not candidates:
            refined.append(event)
            continue
        contact = min(candidates, key=lambda observation: observation.clip_seconds)
        if any(
            other is not event
            and other.team == event.team
            and other.completion_seconds is not None
            and abs(other.completion_seconds - contact.clip_seconds) <= 0.2
            for other in source
        ):
            refined.append(event)
            continue
        refined.append(
            replace(
                event,
                to_player_track_id=contact.player_track_id,
                completion_seconds=round(contact.clip_seconds, 3),
                details=(
                    f"{event.details} Reception moved from a tracker handoff "
                    "to the next sharp ball-direction change at a teammate."
                ),
            )
        )
    return _deduplicate_receptions(refined)


def infer_short_exchange_receptions(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    maximum_prior_reception_seconds: float,
    maximum_release_lead_seconds: float = 0.8,
    nearby_control_seconds: float = 0.4,
) -> list[PredictedEvent]:
    source = list(events)
    controls = list(observations)
    motion = _ball_motion_evidence(balls)
    inferred: list[PredictedEvent] = []
    for outgoing in source:
        if outgoing.event_type != "pass_candidate":
            continue
        candidates: list[tuple[float, PossessionObservation]] = []
        for observation in controls:
            lead = outgoing.clip_seconds - observation.clip_seconds
            if (
                observation.team != outgoing.team
                or observation.control_ratio > 0.35
                or lead < 0.2
                or lead > maximum_release_lead_seconds
            ):
                continue
            evidence = motion.get(
                (next(
                    (
                        int(ball["track_id"])
                        for ball in balls.get(observation.source_frame, [])
                    ),
                    -1,
                ), observation.source_frame)
            )
            if (
                evidence is None
                or evidence[0] < minimum_speed_pixels_per_second
                or evidence[1] > 0.25
            ):
                continue
            nearby_tracks = {
                nearby.player_track_id
                for nearby in controls
                if nearby.team == outgoing.team
                and abs(
                    nearby.clip_seconds - observation.clip_seconds
                )
                <= nearby_control_seconds
                and nearby.control_ratio <= 0.35
            }
            if len(nearby_tracks) < 2:
                continue
            prior_receptions = [
                event
                for event in source
                if event.team == outgoing.team
                and event.completion_seconds is not None
                and 0.8
                <= observation.clip_seconds - event.completion_seconds
                <= maximum_prior_reception_seconds
            ]
            if not prior_receptions:
                continue
            if any(
                event.team == outgoing.team
                and event.completion_seconds is not None
                and abs(
                    event.completion_seconds - observation.clip_seconds
                )
                <= maximum_release_lead_seconds
                for event in source
            ):
                continue
            candidates.append((observation.control_ratio, observation))
        if not candidates:
            continue
        _, contact = min(candidates, key=lambda item: item[0])
        prior = max(
            (
                event
                for event in source
                if event.team == outgoing.team
                and event.completion_seconds is not None
                and 0.8
                <= contact.clip_seconds - event.completion_seconds
                <= maximum_prior_reception_seconds
            ),
            key=lambda event: event.completion_seconds or 0,
        )
        inferred.append(
            PredictedEvent(
                event_type="pass_candidate",
                clip_seconds=round(contact.clip_seconds, 3),
                team=outgoing.team,
                from_player_track_id=prior.to_player_track_id,
                to_player_track_id=contact.player_track_id,
                confidence=0.6,
                details=(
                    "A sharp controlled contact between co-visible teammates "
                    "completed a short exchange before the next pass."
                ),
                completion_seconds=round(contact.clip_seconds, 3),
            )
        )
    return _deduplicate_receptions([*source, *inferred])


def infer_post_turnover_first_pass(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    *,
    co_visible_track_pairs: Iterable[frozenset[int]],
    maximum_chain_seconds: float = 3.0,
    maximum_control_ratio: float = 1.0,
) -> list[PredictedEvent]:
    source = list(events)
    controls = list(observations)
    distinct_players = set(co_visible_track_pairs)
    inferred: list[PredictedEvent] = []
    for outgoing in source:
        if (
            outgoing.event_type != "pass_candidate"
            or outgoing.from_player_track_id is None
        ):
            continue
        prior_turnovers = [
            event
            for event in source
            if event.event_type == "turnover_candidate"
            and event.team != outgoing.team
            and event.to_player_track_id is not None
            and event.completion_seconds is not None
            and 0
            < outgoing.clip_seconds - event.completion_seconds
            <= maximum_chain_seconds
        ]
        if not prior_turnovers:
            continue
        turnover = max(
            prior_turnovers,
            key=lambda event: event.completion_seconds or 0,
        )
        gained_by = turnover.to_player_track_id
        passer = outgoing.from_player_track_id
        if (
            gained_by == passer
            or frozenset((gained_by, passer)) not in distinct_players
        ):
            continue
        first_passer_control = next(
            (
                observation
                for observation in controls
                if observation.player_track_id == passer
                and observation.team == outgoing.team
                and turnover.completion_seconds
                < observation.clip_seconds
                < outgoing.clip_seconds
                and observation.control_ratio <= maximum_control_ratio
            ),
            None,
        )
        if first_passer_control is None:
            continue
        prior_owner_controls = [
            observation
            for observation in controls
            if observation.player_track_id == gained_by
            and turnover.completion_seconds
            <= observation.clip_seconds
            < first_passer_control.clip_seconds
            and observation.control_ratio <= maximum_control_ratio
        ]
        if not prior_owner_controls:
            continue
        if any(
            observation.player_track_id == gained_by
            and observation.team == outgoing.team
            and first_passer_control.clip_seconds
            < observation.clip_seconds
            < outgoing.clip_seconds
            and observation.control_ratio <= maximum_control_ratio
            for observation in controls
        ):
            continue
        release = max(
            prior_owner_controls,
            key=lambda observation: observation.clip_seconds,
        )
        inferred.append(
            PredictedEvent(
                event_type="pass_candidate",
                clip_seconds=round(release.clip_seconds, 3),
                team=outgoing.team,
                from_player_track_id=gained_by,
                to_player_track_id=passer,
                confidence=0.6,
                details=(
                    "After the opponent turnover, controlled possession moved "
                    "between two co-visible teammates before the next pass."
                ),
                completion_seconds=round(
                    first_passer_control.clip_seconds,
                    3,
                ),
            )
        )
    return _deduplicate_receptions([*source, *inferred])


def infer_ball_reentry_receptions(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    minimum_tracking_gap_seconds: float = 1.5,
    maximum_reentry_control_seconds: float = 0.4,
    maximum_following_release_seconds: float = 2.0,
    maximum_control_ratio: float = 0.7,
    minimum_distance_ratio: float = 1.5,
    maximum_contiguous_step_seconds: float = 0.4,
) -> list[PredictedEvent]:
    source = list(events)
    controls = list(observations)
    points = sorted(
        (
            {**point, "track_id": int(point["track_id"])}
            for frame_points in balls.values()
            for point in frame_points
            if not point.get("interpolated", False)
        ),
        key=lambda point: float(point["clip_seconds"]),
    )
    motion = _ball_motion_evidence(balls)
    inferred: list[PredictedEvent] = []
    for observation in controls:
        if observation.control_ratio > maximum_control_ratio:
            continue
        point_index = next(
            (
                index
                for index, point in enumerate(points)
                if int(point["source_frame"]) == observation.source_frame
            ),
            None,
        )
        if point_index is None or point_index == 0 or point_index + 1 >= len(points):
            continue
        reentry_index = point_index
        while (
            reentry_index > 0
            and float(points[reentry_index]["clip_seconds"])
            - float(points[reentry_index - 1]["clip_seconds"])
            <= maximum_contiguous_step_seconds
        ):
            reentry_index -= 1
        if (
            reentry_index == 0
            or float(points[reentry_index]["clip_seconds"])
            - float(points[reentry_index - 1]["clip_seconds"])
            < minimum_tracking_gap_seconds
            or observation.clip_seconds
            - float(points[reentry_index]["clip_seconds"])
            > maximum_reentry_control_seconds
        ):
            continue
        previous_ball = points[point_index - 1]
        current_ball = points[point_index]
        following_ball = points[point_index + 1]
        if not (
            previous_ball["track_id"]
            == current_ball["track_id"]
            == following_ball["track_id"]
        ):
            continue
        evidence = motion.get(
            (current_ball["track_id"], observation.source_frame)
        )
        if (
            evidence is None
            or evidence[0] < minimum_speed_pixels_per_second
        ):
            continue
        current_distance = hypot(
            float(current_ball["x"]) - observation.player_x,
            float(current_ball["y"]) - observation.player_y,
        )
        previous_distance = hypot(
            float(previous_ball["x"]) - observation.player_x,
            float(previous_ball["y"]) - observation.player_y,
        )
        following_distance = hypot(
            float(following_ball["x"]) - observation.player_x,
            float(following_ball["y"]) - observation.player_y,
        )
        if (
            previous_distance < current_distance * minimum_distance_ratio
            or following_distance < current_distance * minimum_distance_ratio
        ):
            continue
        reentry_seconds = float(points[reentry_index]["clip_seconds"])
        prior_controls = [
            candidate
            for candidate in controls
            if candidate.clip_seconds < reentry_seconds
        ]
        if not prior_controls:
            continue
        prior = max(prior_controls, key=lambda candidate: candidate.clip_seconds)
        if prior.team != observation.team:
            continue
        following = [
            event
            for event in source
            if event.event_type == "pass_candidate"
            and event.team == observation.team
            and 0
            < event.clip_seconds - observation.clip_seconds
            <= maximum_following_release_seconds
        ]
        if (
            not following
            or any(
                event.completion_seconds is not None
                and abs(event.completion_seconds - observation.clip_seconds) <= 0.5
                for event in [*source, *inferred]
            )
        ):
            continue
        inferred.append(
            PredictedEvent(
                event_type="pass_candidate",
                clip_seconds=round(observation.clip_seconds, 3),
                team=observation.team,
                from_player_track_id=prior.player_track_id,
                to_player_track_id=observation.player_track_id,
                confidence=0.6,
                details=(
                    "A local closest approach at the first controlled ball "
                    "re-entry recovered a same-team reception after a tracking gap."
                ),
                completion_seconds=round(observation.clip_seconds, 3),
            )
        )
    return _deduplicate_receptions([*source, *inferred])


def infer_pre_release_flight_receptions(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
    co_visible_track_pairs: Iterable[frozenset[int]],
    minimum_speed_pixels_per_second: float,
    maximum_sender_lookback_seconds: float,
    maximum_control_ratio: float = 0.5,
    maximum_sender_ratio: float = 1.0,
    maximum_contact_lead_seconds: float = 0.41,
    maximum_sharp_contact_ratio: float = 1.2,
    maximum_contact_direction_cosine: float = -0.25,
    maximum_ball_step_seconds: float = 0.4,
    minimum_travel_heights: float = 1.5,
    maximum_handoff_speed_heights_per_second: float = 3.0,
) -> list[PredictedEvent]:
    """Recover an incoming pass confirmed by the receiver's immediate release."""
    source = list(events)
    controls = list(observations)
    distinct_players = set(co_visible_track_pairs)
    motion = _ball_motion_evidence(balls)
    points = sorted(
        (
            point
            for frame_points in balls.values()
            for point in frame_points
            if not point.get("interpolated", False)
        ),
        key=lambda point: float(point["clip_seconds"]),
    )
    inferred: list[PredictedEvent] = []

    def distinct_player_evidence(
        sender: PossessionObservation,
        receiver: PossessionObservation,
    ) -> bool:
        if frozenset(
            (sender.player_track_id, receiver.player_track_id)
        ) in distinct_players:
            return True
        elapsed = receiver.clip_seconds - sender.clip_seconds
        scale = max(
            1.0,
            (sender.player_height + receiver.player_height) / 2,
        )
        return (
            elapsed > 0
            and hypot(
                receiver.player_x - sender.player_x,
                receiver.player_y - sender.player_y,
            )
            / scale
            / elapsed
            > maximum_handoff_speed_heights_per_second
        )

    for outgoing in source:
        if (
            outgoing.event_type != "pass_candidate"
            or outgoing.from_player_track_id is None
        ):
            continue
        receiver_controls = [
            observation
            for observation in controls
            if observation.team == outgoing.team
            and observation.player_track_id == outgoing.from_player_track_id
            and (
                observation.control_ratio <= maximum_control_ratio
                or (
                    observation.control_ratio <= maximum_sharp_contact_ratio
                    and (
                        evidence := next(
                            (
                                value
                                for (track_id, frame), value in motion.items()
                                if frame == observation.source_frame
                            ),
                            None,
                        )
                    )
                    is not None
                    and evidence[0] >= minimum_speed_pixels_per_second
                    and evidence[1] <= maximum_contact_direction_cosine
                )
            )
            and 0
            <= outgoing.clip_seconds - observation.clip_seconds
            <= maximum_contact_lead_seconds
        ]
        if not receiver_controls:
            continue
        receiver = max(
            receiver_controls,
            key=lambda observation: observation.clip_seconds,
        )
        senders = [
            observation
            for observation in controls
            if observation.team == receiver.team
            and observation.player_track_id != receiver.player_track_id
            and observation.control_ratio <= maximum_sender_ratio
            and 0
            < receiver.clip_seconds - observation.clip_seconds
            <= maximum_sender_lookback_seconds
            and distinct_player_evidence(observation, receiver)
        ]
        if not senders:
            continue
        sender = max(senders, key=lambda observation: observation.clip_seconds)
        if any(
            event.event_type == "pass_candidate"
            and event.team == receiver.team
            and event.to_player_track_id == receiver.player_track_id
            and event.completion_seconds is not None
            and sender.clip_seconds
            < event.completion_seconds
            <= receiver.clip_seconds
            for event in source
        ):
            continue
        if any(
            observation.team != receiver.team
            and observation.control_ratio <= maximum_control_ratio
            and sender.clip_seconds
            < observation.clip_seconds
            < receiver.clip_seconds
            for observation in controls
        ):
            continue
        flight_steps = [
            (first, second)
            for first, second in zip(points, points[1:])
            if int(first["track_id"]) == int(second["track_id"])
            and sender.clip_seconds
            <= float(first["clip_seconds"])
            < float(second["clip_seconds"])
            <= receiver.clip_seconds
            and 0
            < float(second["clip_seconds"]) - float(first["clip_seconds"])
            <= maximum_ball_step_seconds
            and hypot(
                float(second["x"]) - float(first["x"]),
                float(second["y"]) - float(first["y"]),
            )
            / (
                float(second["clip_seconds"]) - float(first["clip_seconds"])
            )
            >= minimum_speed_pixels_per_second
        ]
        if not flight_steps:
            continue
        release_seconds = float(flight_steps[0][0]["clip_seconds"])
        travel_heights = hypot(
            receiver.ball_x - sender.ball_x,
            receiver.ball_y - sender.ball_y,
        ) / max(1.0, sender.player_height)
        if (
            travel_heights < minimum_travel_heights
            or any(
                event.completion_seconds is not None
                and abs(
                    event.completion_seconds - receiver.clip_seconds
                )
                <= maximum_contact_lead_seconds
                for event in [*source, *inferred]
            )
        ):
            continue
        inferred.append(
            PredictedEvent(
                event_type="pass_candidate",
                clip_seconds=round(release_seconds, 3),
                team=receiver.team,
                from_player_track_id=sender.player_track_id,
                to_player_track_id=receiver.player_track_id,
                confidence=0.6,
                details=(
                    "Continuous ball flight from a distinct co-visible "
                    "teammate reached controlled reception immediately before "
                    "the receiver released the next pass."
                ),
                completion_seconds=round(receiver.clip_seconds, 3),
            )
        )
    return _deduplicate_receptions([*source, *inferred])


def infer_unresolved_direction_change_receptions(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
    players: dict[int, list[dict[str, Any]]] | None = None,
    minimum_speed_pixels_per_second: float,
    maximum_direction_cosine: float = -0.25,
    maximum_control_ratio: float = 0.5,
    event_exclusion_seconds: float = 1.0,
    minimum_evidence_points: int = 3,
) -> list[PredictedEvent]:
    source = list(events)
    observation_list = list(observations)
    motion = _ball_motion_evidence(balls)
    inferred: list[PredictedEvent] = []
    last_observation_seconds = max(
        (
            candidate.clip_seconds
            for candidate in observation_list
            if candidate.control_ratio <= maximum_control_ratio
        ),
        default=0.0,
    )
    for observation in observation_list:
        if observation.control_ratio > maximum_control_ratio:
            continue
        evidence = next(
            (
                value
                for (track_id, frame), value in motion.items()
                if frame == observation.source_frame
            ),
            None,
        )
        if (
            evidence is None
            or evidence[0] < minimum_speed_pixels_per_second
            or evidence[1] > maximum_direction_cosine
            or any(
                event.completion_seconds is not None
                and abs(event.completion_seconds - observation.clip_seconds)
                <= event_exclusion_seconds
                for event in [*source, *inferred]
            )
        ):
            continue
        receiver_team = None
        if players is not None:
            receiver_team, receiver_confidence, receiver_support = (
                _receiver_team_evidence(
                    players,
                    balls,
                    observation.clip_seconds,
                    window_seconds=0.8,
                )
            )
            if (
                receiver_team is not None
                and receiver_team != observation.team
                and receiver_confidence >= 0.6
                and receiver_support >= minimum_evidence_points
            ):
                continue
        prior_events = [
            event
            for event in source
            if (event.completion_seconds or event.clip_seconds)
            < observation.clip_seconds
        ]
        following_events = [
            event
            for event in source
            if (event.completion_seconds or event.clip_seconds)
            > observation.clip_seconds
        ]
        prior = (
            max(
                prior_events,
                key=lambda event: event.completion_seconds or event.clip_seconds,
            )
            if prior_events
            else None
        )
        following = (
            min(
                following_events,
                key=lambda event: event.completion_seconds or event.clip_seconds,
            )
            if following_events
            else None
        )
        linked_to_possession = (
            prior is not None
            and prior.team == observation.team
            and prior.event_type == "pass_candidate"
            and following is not None
            and following.team == observation.team
            and following.from_player_track_id == observation.player_track_id
            and following.event_type == "pass_candidate"
        ) or (
            prior is not None
            and following is not None
            and prior.team == observation.team == following.team
            and prior.event_type == following.event_type == "pass_candidate"
            and observation.clip_seconds <= following.clip_seconds
            and following.clip_seconds - observation.clip_seconds <= 0.6
        ) or (
            following is None
            and prior is not None
            and prior.team == observation.team
            and prior.event_type == "pass_candidate"
            and last_observation_seconds - observation.clip_seconds <= 0.6
            and any(
                candidate.team == observation.team
                and candidate.player_track_id == observation.player_track_id
                and observation.clip_seconds < candidate.clip_seconds
                <= last_observation_seconds
                for candidate in observation_list
            )
        )
        known_owner_track_ids = {
            track_id
            for track_id in (
                prior.to_player_track_id if prior is not None else None,
                following.from_player_track_id
                if following is not None
                else None,
            )
            if track_id is not None
        }
        same_tracked_owner = observation.player_track_id in known_owner_track_ids
        retained_owner = (
            prior is not None
            and following is not None
            and prior.to_player_track_id == observation.player_track_id
            and following.from_player_track_id == observation.player_track_id
        )
        if (
            not linked_to_possession
            or retained_owner
            or same_tracked_owner
            and evidence[0] < minimum_speed_pixels_per_second * 2
        ):
            continue
        inferred.append(
            PredictedEvent(
                event_type="pass_candidate",
                clip_seconds=round(observation.clip_seconds, 3),
                team=observation.team,
                from_player_track_id=None,
                to_player_track_id=observation.player_track_id,
                confidence=0.55,
                details=(
                    "A strong controlled touch and sharp ball-direction change "
                    "resolved a same-team reception hidden by track continuity."
                ),
                completion_seconds=round(observation.clip_seconds, 3),
            )
        )
    return _deduplicate_receptions([*source, *inferred])


def refine_aerial_challenged_receiver_receptions(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    aerial_boundary_intervals: Iterable[dict[str, Any]],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_delay_seconds: float = 0.6,
    maximum_delay_seconds: float = 4.0,
    maximum_candidate_control_ratio: float = 0.75,
    opponent_overlap_seconds: float = 0.21,
    confirmation_seconds: float = 1.2,
    maximum_proximity_ratio: float = 0.75,
) -> list[PredictedEvent]:
    source = list(events)
    controls = list(observations)
    aerial_intervals = list(aerial_boundary_intervals)
    refined: list[PredictedEvent] = []
    for event in source:
        completion = event.completion_seconds
        if (
            event.event_type != "pass_candidate"
            or completion is None
            or event.to_player_track_id is None
            or not any(
                float(interval["start_seconds"])
                <= event.clip_seconds
                <= float(interval.get("resumed_seconds") or interval["end_seconds"])
                for interval in aerial_intervals
            )
        ):
            refined.append(event)
            continue
        candidates = [
            observation
            for observation in controls
            if observation.team == event.team
            and observation.player_track_id != event.to_player_track_id
            and minimum_delay_seconds
            <= observation.clip_seconds - completion
            <= maximum_delay_seconds
            and observation.control_ratio <= maximum_candidate_control_ratio
            and any(
                confirmation.player_track_id == observation.player_track_id
                and observation.clip_seconds
                < confirmation.clip_seconds
                <= observation.clip_seconds + confirmation_seconds
                for confirmation in controls
            )
            and any(
                abs(opponent.clip_seconds - observation.clip_seconds)
                <= opponent_overlap_seconds
                and opponent.team != event.team
                for opponent in controls
            )
        ]
        if not candidates:
            refined.append(event)
            continue
        candidate = min(candidates, key=lambda observation: observation.clip_seconds)
        first_proximity = candidate.clip_seconds
        for source_frame, frame_balls in balls.items():
            frame_players = [
                player
                for player in players.get(source_frame, [])
                if int(player["track_id"]) == candidate.player_track_id
            ]
            if not frame_players:
                continue
            for ball in frame_balls:
                timestamp = float(ball["clip_seconds"])
                if not completion < timestamp <= candidate.clip_seconds:
                    continue
                for player in frame_players:
                    height = max(1.0, float(player["y2"]) - float(player["y1"]))
                    player_x = (float(player["x1"]) + float(player["x2"])) / 2
                    player_y = float(player["y2"])
                    proximity_ratio = (
                        hypot(
                            float(ball["x"]) - player_x,
                            float(ball["y"]) - player_y,
                        )
                        / height
                    )
                    if proximity_ratio <= maximum_proximity_ratio:
                        first_proximity = min(first_proximity, timestamp)
        refined.append(
            replace(
                event,
                to_player_track_id=candidate.player_track_id,
                completion_seconds=round(first_proximity, 3),
                details=(
                    f"{event.details} A later same-team receiver retained the "
                    "ball through an overlapping opponent challenge."
                ),
            )
        )

    accepted: list[PredictedEvent] = []
    for event in refined:
        if (
            event.event_type == "pass_candidate"
            and event.to_player_track_id is None
            and event.from_player_track_id is not None
            and event.completion_seconds is not None
            and any(
                following is not event
                and following.event_type == "pass_candidate"
                and following.from_player_track_id == event.from_player_track_id
                and 0
                <= following.clip_seconds - event.completion_seconds
                <= 1.0
                for following in refined
            )
        ):
            continue
        accepted.append(event)
    return _deduplicate_receptions(accepted)


def infer_occluded_exchange_receptions(
    events: Iterable[PredictedEvent],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    maximum_direction_cosine: float = -0.8,
    minimum_event_separation_seconds: float = 0.8,
    minimum_exchange_span_seconds: float = 2.2,
    maximum_contact_leg_seconds: float = 1.5,
) -> list[PredictedEvent]:
    source = sorted(events, key=lambda event: event.completion_seconds or event.clip_seconds)
    motion = _ball_motion_evidence(balls)
    inferred: list[PredictedEvent] = []
    for previous, following in zip(source, source[1:]):
        previous_completion = previous.completion_seconds
        following_completion = following.completion_seconds
        if (
            previous.event_type != "pass_candidate"
            or following.event_type != "pass_candidate"
            or previous.team != following.team
            or previous_completion is None
            or following_completion is None
            or following_completion - previous_completion
            < minimum_exchange_span_seconds
        ):
            continue
        candidates: list[tuple[float, float]] = []
        for (track_id, source_frame), (speed, direction_cosine) in motion.items():
            ball = next(
                (
                    point
                    for point in balls.get(source_frame, [])
                    if int(point["track_id"]) == track_id
                ),
                None,
            )
            if ball is None:
                continue
            timestamp = float(ball["clip_seconds"])
            if (
                timestamp < previous_completion + minimum_event_separation_seconds
                or timestamp
                > following_completion - minimum_event_separation_seconds
                or timestamp - previous_completion > maximum_contact_leg_seconds
                or following_completion - timestamp > maximum_contact_leg_seconds
                or speed < minimum_speed_pixels_per_second
                or direction_cosine > maximum_direction_cosine
            ):
                continue
            candidates.append((direction_cosine, timestamp))
        if not candidates:
            continue
        _, contact = min(candidates)
        inferred.append(
            PredictedEvent(
                event_type="pass_candidate",
                clip_seconds=round(contact, 3),
                team=previous.team,
                from_player_track_id=previous.to_player_track_id,
                to_player_track_id=None,
                confidence=0.5,
                details=(
                    "A sharp reversal between linked same-team receptions "
                    "recovered an occluded rapid exchange."
                ),
                completion_seconds=round(contact, 3),
            )
        )
    return _deduplicate_receptions([*source, *inferred])


def infer_unobserved_chain_contacts(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
    players: dict[int, list[dict[str, Any]]] | None = None,
    minimum_speed_pixels_per_second: float,
    minimum_gap_seconds: float = 4.0,
    contact_group_seconds: float = 1.0,
    segment_end_seconds: float | None = None,
) -> list[PredictedEvent]:
    """Recover contacts hidden by an extended gap in an otherwise stable attack."""
    source = sorted(
        events,
        key=lambda event: event.completion_seconds or event.clip_seconds,
    )
    controls = list(observations)
    motion = _ball_motion_evidence(balls)
    player_points = defaultdict(list)
    for frame_players in (players or {}).values():
        for player in frame_players:
            player_points[int(player["track_id"])].append(player)

    def forward_track_team(track_id: int, timestamp: float) -> str | None:
        labels = [
            classify_color_scores(
                point["color_scores"],
                team_profile="red-black",
            )
            for point in player_points.get(track_id, [])
            if timestamp
            <= float(point["clip_seconds"])
            <= timestamp + 0.8
            and isinstance(point.get("color_scores"), dict)
        ]
        labels = [label for label in labels if label in {"red", "black"}]
        if len(labels) < 3:
            return None
        label, count = Counter(labels).most_common(1)[0]
        return label if count / len(labels) >= 0.6 else None

    inferred: list[PredictedEvent] = []
    event_pairs = [
        (previous, following, False)
        for previous, following in zip(source, source[1:])
    ]
    if source and segment_end_seconds is not None:
        previous = source[-1]
        previous_completion = previous.completion_seconds
        terminal_controls = [
            control
            for control in controls
            if previous.team == control.team
            and control.control_ratio <= 0.5
            and previous_completion is not None
            and previous_completion < control.clip_seconds
            < segment_end_seconds
        ]
        if (
            previous.event_type == "pass_candidate"
            and previous.team is not None
            and previous_completion is not None
            and segment_end_seconds - previous_completion
            >= minimum_gap_seconds
            and terminal_controls
            and segment_end_seconds
            - terminal_controls[-1].clip_seconds
            <= 1.0
        ):
            event_pairs.append(
                (
                    previous,
                    PredictedEvent(
                        event_type="pass_candidate",
                        clip_seconds=segment_end_seconds,
                        team=previous.team,
                        from_player_track_id=(
                            terminal_controls[-1].player_track_id
                        ),
                        to_player_track_id=None,
                        confidence=0.0,
                        details="Segment-end possession sentinel.",
                        completion_seconds=segment_end_seconds,
                    ),
                    True,
                )
            )
    for previous, following, terminal_boundary in event_pairs:
        previous_completion = previous.completion_seconds
        following_completion = following.completion_seconds
        if (
            previous.event_type != "pass_candidate"
            or following.event_type != "pass_candidate"
            or previous.team != following.team
            or previous.team is None
            or previous_completion is None
            or following_completion is None
            or following_completion - previous_completion
            < minimum_gap_seconds
        ):
            continue
        candidates: list[tuple[float, float, float]] = []
        for (track_id, source_frame), (speed, direction_cosine) in motion.items():
            ball = next(
                (
                    point
                    for point in balls.get(source_frame, [])
                    if int(point["track_id"]) == track_id
                ),
                None,
            )
            if ball is None:
                continue
            timestamp = float(ball["clip_seconds"])
            sharp_reversal = direction_cosine <= -0.7
            if (
                timestamp <= previous_completion + 0.4
                or timestamp >= following_completion - 0.4
                or (
                    not sharp_reversal
                    and (
                        speed < minimum_speed_pixels_per_second * 9
                        or direction_cosine > 0.25
                    )
                )
            ):
                continue
            candidates.append((timestamp, direction_cosine, speed))
        if not any(
            direction_cosine <= -0.7
            for _, direction_cosine, _ in candidates
        ):
            continue
        grouped: list[list[tuple[float, float, float]]] = []
        for candidate in sorted(candidates):
            if (
                grouped
                and candidate[0] - grouped[-1][-1][0] <= contact_group_seconds
            ):
                grouped[-1].append(candidate)
            else:
                grouped.append([candidate])
        if (
            len(grouped) == 1
            and max(speed for _, _, speed in grouped[0])
            < minimum_speed_pixels_per_second * 9
            and not (
                terminal_boundary
                and sum(
                    direction_cosine <= -0.7
                    for _, direction_cosine, _ in grouped[0]
                )
                >= 2
            )
        ):
            continue
        for group in grouped:
            nearby_controls = [
                control
                for control in controls
                if control.team == previous.team
                and control.control_ratio <= 0.5
                and not (
                    previous.to_player_track_id is not None
                    and previous.to_player_track_id
                    == following.from_player_track_id
                    == control.player_track_id
                )
                and any(
                    abs(control.clip_seconds - timestamp) <= 0.25
                    for timestamp, _, _ in group
                )
            ]
            if nearby_controls:
                contact_owner = min(
                    nearby_controls,
                    key=lambda control: control.control_ratio,
                )
                contact = contact_owner.clip_seconds
                track_team = forward_track_team(
                    contact_owner.player_track_id,
                    contact,
                )
                if track_team is not None and track_team != previous.team:
                    continue
            else:
                if (
                    previous.to_player_track_id is not None
                    and previous.to_player_track_id
                    == following.from_player_track_id
                ):
                    continue
                _, contact, _ = min(
                    (direction_cosine, timestamp, speed)
                    for timestamp, direction_cosine, speed in group
                )
            if any(
                event.completion_seconds is not None
                and abs(event.completion_seconds - contact) < 0.4
                for event in [*source, *inferred]
            ):
                continue
            inferred.append(
                PredictedEvent(
                    event_type="pass_candidate",
                    clip_seconds=round(contact, 3),
                    team=previous.team,
                    from_player_track_id=None,
                    to_player_track_id=None,
                    confidence=0.5,
                    details=(
                        "Ball-direction evidence recovered a contact hidden "
                        "inside a prolonged same-team possession chain."
                    ),
                    completion_seconds=round(contact, 3),
                )
            )
    accepted: list[PredictedEvent] = []
    for event in source:
        prior_hidden_contacts = [
            prior
            for prior in source
            if prior.details.startswith("A strong controlled touch")
            and prior.completion_seconds is not None
            and 0 < event.clip_seconds - prior.completion_seconds <= 3.0
        ]
        receiver_controls = [
            control
            for control in controls
            if (
                event.to_player_track_id is not None
                and control.player_track_id == event.to_player_track_id
                and event.completion_seconds is not None
                and 0
                <= control.clip_seconds - event.completion_seconds
                <= 0.8
            )
        ]
        if (
            event.event_type == "pass_candidate"
            and event.details.startswith("Ball release")
            and prior_hidden_contacts
            and (
                not any(
                    prior.to_player_track_id == event.from_player_track_id
                    for prior in prior_hidden_contacts
                )
            )
            and receiver_controls
            and min(control.control_ratio for control in receiver_controls) > 0.5
        ):
            continue
        accepted.append(event)
    return _deduplicate_receptions([*accepted, *inferred])


def suppress_redundant_retained_possession_links(
    events: Iterable[PredictedEvent],
) -> list[PredictedEvent]:
    """Collapse an inferred handoff superseded by retained-team possession."""
    source = list(events)
    retained_links = [
        event
        for event in source
        if event.details.startswith(
            "Opponent proximity never became controlled possession"
        )
    ]
    clustered_hidden_contacts = [
        hidden
        for hidden in source
        if hidden.details.startswith("A strong controlled touch")
        and hidden.completion_seconds is not None
        and any(
            chain.details.startswith("Ball-direction evidence")
            and chain.completion_seconds is not None
            and 0 < hidden.completion_seconds - chain.completion_seconds <= 1.2
            for chain in source
        )
    ]
    return _deduplicate_receptions(
        [
            event
            for event in source
            if not (
                event.event_type == "pass_candidate"
                and event.to_player_track_id is not None
                and event.completion_seconds is not None
                and any(
                    retained.team == event.team
                    and retained.from_player_track_id == event.to_player_track_id
                    and abs(retained.clip_seconds - event.completion_seconds)
                    <= 0.04
                    for retained in retained_links
                )
                or event.event_type == "pass_candidate"
                and event.details.startswith("Ball release")
                and any(
                    hidden.team == event.team
                    and hidden.to_player_track_id == event.from_player_track_id
                    and hidden.completion_seconds is not None
                    and 0 < event.clip_seconds - hidden.completion_seconds <= 3.0
                    for hidden in clustered_hidden_contacts
                )
            )
        ]
    )


def filter_disconnected_low_confidence_startup(
    events: Iterable[PredictedEvent],
    *,
    maximum_low_confidence: float = 0.55,
    minimum_following_gap_seconds: float = 4.0,
) -> list[PredictedEvent]:
    source = sorted(events, key=lambda event: event.clip_seconds)
    first_trusted_index = next(
        (
            index
            for index, event in enumerate(source)
            if event.confidence >= maximum_low_confidence
            or event.event_type != "pass_candidate"
        ),
        None,
    )
    if first_trusted_index in {None, 0}:
        return source
    startup = source[:first_trusted_index]
    first_trusted = source[first_trusted_index]
    last_completion = max(
        event.completion_seconds or event.clip_seconds for event in startup
    )
    if first_trusted.clip_seconds - last_completion < minimum_following_gap_seconds:
        return source
    return source[first_trusted_index:]


def infer_deceleration_transfer_events(
    balls: dict[int, list[dict[str, Any]]],
    possession_segments: Iterable[PossessionSegment],
    *,
    minimum_incoming_speed_pixels_per_second: float,
    maximum_outgoing_speed_ratio: float,
    sender_lookback_seconds: float,
    receiver_window_seconds: float,
    minimum_transfer_heights: float,
) -> list[PredictedEvent]:
    if minimum_incoming_speed_pixels_per_second <= 0:
        raise ValueError("Minimum incoming speed must be positive")
    if not 0 < maximum_outgoing_speed_ratio < 1:
        raise ValueError("Maximum outgoing speed ratio must be between 0 and 1")
    tracks: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame_points in balls.values():
        for point in frame_points:
            if not point.get("interpolated", False):
                tracks[int(point["track_id"])].append(point)

    segments = list(possession_segments)
    events: list[PredictedEvent] = []
    all_points = sorted(
        (point for points in tracks.values() for point in points),
        key=lambda point: float(point["clip_seconds"]),
    )
    for sender, receiver in zip(segments, segments[1:]):
        if sender.team != receiver.team:
            continue
        candidates: list[tuple[float, float, float]] = []
        for previous, current, following in zip(
            all_points, all_points[1:], all_points[2:]
        ):
            incoming_seconds = float(current["clip_seconds"]) - float(
                previous["clip_seconds"]
            )
            outgoing_seconds = float(following["clip_seconds"]) - float(
                current["clip_seconds"]
            )
            if incoming_seconds <= 0 or outgoing_seconds <= 0:
                continue
            incoming_speed = hypot(
                float(current["x"]) - float(previous["x"]),
                float(current["y"]) - float(previous["y"]),
            ) / incoming_seconds
            outgoing_speed = hypot(
                float(following["x"]) - float(current["x"]),
                float(following["y"]) - float(current["y"]),
            ) / outgoing_seconds
            if (
                incoming_speed < minimum_incoming_speed_pixels_per_second
                or outgoing_speed
                > incoming_speed * maximum_outgoing_speed_ratio
            ):
                continue
            completion = float(current["clip_seconds"])
            if (
                not sender.end_seconds < completion < receiver.start_seconds
                or completion - sender.end_seconds
                > min(sender_lookback_seconds, 0.75)
                or receiver.start_seconds - completion
                > receiver_window_seconds
                or receiver.start_seconds - completion < 0.6
            ):
                continue
            second_flight = any(
                float(first["clip_seconds"]) >= completion + 0.6
                and float(second["clip_seconds"]) <= receiver.start_seconds
                and float(second["clip_seconds"]) > float(first["clip_seconds"])
                and hypot(
                    float(second["x"]) - float(first["x"]),
                    float(second["y"]) - float(first["y"]),
                )
                / (
                    float(second["clip_seconds"])
                    - float(first["clip_seconds"])
                )
                >= max(
                    150.0,
                    minimum_incoming_speed_pixels_per_second * 3,
                )
                for first, second in zip(all_points, all_points[1:])
            )
            if not second_flight:
                continue
            sender_observation = sender.observations[-1]
            travel_heights = hypot(
                float(current["x"]) - sender_observation.ball_x,
                float(current["y"]) - sender_observation.ball_y,
            ) / max(1.0, sender_observation.player_height)
            if travel_heights < minimum_transfer_heights:
                continue
            candidates.append(
                (incoming_speed / max(outgoing_speed, 1.0), completion, incoming_speed)
            )
        if not candidates:
            continue
        _, completion, incoming_speed = max(candidates)
        events.append(
            PredictedEvent(
                event_type="pass_candidate",
                clip_seconds=round(sender.end_seconds, 3),
                team=sender.team,
                from_player_track_id=sender.player_track_id,
                to_player_track_id=None,
                confidence=0.6,
                details=(
                    f"Ball sharply decelerated before a second flight and "
                    f"{receiver.team} retained control."
                ),
                completion_seconds=round(completion, 3),
            )
        )
    return _deduplicate_receptions(events)


def filter_ambiguous_startup_transfers(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    *,
    startup_guard_seconds: float,
    maximum_receiver_control_ratio: float,
    maximum_sender_control_ratio: float = 0.5,
    observation_tolerance_seconds: float = 0.25,
) -> list[PredictedEvent]:
    if startup_guard_seconds < 0:
        raise ValueError("Startup guard seconds cannot be negative")
    if maximum_receiver_control_ratio <= 0:
        raise ValueError("Maximum receiver control ratio must be positive")
    receiver_observations: dict[int, list[PossessionObservation]] = defaultdict(list)
    for observation in observations:
        receiver_observations[observation.player_track_id].append(observation)

    accepted: list[PredictedEvent] = []
    for event in events:
        completion = event.completion_seconds
        if (
            completion is None
            or completion > startup_guard_seconds
            or event.from_player_track_id is None
            or event.to_player_track_id is None
        ):
            accepted.append(event)
            continue
        nearby = [
            observation
            for observation in receiver_observations.get(
                event.to_player_track_id, []
            )
            if abs(observation.clip_seconds - completion)
            <= observation_tolerance_seconds
        ]
        sender_near_release = [
            observation
            for observation in receiver_observations.get(
                event.from_player_track_id, []
            )
            if abs(observation.clip_seconds - event.clip_seconds)
            <= observation_tolerance_seconds
        ]
        if (
            nearby
            and min(item.control_ratio for item in nearby)
            <= maximum_receiver_control_ratio
            and sender_near_release
            and min(item.control_ratio for item in sender_near_release)
            <= maximum_sender_control_ratio
        ):
            accepted.append(event)
    return accepted


def _deduplicate_receptions(
    events: Iterable[PredictedEvent],
    *,
    completion_tolerance_seconds: float = 0.25,
    cross_sender_completion_tolerance_seconds: float = 0.04,
) -> list[PredictedEvent]:
    accepted: list[PredictedEvent] = []
    for event in sorted(events, key=lambda item: item.clip_seconds):
        duplicate_index = next(
            (
                index
                for index, prior in enumerate(accepted)
                if prior.event_type == event.event_type
                and prior.team == event.team
                and prior.to_player_track_id == event.to_player_track_id
                and prior.completion_seconds is not None
                and event.completion_seconds is not None
                and abs(prior.completion_seconds - event.completion_seconds)
                <= (
                    completion_tolerance_seconds
                    if prior.from_player_track_id == event.from_player_track_id
                    else cross_sender_completion_tolerance_seconds
                )
            ),
            None,
        )
        if duplicate_index is None:
            accepted.append(event)
        elif (
            accepted[duplicate_index].from_player_track_id
            == event.from_player_track_id
        ):
            accepted[duplicate_index] = event
    return accepted


def infer_boundary_turnovers(
    intervals: Iterable[dict[str, Any]],
    possession_segments: Iterable[PossessionSegment],
    *,
    prior_events: Iterable[PredictedEvent] = (),
    ownership_lookback_seconds: float = 2.0,
    event_deduplication_seconds: float = 3.0,
    startup_restart_max_seconds: float | None = None,
) -> list[PredictedEvent]:
    segments = list(possession_segments)
    existing = list(prior_events)
    events: list[PredictedEvent] = []
    for interval in intervals:
        if (
            interval.get("starts_outside")
            or interval.get("stoppage_kind") == "stationary_ball_restart"
        ):
            continue
        start = float(interval["start_seconds"])
        effective_lookback = _boundary_ownership_lookback(
            interval, ownership_lookback_seconds
        )
        owners = [
            segment
            for segment in segments
            if segment.end_seconds <= start
            and segment.end_seconds >= start - effective_lookback
        ]
        if not owners:
            continue
        owner = max(owners, key=lambda segment: segment.end_seconds)
        if _same_team_restart_receiver(
            interval,
            segments,
            owner,
            startup_restart_max_seconds=startup_restart_max_seconds,
        ) is not None:
            continue
        if any(
            event.event_type == "turnover_candidate"
            and event.team == owner.team
            and abs(event.clip_seconds - start) <= event_deduplication_seconds
            for event in [*existing, *events]
        ):
            continue
        duration = float(interval.get("duration_seconds", 0))
        events.append(
            PredictedEvent(
                event_type="turnover_candidate",
                clip_seconds=round(start, 3),
                team=owner.team,
                from_player_track_id=owner.player_track_id,
                to_player_track_id=None,
                confidence=round(min(0.8, 0.5 + duration / 20), 4),
                details=(
                    f"Ball remained outside the calibrated pitch for "
                    f"{duration:.2f}s after {owner.team} control."
                ),
                completion_seconds=round(start, 3),
            )
        )
    return events


def filter_aerial_boundary_intervals(
    intervals: Iterable[dict[str, Any]],
    possession_segments: Iterable[PossessionSegment],
    *,
    maximum_prior_gap_seconds: float = 1.0,
    maximum_resume_gap_seconds: float = 1.2,
    maximum_crossing_span_seconds: float = 4.0,
) -> list[dict[str, Any]]:
    segments = list(possession_segments)
    accepted: list[dict[str, Any]] = []
    for interval in intervals:
        resumed = interval.get("resumed_seconds")
        if resumed is None:
            accepted.append(interval)
            continue
        start = float(interval["start_seconds"])
        resumed_seconds = float(resumed)
        prior = [
            segment
            for segment in segments
            if segment.end_seconds <= start
            and start - segment.end_seconds <= maximum_prior_gap_seconds
        ]
        following = [
            segment
            for segment in segments
            if segment.start_seconds >= resumed_seconds
            and segment.start_seconds - resumed_seconds
            <= maximum_resume_gap_seconds
        ]
        if (
            prior
            and following
            and following[0].start_seconds - start
            <= maximum_crossing_span_seconds
        ):
            prior_owner = max(prior, key=lambda segment: segment.end_seconds)
            next_owner = min(following, key=lambda segment: segment.start_seconds)
            if prior_owner.team == next_owner.team:
                continue
        accepted.append(interval)
    return accepted


def annotate_restart_releases(
    intervals: Iterable[dict[str, Any]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
) -> list[dict[str, Any]]:
    if minimum_speed_pixels_per_second <= 0:
        raise ValueError("Minimum restart speed must be positive")
    points = sorted(
        (
            point
            for frame_points in balls.values()
            for point in frame_points
            if not point.get("interpolated", False)
        ),
        key=lambda point: float(point["clip_seconds"]),
    )
    source = [dict(interval) for interval in intervals]
    for index, interval in enumerate(source):
        geometric_resume = interval.get("resumed_seconds")
        if geometric_resume is None:
            interval["play_resumed_seconds"] = None
            continue
        search_end = (
            float(source[index + 1]["start_seconds"])
            if index + 1 < len(source)
            else float("inf")
        )
        release = None
        for first, second in zip(points, points[1:]):
            first_seconds = float(first["clip_seconds"])
            second_seconds = float(second["clip_seconds"])
            if first_seconds < float(geometric_resume):
                continue
            if second_seconds > search_end:
                break
            elapsed = second_seconds - first_seconds
            if elapsed <= 0:
                continue
            speed = hypot(
                float(second["x"]) - float(first["x"]),
                float(second["y"]) - float(first["y"]),
            ) / elapsed
            if speed >= minimum_speed_pixels_per_second:
                release = round(first_seconds, 3)
                break
        interval["play_resumed_seconds"] = release
    return source


def extend_restarts_through_ball_setup(
    intervals: Iterable[dict[str, Any]],
    possession_segments: Iterable[PossessionSegment],
    ball_points: Iterable[dict[str, Any]],
    *,
    maximum_receiver_delay_seconds: float = 2.0,
    minimum_setup_control_seconds: float = 1.0,
    settled_speed_pixels_per_second: float = 100.0,
    minimum_settled_seconds: float = 0.4,
    minimum_restart_speed_pixels_per_second: float = 200.0,
    maximum_restart_search_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    """Keep play stopped when an apparent restart only relocates the ball."""
    segments = list(possession_segments)
    balls_by_seconds: dict[float, dict[str, Any]] = {}
    for point in ball_points:
        if point.get("interpolated", False):
            continue
        seconds = float(point["clip_seconds"])
        previous = balls_by_seconds.get(seconds)
        if previous is None or float(point.get("confidence", 0)) > float(
            previous.get("confidence", 0)
        ):
            balls_by_seconds[seconds] = point
    balls = [balls_by_seconds[key] for key in sorted(balls_by_seconds)]
    ball_steps: list[tuple[float, float, float]] = []
    for first, second in zip(balls, balls[1:]):
        start = float(first["clip_seconds"])
        end = float(second["clip_seconds"])
        elapsed = end - start
        if elapsed <= 0 or elapsed > 0.3:
            continue
        speed = hypot(
            float(second["x"]) - float(first["x"]),
            float(second["y"]) - float(first["y"]),
        ) / elapsed
        ball_steps.append((start, end, speed))

    extended: list[dict[str, Any]] = []
    for source_interval in intervals:
        interval = dict(source_interval)
        release_value = interval.get("play_resumed_seconds")
        if (
            interval.get("stoppage_kind") != "stationary_ball_restart"
            or release_value is None
        ):
            extended.append(interval)
            continue
        release = float(release_value)
        setup_controls = [
            segment
            for segment in segments
            if release < segment.start_seconds
            <= release + maximum_receiver_delay_seconds
            and segment.end_seconds - segment.start_seconds
            >= minimum_setup_control_seconds
        ]
        if not setup_controls:
            extended.append(interval)
            continue
        setup = min(setup_controls, key=lambda segment: segment.start_seconds)
        search_end = setup.end_seconds + maximum_restart_search_seconds
        latest_restart = None
        settled_start = None
        settled_end = None
        for index, (start, end, speed) in enumerate(ball_steps):
            if end < setup.start_seconds - 1e-9 or start > search_end + 1e-9:
                continue
            if settled_end is not None and start - settled_end > 0.3:
                settled_start = None
                settled_end = None
            if speed <= settled_speed_pixels_per_second:
                if settled_start is None:
                    settled_start = start
                settled_end = end
                continue
            was_settled = (
                settled_start is not None
                and settled_end is not None
                and settled_end - settled_start
                >= minimum_settled_seconds - 1e-9
            )
            following_speeds = [
                candidate[2] for candidate in ball_steps[index : index + 3]
            ]
            if (
                was_settled
                and speed >= minimum_restart_speed_pixels_per_second
                and sum(
                    candidate >= settled_speed_pixels_per_second
                    for candidate in following_speeds
                )
                >= 2
            ):
                latest_restart = start
            settled_start = None
            settled_end = None
        resumed = latest_restart if latest_restart is not None else setup.end_seconds
        interval["play_resumed_seconds"] = round(resumed, 3)
        interval["end_seconds"] = round(resumed, 3)
        interval["duration_seconds"] = round(
            resumed - float(interval["start_seconds"]),
            3,
        )
        evidence = dict(interval.get("movement_evidence", {}))
        evidence["discarded_repositioning_release_seconds"] = round(
            release, 3
        )
        evidence["setup_control_start_seconds"] = round(
            setup.start_seconds, 3
        )
        evidence["setup_control_end_seconds"] = round(setup.end_seconds, 3)
        evidence["confirmed_restart_release_seconds"] = round(resumed, 3)
        interval["movement_evidence"] = evidence
        interval["release_confidence"] = min(
            float(interval.get("release_confidence", 0.85)),
            0.75,
        )
        extended.append(interval)
    return extended


def infer_initial_possession_transfer(
    initial_team: str,
    possession_segments: Iterable[PossessionSegment],
) -> PredictedEvent | None:
    segments = list(possession_segments)
    if not segments:
        return None
    receiver = min(segments, key=lambda segment: segment.start_seconds)
    if receiver.team == initial_team:
        return None
    return PredictedEvent(
        event_type="turnover_candidate",
        clip_seconds=0.0,
        team=initial_team,
        from_player_track_id=None,
        to_player_track_id=receiver.player_track_id,
        confidence=0.65,
        details=(
            f"Chunk inherited {initial_team} possession; first detected "
            f"controlled touch belongs to {receiver.team}."
        ),
        completion_seconds=round(receiver.start_seconds, 3),
    )


def _event_released_outside(
    event: PredictedEvent,
    intervals: Iterable[dict[str, Any]],
    observations: Iterable[PossessionObservation] = (),
) -> bool:
    if event.event_type != "pass_candidate":
        return False
    controls = list(observations)
    for interval in intervals:
        if interval.get("starts_outside"):
            continue
        start = float(interval["start_seconds"])
        resumed = interval.get(
            "play_resumed_seconds", interval.get("resumed_seconds")
        )
        end = (
            float(resumed)
            if resumed is not None
            else float("inf")
        )
        if start <= event.clip_seconds <= end:
            geometric_resume = interval.get("resumed_seconds")
            sender_controlled_after_reentry = (
                geometric_resume is not None
                and event.from_player_track_id is not None
                and any(
                    observation.player_track_id == event.from_player_track_id
                    and float(geometric_resume)
                    <= observation.clip_seconds
                    < event.clip_seconds
                    for observation in controls
                )
            )
            if sender_controlled_after_reentry:
                return False
            return True
    return False


def _event_completed_outside(
    event: PredictedEvent,
    intervals: Iterable[dict[str, Any]],
) -> bool:
    if event.completion_seconds is None:
        return False
    for interval in intervals:
        if interval.get("starts_outside"):
            continue
        start = float(interval["start_seconds"])
        resumed = interval.get(
            "play_resumed_seconds", interval.get("resumed_seconds")
        )
        if resumed is None:
            resumed = float("inf")
        if start <= event.completion_seconds <= float(resumed):
            return True
    return False


def _deceleration_immediately_precedes_boundary(
    event: PredictedEvent,
    intervals: Iterable[dict[str, Any]],
    *,
    maximum_seconds: float = 0.5,
) -> bool:
    if (
        event.completion_seconds is None
        or not event.details.startswith("Ball sharply decelerated")
    ):
        return False
    return any(
        0
        <= float(interval["start_seconds"]) - event.completion_seconds
        <= maximum_seconds
        for interval in intervals
        if not interval.get("starts_outside")
    )


def infer_restart_passes(
    intervals: Iterable[dict[str, Any]],
    possession_segments: Iterable[PossessionSegment],
    *,
    prior_events: Iterable[PredictedEvent] = (),
    ownership_lookback_seconds: float = 2.0,
    maximum_reception_seconds: float = 8.0,
    balls: dict[int, list[dict[str, Any]]] | None = None,
    startup_restart_max_seconds: float | None = None,
    control_observations: Iterable[PossessionObservation] = (),
) -> list[PredictedEvent]:
    segments = list(possession_segments)
    existing = list(prior_events)
    raw_controls = list(control_observations)
    events: list[PredictedEvent] = []
    for interval in intervals:
        resumed_value = interval.get(
            "play_resumed_seconds", interval.get("resumed_seconds")
        )
        if interval.get("starts_outside") or resumed_value is None:
            continue
        start = float(interval["start_seconds"])
        resumed = float(resumed_value)
        effective_lookback = _boundary_ownership_lookback(
            interval, ownership_lookback_seconds
        )
        owners = [
            segment
            for segment in segments
            if segment.end_seconds <= start
            and segment.end_seconds >= start - effective_lookback
        ]
        if not owners:
            continue
        owner = max(owners, key=lambda segment: segment.end_seconds)
        geometric_resume = float(interval.get("resumed_seconds", resumed))
        raw_receivers = [
            observation
            for observation in raw_controls
            if geometric_resume
            <= observation.clip_seconds
            <= geometric_resume + maximum_reception_seconds
            and observation.player_track_id != owner.player_track_id
            and any(
                later.player_track_id == observation.player_track_id
                and 0
                < later.clip_seconds - observation.clip_seconds
                <= 0.64
                for later in raw_controls
            )
        ]
        stable_receivers = [
            segment
            for segment in segments
            if resumed
            <= segment.start_seconds
            <= resumed + maximum_reception_seconds
            and segment.player_track_id != owner.player_track_id
        ]
        first_stable_receiver = (
            min(stable_receivers, key=lambda segment: segment.start_seconds)
            if stable_receivers
            else None
        )
        raw_receiver = (
            min(raw_receivers, key=lambda observation: observation.clip_seconds)
            if raw_receivers
            else None
        )
        if (
            raw_receiver is not None
            and (
                first_stable_receiver is None
                or raw_receiver.team == first_stable_receiver.team
                or not 0
                <= first_stable_receiver.start_seconds
                - raw_receiver.clip_seconds
                <= 0.64
            )
        ):
            raw_receiver = None
        same_team_restart_receiver = _same_team_restart_receiver(
            interval,
            segments,
            owner,
            startup_restart_max_seconds=startup_restart_max_seconds,
            maximum_reception_seconds=maximum_reception_seconds,
        )
        receiver_confirmed_turnover = any(
            event.event_type == "turnover_candidate"
            and event.team == owner.team
            and event.to_player_track_id is not None
            and abs(event.clip_seconds - start) <= 3.0
            for event in existing
        )
        if receiver_confirmed_turnover:
            continue
        if raw_receiver is not None:
            receiver = PossessionSegment(
                raw_receiver.team,
                raw_receiver.player_track_id,
                [raw_receiver],
            )
        elif same_team_restart_receiver is not None:
            receiver = same_team_restart_receiver
        else:
            receivers = [
                segment
                for segment in stable_receivers
                if segment.team != owner.team
            ]
            if not receivers:
                continue
            receiver = min(receivers, key=lambda segment: segment.start_seconds)
        reception_search_start = (
            float(interval.get("resumed_seconds", resumed))
            if same_team_restart_receiver is not None
            else resumed
        )
        completion = (
            _restart_reception_seconds(
                balls,
                resumed_seconds=reception_search_start,
                latest_seconds=receiver.start_seconds,
            )
            if balls is not None
            else None
        )
        completion = receiver.start_seconds if completion is None else completion
        if any(
            event.event_type in {"pass_candidate", "restart_pass_candidate"}
            and event.team == receiver.team
            and event.completion_seconds is not None
            and abs(event.completion_seconds - completion) <= 0.8
            for event in existing
        ):
            continue
        events.append(
            PredictedEvent(
                event_type="restart_pass_candidate",
                clip_seconds=round(
                    float(interval.get("end_seconds", resumed))
                    if same_team_restart_receiver is not None
                    else resumed,
                    3,
                ),
                team=receiver.team,
                from_player_track_id=None,
                to_player_track_id=receiver.player_track_id,
                confidence=0.55,
                details=(
                    (
                        f"The segment opened during a {owner.team} restart; "
                        f"the receiving {receiver.team} player made the first "
                        "detected controlled touch."
                    )
                    if same_team_restart_receiver is not None
                    and startup_restart_max_seconds is not None
                    and start <= startup_restart_max_seconds
                    else (
                        f"After play resumed, the receiving {receiver.team} "
                        "player made the first repeatedly detected controlled "
                        "touch."
                    )
                    if raw_receiver is not None
                    and receiver.team == owner.team
                    else (
                        f"A {owner.team} player controlled the ball near the "
                        "upper body at the boundary; the receiving teammate "
                        "made the first detected controlled touch."
                    )
                    if same_team_restart_receiver is not None
                    else (
                        f"After {owner.team} put the ball outside, play resumed "
                        f"and the opposing {receiver.team} team made the first "
                        "detected controlled touch. Restart taker is not visible."
                    )
                ),
                completion_seconds=round(completion, 3),
            )
        )
    return events


def _same_team_restart_receiver(
    interval: dict[str, Any],
    segments: Iterable[PossessionSegment],
    owner: PossessionSegment,
    *,
    startup_restart_max_seconds: float | None,
    maximum_reception_seconds: float = 8.0,
) -> PossessionSegment | None:
    resumed_value = interval.get(
        "play_resumed_seconds", interval.get("resumed_seconds")
    )
    if resumed_value is None:
        return None
    opens_during_restart = (
        startup_restart_max_seconds is not None
        and float(interval["start_seconds"]) <= startup_restart_max_seconds
    )
    held_near_upper_body = sum(
        1
        for observation in owner.observations
        if (
            observation.player_y - observation.ball_y
        ) / max(1.0, observation.player_height)
        >= 0.65
        and observation.control_ratio <= 1.6
    ) >= 2
    if not opens_during_restart and not held_near_upper_body:
        return None
    resumed = float(resumed_value)
    receivers = [
        segment
        for segment in segments
        if resumed <= segment.start_seconds <= resumed + maximum_reception_seconds
        and segment.player_track_id != owner.player_track_id
    ]
    if not receivers:
        return None
    receiver = min(receivers, key=lambda segment: segment.start_seconds)
    return receiver if receiver.team == owner.team else None


def _restart_reception_seconds(
    balls: dict[int, list[dict[str, Any]]],
    *,
    resumed_seconds: float,
    latest_seconds: float,
    minimum_incoming_speed: float = 200.0,
    maximum_outgoing_speed_ratio: float = 0.5,
) -> float | None:
    points = sorted(
        (
            point
            for frame_points in balls.values()
            for point in frame_points
            if not point.get("interpolated", False)
        ),
        key=lambda point: float(point["clip_seconds"]),
    )
    candidates: list[tuple[float, float]] = []
    for previous, current, following in zip(points, points[1:], points[2:]):
        completion = float(current["clip_seconds"])
        if not resumed_seconds <= completion <= latest_seconds:
            continue
        incoming_seconds = completion - float(previous["clip_seconds"])
        outgoing_seconds = float(following["clip_seconds"]) - completion
        if incoming_seconds <= 0 or outgoing_seconds <= 0:
            continue
        incoming_speed = hypot(
            float(current["x"]) - float(previous["x"]),
            float(current["y"]) - float(previous["y"]),
        ) / incoming_seconds
        outgoing_speed = hypot(
            float(following["x"]) - float(current["x"]),
            float(following["y"]) - float(current["y"]),
        ) / outgoing_seconds
        if (
            incoming_speed >= minimum_incoming_speed
            and outgoing_speed
            <= incoming_speed * maximum_outgoing_speed_ratio
        ):
            candidates.append(
                (incoming_speed / max(outgoing_speed, 1.0), completion)
            )
    return max(candidates)[1] if candidates else None


def _boundary_ownership_lookback(
    interval: dict[str, Any],
    configured_seconds: float,
) -> float:
    if float(interval.get("duration_seconds", 0)) >= 3.0:
        return configured_seconds
    return min(configured_seconds, 2.0)


def merge_transfer_events(
    primary: Iterable[PredictedEvent],
    fallback: Iterable[PredictedEvent],
    *,
    deduplication_seconds: float,
) -> list[PredictedEvent]:
    def forms_transfer_chain(
        first: PredictedEvent,
        second: PredictedEvent,
    ) -> bool:
        return (
            first.to_player_track_id is not None
            and first.to_player_track_id == second.from_player_track_id
            and first.completion_seconds is not None
            and second.completion_seconds is not None
            and first.completion_seconds < second.completion_seconds
        )

    merged = sorted(primary, key=lambda event: event.clip_seconds)
    for event in sorted(fallback, key=lambda item: item.clip_seconds):
        if any(
            abs(event.clip_seconds - accepted.clip_seconds)
            <= deduplication_seconds
            and not forms_transfer_chain(accepted, event)
            and not forms_transfer_chain(event, accepted)
            for accepted in merged
        ):
            continue
        merged.append(event)
    return _deduplicate_receptions(merged)


def evaluate_events(
    predictions: Iterable[PredictedEvent],
    ground_truth: list[dict[str, Any]],
    *,
    tolerance_seconds: float,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for event_type in ("pass", "shot"):
        predicted = [
            event
            for event in predictions
            if event.event_type == f"{event_type}_candidate"
        ]
        truth = [
            event
            for event in ground_truth
            if event.get("event_type") == event_type
        ]
        unmatched_truth = set(range(len(truth)))
        matches: list[dict[str, Any]] = []
        for event in sorted(predicted, key=lambda item: item.clip_seconds):
            candidates = [
                (
                    abs(event.clip_seconds - float(truth[index]["clip_seconds"])),
                    index,
                )
                for index in unmatched_truth
                if abs(
                    event.clip_seconds - float(truth[index]["clip_seconds"])
                )
                <= tolerance_seconds
            ]
            if not candidates:
                continue
            error, truth_index = min(candidates)
            unmatched_truth.remove(truth_index)
            matches.append(
                {
                    "predicted_seconds": event.clip_seconds,
                    "ground_truth_seconds": truth[truth_index]["clip_seconds"],
                    "absolute_error_seconds": round(error, 3),
                }
            )
        true_positives = len(matches)
        false_positives = len(predicted) - true_positives
        false_negatives = len(truth) - true_positives
        precision = (
            true_positives / len(predicted) if predicted else 0.0
        )
        recall = true_positives / len(truth) if truth else 0.0
        results[event_type] = {
            "predicted": len(predicted),
            "ground_truth": len(truth),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "matches": matches,
        }
    results["tolerance_seconds"] = tolerance_seconds
    results["limitations"] = [
        "Pass candidates combine observed ball flight with sender/receiver control.",
        "High passes are evaluated as passes because height is not calibrated.",
        "Shot candidates use manually calibrated normalized goal centers.",
    ]
    return results


def infer_shot_events(
    balls: dict[int, list[dict[str, Any]]],
    possession_segments: Iterable[PossessionSegment],
    *,
    width: int,
    height: int,
    minimum_speed_pixels_per_second: float,
    minimum_goal_cosine: float,
    maximum_step_seconds: float = 0.8,
    debounce_seconds: float = 2.0,
    receiver_window_seconds: float = 0.8,
    prior_events: Iterable[PredictedEvent] = (),
) -> list[PredictedEvent]:
    tracks: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame_points in balls.values():
        for point in frame_points:
            tracks[int(point["track_id"])].append(point)

    goal_centers = {
        "left": (width * 0.18, height * 0.27),
        "right": (width * 0.95, height * 0.27),
    }
    candidates: list[tuple[float, float, str]] = []
    for points in tracks.values():
        ordered = sorted(
            (
                point
                for point in points
                if not point.get("interpolated", False)
            ),
            key=lambda point: float(point["clip_seconds"]),
        )
        for first, second in zip(ordered, ordered[1:]):
            elapsed = float(second["clip_seconds"]) - float(first["clip_seconds"])
            if elapsed <= 0 or elapsed > maximum_step_seconds:
                continue
            start_x = float(first["x"])
            start_y = float(first["y"])
            movement_x = float(second["x"]) - start_x
            movement_y = float(second["y"]) - start_y
            movement = hypot(movement_x, movement_y)
            speed = movement / elapsed
            if speed < minimum_speed_pixels_per_second:
                continue
            if start_x >= width * 0.6:
                goal_side = "right"
            elif start_x <= width * 0.4:
                goal_side = "left"
            else:
                continue
            goal_x, goal_y = goal_centers[goal_side]
            goal_x -= start_x
            goal_y -= start_y
            goal_distance = hypot(goal_x, goal_y)
            cosine = (
                (movement_x * goal_x + movement_y * goal_y)
                / (movement * goal_distance)
                if movement > 0 and goal_distance > 0
                else -1.0
            )
            if cosine < minimum_goal_cosine:
                continue
            candidates.append(
                (
                    (float(first["clip_seconds"]) + float(second["clip_seconds"]))
                    / 2,
                    speed,
                    goal_side,
                )
            )

    grouped_candidates: list[tuple[float, float, str]] = []
    for candidate in sorted(candidates):
        if (
            grouped_candidates
            and candidate[0] - grouped_candidates[-1][0] < debounce_seconds
        ):
            if candidate[1] > grouped_candidates[-1][1]:
                grouped_candidates[-1] = candidate
            continue
        grouped_candidates.append(candidate)

    events: list[PredictedEvent] = []
    segments = list(possession_segments)
    confirmed_events = list(prior_events)
    for timestamp, speed, goal_side in grouped_candidates:
        if any(
            0 <= segment.start_seconds - timestamp <= receiver_window_seconds
            and sum(
                not observation.ball_interpolated
                for observation in segment.observations
            )
            >= 2
            for segment in segments
        ):
            continue
        prior = [
            segment
            for segment in segments
            if segment.end_seconds <= timestamp
            and timestamp - segment.end_seconds <= 3.0
        ]
        owner = max(prior, key=lambda segment: segment.end_seconds) if prior else None
        confirmed_prior = [
            event
            for event in confirmed_events
            if event.team in {"blue", "white"}
            and event.clip_seconds <= timestamp
            and timestamp - event.clip_seconds <= 3.0
        ]
        confirmed_owner = (
            max(confirmed_prior, key=lambda event: event.clip_seconds)
            if confirmed_prior
            else None
        )
        team = confirmed_owner.team if confirmed_owner else owner.team if owner else None
        player_track_id = (
            (
                confirmed_owner.to_player_track_id
                or confirmed_owner.from_player_track_id
            )
            if confirmed_owner
            else owner.player_track_id if owner else None
        )
        events.append(
            PredictedEvent(
                event_type="shot_candidate",
                clip_seconds=round(timestamp, 3),
                team=team,
                from_player_track_id=player_track_id,
                to_player_track_id=None,
                confidence=round(
                    min(0.95, 0.45 + speed / 1200),
                    4,
                ),
                details=(
                    f"Ball speed {speed:.2f} pixels/second toward {goal_side} goal."
                ),
            )
        )
    return events


def _control_observations(
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    control_radius_heights: float,
    maximum_flyby_speed_pixels_per_second: float | None = None,
    maximum_flyby_speed_heights_per_second: float | None = None,
    minimum_flyby_direction_cosine: float = 0.85,
    maximum_ground_contact_height_ratio: float | None = None,
    maximum_aerial_contact_direction_cosine: float = 0.5,
    future_control_confirmation_seconds: float = 0.0,
) -> list[PossessionObservation]:
    if (
        maximum_flyby_speed_pixels_per_second is not None
        and maximum_flyby_speed_pixels_per_second <= 0
    ):
        raise ValueError("Maximum fly-by pixel speed must be positive")
    if (
        maximum_flyby_speed_heights_per_second is not None
        and maximum_flyby_speed_heights_per_second <= 0
    ):
        raise ValueError("Maximum fly-by normalized speed must be positive")
    if (
        maximum_flyby_speed_pixels_per_second is not None
        or maximum_flyby_speed_heights_per_second is not None
    ):
        if not -1 <= minimum_flyby_direction_cosine <= 1:
            raise ValueError("Fly-by direction cosine must be between -1 and 1")
    if (
        maximum_ground_contact_height_ratio is not None
        and maximum_ground_contact_height_ratio < 0
    ):
        raise ValueError("Maximum ground-contact height ratio cannot be negative")
    if not -1 <= maximum_aerial_contact_direction_cosine <= 1:
        raise ValueError("Aerial-contact direction cosine must be between -1 and 1")
    if future_control_confirmation_seconds < 0:
        raise ValueError("Future control confirmation cannot be negative")
    motion = _ball_motion_evidence(balls)
    proximity_by_track: dict[int, list[tuple[float, float, float]]] = defaultdict(
        list
    )
    for source_frame, frame_balls in balls.items():
        for ball in frame_balls:
            for player in players.get(source_frame, []):
                height = max(1.0, float(player["y2"]) - float(player["y1"]))
                player_x = (float(player["x1"]) + float(player["x2"])) / 2
                player_y = float(player["y2"])
                distance = hypot(
                    float(ball["x"]) - player_x,
                    float(ball["y"]) - player_y,
                )
                ratio = distance / height
                if ratio <= control_radius_heights:
                    proximity_by_track[int(player["track_id"])].append(
                        (
                            float(ball["clip_seconds"]),
                            (player_y - float(ball["y"])) / height,
                            ratio,
                        )
                    )
    observations: list[PossessionObservation] = []
    for source_frame, frame_balls in sorted(balls.items()):
        frame_players = players.get(source_frame, [])
        candidates: list[
            tuple[float, float, dict[str, Any], dict[str, Any]]
        ] = []
        for ball in frame_balls:
            evidence = motion.get(
                (int(ball["track_id"]), int(source_frame))
            )
            ball_candidates: list[
                tuple[float, float, dict[str, Any], dict[str, Any]]
            ] = []
            for player in frame_players:
                height = max(1.0, float(player["y2"]) - float(player["y1"]))
                player_x = (float(player["x1"]) + float(player["x2"])) / 2
                player_y = float(player["y2"])
                distance = hypot(
                    float(ball["x"]) - player_x,
                    float(ball["y"]) - player_y,
                )
                ratio = distance / height
                ball_height_ratio = (
                    player_y - float(ball["y"])
                ) / height
                horizontal_ratio = abs(
                    float(ball["x"]) - player_x
                ) / height
                future_control_confirmed = (
                    future_control_confirmation_seconds > 0
                    and maximum_ground_contact_height_ratio is not None
                    and bool(observations)
                    and observations[-1].team == str(player["team"])
                    and any(
                        0
                        < candidate_seconds - float(ball["clip_seconds"])
                        <= future_control_confirmation_seconds
                        and candidate_height_ratio
                        <= maximum_ground_contact_height_ratio
                        and candidate_ratio <= 0.5
                        for (
                            candidate_seconds,
                            candidate_height_ratio,
                            candidate_ratio,
                        ) in proximity_by_track[int(player["track_id"])]
                    )
                )
                elevated_without_deflection = (
                    maximum_ground_contact_height_ratio is not None
                    and ball_height_ratio > maximum_ground_contact_height_ratio
                    and not future_control_confirmed
                    and (
                        evidence is None
                        or evidence[1]
                        > maximum_aerial_contact_direction_cosine
                        or horizontal_ratio > 0.5
                    )
                )
                if elevated_without_deflection:
                    continue
                if ratio <= control_radius_heights:
                    ball_candidates.append((distance, ratio, ball, player))
            if not ball_candidates:
                continue
            nearest = min(ball_candidates, key=lambda item: item[0])
            nearest_matches_prior_owner = (
                bool(observations)
                and observations[-1].team == str(nearest[3]["team"])
            )
            future_nearest_control_confirmed = (
                nearest_matches_prior_owner
                and any(
                    0
                    < candidate_seconds - float(nearest[2]["clip_seconds"])
                    <= future_control_confirmation_seconds
                    and candidate_height_ratio
                    <= (
                        maximum_ground_contact_height_ratio
                        if maximum_ground_contact_height_ratio is not None
                        else 0.4
                    )
                    and candidate_ratio <= 0.5
                    for (
                        candidate_seconds,
                        candidate_height_ratio,
                        candidate_ratio,
                    ) in proximity_by_track[int(nearest[3]["track_id"])]
                )
            )
            if (
                evidence is not None
                and evidence[1] >= minimum_flyby_direction_cosine
                and not future_nearest_control_confirmed
            ):
                pixel_flyby = (
                    maximum_flyby_speed_pixels_per_second is not None
                    and evidence[0] >= maximum_flyby_speed_pixels_per_second
                )
                nearest_height = max(
                    1.0,
                    float(nearest[3]["y2"]) - float(nearest[3]["y1"]),
                )
                normalized_flyby = (
                    maximum_flyby_speed_heights_per_second is not None
                    and evidence[0] / nearest_height
                    >= maximum_flyby_speed_heights_per_second
                )
                if pixel_flyby or normalized_flyby:
                    continue
            candidates.extend(ball_candidates)
        if not candidates:
            continue
        _, ratio, ball, player = min(candidates, key=lambda item: item[0])
        observations.append(
            PossessionObservation(
                source_frame=source_frame,
                clip_seconds=float(ball["clip_seconds"]),
                team=str(player["team"]),
                player_track_id=int(player["track_id"]),
                player_x=(float(player["x1"]) + float(player["x2"])) / 2,
                player_y=float(player["y2"]),
                player_height=max(
                    1.0, float(player["y2"]) - float(player["y1"])
                ),
                ball_x=float(ball["x"]),
                ball_y=float(ball["y"]),
                control_ratio=round(ratio, 4),
                ball_interpolated=bool(ball.get("interpolated", False)),
            )
        )
    return observations


def _ball_motion_evidence(
    balls: dict[int, list[dict[str, Any]]],
) -> dict[tuple[int, int], tuple[float, float]]:
    tracks: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame_points in balls.values():
        for point in frame_points:
            if not point.get("interpolated", False):
                tracks[int(point["track_id"])].append(point)
    evidence: dict[tuple[int, int], tuple[float, float]] = {}
    for track_id, points in tracks.items():
        ordered = sorted(points, key=lambda point: float(point["clip_seconds"]))
        for previous, current, following in zip(
            ordered, ordered[1:], ordered[2:]
        ):
            incoming_seconds = float(current["clip_seconds"]) - float(
                previous["clip_seconds"]
            )
            outgoing_seconds = float(following["clip_seconds"]) - float(
                current["clip_seconds"]
            )
            if incoming_seconds <= 0 or outgoing_seconds <= 0:
                continue
            incoming = (
                float(current["x"]) - float(previous["x"]),
                float(current["y"]) - float(previous["y"]),
            )
            outgoing = (
                float(following["x"]) - float(current["x"]),
                float(following["y"]) - float(current["y"]),
            )
            incoming_distance = hypot(*incoming)
            outgoing_distance = hypot(*outgoing)
            if incoming_distance == 0 or outgoing_distance == 0:
                continue
            cosine = (
                incoming[0] * outgoing[0] + incoming[1] * outgoing[1]
            ) / (incoming_distance * outgoing_distance)
            speed = max(
                incoming_distance / incoming_seconds,
                outgoing_distance / outgoing_seconds,
            )
            evidence[(track_id, int(current["source_frame"]))] = (
                speed,
                cosine,
            )
    return evidence


def _smooth_teams(
    observations: list[PossessionObservation],
    window_seconds: float,
) -> list[PossessionObservation]:
    if window_seconds <= 0:
        return list(observations)
    smoothed: list[PossessionObservation] = []
    for index, observation in enumerate(observations):
        nearby = [
            item
            for item in observations
            if abs(item.clip_seconds - observation.clip_seconds) <= window_seconds
        ]
        votes: dict[str, float] = defaultdict(float)
        for item in nearby:
            votes[item.team] += 1 / max(0.1, item.control_ratio) ** 2
        team = max(votes, key=votes.get)
        continued_team_control = (
            index > 0
            and observations[index - 1].team == observation.team
            and observation.clip_seconds
            - observations[index - 1].clip_seconds
            <= window_seconds
        )
        if (
            team == observation.team
            or observation.control_ratio <= 0.35
            or continued_team_control
        ):
            smoothed.append(observation)
    return smoothed


def _load_player_points(
    path: Path, expected_manifest: Path
) -> dict[int, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if Path(payload.get("manifest", "")).resolve() != expected_manifest:
        raise ValueError("Player tracks were created for a different manifest")
    points: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for track in payload.get("tracks", []):
        for point in track.get("points", []):
            point_team = point.get("team")
            if point_team not in {"red", "black", "blue", "white"}:
                continue
            value = dict(point)
            value["team"] = point_team
            value["track_id"] = int(track["track_id"])
            value["role"] = track.get("role", "player")
            points[int(point["source_frame"])].append(value)
    return points


def _load_ball_points(
    path: Path, expected_manifest: Path
) -> dict[int, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if Path(payload.get("manifest", "")).resolve() != expected_manifest:
        raise ValueError("Ball tracks were created for a different manifest")
    points: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for track in payload.get("tracks", []):
        for point in track.get("points", []):
            value = dict(point)
            value["track_id"] = int(track["track_id"])
            points[int(point["source_frame"])].append(value)
    return points


def _video_dimensions(video: Path) -> tuple[int, int]:
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        capture.release()
    if width <= 0 or height <= 0:
        raise ValueError("Benchmark video dimensions are invalid")
    return width, height
