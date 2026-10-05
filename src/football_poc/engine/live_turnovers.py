from __future__ import annotations

from football_poc.engine.common import *

def _live_reconcile_track_identity_team_switches(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    *,
    maximum_chain_seconds: float,
    evidence_window_seconds: float = 0.8,
    minimum_evidence_points: int = 3,
) -> list[PredictedEvent]:
    if maximum_chain_seconds < 0:
        raise ValueError("Maximum chain duration cannot be negative")
    if evidence_window_seconds <= 0:
        raise ValueError("Evidence window must be positive")
    if minimum_evidence_points <= 0:
        raise ValueError("Minimum evidence points must be positive")

    teams = {
        str(player.get("team"))
        for frame_players in players.values()
        for player in frame_players
    }
    if teams & {"red", "black"}:
        team_pair = ("red", "black")
        team_profile = "red-black"
    elif teams & {"blue", "white"}:
        team_pair = ("blue", "white")
        team_profile = "blue-white"
    else:
        return list(events)

    points_by_track: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame_players in players.values():
        for player in frame_players:
            points_by_track[int(player["track_id"])].append(player)

    def local_team(track_id: int | None, timestamp: float | None) -> str | None:
        if track_id is None or timestamp is None:
            return None
        labels: list[str] = []
        for point in points_by_track.get(track_id, []):
            if (
                abs(float(point["clip_seconds"]) - timestamp)
                > evidence_window_seconds
            ):
                continue
            scores = point.get("color_scores")
            if not isinstance(scores, dict):
                continue
            label = classify_color_scores(scores, team_profile=team_profile)
            if label in team_pair:
                labels.append(label)
        if len(labels) < minimum_evidence_points:
            return None
        label, count = Counter(labels).most_common(1)[0]
        return label if count / len(labels) >= 0.6 else None

    def other_team(team: str | None) -> str | None:
        if team == team_pair[0]:
            return team_pair[1]
        if team == team_pair[1]:
            return team_pair[0]
        return None

    corrected: list[PredictedEvent] = []
    for event in sorted(events, key=lambda item: item.clip_seconds):
        sender_team = event.team
        chain_anchor = next(
            (
                prior
                for prior in reversed(corrected)
                if (
                    prior.details.startswith(
                        "Frame-level jersey evidence corrected"
                    )
                    or prior.details.startswith(
                        "Track-switch possession continuity preserved"
                    )
                )
                and event.from_player_track_id is not None
                and prior.to_player_track_id == event.from_player_track_id
                and prior.completion_seconds is not None
                and 0
                <= event.clip_seconds - prior.completion_seconds
                <= maximum_chain_seconds
            ),
            None,
        )
        if chain_anchor is not None:
            sender_team = (
                chain_anchor.team
                if chain_anchor.event_type
                in {"pass_candidate", "restart_pass_candidate"}
                else other_team(chain_anchor.team)
            )

        receiver_team = local_team(
            event.to_player_track_id,
            event.completion_seconds,
        )
        if receiver_team is None or sender_team not in team_pair:
            corrected.append(event)
            continue
        implied_receiver_team = (
            sender_team
            if event.event_type in {"pass_candidate", "restart_pass_candidate"}
            else other_team(sender_team)
        )
        if chain_anchor is None and (
            event.event_type != "turnover_candidate"
            or receiver_team != sender_team
        ):
            corrected.append(event)
            continue

        event_type = (
            "pass_candidate"
            if receiver_team == sender_team
            else "turnover_candidate"
        )
        corrected.append(
            replace(
                event,
                event_type=event_type,
                team=sender_team,
                details=(
                    "Track-switch possession continuity preserved using "
                    "frame-level jersey evidence."
                    if chain_anchor is not None
                    else (
                        "Frame-level jersey evidence corrected a cross-team "
                        "player-track identity switch."
                    )
                ),
            )
        )
    return _deduplicate_receptions(corrected)

def _live_infer_deferred_contested_turnovers(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    receiver_window_seconds: float = 0.4,
    contact_lookback_seconds: float = 6.0,
) -> list[PredictedEvent]:
    source = list(events)
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
                    if (
                        completion - 1.0
                        <= float(ball["clip_seconds"])
                        <= completion
                    )
                    and (
                        receiver_track_id
                        := _live__controlled_contact_with_local_identity(
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
                receiver_track_id = _live__controlled_contact_with_local_identity(
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
                            "Deferred possession validation recovered a "
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

def _live_infer_terminal_direct_reception(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    minimum_flight_seconds: float = 0.4,
    maximum_flight_seconds: float = 3.0,
) -> list[PredictedEvent]:
    source = list(events)
    observed_balls = sorted(
        (
            ball
            for frame_balls in balls.values()
            for ball in frame_balls
            if not ball.get("interpolated", False)
        ),
        key=lambda ball: float(ball["clip_seconds"]),
    )
    if not source or len(observed_balls) < 3:
        return source
    terminal_ball = observed_balls[-1]
    terminal_contact = _live__projected_terminal_contact(
        players,
        terminal_ball,
    )
    if terminal_contact is None:
        return source
    receiver_team, receiver_track_id = terminal_contact
    prior_event = max(
        source,
        key=lambda event: event.completion_seconds or event.clip_seconds,
    )
    prior_completion = (
        prior_event.completion_seconds or prior_event.clip_seconds
    )
    terminal_seconds = float(terminal_ball["clip_seconds"])
    if (
        prior_event.team != receiver_team
        or terminal_seconds - prior_completion < minimum_flight_seconds
        or any(
            abs(
                (event.completion_seconds or event.clip_seconds)
                - terminal_seconds
            )
            <= 0.4
            for event in source
        )
    ):
        return source

    motion = _ball_motion_evidence(balls)
    release = next(
        (
            ball
            for ball in observed_balls
            if prior_completion < float(ball["clip_seconds"])
            and minimum_flight_seconds
            <= terminal_seconds - float(ball["clip_seconds"])
            <= maximum_flight_seconds
            and (
                evidence := motion.get(
                    (int(ball["track_id"]), int(ball["source_frame"]))
                )
            )
            is not None
            and evidence[0] >= minimum_speed_pixels_per_second
            and evidence[1] <= 0.25
        ),
        None,
    )
    if release is None:
        return source
    sender_track_id = _live__nearby_ball_team_track(
        players.get(int(release["source_frame"]), []),
        release,
        receiver_team,
        maximum_box_distance_heights=0.4,
    )
    if sender_track_id is None or sender_track_id == receiver_track_id:
        return source
    source.append(
        PredictedEvent(
            event_type="pass_candidate",
            clip_seconds=round(float(release["clip_seconds"]), 3),
            team=receiver_team,
            from_player_track_id=sender_track_id,
            to_player_track_id=receiver_track_id,
            confidence=0.55,
            details=(
                "A direction-changing release was followed by the final "
                "directly observed ball sample reaching a projected "
                "same-team runner before an overlapping opponent."
            ),
            completion_seconds=round(terminal_seconds, 3),
        )
    )
    return _deduplicate_receptions(source)

def _live_reconcile_delayed_turnover_chains(
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
        supported = sum(
            local_track_team(source[index].from_player_track_id, source[index].clip_seconds)
            == winner
            or local_track_team(
                source[index].to_player_track_id,
                source[index].completion_seconds,
            )
            == winner
            for index in intermediary_indices
        )
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
