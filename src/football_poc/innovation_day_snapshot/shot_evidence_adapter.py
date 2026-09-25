"""Build Innovation runtime shot evidence from cached runtime artifacts only.

Inputs are the frozen Innovation ball track, cached player tracks (with their
runtime goalkeeper roles), the engine's match-state timeline, and the
camera-specific goal-face calibration. Manual labels, M#/C#, provider events,
and reviewer outcomes are never read.

The camera is monocular, so ball height is not observed in flight. The only
height evidence is a *goal-face arrest*: the ball arrives at speed, stops in
the calibrated goal-face zone, and its arrested image position is projected
onto the goal plane. Flight samples are emitted without height.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable

import numpy as np

from football_poc.innovation_day_snapshot.goal_calibration import (
    GoalFace,
    load_goal_faces,
)
from football_poc.innovation_day_snapshot.shots_on_target import (
    EVIDENCE_FILE_NAME,
    EVIDENCE_SOURCE_KIND,
    SCHEMA_VERSION,
    readiness,
)


ADAPTER_VERSION = "innovation-shot-evidence-v1"
TEAMS = ("red", "black")
FACE_ZONE_PX = 40.0
MIN_APPROACH_SPEED_PX_S = 400.0
APPROACH_WINDOW_S = 1.0
ARREST_SPEED_RATIO = 0.35
ARREST_WINDOW_S = 0.6
RELEASE_LOOKBACK_S = 3.0
MIN_RELEASE_LEAD_S = 0.4
RELEASE_RADIUS_HEIGHTS = 0.6
CONTACT_RADIUS_HEIGHTS = 0.8
CONTACT_WINDOW_S = 0.4


@dataclass(frozen=True)
class BallSample:
    frame: int
    seconds: float
    x: float
    y: float


@dataclass(frozen=True)
class PlayerPoint:
    track_id: int
    team: str | None
    role: str
    foot: tuple[float, float]
    height: float


def _team(value: Any) -> str | None:
    return value if value in TEAMS else None


def load_ball(ball_tracks: dict[str, Any]) -> list[BallSample]:
    points = []
    for track in ball_tracks.get("tracks", []):
        for point in track.get("points", []):
            if point.get("x") is None or point.get("y") is None:
                continue
            points.append(
                BallSample(
                    int(point["source_frame"]),
                    float(point["clip_seconds"]),
                    float(point["x"]),
                    float(point["y"]),
                )
            )
    unique = {sample.frame: sample for sample in points}
    return [unique[frame] for frame in sorted(unique)]


def load_players(player_tracks: dict[str, Any]) -> dict[int, list[PlayerPoint]]:
    by_frame: dict[int, list[PlayerPoint]] = {}
    for track in player_tracks.get("tracks", []):
        track_team = _team(track.get("team"))
        track_role = str(track.get("role") or "player")
        for point in track.get("points", []):
            height = float(point["y2"]) - float(point["y1"])
            if height <= 0:
                continue
            by_frame.setdefault(int(point["source_frame"]), []).append(
                PlayerPoint(
                    int(track["track_id"]),
                    _team(point.get("team")) or track_team,
                    str(point.get("role") or track_role),
                    ((float(point["x1"]) + float(point["x2"])) / 2, float(point["y2"])),
                    height,
                )
            )
    return by_frame


def attacking_goals(affiliations: dict[str, Any]) -> dict[str, str]:
    """Derive attacking direction from the static goalkeeper-role config."""
    defended: dict[str, str] = {}
    for item in affiliations.get("affiliations", []):
        team, goal = _team(item.get("team")), item.get("goal")
        if team and goal in {"left", "right"}:
            defended[team] = goal
    attacking: dict[str, str] = {}
    for team, goal in defended.items():
        attacking[team] = "right" if goal == "left" else "left"
        other = next(candidate for candidate in TEAMS if candidate != team)
        attacking.setdefault(other, goal)
    if len(set(attacking.values())) != len(attacking):
        return {}
    return attacking


def _speed(a: BallSample, b: BallSample) -> float:
    dt = b.seconds - a.seconds
    return 0.0 if dt <= 0 else float(np.hypot(b.x - a.x, b.y - a.y)) / dt


def _nearest(
    players: Iterable[PlayerPoint], ball: BallSample, radius_heights: float
) -> tuple[float, PlayerPoint] | None:
    best = None
    for player in players:
        distance = float(np.hypot(player.foot[0] - ball.x, player.foot[1] - ball.y))
        if distance <= radius_heights * player.height and (
            best is None or distance < best[0]
        ):
            best = (distance, player)
    return best


def find_arrests(ball: list[BallSample], face: GoalFace) -> list[int]:
    """Indices where a fast approach is arrested inside the goal-face zone."""
    arrests: list[int] = []
    index = 1
    while index < len(ball) - 1:
        sample = ball[index]
        if face.image_distance((sample.x, sample.y)) > FACE_ZONE_PX:
            index += 1
            continue
        approach = [
            _speed(a, b)
            for a, b in zip(ball[:index], ball[1 : index + 1])
            if sample.seconds - APPROACH_WINDOW_S <= b.seconds <= sample.seconds
        ]
        after = [
            candidate
            for candidate in ball[index + 1 :]
            if candidate.seconds <= sample.seconds + ARREST_WINDOW_S
        ]
        peak = max(approach, default=0.0)
        arrested = (
            peak >= MIN_APPROACH_SPEED_PX_S
            and len(after) >= 2
            and all(
                face.image_distance((item.x, item.y)) <= FACE_ZONE_PX
                for item in after
            )
            and max(
                _speed(a, b) for a, b in zip([sample, *after], after)
            ) <= ARREST_SPEED_RATIO * peak
        )
        if arrested:
            arrests.append(index)
            while (
                index < len(ball)
                and face.image_distance((ball[index].x, ball[index].y)) <= FACE_ZONE_PX
            ):
                index += 1
            continue
        index += 1
    return arrests


def build_evidence(
    *,
    ball_tracks: dict[str, Any],
    player_tracks: dict[str, Any],
    affiliations: dict[str, Any],
    faces: dict[str, GoalFace],
    calibration_provenance: dict[str, Any],
    match_state: dict[str, Any] | None = None,
    fps: float = 25.0,
) -> dict[str, Any]:
    ball = load_ball(ball_tracks)
    players = load_players(player_tracks)
    attacking = attacking_goals(affiliations)
    releases: list[dict[str, Any]] = []
    contacts: list[dict[str, Any]] = []
    arrivals: list[dict[str, Any]] = []
    for side, face in faces.items():
        for index in find_arrests(ball, face):
            arrest = ball[index]
            window = [
                item
                for item in ball[index : index + 4]
                if item.seconds <= arrest.seconds + ARREST_WINDOW_S
            ]
            y, z = face.project(
                (median(item.x for item in window), median(item.y for item in window))
            )
            release = None
            for back in range(index - 1, -1, -1):
                candidate = ball[back]
                if candidate.seconds < arrest.seconds - RELEASE_LOOKBACK_S:
                    break
                if arrest.seconds - candidate.seconds < MIN_RELEASE_LEAD_S:
                    continue
                touch = _nearest(
                    players.get(candidate.frame, []), candidate, RELEASE_RADIUS_HEIGHTS
                )
                if touch is not None:
                    release = (candidate, touch[1])
                    break
            if release is None:
                continue
            sample, kicker = release
            path = ball[ball.index(sample) : index + 1]
            distances = [
                float(np.hypot(item.x - arrest.x, item.y - arrest.y))
                for item in path
            ]
            direct = all(b <= a + 5.0 for a, b in zip(distances, distances[1:]))
            if kicker.team is None:
                intent = "ambiguous"
            elif attacking.get(kicker.team) == side and direct:
                intent = "scoring_attempt"
            elif attacking.get(kicker.team) == side:
                intent = "ambiguous"
            else:
                intent = "clearance"
            releases.append(
                {
                    "frame": sample.frame,
                    "seconds": sample.seconds,
                    "team": kicker.team,
                    "player_track_id": kicker.track_id,
                    "intent": intent,
                    "continuation_of": None,
                    "evidence": "player_foot_contact_then_direct_goal_face_approach",
                }
            )
            contact = None
            for item in ball[max(index - 1, 0) :]:
                if item.seconds > arrest.seconds + CONTACT_WINDOW_S:
                    break
                touch = _nearest(
                    players.get(item.frame, []), item, CONTACT_RADIUS_HEIGHTS
                )
                if touch is None or touch[1].team == kicker.team:
                    continue
                contact = (item, touch[1])
                break
            if contact is not None:
                item, player = contact
                contacts.append(
                    {
                        "frame": item.frame,
                        "seconds": item.seconds,
                        "kind": (
                            "goalkeeper"
                            if player.role == "goalkeeper"
                            else "last_line_defender"
                        ),
                        "team": player.team,
                        "player_track_id": player.track_id,
                    }
                )
            arrivals.append(
                {
                    "frame": arrest.frame,
                    "seconds": arrest.seconds,
                    "goal_side": side,
                    "y": round(y, 3),
                    "z": round(z, 3),
                    "arrested": True,
                    "method": "monocular_goal_face_arrest",
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "source_kind": EVIDENCE_SOURCE_KIND,
        "adapter_version": ADAPTER_VERSION,
        "calibration": {
            "teams": list(TEAMS),
            "goals": {side: face.to_contract() for side, face in faces.items()},
            "attacking_goal": attacking,
            "provenance": calibration_provenance,
        },
        "ball_trajectory": [
            {
                "frame": item.frame,
                "seconds": item.seconds,
                "x": item.x,
                "y": item.y,
                "z": None,
                "observed": True,
                "coordinate_space": "image_px",
            }
            for item in ball
        ],
        "releases": sorted(releases, key=lambda item: item["frame"]),
        "contacts": sorted(contacts, key=lambda item: item["frame"]),
        "goal_face_arrivals": sorted(arrivals, key=lambda item: item["frame"]),
        "goals": goal_facts_from_match_state(match_state or {}, ball, faces, fps),
    }


def goal_facts_from_match_state(
    match_state: dict[str, Any],
    ball: list[BallSample],
    faces: dict[str, GoalFace],
    fps: float,
) -> list[dict[str, Any]]:
    """Valid goals are the engine's own goal -> kick-off transitions."""
    facts = []
    for transition in match_state.get("transitions", []):
        if transition.get("trigger") != "goal_requires_kick_off" or not ball:
            continue
        seconds = float(transition["clip_seconds"])
        sample = min(ball, key=lambda item: abs(item.seconds - seconds))
        side = min(
            faces, key=lambda name: faces[name].image_distance((sample.x, sample.y))
        )
        facts.append(
            {
                "frame": int(round(seconds * fps)),
                "seconds": seconds,
                "team": None,
                "goal_side": side,
                "valid": True,
                "evidence": "match_state:goal_requires_kick_off",
            }
        )
    return facts


def write_evidence(
    output: Path,
    *,
    ball_tracks: Path,
    player_tracks: Path,
    goal_calibration: Path,
    goalkeeper_affiliations: Path,
    match_state: Path | None = None,
    fps: float = 25.0,
) -> dict[str, Any]:
    faces, provenance = load_goal_faces(goal_calibration)
    evidence = build_evidence(
        ball_tracks=json.loads(ball_tracks.read_text(encoding="utf-8")),
        player_tracks=json.loads(player_tracks.read_text(encoding="utf-8")),
        affiliations=json.loads(goalkeeper_affiliations.read_text(encoding="utf-8")),
        faces=faces,
        calibration_provenance=provenance,
        match_state=(
            json.loads(match_state.read_text(encoding="utf-8"))
            if match_state is not None and match_state.is_file()
            else None
        ),
        fps=fps,
    )
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


def discover_artifact_root() -> Path | None:
    """Same lookup as the shared artifact store, kept local to the frozen engine."""
    configured = os.environ.get("FOOTBALL_ARTIFACT_ROOT", "").strip()
    if configured:
        root = Path(configured).expanduser().resolve()
        return root if root.is_dir() else None
    one_drive = (
        os.environ.get("ONEDRIVECOMMERCIAL") or os.environ.get("ONEDRIVE") or ""
    ).strip()
    if one_drive:
        candidate = Path(one_drive) / "Innovationday Artifacts"
        if candidate.is_dir():
            return candidate.resolve()
    synced = [
        path
        for path in sorted(Path.home().glob("*/* - Innovationday Artifacts"))
        if path.is_dir()
    ]
    return synced[0].resolve() if len(synced) == 1 else None


def resolve_alfheim_config(name: str, project_root: Path) -> Path:
    """Find a static Alfheim camera config locally or in the artifact store."""
    local_path = project_root / "benchmarks" / "alfheim" / "window-555" / name
    if local_path.is_file():
        return local_path
    artifact_root = discover_artifact_root()
    if artifact_root is not None:
        candidates = sorted(
            (artifact_root / "30-shared-baselines").glob(f"*/alfheim-config/{name}")
        )
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise FileNotFoundError(
                f"Multiple shared {name} configurations found; select one explicitly."
            )
    raise FileNotFoundError(
        f"Alfheim configuration {name} was not found locally or in the "
        "shared artifact store."
    )


def build_for_segment(innovation_root: Path, project_root: Path) -> Path:
    """Rebuild <innovation>/shot-evidence.json from cached runtime artifacts."""
    output = innovation_root / EVIDENCE_FILE_NAME
    write_evidence(
        output,
        ball_tracks=innovation_root / "analytics-cache" / "ball-tracks.json",
        player_tracks=innovation_root / "analytics-data" / "player-tracks.json",
        goal_calibration=resolve_alfheim_config("pitch-calibration.json", project_root),
        goalkeeper_affiliations=resolve_alfheim_config(
            "goalkeeper-affiliations.json", project_root
        ),
        match_state=innovation_root / "analytics-data" / "match-state-events.json",
    )
    return output


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--segment-innovation-root",
        type=Path,
        help="Build evidence for a prepared segment and print its readiness.",
    )
    parser.add_argument("--ball-tracks", type=Path)
    parser.add_argument("--player-tracks", type=Path)
    parser.add_argument("--goal-calibration", type=Path)
    parser.add_argument("--goalkeeper-affiliations", type=Path)
    parser.add_argument("--match-state", type=Path)
    parser.add_argument("--fps", type=float, default=25.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.segment_innovation_root is not None:
        try:
            path = build_for_segment(
                args.segment_innovation_root, Path(__file__).resolve().parents[3]
            )
            result = readiness(json.loads(path.read_text(encoding="utf-8")))
            print(json.dumps(result.to_dict()))
        except (FileNotFoundError, ValueError) as error:
            print(json.dumps({"status": "unavailable", "reasons": [str(error)]}))
        return
    missing = [
        name
        for name in (
            "ball_tracks",
            "player_tracks",
            "goal_calibration",
            "goalkeeper_affiliations",
            "output",
        )
        if getattr(args, name) is None
    ]
    if missing:
        parser.error("missing required arguments: " + ", ".join(missing))
    evidence = write_evidence(
        args.output,
        ball_tracks=args.ball_tracks,
        player_tracks=args.player_tracks,
        goal_calibration=args.goal_calibration,
        goalkeeper_affiliations=args.goalkeeper_affiliations,
        match_state=args.match_state,
        fps=args.fps,
    )
    print(
        json.dumps(
            {
                "releases": len(evidence["releases"]),
                "goal_face_arrivals": len(evidence["goal_face_arrivals"]),
                "contacts": len(evidence["contacts"]),
            }
        )
    )


if __name__ == "__main__":
    main()
