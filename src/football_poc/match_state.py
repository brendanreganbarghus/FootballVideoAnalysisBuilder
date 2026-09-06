from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from enum import Enum
from math import hypot
from statistics import median
from typing import Any, Iterable


class MatchPlayState(str, Enum):
    UNKNOWN = "unknown"
    IN_PLAY = "in_play"
    POSSIBLE_STOPPAGE = "possible_stoppage"
    OUT_OF_PLAY = "out_of_play"
    RESTART_PENDING = "restart_pending"
    PERIOD_ENDED = "period_ended"


class RestartType(str, Enum):
    UNKNOWN = "unknown"
    DROPPED_BALL = "dropped_ball"
    THROW_IN = "throw_in"
    CORNER_KICK = "corner_kick"
    GOAL_KICK = "goal_kick"
    FREE_KICK = "free_kick"
    DIRECT_FREE_KICK = "direct_free_kick"
    INDIRECT_FREE_KICK = "indirect_free_kick"
    PENALTY_KICK = "penalty_kick"
    KICK_OFF = "kick_off"


class LawReference(str, Enum):
    REFEREE_AND_ADVANTAGE = "laws_5_and_12_referee_and_advantage"
    START_AND_RESTART = "law_8_start_and_restart"
    BALL_IN_AND_OUT = "law_9_ball_in_and_out"
    FREE_KICKS = "law_13_free_kicks"
    THROW_IN = "law_15_throw_in"
    GOAL_KICK = "law_16_goal_kick"
    CORNER_KICK = "law_17_corner_kick"


@dataclass(frozen=True)
class MatchLawProfile:
    profile_id: str
    reviewed_at: str
    sources: tuple[str, ...]
    analytics_definition: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "reviewed_at": self.reviewed_at,
            "sources": list(self.sources),
            "analytics_definition": self.analytics_definition,
        }


MATCH_LAW_PROFILE = MatchLawProfile(
    profile_id="ifab-laws-latest-observable-v1",
    reviewed_at="2026-09-06",
    sources=(
        "https://www.theifab.com/laws/latest/"
        "the-start-and-restart-of-play/",
        "https://www.theifab.com/laws/latest/"
        "the-ball-in-and-out-of-play/",
        "https://www.theifab.com/laws/latest/fouls-and-misconduct/",
        "https://www.theifab.com/laws/latest/free-kicks/",
        "https://www.theifab.com/laws/latest/the-throw-in/",
        "https://www.theifab.com/laws/latest/the-goal-kick/",
        "https://www.theifab.com/laws/latest/the-corner-kick/",
    ),
    analytics_definition=(
        "The Laws determine match state and legal restart families. "
        "Completed passes, turnovers, possession and shot outcomes use "
        "separate project definitions because the Laws do not define those "
        "statistics."
    ),
)


RESTART_LAW_REFERENCES = {
    RestartType.UNKNOWN: LawReference.START_AND_RESTART,
    RestartType.DROPPED_BALL: LawReference.START_AND_RESTART,
    RestartType.THROW_IN: LawReference.THROW_IN,
    RestartType.CORNER_KICK: LawReference.CORNER_KICK,
    RestartType.GOAL_KICK: LawReference.GOAL_KICK,
    RestartType.FREE_KICK: LawReference.FREE_KICKS,
    RestartType.DIRECT_FREE_KICK: LawReference.FREE_KICKS,
    RestartType.INDIRECT_FREE_KICK: LawReference.FREE_KICKS,
    RestartType.PENALTY_KICK: LawReference.START_AND_RESTART,
    RestartType.KICK_OFF: LawReference.START_AND_RESTART,
}


@dataclass(frozen=True)
class MatchStateTransition:
    clip_seconds: float
    previous_state: MatchPlayState
    state: MatchPlayState
    trigger: str
    confidence: float
    restart_type: RestartType | None = None
    boundary_start_seconds: float | None = None
    law_reference: LawReference | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["previous_state"] = self.previous_state.value
        payload["state"] = self.state.value
        if self.restart_type is not None:
            payload["restart_type"] = self.restart_type.value
        if self.law_reference is not None:
            payload["law_reference"] = self.law_reference.value
        else:
            payload.pop("law_reference")
        return payload


@dataclass(frozen=True)
class MatchStateInterval:
    state: MatchPlayState
    start_seconds: float
    end_seconds: float

    def contains(self, clip_seconds: float, *, is_last: bool = False) -> bool:
        return self.start_seconds <= clip_seconds and (
            clip_seconds < self.end_seconds
            or (is_last and clip_seconds <= self.end_seconds)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
        }


@dataclass(frozen=True)
class MatchStateTimeline:
    duration_seconds: float
    initial_state: MatchPlayState
    intervals: tuple[MatchStateInterval, ...]
    transitions: tuple[MatchStateTransition, ...]

    def state_at(self, clip_seconds: float) -> MatchPlayState:
        if clip_seconds < 0 or clip_seconds > self.duration_seconds + 1e-9:
            raise ValueError("Match-state timestamp is outside the clip")
        for index, interval in enumerate(self.intervals):
            if interval.contains(
                clip_seconds, is_last=index == len(self.intervals) - 1
            ):
                return interval.state
        return self.initial_state

    def allows_event(
        self,
        event_type: str,
        clip_seconds: float,
        completion_seconds: float | None = None,
    ) -> bool:
        if event_type == "restart_pass_candidate":
            return True
        if event_type == "turnover_candidate" and self._is_boundary_exit(
            clip_seconds
        ):
            return True
        timestamps = [clip_seconds]
        if completion_seconds is not None:
            timestamps.append(completion_seconds)
        return all(
            self.state_at(seconds) == MatchPlayState.IN_PLAY
            for seconds in timestamps
        )

    def _is_boundary_exit(self, clip_seconds: float) -> bool:
        return any(
            transition.state == MatchPlayState.OUT_OF_PLAY
            and abs(transition.clip_seconds - clip_seconds) <= 1e-6
            for transition in self.transitions
        )

    def to_dict(
        self,
        *,
        rejected_boundary_candidates: Iterable[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "law_profile": MATCH_LAW_PROFILE.to_dict(),
            "initial_state": self.initial_state.value,
            "duration_seconds": self.duration_seconds,
            "intervals": [interval.to_dict() for interval in self.intervals],
            "transitions": [
                transition.to_dict() for transition in self.transitions
            ],
            "rejected_boundary_candidates": list(
                rejected_boundary_candidates
            ),
        }


def build_match_state_timeline(
    boundary_intervals: Iterable[dict[str, Any]],
    *,
    duration_seconds: float,
) -> MatchStateTimeline:
    if duration_seconds <= 0:
        raise ValueError("Match-state duration must be positive")
    boundaries = sorted(
        (dict(interval) for interval in boundary_intervals),
        key=lambda interval: float(interval["start_seconds"]),
    )
    initial_state = (
        MatchPlayState.UNKNOWN
        if boundaries
        and boundaries[0].get("starts_outside")
        and float(boundaries[0]["start_seconds"]) <= 1e-9
        else MatchPlayState.IN_PLAY
    )
    transitions: list[MatchStateTransition] = []
    current_state = initial_state

    def transition(
        seconds: float,
        state: MatchPlayState,
        trigger: str,
        confidence: float,
        *,
        boundary_start_seconds: float,
        restart_type: RestartType | None = None,
        law_reference: LawReference | None = None,
    ) -> None:
        nonlocal current_state
        clipped_seconds = round(
            min(max(float(seconds), 0.0), duration_seconds), 3
        )
        if state == current_state:
            return
        transitions.append(
            MatchStateTransition(
                clip_seconds=clipped_seconds,
                previous_state=current_state,
                state=state,
                trigger=trigger,
                confidence=confidence,
                restart_type=restart_type,
                boundary_start_seconds=round(boundary_start_seconds, 3),
                law_reference=law_reference,
            )
        )
        current_state = state

    for boundary in boundaries:
        start = float(boundary["start_seconds"])
        if start > duration_seconds:
            break
        resumed_value = boundary.get("resumed_seconds")
        resumed = (
            float(resumed_value) if resumed_value is not None else None
        )
        release_value = boundary.get("play_resumed_seconds")
        release = (
            float(release_value) if release_value is not None else None
        )
        law_event = boundary.get("law_event")
        if law_event == "offence":
            restart_type = RestartType(
                boundary.get("restart_type", RestartType.FREE_KICK.value)
            )
            if boundary.get("advantage_applied") is True:
                continue
            if boundary.get("advantage_applied") is False:
                transition(
                    start,
                    MatchPlayState.RESTART_PENDING,
                    "offence_stopped_play",
                    float(boundary.get("confidence", 0.75)),
                    boundary_start_seconds=start,
                    restart_type=restart_type,
                    law_reference=LawReference.REFEREE_AND_ADVANTAGE,
                )
            else:
                transition(
                    start,
                    MatchPlayState.POSSIBLE_STOPPAGE,
                    "possible_offence_awaiting_play_outcome",
                    float(boundary.get("confidence", 0.5)),
                    boundary_start_seconds=start,
                    restart_type=restart_type,
                    law_reference=LawReference.REFEREE_AND_ADVANTAGE,
                )
                continuation_value = boundary.get(
                    "competitive_play_continued_seconds"
                )
                confirmation_value = boundary.get(
                    "stoppage_confirmed_seconds"
                )
                if continuation_value is not None:
                    transition(
                        float(continuation_value),
                        MatchPlayState.IN_PLAY,
                        "advantage_or_no_stoppage_confirmed",
                        float(
                            boundary.get("continuation_confidence", 0.7)
                        ),
                        boundary_start_seconds=start,
                        law_reference=(
                            LawReference.REFEREE_AND_ADVANTAGE
                        ),
                    )
                    continue
                if confirmation_value is not None:
                    transition(
                        float(confirmation_value),
                        MatchPlayState.RESTART_PENDING,
                        "stoppage_confirmed",
                        float(
                            boundary.get("confirmation_confidence", 0.75)
                        ),
                        boundary_start_seconds=start,
                        restart_type=restart_type,
                        law_reference=(
                            LawReference.REFEREE_AND_ADVANTAGE
                        ),
                    )
            if release is not None:
                transition(
                    release,
                    MatchPlayState.IN_PLAY,
                    "legal_restart_release_detected",
                    float(boundary.get("release_confidence", 0.85)),
                    boundary_start_seconds=start,
                    restart_type=restart_type,
                    law_reference=RESTART_LAW_REFERENCES[restart_type],
                )
            continue
        if law_event in {"goal", "other_referee_stoppage"}:
            restart_type = (
                RestartType.KICK_OFF
                if law_event == "goal"
                else RestartType(
                    boundary.get(
                        "restart_type", RestartType.DROPPED_BALL.value
                    )
                )
            )
            transition(
                start,
                MatchPlayState.RESTART_PENDING,
                (
                    "goal_requires_kick_off"
                    if law_event == "goal"
                    else "referee_stoppage_requires_restart"
                ),
                float(boundary.get("confidence", 0.75)),
                boundary_start_seconds=start,
                restart_type=restart_type,
                law_reference=LawReference.START_AND_RESTART,
            )
            if release is not None:
                transition(
                    release,
                    MatchPlayState.IN_PLAY,
                    "legal_restart_release_detected",
                    float(boundary.get("release_confidence", 0.85)),
                    boundary_start_seconds=start,
                    restart_type=restart_type,
                    law_reference=RESTART_LAW_REFERENCES[restart_type],
                )
            continue
        if law_event == "period_end":
            transition(
                start,
                MatchPlayState.PERIOD_ENDED,
                "period_ended",
                float(boundary.get("confidence", 0.9)),
                boundary_start_seconds=start,
                law_reference=LawReference.START_AND_RESTART,
            )
            continue
        if boundary.get("stoppage_kind") == "stationary_ball_restart":
            restart_type = RestartType(
                boundary.get("restart_type", RestartType.UNKNOWN.value)
            )
            transition(
                start,
                MatchPlayState.RESTART_PENDING,
                "stationary_ball_and_player_disengagement",
                float(boundary.get("confidence", 0.75)),
                boundary_start_seconds=start,
                restart_type=restart_type,
                law_reference=RESTART_LAW_REFERENCES[restart_type],
            )
            if release is not None:
                transition(
                    release,
                    MatchPlayState.IN_PLAY,
                    "restart_kick_and_player_reaction",
                    float(boundary.get("release_confidence", 0.85)),
                    boundary_start_seconds=start,
                    restart_type=restart_type,
                    law_reference=RESTART_LAW_REFERENCES[restart_type],
                )
            continue
        if boundary.get("starts_outside"):
            if start > 1e-9:
                transition(
                    start,
                    MatchPlayState.UNKNOWN,
                    "ball_tracking_opened_outside_boundary",
                    0.5,
                    boundary_start_seconds=start,
                    law_reference=LawReference.BALL_IN_AND_OUT,
                )
            if release is not None:
                transition(
                    release,
                    MatchPlayState.IN_PLAY,
                    "restart_release_detected",
                    0.7,
                    boundary_start_seconds=start,
                    restart_type=RestartType.UNKNOWN,
                    law_reference=LawReference.START_AND_RESTART,
                )
            continue

        transition(
            start,
            MatchPlayState.OUT_OF_PLAY,
            "sustained_boundary_exit",
            0.75,
            boundary_start_seconds=start,
            law_reference=LawReference.BALL_IN_AND_OUT,
        )
        if resumed is not None and (release is None or release > resumed + 1e-9):
            transition(
                resumed,
                MatchPlayState.RESTART_PENDING,
                "ball_reentered_before_restart_release",
                0.7,
                boundary_start_seconds=start,
                restart_type=RestartType.UNKNOWN,
                law_reference=LawReference.START_AND_RESTART,
            )
        if release is not None:
            transition(
                release,
                MatchPlayState.IN_PLAY,
                "restart_release_detected",
                0.8,
                boundary_start_seconds=start,
                restart_type=RestartType.UNKNOWN,
                law_reference=LawReference.START_AND_RESTART,
            )

    ordered = sorted(
        enumerate(transitions),
        key=lambda item: (item[1].clip_seconds, item[0]),
    )
    ordered_transitions = [transition for _, transition in ordered]
    transitions = []
    previous_state = initial_state
    for state_change in ordered_transitions:
        transitions.append(
            MatchStateTransition(
                clip_seconds=state_change.clip_seconds,
                previous_state=previous_state,
                state=state_change.state,
                trigger=state_change.trigger,
                confidence=state_change.confidence,
                restart_type=state_change.restart_type,
                boundary_start_seconds=state_change.boundary_start_seconds,
                law_reference=state_change.law_reference,
            )
        )
        previous_state = state_change.state
    intervals: list[MatchStateInterval] = []
    state = initial_state
    start_seconds = 0.0
    for state_change in transitions:
        if state_change.clip_seconds > start_seconds:
            intervals.append(
                MatchStateInterval(
                    state=state,
                    start_seconds=round(start_seconds, 3),
                    end_seconds=state_change.clip_seconds,
                )
            )
        state = state_change.state
        start_seconds = state_change.clip_seconds
    if start_seconds < duration_seconds or not intervals:
        intervals.append(
            MatchStateInterval(
                state=state,
                start_seconds=round(start_seconds, 3),
                end_seconds=round(duration_seconds, 3),
            )
        )
    return MatchStateTimeline(
        duration_seconds=round(duration_seconds, 3),
        initial_state=initial_state,
        intervals=tuple(intervals),
        transitions=tuple(transitions),
    )


def detect_stationary_ball_restarts(
    ball_points: Iterable[dict[str, Any]],
    player_points: Iterable[dict[str, Any]],
    *,
    stationary_speed_pixels_per_second: float = 40.0,
    minimum_stationary_seconds: float = 0.4,
    maximum_release_delay_seconds: float = 1.5,
    minimum_release_speed_pixels_per_second: float = 350.0,
    sustained_motion_speed_pixels_per_second: float = 150.0,
    player_active_speed_heights_per_second: float = 0.5,
    maximum_setup_active_ratio: float = 0.3,
    minimum_reaction_active_ratio: float = 0.45,
    minimum_reaction_increase: float = 0.15,
    minimum_reacting_players: int = 6,
    nearby_radius_heights: float = 8.0,
) -> list[dict[str, Any]]:
    """Find high-confidence in-field restarts without depending on officials."""
    if stationary_speed_pixels_per_second < 0:
        raise ValueError("Stationary-ball speed cannot be negative")
    if minimum_stationary_seconds <= 0 or maximum_release_delay_seconds <= 0:
        raise ValueError("Restart timing thresholds must be positive")
    if (
        minimum_release_speed_pixels_per_second <= 0
        or sustained_motion_speed_pixels_per_second <= 0
        or player_active_speed_heights_per_second <= 0
    ):
        raise ValueError("Restart movement thresholds must be positive")
    if nearby_radius_heights <= 0 or minimum_reacting_players < 1:
        raise ValueError("Nearby-player thresholds must be positive")
    if not (
        0 <= maximum_setup_active_ratio <= 1
        and 0 <= minimum_reaction_active_ratio <= 1
        and 0 <= minimum_reaction_increase <= 1
    ):
        raise ValueError("Restart activity ratios must be between zero and one")

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
    balls = [
        balls_by_seconds[seconds] for seconds in sorted(balls_by_seconds)
    ]
    ball_steps: list[dict[str, float]] = []
    for first, second in zip(balls, balls[1:]):
        start = float(first["clip_seconds"])
        end = float(second["clip_seconds"])
        elapsed = end - start
        if elapsed <= 0 or elapsed > 0.3:
            continue
        ball_steps.append(
            {
                "start_seconds": start,
                "end_seconds": end,
                "speed": hypot(
                    float(second["x"]) - float(first["x"]),
                    float(second["y"]) - float(first["y"]),
                )
                / elapsed,
            }
        )

    stationary_runs: list[list[dict[str, float]]] = []
    current_run: list[dict[str, float]] = []
    for step in ball_steps:
        contiguous = (
            not current_run
            or abs(
                step["start_seconds"] - current_run[-1]["end_seconds"]
            )
            <= 1e-6
        )
        if step["speed"] <= stationary_speed_pixels_per_second and contiguous:
            current_run.append(step)
            continue
        if (
            current_run
            and current_run[-1]["end_seconds"]
            - current_run[0]["start_seconds"]
            >= minimum_stationary_seconds - 1e-9
        ):
            stationary_runs.append(current_run)
        current_run = (
            [step]
            if step["speed"] <= stationary_speed_pixels_per_second
            else []
        )
    if (
        current_run
        and current_run[-1]["end_seconds"]
        - current_run[0]["start_seconds"]
        >= minimum_stationary_seconds - 1e-9
    ):
        stationary_runs.append(current_run)

    player_tracks: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for point in player_points:
        if point.get("team") not in {"red", "black", "blue", "white"}:
            continue
        player_tracks[int(point["track_id"])].append(point)
    player_motion: list[tuple[float, float, int]] = []
    for track_id, points in player_tracks.items():
        ordered = sorted(points, key=lambda point: float(point["clip_seconds"]))
        for first, second in zip(ordered, ordered[1:]):
            seconds = float(second["clip_seconds"])
            elapsed = seconds - float(first["clip_seconds"])
            height = (
                float(first["y2"])
                - float(first["y1"])
                + float(second["y2"])
                - float(second["y1"])
            ) / 2
            if elapsed <= 0 or elapsed > 0.3 or height <= 0:
                continue
            nearest_ball = min(
                balls,
                key=lambda ball: abs(
                    float(ball["clip_seconds"]) - seconds
                ),
                default=None,
            )
            if (
                nearest_ball is None
                or abs(float(nearest_ball["clip_seconds"]) - seconds) > 0.11
            ):
                continue
            center_x = (float(second["x1"]) + float(second["x2"])) / 2
            center_y = (float(second["y1"]) + float(second["y2"])) / 2
            distance_heights = hypot(
                center_x - float(nearest_ball["x"]),
                center_y - float(nearest_ball["y"]),
            ) / height
            if distance_heights > nearby_radius_heights:
                continue
            speed = hypot(
                (
                    float(second["x1"])
                    + float(second["x2"])
                    - float(first["x1"])
                    - float(first["x2"])
                )
                / 2,
                (
                    float(second["y1"])
                    + float(second["y2"])
                    - float(first["y1"])
                    - float(first["y2"])
                )
                / 2,
            ) / elapsed / height
            player_motion.append((seconds, speed, track_id))

    candidates: list[dict[str, Any]] = []
    used_releases: set[float] = set()
    for run in reversed(stationary_runs):
        stationary_start = run[0]["start_seconds"]
        stationary_end = run[-1]["end_seconds"]
        release_index = None
        for index, step in enumerate(ball_steps):
            if step["start_seconds"] < stationary_end - 1e-9:
                continue
            if (
                step["start_seconds"] - stationary_end
                > maximum_release_delay_seconds + 1e-9
            ):
                break
            following_speeds = [
                candidate["speed"] for candidate in ball_steps[index : index + 3]
            ]
            if (
                step["speed"] >= minimum_release_speed_pixels_per_second
                and sum(
                    speed >= sustained_motion_speed_pixels_per_second
                    for speed in following_speeds
                )
                >= 2
            ):
                release_index = index
                break
        if release_index is None:
            continue
        release = ball_steps[release_index]["start_seconds"]
        if release in used_releases:
            continue
        setup_motion = [
            speed
            for seconds, speed, _ in player_motion
            if stationary_start <= seconds <= stationary_end
        ]
        reaction_motion = [
            (speed, track_id)
            for seconds, speed, track_id in player_motion
            if release - 0.4 <= seconds <= release + 0.4
        ]
        if len(setup_motion) < 8 or len(reaction_motion) < 8:
            continue
        setup_active_ratio = sum(
            speed >= player_active_speed_heights_per_second
            for speed in setup_motion
        ) / len(setup_motion)
        reaction_active_ratio = sum(
            speed >= player_active_speed_heights_per_second
            for speed, _ in reaction_motion
        ) / len(reaction_motion)
        reacting_players = {
            track_id
            for speed, track_id in reaction_motion
            if speed >= player_active_speed_heights_per_second
        }
        if (
            setup_active_ratio > maximum_setup_active_ratio
            or reaction_active_ratio < minimum_reaction_active_ratio
            or reaction_active_ratio - setup_active_ratio
            < minimum_reaction_increase
            or len(reacting_players) < minimum_reacting_players
        ):
            continue
        candidates.append(
            {
                "start_seconds": round(stationary_start, 3),
                "end_seconds": round(release, 3),
                "duration_seconds": round(release - stationary_start, 3),
                "resumed_seconds": round(stationary_start, 3),
                "play_resumed_seconds": round(release, 3),
                "starts_outside": False,
                "stoppage_kind": "stationary_ball_restart",
                "restart_type": RestartType.FREE_KICK.value,
                "confidence": 0.75,
                "release_confidence": 0.85,
                "movement_evidence": {
                    "stationary_end_seconds": round(stationary_end, 3),
                    "setup_active_ratio": round(setup_active_ratio, 4),
                    "reaction_active_ratio": round(reaction_active_ratio, 4),
                    "reacting_player_count": len(reacting_players),
                    "release_speed_pixels_per_second": round(
                        ball_steps[release_index]["speed"], 2
                    ),
                },
            }
        )
        used_releases.add(release)
    return sorted(candidates, key=lambda item: float(item["start_seconds"]))


def partition_fragmented_boundary_candidates(
    boundary_intervals: Iterable[dict[str, Any]],
    possession_intervals: Iterable[dict[str, Any]],
    *,
    minimum_fragment_count: int = 3,
    maximum_boundary_depth_pixels: float = 60.0,
    minimum_interior_margin_seconds: float = 1.0,
    minimum_possession_seconds: float = 0.4,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reject shallow projection artifacts with confirmed control inside them."""
    possessions = list(possession_intervals)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for source_interval in boundary_intervals:
        interval = dict(source_interval)
        start = float(interval["start_seconds"])
        resumed_value = interval.get("resumed_seconds")
        resumed = (
            float(resumed_value)
            if resumed_value is not None
            else float(interval["end_seconds"])
        )
        interior_controls = [
            possession
            for possession in possessions
            if float(possession["start_seconds"])
            >= start + minimum_interior_margin_seconds
            and float(possession["end_seconds"])
            <= resumed - minimum_interior_margin_seconds
            and float(possession["end_seconds"])
            - float(possession["start_seconds"])
            >= minimum_possession_seconds
        ]
        fragmented_projection = (
            int(interval.get("coalesced_candidate_count", 1))
            >= minimum_fragment_count
            and abs(float(interval.get("minimum_signed_distance_px", 0)))
            <= maximum_boundary_depth_pixels
            and bool(interior_controls)
        )
        if fragmented_projection:
            interval["reason"] = "competitive_possession_inside_boundary"
            interval["competitive_evidence"] = {
                "interior_possession_count": len(interior_controls),
                "longest_possession_seconds": round(
                    max(
                        float(possession["end_seconds"])
                        - float(possession["start_seconds"])
                        for possession in interior_controls
                    ),
                    3,
                ),
            }
            rejected.append(interval)
        else:
            accepted.append(interval)
    return accepted, rejected


def partition_continuous_flight_candidates(
    boundary_intervals: Iterable[dict[str, Any]],
    ball_points: Iterable[dict[str, Any]],
    *,
    context_seconds: float = 0.4,
    minimum_median_speed_pixels_per_second: float = 120.0,
    moving_speed_pixels_per_second: float = 80.0,
    minimum_moving_step_ratio: float = 0.75,
    minimum_direction_consistency: float = 0.7,
    minimum_flight_duration_seconds: float = 2.2,
    minimum_flight_depth_pixels: float = 100.0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if context_seconds < 0:
        raise ValueError("Flight-classification context cannot be negative")
    if (
        minimum_median_speed_pixels_per_second <= 0
        or moving_speed_pixels_per_second <= 0
    ):
        raise ValueError("Flight-classification speeds must be positive")
    if not 0 <= minimum_moving_step_ratio <= 1:
        raise ValueError("Moving-step ratio must be between zero and one")
    if not -1 <= minimum_direction_consistency <= 1:
        raise ValueError("Direction consistency must be between -1 and one")
    if minimum_flight_duration_seconds < 0 or minimum_flight_depth_pixels < 0:
        raise ValueError("Flight duration and depth must be non-negative")

    points = sorted(
        (
            point
            for point in ball_points
            if not point.get("interpolated", False)
        ),
        key=lambda point: float(point["clip_seconds"]),
    )
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for source_interval in boundary_intervals:
        interval = dict(source_interval)
        start = float(interval["start_seconds"])
        end = float(interval["end_seconds"])
        sample = [
            point
            for point in points
            if start - context_seconds
            <= float(point["clip_seconds"])
            <= end + context_seconds
        ]
        steps: list[tuple[float, float, float]] = []
        for first, second in zip(sample, sample[1:]):
            elapsed = float(second["clip_seconds"]) - float(
                first["clip_seconds"]
            )
            if elapsed <= 0:
                continue
            delta_x = float(second["x"]) - float(first["x"])
            delta_y = float(second["y"]) - float(first["y"])
            steps.append((delta_x, delta_y, hypot(delta_x, delta_y) / elapsed))
        speeds = [step[2] for step in steps]
        moving_steps = [
            step for step in steps if step[2] >= moving_speed_pixels_per_second
        ]
        direction_cosines = [
            (first[0] * second[0] + first[1] * second[1])
            / (hypot(first[0], first[1]) * hypot(second[0], second[1]))
            for first, second in zip(moving_steps, moving_steps[1:])
            if hypot(first[0], first[1]) > 0
            and hypot(second[0], second[1]) > 0
        ]
        moving_ratio = len(moving_steps) / len(steps) if steps else 0.0
        direction_ratio = (
            sum(
                cosine >= minimum_direction_consistency
                for cosine in direction_cosines
            )
            / len(direction_cosines)
            if direction_cosines
            else 0.0
        )
        continuous_flight = (
            len(steps) >= 4
            and float(interval.get("duration_seconds", end - start))
            >= minimum_flight_duration_seconds
            and abs(float(interval.get("minimum_signed_distance_px", 0)))
            >= minimum_flight_depth_pixels
            and median(speeds) >= minimum_median_speed_pixels_per_second
            and moving_ratio >= minimum_moving_step_ratio
            and direction_ratio >= minimum_moving_step_ratio
        )
        if continuous_flight:
            interval["reason"] = "continuous_flight"
            interval["flight_evidence"] = {
                "median_speed_pixels_per_second": round(median(speeds), 2),
                "moving_step_ratio": round(moving_ratio, 4),
                "direction_consistency_ratio": round(direction_ratio, 4),
            }
            rejected.append(interval)
        else:
            accepted.append(interval)
    return accepted, rejected


def coalesce_stoppage_candidates(
    boundary_intervals: Iterable[dict[str, Any]],
    *,
    maximum_gap_seconds: float = 1.0,
) -> list[dict[str, Any]]:
    if maximum_gap_seconds < 0:
        raise ValueError("Stoppage coalescing gap cannot be negative")
    ordered = sorted(
        (dict(interval) for interval in boundary_intervals),
        key=lambda interval: float(interval["start_seconds"]),
    )
    merged: list[dict[str, Any]] = []
    for interval in ordered:
        if not merged:
            merged.append(interval)
            continue
        previous = merged[-1]
        previous_resume = previous.get(
            "resumed_seconds", previous.get("end_seconds")
        )
        gap = (
            float(interval["start_seconds"]) - float(previous_resume)
            if previous_resume is not None
            else float("inf")
        )
        if (
            previous_resume is not None
            and 0 <= gap <= maximum_gap_seconds
            and not interval.get("starts_outside")
        ):
            previous["end_frame"] = interval.get(
                "end_frame", previous.get("end_frame")
            )
            previous["end_seconds"] = interval["end_seconds"]
            previous["resumed_seconds"] = interval.get("resumed_seconds")
            previous["duration_seconds"] = round(
                float(previous["end_seconds"])
                - float(previous["start_seconds"]),
                3,
            )
            previous["minimum_signed_distance_px"] = min(
                float(previous.get("minimum_signed_distance_px", 0)),
                float(interval.get("minimum_signed_distance_px", 0)),
            )
            previous["coalesced_candidate_count"] = (
                int(previous.get("coalesced_candidate_count", 1)) + 1
            )
            continue
        merged.append(interval)
    return merged
