from __future__ import annotations

from football_poc.engine.common import *

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
    sender_reestablished_seconds: float = 1.0,
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
        if controls and (not losing_control or not gaining_control):
            continue
        sender_reestablished = sorted(
            observation.clip_seconds
            for observation in controls
            if event.from_player_track_id is not None
            and observation.player_track_id == event.from_player_track_id
            and observation.team == event.team
            and contact_seconds < observation.clip_seconds <= event.clip_seconds
        )
        if (
            sender_reestablished
            and sender_reestablished[-1] - sender_reestablished[0]
            >= sender_reestablished_seconds
        ):
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
                    < float(ball["clip_seconds"])
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
            terminal_contact = next(
                (
                    (float(ball["clip_seconds"]), receiver_track_id)
                    for _, frame_balls in sorted(balls.items())
                    for ball in frame_balls
                    if completion - 1.0
                    <= float(ball["clip_seconds"])
                    <= completion
                    and (
                        receiver_track_id
                        := _controlled_contact_with_local_identity(
                            players,
                            ball,
                            receiver_team,
                            motion,
                            minimum_speed_pixels_per_second=(
                                minimum_speed_pixels_per_second
                            ),
                        )
                    )
                    is not None
                ),
                None,
            )
            terminal_completion = (
                terminal_contact[0]
                if terminal_contact is not None
                else completion
            )
            source[event_index] = replace(
                event,
                team=receiver_team,
                to_player_track_id=(
                    terminal_contact[1]
                    if terminal_contact is not None
                    else event.to_player_track_id
                ),
                completion_seconds=round(terminal_completion, 3),
                details=(
                    "Deferred receiver validation confirmed the new "
                    + (
                        "possession team at its earliest direction-changing "
                        "controlled touch. "
                        if terminal_contact is not None
                        else "possession team. "
                    )
                    + event.details
                ),
            )
            completion = terminal_completion
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
                receiver_track_id = _controlled_contact_with_local_identity(
                    players,
                    ball,
                    receiver_team,
                    motion,
                    minimum_speed_pixels_per_second=(
                        minimum_speed_pixels_per_second
                    ),
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
                            "direction-changing intermediate same-team "
                            "controlled contact."
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

def infer_pass_sender_established_turnovers(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    observations: Iterable[PossessionObservation],
    *,
    maximum_transfer_seconds: float,
    maximum_sender_control_ratio: float = 1.1,
    minimum_sender_observations: int = 2,
) -> list[PredictedEvent]:
    """Recover a turnover proved by the new team's subsequent completed pass."""
    source = list(events)
    segments = list(possession_segments)
    controls = list(observations)
    additions: list[PredictedEvent] = []
    for event in source:
        if (
            event.event_type != "pass_candidate"
            or event.team is None
            or event.from_player_track_id is None
        ):
            continue
        prior_owner = max(
            (
                segment
                for segment in segments
                if segment.team != event.team
                and segment.end_seconds <= event.clip_seconds
                and event.clip_seconds - segment.end_seconds
                <= maximum_transfer_seconds
                and _segment_has_strong_control_evidence(segment)
            ),
            key=lambda segment: segment.end_seconds,
            default=None,
        )
        if prior_owner is None:
            continue
        sender_evidence = [
            observation
            for observation in controls
            if observation.team == event.team
            and observation.player_track_id == event.from_player_track_id
            and prior_owner.end_seconds < observation.clip_seconds
            <= event.clip_seconds + 1e-9
            and observation.control_ratio <= maximum_sender_control_ratio
        ]
        if len(sender_evidence) < minimum_sender_observations:
            continue
        if any(
            candidate.team == event.team
            and (
                candidate.completion_seconds or candidate.clip_seconds
            )
            <= event.clip_seconds
            and (
                candidate.completion_seconds or candidate.clip_seconds
            )
            > prior_owner.end_seconds
            for candidate in source
            if candidate is not event
        ):
            continue
        if any(
            candidate.event_type == "turnover_candidate"
            and candidate.team == prior_owner.team
            and prior_owner.end_seconds
            <= (candidate.completion_seconds or candidate.clip_seconds)
            <= event.clip_seconds + 0.4
            for candidate in [*source, *additions]
        ):
            continue
        additions.append(
            PredictedEvent(
                event_type="turnover_candidate",
                clip_seconds=round(prior_owner.end_seconds, 3),
                team=prior_owner.team,
                from_player_track_id=prior_owner.player_track_id,
                to_player_track_id=event.from_player_track_id,
                confidence=0.65,
                details=(
                    "The new team's subsequent completed pass established "
                    "controlled possession by its sender after the prior "
                    "opponent's controlled spell."
                ),
                completion_seconds=round(event.clip_seconds, 3),
            )
        )
    return sorted(
        [*source, *additions],
        key=lambda event: event.clip_seconds,
    )

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



def run(results_dir: Path, settings: TurnoverSettings = TurnoverSettings()) -> dict[str, Any]:
    events = read_stage_json(results_dir / "predicted-events.json")
    turnovers = [event for event in events if event.get("event_type") == settings.event_type]
    return {"stage": "turnover", "count": len(turnovers), "events": turnovers}
