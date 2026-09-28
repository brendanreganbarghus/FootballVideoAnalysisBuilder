from __future__ import annotations

from football_poc.engine.common import *

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
