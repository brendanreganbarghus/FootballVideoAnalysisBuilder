from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from math import hypot
from pathlib import Path
from typing import Any, Iterable

import cv2

from football_poc.benchmark import BenchmarkManifest


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
    evaluation_tolerance_seconds: float = 1.0,
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
    stable_segments = [
        segment
        for segment in segments
        if len(segment.observations) >= minimum_segment_observations
    ]
    segment_transfer_events = infer_transfer_events(
        stable_segments,
        maximum_transfer_seconds=maximum_transfer_seconds,
        minimum_transfer_heights=minimum_transfer_heights,
    )
    flight_transfer_events = infer_flight_transfer_events(
        balls,
        state_segments,
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
        [*flight_transfer_events, *deceleration_transfer_events],
        segment_transfer_events,
        deduplication_seconds=transfer_deduplication_seconds,
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
    if boundary_events_path is not None:
        boundary_payload = json.loads(
            boundary_events_path.read_text(encoding="utf-8")
        )
        boundary_intervals = filter_aerial_boundary_intervals(
            boundary_payload.get("intervals", []),
            stable_segments,
        )
        boundary_intervals = annotate_restart_releases(
            boundary_intervals,
            balls,
            minimum_speed_pixels_per_second=(
                minimum_restart_speed_pixels_per_second
            ),
        )
        transfer_events = [
            event
            for event in transfer_events
            if not _event_released_outside(event, boundary_intervals)
            and not _event_completed_outside(event, boundary_intervals)
            and not _deceleration_immediately_precedes_boundary(
                event, boundary_intervals
            )
        ]
        boundary_turnovers = infer_boundary_turnovers(
            boundary_intervals,
            stable_segments,
            prior_events=transfer_events,
            ownership_lookback_seconds=boundary_ownership_lookback_seconds,
        )
        transfer_events = sorted(
            transfer_events
            + boundary_turnovers
            + infer_restart_passes(
                boundary_intervals,
                stable_segments,
                prior_events=[*transfer_events, *boundary_turnovers],
                ownership_lookback_seconds=boundary_ownership_lookback_seconds,
                balls=balls,
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
        stable_turnover_state_segments = [
            segment
            for segment in turnover_state_segments
            if len(segment.observations) >= minimum_segment_observations
        ]
        turnover_segments = build_possession_segments(
            turnover_observations,
            segment_gap_seconds=segment_gap_seconds,
            identity_switch_radius_heights=identity_switch_radius_heights,
            co_visible_track_return_seconds=co_visible_track_return_seconds,
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
        stable_turnover_segments = [
            segment
            for segment in turnover_segments
            if len(segment.observations) >= minimum_segment_observations
        ]
        turnover_segment_events = infer_transfer_events(
            stable_turnover_segments,
            maximum_transfer_seconds=maximum_transfer_seconds,
            minimum_transfer_heights=minimum_transfer_heights,
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
    ground_truth = [
        {
            "event_type": (
                "pass"
                if action.get("label") in {"pass", "high_pass"}
                else action.get("label")
            ),
            "clip_seconds": float(action["clip_seconds"]),
            "source_label": action.get("label"),
            "team": action.get("team"),
        }
        for action in manifest.actions
        if action.get("label") in {"pass", "high_pass", "shot"}
    ]
    evaluation = evaluate_events(
        events,
        ground_truth,
        tolerance_seconds=evaluation_tolerance_seconds,
    )

    output.mkdir(parents=True, exist_ok=True)
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
    (output / "event-evaluation.json").write_text(
        json.dumps(evaluation, indent=2), encoding="utf-8"
    )
    print(f"Possession and event outputs written to {output.resolve()}")
    return destination


def build_possession_segments(
    observations: Iterable[PossessionObservation],
    *,
    segment_gap_seconds: float,
    identity_switch_radius_heights: float,
    co_visible_track_return_seconds: float = 0.0,
) -> list[PossessionSegment]:
    if co_visible_track_return_seconds < 0:
        raise ValueError("Co-visible track return duration cannot be negative")
    ordered = sorted(observations, key=lambda item: item.clip_seconds)
    incompatible_track_pairs: set[frozenset[int]] = set()
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
            observation.player_track_id == current.player_track_id
            or player_distance / player_scale <= identity_switch_radius_heights
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
            and same_physical_player
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
                if (
                    transient_duration <= maximum_transient_seconds
                    or owner_continuity
                ):
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
) -> list[PredictedEvent]:
    stable = list(segments)
    events: list[PredictedEvent] = []
    for previous, current in zip(stable, stable[1:]):
        gap = current.start_seconds - previous.end_seconds
        if gap < 0 or gap > maximum_transfer_seconds:
            continue
        if previous.player_track_id == current.player_track_id:
            continue
        previous_last = previous.observations[-1]
        current_first = current.observations[0]
        scale = max(
            1.0,
            (previous_last.player_height + current_first.player_height) / 2,
        )
        travel = hypot(
            current_first.ball_x - previous_last.ball_x,
            current_first.ball_y - previous_last.ball_y,
        )
        travel_heights = travel / scale
        if travel_heights < minimum_transfer_heights:
            continue

        event_type = (
            "pass_candidate"
            if previous.team == current.team
            else "turnover_candidate"
        )
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
                clip_seconds=previous.end_seconds,
                team=previous.team,
                from_player_track_id=previous.player_track_id,
                to_player_track_id=current.player_track_id,
                confidence=round(confidence, 4),
                details=(
                    f"Control transferred after {gap:.2f}s and "
                    f"{travel_heights:.2f} player-heights of ball travel."
                ),
                completion_seconds=round(current.start_seconds, 3),
            )
        )
    return events


def infer_flight_transfer_events(
    balls: dict[int, list[dict[str, Any]]],
    possession_segments: Iterable[PossessionSegment],
    *,
    minimum_speed_pixels_per_second: float,
    maximum_step_seconds: float,
    debounce_seconds: float,
    sender_lookback_seconds: float,
    receiver_window_seconds: float,
    minimum_sender_observations: int = 1,
    minimum_receiver_observations: int = 1,
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
    events: list[PredictedEvent] = []
    for timestamp, speed in grouped_releases:
        senders = [
            segment
            for segment in segments
            if segment.start_seconds <= timestamp
            and segment.end_seconds >= timestamp - sender_lookback_seconds
            and len(segment.observations) >= minimum_sender_observations
        ]
        if not senders:
            continue
        sender = max(senders, key=lambda segment: segment.end_seconds)
        receivers = [
            segment
            for segment in segments
            if timestamp <= segment.start_seconds
            <= timestamp + receiver_window_seconds
            and segment.player_track_id != sender.player_track_id
            and len(segment.observations) >= minimum_receiver_observations
        ]
        if not receivers:
            continue
        receiver = receivers[0]
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
                details=(
                    f"Ball release at {speed:.2f} pixels/second followed by "
                    f"{receiver.team} control after "
                    f"{receiver.start_seconds - timestamp:.2f}s."
                ),
                completion_seconds=round(receiver.start_seconds, 3),
            )
        )
    return _deduplicate_receptions(events)


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
        if (
            not nearby
            or min(item.control_ratio for item in nearby)
            <= maximum_receiver_control_ratio
        ):
            accepted.append(event)
    return accepted


def _deduplicate_receptions(
    events: Iterable[PredictedEvent],
    *,
    completion_tolerance_seconds: float = 0.25,
) -> list[PredictedEvent]:
    accepted: list[PredictedEvent] = []
    for event in sorted(events, key=lambda item: item.clip_seconds):
        duplicate_index = next(
            (
                index
                for index, prior in enumerate(accepted)
                if prior.from_player_track_id == event.from_player_track_id
                and prior.to_player_track_id == event.to_player_track_id
                and prior.completion_seconds is not None
                and event.completion_seconds is not None
                and abs(prior.completion_seconds - event.completion_seconds)
                <= completion_tolerance_seconds
            ),
            None,
        )
        if duplicate_index is None:
            accepted.append(event)
        else:
            accepted[duplicate_index] = event
    return accepted


def infer_boundary_turnovers(
    intervals: Iterable[dict[str, Any]],
    possession_segments: Iterable[PossessionSegment],
    *,
    prior_events: Iterable[PredictedEvent] = (),
    ownership_lookback_seconds: float = 2.0,
    event_deduplication_seconds: float = 3.0,
) -> list[PredictedEvent]:
    segments = list(possession_segments)
    existing = list(prior_events)
    events: list[PredictedEvent] = []
    for interval in intervals:
        if interval.get("starts_outside"):
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
    maximum_prior_gap_seconds: float = 0.5,
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
) -> bool:
    if event.event_type != "pass_candidate":
        return False
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
) -> list[PredictedEvent]:
    segments = list(possession_segments)
    existing = list(prior_events)
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
        receiver_confirmed_turnover = any(
            event.event_type == "turnover_candidate"
            and event.team == owner.team
            and event.to_player_track_id is not None
            and abs(event.clip_seconds - start) <= 3.0
            for event in existing
        )
        if receiver_confirmed_turnover:
            continue
        receivers = [
            segment
            for segment in segments
            if resumed <= segment.start_seconds <= resumed + maximum_reception_seconds
            and segment.team != owner.team
        ]
        if not receivers:
            continue
        receiver = min(receivers, key=lambda segment: segment.start_seconds)
        completion = (
            _restart_reception_seconds(
                balls,
                resumed_seconds=resumed,
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
                clip_seconds=round(resumed, 3),
                team=receiver.team,
                from_player_track_id=None,
                to_player_track_id=receiver.player_track_id,
                confidence=0.55,
                details=(
                    f"After {owner.team} put the ball outside, play resumed and "
                    f"the opposing {receiver.team} team made the first detected "
                    "controlled touch. Restart taker is not visible."
                ),
                completion_seconds=round(completion, 3),
            )
        )
    return events


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
    merged = sorted(primary, key=lambda event: event.clip_seconds)
    for event in sorted(fallback, key=lambda item: item.clip_seconds):
        if any(
            abs(event.clip_seconds - accepted.clip_seconds)
            <= deduplication_seconds
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
    for observation in observations:
        nearby = [
            item
            for item in observations
            if abs(item.clip_seconds - observation.clip_seconds) <= window_seconds
        ]
        votes: dict[str, float] = defaultdict(float)
        for item in nearby:
            votes[item.team] += 1 / max(0.1, item.control_ratio) ** 2
        team = max(votes, key=votes.get)
        if team == observation.team or observation.control_ratio <= 0.35:
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
        track_team = track.get("team")
        for point in track.get("points", []):
            point_team = point.get("team")
            if point_team not in {"red", "black", "blue", "white"}:
                point_team = track_team
            if point_team not in {"red", "black", "blue", "white"}:
                continue
            value = dict(point)
            value["team"] = point_team
            value["track_id"] = int(track["track_id"])
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
