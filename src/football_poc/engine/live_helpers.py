from __future__ import annotations

from football_poc.engine.common import *

def _live__nearby_ball_team_track(
    players: Iterable[dict[str, Any]],
    ball: dict[str, Any],
    team: str,
    *,
    maximum_box_distance_heights: float,
    locally_confirmed_team_track_ids: set[int] | None = None,
) -> int | None:
    team_profile = (
        "red-black"
        if team in {"red", "black"}
        else "blue-white"
    )
    candidates: list[tuple[float, int]] = []
    for player in players:
        color_scores = player.get("color_scores")
        local_team = (
            classify_color_scores(color_scores, team_profile=team_profile)
            if isinstance(color_scores, dict)
            else "unknown"
        )
        track_id = int(player["track_id"])
        player_team = (
            team
            if track_id in (locally_confirmed_team_track_ids or set())
            else local_team
            if local_team in {"red", "black", "blue", "white"}
            else str(player.get("team"))
        )
        if player_team != team:
            continue
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
        distance = hypot(horizontal, vertical) / height
        if distance <= maximum_box_distance_heights:
            candidates.append((distance, track_id))
    return min(candidates)[1] if candidates else None

def _live__controlled_contact_team_track(
    players: Iterable[dict[str, Any]],
    ball: dict[str, Any],
    team: str,
    motion: dict[tuple[int, int], tuple[float, float]],
    *,
    minimum_speed_pixels_per_second: float,
    maximum_direction_cosine: float = 0.25,
    maximum_box_distance_heights: float = 0.4,
    locally_confirmed_team_track_ids: set[int] | None = None,
) -> int | None:
    evidence = motion.get(
        (int(ball["track_id"]), int(ball["source_frame"]))
    )
    if (
        evidence is None
        or evidence[0] < minimum_speed_pixels_per_second
        or evidence[1] > maximum_direction_cosine
    ):
        return None
    stable_team_players = [
        player
        for player in players
        if (
            str(player.get("team")) == team
            or int(player["track_id"])
            in (locally_confirmed_team_track_ids or set())
        )
    ]
    return _live__nearby_ball_team_track(
        stable_team_players,
        ball,
        team,
        maximum_box_distance_heights=maximum_box_distance_heights,
        locally_confirmed_team_track_ids=locally_confirmed_team_track_ids,
    )

def _live__controlled_contact_with_local_identity(
    players: dict[int, list[dict[str, Any]]],
    ball: dict[str, Any],
    team: str,
    motion: dict[tuple[int, int], tuple[float, float]],
    *,
    minimum_speed_pixels_per_second: float,
) -> int | None:
    source_frame = int(ball["source_frame"])
    receiver_track_id = _live__controlled_contact_team_track(
        players.get(source_frame, []),
        ball,
        team,
        motion,
        minimum_speed_pixels_per_second=minimum_speed_pixels_per_second,
    )
    if receiver_track_id is not None:
        return receiver_track_id
    local_team_tracks = _live__locally_confirmed_team_track_ids(
        players,
        team,
        float(ball["clip_seconds"]),
    )
    return _live__controlled_contact_team_track(
        players.get(source_frame, []),
        ball,
        team,
        motion,
        minimum_speed_pixels_per_second=minimum_speed_pixels_per_second,
        locally_confirmed_team_track_ids=local_team_tracks,
    )

def _live__projected_terminal_contact(
    players: dict[int, list[dict[str, Any]]],
    ball: dict[str, Any],
    *,
    maximum_projection_seconds: float = 0.24,
    maximum_contact_distance_heights: float = 0.05,
    minimum_opponent_margin_heights: float = 0.01,
) -> tuple[str, int] | None:
    timestamp = float(ball["clip_seconds"])
    points_by_track: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame_players in players.values():
        for player in frame_players:
            if float(player["clip_seconds"]) <= timestamp:
                points_by_track[int(player["track_id"])].append(player)

    candidates: list[tuple[float, str, int]] = []
    ball_radius = max(1.0, float(ball.get("box_diagonal") or 0.0) / 2.0)
    for track_id, track_points in points_by_track.items():
        ordered = sorted(
            track_points,
            key=lambda point: float(point["clip_seconds"]),
        )
        if len(ordered) < 2:
            continue
        previous, current = ordered[-2:]
        current_seconds = float(current["clip_seconds"])
        prior_seconds = float(previous["clip_seconds"])
        projection_seconds = timestamp - current_seconds
        observation_seconds = current_seconds - prior_seconds
        if (
            projection_seconds < 0
            or projection_seconds > maximum_projection_seconds
            or observation_seconds <= 0
            or observation_seconds > 0.6
        ):
            continue
        team = str(current.get("team"))
        if team not in {"red", "black", "blue", "white"}:
            continue
        previous_center = (
            float(previous["x1"]) + float(previous["x2"])
        ) / 2.0
        current_center = (
            float(current["x1"]) + float(current["x2"])
        ) / 2.0
        projected_center = current_center + (
            (current_center - previous_center)
            * projection_seconds
            / observation_seconds
        )
        projected_feet = float(current["y2"]) + (
            (float(current["y2"]) - float(previous["y2"]))
            * projection_seconds
            / observation_seconds
        )
        width = max(1.0, float(current["x2"]) - float(current["x1"]))
        height = max(1.0, float(current["y2"]) - float(current["y1"]))
        projected_x1 = projected_center - width / 2.0
        projected_x2 = projected_center + width / 2.0
        projected_y1 = projected_feet - height
        horizontal = max(
            projected_x1 - float(ball["x"]) - ball_radius,
            0.0,
            float(ball["x"]) - projected_x2 - ball_radius,
        )
        vertical = max(
            projected_y1 - float(ball["y"]) - ball_radius,
            0.0,
            float(ball["y"]) - projected_feet - ball_radius,
        )
        candidates.append(
            (hypot(horizontal, vertical) / height, team, track_id)
        )

    if not candidates:
        return None
    candidates.sort()
    distance, team, track_id = candidates[0]
    if distance > maximum_contact_distance_heights:
        return None
    opponent_distance = next(
        (
            candidate_distance
            for candidate_distance, candidate_team, _ in candidates
            if candidate_team != team
        ),
        float("inf"),
    )
    if opponent_distance - distance < minimum_opponent_margin_heights:
        return None
    return team, track_id

def _live__locally_confirmed_team_track_ids(
    players: dict[int, list[dict[str, Any]]],
    team: str,
    timestamp: float,
    *,
    evidence_window_seconds: float = 0.4,
    minimum_evidence_points: int = 2,
) -> set[int]:
    team_profile = (
        "red-black"
        if team in {"red", "black"}
        else "blue-white"
    )
    eligible_teams = set(team_profile.split("-"))
    labels_by_track: dict[int, list[str]] = defaultdict(list)
    for frame_players in players.values():
        for player in frame_players:
            if (
                abs(float(player["clip_seconds"]) - timestamp)
                > evidence_window_seconds
            ):
                continue
            color_scores = player.get("color_scores")
            if not isinstance(color_scores, dict):
                continue
            label = classify_color_scores(
                color_scores,
                team_profile=team_profile,
            )
            if label in eligible_teams:
                labels_by_track[int(player["track_id"])].append(label)
    confirmed: set[int] = set()
    for track_id, labels in labels_by_track.items():
        counts = Counter(labels)
        if (
            counts[team] >= minimum_evidence_points
            and counts[team]
            > sum(
                count
                for label, count in counts.items()
                if label != team
            )
        ):
            confirmed.add(track_id)
    return confirmed
