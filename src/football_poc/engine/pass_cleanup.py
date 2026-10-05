from __future__ import annotations

from football_poc.engine.common import *

def collapse_competing_same_sender_receptions(
    events: Iterable[PredictedEvent],
    *,
    maximum_completion_delta_seconds: float = 0.5,
) -> list[PredictedEvent]:
    """Keep one interpretation when one sender has two overlapping receptions."""
    accepted: list[PredictedEvent] = []
    for event in sorted(
        events,
        key=lambda item: item.completion_seconds or item.clip_seconds,
    ):
        completion = event.completion_seconds
        competing_index = next(
            (
                index
                for index, prior in enumerate(accepted)
                if event.event_type == prior.event_type == "pass_candidate"
                and event.team == prior.team
                and event.from_player_track_id is not None
                and event.from_player_track_id == prior.from_player_track_id
                and completion is not None
                and prior.completion_seconds is not None
                and abs(completion - prior.completion_seconds)
                <= maximum_completion_delta_seconds
            ),
            None,
        )
        if competing_index is None:
            accepted.append(event)
            continue
        prior = accepted[competing_index]
        if event.confidence > prior.confidence:
            accepted[competing_index] = event
    return sorted(accepted, key=lambda event: event.clip_seconds)

def suppress_duplicate_track_handoff_passes(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    *,
    evidence_window_seconds: float = 0.41,
    minimum_smaller_box_overlap: float = 0.9,
) -> list[PredictedEvent]:
    """Reject same-player tracker duplicates presented as completed passes."""
    points_by_track: dict[int, dict[int, dict[str, Any]]] = defaultdict(dict)
    for frame, frame_players in players.items():
        for player in frame_players:
            track_id = player.get("track_id")
            if track_id is not None:
                points_by_track[int(track_id)][int(frame)] = player
    track_bounds = {
        track_id: (min(points), max(points))
        for track_id, points in points_by_track.items()
        if points
    }

    def overlap_fraction(
        first: dict[str, Any],
        second: dict[str, Any],
    ) -> float:
        width = max(
            0.0,
            min(float(first["x2"]), float(second["x2"]))
            - max(float(first["x1"]), float(second["x1"])),
        )
        height = max(
            0.0,
            min(float(first["y2"]), float(second["y2"]))
            - max(float(first["y1"]), float(second["y1"])),
        )
        first_area = max(
            1.0,
            (float(first["x2"]) - float(first["x1"]))
            * (float(first["y2"]) - float(first["y1"])),
        )
        second_area = max(
            1.0,
            (float(second["x2"]) - float(second["x1"]))
            * (float(second["y2"]) - float(second["y1"])),
        )
        return width * height / min(first_area, second_area)

    accepted: list[PredictedEvent] = []
    for event in events:
        completion = event.completion_seconds
        sender_id = event.from_player_track_id
        receiver_id = event.to_player_track_id
        if (
            event.event_type != "pass_candidate"
            or event.team is None
            or completion is None
            or sender_id is None
            or receiver_id is None
        ):
            accepted.append(event)
            continue
        sender_points = points_by_track.get(sender_id, {})
        receiver_points = points_by_track.get(receiver_id, {})
        duplicate_handoff = False
        for frame in sender_points.keys() & receiver_points.keys():
            sender = sender_points[frame]
            receiver = receiver_points[frame]
            timestamp = float(receiver["clip_seconds"])
            if not (
                event.clip_seconds - evidence_window_seconds
                <= timestamp
                <= completion + 1e-9
            ):
                continue
            if (
                overlap_fraction(sender, receiver)
                < minimum_smaller_box_overlap
            ):
                continue
            sender_bounds = track_bounds.get(sender_id)
            receiver_bounds = track_bounds.get(receiver_id)
            boundary_handoff = bool(
                sender_bounds
                and receiver_bounds
                and sender_bounds[1] == receiver_bounds[0] == frame
            )
            receiver_team = receiver.get("team")
            unstable_duplicate = receiver_team not in {
                None,
                "unknown",
                event.team,
            }
            if boundary_handoff or unstable_duplicate:
                duplicate_handoff = True
                break
        if not duplicate_handoff:
            accepted.append(event)
    return accepted

def suppress_noncausal_nonreturn_passes(
    events: Iterable[PredictedEvent],
    *,
    maximum_return_seconds: float = 3.0,
    observations: Iterable[PossessionObservation] | None = None,
    maximum_control_ratio: float = 1.0,
) -> list[PredictedEvent]:
    """Require reciprocal evidence when control predates inferred release.

    With observations, only a controlled receiver touch between the sender's
    last control and the release is non-causal; earlier weak proximity alone
    does not contradict a slow release.
    """
    source = list(events)
    controls = None if observations is None else list(observations)

    def receiver_controlled_before_release(event: PredictedEvent) -> bool:
        if controls is None:
            return True
        sender_last = max(
            (
                observation.clip_seconds
                for observation in controls
                if observation.player_track_id == event.from_player_track_id
                and observation.clip_seconds <= event.clip_seconds
            ),
            default=None,
        )
        return any(
            observation.player_track_id == event.to_player_track_id
            and observation.control_ratio <= maximum_control_ratio
            and (sender_last is None or observation.clip_seconds > sender_last)
            and observation.clip_seconds < event.clip_seconds
            for observation in controls
        )

    accepted: list[PredictedEvent] = []
    for event in source:
        noncausal_reception = (
            event.event_type == "pass_candidate"
            and " control after -" in event.details
            and receiver_controlled_before_release(event)
        )
        reciprocal_return = noncausal_reception and any(
            prior.event_type == "pass_candidate"
            and prior.team == event.team
            and prior.from_player_track_id == event.to_player_track_id
            and prior.to_player_track_id == event.from_player_track_id
            and prior.completion_seconds is not None
            and 0
            < event.clip_seconds - prior.completion_seconds
            <= maximum_return_seconds
            for prior in source
        )
        if not noncausal_reception or reciprocal_return:
            accepted.append(event)
    return accepted

def reconcile_late_strong_control_transfers(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
    co_visible_track_pairs: set[frozenset[int]],
    segment_end_seconds: float,
    minimum_speed_pixels_per_second: float,
    maximum_control_delay_seconds: float = 0.4,
) -> list[PredictedEvent]:
    """Prefer the last evidenced owner and causal release at a transfer."""
    segments = list(possession_segments)
    controls = list(observations)
    observed_ball_points = sorted(
        (
            point
            for frame_points in balls.values()
            for point in frame_points
            if not point.get("interpolated", False)
        ),
        key=lambda point: float(point["clip_seconds"]),
    )
    refined: list[PredictedEvent] = []
    for event in events:
        completion = event.completion_seconds
        if completion is None or event.team is None:
            refined.append(event)
            continue
        if (
            event.event_type == "pass_candidate"
            and completion < event.clip_seconds
            and segment_end_seconds - completion <= 1.5
            and event.from_player_track_id is not None
            and event.to_player_track_id is not None
            and frozenset(
                (
                    event.from_player_track_id,
                    event.to_player_track_id,
                )
            )
            in co_visible_track_pairs
        ):
            sender = max(
                (
                    observation
                    for observation in controls
                    if observation.team == event.team
                    and observation.player_track_id
                    == event.from_player_track_id
                    and completion - 1.0
                    <= observation.clip_seconds
                    <= completion
                    and observation.control_ratio <= 1.0
                ),
                key=lambda observation: observation.clip_seconds,
                default=None,
            )
            release = next(
                (
                    (float(first["clip_seconds"]), speed)
                    for first, second in zip(
                        observed_ball_points, observed_ball_points[1:]
                    )
                    if sender is not None
                    and abs(
                        float(second["clip_seconds"])
                        - sender.clip_seconds
                    )
                    <= 0.04
                    and (
                        elapsed := float(second["clip_seconds"])
                        - float(first["clip_seconds"])
                    )
                    > 0
                    and (
                        speed := hypot(
                            float(second["x"]) - float(first["x"]),
                            float(second["y"]) - float(first["y"]),
                        )
                        / elapsed
                    )
                    >= minimum_speed_pixels_per_second
                ),
                None,
            )
            if release is not None and release[0] < completion:
                release_seconds, speed = release
                refined.append(
                    replace(
                        event,
                        clip_seconds=round(release_seconds, 3),
                        confidence=round(min(0.9, 0.45 + speed / 1000), 4),
                        details=(
                            f"Ball release at {speed:.2f} pixels/second "
                            f"followed by {event.team} control after "
                            f"{completion - release_seconds:.2f}s."
                        ),
                    )
                )
                continue
        if (
            event.event_type != "turnover_candidate"
            or event.from_player_track_id is None
            or event.to_player_track_id is None
        ):
            refined.append(event)
            continue
        late_owner = max(
            (
                observation
                for observation in controls
                if observation.team == event.team
                and observation.player_track_id
                != event.from_player_track_id
                and event.clip_seconds
                < observation.clip_seconds
                <= completion
                and observation.control_ratio <= 0.5
            ),
            key=lambda observation: observation.clip_seconds,
            default=None,
        )
        if late_owner is None:
            refined.append(event)
            continue
        receiver_controls = sorted(
            (
                observation
                for observation in controls
                if observation.team != event.team
                and observation.player_track_id
                == event.to_player_track_id
                and completion
                <= observation.clip_seconds
                <= completion + maximum_control_delay_seconds + 1e-9
            ),
            key=lambda observation: observation.clip_seconds,
        )
        strong_receiver = next(
            (
                observation
                for observation in receiver_controls
                if observation.control_ratio <= 0.5
            ),
            None,
        )
        if strong_receiver is None:
            refined.append(event)
            continue
        first_receiver = receiver_controls[0]
        if first_receiver.control_ratio > 0.5:
            prior_owner = max(
                (
                    segment
                    for segment in segments
                    if segment.team == event.team
                    and segment.player_track_id
                    != late_owner.player_track_id
                    and segment.end_seconds < late_owner.clip_seconds
                ),
                key=lambda segment: segment.end_seconds,
                default=None,
            )
            receiver_segment = next(
                (
                    segment
                    for segment in segments
                    if segment.player_track_id == event.to_player_track_id
                    and segment.start_seconds
                    <= first_receiver.clip_seconds
                    <= segment.end_seconds
                ),
                None,
            )
            if prior_owner is not None and receiver_segment is not None:
                previous = prior_owner.observations[-1]
                scale = max(
                    1.0,
                    (
                        previous.player_height
                        + first_receiver.player_height
                    )
                    / 2,
                )
                travel_heights = hypot(
                    first_receiver.ball_x - previous.ball_x,
                    first_receiver.ball_y - previous.ball_y,
                ) / scale
                confidence = min(
                    1.0,
                    0.3
                    + 0.05 * min(len(prior_owner.observations), 3)
                    + 0.05 * min(len(receiver_segment.observations), 3)
                    + 0.05 * min(travel_heights, 3),
                )
                refined.append(
                    replace(
                        event,
                        clip_seconds=round(late_owner.clip_seconds, 3),
                        from_player_track_id=late_owner.player_track_id,
                        confidence=round(confidence, 4),
                        details=(
                            "The receiver's controlled touch was corroborated "
                            "by continued team control and the receiver track "
                            "returning."
                        ),
                        completion_seconds=round(
                            strong_receiver.clip_seconds, 3
                        ),
                    )
                )
                continue
        release = next(
            (
                (float(first["clip_seconds"]), speed)
                for first, second in zip(
                    observed_ball_points, observed_ball_points[1:]
                )
                if float(first["clip_seconds"])
                >= late_owner.clip_seconds + maximum_control_delay_seconds
                - 1e-9
                and float(second["clip_seconds"]) <= completion + 1e-9
                and (
                    elapsed := float(second["clip_seconds"])
                    - float(first["clip_seconds"])
                )
                > 0
                and (
                    speed := hypot(
                        float(second["x"]) - float(first["x"]),
                        float(second["y"]) - float(first["y"]),
                    )
                    / elapsed
                )
                >= minimum_speed_pixels_per_second
            ),
            None,
        )
        if release is None:
            refined.append(event)
            continue
        release_seconds, speed = release
        refined.append(
            replace(
                event,
                clip_seconds=round(release_seconds, 3),
                from_player_track_id=late_owner.player_track_id,
                confidence=round(min(0.9, 0.45 + speed / 1000), 4),
                details=(
                    f"Ball release at {speed:.2f} pixels/second followed by "
                    f"{first_receiver.team} control after "
                    f"{completion - release_seconds:.2f}s."
                ),
            )
        )
    return refined

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

def suppress_label_flicker_tackle_artifacts(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    *,
    maximum_tail_gap_seconds: float = 0.2,
    maximum_tail_flight_seconds: float = 0.4,
    label_match_seconds: float = 0.25,
) -> list[PredictedEvent]:
    """Count a tackle once when a challenged player's box flips team colour.

    During a physical challenge two opposing players overlap, so one tracked
    box can carry both kits within a second. Only when such a colour flicker is
    observed, two artifacts are rejected: a turnover whose receiver wears the
    losing team's colour and immediately "loses" the ball again, and a very
    short same-team pass that starts exactly where the tackle turnover ends.
    """
    labels: dict[int, list[tuple[float, str]]] = defaultdict(list)
    for frame_players in players.values():
        for player in frame_players:
            track_id = player.get("track_id")
            team = player.get("team")
            if track_id is not None and team in {"red", "black", "blue", "white"}:
                labels[int(track_id)].append((float(player["clip_seconds"]), str(team)))
    for points in labels.values():
        points.sort()

    def flickers(track_id: int | None, start: float, end: float) -> bool:
        if track_id is None:
            return False
        teams = {
            team
            for seconds, team in labels.get(track_id, [])
            if start - 1e-6 <= seconds <= end + 1e-6
        }
        return len(teams) >= 2

    def label_at(track_id: int | None, seconds: float) -> str | None:
        if track_id is None:
            return None
        nearest = min(
            labels.get(track_id, []),
            key=lambda point: abs(point[0] - seconds),
            default=None,
        )
        if nearest is None or abs(nearest[0] - seconds) > label_match_seconds:
            return None
        return nearest[1]

    ordered = sorted(events, key=lambda event: event.clip_seconds)
    rejected: set[int] = set()
    for index, turnover in enumerate(ordered):
        if turnover.event_type != "turnover_candidate" or turnover.team is None:
            continue
        completion = turnover.completion_seconds or turnover.clip_seconds
        following = [
            (later_index, event)
            for later_index, event in enumerate(ordered[index + 1 :], start=index + 1)
            if later_index not in rejected
        ]
        next_turnover = next(
            (
                (later_index, event)
                for later_index, event in following
                if event.event_type == "turnover_candidate"
            ),
            None,
        )
        receiver = turnover.to_player_track_id
        if (
            next_turnover is not None
            and receiver is not None
            and next_turnover[1].team not in {None, turnover.team}
            and next_turnover[1].from_player_track_id == receiver
            and label_at(receiver, completion) == turnover.team
            and flickers(
                receiver,
                completion,
                next_turnover[1].completion_seconds or next_turnover[1].clip_seconds,
            )
        ):
            rejected.add(index)
            continue
        tail = next(
            (
                (later_index, event)
                for later_index, event in following
                if event.event_type == "pass_candidate"
            ),
            None,
        )
        if tail is None:
            continue
        tail_index, tail_pass = tail
        tail_completion = tail_pass.completion_seconds
        if (
            tail_pass.team is None
            or tail_pass.team == turnover.team
            or tail_completion is None
            or receiver is None
            or tail_pass.from_player_track_id != receiver
            or abs(tail_pass.clip_seconds - completion) > maximum_tail_gap_seconds
            or tail_completion - tail_pass.clip_seconds > maximum_tail_flight_seconds
        ):
            continue
        if any(
            flickers(track_id, turnover.clip_seconds, tail_completion)
            for track_id in (
                turnover.from_player_track_id,
                receiver,
                tail_pass.to_player_track_id,
            )
        ):
            rejected.add(tail_index)
    return [event for index, event in enumerate(ordered) if index not in rejected]

def collapse_simultaneous_releases_to_same_receiver(
    events: Iterable[PredictedEvent],
    *,
    maximum_release_delta_seconds: float = 0.5,
) -> list[PredictedEvent]:
    """Count one pass when two senders "release" the same ball to one receiver.

    A ball cannot leave two different same-team players at almost the same
    moment and reach the same receiver twice; nearby boxes at the release point
    are competing interpretations of one pass, so the stronger one is kept.
    """
    accepted: list[PredictedEvent] = []
    for event in sorted(events, key=lambda item: item.clip_seconds):
        competing_index = next(
            (
                index
                for index, prior in enumerate(accepted)
                if event.event_type == prior.event_type == "pass_candidate"
                and event.team is not None
                and event.team == prior.team
                and event.to_player_track_id is not None
                and event.to_player_track_id == prior.to_player_track_id
                and event.from_player_track_id != prior.from_player_track_id
                and abs(event.clip_seconds - prior.clip_seconds)
                <= maximum_release_delta_seconds
            ),
            None,
        )
        if competing_index is None:
            accepted.append(event)
        elif event.confidence > accepted[competing_index].confidence:
            accepted[competing_index] = event
    return sorted(accepted, key=lambda event: event.clip_seconds)


def _ball_window_velocity(
    ball_points: list[dict[str, Any]], start: float, end: float
) -> tuple[float, float] | None:
    window = [
        point
        for point in ball_points
        if start - 1e-06 <= float(point["clip_seconds"]) <= end + 1e-06
    ]
    if len(window) < 2:
        return None
    first, last = window[0], window[-1]
    seconds = float(last["clip_seconds"]) - float(first["clip_seconds"])
    if seconds <= 0:
        return None
    return (
        (float(last["x"]) - float(first["x"])) / seconds,
        (float(last["y"]) - float(first["y"])) / seconds,
    )


def _completion_shows_contact(
    ball_points: list[dict[str, Any]],
    completion: float,
    *,
    window_seconds: float,
    maximum_carry_speed_ratio: float,
    minimum_carry_direction_cosine: float,
) -> bool:
    incoming = _ball_window_velocity(
        ball_points, completion - window_seconds, completion
    )
    outgoing = _ball_window_velocity(
        ball_points, completion, completion + window_seconds
    )
    if incoming is None or outgoing is None:
        return True
    incoming_speed = hypot(*incoming)
    outgoing_speed = hypot(*outgoing)
    if incoming_speed <= 0 or outgoing_speed <= 0:
        return True
    if outgoing_speed / incoming_speed <= maximum_carry_speed_ratio:
        return True
    cosine = (incoming[0] * outgoing[0] + incoming[1] * outgoing[1]) / (
        incoming_speed * outgoing_speed
    )
    return cosine < minimum_carry_direction_cosine


def merge_rolling_ball_duplicate_receptions(
    events: Iterable[PredictedEvent],
    balls: dict[int, list[dict[str, Any]]],
    *,
    maximum_gap_seconds: float = 3.0,
    window_seconds: float = 0.4,
    maximum_carry_speed_ratio: float = 0.5,
    minimum_carry_direction_cosine: float = 0.7,
) -> list[PredictedEvent]:
    """Count one pass when the ball merely rolls past the receiver first.

    Ball proximity is not a reception unless the ball also slows sharply or
    changes direction there. When a same-team pass "completes" while the ball
    keeps rolling at the same pace and heading, and the engine later finds the
    same receiver's real touch with no other event in between, both rows
    describe one pass: its completion moves to the real touch and the
    sender-less duplicate is dropped.
    """
    ball_points = sorted(
        (
            point
            for frame_points in balls.values()
            for point in frame_points
            if not point.get("interpolated", False)
        ),
        key=lambda point: float(point["clip_seconds"]),
    )
    ordered = sorted(events, key=lambda item: item.clip_seconds)
    removed: set[int] = set()
    for index, event in enumerate(ordered):
        if (
            index in removed
            or event.event_type != "pass_candidate"
            or event.from_player_track_id is None
            or event.to_player_track_id is None
            or event.completion_seconds is None
            or index + 1 >= len(ordered)
        ):
            continue
        following = ordered[index + 1]
        if (
            following.event_type != "pass_candidate"
            or following.team != event.team
            or following.from_player_track_id is not None
            or following.to_player_track_id != event.to_player_track_id
            or following.completion_seconds is None
            or not 0
            < following.completion_seconds - event.completion_seconds
            <= maximum_gap_seconds
        ):
            continue
        if _completion_shows_contact(
            ball_points,
            event.completion_seconds,
            window_seconds=window_seconds,
            maximum_carry_speed_ratio=maximum_carry_speed_ratio,
            minimum_carry_direction_cosine=minimum_carry_direction_cosine,
        ):
            continue
        ordered[index] = replace(
            event, completion_seconds=following.completion_seconds
        )
        removed.add(index + 1)
    return [event for index, event in enumerate(ordered) if index not in removed]
