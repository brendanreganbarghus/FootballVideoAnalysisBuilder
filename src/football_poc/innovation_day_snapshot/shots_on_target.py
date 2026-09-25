"""Conservative Innovation Day shots-on-target analytics.

Shots on target are a project analytics contract, not an IFAB statistic. An
intentional scoring attempt counts once when it produces a separately
confirmed valid goal, or when a goalkeeper/last-line defender saves a
goal-bound attempt. Ordinary blocks, woodwork that stays out, off-target
attempts, and unresolved outcomes never count.

The classifier consumes only a normalized runtime evidence file
(``shot-evidence.json``). Frozen BAC image coordinates cannot establish ball
height, goal-mouth intersection, or save contacts, so without that evidence
the analysis reports ``unavailable`` with explicit reasons and emits nothing.
Manual labels, M#/C# references, and provider events are never inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

SCHEMA_VERSION = 1
DEFINITION_VERSION = "innovation-sot-v1"
EVIDENCE_SOURCE_KIND = "innovation_runtime_shot_evidence"
SETTING_FILE_NAME = "shots-on-target-setting.json"
EVIDENCE_FILE_NAME = "shot-evidence.json"
SUMMARY_FILE_NAME = "shots-on-target.json"
EVENT_TYPE = "shot_on_target"

RELEASE_INTENTS = {"scoring_attempt", "pass", "cross", "clearance", "ambiguous"}
CONTACT_KINDS = {
    "goalkeeper",
    "last_line_defender",
    "outfield",
    "woodwork",
    "unknown",
}
STOPPAGE_TOLERANCE_SECONDS = 0.2
MINIMUM_OBSERVED_SAMPLES = 2
FACE_CONTACT_TOLERANCE_SECONDS = 0.6
FACE_LIVE_PLAY_SECONDS = 2.0


class ShotEvidenceError(ValueError):
    """Raised when runtime shot evidence or configuration is malformed."""


@dataclass(frozen=True)
class GoalGeometry:
    side: str
    goal_line_x: float
    post_low_y: float
    post_high_y: float
    crossbar_z: float
    uncertainty_m: float

    def classify(self, y: float, z: float) -> str:
        u = self.uncertainty_m
        if z < -u:
            return "ambiguous"
        if (
            self.post_low_y + u <= y <= self.post_high_y - u
            and z <= self.crossbar_z - u
        ):
            return "inside"
        if (
            y < self.post_low_y - u
            or y > self.post_high_y + u
            or z > self.crossbar_z + u
        ):
            return "outside"
        return "ambiguous"


@dataclass(frozen=True)
class Sample:
    frame: int
    seconds: float
    x: float
    y: float
    z: float
    observed: bool


@dataclass(frozen=True)
class Release:
    frame: int
    seconds: float
    team: str | None
    player_track_id: int | None
    intent: str
    continuation_of: int | None
    evidence: str


@dataclass(frozen=True)
class Contact:
    frame: int
    seconds: float
    kind: str
    team: str | None
    player_track_id: int | None


@dataclass(frozen=True)
class GoalFact:
    frame: int
    seconds: float
    team: str | None
    goal_side: str
    valid: bool
    evidence: str


@dataclass(frozen=True)
class FaceArrival:
    frame: int
    seconds: float
    goal_side: str
    y: float
    z: float
    arrested: bool
    method: str


@dataclass(frozen=True)
class ShotEvidence:
    teams: tuple[str, ...]
    goals: dict[str, GoalGeometry]
    attacking_goal: dict[str, str]
    trajectory: tuple[Sample, ...]
    releases: tuple[Release, ...]
    contacts: tuple[Contact, ...]
    goal_facts: tuple[GoalFact, ...]
    face_arrivals: tuple[FaceArrival, ...] = ()


@dataclass(frozen=True)
class Readiness:
    status: str
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "reasons": list(self.reasons)}


@dataclass
class Attempt:
    attempt_id: str
    team: str | None
    release: Release
    target_goal: str | None
    resolution: str = "unresolved"
    reason: str = ""
    outcome_frame: int | None = None
    outcome_seconds: float | None = None
    contact: Contact | None = None
    goal: GoalFact | None = None
    duplicate_release_frames: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "team": self.team,
            "target_goal": self.target_goal,
            "release_frame": self.release.frame,
            "release_seconds": self.release.seconds,
            "release_player_track_id": self.release.player_track_id,
            "resolution": self.resolution,
            "reason": self.reason,
            "outcome_frame": self.outcome_frame,
            "outcome_seconds": self.outcome_seconds,
            "contact_kind": self.contact.kind if self.contact else None,
            "contact_player_track_id": (
                self.contact.player_track_id if self.contact else None
            ),
            "linked_goal_frame": self.goal.frame if self.goal else None,
            "duplicate_release_frames": list(self.duplicate_release_frames),
        }


def _require(mapping: Any, key: str, context: str) -> Any:
    if not isinstance(mapping, dict) or key not in mapping:
        raise ShotEvidenceError(f"{context} requires '{key}'")
    return mapping[key]


def _number(value: Any, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ShotEvidenceError(f"{context} must be a number")
    return float(value)


def _integer(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ShotEvidenceError(f"{context} must be an integer")
    return value


def _optional_team(value: Any, teams: tuple[str, ...], context: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ShotEvidenceError(f"{context} team must be a string or null")
    return value if value in teams else None


def _optional_track(value: Any, context: str) -> int | None:
    return None if value is None else _integer(value, context)


def readiness(payload: dict[str, Any] | None) -> Readiness:
    """Report whether runtime evidence satisfies the SOT contract."""
    if payload is None:
        return Readiness(
            "unavailable",
            (
                "shot_evidence_adapter_missing",
                "goal_calibration_missing",
                "ball_height_missing",
                "save_contact_evidence_missing",
                "valid_goal_evidence_missing",
            ),
        )
    if not isinstance(payload, dict):
        raise ShotEvidenceError("Shot evidence must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ShotEvidenceError("Unsupported shot evidence schema_version")
    if payload.get("source_kind") != EVIDENCE_SOURCE_KIND:
        raise ShotEvidenceError(
            "Shot evidence must come from the Innovation runtime evidence "
            "adapter, never from manual or provider event labels"
        )
    reasons: list[str] = []
    calibration = payload.get("calibration")
    if not isinstance(calibration, dict) or not calibration.get("goals"):
        reasons.append("goal_calibration_missing")
    elif not calibration.get("attacking_goal"):
        reasons.append("attacking_direction_missing")
    trajectory = payload.get("ball_trajectory")
    has_height = isinstance(trajectory, list) and any(
        isinstance(sample, dict)
        and sample.get("observed") is True
        and sample.get("z") is not None
        for sample in trajectory
    )
    if not isinstance(trajectory, list) or not (
        has_height or isinstance(payload.get("goal_face_arrivals"), list)
    ):
        reasons.append("ball_height_missing")
    if not isinstance(payload.get("releases"), list):
        reasons.append("release_evidence_missing")
    if not isinstance(payload.get("contacts"), list):
        reasons.append("save_contact_evidence_missing")
    if not isinstance(payload.get("goals"), list):
        reasons.append("valid_goal_evidence_missing")
    if reasons:
        return Readiness("unavailable", tuple(reasons))
    parse_evidence(payload)
    return Readiness("ready")


def parse_evidence(payload: dict[str, Any]) -> ShotEvidence:
    calibration = _require(payload, "calibration", "Shot evidence")
    teams_value = _require(calibration, "teams", "Calibration")
    if (
        not isinstance(teams_value, list)
        or len(teams_value) != 2
        or not all(isinstance(team, str) and team for team in teams_value)
        or len(set(teams_value)) != 2
    ):
        raise ShotEvidenceError("Calibration teams must list two team labels")
    teams = tuple(teams_value)
    goals: dict[str, GoalGeometry] = {}
    goals_value = _require(calibration, "goals", "Calibration")
    if not isinstance(goals_value, dict):
        raise ShotEvidenceError("Calibration goals must be an object")
    for side, goal in goals_value.items():
        if side not in {"left", "right"}:
            raise ShotEvidenceError(f"Unknown goal side: {side}")
        posts = _require(goal, "post_y", f"Goal {side}")
        if not isinstance(posts, list) or len(posts) != 2:
            raise ShotEvidenceError(f"Goal {side} post_y needs two values")
        low, high = sorted(_number(value, f"Goal {side} post") for value in posts)
        crossbar = _number(_require(goal, "crossbar_z", f"Goal {side}"), "crossbar_z")
        uncertainty = _number(
            _require(goal, "uncertainty_m", f"Goal {side}"), "uncertainty_m"
        )
        if high <= low or crossbar <= 0 or uncertainty < 0:
            raise ShotEvidenceError(f"Goal {side} geometry is invalid")
        goals[side] = GoalGeometry(
            side,
            _number(_require(goal, "goal_line_x", f"Goal {side}"), "goal_line_x"),
            low,
            high,
            crossbar,
            uncertainty,
        )
    attacking_value = _require(calibration, "attacking_goal", "Calibration")
    if not isinstance(attacking_value, dict):
        raise ShotEvidenceError("attacking_goal must map team to goal side")
    attacking_goal: dict[str, str] = {}
    for team, side in attacking_value.items():
        if team not in teams or side not in goals:
            raise ShotEvidenceError(
                "attacking_goal must reference calibrated teams and goals"
            )
        attacking_goal[team] = side
    trajectory = []
    for index, sample in enumerate(_require(payload, "ball_trajectory", "Shot evidence")):
        context = f"ball_trajectory[{index}]"
        observed = _require(sample, "observed", context)
        if not isinstance(observed, bool):
            raise ShotEvidenceError(f"{context}.observed must be boolean")
        z = sample.get("z")
        if z is None:
            continue
        trajectory.append(
            Sample(
                _integer(_require(sample, "frame", context), f"{context}.frame"),
                _number(_require(sample, "seconds", context), f"{context}.seconds"),
                _number(_require(sample, "x", context), f"{context}.x"),
                _number(_require(sample, "y", context), f"{context}.y"),
                _number(z, f"{context}.z"),
                observed,
            )
        )
    releases = []
    for index, item in enumerate(_require(payload, "releases", "Shot evidence")):
        context = f"releases[{index}]"
        intent = _require(item, "intent", context)
        if intent not in RELEASE_INTENTS:
            raise ShotEvidenceError(f"{context}.intent is unsupported")
        releases.append(
            Release(
                _integer(_require(item, "frame", context), f"{context}.frame"),
                _number(_require(item, "seconds", context), f"{context}.seconds"),
                _optional_team(item.get("team"), teams, context),
                _optional_track(item.get("player_track_id"), context),
                intent,
                _optional_track(item.get("continuation_of"), context),
                str(item.get("evidence") or ""),
            )
        )
    contacts = []
    for index, item in enumerate(_require(payload, "contacts", "Shot evidence")):
        context = f"contacts[{index}]"
        kind = _require(item, "kind", context)
        if kind not in CONTACT_KINDS:
            raise ShotEvidenceError(f"{context}.kind is unsupported")
        contacts.append(
            Contact(
                _integer(_require(item, "frame", context), f"{context}.frame"),
                _number(_require(item, "seconds", context), f"{context}.seconds"),
                kind,
                _optional_team(item.get("team"), teams, context),
                _optional_track(item.get("player_track_id"), context),
            )
        )
    goal_facts = []
    for index, item in enumerate(_require(payload, "goals", "Shot evidence")):
        context = f"goals[{index}]"
        valid = _require(item, "valid", context)
        if not isinstance(valid, bool):
            raise ShotEvidenceError(f"{context}.valid must be boolean")
        side = _require(item, "goal_side", context)
        if side not in {"left", "right"}:
            raise ShotEvidenceError(f"{context}.goal_side is unsupported")
        goal_facts.append(
            GoalFact(
                _integer(_require(item, "frame", context), f"{context}.frame"),
                _number(_require(item, "seconds", context), f"{context}.seconds"),
                _optional_team(item.get("team"), teams, context),
                side,
                valid,
                str(item.get("evidence") or ""),
            )
        )
    arrivals = []
    for index, item in enumerate(payload.get("goal_face_arrivals") or []):
        context = f"goal_face_arrivals[{index}]"
        side = _require(item, "goal_side", context)
        if side not in goals:
            raise ShotEvidenceError(f"{context}.goal_side is not calibrated")
        arrested = _require(item, "arrested", context)
        if not isinstance(arrested, bool):
            raise ShotEvidenceError(f"{context}.arrested must be boolean")
        arrivals.append(
            FaceArrival(
                _integer(_require(item, "frame", context), f"{context}.frame"),
                _number(_require(item, "seconds", context), f"{context}.seconds"),
                side,
                _number(_require(item, "y", context), f"{context}.y"),
                _number(_require(item, "z", context), f"{context}.z"),
                arrested,
                str(item.get("method") or ""),
            )
        )
    return ShotEvidence(
        teams,
        goals,
        attacking_goal,
        tuple(sorted(trajectory, key=lambda sample: sample.frame)),
        tuple(sorted(releases, key=lambda release: release.frame)),
        tuple(sorted(contacts, key=lambda contact: contact.frame)),
        tuple(sorted(goal_facts, key=lambda goal: goal.frame)),
        tuple(sorted(arrivals, key=lambda arrival: arrival.frame)),
    )


def state_lookup(match_state: dict[str, Any]) -> Callable[[float], str]:
    intervals = [
        (
            float(interval["start_seconds"]),
            float(interval["end_seconds"]),
            str(interval["state"]),
        )
        for interval in match_state.get("intervals", [])
    ]
    initial = str(match_state.get("initial_state", "in_play"))

    def state_at(seconds: float) -> str:
        for index, (start, end, state) in enumerate(intervals):
            if start <= seconds and (
                seconds < end or (index == len(intervals) - 1 and seconds <= end)
            ):
                return state
        return initial

    return state_at


def _stoppage_before(
    match_state: dict[str, Any], start: float, end: float
) -> bool:
    for interval in match_state.get("intervals", []):
        begin = float(interval["start_seconds"])
        if (
            str(interval["state"]) != "in_play"
            and start < begin < end - STOPPAGE_TOLERANCE_SECONDS
        ):
            return True
    return False


def _attempt_id(team: str | None, release: Release, goal: str | None) -> str:
    return f"sot-v1-{team or 'unknown'}-{release.frame:06d}-{goal or 'unknown'}"


def _goal_line_crossing(
    samples: list[Sample], geometry: GoalGeometry
) -> tuple[Sample, float, float] | None:
    for first, second in zip(samples, samples[1:]):
        a = first.x - geometry.goal_line_x
        b = second.x - geometry.goal_line_x
        if a == 0:
            return first, first.y, first.z
        if a * b < 0 or b == 0:
            ratio = a / (a - b)
            return (
                second,
                first.y + (second.y - first.y) * ratio,
                first.z + (second.z - first.z) * ratio,
            )
    return None


def _projected_frame_position(
    samples: list[Sample], geometry: GoalGeometry
) -> str:
    if len(samples) < MINIMUM_OBSERVED_SAMPLES:
        return "insufficient"
    first, second = samples[-2], samples[-1]
    dx = second.x - first.x
    remaining = geometry.goal_line_x - second.x
    if dx == 0 or remaining * dx < 0:
        return "outside"
    ratio = remaining / dx
    return geometry.classify(
        second.y + (second.y - first.y) * ratio,
        second.z + (second.z - first.z) * ratio,
    )


def _face_arrival_near(
    evidence: ShotEvidence,
    target: str,
    within: Callable[[int], bool],
    seconds: float,
) -> FaceArrival | None:
    return next(
        (
            item
            for item in evidence.face_arrivals
            if item.goal_side == target
            and within(item.frame)
            and abs(item.seconds - seconds) <= FACE_CONTACT_TOLERANCE_SECONDS
        ),
        None,
    )


def _resolve_face_arrival(
    attempt: Attempt,
    arrival: FaceArrival,
    geometry: GoalGeometry,
    match_state: dict[str, Any],
    duration_seconds: float,
) -> None:
    """Resolve a monocular goal-face arrest without a detected contact.

    A ball arrested inside the calibrated goal face has reached the goal
    plane inside the frame. If play then stays live (no goal), it was stopped
    on the line and counts as on target. Arrests outside the frame count as
    off target only when the ball then leaves play.
    """
    attempt.outcome_frame = arrival.frame
    attempt.outcome_seconds = arrival.seconds
    if not arrival.arrested:
        attempt.reason = "outcome_not_observed"
        return
    if _stoppage_before(match_state, attempt.release.seconds, arrival.seconds):
        attempt.reason = "play_stopped_before_outcome"
        return
    position = geometry.classify(arrival.y, arrival.z)
    live_until = arrival.seconds + FACE_LIVE_PLAY_SECONDS
    if position == "ambiguous":
        attempt.reason = "goal_frame_ambiguous"
    elif live_until > duration_seconds:
        attempt.reason = "flight_truncated"
    elif position == "inside":
        if _stoppage_before(
            match_state, arrival.seconds, live_until + STOPPAGE_TOLERANCE_SECONDS
        ):
            attempt.reason = "goal_entry_without_goal_confirmation"
        else:
            attempt.resolution = "on_target"
            attempt.reason = "stopped_at_goal_face"
    elif _stoppage_before(
        match_state, arrival.seconds, live_until + STOPPAGE_TOLERANCE_SECONDS
    ):
        attempt.resolution = "off_target"
        attempt.reason = "wide_or_high"
    else:
        attempt.reason = "off_frame_arrest_in_play"


def classify_attempts(
    evidence: ShotEvidence,
    match_state: dict[str, Any],
    *,
    duration_seconds: float,
) -> list[Attempt]:
    state_at = state_lookup(match_state)
    attempts: list[Attempt] = []
    releases = list(evidence.releases)
    distinct: list[Release] = []
    duplicates: dict[int, list[int]] = {}
    for release in releases:
        if release.intent not in {"scoring_attempt", "ambiguous"}:
            distinct.append(release)
            continue
        if release.continuation_of is not None:
            duplicates.setdefault(release.continuation_of, []).append(release.frame)
            continue
        previous = next(
            (
                earlier
                for earlier in reversed(distinct)
                if earlier.intent in {"scoring_attempt", "ambiguous"}
            ),
            None,
        )
        if (
            previous is not None
            and previous.team == release.team
            and not any(
                previous.frame < item.frame <= release.frame
                for item in (*evidence.contacts, *evidence.goal_facts)
            )
            and not any(
                previous.frame < other.frame < release.frame
                for other in distinct
                if other.intent not in {"scoring_attempt", "ambiguous"}
            )
        ):
            # Same team, no intervening contact or other release: the same
            # flight observed again (for example after a track-ID handoff).
            duplicates.setdefault(previous.frame, []).append(release.frame)
            continue
        distinct.append(release)

    for index, release in enumerate(distinct):
        if release.intent not in {"scoring_attempt", "ambiguous"}:
            continue
        target = (
            evidence.attacking_goal.get(release.team) if release.team else None
        )
        attempt = Attempt(
            _attempt_id(release.team, release, target),
            release.team,
            release,
            target,
            duplicate_release_frames=sorted(duplicates.get(release.frame, [])),
        )
        attempts.append(attempt)
        next_release = next(
            (item for item in distinct[index + 1 :]), None
        )
        window_end = next_release.seconds if next_release else duration_seconds
        window_end_frame = next_release.frame if next_release else None

        def within(frame: int) -> bool:
            return frame > release.frame and (
                window_end_frame is None or frame <= window_end_frame
            )

        if release.intent == "ambiguous":
            attempt.reason = "ambiguous_intent"
            continue
        if release.team is None:
            attempt.reason = "unknown_attacking_team"
            continue
        release_state = state_at(release.seconds)
        if release_state == "unknown":
            attempt.reason = "match_state_unknown"
            continue
        if release_state != "in_play":
            attempt.resolution = "excluded"
            attempt.reason = "release_not_in_play"
            continue
        if target is None:
            attempt.reason = "attacking_direction_unknown"
            continue
        geometry = evidence.goals[target]
        goal = next(
            (
                fact
                for fact in evidence.goal_facts
                if within(fact.frame)
                and fact.goal_side == target
            ),
            None,
        )
        contact = next(
            (item for item in evidence.contacts if within(item.frame)), None
        )
        if goal is not None:
            if not goal.valid or not goal.evidence or goal.team not in {
                release.team,
                None,
            }:
                attempt.reason = "unsupported_goal_claim"
                continue
            if _stoppage_before(match_state, release.seconds, goal.seconds):
                attempt.reason = "play_stopped_before_outcome"
                continue
            attempt.resolution = "on_target"
            attempt.reason = "valid_goal"
            attempt.goal = goal
            attempt.outcome_frame = goal.frame
            attempt.outcome_seconds = goal.seconds
            continue
        flight = [
            sample
            for sample in evidence.trajectory
            if sample.observed
            and sample.frame >= release.frame
            and (contact is None or sample.frame <= contact.frame)
            and (window_end_frame is None or sample.frame <= window_end_frame)
        ]
        if contact is not None:
            attempt.contact = contact
            attempt.outcome_frame = contact.frame
            attempt.outcome_seconds = contact.seconds
            if _stoppage_before(match_state, release.seconds, contact.seconds):
                attempt.reason = "play_stopped_before_outcome"
                continue
            if contact.kind == "unknown":
                attempt.reason = "contact_role_unknown"
                continue
            if contact.kind == "woodwork":
                attempt.resolution = "off_target"
                attempt.reason = "woodwork_out"
                continue
            if contact.kind == "outfield":
                attempt.resolution = "blocked"
                attempt.reason = "ordinary_block"
                continue
            if contact.team == release.team:
                attempt.reason = "contact_team_conflict"
                continue
            projected = _projected_frame_position(flight, geometry)
            if projected == "insufficient":
                arrival = _face_arrival_near(evidence, target, within, contact.seconds)
                if arrival is not None:
                    projected = geometry.classify(arrival.y, arrival.z)
            if projected == "insufficient":
                attempt.reason = "insufficient_observed_motion"
            elif projected == "inside":
                attempt.resolution = "on_target"
                attempt.reason = (
                    "goalkeeper_save"
                    if contact.kind == "goalkeeper"
                    else "last_line_defender_save"
                )
            elif projected == "outside":
                attempt.resolution = "off_target"
                attempt.reason = "pre_contact_path_off_target"
            else:
                attempt.reason = "goal_frame_ambiguous"
            continue
        arrival = next(
            (
                item
                for item in evidence.face_arrivals
                if item.goal_side == target and within(item.frame)
            ),
            None,
        )
        if len(flight) < MINIMUM_OBSERVED_SAMPLES and arrival is not None:
            _resolve_face_arrival(
                attempt, arrival, geometry, match_state, duration_seconds
            )
            continue
        if len(flight) < MINIMUM_OBSERVED_SAMPLES:
            attempt.reason = "insufficient_observed_motion"
            continue
        crossing = _goal_line_crossing(flight, geometry)
        if crossing is None:
            attempt.reason = (
                "flight_truncated" if next_release is None
                else "outcome_not_observed"
            )
            continue
        sample, y, z = crossing
        attempt.outcome_frame = sample.frame
        attempt.outcome_seconds = sample.seconds
        position = geometry.classify(y, z)
        if position == "outside":
            attempt.resolution = "off_target"
            attempt.reason = "wide_or_high"
        elif position == "inside":
            attempt.reason = "goal_entry_without_goal_confirmation"
        else:
            attempt.reason = "goal_frame_ambiguous"
    return attempts


def attempt_event(attempt: Attempt) -> dict[str, Any]:
    confidence = {"valid_goal": 0.9, "stopped_at_goal_face": 0.65}.get(
        attempt.reason, 0.8
    )
    return {
        "event_type": EVENT_TYPE,
        "clip_seconds": round(attempt.release.seconds, 3),
        "team": attempt.team,
        "from_player_track_id": attempt.release.player_track_id,
        "to_player_track_id": (
            attempt.contact.player_track_id if attempt.contact else None
        ),
        "confidence": confidence,
        "details": (
            f"Shot on target ({attempt.reason.replace('_', ' ')}) toward the "
            f"{attempt.target_goal} goal."
        ),
        "completion_seconds": round(float(attempt.outcome_seconds), 3),
        "attempt_id": attempt.attempt_id,
        "shot_outcome": {
            "definition_version": DEFINITION_VERSION,
            "reason": attempt.reason,
            "release_frame": attempt.release.frame,
            "outcome_frame": attempt.outcome_frame,
            "target_goal": attempt.target_goal,
            "linked_goal_frame": attempt.goal.frame if attempt.goal else None,
        },
    }


def _fingerprint(payload: Any) -> str | None:
    if payload is None:
        return None
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def disabled_summary() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "definition_version": DEFINITION_VERSION,
        "enabled": False,
        "analysis_status": "disabled",
        "readiness": None,
        "counts": None,
        "total": None,
        "unresolved_attempt_count": None,
        "unresolved_reasons": {},
        "attempts": [],
    }


def summarize(
    attempts: Iterable[Attempt] | None,
    *,
    readiness_result: Readiness,
    teams: Iterable[str] = (),
    evidence_fingerprint: str | None = None,
    configuration_fingerprint: str | None = None,
) -> dict[str, Any]:
    base = {
        "schema_version": SCHEMA_VERSION,
        "definition_version": DEFINITION_VERSION,
        "enabled": True,
        "readiness": readiness_result.to_dict(),
        "evidence_fingerprint": evidence_fingerprint,
        "configuration_fingerprint": configuration_fingerprint,
    }
    if attempts is None or readiness_result.status != "ready":
        return {
            **base,
            "analysis_status": "unavailable",
            "counts": None,
            "total": None,
            "unresolved_attempt_count": None,
            "unresolved_reasons": {
                reason: 1 for reason in readiness_result.reasons
            },
            "attempts": [],
        }
    ordered = sorted(attempts, key=lambda attempt: attempt.attempt_id)
    seen: set[str] = set()
    counts = {team: 0 for team in teams}
    unresolved: dict[str, int] = {}
    for attempt in ordered:
        if attempt.attempt_id in seen:
            continue
        seen.add(attempt.attempt_id)
        if attempt.resolution == "on_target" and attempt.team in counts:
            counts[attempt.team] += 1
        elif attempt.resolution == "unresolved":
            unresolved[attempt.reason] = unresolved.get(attempt.reason, 0) + 1
    unresolved_count = sum(unresolved.values())
    return {
        **base,
        "analysis_status": "partial" if unresolved_count else "complete",
        "counts": counts,
        "total": sum(counts.values()),
        "unresolved_attempt_count": unresolved_count,
        "unresolved_reasons": dict(sorted(unresolved.items())),
        "attempts": [attempt.to_dict() for attempt in ordered],
    }


def load_setting(path: Path) -> bool:
    """Read the opt-in setting. Missing means disabled; malformed raises."""
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ShotEvidenceError(f"Malformed {path.name}: {error}") from error
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != SCHEMA_VERSION
        or not isinstance(payload.get("enabled"), bool)
    ):
        raise ShotEvidenceError(
            f"{path.name} must contain schema_version 1 and a boolean 'enabled'"
        )
    return payload["enabled"]


def _load_evidence(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ShotEvidenceError(f"Malformed {path.name}: {error}") from error


def apply_shots_on_target(
    output: Path,
    evidence_path: Path | None,
    *,
    duration_seconds: float,
) -> dict[str, Any]:
    """Append resolved SOT events to cached engine output and write a summary.

    Pass/turnover rows are left byte-for-byte in their existing order; SOT rows
    are merged by release time using a stable sort.
    """
    payload = _load_evidence(evidence_path)
    result = readiness(payload)
    events_path = output / "predicted-events.json"
    configuration_fingerprint = _fingerprint(
        {"definition_version": DEFINITION_VERSION, "enabled": True}
    )
    if result.status != "ready":
        summary = summarize(
            None,
            readiness_result=result,
            configuration_fingerprint=configuration_fingerprint,
        )
    else:
        evidence = parse_evidence(payload)
        match_state = json.loads(
            (output / "match-state-events.json").read_text(encoding="utf-8")
        )
        attempts = classify_attempts(
            evidence, match_state, duration_seconds=duration_seconds
        )
        summary = summarize(
            attempts,
            readiness_result=result,
            teams=evidence.teams,
            evidence_fingerprint=_fingerprint(payload),
            configuration_fingerprint=configuration_fingerprint,
        )
        events = json.loads(events_path.read_text(encoding="utf-8"))
        events = [
            event for event in events if event.get("event_type") != EVENT_TYPE
        ]
        events.extend(
            attempt_event(attempt)
            for attempt in attempts
            if attempt.resolution == "on_target"
        )
        events.sort(key=lambda event: float(event["clip_seconds"]))
        events_path.write_text(json.dumps(events, indent=2), encoding="utf-8")
    (output / SUMMARY_FILE_NAME).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Check Innovation shots-on-target evidence readiness."
    )
    parser.add_argument("command", choices=["readiness"])
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        result = readiness(_load_evidence(args.evidence)).to_dict()
    except ShotEvidenceError as error:
        result = {"status": "invalid", "reasons": [str(error)]}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
