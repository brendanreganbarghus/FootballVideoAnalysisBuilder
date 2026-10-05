from __future__ import annotations

from football_poc.engine.common import *

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
        if gained_by is None:
            inferred_owners = [
                observation
                for observation in controls
                if observation.team == outgoing.team
                and observation.player_track_id != passer
                and turnover.completion_seconds
                <= observation.clip_seconds
                < first_passer_control.clip_seconds
                and observation.control_ratio <= maximum_control_ratio
            ]
            if not inferred_owners:
                continue
            gained_by = max(
                inferred_owners,
                key=lambda observation: observation.clip_seconds,
            ).player_track_id
        if (
            gained_by == passer
            or frozenset((gained_by, passer)) not in distinct_players
        ):
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
    players: dict[int, list[dict[str, Any]]] | None = None,
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
        tracking_gap_supported = (
            reentry_index > 0
            and float(points[reentry_index]["clip_seconds"])
            - float(points[reentry_index - 1]["clip_seconds"])
            >= minimum_tracking_gap_seconds
            and observation.clip_seconds
            - float(points[reentry_index]["clip_seconds"])
            <= maximum_reentry_control_seconds + 1e-9
        )
        continuous_first_visible_supported = (
            players is not None
            and reentry_index == 0
            and observation.clip_seconds
            - float(points[reentry_index]["clip_seconds"])
            <= maximum_reentry_control_seconds + 1e-9
        )
        if not tracking_gap_supported and not continuous_first_visible_supported:
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
        if prior.player_track_id == observation.player_track_id:
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
            (not following and not continuous_first_visible_supported)
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
            event.event_type in {"pass_candidate", "turnover_candidate"}
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
        if any(
            observation.player_track_id == receiver.player_track_id
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
