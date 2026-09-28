from __future__ import annotations

from football_poc.engine.common import *

def _live_build_possession_segments(
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

def _live_infer_transfer_events(
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
        if (
            previous.team == current.team
            and travel_heights < minimum_transfer_heights
        ):
            continue
        if (
            previous.team != current.team
            and travel_heights < minimum_transfer_heights
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

def _live_infer_direction_change_transfer_events(
    balls: dict[int, list[dict[str, Any]]],
    possession_segments: Iterable[PossessionSegment],
    *,
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
    events: list[PredictedEvent] = []
    for sender, receiver in zip(segments, segments[1:]):
        gap = receiver.start_seconds - sender.end_seconds
        if (
            sender.team != receiver.team
            or sender.player_track_id == receiver.player_track_id
            or gap < 0
            or gap > maximum_transfer_seconds
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

def _live_infer_flight_transfer_events(
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

def _live_merge_transfer_events(
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

def _live_filter_ambiguous_startup_transfers(
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
