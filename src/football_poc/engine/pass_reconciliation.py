from __future__ import annotations

from football_poc.engine.common import *

def reconcile_one_touch_team_transfers(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    maximum_prior_reception_seconds: float,
    maximum_direction_cosine: float = 0.25,
    observation_tolerance_seconds: float = 0.04,
    receiver_tolerance_seconds: float = 0.25,
) -> list[PredictedEvent]:
    source = list(events)
    controls = list(observations)
    motion = _ball_motion_evidence(balls)
    reconciled: list[PredictedEvent] = []
    for outgoing in source:
        if outgoing.event_type != "pass_candidate":
            reconciled.append(outgoing)
            continue
        candidates: list[PossessionObservation] = []
        for observation in controls:
            if (
                observation.team == outgoing.team
                or abs(observation.clip_seconds - outgoing.clip_seconds)
                > observation_tolerance_seconds
            ):
                continue
            evidence = next(
                (
                    value
                    for (_, frame), value in motion.items()
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
            reconciled.append(outgoing)
            continue
        contact = min(candidates, key=lambda item: item.control_ratio)
        anchors = [
            event
            for event in source
            if event.team == contact.team
            and event.completion_seconds is not None
            and 0
            < outgoing.clip_seconds - event.completion_seconds
            <= maximum_prior_reception_seconds
        ]
        if not anchors:
            reconciled.append(outgoing)
            continue
        anchor = max(anchors, key=lambda event: event.completion_seconds or 0)
        reconciled.append(
            PredictedEvent(
                event_type="pass_candidate",
                clip_seconds=round(outgoing.clip_seconds, 3),
                team=contact.team,
                from_player_track_id=None,
                to_player_track_id=contact.player_track_id,
                confidence=0.6,
                details=(
                    "A sharp one-touch contact completed the incoming "
                    "same-team pass and immediately released the next pass."
                ),
                completion_seconds=round(outgoing.clip_seconds, 3),
            )
        )
        reconciled.append(
            replace(
                outgoing,
                team=contact.team,
                from_player_track_id=contact.player_track_id,
                details=(
                    "A sharp one-touch contact established the outgoing "
                    f"{contact.team} pass."
                ),
            )
        )
    chained: list[PredictedEvent] = []
    for event in sorted(reconciled, key=lambda item: item.clip_seconds):
        anchors = [
            prior
            for prior in chained
            if event.from_player_track_id is not None
            and (
                prior.details.startswith(
                    "A sharp one-touch contact established"
                )
                or prior.details.startswith(
                    "Possession-chain continuity preserved"
                )
            )
            and prior.to_player_track_id == event.from_player_track_id
            and prior.completion_seconds is not None
            and 0
            <= event.clip_seconds - prior.completion_seconds
            <= maximum_prior_reception_seconds
        ]
        if not anchors or event.team == anchors[-1].team:
            chained.append(event)
            continue
        anchor = max(anchors, key=lambda item: item.completion_seconds or 0)
        receiver_teams = [
            observation.team
            for observation in controls
            if event.to_player_track_id is not None
            and observation.player_track_id == event.to_player_track_id
            and event.completion_seconds is not None
            and abs(
                observation.clip_seconds - event.completion_seconds
            )
            <= receiver_tolerance_seconds
        ]
        if not receiver_teams:
            chained.append(event)
            continue
        receiver_team = Counter(receiver_teams).most_common(1)[0][0]
        chained.append(
            replace(
                event,
                event_type=(
                    "pass_candidate"
                    if receiver_team == anchor.team
                    else "turnover_candidate"
                ),
                team=anchor.team,
                details=(
                    "Possession-chain continuity preserved the corrected "
                    "sender team through the next release."
                ),
            )
        )
    return _deduplicate_receptions(chained)

def reconcile_intervening_opponent_aerial_contacts(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    maximum_direction_cosine: float = -0.75,
    maximum_control_ratio: float = 1.0,
    maximum_immediate_control_ratio: float = 0.5,
    minimum_weak_contact_duration_seconds: float = 0.4,
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
                or (
                    contact.control_ratio > maximum_immediate_control_ratio
                    and completion - contact.clip_seconds
                    < minimum_weak_contact_duration_seconds
                )
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

def reconcile_track_identity_team_switches(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    *,
    maximum_chain_seconds: float,
    control_observations: Iterable[PossessionObservation] | None = None,
    sender_control_window_seconds: float = 0.4,
    evidence_window_seconds: float = 0.8,
    minimum_evidence_points: int = 3,
) -> list[PredictedEvent]:
    if maximum_chain_seconds < 0:
        raise ValueError("Maximum chain duration cannot be negative")
    if evidence_window_seconds <= 0:
        raise ValueError("Evidence window must be positive")
    if minimum_evidence_points <= 0:
        raise ValueError("Minimum evidence points must be positive")
    if sender_control_window_seconds < 0:
        raise ValueError("Sender control window cannot be negative")

    controls = (
        None
        if control_observations is None
        else list(control_observations)
    )
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
        if count / len(labels) < 0.6:
            return None
        # The same box clearly showing the other kit shortly before means the
        # jersey read is mixed (e.g. a white back number on a black shirt).
        opposite = team_pair[1] if label == team_pair[0] else team_pair[0]
        recent_opposite = 0
        for point in points_by_track.get(track_id, []):
            offset = timestamp - float(point["clip_seconds"])
            if not 0 <= offset <= 2 * evidence_window_seconds:
                continue
            scores = point.get("color_scores")
            if isinstance(scores, dict) and classify_color_scores(
                scores, team_profile=team_profile
            ) == opposite:
                recent_opposite += 1
        if recent_opposite >= minimum_evidence_points:
            return None
        return label

    def stable_precontact_team(
        track_id: int | None,
        timestamp: float | None,
        released_at: float | None = None,
    ) -> str | None:
        if track_id is None or timestamp is None:
            return None
        track_points = points_by_track.get(track_id, [])
        if not track_points:
            return None
        # A track born mid-flight, inside the window, has no established prior
        # identity; its first boxes often still include the player it
        # emerged from.
        born = min(float(point["clip_seconds"]) for point in track_points)
        if (
            released_at is not None
            and born > released_at + 1e-9
            and born >= timestamp - evidence_window_seconds - 1e-9
        ):
            return None
        labels = [
            str(point.get("team"))
            for point in track_points
            if (
                timestamp - evidence_window_seconds
                <= float(point["clip_seconds"])
                < timestamp
                and point.get("team") in team_pair
            )
        ]
        if len(labels) < minimum_evidence_points:
            return None
        label, count = Counter(labels).most_common(1)[0]
        return label if count / len(labels) >= 0.8 else None

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
            if controls is not None and not any(
                observation.player_track_id == event.from_player_track_id
                and observation.control_ratio <= 1.0
                and 0
                <= event.clip_seconds - observation.clip_seconds
                <= sender_control_window_seconds
                for observation in controls
            ):
                continue
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
        tracked_receiver_team = stable_precontact_team(
            event.to_player_track_id,
            event.completion_seconds,
            event.clip_seconds,
        )
        if (
            event.event_type in {
                "pass_candidate",
                "restart_pass_candidate",
            }
            and receiver_team == sender_team
            and tracked_receiver_team is not None
            and receiver_team != tracked_receiver_team
        ):
            continue
        if (
            event.event_type == "turnover_candidate"
            and receiver_team == sender_team
            and tracked_receiver_team is not None
            and receiver_team != tracked_receiver_team
        ):
            receiver_team = tracked_receiver_team
        if receiver_team is None or sender_team not in team_pair:
            corrected.append(event)
            continue
        implied_receiver_team = (
            sender_team
            if event.event_type in {"pass_candidate", "restart_pass_candidate"}
            else other_team(sender_team)
        )
        if chain_anchor is None and receiver_team == implied_receiver_team:
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
    consistent: list[PredictedEvent] = []
    established_owner: str | None = None
    established_at: float | None = None
    for event in _deduplicate_receptions(corrected):
        within_chain = (
            established_owner is not None
            and established_at is not None
            and event.clip_seconds - established_at
            <= maximum_chain_seconds + 1e-9
        )
        if (
            within_chain
            and event.event_type == "turnover_candidate"
            and event.team != established_owner
        ):
            continue
        consistent.append(event)
        if event.event_type == "turnover_candidate":
            if (
                event.details.startswith(
                    "Frame-level jersey evidence corrected"
                )
                or (within_chain and event.team == established_owner)
            ):
                established_owner = other_team(event.team)
                established_at = event.completion_seconds
            else:
                established_owner = None
                established_at = None
        elif not within_chain:
            established_owner = None
            established_at = None
    return consistent

def suppress_passes_crossing_opponent_control(
    events: Iterable[PredictedEvent],
    observations: Iterable[PossessionObservation],
    *,
    maximum_control_ratio: float = 0.5,
    maximum_support_ratio: float = 1.0,
    maximum_support_step_seconds: float = 0.4,
) -> list[PredictedEvent]:
    controls = list(observations)
    retained: list[PredictedEvent] = []
    for event in events:
        if (
            event.event_type != "pass_candidate"
            or event.completion_seconds is None
        ):
            retained.append(event)
            continue

        def receiver_reception(observation: PossessionObservation) -> bool:
            # A colour misread on the receiver's own track that runs straight
            # into the completion is the reception itself, not an opponent.
            if observation.player_track_id != event.to_player_track_id:
                return False
            chain = sorted(
                (
                    item
                    for item in controls
                    if observation.clip_seconds
                    <= item.clip_seconds
                    <= event.completion_seconds + 1e-9
                ),
                key=lambda item: item.clip_seconds,
            )
            times = [observation.clip_seconds, *(i.clip_seconds for i in chain)]
            return (
                all(
                    item.player_track_id == event.to_player_track_id
                    for item in chain
                )
                and event.completion_seconds - chain[-1].clip_seconds <= 1e-9
                and all(
                    later - earlier <= maximum_support_step_seconds
                    for earlier, later in zip(times, times[1:])
                )
            )

        intervening = [
            observation
            for observation in controls
            if observation.team != event.team
            and event.clip_seconds < observation.clip_seconds
            < event.completion_seconds
            and not receiver_reception(observation)
        ]
        opponent_control = any(
            observation.control_ratio <= maximum_control_ratio
            and any(
                support is not observation
                and support.team == observation.team
                and support.player_track_id == observation.player_track_id
                and support.control_ratio <= maximum_support_ratio
                and abs(support.clip_seconds - observation.clip_seconds)
                <= maximum_support_step_seconds
                for support in intervening
            )
            for observation in intervening
        )
        if not opponent_control:
            retained.append(event)
    return retained

def backdate_unseen_carrier_dispossessions(
    events: Iterable[PredictedEvent],
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
    minimum_turnover_seconds: float = 0.6,
    sample_seconds: float = 0.18,
    maximum_dip_fraction: float = 0.35,
    maximum_unseen_contact_ratio: float = 0.5,
    maximum_sender_displacement_heights: float = 0.5,
) -> list[PredictedEvent]:
    """Move a late turnover back to an unseen player's dispossession.

    When the ball leaves a stationary owner, almost stops and is then
    played away again faster than before with no detected player within
    control distance, an undetected opponent took the ball at the release.
    The later first detected control is only where tracking recovered.
    """
    ordered = sorted(
        (
            point
            for frame_points in balls.values()
            for point in frame_points
            if int(point.get("track_id", 1)) == 1
            and not point.get("interpolated", False)
        ),
        key=lambda point: float(point["clip_seconds"]),
    )
    points_by_track: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame_players in players.values():
        for player in frame_players:
            points_by_track[int(player["track_id"])].append(player)
    refined: list[PredictedEvent] = []
    for event in events:
        completion = event.completion_seconds
        release = event.clip_seconds
        if (
            event.event_type != "turnover_candidate"
            or completion is None
            or event.from_player_track_id is None
            or completion - release < minimum_turnover_seconds
        ):
            refined.append(event)
            continue
        samples: list[dict[str, Any]] = []
        for point in ordered:
            timestamp = float(point["clip_seconds"])
            if timestamp < release - 1e-6 or timestamp > completion + 1e-6:
                continue
            if (
                not samples
                or timestamp - float(samples[-1]["clip_seconds"])
                >= sample_seconds
            ):
                samples.append(point)
        speeds = [
            (
                hypot(
                    float(current["x"]) - float(previous["x"]),
                    float(current["y"]) - float(previous["y"]),
                )
                / (
                    float(current["clip_seconds"])
                    - float(previous["clip_seconds"])
                ),
                previous,
            )
            for previous, current in zip(samples, samples[1:])
        ]
        retouch = None
        peak = 0.0
        dip_index = None
        for index, (speed, _) in enumerate(speeds):
            if dip_index is None:
                if peak > 0 and speed <= maximum_dip_fraction * peak:
                    dip_index = index
                else:
                    peak = max(peak, speed)
            elif speed >= max(peak, minimum_speed_pixels_per_second):
                retouch = speeds[index][1]
                break
        if retouch is None or dip_index is None:
            refined.append(event)
            continue
        retouch_frame = int(retouch["source_frame"])
        if any(
            hypot(
                (float(player["x1"]) + float(player["x2"])) / 2
                - float(retouch["x"]),
                float(player["y2"]) - float(retouch["y"]),
            )
            / max(1.0, float(player["y2"]) - float(player["y1"]))
            <= maximum_unseen_contact_ratio
            for player in players.get(retouch_frame, [])
        ):
            refined.append(event)
            continue
        sender = [
            point
            for point in points_by_track[int(event.from_player_track_id)]
            if release - 1e-6
            <= float(point["clip_seconds"])
            <= completion + 1e-6
        ]
        if len(sender) < 2:
            refined.append(event)
            continue
        heights = sorted(
            float(point["y2"]) - float(point["y1"]) for point in sender
        )
        height = max(1.0, heights[len(heights) // 2])
        start_x = (float(sender[0]["x1"]) + float(sender[0]["x2"])) / 2
        start_y = float(sender[0]["y2"])
        if any(
            hypot(
                (float(point["x1"]) + float(point["x2"])) / 2 - start_x,
                float(point["y2"]) - start_y,
            )
            >= maximum_sender_displacement_heights * height
            for point in sender
        ):
            refined.append(event)
            continue
        refined.append(
            replace(
                event,
                completion_seconds=round(release, 3),
                details=(
                    "The ball left a stationary owner, nearly stopped and was "
                    "played on faster with no detected player in control "
                    "distance, so an undetected opponent won it at the "
                    f"release. {event.details}"
                ),
            )
        )
    return refined
