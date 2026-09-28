from __future__ import annotations

from football_poc.engine.common import *

def _live_suppress_uncontrolled_opponent_turnovers(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    maximum_box_distance_heights: float = 0.25,
    maximum_continuity_seconds: float = 2.0,
) -> list[PredictedEvent]:
    """Reject turnovers where only the current team remains in direct contact."""
    accepted: list[PredictedEvent] = []
    retained_team: str | None = None
    retained_at: float | None = None
    for event in events:
        completion = event.completion_seconds
        if (
            retained_team is not None
            and retained_at is not None
            and event.event_type == "pass_candidate"
            and event.team != retained_team
            and event.clip_seconds - retained_at <= maximum_continuity_seconds
        ):
            event = replace(
                event,
                team=retained_team,
                details=(
                    "Possession continuity prevented a silent team change after "
                    f"the prior turnover was rejected. {event.details}"
                ),
            )
            retained_team = None
            retained_at = None
        if (
            event.event_type != "turnover_candidate"
            or event.to_player_track_id is None
            or completion is None
        ):
            accepted.append(event)
            continue
        ball_and_players = next(
            (
                (ball, players.get(source_frame, []))
                for source_frame, frame_balls in balls.items()
                for ball in frame_balls
                if abs(float(ball["clip_seconds"]) - completion) <= 0.04
            ),
            None,
        )
        if ball_and_players is None:
            accepted.append(event)
            continue
        ball, frame_players = ball_and_players
        nearby_teams: set[str] = set()
        for player in frame_players:
            height = max(1.0, float(player["y2"]) - float(player["y1"]))
            horizontal = max(
                float(player["x1"]) - float(ball["x"]),
                0.0,
                float(ball["x"]) - float(player["x2"]),
            )
            vertical = max(
                float(player["y1"]) - float(ball["y"]),
                0.0,
                float(ball["y"]) - float(player["y2"]),
            )
            if hypot(horizontal, vertical) / height <= maximum_box_distance_heights:
                nearby_teams.add(str(player.get("team")))
        if nearby_teams == {event.team}:
            retained_team = event.team
            retained_at = completion
            continue
        accepted.append(event)
    return accepted

def _live_refine_weak_reception_completion_times(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    *,
    maximum_confirmation_seconds: float = 0.6,
    maximum_turnover_confirmation_seconds: float = 1.2,
    maximum_strong_control_ratio: float = 0.1,
) -> list[PredictedEvent]:
    source = list(events)
    segments = list(possession_segments)
    refined: list[PredictedEvent] = []
    for event in source:
        segment = next(
            (
                candidate
                for candidate in segments
                if event.to_player_track_id == candidate.player_track_id
                and event.completion_seconds == candidate.start_seconds
                and candidate.observations[0].control_ratio > 1.0
            ),
            None,
        )
        if segment is None:
            refined.append(event)
            continue
        strong_controls = [
            observation
            for observation in segment.observations
            if observation.clip_seconds
            <= segment.start_seconds
            + (
                maximum_turnover_confirmation_seconds
                if event.event_type == "turnover_candidate"
                else maximum_confirmation_seconds
            )
            and observation.control_ratio
            <= (
                0.5
                if event.event_type == "turnover_candidate"
                else maximum_strong_control_ratio
            )
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

def _live_refine_delayed_turnovers_to_contested_decelerations(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    observations: Iterable[PossessionObservation] = (),
    *,
    minimum_speed_pixels_per_second: float,
    maximum_lookback_seconds: float = 6.0,
    maximum_outgoing_speed_ratio: float = 0.35,
    nearby_window_seconds: float = 0.21,
    maximum_box_distance_heights: float = 1.5,
) -> list[PredictedEvent]:
    """Move delayed turnovers back to an earlier contested ball-stopping touch."""
    source = sorted(events, key=lambda event: event.clip_seconds)
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
            winning_tracks: list[int] = []
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
                winning_track = _live__nearby_ball_team_track(
                    frame_players,
                    frame_balls[0],
                    winning_team,
                    maximum_box_distance_heights=maximum_box_distance_heights,
                )
                if winning_track is not None:
                    winning_tracks.append(winning_track)
            if (
                event.team in nearby_teams
                and winning_team in nearby_teams
                and winning_tracks
            ):
                winner = Counter(winning_tracks).most_common(1)[0][0]
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
                    "A contested ball deceleration located the possession "
                    f"change before later {winning_team} control."
                ),
            )
        )
    return _deduplicate_receptions(refined)

def _live_infer_ball_reentry_receptions(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    players: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    minimum_tracking_gap_seconds: float = 1.5,
    maximum_reentry_control_seconds: float = 0.4,
    maximum_following_release_seconds: float = 2.0,
    maximum_control_ratio: float = 0.7,
    minimum_distance_ratio: float = 1.5,
    maximum_contiguous_step_seconds: float = 0.4,
    minimum_sender_tracking_seconds: float = 1.0,
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
        receiver_points = [
            point
            for frame_points in players.values()
            for point in frame_points
            if int(point["track_id"]) == observation.player_track_id
        ]
        receiver_visible_before = any(
            0
            <= observation.clip_seconds - float(point["clip_seconds"])
            <= maximum_reentry_control_seconds
            for point in receiver_points
        )
        receiver_visible_after = any(
            0
            < float(point["clip_seconds"]) - observation.clip_seconds
            <= maximum_reentry_control_seconds
            for point in receiver_points
        )
        if not (receiver_visible_before and receiver_visible_after):
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
        has_tracking_gap = (
            reentry_index > 0
            and float(points[reentry_index]["clip_seconds"])
            - float(points[reentry_index - 1]["clip_seconds"])
            >= minimum_tracking_gap_seconds
            and observation.clip_seconds
            - float(points[reentry_index]["clip_seconds"])
            <= maximum_reentry_control_seconds
        )
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
        prior_controls = [
            candidate
            for candidate in controls
            if candidate.clip_seconds < observation.clip_seconds
            and any(
                candidate.clip_seconds - float(point["clip_seconds"])
                >= minimum_sender_tracking_seconds
                for frame_points in players.values()
                for point in frame_points
                if int(point["track_id"]) == candidate.player_track_id
                and float(point["clip_seconds"]) <= candidate.clip_seconds
            )
        ]
        if not prior_controls:
            continue
        prior = max(prior_controls, key=lambda candidate: candidate.clip_seconds)
        has_control_gap = (
            observation.clip_seconds - prior.clip_seconds
            >= minimum_tracking_gap_seconds
        )
        if (
            prior.team != observation.team
            or prior.player_track_id == observation.player_track_id
            or not (has_tracking_gap or has_control_gap)
        ):
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
            not following
            and not (
                has_control_gap
                and observation.ball_event_evidence_eligible
                and not observation.ball_interpolated
            )
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
                    "re-entry recovered a same-team reception after an "
                    "observation gap."
                ),
                completion_seconds=round(observation.clip_seconds, 3),
            )
        )
    return _deduplicate_receptions([*source, *inferred])

def _live_infer_unresolved_direction_change_receptions(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    maximum_direction_cosine: float = -0.25,
    maximum_control_ratio: float = 0.5,
    event_exclusion_seconds: float = 1.0,
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
            following is not None
            and following.team == observation.team
            and following.from_player_track_id == observation.player_track_id
            and (
                prior is not None
                and prior.team == observation.team
                and prior.event_type == "pass_candidate"
                or following.event_type == "pass_candidate"
            )
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
        if (
            not linked_to_possession
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
