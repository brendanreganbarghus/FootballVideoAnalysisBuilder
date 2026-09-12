from __future__ import annotations

from dataclasses import asdict, dataclass
from math import dist
from statistics import median
from typing import Iterable

import cv2
import numpy as np


@dataclass(frozen=True)
class TrackInitializationEvidence:
    track_id: int
    color_bgr: tuple[int, int, int]
    sample_count: int
    start_seconds: float
    end_seconds: float
    normalized_positions: tuple[tuple[float, float], ...]

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)


@dataclass(frozen=True)
class TeamCluster:
    team: str
    color_bgr: tuple[int, int, int]
    track_ids: tuple[int, ...]
    confidence: float


@dataclass(frozen=True)
class GoalkeeperInitialization:
    track_id: int
    team: str | None
    defends_goal: str
    confidence: float
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class TeamDirection:
    team: str
    defends_goal: str
    attacks_towards: str
    confidence: float


@dataclass(frozen=True)
class MatchInitialization:
    half: int | None
    source_start_seconds: float
    starts_at_kickoff: bool
    status: str
    teams: tuple[TeamCluster, ...]
    official_track_ids: tuple[int, ...]
    goalkeepers: tuple[GoalkeeperInitialization, ...]
    directions: tuple[TeamDirection, ...]
    abstention_reasons: tuple[str, ...]
    side_switch_detected: bool | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def infer_match_initialization(
    evidence: Iterable[TrackInitializationEvidence],
    *,
    half: int | None,
    source_start_seconds: float,
    starts_at_kickoff: bool,
) -> MatchInitialization:
    tracks = tuple(evidence)
    reasons: list[str] = []
    teams = infer_team_clusters(tracks)
    if len(teams) != 2:
        reasons.append("two_outfield_kit_clusters_not_confident")
        return MatchInitialization(
            half=half,
            source_start_seconds=source_start_seconds,
            starts_at_kickoff=starts_at_kickoff,
            status="abstained",
            teams=teams,
            official_track_ids=(),
            goalkeepers=(),
            directions=(),
            abstention_reasons=tuple(reasons),
        )

    assignments = {
        track_id: team.team
        for team in teams
        for track_id in team.track_ids
    }
    goalkeepers = infer_goalkeepers(tracks, teams, assignments)
    goalkeeper_ids = {candidate.track_id for candidate in goalkeepers}
    officials = tuple(
        sorted(
            track.track_id
            for track in tracks
            if track.track_id not in assignments
            and track.track_id not in goalkeeper_ids
            and track.duration_seconds >= 4.0
            and _central_occupancy(track) >= 0.55
        )
    )

    directions: tuple[TeamDirection, ...] = ()
    if not starts_at_kickoff:
        reasons.append("segment_does_not_begin_at_kickoff")
    elif len(goalkeepers) < 2 or any(
        goalkeeper.team is None for goalkeeper in goalkeepers
    ):
        reasons.append("both_goalkeepers_not_confidently_affiliated")
    else:
        directions = tuple(
            TeamDirection(
                team=str(goalkeeper.team),
                defends_goal=goalkeeper.defends_goal,
                attacks_towards=(
                    "right" if goalkeeper.defends_goal == "left" else "left"
                ),
                confidence=goalkeeper.confidence,
            )
            for goalkeeper in sorted(
                goalkeepers, key=lambda candidate: str(candidate.team)
            )
        )

    return MatchInitialization(
        half=half,
        source_start_seconds=source_start_seconds,
        starts_at_kickoff=starts_at_kickoff,
        status="complete" if directions else "partial",
        teams=teams,
        official_track_ids=officials,
        goalkeepers=goalkeepers,
        directions=directions,
        abstention_reasons=tuple(reasons),
    )


def detect_halftime_side_switch(
    first_half: MatchInitialization,
    second_half: MatchInitialization,
) -> bool | None:
    first = {direction.team: direction.defends_goal for direction in first_half.directions}
    second = {
        direction.team: direction.defends_goal for direction in second_half.directions
    }
    if len(first) != 2 or set(first) != set(second):
        return None
    return all(first[team] != second[team] for team in first)


def infer_team_clusters(
    evidence: Iterable[TrackInitializationEvidence],
) -> tuple[TeamCluster, ...]:
    candidates = [
        track
        for track in evidence
        if track.sample_count >= 3 and track.duration_seconds >= 1.5
    ]
    if len(candidates) < 4:
        return ()
    lab = {
        track.track_id: _bgr_to_lab(track.color_bgr) for track in candidates
    }
    best: tuple[float, list[TrackInitializationEvidence], list[TrackInitializationEvidence]] | None = None
    for first_index, first in enumerate(candidates):
        for second in candidates[first_index + 1 :]:
            first_center = lab[first.track_id]
            second_center = lab[second.track_id]
            separation = dist(first_center, second_center)
            if separation < 18:
                continue
            left: list[TrackInitializationEvidence] = []
            right: list[TrackInitializationEvidence] = []
            for candidate in candidates:
                target = lab[candidate.track_id]
                (
                    left
                    if dist(target, first_center) <= dist(target, second_center)
                    else right
                ).append(candidate)
            if len(left) < 2 or len(right) < 2:
                continue
            left_center = _weighted_lab_center(left, lab)
            right_center = _weighted_lab_center(right, lab)
            within = (
                sum(dist(lab[item.track_id], left_center) for item in left)
                + sum(dist(lab[item.track_id], right_center) for item in right)
            ) / len(candidates)
            balance = min(len(left), len(right)) / max(len(left), len(right))
            score = dist(left_center, right_center) * balance / (1.0 + within)
            if best is None or score > best[0]:
                best = (score, left, right)
    if best is None:
        return ()

    _, first_group, second_group = best
    groups = [first_group, second_group]
    initial_centers = [
        _weighted_lab_center(group, lab) for group in groups
    ]
    trimmed_groups: list[list[TrackInitializationEvidence]] = []
    for group, center in zip(groups, initial_centers, strict=True):
        distances = [dist(lab[item.track_id], center) for item in group]
        threshold = max(18.0, min(55.0, median(distances) * 2.5))
        trimmed_groups.append(
            [
                item
                for item in group
                if dist(lab[item.track_id], center) <= threshold
            ]
        )
    if any(len(group) < 2 for group in trimmed_groups):
        return ()
    groups = trimmed_groups
    centers = [_weighted_bgr_center(group) for group in groups]
    lab_centers = [_bgr_to_lab(center) for center in centers]
    separation = dist(lab_centers[0], lab_centers[1])
    within = median(
        dist(lab[item.track_id], lab_centers[index])
        for index, group in enumerate(groups)
        for item in group
    )
    balance = min(len(group) for group in groups) / max(len(group) for group in groups)
    confidence = round(
        max(0.0, min(1.0, (separation / (separation + within + 1e-6)) * balance)),
        3,
    )
    if confidence < 0.42:
        return ()

    labels = [_color_name(center) for center in centers]
    if labels[0] == labels[1]:
        labels = ["team_a", "team_b"]
    ordered = sorted(
        zip(labels, centers, groups, strict=True),
        key=lambda item: item[0],
    )
    return tuple(
        TeamCluster(
            team=label,
            color_bgr=center,
            track_ids=tuple(sorted(track.track_id for track in group)),
            confidence=confidence,
        )
        for label, center, group in ordered
    )


def infer_goalkeepers(
    evidence: Iterable[TrackInitializationEvidence],
    teams: tuple[TeamCluster, ...],
    assignments: dict[int, str],
) -> tuple[GoalkeeperInitialization, ...]:
    team_centers = {
        team.team: _bgr_to_lab(team.color_bgr) for team in teams
    }
    tracks = tuple(evidence)
    team_side = _team_opening_sides(tracks, assignments)
    candidates: list[tuple[float, TrackInitializationEvidence, str]] = []
    for track in tracks:
        if track.track_id in assignments or track.duration_seconds < 6.0:
            continue
        side, occupancy = _goal_side_occupancy(track)
        if side is None or occupancy < 0.6:
            continue
        color = _bgr_to_lab(track.color_bgr)
        color_distance = min(dist(color, center) for center in team_centers.values())
        if color_distance < 24:
            continue
        x_positions = [position[0] for position in track.normalized_positions]
        movement_span = max(x_positions) - min(x_positions) if x_positions else 1.0
        position_score = occupancy * max(0.0, 1.0 - movement_span / 0.35)
        appearance_score = min(1.0, color_distance / 70.0)
        confidence = 0.55 * position_score + 0.45 * appearance_score
        candidates.append((confidence, track, side))

    selected: list[GoalkeeperInitialization] = []
    for side in ("left", "right"):
        side_candidates = [item for item in candidates if item[2] == side]
        if not side_candidates:
            continue
        confidence, track, _ = max(side_candidates, key=lambda item: item[0])
        if confidence < 0.58:
            continue
        selected.append(
            GoalkeeperInitialization(
                track_id=track.track_id,
                team=team_side.get(side),
                defends_goal=side,
                confidence=round(confidence, 3),
                evidence=(
                    "distinct_from_outfield_clusters",
                    "sustained_goal_side_position",
                    "limited_goal_side_movement",
                ),
            )
        )
    return tuple(selected)


def _team_opening_sides(
    evidence: tuple[TrackInitializationEvidence, ...],
    assignments: dict[int, str],
) -> dict[str, str]:
    positions: dict[str, list[float]] = {}
    for track in evidence:
        team = assignments.get(track.track_id)
        if team is None:
            continue
        if track.normalized_positions:
            positions.setdefault(team, []).extend(
                x for x, _ in track.normalized_positions
            )
    if len(positions) != 2:
        return {}
    medians = sorted(
        ((median(values), team) for team, values in positions.items()),
        key=lambda item: item[0],
    )
    if medians[1][0] - medians[0][0] < 0.08:
        return {}
    return {"left": medians[0][1], "right": medians[1][1]}


def _goal_side_occupancy(
    track: TrackInitializationEvidence,
) -> tuple[str | None, float]:
    if not track.normalized_positions:
        return None, 0.0
    left = sum(x <= 0.24 for x, _ in track.normalized_positions)
    right = sum(x >= 0.76 for x, _ in track.normalized_positions)
    count = len(track.normalized_positions)
    if left >= right and left:
        return "left", left / count
    if right:
        return "right", right / count
    return None, 0.0


def _central_occupancy(track: TrackInitializationEvidence) -> float:
    if not track.normalized_positions:
        return 0.0
    return sum(
        0.2 < x < 0.8 and 0.15 < y < 0.9
        for x, y in track.normalized_positions
    ) / len(track.normalized_positions)


def _weighted_lab_center(
    tracks: list[TrackInitializationEvidence],
    colors: dict[int, tuple[float, float, float]],
) -> tuple[float, float, float]:
    weights = np.asarray(
        [min(20.0, max(1.0, track.duration_seconds)) for track in tracks],
        dtype=np.float64,
    )
    values = np.asarray([colors[track.track_id] for track in tracks], dtype=np.float64)
    center = np.average(values, axis=0, weights=weights)
    return tuple(float(value) for value in center)


def _weighted_bgr_center(
    tracks: list[TrackInitializationEvidence],
) -> tuple[int, int, int]:
    weights = np.asarray(
        [min(20.0, max(1.0, track.duration_seconds)) for track in tracks],
        dtype=np.float64,
    )
    values = np.asarray([track.color_bgr for track in tracks], dtype=np.float64)
    center = np.average(values, axis=0, weights=weights)
    return tuple(int(round(value)) for value in center)


def _bgr_to_lab(color: tuple[int, int, int]) -> tuple[float, float, float]:
    pixel = np.asarray([[color]], dtype=np.uint8)
    converted = cv2.cvtColor(pixel, cv2.COLOR_BGR2LAB)[0, 0]
    return tuple(float(channel) for channel in converted)


def _color_name(color: tuple[int, int, int]) -> str:
    palette = {
        "black": (25, 25, 25),
        "blue": (170, 70, 25),
        "green": (45, 140, 45),
        "red": (35, 35, 190),
        "white": (220, 220, 220),
        "yellow": (40, 210, 220),
    }
    color_lab = _bgr_to_lab(color)
    return min(
        palette,
        key=lambda name: dist(color_lab, _bgr_to_lab(palette[name])),
    )
