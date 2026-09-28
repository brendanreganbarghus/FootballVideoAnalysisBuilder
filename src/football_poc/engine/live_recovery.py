from __future__ import annotations

from football_poc.engine.common import *

def _live_infer_unobserved_chain_contacts(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
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
                contact = min(
                    nearby_controls,
                    key=lambda control: control.control_ratio,
                ).clip_seconds
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

def _live_reconcile_intervening_opponent_aerial_contacts(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    maximum_direction_cosine: float = -0.75,
    maximum_control_ratio: float = 1.0,
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

def _live__smooth_teams(
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

def _live_collapse_transient_opponent_segments(
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
                transient_bridge = (
                    transient_duration <= maximum_transient_seconds
                    and following_gap <= continuity_window
                )
                coherent_opponent_control = any(
                    len(segment.observations) >= 4
                    and sum(
                        observation.control_ratio <= 0.5
                        for observation in segment.observations
                    )
                    >= 2
                    for segment in source[index:end]
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
