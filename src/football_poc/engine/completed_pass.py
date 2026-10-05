from __future__ import annotations

from football_poc.engine.common import *

def infer_transfer_events(
    segments: Iterable[PossessionSegment],
    *,
    maximum_transfer_seconds: float,
    minimum_transfer_heights: float,
    receiver_return_confirmation_seconds: float = 1.2,
    control_observations: Iterable[PossessionObservation] = (),
    maximum_uncontested_transfer_seconds: float = 6.0,
    co_visible_track_pairs: set[frozenset[int]] = frozenset(),
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
        previous_index = current_index - 1
        while previous_index >= 0 and stable[previous_index] is not previous:
            previous_index -= 1
        earlier = stable[previous_index - 1] if previous_index >= 1 else None
        sender_dribbling = (
            not previous_controls
            and len(previous.observations) >= 3
            and previous_last.control_ratio <= 1.0
            and earlier is not None
            and earlier.player_track_id == previous.player_track_id
            and earlier.team == previous.team
            and any(
                observation.control_ratio <= 0.5
                for observation in earlier.observations
            )
            and previous.start_seconds - earlier.end_seconds
            <= receiver_return_confirmation_seconds + 1e-9
        )
        if len(current_controls) >= 2:
            current_first = current_controls[0]
        gap = current_first.clip_seconds - previous_last.clip_seconds
        if gap < 0:
            continue
        if gap > maximum_transfer_seconds and not (
            previous.team == current.team
            and controls
            and gap <= maximum_uncontested_transfer_seconds
            and frozenset(
                (previous.player_track_id, current.player_track_id)
            )
            in co_visible_track_pairs
            and not any(
                observation.team != previous.team
                and previous_last.clip_seconds
                < observation.clip_seconds
                < current_first.clip_seconds
                for observation in controls
            )
        ):
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
            (previous_last.control_ratio > 0.5 and not sender_dribbling)
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
                    and (
                        observation.control_ratio <= 1.0
                        or (
                            observation.control_ratio
                            <= maximum_reception_ratio
                            and _segment_has_reception_evidence(
                                segment, balls, motion_evidence=motion
                            )
                        )
                    )
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

# A pass can take about a second to reach its receiver. Ball positions arrive
# only once per sample, so one sample interval is added as margin.
DECELERATION_MAXIMUM_FLIGHT_SECONDS = 1.0


def infer_deceleration_transfer_events(
    balls: dict[int, list[dict[str, Any]]],
    possession_segments: Iterable[PossessionSegment],
    *,
    minimum_incoming_speed_pixels_per_second: float,
    maximum_outgoing_speed_ratio: float,
    sender_lookback_seconds: float,
    receiver_window_seconds: float,
    minimum_transfer_heights: float,
    players: dict[int, list[dict[str, Any]]] | None = None,
    reception_reach_heights: float = 1.2,
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
    sample_gaps = sorted(
        gap
        for gap in (
            float(second["clip_seconds"]) - float(first["clip_seconds"])
            for first, second in zip(all_points, all_points[1:])
        )
        if gap > 0
    )
    sample_seconds = sample_gaps[len(sample_gaps) // 2] if sample_gaps else 0.0
    maximum_flight_seconds = min(
        sender_lookback_seconds,
        DECELERATION_MAXIMUM_FLIGHT_SECONDS + sample_seconds,
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
                > maximum_flight_seconds
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
            # A ball cannot stop by itself: the slow-down is a reception only
            # when a receiving-team player is within reach of the ball.
            if players is not None and not any(
                _teammate_within_reach(
                    players, point, receiver.team, reception_reach_heights
                )
                for point in (previous, current)
            ):
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

def _teammate_within_reach(
    players: dict[int, list[dict[str, Any]]],
    ball: dict[str, Any],
    team: str,
    reach_heights: float,
) -> bool:
    for player in players.get(int(ball["source_frame"]), []):
        if player.get("team") != team:
            continue
        height = max(1.0, float(player["y2"]) - float(player["y1"]))
        distance = hypot(
            (float(player["x1"]) + float(player["x2"])) / 2 - float(ball["x"]),
            float(player["y2"]) - float(ball["y"]),
        )
        if distance <= reach_heights * height:
            return True
    return False

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
        causal_replacement = next(
            (
                index
                for index, accepted in enumerate(merged)
                if accepted.event_type == event.event_type
                and accepted.team == event.team
                and accepted.from_player_track_id is not None
                and accepted.from_player_track_id == event.from_player_track_id
                and accepted.to_player_track_id == event.to_player_track_id
                and accepted.completion_seconds is not None
                and accepted.completion_seconds < accepted.clip_seconds
                and event.completion_seconds is not None
                and event.completion_seconds > event.clip_seconds
                and (
                    abs(event.clip_seconds - accepted.clip_seconds)
                    <= deduplication_seconds
                    or abs(event.completion_seconds - accepted.completion_seconds)
                    <= deduplication_seconds
                )
            ),
            None,
        )
        if causal_replacement is not None:
            merged[causal_replacement] = event
            continue
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



def run(results_dir: Path, settings: CompletedPassSettings = CompletedPassSettings()) -> dict[str, Any]:
    events = read_stage_json(results_dir / "predicted-events.json")
    passes = [event for event in events if event.get("event_type") == settings.event_type]
    return {"stage": "completed_pass", "count": len(passes), "events": passes}

def filter_ambiguous_startup_transfers(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    *,
    startup_guard_seconds: float,
    maximum_receiver_control_ratio: float,
    maximum_sender_control_ratio: float = 0.5,
    observation_tolerance_seconds: float = 0.5,
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
