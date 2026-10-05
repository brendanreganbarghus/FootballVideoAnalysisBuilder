from __future__ import annotations

from football_poc.engine.common import *

def propagate_deferred_possession_chains(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    observations: Iterable[PossessionObservation] = (),
    *,
    minimum_speed_pixels_per_second: float,
) -> list[PredictedEvent]:
    source = sorted(events, key=lambda event: event.clip_seconds)
    motion = _ball_motion_evidence(balls)
    additions: list[PredictedEvent] = []
    for anchor_index, anchor in enumerate(source):
        if not anchor.details.startswith("Deferred receiver validation"):
            continue
        possession_team = anchor.team
        previous = anchor
        for event_index in range(anchor_index + 1, len(source)):
            event = source[event_index]
            if event.event_type == "turnover_candidate":
                if event.team == possession_team:
                    break
                continue
            if event.event_type != "pass_candidate":
                continue
            chain_continues = (
                event.from_player_track_id is not None
                and (
                    event.from_player_track_id
                    == previous.to_player_track_id
                    or (
                        previous.to_player_track_id is None
                        and event.from_player_track_id
                        == previous.from_player_track_id
                    )
                )
            )
            if not chain_continues:
                break
            if event.team != possession_team:
                opposing_team = event.team
                contact_seconds = _contested_contact_seconds(
                    players,
                    balls,
                    motion,
                    first_seconds=(
                        (previous.completion_seconds or previous.clip_seconds)
                        - 1.0
                    ),
                    last_seconds=event.clip_seconds,
                    first_team=possession_team,
                    second_team=opposing_team,
                    minimum_speed_pixels_per_second=(
                        minimum_speed_pixels_per_second
                    ),
                )
                if contact_seconds is not None:
                    source[event_index] = replace(
                        event,
                        team=possession_team,
                        details=(
                            "The incoming pass completed before the linked "
                            f"contested turnover. {event.details}"
                        ),
                    )
                    additions.append(
                        PredictedEvent(
                            event_type="turnover_candidate",
                            clip_seconds=round(contact_seconds, 3),
                            team=possession_team,
                            from_player_track_id=(
                                previous.to_player_track_id
                            ),
                            to_player_track_id=event.from_player_track_id,
                            confidence=0.6,
                            details=(
                                "A linked possession chain ended at a "
                                "contested direction-changing contact."
                            ),
                            completion_seconds=round(contact_seconds, 3),
                        )
                    )
                    break
                source[event_index] = replace(
                    event,
                    team=possession_team,
                    details=(
                        "Possession-chain validation prevented a silent team "
                        f"change. {event.details}"
                    ),
                )
                event = source[event_index]
            previous = event
    return _deduplicate_receptions([*source, *additions])

def suppress_overlapping_opponent_handoffs(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    maximum_box_distance_heights: float = 1.2,
) -> list[PredictedEvent]:
    accepted: list[PredictedEvent] = []
    for event in events:
        completion = event.completion_seconds
        if (
            event.event_type != "pass_candidate"
            or completion is None
            or event.from_player_track_id is None
            or event.to_player_track_id is None
            or not event.details.startswith(
                "Possession-chain validation prevented a silent team change"
            )
        ):
            accepted.append(event)
            continue
        release_ball = min(
            (
                ball
                for frame_balls in balls.values()
                for ball in frame_balls
            ),
            key=lambda ball: abs(float(ball["clip_seconds"]) - event.clip_seconds),
        )
        completion_ball = min(
            (
                ball
                for frame_balls in balls.values()
                for ball in frame_balls
            ),
            key=lambda ball: abs(float(ball["clip_seconds"]) - completion),
        )
        sender_team = next(
            (
                str(player["team"])
                for player in players.get(
                    int(release_ball["source_frame"]), []
                )
                if int(player["track_id"]) == event.from_player_track_id
            ),
            None,
        )
        receiver_team = next(
            (
                str(player["team"])
                for player in players.get(
                    int(completion_ball["source_frame"]), []
                )
                if int(player["track_id"]) == event.to_player_track_id
            ),
            None,
        )
        nearby_team_tracks = [
            (
                hypot(
                    max(
                        float(player["x1"]) - float(completion_ball["x"]),
                        0.0,
                        float(completion_ball["x"]) - float(player["x2"]),
                    ),
                    max(
                        float(player["y1"]) - float(completion_ball["y"]),
                        0.0,
                        float(completion_ball["y"]) - float(player["y2"]),
                    ),
                )
                / max(1.0, float(player["y2"]) - float(player["y1"])),
                int(player["track_id"]),
            )
            for player in players.get(int(completion_ball["source_frame"]), [])
            if str(player.get("team")) == event.team
        ]
        nearby_team_track = next(
            (
                track_id
                for distance, track_id in sorted(nearby_team_tracks)
                if distance <= maximum_box_distance_heights
            ),
            None,
        )
        if (
            sender_team != event.team
            and receiver_team != event.team
            and nearby_team_track is not None
            and nearby_team_track != event.to_player_track_id
        ):
            continue
        accepted.append(event)
    return accepted

def reconcile_delayed_turnover_chains(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    maximum_lookback_seconds: float = 6.0,
    minimum_supported_intermediary_events: int = 1,
) -> list[PredictedEvent]:
    source = sorted(events, key=lambda event: event.clip_seconds)
    motion = _ball_motion_evidence(balls)
    teams = {
        str(player.get("team"))
        for frame_players in players.values()
        for player in frame_players
    }
    team_pair = (
        ("red", "black")
        if teams & {"red", "black"}
        else ("blue", "white")
    )

    def other_team(team: str | None) -> str | None:
        if team == team_pair[0]:
            return team_pair[1]
        if team == team_pair[1]:
            return team_pair[0]
        return None

    def local_track_team(track_id: int | None, timestamp: float | None) -> str | None:
        if track_id is None or timestamp is None:
            return None
        labels: list[str] = []
        profile = "red-black" if team_pair == ("red", "black") else "blue-white"
        for frame_players in players.values():
            for player in frame_players:
                if (
                    int(player["track_id"]) != track_id
                    or abs(float(player["clip_seconds"]) - timestamp) > 0.3
                ):
                    continue
                scores = player.get("color_scores")
                if not isinstance(scores, dict):
                    continue
                label = classify_color_scores(scores, team_profile=profile)
                if label in team_pair:
                    labels.append(label)
        if not labels:
            return None
        label, count = Counter(labels).most_common(1)[0]
        return label if count / len(labels) >= 0.6 else None

    for turnover_index, turnover in enumerate(source):
        if (
            turnover.event_type != "turnover_candidate"
            or turnover.team not in team_pair
            or turnover.to_player_track_id is None
            or turnover.completion_seconds is None
        ):
            continue
        winner = other_team(turnover.team)
        if winner is None:
            continue
        completion = turnover.completion_seconds
        intermediary_indices = [
            index
            for index, event in enumerate(source)
            if event.event_type == "pass_candidate"
            and event.team == turnover.team
            and event.completion_seconds is not None
            and completion - maximum_lookback_seconds
            <= event.clip_seconds
            < completion
        ]
        if not intermediary_indices:
            continue
        supported = 0
        for index in intermediary_indices:
            intermediary = source[index]
            endpoint_teams = {
                team
                for team in (
                    local_track_team(
                        intermediary.from_player_track_id,
                        intermediary.clip_seconds,
                    ),
                    local_track_team(
                        intermediary.to_player_track_id,
                        intermediary.completion_seconds,
                    ),
                )
                if team is not None
            }
            if winner in endpoint_teams and turnover.team not in endpoint_teams:
                supported += 1
        if supported < minimum_supported_intermediary_events:
            continue
        first_release = min(source[index].clip_seconds for index in intermediary_indices)
        contact_candidates: list[tuple[float, float]] = []
        for (ball_track_id, source_frame), (speed, direction_cosine) in motion.items():
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
                timestamp < completion - maximum_lookback_seconds
                or timestamp > first_release
                or speed < minimum_speed_pixels_per_second
                or direction_cosine > 0.5
                or winner
                not in _nearby_ball_teams(
                    players.get(source_frame, []),
                    ball,
                    maximum_box_distance_heights=0.25,
                )
            ):
                continue
            contact_candidates.append((timestamp, direction_cosine))
        if not contact_candidates:
            continue
        contact = min(contact_candidates)[0]
        source[turnover_index] = replace(
            turnover,
            clip_seconds=round(contact, 3),
            completion_seconds=round(contact, 3),
            details=(
                "Earlier direction-changing control resolved a delayed "
                f"possession-team transition. {turnover.details}"
            ),
        )
        for index in intermediary_indices:
            source[index] = replace(
                source[index],
                team=winner,
                details=(
                    "Possession-chain validation corrected a delayed team "
                    f"transition. {source[index].details}"
                ),
            )
    return _deduplicate_receptions(source)

def reconcile_unconfirmed_turnovers(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    *,
    maximum_receiver_control_ratio: float = 1.0,
    minimum_unconfirmed_seconds: float = 0.8,
) -> list[PredictedEvent]:
    """Keep possession with the releasing team until opponent control is clear."""
    segments = list(possession_segments)
    reconciled: list[PredictedEvent] = []
    for event in events:
        if (
            event.event_type != "turnover_candidate"
            or event.to_player_track_id is None
            or event.completion_seconds is None
        ):
            reconciled.append(event)
            continue
        receiver = next(
            (
                segment
                for segment in segments
                if (
                    segment.player_track_id == event.to_player_track_id
                    and segment.start_seconds
                    <= event.completion_seconds
                    <= segment.end_seconds
                )
            ),
            None,
        )
        if (
            receiver is None
            or receiver.end_seconds - receiver.start_seconds
            < minimum_unconfirmed_seconds - 1e-9
            or any(
                observation.control_ratio <= maximum_receiver_control_ratio
                for observation in receiver.observations
            )
        ):
            reconciled.append(event)
            continue
        reconciled.append(
            replace(
                event,
                event_type="pass_candidate",
                to_player_track_id=None,
                details=(
                    "Opponent proximity never became controlled possession; "
                    f"the releasing {event.team} team retained the ball. "
                    f"{event.details}"
                ),
            )
        )
    return _deduplicate_receptions(
        [
            event
            for event in reconciled
            if not (
                event.event_type == "pass_candidate"
                and event.to_player_track_id is not None
                and any(
                    retained.details.startswith(
                        "Opponent proximity never became controlled"
                    )
                    and retained.from_player_track_id
                    == event.to_player_track_id
                    and abs(retained.clip_seconds - (event.completion_seconds or -1))
                    <= 0.04
                    for retained in reconciled
                )
            )
        ]
    )

def reconcile_deflected_turnover_sequences(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    *,
    maximum_sequence_seconds: float = 1.8,
    maximum_control_ratio: float = 0.35,
) -> list[PredictedEvent]:
    """Move a premature contested turnover to the opponent's first clear control."""
    source = list(events)
    segments = list(possession_segments)
    removed: set[int] = set()
    replacements: dict[int, PredictedEvent] = {}

    for turnover_index, turnover in enumerate(source):
        turnover_time = turnover.completion_seconds
        if (
            turnover.event_type != "turnover_candidate"
            or turnover_time is None
        ):
            continue
        retained = next(
            (
                event
                for event in source
                if event.event_type == "pass_candidate"
                and event.team == turnover.team
                and event.completion_seconds is not None
                and turnover_time < event.completion_seconds
                <= turnover_time + maximum_sequence_seconds
            ),
            None,
        )
        if retained is None:
            continue
        retained_time = retained.completion_seconds
        gained_index = next(
            (
                index
                for index, event in enumerate(source)
                if event.event_type == "pass_candidate"
                and event.team != turnover.team
                and event.to_player_track_id is not None
                and event.completion_seconds is not None
                and retained_time <= event.completion_seconds
                <= turnover_time + maximum_sequence_seconds
                and event.from_player_track_id == retained.from_player_track_id
            ),
            None,
        )
        if gained_index is None:
            continue
        gained = source[gained_index]
        gained_time = gained.completion_seconds
        controlled = any(
            segment.team == gained.team
            and segment.player_track_id == gained.to_player_track_id
            and segment.start_seconds <= gained_time <= segment.end_seconds
            and any(
                observation.control_ratio <= maximum_control_ratio
                for observation in segment.observations
                if abs(observation.clip_seconds - gained_time) <= 0.2
            )
            for segment in segments
        )
        if not controlled:
            continue
        removed.add(turnover_index)
        replacements[gained_index] = replace(
            gained,
            event_type="turnover_candidate",
            clip_seconds=round(gained_time, 3),
            team=turnover.team,
            details=(
                "An initial opponent deflection did not end possession; "
                "the turnover occurred at the opponent's first controlled touch."
            ),
        )

    return [
        replacements.get(index, event)
        for index, event in enumerate(source)
        if index not in removed
    ]

def suppress_uncontrolled_opponent_turnovers(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    possession_segments: Iterable[PossessionSegment] = (),
    *,
    maximum_box_distance_heights: float = 0.25,
    maximum_continuity_seconds: float = 2.0,
) -> list[PredictedEvent]:
    """Reject turnovers where only the current team remains in direct contact."""
    segments = list(possession_segments)
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
        if event.details.startswith(
            "Frame-level jersey evidence corrected"
        ):
            accepted.append(event)
            continue
        retained_control = next(
            (
                segment
                for segment in segments
                if (
                    segment.team == event.team
                    and segment.start_seconds <= completion
                    and segment.end_seconds > completion + 0.04
                )
            ),
            None,
        )
        if retained_control is not None:
            retained_team = event.team
            retained_at = completion
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


def suppress_unestablished_brief_opponent_turnovers(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    *,
    maximum_losing_control_seconds: float = 1.0,
) -> list[PredictedEvent]:
    """Reject a turnover by a team that never gained possession.

    A defender shadowing a dribbler can briefly look closest to the ball. When
    no earlier event gave that defender's team the ball and the apparent
    control is brief, the ball simply stays with the team that already had it.
    """
    segments = list(possession_segments)
    accepted: list[PredictedEvent] = []
    for event in sorted(events, key=lambda item: item.clip_seconds):
        previous = next(
            (
                prior
                for prior in reversed(accepted)
                if prior.event_type in {"pass_candidate", "turnover_candidate"}
                and prior.team is not None
            ),
            None,
        )
        if (
            event.event_type != "turnover_candidate"
            or event.team is None
            or event.from_player_track_id is None
            or previous is None
        ):
            accepted.append(event)
            continue
        losing_team_gained = (
            previous.team == event.team
            if previous.event_type == "pass_candidate"
            else previous.team != event.team
        )
        losing_segment = next(
            (
                segment
                for segment in segments
                if segment.team == event.team
                and segment.player_track_id == event.from_player_track_id
                and segment.start_seconds - 0.04
                <= event.clip_seconds
                <= segment.end_seconds + 0.04
            ),
            None,
        )
        if (
            losing_team_gained
            or losing_segment is None
            or losing_segment.end_seconds - losing_segment.start_seconds
            > maximum_losing_control_seconds
        ):
            accepted.append(event)
            continue
    return accepted


def reconcile_self_track_turnovers(
    events: Iterable[PredictedEvent],
    possession_segments: Iterable[PossessionSegment],
    control_observations: Iterable[PossessionObservation],
    *,
    maximum_flicker_seconds: float = 1.0,
) -> list[PredictedEvent]:
    """Treat a turnover from a player track to itself as a colour flicker.

    One physical player cannot lose the ball to himself. The turnover is
    dropped and the event that delivered the ball to that player is credited
    to the team the track settles on afterwards.
    """
    segments = list(possession_segments)
    source = sorted(events, key=lambda item: item.clip_seconds)
    result: list[PredictedEvent] = []
    for event in source:
        completion = event.completion_seconds
        if (
            event.event_type != "turnover_candidate"
            or event.from_player_track_id is None
            or event.from_player_track_id != event.to_player_track_id
            or completion is None
        ):
            result.append(event)
            continue
        flicker_times = [
            observation.clip_seconds
            for observation in control_observations
            if observation.player_track_id == event.from_player_track_id
            and observation.team == event.team
        ]
        if (
            not flicker_times
            or max(flicker_times) - min(flicker_times)
            > maximum_flicker_seconds
        ):
            result.append(event)
            continue
        settled = next(
            (
                segment.team
                for segment in segments
                if segment.player_track_id == event.to_player_track_id
                and segment.team != event.team
                and segment.end_seconds >= completion - 0.04
                and segment.start_seconds <= completion + 0.04
            ),
            None,
        )
        if settled is None:
            result.append(event)
            continue
        delivery_index = next(
            (
                index
                for index in range(len(result) - 1, -1, -1)
                if result[index].to_player_track_id == event.to_player_track_id
                and result[index].team == event.team
                and result[index].event_type == "pass_candidate"
            ),
            None,
        )
        if delivery_index is not None:
            delivery = result[delivery_index]
            result[delivery_index] = replace(
                delivery,
                team=settled,
                details=(
                    "The receiver's brief opposite-colour reading was a "
                    f"label flicker on one player track. {delivery.details}"
                ),
            )
    return result
