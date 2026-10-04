from __future__ import annotations

from football_poc.engine.common import *

def split_acceleration_confirmed_one_touch_passes(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    minimum_leg_speed_pixels_per_second: float = 500.0,
    maximum_leg_speed_pixels_per_second: float = 1800.0,
    minimum_acceleration_ratio: float = 1.5,
    maximum_player_distance_heights: float = 0.6,
) -> list[PredictedEvent]:
    """Split a long pass when a distinct teammate makes a one-touch relay."""
    source = list(events)
    points = sorted(
        (
            point
            for frame_points in balls.values()
            for point in frame_points
            if not point.get("interpolated", False)
        ),
        key=lambda point: float(point["clip_seconds"]),
    )
    motion: dict[int, tuple[float, float]] = {}
    for previous, current, following in zip(points, points[1:], points[2:]):
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
        motion[int(current["source_frame"])] = (
            incoming_speed,
            outgoing_speed,
        )
    refined: list[PredictedEvent] = []
    additions: list[PredictedEvent] = []
    for event in source:
        completion = event.completion_seconds
        if (
            event.event_type != "pass_candidate"
            or event.team is None
            or event.from_player_track_id is None
            or event.to_player_track_id is None
            or completion is None
            or completion - event.clip_seconds < 1.0
        ):
            refined.append(event)
            continue
        candidates: list[tuple[float, int, int]] = []
        for source_frame, frame_players in players.items():
            frame_balls = balls.get(source_frame, [])
            speeds = motion.get(source_frame)
            if not frame_balls or speeds is None:
                continue
            ball = frame_balls[0]
            timestamp = float(ball["clip_seconds"])
            incoming_speed, outgoing_speed = speeds
            if (
                timestamp < event.clip_seconds + 0.2
                or timestamp > completion - 0.2
                or incoming_speed < minimum_leg_speed_pixels_per_second
                or outgoing_speed < minimum_leg_speed_pixels_per_second
                or max(incoming_speed, outgoing_speed)
                > maximum_leg_speed_pixels_per_second
                or outgoing_speed
                < incoming_speed * minimum_acceleration_ratio
                or max(incoming_speed, outgoing_speed)
                < minimum_speed_pixels_per_second
            ):
                continue
            for player in frame_players:
                track_id = int(player["track_id"])
                if (
                    str(player.get("team")) != event.team
                    or track_id
                    in {
                        event.from_player_track_id,
                        event.to_player_track_id,
                    }
                ):
                    continue
                height = max(
                    1.0,
                    float(player["y2"]) - float(player["y1"]),
                )
                distance = hypot(
                    (float(player["x1"]) + float(player["x2"])) / 2
                    - float(ball["x"]),
                    float(player["y2"]) - float(ball["y"]),
                ) / height
                if distance <= maximum_player_distance_heights:
                    candidates.append((distance, source_frame, track_id))
        if not candidates:
            refined.append(event)
            continue
        _, source_frame, receiver_track_id = min(candidates)
        ball = balls[source_frame][0]
        contact = round(float(ball["clip_seconds"]), 3)
        if any(
            other is not event
            and other.team == event.team
            and other.completion_seconds is not None
            and abs(other.completion_seconds - contact) <= 0.4
            for other in source
        ):
            refined.append(event)
            continue
        additions.append(
            PredictedEvent(
                event_type="pass_candidate",
                clip_seconds=event.clip_seconds,
                team=event.team,
                from_player_track_id=event.from_player_track_id,
                to_player_track_id=receiver_track_id,
                confidence=0.65,
                details=(
                    "A distinct same-team player accelerated a high-speed "
                    "delivery, completing the incoming pass before a "
                    "one-touch relay."
                ),
                completion_seconds=contact,
            )
        )
        refined.append(
            replace(
                event,
                clip_seconds=contact,
                from_player_track_id=receiver_track_id,
                details=(
                    "The outgoing pass began at an acceleration-confirmed "
                    f"one-touch relay. {event.details}"
                ),
            )
        )
    return _deduplicate_receptions([*refined, *additions])

def infer_terminal_brief_reception(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    segment_end_seconds: float,
    maximum_player_distance_heights: float = 0.8,
) -> list[PredictedEvent]:
    """Recover a brief same-team reception near the end of a segment."""
    source = list(events)
    controls = list(observations)
    if not source:
        return source
    previous = max(
        source,
        key=lambda event: event.completion_seconds or event.clip_seconds,
    )
    completion = previous.completion_seconds
    if (
        previous.event_type != "pass_candidate"
        or previous.team is None
        or previous.to_player_track_id is None
        or completion is None
        or segment_end_seconds - completion < 1.0
    ):
        return source
    owner_controls = [
        observation
        for observation in controls
        if observation.team == previous.team
        and observation.player_track_id == previous.to_player_track_id
        and observation.clip_seconds >= completion
        and observation.control_ratio <= 0.7
    ]
    if not owner_controls:
        return source
    last_owner = max(
        owner_controls,
        key=lambda observation: observation.clip_seconds,
    )
    candidates: list[tuple[float, int, int]] = []
    for source_frame, frame_players in players.items():
        frame_balls = balls.get(source_frame, [])
        if not frame_balls:
            continue
        ball = frame_balls[0]
        timestamp = float(ball["clip_seconds"])
        if not (
            last_owner.clip_seconds + 0.4
            <= timestamp
            <= segment_end_seconds - 0.6
        ):
            continue
        for player in frame_players:
            track_id = int(player["track_id"])
            if (
                track_id == previous.to_player_track_id
                or str(player.get("team")) != previous.team
            ):
                continue
            height = max(
                1.0,
                float(player["y2"]) - float(player["y1"]),
            )
            distance = hypot(
                (float(player["x1"]) + float(player["x2"])) / 2
                - float(ball["x"]),
                float(player["y2"]) - float(ball["y"]),
            ) / height
            if distance > maximum_player_distance_heights:
                continue
            opponent_control = any(
                observation.team != previous.team
                and observation.control_ratio <= 1.0
                and timestamp
                < observation.clip_seconds
                <= timestamp + 0.8
                for observation in controls
            )
            if opponent_control:
                candidates.append((timestamp, source_frame, track_id))
    if not candidates:
        return source
    contact, _, receiver_track_id = min(candidates)
    inferred = PredictedEvent(
        event_type="pass_candidate",
        clip_seconds=round(last_owner.clip_seconds, 3),
        team=previous.team,
        from_player_track_id=previous.to_player_track_id,
        to_player_track_id=receiver_track_id,
        confidence=0.55,
        details=(
            "A brief same-team reception was established immediately before "
            "a challenged possession transition near the segment boundary."
        ),
        completion_seconds=round(contact, 3),
    )
    return _deduplicate_receptions([*source, inferred])

def infer_delayed_first_flight_reception(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    possession_segments: Iterable[PossessionSegment],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    match_state: MatchStateTimeline,
    *,
    minimum_speed_pixels_per_second: float,
    minimum_flight_seconds: float = 1.0,
    maximum_reception_ratio: float = 0.9,
    maximum_speed_retention: float = 0.6,
    maximum_following_turnover_seconds: float = 2.0,
) -> list[PredictedEvent]:
    """Recover the first reception when play starts after a delayed long flight."""
    source = list(events)
    controls = list(observations)
    segments = list(possession_segments)
    points = sorted(
        (
            point
            for frame_points in balls.values()
            for point in frame_points
            if not point.get("interpolated", False)
        ),
        key=lambda point: float(point["clip_seconds"]),
    )
    if len(points) < 3:
        return source

    first_existing_completion = min(
        (
            event.completion_seconds
            for event in source
            if event.completion_seconds is not None
        ),
        default=float("inf"),
    )
    flight_start: float | None = None
    for index in range(1, len(points) - 1):
        previous, current, following = points[index - 1 : index + 2]
        timestamp = float(current["clip_seconds"])
        incoming_seconds = timestamp - float(previous["clip_seconds"])
        outgoing_seconds = float(following["clip_seconds"]) - timestamp
        if incoming_seconds <= 0 or outgoing_seconds <= 0:
            flight_start = None
            continue
        incoming_speed = hypot(
            float(current["x"]) - float(previous["x"]),
            float(current["y"]) - float(previous["y"]),
        ) / incoming_seconds
        outgoing_speed = hypot(
            float(following["x"]) - float(current["x"]),
            float(following["y"]) - float(current["y"]),
        ) / outgoing_seconds
        if incoming_speed >= minimum_speed_pixels_per_second:
            flight_start = (
                float(previous["clip_seconds"])
                if flight_start is None
                else flight_start
            )
        else:
            flight_start = None
            continue
        if (
            timestamp >= first_existing_completion
            or timestamp - flight_start < minimum_flight_seconds
            or outgoing_speed > incoming_speed * maximum_speed_retention
        ):
            continue
        candidates: list[
            tuple[float, dict[str, Any]]
        ] = []
        for player in players.get(int(current["source_frame"]), []):
            team = str(player.get("team"))
            if team not in {"red", "black", "blue", "white"}:
                continue
            height = max(1.0, float(player["y2"]) - float(player["y1"]))
            ratio = hypot(
                (float(player["x1"]) + float(player["x2"])) / 2
                - float(current["x"]),
                float(player["y2"]) - float(current["y"]),
            ) / height
            if ratio <= maximum_reception_ratio:
                candidates.append((ratio, player))
        if not candidates:
            continue
        _, receiver = min(candidates, key=lambda item: item[0])
        receiver_team = str(receiver["team"])
        following = next(
            (
                segment
                for segment in segments
                if segment.team != receiver_team
                and timestamp < segment.start_seconds
                <= timestamp + maximum_following_turnover_seconds
                and (
                    strong := [
                        observation
                        for observation in segment.observations
                        if observation.control_ratio <= 0.5
                    ]
                )
            ),
            None,
        )
        if following is None:
            continue
        turnover_control = min(
            (
                observation
                for observation in following.observations
                if observation.control_ratio <= 0.5
            ),
            key=lambda observation: observation.clip_seconds,
        )
        if not match_state.allows_event(
            "pass_candidate",
            flight_start,
            timestamp,
        ) or not match_state.allows_event(
            "turnover_candidate",
            timestamp,
            turnover_control.clip_seconds,
        ):
            continue
        recovered = [
            PredictedEvent(
                event_type="pass_candidate",
                clip_seconds=round(flight_start, 3),
                team=receiver_team,
                from_player_track_id=None,
                to_player_track_id=int(receiver["track_id"]),
                confidence=0.6,
                details=(
                    "A sustained in-play delivery decelerated at the first "
                    "supported controlled touch."
                ),
                completion_seconds=round(timestamp, 3),
            ),
            PredictedEvent(
                event_type="turnover_candidate",
                clip_seconds=round(timestamp, 3),
                team=receiver_team,
                from_player_track_id=int(receiver["track_id"]),
                to_player_track_id=following.player_track_id,
                confidence=0.6,
                details=(
                    "The first receiver's one-touch control was followed by "
                    "clear opponent control."
                ),
                completion_seconds=round(
                    turnover_control.clip_seconds,
                    3,
                ),
            ),
        ]
        return _deduplicate_receptions([*source, *recovered])
    return source

def infer_short_controlled_teammate_transfers(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    *,
    co_visible_track_pairs: Iterable[frozenset[int]],
    minimum_transfer_heights: float,
    maximum_segment_gap_seconds: float = 1.0,
    minimum_short_transfer_heights: float = 0.2,
) -> list[PredictedEvent]:
    """Recover short passes whose distance is below the normal flight threshold."""
    source = list(events)
    segments = list(possession_segments)
    distinct_pairs = set(co_visible_track_pairs)
    inferred: list[PredictedEvent] = []
    for sender_index, sender in enumerate(segments):
        for receiver_index in range(
            sender_index + 1,
            min(sender_index + 4, len(segments)),
        ):
            receiver = segments[receiver_index]
            controlled_receiver = [
                observation
                for observation in receiver.observations
                if observation.control_ratio <= 0.5
            ]
            pair = frozenset(
                (sender.player_track_id, receiver.player_track_id)
            )
            intervening = segments[sender_index + 1 : receiver_index]
            controlled_sender = [
                observation
                for observation in sender.observations
                if observation.control_ratio <= 0.5
            ]
            direct_handover = (
                not intervening
                and len(controlled_sender) >= 2
                and len(controlled_receiver) >= 3
            )
            if (
                sender.team != receiver.team
                or sender.player_track_id == receiver.player_track_id
                or len(sender.observations) < 2
                or len(receiver.observations) < 3
                or not any(
                    observation.control_ratio <= 1.0
                    for observation in sender.observations
                )
                or not controlled_receiver
                or pair not in distinct_pairs
                or (
                    not direct_handover
                    and (
                        len(intervening) < 2
                        or any(
                            segment.team != sender.team
                            or segment.player_track_id not in pair
                            for segment in intervening
                        )
                        or intervening[0].player_track_id
                        != receiver.player_track_id
                        or intervening[-1].player_track_id
                        != sender.player_track_id
                    )
                )
                or not 0
                <= receiver.start_seconds - sender.end_seconds
                <= maximum_segment_gap_seconds
            ):
                continue
            reception = controlled_receiver[0]
            release = (
                controlled_sender[-1]
                if direct_handover
                else sender.observations[-1]
            )
            transfer_heights = hypot(
                reception.ball_x - release.ball_x,
                reception.ball_y - release.ball_y,
            ) / max(
                1.0,
                (release.player_height + reception.player_height) / 2,
            )
            if not (
                minimum_short_transfer_heights
                <= transfer_heights
                < minimum_transfer_heights
            ) or any(
                event.completion_seconds is not None
                and abs(event.completion_seconds - reception.clip_seconds)
                <= 0.8
                and not (
                    direct_handover
                    and event.to_player_track_id == sender.player_track_id
                    and event.completion_seconds <= release.clip_seconds
                )
                for event in [*source, *inferred]
            ):
                continue
            inferred.append(
                PredictedEvent(
                    event_type="pass_candidate",
                    clip_seconds=round(release.clip_seconds, 3),
                    team=sender.team,
                    from_player_track_id=sender.player_track_id,
                    to_player_track_id=receiver.player_track_id,
                    confidence=0.6,
                    details=(
                        "Distinct co-visible teammates established "
                        "consecutive controlled touches across a short ball "
                        "transfer."
                    ),
                    completion_seconds=round(reception.clip_seconds, 3),
                )
            )
            break
    return _deduplicate_receptions([*source, *inferred])

def reconcile_brief_opponent_turnover_pairs(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    players: dict[int, list[dict[str, Any]]],
    *,
    maximum_return_seconds: float = 2.0,
    local_team_window_seconds: float = 0.8,
    minimum_local_team_points: int = 3,
) -> list[PredictedEvent]:
    """Keep a pass intact when a brief opponent detour is a team-label error."""
    source = sorted(
        events,
        key=lambda event: event.completion_seconds or event.clip_seconds,
    )
    controls = list(observations)
    points_by_track: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame_players in players.values():
        for player in frame_players:
            points_by_track[int(player["track_id"])].append(player)
    removed: set[int] = set()
    replacements: dict[int, PredictedEvent] = {}
    for first_index, second_index in zip(
        range(len(source) - 1),
        range(1, len(source)),
    ):
        first = source[first_index]
        second = source[second_index]
        first_completion = first.completion_seconds
        second_completion = second.completion_seconds
        if (
            first.event_type != "turnover_candidate"
            or second.event_type != "turnover_candidate"
            or first.team is None
            or second.team == first.team
            or first.to_player_track_id is None
            or second.from_player_track_id != first.to_player_track_id
            or second.to_player_track_id is None
            or first_completion is None
            or second_completion is None
            or not 0
            < second_completion - first_completion
            <= maximum_return_seconds
        ):
            continue
        labels = [
            classify_color_scores(
                point["color_scores"],
                team_profile=(
                    "red-black"
                    if first.team in {"red", "black"}
                    else "blue-white"
                ),
            )
            for point in points_by_track[first.to_player_track_id]
            if abs(
                float(point["clip_seconds"]) - first_completion
            )
            <= local_team_window_seconds
            and isinstance(point.get("color_scores"), dict)
        ]
        labels = [
            label
            for label in labels
            if label in {"red", "black", "blue", "white"}
        ]
        first_team_votes = sum(label == first.team for label in labels)
        second_team_votes = sum(label == second.team for label in labels)
        final_control = any(
            observation.player_track_id == second.to_player_track_id
            and observation.team == first.team
            and second_completion
            <= observation.clip_seconds
            <= second_completion + 0.4
            and observation.control_ratio <= 0.5
            for observation in controls
        )
        if (
            first_team_votes < minimum_local_team_points
            or first_team_votes <= second_team_votes
            or not final_control
        ):
            continue
        removed.add(first_index)
        replacements[second_index] = PredictedEvent(
            event_type="pass_candidate",
            clip_seconds=first.clip_seconds,
            team=first.team,
            from_player_track_id=first.from_player_track_id,
            to_player_track_id=second.to_player_track_id,
            confidence=min(first.confidence, second.confidence),
            details=(
                "Local jersey evidence rejected a brief false opponent "
                "identity; the original team retained the delivery until "
                "the next controlled teammate touch."
            ),
            completion_seconds=round(second_completion, 3),
        )
    return _deduplicate_receptions(
        [
            replacements.get(index, event)
            for index, event in enumerate(source)
            if index not in removed
        ]
    )

def split_sharp_direction_change_passes(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    minimum_pass_duration_seconds: float = 2.0,
    minimum_contact_speed_multiplier: float = 9.0,
    maximum_direction_cosine: float = -0.8,
    maximum_contact_ratio: float = 1.4,
    local_team_window_seconds: float = 0.8,
    minimum_local_team_points: int = 3,
) -> list[PredictedEvent]:
    """Split a long pass at a supported same-team one-touch redirection."""
    source = list(events)
    motion = _ball_motion_evidence(balls)
    points_by_track: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame_players in players.values():
        for player in frame_players:
            points_by_track[int(player["track_id"])].append(player)
    refined: list[PredictedEvent] = []
    additions: list[PredictedEvent] = []
    for event in source:
        completion = event.completion_seconds
        if (
            event.event_type != "pass_candidate"
            or event.team is None
            or event.to_player_track_id is None
            or completion is None
            or completion - event.clip_seconds
            < minimum_pass_duration_seconds
        ):
            refined.append(event)
            continue
        candidates: list[tuple[float, int, int]] = []
        for (ball_track_id, source_frame), (
            speed,
            direction_cosine,
        ) in motion.items():
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
                timestamp <= event.clip_seconds + 0.4
                or timestamp >= completion - 0.4
                or speed
                < (
                    minimum_speed_pixels_per_second
                    * minimum_contact_speed_multiplier
                )
                or direction_cosine > maximum_direction_cosine
            ):
                continue
            for player in players.get(source_frame, []):
                track_id = int(player["track_id"])
                if track_id in {
                    event.from_player_track_id,
                    event.to_player_track_id,
                }:
                    continue
                height = max(
                    1.0,
                    float(player["y2"]) - float(player["y1"]),
                )
                ratio = hypot(
                    (float(player["x1"]) + float(player["x2"])) / 2
                    - float(ball["x"]),
                    float(player["y2"]) - float(ball["y"]),
                ) / height
                if ratio > maximum_contact_ratio:
                    continue
                labels = [
                    classify_color_scores(
                        point["color_scores"],
                        team_profile=(
                            "red-black"
                            if event.team in {"red", "black"}
                            else "blue-white"
                        ),
                    )
                    for point in points_by_track[track_id]
                    if abs(
                        float(point["clip_seconds"]) - timestamp
                    )
                    <= local_team_window_seconds
                    and isinstance(point.get("color_scores"), dict)
                ]
                labels = [
                    label
                    for label in labels
                    if label in {"red", "black", "blue", "white"}
                ]
                if (
                    sum(label == event.team for label in labels)
                    < minimum_local_team_points
                ):
                    continue
                candidates.append((direction_cosine, source_frame, track_id))
        if not candidates:
            refined.append(event)
            continue
        _, source_frame, contact_track_id = min(candidates)
        contact = round(
            float(balls[source_frame][0]["clip_seconds"]),
            3,
        )
        additions.append(
            PredictedEvent(
                event_type="pass_candidate",
                clip_seconds=event.clip_seconds,
                team=event.team,
                from_player_track_id=event.from_player_track_id,
                to_player_track_id=contact_track_id,
                confidence=min(event.confidence, 0.6),
                details=(
                    "A sharp ball reversal with stable local same-team jersey "
                    "evidence established an intermediate one-touch reception."
                ),
                completion_seconds=contact,
            )
        )
        refined.append(
            replace(
                event,
                clip_seconds=contact,
                from_player_track_id=contact_track_id,
                details=(
                    "The outgoing pass began at a sharp, locally confirmed "
                    f"same-team one-touch contact. {event.details}"
                ),
            )
        )
    return _deduplicate_receptions([*refined, *additions])
