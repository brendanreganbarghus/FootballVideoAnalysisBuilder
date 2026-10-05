from __future__ import annotations

from football_poc.engine.common import *

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

def _receiver_continuation_observations(
    segment: PossessionSegment,
    segments: list[PossessionSegment],
    *,
    weak_control_ratio: float = 0.5,
) -> list[PossessionObservation]:
    """Join a purely weak reception to the same receiver's later same-team control.

    A pass can be credited on weak proximity while the ball is still rolling
    toward the receiver; a brief ownership flicker then splits the receiver's
    possession.  The first clear touch is in the receiver's next segment as
    long as no opponent owned the ball in between.
    """
    observations = list(segment.observations)
    if any(o.control_ratio <= weak_control_ratio for o in observations):
        return observations
    later = sorted(
        (s for s in segments if s.start_seconds > segment.end_seconds),
        key=lambda s: s.start_seconds,
    )
    for candidate in later:
        if candidate.team != segment.team:
            break
        if candidate.player_track_id == segment.player_track_id:
            observations.extend(candidate.observations)
            break
    return observations

def refine_weak_reception_completion_times(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    balls: dict[int, list[dict[str, Any]]] | None = None,
    *,
    maximum_confirmation_seconds: float = 0.6,
    maximum_extended_confirmation_seconds: float = 2.5,
    maximum_turnover_confirmation_seconds: float = 1.2,
    maximum_strong_control_ratio: float = 0.1,
    minimum_terminal_observations: int = 4,
    minimum_speed_pixels_per_second: float = 60.0,
    maximum_contact_direction_cosine: float = -0.1,
    weak_start_tolerance_seconds: float = 0.41,
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
                and event.completion_seconds is not None
                and candidate.start_seconds
                <= event.completion_seconds
                <= candidate.start_seconds + weak_start_tolerance_seconds
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
                for observation in _receiver_continuation_observations(
                    segment, segments
                )
                if observation.clip_seconds
                <= (
                    max(segment.start_seconds, event.completion_seconds)
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
            terminal_controls = (
                [extended_controls[-1]]
                if (
                    len(extended_controls) >= minimum_terminal_observations
                    and extended_controls[-1].control_ratio <= 0.5
                    and extended_controls[-1].clip_seconds
                    == segment.end_seconds
                )
                else []
            )
            strong_controls = (
                verified_controls
                or sustained_confirmations
                or terminal_controls
            )
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
        strong_controls = [
            observation
            for observation in strong_controls
            if observation.clip_seconds >= event.completion_seconds
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

def infer_opening_live_reception(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    balls: dict[int, list[dict[str, Any]]],
    match_state: MatchStateTimeline,
    *,
    minimum_speed_pixels_per_second: float,
    maximum_transfer_seconds: float,
    maximum_first_control_seconds: float = 2.0,
    maximum_contact_direction_cosine: float = -0.8,
) -> list[PredictedEvent]:
    """Recover a clip-opening pass that ends at the first controlled touch."""
    source = list(events)
    segments = list(possession_segments)
    if len(segments) < 2:
        return source
    first, following = segments[:2]
    if (
        first.start_seconds <= 0
        or first.start_seconds > maximum_first_control_seconds
        or len(first.observations) < 3
        or not any(
            observation.control_ratio <= 0.5
            for observation in first.observations
        )
        or following.team != first.team
        or following.player_track_id == first.player_track_id
        or following.start_seconds - first.end_seconds
        > maximum_transfer_seconds
        or any(
            event.event_type in {"pass_candidate", "restart_pass_candidate"}
            and event.team == first.team
            and event.completion_seconds is not None
            and abs(event.completion_seconds - first.start_seconds) <= 0.5
            for event in source
        )
    ):
        return source
    motion = _ball_motion_evidence(balls)
    contacts = [
        observation
        for observation in first.observations
        if observation.clip_seconds <= first.start_seconds + 0.4
        and (
            evidence := motion.get(
                (1, observation.source_frame)
            )
        )
        is not None
        and evidence[0] >= minimum_speed_pixels_per_second
        and evidence[1] <= maximum_contact_direction_cosine
    ]
    if not contacts:
        return source
    contact = min(
        contacts,
        key=lambda observation: (
            motion[(1, observation.source_frame)][1],
            observation.clip_seconds,
        ),
    )
    if not match_state.allows_event(
        "pass_candidate",
        0.0,
        contact.clip_seconds,
    ):
        return source
    opening = PredictedEvent(
        event_type="pass_candidate",
        clip_seconds=0.0,
        team=first.team,
        from_player_track_id=None,
        to_player_track_id=first.player_track_id,
        confidence=0.6,
        details=(
            "The clip opened during a live delivery; a sharp ball-direction "
            "change and sustained teammate control established the first "
            "controlled reception."
        ),
        completion_seconds=round(contact.clip_seconds, 3),
    )
    return _deduplicate_receptions([opening, *source])

def infer_sparse_control_transfer(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
    co_visible_track_pairs: set[frozenset[int]],
    minimum_speed_pixels_per_second: float,
    maximum_control_ratio: float = 1.1,
    maximum_observation_gap_seconds: float = 1.5,
    maximum_transfer_seconds: float = 2.0,
    maximum_contact_direction_cosine: float = -0.7,
    minimum_transfer_heights: float = 0.5,
) -> list[PredictedEvent]:
    """Recover a pass when sparse tracking still supports both players."""
    source = list(events)
    grouped: list[list[PossessionObservation]] = []
    for observation in observations:
        if observation.control_ratio > maximum_control_ratio:
            continue
        if (
            grouped
            and grouped[-1][-1].team == observation.team
            and grouped[-1][-1].player_track_id
            == observation.player_track_id
            and observation.clip_seconds
            - grouped[-1][-1].clip_seconds
            <= maximum_observation_gap_seconds
        ):
            grouped[-1].append(observation)
        else:
            grouped.append([observation])
    motion = _ball_motion_evidence(balls)
    additions: list[PredictedEvent] = []
    for sender, receiver in zip(grouped, grouped[1:]):
        release = sender[-1]
        contact = receiver[0]
        gap = contact.clip_seconds - release.clip_seconds
        evidence = motion.get((1, contact.source_frame))
        scale = max(
            1.0,
            (release.player_height + contact.player_height) / 2,
        )
        travel_heights = hypot(
            contact.ball_x - release.ball_x,
            contact.ball_y - release.ball_y,
        ) / scale
        if (
            len(sender) < 2
            or release.team != contact.team
            or release.player_track_id == contact.player_track_id
            or frozenset(
                (release.player_track_id, contact.player_track_id)
            )
            not in co_visible_track_pairs
            or not 0 <= gap <= maximum_transfer_seconds
            or contact.control_ratio > 1.0
            or evidence is None
            or evidence[0] < minimum_speed_pixels_per_second
            or evidence[1] > maximum_contact_direction_cosine
            or travel_heights < minimum_transfer_heights
            or any(
                observation.team != release.team
                and observation.control_ratio <= 0.5
                and release.clip_seconds
                < observation.clip_seconds
                < contact.clip_seconds
                for observation in observations
            )
            or any(
                event.completion_seconds is not None
                and abs(
                    event.completion_seconds - contact.clip_seconds
                ) <= 1.0
                for event in [*source, *additions]
            )
        ):
            continue
        additions.append(
            PredictedEvent(
                event_type="pass_candidate",
                clip_seconds=round(release.clip_seconds, 3),
                team=release.team,
                from_player_track_id=release.player_track_id,
                to_player_track_id=contact.player_track_id,
                confidence=0.6,
                details=(
                    "Sparse same-team control was confirmed by a sharp "
                    "direction-changing reception."
                ),
                completion_seconds=round(contact.clip_seconds, 3),
            )
        )
    return _deduplicate_receptions([*source, *additions])
