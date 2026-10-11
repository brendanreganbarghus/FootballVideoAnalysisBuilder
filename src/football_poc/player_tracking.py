from __future__ import annotations

import json
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from math import hypot
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Sequence

import cv2
import numpy as np

from football_poc.benchmark import BenchmarkManifest
from football_poc.image_space import scale_factors, scale_goalkeeper_affiliations
from football_poc.match_initialization import (
    MatchInitialization,
    TrackInitializationEvidence,
    infer_match_initialization,
)
from football_poc.pitch_geometry import load_pitch_boundary, signed_pitch_distance
from football_poc.team_colors import (
    assign_color_group,
    dominant_jersey_color,
)

OUTFIELD_TEAMS = frozenset({"red", "black", "blue", "white"})


# A player hidden behind another for at most this long is joined up again.
HIDDEN_BRIDGE_MAX_GAP_SECONDS = 0.8
HIDDEN_BRIDGE_REACH_HEIGHTS = 0.8
HIDDEN_BRIDGE_MINIMUM_COVER = 0.3


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
    # This box's own kit reading, before the track's team is smoothed.
    kit_team: str | None = None
    # Estimated box while the player is hidden behind another player.
    hidden: bool = False

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
    pitch_calibration_path: Path | None = None,
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
    calibrated_boundary = (
        _calibrated_pitch_boundary(pitch_calibration_path, (width, height))
        if pitch_calibration_path is not None
        else None
    )

    def on_pitch(point: PlayerPoint) -> bool:
        if calibrated_boundary is not None:
            return signed_pitch_distance(point.foot, calibrated_boundary) >= 0
        return _inside_pitch(point.foot[0], point.foot[1], width, height)

    points: list[PlayerPoint] = []
    # People outside the lines (officials, staff, ball boys) are kept as
    # objects in their own file and never take part as players.
    outside_points: list[PlayerPoint] = []
    for record in records:
        for point in _player_points(record, confidence):
            if on_pitch(point) or _near_ball(
                point, balls_by_frame.get(point.source_frame, ())
            ):
                points.append(point)
            else:
                outside_points.append(point)
    points = _drop_piece_boxes(points)
    player_teams = PLAYER_TEAMS_BY_PROFILE.get(team_profile, frozenset())
    colors_read = (
        team_color_references_path is None and bool(player_teams)
    )
    if colors_read:
        team_colors = _read_point_colors(
            points, manifest.video, team_profile=team_profile
        )
    else:
        team_colors = {}
    tracks = _associate_players(
        points,
        max_gap_seconds=max_gap_seconds,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        player_teams=player_teams if colors_read else frozenset(),
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
        team_colors = _classify_tracks(
            accepted,
            manifest.video,
            team_profile=team_profile,
            colors_read=colors_read,
        ) or team_colors
    if goalkeeper_affiliations_path is not None:
        affiliations = json.loads(
            goalkeeper_affiliations_path.read_text(encoding="utf-8")
        )
        apply_goalkeeper_affiliations(
            accepted,
            scale_goalkeeper_affiliations(affiliations, (width, height)),
        )
    if colors_read:
        accepted = [track for track in accepted if not _is_still_object(track)]
    overlaps = (
        resolve_overlap_teams(
            accepted, team_profile=team_profile, team_colors=team_colors
        )
        if team_profile in ("red-black", "blue-white")
        else None
    )
    if colors_read:
        accepted = bridge_hidden_gaps(
            accepted,
            player_teams=player_teams,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        )

    output.mkdir(parents=True, exist_ok=True)
    if overlaps is not None:
        (output / "player-overlaps.json").write_text(
            json.dumps(overlaps, indent=2), encoding="utf-8"
        )
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
    outside_tracks = [
        track
        for track in _associate_players(
            outside_points,
            max_gap_seconds=max_gap_seconds,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        )
        if len(track.points) >= minimum_track_points
    ]
    (output / "outside-pitch-objects.json").write_text(
        json.dumps(
            {
                "role": "outside_pitch",
                "objects": [
                    {
                        "object_id": f"O{track.track_id}",
                        "points": [asdict(point) for point in track.points],
                    }
                    for track in outside_tracks
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
    player_teams: frozenset[str] = frozenset(),
) -> tuple[PlayerTrack, ...]:
    by_frame: dict[int, list[PlayerPoint]] = {}
    for point in points:
        by_frame.setdefault(point.source_frame, []).append(point)

    tracks: list[PlayerTrack] = []
    # Tracks that last shared a player with a stronger track. Without its own
    # box such a track must not jump onto a different nearby player after a gap.
    duplicated: set[int] = set()
    next_track_id = 1
    for frame_points in by_frame.values():
        timestamp = frame_points[0].clip_seconds
        active = [
            track
            for track in tracks
            if timestamp - track.last.clip_seconds <= max_gap_seconds
        ]
        pairs: list[tuple[tuple[bool, float], int, int]] = []
        for track_index, track in enumerate(active):
            predicted_x, predicted_y = track.predicted_foot(timestamp)
            elapsed = timestamp - track.last.clip_seconds
            history_team = _clear_team_history(track, player_teams)
            if track.track_id in duplicated:
                max_distance = max(25.0, track.last.height * 0.8)
            else:
                max_distance = max(
                    25.0,
                    track.last.height * 0.8
                    + max_speed_pixels_per_second * elapsed,
                )
            for point_index, point in enumerate(frame_points):
                if (
                    history_team is not None
                    and point.team in player_teams
                    and point.team != history_team
                ):
                    # The box's own shirt clearly shows the other team.
                    continue
                point_x, point_y = point.foot
                distance = hypot(point_x - predicted_x, point_y - predicted_y)
                if distance <= max_distance:
                    # A person keeps roughly the same height between samples,
                    # so a cut-off piece must not take over from a full box.
                    cost = (
                        distance / max_distance
                        - 0.25 * _box_iou(track.last, point)
                        + HEIGHT_CHANGE_COST
                        * abs(point.height - track.last.height)
                        / max(point.height, track.last.height, 1.0)
                    )
                    # A track that last shared its player with a stronger
                    # track picks only after every independent track, so a
                    # merged box cannot take a hidden player's own box.
                    pairs.append(
                        (
                            (track.track_id in duplicated, cost),
                            track_index,
                            point_index,
                        )
                    )

        assigned_tracks: set[int] = set()
        assigned_points: set[int] = set()
        updated: list[PlayerTrack] = []
        for _, track_index, point_index in sorted(pairs):
            if track_index in assigned_tracks or point_index in assigned_points:
                continue
            track = active[track_index]
            track.points.append(frame_points[point_index])
            assigned_tracks.add(track_index)
            assigned_points.add(point_index)
            updated.append(track)
            duplicated.discard(track.track_id)

        for point_index, point in enumerate(frame_points):
            if point_index not in assigned_points:
                track = PlayerTrack(next_track_id, [point])
                tracks.append(track)
                updated.append(track)
                next_track_id += 1

        for first_index, first in enumerate(updated):
            for second in updated[first_index + 1 :]:
                if first.track_id in duplicated or second.track_id in duplicated:
                    continue
                if _box_overlap_of_smaller(first.last, second.last) >= 0.6:
                    weaker = (
                        first
                        if (len(first.points), first.last.confidence)
                        < (len(second.points), second.last.confidence)
                        else second
                    )
                    duplicated.add(weaker.track_id)
    return tuple(tracks)


def _drop_piece_boxes(points: list[PlayerPoint]) -> list[PlayerPoint]:
    """Drop boxes that are only a piece (legs, head, a thin sliver) of a box.

    A box lying almost fully inside a much taller or much wider box in the
    same frame is the same person cut off by YOLO, not another player.
    """
    by_frame: dict[int, list[PlayerPoint]] = defaultdict(list)
    for point in points:
        by_frame[point.source_frame].append(point)
    kept: list[PlayerPoint] = []
    for frame_points in by_frame.values():
        pieces = {
            id(other): [
                point
                for point in frame_points
                if _is_piece_of(point, other)
            ]
            for other in frame_points
        }
        # Two players standing one behind the other can also get one weak
        # box around both. When two separate boxes inside it are each at
        # least as sure as that box, it is the merge, not the players.
        merged = {
            id(other)
            for other in frame_points
            if any(
                _box_overlap_of_smaller(first, second) < PIECE_BOX_CONTAINMENT
                and other.confidence <= min(first.confidence, second.confidence)
                for index, first in enumerate(pieces[id(other)])
                for second in pieces[id(other)][index + 1 :]
            )
        }
        for point in frame_points:
            if id(point) in merged:
                continue
            if not any(
                id(other) not in merged and _is_piece_of(point, other)
                for other in frame_points
            ):
                kept.append(point)
    return kept


def _is_piece_of(point: PlayerPoint, other: PlayerPoint) -> bool:
    return (
        other is not point
        and (
            point.height < PIECE_BOX_HEIGHT_SHARE * other.height
            or (point.x2 - point.x1) < PIECE_BOX_WIDTH_SHARE * (other.x2 - other.x1)
        )
        and _box_overlap_of_smaller(point, other) >= PIECE_BOX_CONTAINMENT
    )


def _clear_team_history(
    track: PlayerTrack, player_teams: frozenset[str]
) -> str | None:
    """Return the team a track has clearly shown in its recent readable boxes."""
    if not player_teams:
        return None
    recent = [
        point.team
        for point in track.points[-TEAM_HISTORY_POINTS * 3 :]
        if point.team != "unknown"
    ][-TEAM_HISTORY_POINTS:]
    if len(recent) < TEAM_HISTORY_POINTS:
        return None
    team, count = Counter(recent).most_common(1)[0]
    if team in player_teams and count >= TEAM_HISTORY_AGREEMENT:
        return team
    return None


def _box_overlap_of_smaller(first: PlayerPoint, second: PlayerPoint) -> float:
    width = max(0.0, min(first.x2, second.x2) - max(first.x1, second.x1))
    height = max(0.0, min(first.y2, second.y2) - max(first.y1, second.y1))
    smaller = min(
        (first.x2 - first.x1) * (first.y2 - first.y1),
        (second.x2 - second.x1) * (second.y2 - second.y1),
    )
    return width * height / smaller if smaller > 0 else 0.0


def bridge_hidden_gaps(
    tracks: list[PlayerTrack],
    *,
    player_teams: frozenset[str],
    max_speed_pixels_per_second: float,
    max_gap_seconds: float = HIDDEN_BRIDGE_MAX_GAP_SECONDS,
    reach_heights: float = HIDDEN_BRIDGE_REACH_HEIGHTS,
    minimum_cover: float = HIDDEN_BRIDGE_MINIMUM_COVER,
) -> list[PlayerTrack]:
    """Join a player track that ends and restarts behind another player.

    When a player walks behind another, the detector gives one box for both
    and the hidden player's track ends; it restarts as a new track when he
    reappears. Two same-team tracks are joined only when the estimated box
    in every missing frame is covered by another player's box, so the gap is
    explained by occlusion. The missing frames get estimated hidden points.
    """
    frames: dict[int, list[tuple[PlayerTrack, PlayerPoint]]] = defaultdict(list)
    for track in tracks:
        for point in track.points:
            frames[point.source_frame].append((track, point))
    candidates: list[tuple[float, PlayerTrack, PlayerTrack, list[PlayerPoint]]] = []
    for first in tracks:
        if first.role != "player" or first.team not in player_teams:
            continue
        end = first.last
        for second in tracks:
            if second is first or second.role != "player":
                continue
            if second.team != first.team:
                continue
            start = second.points[0]
            gap = start.clip_seconds - end.clip_seconds
            if not 0 < gap <= max_gap_seconds:
                continue
            distance = hypot(end.foot[0] - start.foot[0], end.foot[1] - start.foot[1])
            if distance > max_speed_pixels_per_second * gap + reach_heights * end.height:
                continue
            hidden = _hidden_points(
                end, start, frames, (first, second), minimum_cover
            )
            if hidden is None:
                continue
            candidates.append((distance / gap, first, second, hidden))
    candidates.sort(key=lambda item: item[0])
    ended: set[int] = set()
    started: set[int] = set()
    joins: dict[int, tuple[PlayerTrack, list[PlayerPoint]]] = {}
    for _, first, second, hidden in candidates:
        if first.track_id in ended or second.track_id in started:
            continue
        ended.add(first.track_id)
        started.add(second.track_id)
        joins[first.track_id] = (second, hidden)
    if not joins:
        return tracks
    absorbed = {second.track_id for second, _ in joins.values()}
    by_id = {track.track_id: track for track in tracks}
    for track in tracks:
        if track.track_id in absorbed:
            continue
        current = track
        while current.track_id in joins:
            second, hidden = joins[current.track_id]
            for point in hidden:
                point.team = track.team
            track.points.extend(hidden)
            track.points.extend(by_id[second.track_id].points)
            current = second
    return [track for track in tracks if track.track_id not in absorbed]


def _hidden_points(
    end: PlayerPoint,
    start: PlayerPoint,
    frames: dict[int, list[tuple[PlayerTrack, PlayerPoint]]],
    pair: tuple[PlayerTrack, PlayerTrack],
    minimum_cover: float,
) -> list[PlayerPoint] | None:
    gap_frames = sorted(
        frame for frame in frames if end.source_frame < frame < start.source_frame
    )
    if not gap_frames:
        return None
    hidden: list[PlayerPoint] = []
    span = start.source_frame - end.source_frame
    for frame in gap_frames:
        share = (frame - end.source_frame) / span
        members = frames[frame]
        estimate = PlayerPoint(
            source_frame=frame,
            clip_seconds=end.clip_seconds
            + share * (start.clip_seconds - end.clip_seconds),
            confidence=0.0,
            x1=end.x1 + share * (start.x1 - end.x1),
            y1=end.y1 + share * (start.y1 - end.y1),
            x2=end.x2 + share * (start.x2 - end.x2),
            y2=end.y2 + share * (start.y2 - end.y2),
            hidden=True,
        )
        covered = any(
            _box_overlap_of_smaller(estimate, point) >= minimum_cover
            for track, point in members
            if track not in pair
        )
        if not covered:
            return None
        hidden.append(estimate)
    return hidden


def _resolve_part_boxes(
    tracks: list[PlayerTrack],
    members_by_frame: dict[int, list[tuple[PlayerTrack, PlayerPoint]]],
) -> list[dict[str, Any]]:
    """Give a box that is only a piece of a person the team of that person.

    YOLO sometimes boxes only a head, legs or a slice of a player who already
    has a full box. Such a box lies mostly inside the larger box in the same
    frame, so it is a piece of that person, not another player.
    """
    part_boxes: list[dict[str, Any]] = []
    for source_frame in sorted(members_by_frame):
        members = members_by_frame[source_frame]
        for track, point in members:
            if point.team != "unknown":
                continue
            hosts = [
                (other_track, other)
                for other_track, other in members
                if other is not point
                and other.team != "unknown"
                and _area(other) > _area(point)
                and _box_overlap_of_smaller(point, other) >= MERGED_BOX_CONTAINMENT
            ]
            if not hosts:
                continue
            host_track, host = max(
                hosts, key=lambda item: _box_overlap_of_smaller(point, item[1])
            )
            point.team = host.team
            part_boxes.append(
                {
                    "source_frame": source_frame,
                    "clip_seconds": point.clip_seconds,
                    "track_id": track.track_id,
                    "inside_track_id": host_track.track_id,
                    "team": host.team,
                }
            )
    for track in tracks:
        known = [
            (point.clip_seconds, point.team)
            for point in track.points
            if point.team != "unknown"
        ]
        if not known:
            continue
        for point in track.points:
            if point.team == "unknown":
                point.team = min(
                    known, key=lambda item: abs(item[0] - point.clip_seconds)
                )[1]
    return part_boxes


def resolve_overlap_teams(
    tracks: list[PlayerTrack],
    *,
    team_profile: str,
    minimum_overlap: float = 0.2,
    contact_radius_heights: float = 0.75,
    clear_votes: int = 3,
    team_colors: dict[str, tuple[list[float], list[float]]] | None = None,
) -> dict[str, Any]:
    """Settle the team of overlapped or uncoloured boxes from evidence.

    An overlapped box is read only on its own, unshared jersey pixels (see
    ``_jersey_features``); that reading beats the track history, because a
    track can jump to another person during an overlap. Without a reading, the
    same track's nearest frames where the person stands alone with a readable
    kit decide. Every overlap group is returned so later rules can see which
    people shared a location.
    """
    members_by_frame: dict[int, list[tuple[PlayerTrack, PlayerPoint]]] = (
        defaultdict(list)
    )
    for track in tracks:
        for point in track.points:
            members_by_frame[point.source_frame].append((track, point))

    overlapped: set[int] = set()
    crowded: set[int] = set()
    frames: list[dict[str, Any]] = []
    for source_frame in sorted(members_by_frame):
        members = members_by_frame[source_frame]
        parent = list(range(len(members)))

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        for first in range(len(members)):
            for second in range(first + 1, len(members)):
                one, other = members[first][1], members[second][1]
                if _box_overlap_of_smaller(one, other) >= CROWD_BOX_OVERLAP:
                    crowded.update((id(one), id(other)))
                if (
                    _box_overlap_of_smaller(one, other) >= minimum_overlap
                    or hypot(
                        one.foot[0] - other.foot[0], one.foot[1] - other.foot[1]
                    )
                    <= contact_radius_heights * max(one.height, other.height)
                ):
                    parent[find(first)] = find(second)
        grouped: dict[int, list[int]] = defaultdict(list)
        for index in range(len(members)):
            grouped[find(index)].append(index)
        groups = [indices for indices in grouped.values() if len(indices) > 1]
        if not groups:
            continue
        for indices in groups:
            for index in indices:
                overlapped.add(id(members[index][1]))
        frames.append(
            {
                "source_frame": source_frame,
                "clip_seconds": members[0][1].clip_seconds,
                "groups": [[members[index] for index in indices] for indices in groups],
            }
        )

    resolved = 0

    def read(point: PlayerPoint) -> str:
        if team_colors:
            return nearest_team_color(
                point.color_scores, team_colors, overlapped=id(point) in crowded
            )
        return classify_color_scores(point.color_scores, team_profile=team_profile)

    for track in tracks:
        if track.role == "goalkeeper":
            continue
        clear: list[tuple[float, str]] = []
        for point in track.points:
            # A box in contact is still clear: it was read on its own
            # unshared pixels with the people in front masked out.
            if not point.color_scores:
                continue
            reading = read(point)
            if reading != "unknown":
                clear.append((point.clip_seconds, reading))
        for point in track.points:
            if id(point) not in overlapped and point.team != "unknown":
                continue
            own_reading = (
                read(point) if point.color_scores else "unknown"
            )
            if own_reading != "unknown":
                if own_reading != point.team:
                    resolved += 1
                point.team = own_reading
                continue
            if not clear:
                continue
            nearest = sorted(
                clear, key=lambda item: abs(item[0] - point.clip_seconds)
            )[:clear_votes]
            counts = Counter(team for _, team in nearest)
            highest = max(counts.values())
            team = next(team for _, team in nearest if counts[team] == highest)
            if team != point.team:
                resolved += 1
            point.team = team

    part_boxes = _resolve_part_boxes(tracks, members_by_frame)
    resolved += len(part_boxes)

    total = sum(len(track.points) for track in tracks)
    return {
        "minimum_overlap_of_smaller_box": minimum_overlap,
        "contact_radius_heights": contact_radius_heights,
        "part_boxes": part_boxes,
        "learned_team_colors": {
            team: dict(zip(COLOR_VECTOR_NAMES, (round(v, 4) for v in centre)))
            for team, (centre, _) in (team_colors or {}).items()
        },
        "summary": {
            "points": total,
            "overlapped_points": len(overlapped),
            "teams_changed": resolved,
            "part_boxes": len(part_boxes),
            "unknown_left": sum(
                1
                for track in tracks
                for point in track.points
                if point.team == "unknown"
            ),
        },
        "frames": [
            {
                "source_frame": frame["source_frame"],
                "clip_seconds": frame["clip_seconds"],
                "groups": [
                    [
                        {
                            "track_id": track.track_id,
                            "team": point.team,
                            "x1": point.x1,
                            "y1": point.y1,
                            "x2": point.x2,
                            "y2": point.y2,
                        }
                        for track, point in group
                    ]
                    for group in frame["groups"]
                ],
            }
            for frame in frames
        ],
    }


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
        # Red kits carry white trim; a saturated warm crop with no white is a
        # high-visibility orange vest (steward or ballboy), not a player.
        if warm >= 0.2 and white < 0.05:
            return "official"
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
    colors_read: bool = False,
) -> dict[str, tuple[list[float], list[float]]]:
    team_colors: dict[str, tuple[list[float], list[float]]] = {}
    if not colors_read:
        team_colors = _read_point_colors(
            [point for track in tracks for point in track.points],
            video,
            team_profile=team_profile,
        )
    _settle_track_teams(tracks)
    return team_colors


def _read_point_colors(
    points: Sequence[PlayerPoint],
    video: Path,
    *,
    team_profile: str,
) -> dict[str, tuple[list[float], list[float]]]:
    """Read each box's own jersey colour and set its per-frame team.

    Returns the team colours learned from this clip (see
    ``learn_team_colors``); every read box takes the closest one.
    """
    samples_by_frame: dict[int, list[PlayerPoint]] = defaultdict(list)
    for point in points:
        samples_by_frame[point.source_frame].append(point)
    if not samples_by_frame:
        return {}
    expected_height = _expected_person_heights(points)

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
            merged = _merged_box_ids(frame_samples)
            occluders = [other for other in frame_samples if id(other) not in merged]
            for point in frame_samples:
                if _is_cut_off(point, expected_height):
                    # Too short to contain the shirt; the track's clear
                    # frames decide its team instead.
                    continue
                features = _jersey_features(frame, point, occluders)
                if features is not None:
                    point.color_scores = {
                        key: round(value, 4) for key, value in features.items()
                    }
                    point.team = classify_color_scores(
                        features, team_profile=team_profile
                    )
    finally:
        capture.release()
    team_colors = learn_team_colors(points, team_profile=team_profile)
    for frame_samples in samples_by_frame.values():
        for point in frame_samples:
            if point.color_scores:
                point.team = nearest_team_color(
                    point.color_scores,
                    team_colors,
                    overlapped=any(
                        other is not point
                        and _box_overlap_of_smaller(point, other) >= CROWD_BOX_OVERLAP
                        for other in frame_samples
                    ),
                )
    return team_colors


HEIGHT_CHANGE_COST = 0.5
PIECE_BOX_HEIGHT_SHARE = 0.6
# Two players side by side in one merged box are each about half its width.
PIECE_BOX_WIDTH_SHARE = 0.4
PIECE_BOX_CONTAINMENT = 0.8
# A kit is a shirt and shorts; each is read on its own band.
KIT_PARTS = {"shirt": (0.12, 0.45), "shorts": (0.45, 0.70)}
COLOR_FEATURES = ("blue", "white", "dark", "warm", "yellow")
MINIMUM_TEAM_COLOR_SAMPLES = 20
# Share of the smaller box covered by another player's box: they overlap.
CROWD_BOX_OVERLAP = 0.3
STILL_OBJECT_MOVEMENT_HEIGHTS = 0.5


def _is_still_object(track: PlayerTrack) -> bool:
    """A box that never moves and never shows a shirt is not a person.

    YOLO sometimes calls an object (a bag in the goal net, a post) a person.
    A person on the pitch either moves or has a readable shirt; a track with
    neither, whose feet stay within half a body height, is dropped.
    """
    if track.role == "goalkeeper":
        return False
    if any(point.color_scores for point in track.points):
        return False
    heights = [point.y2 - point.y1 for point in track.points]
    body_height = median(heights)
    first_x, first_y = track.points[0].foot
    return all(
        hypot(point.foot[0] - first_x, point.foot[1] - first_y)
        <= STILL_OBJECT_MOVEMENT_HEIGHTS * body_height
        for point in track.points
    )


COLOR_VECTOR_NAMES = tuple(
    f"{part}_{key}" for part in KIT_PARTS for key in COLOR_FEATURES
)


def _color_vector(scores: dict[str, float]) -> list[float]:
    """A box's kit: shirt and shorts colour mixes, read separately.

    Bright and shaded yellow are one colour. A part that could not be read
    (hidden behind someone) falls back to the whole-kit reading.
    """
    vector: list[float] = []
    for part in KIT_PARTS:
        prefix = f"{part}_" if f"{part}_dark" in scores else ""
        mix = {key: scores.get(prefix + key, 0.0) for key in COLOR_FEATURES}
        mix["yellow"] += scores.get(prefix + "shaded_yellow", 0.0)
        vector.extend(mix[key] for key in COLOR_FEATURES)
    return vector


def learn_team_colors(
    points: Sequence[PlayerPoint], *, team_profile: str
) -> dict[str, tuple[list[float], list[float]]]:
    """Learn each team's colour mix from the boxes this clip reads clearly.

    A box that the fixed colour limits read as one team is a clear example of
    that team. The average mix of those examples is the team's colour in this
    clip's light; the spread of all clear examples scales each measure.
    """
    examples: dict[str, list[list[float]]] = defaultdict(list)
    for point in points:
        if not point.color_scores:
            continue
        team = classify_color_scores(point.color_scores, team_profile=team_profile)
        if team != "unknown":
            examples[team].append(_color_vector(point.color_scores))
    examples = {
        team: rows
        for team, rows in examples.items()
        if len(rows) >= MINIMUM_TEAM_COLOR_SAMPLES
    }
    if not examples:
        return {}
    every = np.array([row for rows in examples.values() for row in rows])
    spread = (every.std(axis=0) + 1e-6).tolist()
    return {
        team: (np.array(rows).mean(axis=0).tolist(), spread)
        for team, rows in examples.items()
    }


def nearest_team_color(
    scores: dict[str, float],
    team_colors: dict[str, tuple[list[float], list[float]]],
    *,
    overlapped: bool = False,
) -> str:
    """The learned team whose colour mix is closest to this box's reading.

    In a box that overlaps another player's box, a shirt of one team over
    shorts of the other is two players: the shorts belong to the one in
    front, so the shirt is this box's player.
    """
    if not team_colors:
        return "unknown"
    reading = np.array(_color_vector(scores))

    def nearest(part: slice) -> str:
        return min(
            team_colors,
            key=lambda team: float(
                np.linalg.norm(
                    (reading[part] - np.array(team_colors[team][0])[part])
                    / np.array(team_colors[team][1])[part]
                )
            ),
        )

    if overlapped and "shirt_dark" in scores and "shorts_dark" in scores:
        size = len(COLOR_FEATURES)
        shirt = nearest(slice(0, size))
        if shirt != nearest(slice(size, 2 * size)):
            return shirt
    return nearest(slice(None))


def _height_cell(point: PlayerPoint) -> tuple[int, int]:
    return (
        int(point.y2 // PERSON_HEIGHT_BAND_PIXELS),
        int(((point.x1 + point.x2) / 2) // PERSON_HEIGHT_COLUMN_PIXELS),
    )


def _expected_person_heights(
    points: Sequence[PlayerPoint],
) -> dict[tuple[int, int], float]:
    """Median box height of people whose feet stand in the same image cell.

    The cell is both a row and a column band, because in a panorama people at
    the same image row look smaller at the sides than in the middle.
    """
    by_cell: dict[tuple[int, int], list[float]] = defaultdict(list)
    for point in points:
        by_cell[_height_cell(point)].append(point.height)
    return {
        cell: median(heights)
        for cell, heights in by_cell.items()
        if len(heights) >= PERSON_HEIGHT_MINIMUM_SAMPLES
    }


def _is_cut_off(
    point: PlayerPoint, expected_height: dict[tuple[int, int], float]
) -> bool:
    expected = expected_height.get(_height_cell(point))
    return expected is not None and point.height < CUT_OFF_HEIGHT_SHARE * expected


def _settle_track_teams(tracks: list[PlayerTrack]) -> None:
    tracks[:] = split_tracks_on_sustained_team_change(tracks)
    for track in tracks:
        for point in track.points:
            point.kit_team = point.team
        samples = [point.color_scores for point in track.points if point.color_scores]
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


def split_tracks_on_sustained_team_change(
    tracks: list[PlayerTrack],
    *,
    consecutive_votes: int = 4,
    window_size: int = 7,
) -> list[PlayerTrack]:
    """Split a track where its raw kit votes switch to the other outfield team.

    A merged or overlapping box can carry a track identity from one player to
    a nearby opponent. When ``consecutive_votes`` known kit votes in a row
    contradict the track's causal team, the track is treated as a new player
    from the first contradicting vote. Expects raw per-point labels in
    ``point.team``.
    """
    next_id = max((track.track_id for track in tracks), default=0) + 1
    result: list[PlayerTrack] = []
    for track in tracks:
        remaining = track.points
        first = True
        while remaining:
            cut = _sustained_team_change_index(
                remaining, consecutive_votes, window_size
            )
            part = remaining if cut is None else remaining[:cut]
            remaining = [] if cut is None else remaining[cut:]
            if first:
                result.append(
                    PlayerTrack(track.track_id, part, track.team, track.color_scores, track.role)
                )
                first = False
            else:
                result.append(PlayerTrack(next_id, part, role=track.role))
                next_id += 1
    return result


def _sustained_team_change_index(
    points: list[PlayerPoint], consecutive_votes: int, window_size: int
) -> int | None:
    history: deque[str] = deque(maxlen=window_size)
    current = "unknown"
    run: list[int] = []
    # The team the track had when the contradicting run began. The window
    # majority may flip during the run; the run still contradicts this team.
    anchor = "unknown"
    for index, point in enumerate(points):
        vote = point.team
        if vote == "unknown":
            continue
        if run and vote == anchor:
            run = []
        if run and vote != anchor and vote in OUTFIELD_TEAMS:
            run.append(index)
        elif current != "unknown" and vote != current and vote in OUTFIELD_TEAMS:
            anchor = current
            run = [index]
        if len(run) >= consecutive_votes and run[0] > 0:
            return run[0]
        history.append(vote)
        counts = Counter(history)
        highest = max(counts.values())
        leaders = {team for team, count in counts.items() if count == highest}
        if current not in leaders:
            current = next(team for team in reversed(history) if team in leaders)
    return None


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


MINIMUM_UNSHARED_JERSEY_SHARE = 0.25
MERGED_BOX_CONTAINMENT = 0.6
TEAM_HISTORY_POINTS = 5
TEAM_HISTORY_AGREEMENT = 4
PERSON_HEIGHT_BAND_PIXELS = 20
PERSON_HEIGHT_COLUMN_PIXELS = 200
PERSON_HEIGHT_MINIMUM_SAMPLES = 20
CUT_OFF_HEIGHT_SHARE = 0.6
# Height bands of a box (share of its height from the top) read as the kit.
JERSEY_CROP_TOP = 0.12
JERSEY_CROP_BOTTOM = 0.58
PLAYER_TEAMS_BY_PROFILE = {
    "red-black": frozenset({"red", "black"}),
    "blue-white": frozenset({"blue", "white"}),
}


def _merged_box_ids(points: Sequence[PlayerPoint]) -> set[int]:
    """Return boxes that each enclose two or more other boxes in the frame.

    Such a box is drawn around a group of people rather than one person, so it
    must not count as a person standing in front of the people inside it.
    """
    merged: set[int] = set()
    for point in points:
        inside = sum(
            1
            for other in points
            if other is not point
            and _area(other) < _area(point)
            and _box_overlap_of_smaller(point, other) >= MERGED_BOX_CONTAINMENT
        )
        if inside >= 2:
            merged.add(id(point))
    return merged


def _area(point: PlayerPoint) -> float:
    return max(0.0, point.x2 - point.x1) * max(0.0, point.y2 - point.y1)


def _jersey_features(
    frame: np.ndarray,
    point: PlayerPoint,
    occluders: Iterable[PlayerPoint] = (),
) -> dict[str, float] | None:
    """Measure kit colours on the jersey pixels that belong to this person.

    Pixels covered by a person standing in front (a lower foot is nearer the
    camera) show that other person, so they are left out. When too little of
    the jersey remains visible, there is no reading.
    """
    occluders = list(occluders)
    scores = _kit_shares(frame, point, occluders, JERSEY_CROP_TOP, JERSEY_CROP_BOTTOM)
    if scores is None:
        return None
    for part, (top, bottom) in KIT_PARTS.items():
        part_scores = _kit_shares(frame, point, occluders, top, bottom)
        if part_scores is not None:
            scores.update(
                {f"{part}_{key}": share for key, share in part_scores.items()}
            )
    return scores


def _kit_shares(
    frame: np.ndarray,
    point: PlayerPoint,
    occluders: Sequence[PlayerPoint],
    top: float,
    bottom: float,
) -> dict[str, float] | None:
    """Kit colour shares in one height band of the box (0 = top, 1 = feet)."""
    crop = _jersey_crop(frame, point, top, bottom)
    if crop is None:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    own = np.ones(hue.shape, dtype=bool)
    crop_x1, crop_y1 = _jersey_crop_origin(point, top)
    for other in occluders:
        if other is point or other.y2 <= point.y2:
            continue
        left = max(0, int(other.x1) - crop_x1)
        right = min(own.shape[1], int(other.x2) - crop_x1)
        upper = max(0, int(other.y1) - crop_y1)
        lower = min(own.shape[0], int(other.y2) - crop_y1)
        if right > left and lower > upper:
            own[upper:lower, left:right] = False
    if own.mean() < MINIMUM_UNSHARED_JERSEY_SHARE:
        return None

    def share(mask: np.ndarray) -> float:
        return float(np.mean(mask[own]))

    # A strongly yellow pixel in shadow is a yellow kit, not a black one.
    shaded_yellow = (
        (value < 80) & (hue >= 15) & (hue <= 35) & (saturation >= 130)
    )
    return {
        "blue": share((hue >= 90) & (hue <= 135) & (saturation > 70)),
        "white": share((saturation < 60) & (value > 135)),
        "dark": share((value < 80) & ~shaded_yellow),
        "warm": share(
            ((hue < 15) | (hue > 165)) & (saturation > 80) & (value > 100)
        ),
        "yellow": share(
            (hue >= 15) & (hue <= 40) & (saturation > 80) & (value > 100)
        ),
        "shaded_yellow": share(shaded_yellow),
    }


def _jersey_crop_origin(
    point: PlayerPoint, top: float = 0.12
) -> tuple[int, int]:
    width = point.x2 - point.x1
    height = point.y2 - point.y1
    return (
        max(0, int(point.x1 + width * 0.2)),
        max(0, int(point.y1 + height * top)),
    )


def _jersey_crop(
    frame: np.ndarray,
    point: PlayerPoint,
    top: float = 0.12,
    bottom: float = 0.58,
) -> np.ndarray | None:
    width = point.x2 - point.x1
    height = point.y2 - point.y1
    x1 = max(0, int(point.x1 + width * 0.2))
    x2 = min(frame.shape[1], int(point.x2 - width * 0.2))
    y1 = max(0, int(point.y1 + height * top))
    y2 = min(frame.shape[0], int(point.y1 + height * bottom))
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


def _calibrated_pitch_boundary(
    calibration_path: Path, frame_size: tuple[float, float]
) -> tuple[tuple[float, float], ...]:
    """Calibrated pitch lines converted to the video frame size of the boxes."""
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    sx, sy = scale_factors(calibration, frame_size)
    return tuple((x * sx, y * sy) for x, y in load_pitch_boundary(calibration_path))


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
