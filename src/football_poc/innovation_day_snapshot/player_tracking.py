from __future__ import annotations

import json
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from math import hypot
from pathlib import Path
from statistics import median
from typing import Any, Iterable

import cv2
import numpy as np

from football_poc.innovation_day_snapshot.benchmark import BenchmarkManifest
from football_poc.innovation_day_snapshot.match_initialization import (
    MatchInitialization,
    TrackInitializationEvidence,
    infer_match_initialization,
)
from football_poc.innovation_day_snapshot.team_colors import (
    assign_color_group,
    dominant_jersey_color,
)


@dataclass
class PlayerPoint:
    source_frame: int
    clip_seconds: float
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    team: str = "unknown"
    color_scores: dict[str, float] | None = None

    @property
    def foot(self) -> tuple[float, float]:
        return (self.x1 + self.x2) / 2, self.y2

    @property
    def height(self) -> float:
        return max(1.0, self.y2 - self.y1)


@dataclass
class PlayerTrack:
    track_id: int
    points: list[PlayerPoint]
    team: str = "unknown"
    color_scores: dict[str, float] | None = None
    role: str = "player"

    @property
    def last(self) -> PlayerPoint:
        return self.points[-1]

    def predicted_foot(self, clip_seconds: float) -> tuple[float, float]:
        current_x, current_y = self.last.foot
        if len(self.points) < 2:
            return current_x, current_y
        previous = self.points[-2]
        previous_x, previous_y = previous.foot
        elapsed = self.last.clip_seconds - previous.clip_seconds
        if elapsed <= 0:
            return current_x, current_y
        future = clip_seconds - self.last.clip_seconds
        return (
            current_x + (current_x - previous_x) / elapsed * future,
            current_y + (current_y - previous_y) / elapsed * future,
        )


def track_cached_players(
    *,
    manifest_path: Path,
    player_cache_path: Path,
    ball_tracks_path: Path,
    output: Path,
    confidence: float = 0.3,
    max_gap_seconds: float = 0.4,
    max_speed_pixels_per_second: float = 500.0,
    minimum_track_points: int = 8,
    render_video: bool = True,
    team_profile: str = "auto",
    goalkeeper_affiliations_path: Path | None = None,
    team_color_references_path: Path | None = None,
) -> Path:
    manifest = BenchmarkManifest.load(manifest_path)
    metadata, records = _load_player_cache(
        player_cache_path, manifest.sha256
    )
    _validate_options(
        confidence=confidence,
        max_gap_seconds=max_gap_seconds,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        minimum_track_points=minimum_track_points,
    )
    width, height = _video_dimensions(manifest.video)
    balls_by_frame = _load_ball_points(ball_tracks_path)
    points = [
        point
        for record in records
        for point in _player_points(record, confidence)
        if (
            _inside_pitch(point.foot[0], point.foot[1], width, height)
            or _near_ball(
                point,
                balls_by_frame.get(point.source_frame, ()),
            )
        )
    ]
    tracks = _associate_players(
        points,
        max_gap_seconds=max_gap_seconds,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    accepted = [
        track for track in tracks if len(track.points) >= minimum_track_points
    ]
    initialization: MatchInitialization | None = None
    if team_color_references_path is not None:
        references_payload = json.loads(
            team_color_references_path.read_text(encoding="utf-8")
        )
        references = {
            str(label): tuple(int(channel) for channel in color)
            for label, color in references_payload["team_colors_bgr"].items()
        }
        _classify_tracks_kmeans(accepted, manifest.video, references)
    elif team_profile == "auto":
        initialization = _classify_tracks_auto(
            accepted,
            manifest.video,
            width=width,
            height=height,
            half=manifest.half,
            source_start_seconds=manifest.source_start_seconds,
            starts_at_kickoff=manifest.starts_at_kickoff,
        )
    else:
        _classify_tracks(accepted, manifest.video, team_profile=team_profile)
    if goalkeeper_affiliations_path is not None:
        affiliations = json.loads(
            goalkeeper_affiliations_path.read_text(encoding="utf-8")
        )
        apply_goalkeeper_affiliations(accepted, affiliations["affiliations"])

    output.mkdir(parents=True, exist_ok=True)
    destination = output / "player-tracks.json"
    destination.write_text(
        json.dumps(
            {
                "manifest": str(manifest.path),
                "player_cache": str(player_cache_path.resolve()),
                "player_cache_configuration": metadata,
                "match_initialization": (
                    initialization.to_dict() if initialization else None
                ),
                "tracks": [
                    {
                        "track_id": track.track_id,
                        "team": track.team,
                        "role": track.role,
                        "color_scores": track.color_scores,
                        "points": [asdict(point) for point in track.points],
                    }
                    for track in accepted
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if initialization is not None:
        (output / "match-initialization.json").write_text(
            json.dumps(initialization.to_dict(), indent=2),
            encoding="utf-8",
        )
    _write_summary(output, records, accepted)
    if render_video:
        _render_verification_video(
            manifest=manifest,
            records=records,
            tracks=accepted,
            ball_tracks_path=ball_tracks_path,
            output=output / "tracking-verification.mp4",
        )
    print(f"Player tracks written to {destination.resolve()}")
    return destination


def _associate_players(
    points: Iterable[PlayerPoint],
    *,
    max_gap_seconds: float,
    max_speed_pixels_per_second: float,
) -> tuple[PlayerTrack, ...]:
    by_frame: dict[int, list[PlayerPoint]] = {}
    for point in points:
        by_frame.setdefault(point.source_frame, []).append(point)

    tracks: list[PlayerTrack] = []
    next_track_id = 1
    for frame_points in by_frame.values():
        timestamp = frame_points[0].clip_seconds
        active = [
            track
            for track in tracks
            if timestamp - track.last.clip_seconds <= max_gap_seconds
        ]
        pairs: list[tuple[float, int, int]] = []
        for track_index, track in enumerate(active):
            predicted_x, predicted_y = track.predicted_foot(timestamp)
            elapsed = timestamp - track.last.clip_seconds
            max_distance = max(
                25.0,
                track.last.height * 0.8
                + max_speed_pixels_per_second * elapsed,
            )
            for point_index, point in enumerate(frame_points):
                point_x, point_y = point.foot
                distance = hypot(point_x - predicted_x, point_y - predicted_y)
                if distance <= max_distance:
                    cost = distance / max_distance - 0.25 * _box_iou(
                        track.last, point
                    )
                    pairs.append((cost, track_index, point_index))

        assigned_tracks: set[int] = set()
        assigned_points: set[int] = set()
        for _, track_index, point_index in sorted(pairs):
            if track_index in assigned_tracks or point_index in assigned_points:
                continue
            active[track_index].points.append(frame_points[point_index])
            assigned_tracks.add(track_index)
            assigned_points.add(point_index)

        for point_index, point in enumerate(frame_points):
            if point_index not in assigned_points:
                tracks.append(PlayerTrack(next_track_id, [point]))
                next_track_id += 1
    return tuple(tracks)


def classify_color_scores(
    scores: dict[str, float], *, team_profile: str = "blue-white"
) -> str:
    blue = scores.get("blue", 0.0)
    white = scores.get("white", 0.0)
    dark = scores.get("dark", 0.0)
    warm = scores.get("warm", 0.0)
    yellow = scores.get("yellow", 0.0)
    if team_profile == "red-black":
        if yellow >= 0.35 and white < 0.1:
            return "official"
        if dark >= 0.3:
            return "black"
        if (
            white >= 0.12
            and warm + yellow >= 0.12
            or warm >= 0.12
        ):
            return "red"
    elif team_profile == "blue-white":
        if warm >= 0.15 or yellow >= 0.15:
            return "goalkeeper"
        if dark >= 0.35:
            return "official"
        if blue >= 0.2 and blue > white * 1.75:
            return "blue"
        if white >= 0.2 and white > blue * 1.25:
            return "white"
    else:
        raise ValueError(f"Unsupported team profile: {team_profile}")
    return "unknown"


def apply_goalkeeper_affiliations(
    tracks: list[PlayerTrack], affiliations: list[dict[str, Any]]
) -> None:
    for track in tracks:
        foot_x = median(point.foot[0] for point in track.points)
        foot_y = median(point.foot[1] for point in track.points)
        track_duration = track.points[-1].clip_seconds - track.points[0].clip_seconds
        for affiliation in affiliations:
            eligible = set(affiliation.get("eligible_teams", ["unknown"]))
            region = affiliation["region"]
            if (
                track.team in eligible
                and track_duration
                >= float(affiliation.get("minimum_track_seconds", 0.0))
                and float(region["x_min"]) <= foot_x <= float(region["x_max"])
                and float(region["y_min"]) <= foot_y <= float(region["y_max"])
            ):
                track.team = str(affiliation["team"])
                track.role = "goalkeeper"
                for point in track.points:
                    point.team = track.team
                break


def _classify_tracks(
    tracks: list[PlayerTrack],
    video: Path,
    *,
    team_profile: str,
) -> None:
    samples_by_frame: dict[int, list[tuple[PlayerTrack, PlayerPoint]]] = defaultdict(
        list
    )
    for track in tracks:
        for point in track.points:
            samples_by_frame[point.source_frame].append((track, point))

    feature_samples: dict[int, list[dict[str, float]]] = defaultdict(list)
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        current_frame = min(samples_by_frame)
        capture.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        for source_frame in sorted(samples_by_frame):
            while current_frame < source_frame:
                if not capture.grab():
                    raise RuntimeError(
                        f"Could not skip to color sample frame {source_frame}"
                    )
                current_frame += 1
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(
                    f"Could not read color sample frame {source_frame}"
                )
            current_frame = source_frame + 1
            frame_samples = samples_by_frame[source_frame]
            for track, point in frame_samples:
                features = _jersey_features(frame, point)
                if features is not None:
                    point.color_scores = {
                        key: round(value, 4) for key, value in features.items()
                    }
                    point.team = classify_color_scores(
                        features, team_profile=team_profile
                    )
                    feature_samples[track.track_id].append(features)
    finally:
        capture.release()

    for track in tracks:
        samples = feature_samples.get(track.track_id, [])
        if not samples:
            track.color_scores = {}
            track.team = "unknown"
            continue
        aggregate = {
            key: round(median(sample[key] for sample in samples), 4)
            for key in ("blue", "white", "dark", "warm", "yellow")
        }
        track.color_scores = aggregate
        _stabilize_track_team_causally(track)


def _classify_tracks_auto(
    tracks: list[PlayerTrack],
    video: Path,
    *,
    width: int,
    height: int,
    half: int | None,
    source_start_seconds: float,
    starts_at_kickoff: bool,
) -> MatchInitialization:
    samples_by_frame: dict[int, list[tuple[PlayerTrack, PlayerPoint]]] = defaultdict(
        list
    )
    for track in tracks:
        for point in _evenly_sampled_points(track.points, limit=12):
            samples_by_frame[point.source_frame].append((track, point))

    colors_by_track: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        current_frame = min(samples_by_frame)
        capture.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        for source_frame in sorted(samples_by_frame):
            while current_frame < source_frame:
                if not capture.grab():
                    raise RuntimeError(
                        f"Could not skip to color sample frame {source_frame}"
                    )
                current_frame += 1
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(
                    f"Could not read color sample frame {source_frame}"
                )
            current_frame = source_frame + 1
            for track, point in samples_by_frame[source_frame]:
                crop = _jersey_crop(frame, point)
                if crop is None:
                    continue
                color = dominant_jersey_color(crop)
                colors_by_track[track.track_id].append(color)
                point.color_scores = {
                    "blue": round(color[0] / 255, 4),
                    "green": round(color[1] / 255, 4),
                    "red": round(color[2] / 255, 4),
                }
    finally:
        capture.release()

    evidence: list[TrackInitializationEvidence] = []
    for track in tracks:
        colors = colors_by_track.get(track.track_id, [])
        if not colors:
            track.color_scores = {}
            _stabilize_track_team(track, "unknown")
            continue
        color = tuple(
            int(round(median(sample[channel] for sample in colors)))
            for channel in range(3)
        )
        track.color_scores = {
            "blue": round(color[0] / 255, 4),
            "green": round(color[1] / 255, 4),
            "red": round(color[2] / 255, 4),
        }
        evidence.append(
            TrackInitializationEvidence(
                track_id=track.track_id,
                color_bgr=color,
                sample_count=len(colors),
                start_seconds=track.points[0].clip_seconds,
                end_seconds=track.points[-1].clip_seconds,
                normalized_positions=tuple(
                    (point.foot[0] / width, point.foot[1] / height)
                    for point in track.points
                ),
            )
        )

    initialization = infer_match_initialization(
        evidence,
        half=half,
        source_start_seconds=source_start_seconds,
        starts_at_kickoff=starts_at_kickoff,
    )
    team_by_track = {
        track_id: cluster.team
        for cluster in initialization.teams
        for track_id in cluster.track_ids
    }
    official_ids = set(initialization.official_track_ids)
    goalkeepers = {
        goalkeeper.track_id: goalkeeper for goalkeeper in initialization.goalkeepers
    }
    for track in tracks:
        team = team_by_track.get(track.track_id, "unknown")
        role = "player"
        if track.track_id in official_ids:
            team = "official"
            role = "official"
        goalkeeper = goalkeepers.get(track.track_id)
        if goalkeeper is not None:
            team = goalkeeper.team or "unknown"
            role = "goalkeeper"
        _stabilize_track_team(track, team)
        track.role = role
    return initialization


def _evenly_sampled_points(
    points: list[PlayerPoint], *, limit: int
) -> tuple[PlayerPoint, ...]:
    if limit < 1:
        raise ValueError("Sample limit must be positive")
    if len(points) <= limit:
        return tuple(points)
    indices = {
        round(index * (len(points) - 1) / (limit - 1))
        for index in range(limit)
    }
    return tuple(points[index] for index in sorted(indices))


def _classify_tracks_kmeans(
    tracks: list[PlayerTrack],
    video: Path,
    references: dict[str, tuple[int, int, int]],
) -> None:
    samples_by_frame: dict[int, list[tuple[PlayerTrack, PlayerPoint]]] = defaultdict(
        list
    )
    for track in tracks:
        for point in track.points:
            samples_by_frame[point.source_frame].append((track, point))
    colors_by_track: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        current_frame = min(samples_by_frame)
        capture.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        for source_frame in sorted(samples_by_frame):
            while current_frame < source_frame:
                if not capture.grab():
                    raise RuntimeError(
                        f"Could not skip to color sample frame {source_frame}"
                    )
                current_frame += 1
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(
                    f"Could not read color sample frame {source_frame}"
                )
            current_frame = source_frame + 1
            for track, point in samples_by_frame[source_frame]:
                crop = _jersey_crop(frame, point)
                if crop is None:
                    continue
                color = dominant_jersey_color(crop)
                point.color_scores = {
                    "blue": color[0] / 255,
                    "green": color[1] / 255,
                    "red": color[2] / 255,
                }
                point.team = assign_color_group(color, references)
                colors_by_track[track.track_id].append(color)
    finally:
        capture.release()

    for track in tracks:
        colors = colors_by_track.get(track.track_id, [])
        labels = Counter(
            point.team for point in track.points if point.team != "unknown"
        )
        stable_team = labels.most_common(1)[0][0] if labels else "unknown"
        _stabilize_track_team(track, stable_team)
        track.color_scores = (
            {
                "blue": round(median(color[0] for color in colors) / 255, 4),
                "green": round(median(color[1] for color in colors) / 255, 4),
                "red": round(median(color[2] for color in colors) / 255, 4),
            }
            if colors
            else {}
        )


def _stabilize_track_team(track: PlayerTrack, team: str) -> None:
    track.team = team
    for point in track.points:
        point.team = team


def _stabilize_track_team_causally(
    track: PlayerTrack,
    *,
    window_size: int = 7,
) -> None:
    if window_size < 1:
        raise ValueError("Team stabilization window must be positive")
    history: deque[str] = deque(maxlen=window_size)
    current_team = "unknown"
    for point in track.points:
        if point.team != "unknown":
            history.append(point.team)
        if history:
            counts = Counter(history)
            highest = max(counts.values())
            leaders = {
                team for team, count in counts.items() if count == highest
            }
            if current_team not in leaders:
                current_team = next(
                    team for team in reversed(history) if team in leaders
                )
        point.team = current_team
    track.team = current_team


def _jersey_features(
    frame: np.ndarray, point: PlayerPoint
) -> dict[str, float] | None:
    crop = _jersey_crop(frame, point)
    if crop is None:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    return {
        "blue": float(np.mean((hue >= 90) & (hue <= 135) & (saturation > 70))),
        "white": float(np.mean((saturation < 60) & (value > 135))),
        "dark": float(np.mean(value < 80)),
        "warm": float(
            np.mean(
                ((hue < 15) | (hue > 165))
                & (saturation > 80)
                & (value > 100)
            )
        ),
        "yellow": float(
            np.mean(
                (hue >= 15)
                & (hue <= 40)
                & (saturation > 80)
                & (value > 100)
            )
        ),
    }


def _jersey_crop(
    frame: np.ndarray, point: PlayerPoint
) -> np.ndarray | None:
    width = point.x2 - point.x1
    height = point.y2 - point.y1
    x1 = max(0, int(point.x1 + width * 0.2))
    x2 = min(frame.shape[1], int(point.x2 - width * 0.2))
    y1 = max(0, int(point.y1 + height * 0.12))
    y2 = min(frame.shape[0], int(point.y1 + height * 0.58))
    if x2 <= x1 or y2 <= y1:
        return None
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    return crop


def _load_player_cache(
    cache_path: Path, manifest_sha256: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not cache_path.is_file():
        raise FileNotFoundError(f"Player detection cache does not exist: {cache_path}")
    lines = cache_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("Player detection cache is empty")
    metadata = json.loads(lines[0])
    if metadata.get("manifest_sha256") != manifest_sha256:
        raise ValueError("Player cache was created for a different manifest")
    records = [
        json.loads(line)
        for line in lines[1:]
        if json.loads(line).get("type") == "frame"
    ]
    if not records:
        raise ValueError("Player cache contains no frames")
    records.sort(key=lambda record: int(record["source_frame"]))
    return metadata, records


def _player_points(
    record: dict[str, Any], confidence: float
) -> list[PlayerPoint]:
    return [
        PlayerPoint(
            source_frame=int(record["source_frame"]),
            clip_seconds=float(record["clip_seconds"]),
            confidence=float(detection["confidence"]),
            x1=float(detection["x1"]),
            y1=float(detection["y1"]),
            x2=float(detection["x2"]),
            y2=float(detection["y2"]),
        )
        for detection in record.get("detections", [])
        if detection.get("class_name") == "person"
        and float(detection["confidence"]) >= confidence
    ]


def _inside_pitch(x: float, y: float, width: int, height: int) -> bool:
    normalized_x = abs(x - width / 2) / (width / 2)
    top = (80 + 180 * normalized_x**2) / 1080 * height
    bottom = (640 + 65 * (1 - normalized_x**2)) / 1080 * height
    return top <= y <= bottom


def _near_ball(
    point: PlayerPoint,
    balls: Iterable[tuple[float, float]],
    *,
    maximum_distance_ratio: float = 1.5,
) -> bool:
    foot_x, foot_y = point.foot
    return any(
        hypot(foot_x - ball_x, foot_y - ball_y) / point.height
        <= maximum_distance_ratio
        for ball_x, ball_y in balls
    )


def _box_iou(first: PlayerPoint, second: PlayerPoint) -> float:
    intersection_width = max(0.0, min(first.x2, second.x2) - max(first.x1, second.x1))
    intersection_height = max(
        0.0, min(first.y2, second.y2) - max(first.y1, second.y1)
    )
    intersection = intersection_width * intersection_height
    first_area = max(0.0, first.x2 - first.x1) * max(0.0, first.y2 - first.y1)
    second_area = max(0.0, second.x2 - second.x1) * max(
        0.0, second.y2 - second.y1
    )
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def _write_summary(
    output: Path,
    records: list[dict[str, Any]],
    tracks: list[PlayerTrack],
) -> None:
    frame_teams: dict[int, Counter[str]] = defaultdict(Counter)
    for track in tracks:
        for point in track.points:
            frame_teams[point.source_frame][point.team] += 1
    team_counts = Counter(track.team for track in tracks)
    labels = sorted(
        {"blue", "white", "red", "black", "goalkeeper", "official", "unknown"}
        | set(team_counts)
    )
    median_visible = {
        team: round(
            median(counts.get(team, 0) for counts in frame_teams.values()), 2
        )
        for team in labels
    }
    summary = {
        "processed_frames": len(records),
        "accepted_tracks": len(tracks),
        "track_labels": dict(sorted(team_counts.items())),
        "median_visible_per_frame": median_visible,
        "longest_tracks": [
            {
                "track_id": track.track_id,
                "team": track.team,
                "points": len(track.points),
                "start_seconds": track.points[0].clip_seconds,
                "end_seconds": track.points[-1].clip_seconds,
            }
            for track in sorted(
                tracks, key=lambda candidate: len(candidate.points), reverse=True
            )[:25]
        ],
    }
    (output / "player-tracking-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


def _render_verification_video(
    *,
    manifest: BenchmarkManifest,
    records: list[dict[str, Any]],
    tracks: list[PlayerTrack],
    ball_tracks_path: Path,
    output: Path,
) -> None:
    players_by_frame: dict[int, list[tuple[PlayerTrack, PlayerPoint]]] = defaultdict(
        list
    )
    for track in tracks:
        for point in track.points:
            players_by_frame[point.source_frame].append((track, point))
    balls_by_frame = _load_ball_points(ball_tracks_path)

    width, height = _video_dimensions(manifest.video)
    stride = int(records[1]["source_frame"]) - int(records[0]["source_frame"])
    writer = cv2.VideoWriter(
        str(output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        manifest.fps / stride,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not open verification video writer: {output}")
    capture = cv2.VideoCapture(str(manifest.video))
    current_frame = int(records[0]["source_frame"])
    capture.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
    try:
        for record in records:
            source_frame = int(record["source_frame"])
            while current_frame < source_frame:
                if not capture.grab():
                    raise RuntimeError(
                        f"Could not skip to render frame {source_frame}"
                    )
                current_frame += 1
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"Could not read render frame {source_frame}")
            current_frame = source_frame + 1
            for track, point in players_by_frame.get(source_frame, []):
                color = _team_color(point.team)
                cv2.rectangle(
                    frame,
                    (int(point.x1), int(point.y1)),
                    (int(point.x2), int(point.y2)),
                    color,
                    2,
                )
                cv2.putText(
                    frame,
                    (
                        f"{point.team} goalkeeper #{track.track_id}"
                        if track.role == "goalkeeper"
                        else f"{point.team} #{track.track_id}"
                    ),
                    (int(point.x1), max(20, int(point.y1) - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    color,
                    1,
                    cv2.LINE_AA,
                )
            for x, y in balls_by_frame.get(source_frame, []):
                cv2.circle(frame, (round(x), round(y)), 12, (0, 255, 255), 3)
            writer.write(frame)
    finally:
        capture.release()
        writer.release()


def _load_ball_points(path: Path) -> dict[int, list[tuple[float, float]]]:
    if not path.is_file():
        raise FileNotFoundError(f"Ball tracks do not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    points: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for track in payload.get("tracks", []):
        for point in track.get("points", []):
            points[int(point["source_frame"])].append(
                (float(point["x"]), float(point["y"]))
            )
    return points


def _team_color(team: str) -> tuple[int, int, int]:
    return {
        "blue": (255, 80, 20),
        "white": (255, 255, 255),
        "red": (20, 20, 235),
        "black": (60, 60, 60),
        "goalkeeper": (0, 120, 255),
        "official": (30, 30, 30),
    }.get(team, (160, 160, 160))


def _video_dimensions(video: Path) -> tuple[int, int]:
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        capture.release()
    if width <= 0 or height <= 0:
        raise ValueError("Benchmark video dimensions are invalid")
    return width, height


def _validate_options(
    *,
    confidence: float,
    max_gap_seconds: float,
    max_speed_pixels_per_second: float,
    minimum_track_points: int,
) -> None:
    if not 0 < confidence <= 1:
        raise ValueError("Player confidence must be greater than 0 and at most 1")
    if max_gap_seconds <= 0 or max_speed_pixels_per_second <= 0:
        raise ValueError("Track gap and speed limits must be greater than zero")
    if minimum_track_points < 2:
        raise ValueError("Minimum track points must be at least 2")
