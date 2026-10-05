from __future__ import annotations

from football_poc.engine.common import *

def filter_aerial_boundary_intervals(
    intervals: Iterable[dict[str, Any]],
    possession_segments: Iterable[PossessionSegment],
    *,
    maximum_prior_gap_seconds: float = 1.0,
    maximum_resume_gap_seconds: float = 1.2,
    maximum_crossing_span_seconds: float = 4.0,
) -> list[dict[str, Any]]:
    segments = list(possession_segments)
    accepted: list[dict[str, Any]] = []
    for interval in intervals:
        resumed = interval.get("resumed_seconds")
        if resumed is None:
            accepted.append(interval)
            continue
        start = float(interval["start_seconds"])
        resumed_seconds = float(resumed)
        prior = [
            segment
            for segment in segments
            if segment.end_seconds <= start
            and start - segment.end_seconds <= maximum_prior_gap_seconds
        ]
        following = [
            segment
            for segment in segments
            if segment.start_seconds >= resumed_seconds
            and segment.start_seconds - resumed_seconds
            <= maximum_resume_gap_seconds
        ]
        if (
            prior
            and following
            and following[0].start_seconds - start
            <= maximum_crossing_span_seconds
        ):
            prior_owner = max(prior, key=lambda segment: segment.end_seconds)
            next_owner = min(following, key=lambda segment: segment.start_seconds)
            if prior_owner.team == next_owner.team:
                continue
        accepted.append(interval)
    return accepted

def annotate_restart_releases(
    intervals: Iterable[dict[str, Any]],
    balls: dict[int, list[dict[str, Any]]],
    *,
    minimum_speed_pixels_per_second: float,
) -> list[dict[str, Any]]:
    if minimum_speed_pixels_per_second <= 0:
        raise ValueError("Minimum restart speed must be positive")
    points = sorted(
        (
            point
            for frame_points in balls.values()
            for point in frame_points
            if not point.get("interpolated", False)
        ),
        key=lambda point: float(point["clip_seconds"]),
    )
    source = [dict(interval) for interval in intervals]
    for index, interval in enumerate(source):
        geometric_resume = interval.get("resumed_seconds")
        if geometric_resume is None:
            interval["play_resumed_seconds"] = None
            continue
        search_end = (
            float(source[index + 1]["start_seconds"])
            if index + 1 < len(source)
            else float("inf")
        )
        release = None
        for first, second in zip(points, points[1:]):
            first_seconds = float(first["clip_seconds"])
            second_seconds = float(second["clip_seconds"])
            if first_seconds < float(geometric_resume):
                continue
            if second_seconds > search_end:
                break
            elapsed = second_seconds - first_seconds
            if elapsed <= 0:
                continue
            speed = hypot(
                float(second["x"]) - float(first["x"]),
                float(second["y"]) - float(first["y"]),
            ) / elapsed
            if speed >= minimum_speed_pixels_per_second:
                release = round(first_seconds, 3)
                break
        interval["play_resumed_seconds"] = release
    return source

def extend_restarts_through_ball_setup(
    intervals: Iterable[dict[str, Any]],
    possession_segments: Iterable[PossessionSegment],
    ball_points: Iterable[dict[str, Any]],
    *,
    maximum_receiver_delay_seconds: float = 2.0,
    minimum_setup_control_seconds: float = 1.0,
    settled_speed_pixels_per_second: float = 100.0,
    minimum_settled_seconds: float = 0.4,
    minimum_restart_speed_pixels_per_second: float = 200.0,
    maximum_restart_search_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    """Keep play stopped when an apparent restart only relocates the ball.

    Applies to in-field stationary-ball restarts and to ball-out-of-pitch
    spells (intervals with a geometric re-entry): a ball carried or handed
    to a player who then sets it up has not been restarted (Law 8/9), so
    touches before the confirmed restart cannot be passes.
    """
    segments = list(possession_segments)
    balls_by_seconds: dict[float, dict[str, Any]] = {}
    for point in ball_points:
        if point.get("interpolated", False):
            continue
        seconds = float(point["clip_seconds"])
        previous = balls_by_seconds.get(seconds)
        if previous is None or float(point.get("confidence", 0)) > float(
            previous.get("confidence", 0)
        ):
            balls_by_seconds[seconds] = point
    balls = [balls_by_seconds[key] for key in sorted(balls_by_seconds)]
    ball_steps: list[tuple[float, float, float]] = []
    for first, second in zip(balls, balls[1:]):
        start = float(first["clip_seconds"])
        end = float(second["clip_seconds"])
        elapsed = end - start
        if elapsed <= 0 or elapsed > 0.3:
            continue
        speed = hypot(
            float(second["x"]) - float(first["x"]),
            float(second["y"]) - float(first["y"]),
        ) / elapsed
        ball_steps.append((start, end, speed))

    extended: list[dict[str, Any]] = []
    for source_interval in intervals:
        interval = dict(source_interval)
        release_value = interval.get("play_resumed_seconds")
        relocatable = (
            interval.get("stoppage_kind") == "stationary_ball_restart"
            or interval.get("resumed_seconds") is not None
        )
        if not relocatable or release_value is None:
            extended.append(interval)
            continue
        release = float(release_value)
        setup_controls = [
            segment
            for segment in segments
            if release < segment.start_seconds
            <= release + maximum_receiver_delay_seconds
            and segment.end_seconds - segment.start_seconds
            >= minimum_setup_control_seconds
        ]
        if not setup_controls:
            extended.append(interval)
            continue
        setup = min(setup_controls, key=lambda segment: segment.start_seconds)
        search_end = setup.end_seconds + maximum_restart_search_seconds
        latest_restart = None
        settled_start = None
        settled_end = None
        for index, (start, end, speed) in enumerate(ball_steps):
            if end < setup.start_seconds - 1e-9 or start > search_end + 1e-9:
                continue
            if settled_end is not None and start - settled_end > 0.3:
                settled_start = None
                settled_end = None
            if speed <= settled_speed_pixels_per_second:
                if settled_start is None:
                    settled_start = start
                settled_end = end
                continue
            was_settled = (
                settled_start is not None
                and settled_end is not None
                and settled_end - settled_start
                >= minimum_settled_seconds - 1e-9
            )
            following_speeds = [
                candidate[2] for candidate in ball_steps[index : index + 3]
            ]
            if (
                was_settled
                and speed >= minimum_restart_speed_pixels_per_second
                and sum(
                    candidate >= settled_speed_pixels_per_second
                    for candidate in following_speeds
                )
                >= 2
            ):
                latest_restart = start
            settled_start = None
            settled_end = None
        resumed = latest_restart if latest_restart is not None else setup.end_seconds
        interval["play_resumed_seconds"] = round(resumed, 3)
        interval["end_seconds"] = round(resumed, 3)
        interval["duration_seconds"] = round(
            resumed - float(interval["start_seconds"]),
            3,
        )
        evidence = dict(interval.get("movement_evidence", {}))
        evidence["discarded_repositioning_release_seconds"] = round(
            release, 3
        )
        evidence["setup_control_start_seconds"] = round(
            setup.start_seconds, 3
        )
        evidence["setup_control_end_seconds"] = round(setup.end_seconds, 3)
        evidence["confirmed_restart_release_seconds"] = round(resumed, 3)
        interval["movement_evidence"] = evidence
        interval["release_confidence"] = min(
            float(interval.get("release_confidence", 0.85)),
            0.75,
        )
        extended.append(interval)
    return extended

def _event_released_outside(
    event: PredictedEvent,
    intervals: Iterable[dict[str, Any]],
    observations: Iterable[PossessionObservation] = (),
) -> bool:
    if event.event_type != "pass_candidate":
        return False
    controls = list(observations)
    for interval in intervals:
        if interval.get("starts_outside"):
            continue
        start = float(interval["start_seconds"])
        resumed = interval.get(
            "play_resumed_seconds", interval.get("resumed_seconds")
        )
        end = (
            float(resumed)
            if resumed is not None
            else float("inf")
        )
        if start <= event.clip_seconds <= end:
            geometric_resume = interval.get("resumed_seconds")
            sender_controlled_after_reentry = (
                geometric_resume is not None
                and event.from_player_track_id is not None
                and any(
                    observation.player_track_id == event.from_player_track_id
                    and float(geometric_resume)
                    <= observation.clip_seconds
                    < event.clip_seconds
                    for observation in controls
                )
            )
            if sender_controlled_after_reentry:
                return False
            return True
    return False

def _event_completed_outside(
    event: PredictedEvent,
    intervals: Iterable[dict[str, Any]],
) -> bool:
    if event.completion_seconds is None:
        return False
    for interval in intervals:
        if interval.get("starts_outside"):
            continue
        start = float(interval["start_seconds"])
        resumed = interval.get(
            "play_resumed_seconds", interval.get("resumed_seconds")
        )
        if resumed is None:
            resumed = float("inf")
        if start <= event.completion_seconds <= float(resumed):
            return True
    return False

def _deceleration_immediately_precedes_boundary(
    event: PredictedEvent,
    intervals: Iterable[dict[str, Any]],
    *,
    maximum_seconds: float = 0.5,
) -> bool:
    if (
        event.completion_seconds is None
        or not event.details.startswith("Ball sharply decelerated")
    ):
        return False
    return any(
        0
        <= float(interval["start_seconds"]) - event.completion_seconds
        <= maximum_seconds
        for interval in intervals
        if not interval.get("starts_outside")
    )

def infer_restart_passes(
    intervals: Iterable[dict[str, Any]],
    possession_segments: Iterable[PossessionSegment],
    *,
    prior_events: Iterable[PredictedEvent] = (),
    ownership_lookback_seconds: float = 2.0,
    maximum_reception_seconds: float = 8.0,
    balls: dict[int, list[dict[str, Any]]] | None = None,
    startup_restart_max_seconds: float | None = None,
    control_observations: Iterable[PossessionObservation] = (),
) -> list[PredictedEvent]:
    segments = list(possession_segments)
    existing = list(prior_events)
    raw_controls = list(control_observations)
    events: list[PredictedEvent] = []
    for interval in intervals:
        resumed_value = interval.get(
            "play_resumed_seconds", interval.get("resumed_seconds")
        )
        if interval.get("starts_outside") or resumed_value is None:
            continue
        start = float(interval["start_seconds"])
        resumed = float(resumed_value)
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
        geometric_resume = float(interval.get("resumed_seconds", resumed))
        raw_receivers = [
            observation
            for observation in raw_controls
            if geometric_resume
            <= observation.clip_seconds
            <= geometric_resume + maximum_reception_seconds
            and observation.player_track_id != owner.player_track_id
            and any(
                later.player_track_id == observation.player_track_id
                and 0
                < later.clip_seconds - observation.clip_seconds
                <= 0.64
                for later in raw_controls
            )
        ]
        stable_receivers = [
            segment
            for segment in segments
            if resumed
            <= segment.start_seconds
            <= resumed + maximum_reception_seconds
            and segment.player_track_id != owner.player_track_id
        ]
        first_stable_receiver = (
            min(stable_receivers, key=lambda segment: segment.start_seconds)
            if stable_receivers
            else None
        )
        raw_receiver = (
            min(raw_receivers, key=lambda observation: observation.clip_seconds)
            if raw_receivers
            else None
        )
        if (
            raw_receiver is not None
            and (
                first_stable_receiver is None
                or raw_receiver.team == first_stable_receiver.team
                or not 0
                <= first_stable_receiver.start_seconds
                - raw_receiver.clip_seconds
                <= 0.64
            )
        ):
            raw_receiver = None
        same_team_restart_receiver = _same_team_restart_receiver(
            interval,
            segments,
            owner,
            startup_restart_max_seconds=startup_restart_max_seconds,
            maximum_reception_seconds=maximum_reception_seconds,
        )
        receiver_confirmed_turnover = any(
            event.event_type == "turnover_candidate"
            and event.team == owner.team
            and event.to_player_track_id is not None
            and abs(event.clip_seconds - start) <= 3.0
            for event in existing
        )
        if receiver_confirmed_turnover:
            continue
        if raw_receiver is not None:
            receiver = PossessionSegment(
                raw_receiver.team,
                raw_receiver.player_track_id,
                [raw_receiver],
            )
        elif same_team_restart_receiver is not None:
            receiver = same_team_restart_receiver
        else:
            receivers = [
                segment
                for segment in stable_receivers
                if segment.team != owner.team
            ]
            if not receivers:
                continue
            receiver = min(receivers, key=lambda segment: segment.start_seconds)
        reception_search_start = (
            float(interval.get("resumed_seconds", resumed))
            if same_team_restart_receiver is not None
            else resumed
        )
        completion = (
            _restart_reception_seconds(
                balls,
                resumed_seconds=reception_search_start,
                latest_seconds=receiver.start_seconds,
            )
            if balls is not None
            else None
        )
        completion = receiver.start_seconds if completion is None else completion
        if any(
            event.event_type in {"pass_candidate", "restart_pass_candidate"}
            and event.team == receiver.team
            and event.completion_seconds is not None
            and abs(event.completion_seconds - completion) <= 0.8
            for event in existing
        ):
            continue
        events.append(
            PredictedEvent(
                event_type="restart_pass_candidate",
                clip_seconds=round(
                    float(interval.get("end_seconds", resumed))
                    if same_team_restart_receiver is not None
                    else resumed,
                    3,
                ),
                team=receiver.team,
                from_player_track_id=None,
                to_player_track_id=receiver.player_track_id,
                confidence=0.55,
                details=(
                    (
                        f"The segment opened during a {owner.team} restart; "
                        f"the receiving {receiver.team} player made the first "
                        "detected controlled touch."
                    )
                    if same_team_restart_receiver is not None
                    and startup_restart_max_seconds is not None
                    and start <= startup_restart_max_seconds
                    else (
                        f"After play resumed, the receiving {receiver.team} "
                        "player made the first repeatedly detected controlled "
                        "touch."
                    )
                    if raw_receiver is not None
                    and receiver.team == owner.team
                    else (
                        f"A {owner.team} player controlled the ball near the "
                        "upper body at the boundary; the receiving teammate "
                        "made the first detected controlled touch."
                    )
                    if same_team_restart_receiver is not None
                    else (
                        f"After {owner.team} put the ball outside, play resumed "
                        f"and the opposing {receiver.team} team made the first "
                        "detected controlled touch. Restart taker is not visible."
                    )
                ),
                completion_seconds=round(completion, 3),
            )
        )
    return events

def _same_team_restart_receiver(
    interval: dict[str, Any],
    segments: Iterable[PossessionSegment],
    owner: PossessionSegment,
    *,
    startup_restart_max_seconds: float | None,
    maximum_reception_seconds: float = 8.0,
) -> PossessionSegment | None:
    resumed_value = interval.get(
        "play_resumed_seconds", interval.get("resumed_seconds")
    )
    if resumed_value is None:
        return None
    opens_during_restart = (
        startup_restart_max_seconds is not None
        and float(interval["start_seconds"]) <= startup_restart_max_seconds
    )
    held_near_upper_body = sum(
        1
        for observation in owner.observations
        if (
            observation.player_y - observation.ball_y
        ) / max(1.0, observation.player_height)
        >= 0.65
        and observation.control_ratio <= 1.6
    ) >= 2
    if not opens_during_restart and not held_near_upper_body:
        return None
    resumed = float(resumed_value)
    receivers = [
        segment
        for segment in segments
        if resumed <= segment.start_seconds <= resumed + maximum_reception_seconds
        and segment.player_track_id != owner.player_track_id
    ]
    if not receivers:
        return None
    receiver = min(receivers, key=lambda segment: segment.start_seconds)
    return receiver if receiver.team == owner.team else None

def _restart_reception_seconds(
    balls: dict[int, list[dict[str, Any]]],
    *,
    resumed_seconds: float,
    latest_seconds: float,
    minimum_incoming_speed: float = 200.0,
    maximum_outgoing_speed_ratio: float = 0.5,
) -> float | None:
    points = sorted(
        (
            point
            for frame_points in balls.values()
            for point in frame_points
            if not point.get("interpolated", False)
        ),
        key=lambda point: float(point["clip_seconds"]),
    )
    candidates: list[tuple[float, float]] = []
    for previous, current, following in zip(points, points[1:], points[2:]):
        completion = float(current["clip_seconds"])
        if not resumed_seconds <= completion <= latest_seconds:
            continue
        incoming_seconds = completion - float(previous["clip_seconds"])
        outgoing_seconds = float(following["clip_seconds"]) - completion
        if incoming_seconds <= 0 or outgoing_seconds <= 0:
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
            incoming_speed >= minimum_incoming_speed
            and outgoing_speed
            <= incoming_speed * maximum_outgoing_speed_ratio
        ):
            candidates.append(
                (incoming_speed / max(outgoing_speed, 1.0), completion)
            )
    return max(candidates)[1] if candidates else None

def _boundary_ownership_lookback(
    interval: dict[str, Any],
    configured_seconds: float,
) -> float:
    if float(interval.get("duration_seconds", 0)) >= 3.0:
        return configured_seconds
    return min(configured_seconds, 2.0)
