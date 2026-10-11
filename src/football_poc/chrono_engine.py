"""Chronological events engine (experimental, runs next to the old engine).

The clip is played through once, frame by frame, in time order. At every
sampled frame the engine first updates match state (Law 9: ball in or out of
play), then who controls the ball, and only then writes an event when
control changes. A decision is never rewritten by a later pass; the only
look-ahead is the short confirmation that a player really controls the
ball.

Runtime inputs only: the tracker's player boxes and teams, the ball points
and the calibrated pitch. Manual review events are never read here.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from math import acos, degrees, hypot
from pathlib import Path
from typing import Any, Iterable

from football_poc.pitch_geometry import signed_pitch_distance

TEAMS = frozenset({"red", "black"})


@dataclass(frozen=True)
class ChronoSettings:
    outside_margin_px: float = 12.0
    control_radius_heights: float = 0.8
    duel_margin_heights: float = 0.4
    control_confirm_samples: int = 2
    control_confirm_gap_seconds: float = 0.5
    stopped_speed_px_per_second: float = 60.0
    restart_speed_px_per_second: float = 200.0
    dead_ball_start_seconds: float = 1.0
    identity_swap_radius_heights: float = 0.75
    identity_swap_gap_seconds: float = 0.5
    touch_turn_degrees: float = 40.0
    touch_speed_ratio: float = 2.0
    touch_radius_heights: float = 0.35
    touch_neighbour_gap_seconds: float = 0.3
    lofted_min_rise_heights: float = 0.3
    lofted_min_fall_ratio: float = 0.3
    lofted_noise_px: float = 3.0
    rolling_turn_degrees: float = 20.0
    rolling_min_speed_ratio: float = 0.7
    rolling_max_speed_ratio: float = 1.15


@dataclass
class MatchStateChange:
    seconds: float
    state: str
    reason: str


@dataclass
class _Control:
    track_id: int
    team: str
    first_seconds: float
    last_seconds: float
    feet: tuple[float, float]
    height: float
    samples: int = 1


@dataclass
class ChronoResult:
    events: list[dict[str, Any]] = field(default_factory=list)
    match_state: list[MatchStateChange] = field(default_factory=list)


SEEN_BALL_STATES = frozenset({"observed", "visually_reacquired"})


def _best_ball(points: list[dict[str, Any]]) -> dict[str, Any] | None:
    # The ball tracker's status decides: only frames where it saw the ball
    # count. Trajectory estimates, hidden and out-of-play frames do not.
    usable = [p for p in points if p.get("state", "observed") in SEEN_BALL_STATES]
    if not usable:
        return None
    return max(usable, key=lambda p: float(p.get("confidence", 0)))


def _feet(box: dict[str, Any]) -> tuple[float, float]:
    return ((float(box["x1"]) + float(box["x2"])) / 2, float(box["y2"]))


def _closest_controller(
    ball: tuple[float, float],
    boxes: Iterable[dict[str, Any]],
    radius_heights: float,
    duel_margin_heights: float = 0.4,
) -> dict[str, Any] | None:
    """The one player who clearly has the ball, or None.

    During a duel an opponent is about as close to the ball as the nearest
    player; nobody has won the ball yet, so nobody controls it.
    """
    ranked: list[tuple[float, dict[str, Any]]] = []
    for box in boxes:
        if box.get("role") == "official" or box.get("team") not in TEAMS:
            continue
        height = float(box["y2"]) - float(box["y1"])
        if height <= 0:
            continue
        fx, fy = _feet(box)
        ranked.append((hypot(ball[0] - fx, ball[1] - fy) / height, box))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0])
    ratio, best = ranked[0]
    if ratio > radius_heights:
        return None
    for other_ratio, other in ranked[1:]:
        if other["team"] != best["team"]:
            if other_ratio - ratio < duel_margin_heights:
                return None
            break
    return best


def _box_distance(ball: tuple[float, float], box: dict[str, Any]) -> float:
    """Distance from the ball to the nearest point of the player, head to feet."""
    dx = max(float(box["x1"]) - ball[0], 0.0, ball[0] - float(box["x2"]))
    dy = max(float(box["y1"]) - ball[1], 0.0, ball[1] - float(box["y2"]))
    return hypot(dx, dy)


def _ball_deflected(
    before: tuple[float, float, float],
    at: tuple[float, float, float],
    after: tuple[float, float, float],
    settings: ChronoSettings,
) -> bool:
    """Law 12 touch evidence: the ball clearly turns or changes speed here."""
    v1 = (at[1] - before[1], at[2] - before[2])
    v2 = (after[1] - at[1], after[2] - at[2])
    d1, d2 = at[0] - before[0], after[0] - at[0]
    if d1 <= 0 or d2 <= 0:
        return False
    s1, s2 = hypot(*v1) / d1, hypot(*v2) / d2
    if s1 < settings.stopped_speed_px_per_second or s2 < settings.stopped_speed_px_per_second:
        return False
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (hypot(*v1) * hypot(*v2))
    turn = degrees(acos(max(-1.0, min(1.0, cos))))
    ratio = max(s1, s2) / min(s1, s2)
    return turn >= settings.touch_turn_degrees or ratio >= settings.touch_speed_ratio


def _rolling_through(
    before: tuple[float, float, float],
    at: tuple[float, float, float],
    after: tuple[float, float, float],
    settings: ChronoSettings,
) -> bool:
    """The ball rolls on here unchanged: same line, same gently slowing pace.

    A player the ball merely rolls past has not received it; receiving it
    stops, slows, turns or kicks the ball on.
    """
    v1 = (at[1] - before[1], at[2] - before[2])
    v2 = (after[1] - at[1], after[2] - at[2])
    d1, d2 = at[0] - before[0], after[0] - at[0]
    if d1 <= 0 or d2 <= 0:
        return False
    s1, s2 = hypot(*v1) / d1, hypot(*v2) / d2
    if s1 < settings.stopped_speed_px_per_second or s2 < settings.stopped_speed_px_per_second:
        return False
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (hypot(*v1) * hypot(*v2))
    turn = degrees(acos(max(-1.0, min(1.0, cos))))
    ratio = s2 / s1
    return (
        turn < settings.rolling_turn_degrees
        and settings.rolling_min_speed_ratio <= ratio <= settings.rolling_max_speed_ratio
    )


def _toucher(
    ball: tuple[float, float],
    boxes: Iterable[dict[str, Any]],
    settings: ChronoSettings,
) -> dict[str, Any] | None:
    """The one player whose body (head to feet) is at a deflected ball.

    A touch may be with any part of the body except the hands (a header,
    for example), so the whole box counts, not just the feet. An opponent
    about as close means a contested ball, so nobody is credited.
    """
    ranked: list[tuple[float, dict[str, Any]]] = []
    for box in boxes:
        if box.get("role") == "official" or box.get("team") not in TEAMS:
            continue
        height = float(box["y2"]) - float(box["y1"])
        if height <= 0:
            continue
        ranked.append((_box_distance(ball, box) / height, box))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0])
    ratio, best = ranked[0]
    if ratio > settings.touch_radius_heights:
        return None
    for other_ratio, other in ranked[1:]:
        if other["team"] != best["team"]:
            if other_ratio - ratio < settings.duel_margin_heights:
                return None
            break
    return best


def _lofted_samples(
    track: list[tuple[int, float, float, float]],
    players: dict[int, list[dict[str, Any]]],
    settings: ChronoSettings,
) -> set[int]:
    """Indices of ball samples in flight: the ball rises, then falls, in the image.

    A ball in the air is drawn at the feet of whoever stands behind it, so it
    cannot be controlled at the feet there; only a body touch (for example a
    header) counts. The flight lasts from the rise until the ball has come
    back down to the level it rose from, or stops falling. The ball must
    fall back by a clear share of its rise; otherwise it was rolling away
    from the camera.
    """
    lofted: set[int] = set()
    noise = settings.lofted_noise_px
    for peak in range(1, len(track) - 1):
        y = track[peak][3]
        if not (track[peak - 1][3] > y + noise or track[peak + 1][3] > y + noise):
            continue
        if track[peak - 1][3] < y or track[peak + 1][3] < y:
            continue
        start = peak
        while start > 0 and track[start - 1][3] >= track[start][3] - noise:
            start -= 1
        end = peak
        while (
            end < len(track) - 1
            and track[end + 1][3] >= track[end][3] - noise
            and track[end][3] < track[start][3]
        ):
            end += 1
        while start < peak and track[start + 1][3] > track[start][3] - noise:
            start += 1
        while end > peak and track[end - 1][3] > track[end][3] - noise:
            end -= 1
        boxes = [
            box
            for box in players.get(track[peak][0], [])
            if box.get("team") in TEAMS
            and box.get("role") != "official"
            and float(box["y2"]) > float(box["y1"])
        ]
        if not boxes:
            continue
        nearest = min(boxes, key=lambda box: _box_distance((track[peak][2], y), box))
        height = float(nearest["y2"]) - float(nearest["y1"])
        rise = track[start][3] - y
        fall = track[end][3] - y
        if min(rise, fall) < settings.lofted_min_rise_heights * height:
            continue
        # A ball in the air comes back down. A ball rolling away from the
        # camera only climbs in the picture, so a tiny dip after a long climb
        # is not a flight.
        if fall < settings.lofted_min_fall_ratio * rise:
            continue
        lofted.update(range(start + 1, end))
    return lofted


def _unbroken(path: list[tuple[float, float, float]], stopped: float) -> bool:
    """True when the ball kept moving and never turned back along the path."""
    steps = []
    for (t0, x0, y0), (t1, x1, y1) in zip(path, path[1:]):
        if t1 <= t0:
            continue
        steps.append((x1 - x0, y1 - y0, hypot(x1 - x0, y1 - y0) / (t1 - t0)))
    if len(steps) < 2:
        return False
    if any(speed < stopped for _, _, speed in steps):
        return False
    for a, b in zip(steps, steps[1:]):
        if a[0] * b[0] + a[1] * b[1] < 0:
            return False
    return True


def _dead_ball_at_start(
    balls: dict[int, list[dict[str, Any]]], settings: ChronoSettings
) -> bool:
    """Laws 8 and 16: a ball lying still when the segment starts is dead.

    In live play the ball keeps moving; a ball that has not moved at all
    during the opening second is set down for a restart (for example a goal
    kick). Play only begins once it is kicked and clearly moves.
    """
    opening = [
        (float(ball["clip_seconds"]), float(ball["x"]), float(ball["y"]))
        for frame in sorted(balls)
        if (ball := _best_ball(balls[frame])) is not None
    ]
    if not opening:
        return False
    first_seconds = opening[0][0]
    window = [
        point
        for point in opening
        if point[0] - first_seconds <= settings.dead_ball_start_seconds
    ]
    if len(window) < 3 or window[-1][0] - first_seconds < settings.dead_ball_start_seconds:
        return False
    return all(
        hypot(b[1] - a[1], b[2] - a[2]) / (b[0] - a[0])
        < settings.stopped_speed_px_per_second
        for a, b in zip(window, window[1:])
        if b[0] > a[0]
    )


def _ball_out_turnover(result: ChronoResult, owner: "_Control | None", out_seconds: float) -> None:
    """Laws 15-17: every restart goes to the opponents of the team that last
    touched the ball, so a team whose controlled ball goes out loses it."""
    if owner is None:
        return
    result.events.append(
        {
            "event_type": "turnover_candidate",
            "clip_seconds": round(owner.last_seconds, 3),
            "completion_seconds": round(out_seconds, 3),
            "team": owner.team,
            "from_player_track_id": owner.track_id,
            "to_player_track_id": None,
            "details": "ball out of play; restart to the opponents",
        }
    )


def run_chronological(
    players: dict[int, list[dict[str, Any]]],
    balls: dict[int, list[dict[str, Any]]],
    boundary: tuple[tuple[float, float], ...],
    settings: ChronoSettings = ChronoSettings(),
    goal_areas: tuple[tuple[tuple[float, float], ...], ...] = (),
    out_of_play_seconds: Iterable[float] = (),
) -> ChronoResult:
    """Walk the ball samples in time order.

    ``out_of_play_seconds`` are the times the ball tracker saw the ball out of
    play (Law 9). Those frames have no live ball position, so they arrive here
    as times only.
    """
    result = ChronoResult()
    tracker_out = sorted(float(s) for s in out_of_play_seconds)
    next_out = 0
    state = (
        "out_of_play"
        if _dead_ball_at_start(balls, settings)
        else "in_play"
    )
    result.match_state.append(
        MatchStateChange(
            0.0,
            state,
            "segment_start_dead_ball_restart_pending"
            if state == "out_of_play"
            else "segment_start",
        )
    )
    owner: _Control | None = None
    candidate: _Control | None = None
    exit_path: list[tuple[float, float, float]] | None = None
    previous: tuple[float, float, float] | None = None
    previous_frame: int | None = None
    last_seconds = 0.0

    track: list[tuple[int, float, float, float]] = [
        (frame, float(b["clip_seconds"]), float(b["x"]), float(b["y"]))
        for frame in sorted(balls)
        if (b := _best_ball(balls[frame])) is not None
    ]
    lofted = _lofted_samples(track, players, settings)
    # Gap-filled positions are a straight guess, not evidence of a free roll.
    estimated = {
        index
        for index, (frame, *_rest) in enumerate(track)
        if (_best_ball(balls[frame]) or {}).get("source_attribution") == "interpolated"
    }
    for index, (frame, t, x, y) in enumerate(track):
        last_seconds = t
        inside = signed_pitch_distance((x, y), boundary) >= -settings.outside_margin_px

        # 1. Match state. The ball tracker's own out-of-play status comes first.
        went_out = None
        while next_out < len(tracker_out) and tracker_out[next_out] < t:
            if went_out is None:
                went_out = tracker_out[next_out]
            next_out += 1
        if went_out is not None and state == "in_play":
            state = "out_of_play"
            result.match_state.append(
                MatchStateChange(went_out, state, "ball_tracker_out_of_play")
            )
            _ball_out_turnover(result, owner, went_out)
            owner = candidate = None
            exit_path = None
        if state == "in_play":
            if not inside:
                if exit_path is None:
                    exit_path = [previous] if previous else []
                exit_path.append((t, x, y))
                if len(exit_path) >= 3 and not _unbroken(
                    exit_path, settings.stopped_speed_px_per_second
                ):
                    exit_seconds = exit_path[1][0] if previous else exit_path[0][0]
                    state = "out_of_play"
                    result.match_state.append(
                        MatchStateChange(exit_seconds, state, "ball_stopped_or_turned_outside")
                    )
                    _ball_out_turnover(result, owner, exit_seconds)
                    owner = candidate = None
                    exit_path = None
            elif exit_path is not None:
                exit_path.append((t, x, y))
                if not _unbroken(exit_path, settings.stopped_speed_px_per_second):
                    exit_seconds = exit_path[1][0] if len(exit_path) > 1 else t
                    result.match_state.append(
                        MatchStateChange(exit_seconds, "out_of_play", "ball_returned_after_stop")
                    )
                    result.match_state.append(
                        MatchStateChange(t, "in_play", "restart_ball_came_back_in")
                    )
                    owner = candidate = None
                exit_path = None
        elif inside and previous is not None and t > previous[0]:
            speed = hypot(x - previous[1], y - previous[2]) / (t - previous[0])
            if speed >= settings.restart_speed_px_per_second:
                state = "in_play"
                in_goal_area = any(
                    signed_pitch_distance((previous[1], previous[2]), area) >= 0
                    for area in goal_areas
                )
                result.match_state.append(
                    MatchStateChange(
                        previous[0],
                        state,
                        "goal_kick_taken" if in_goal_area else "restart_taken_type_unknown",
                    )
                )
                # Law 8/16/17: the player standing at the still ball takes the
                # restart, so the restart's team owns the ball as it is kicked.
                taker = _closest_controller(
                    (previous[1], previous[2]),
                    players.get(previous_frame, []),
                    settings.control_radius_heights,
                    settings.duel_margin_heights,
                )
                if taker is not None:
                    owner = _Control(
                        int(taker["track_id"]),
                        str(taker["team"]),
                        previous[0],
                        previous[0],
                        _feet(taker),
                        float(taker["y2"]) - float(taker["y1"]),
                        settings.control_confirm_samples,
                    )
                    candidate = None
        previous = (t, x, y)
        previous_frame = frame
        if state != "in_play" or exit_path is not None:
            continue

        # 2. Who controls the ball. A clear deflection at one player's body
        # is a touch on its own; otherwise control needs repeated checks at
        # the feet.
        touch = None
        rolling = False
        if 0 < index < len(track) - 1:
            before, after = track[index - 1][1:], track[index + 1][1:]
            if (
                t - before[0] <= settings.touch_neighbour_gap_seconds
                and after[0] - t <= settings.touch_neighbour_gap_seconds
            ):
                if _ball_deflected(before, (t, x, y), after, settings):
                    touch = _toucher((x, y), players.get(frame, []), settings)
                rolling = not estimated.intersection(
                    (index - 1, index, index + 1)
                ) and _rolling_through(before, (t, x, y), after, settings)
        if touch is None and index in lofted:
            continue
        box = touch or _closest_controller(
            (x, y),
            players.get(frame, []),
            settings.control_radius_heights,
            settings.duel_margin_heights,
        )
        if box is None:
            continue
        track_id, team = int(box["track_id"]), str(box["team"])
        height = float(box["y2"]) - float(box["y1"])
        if (
            candidate is not None
            and candidate.track_id == track_id
            and t - candidate.last_seconds <= settings.control_confirm_gap_seconds
        ):
            candidate.samples += 1
            candidate.last_seconds = t
            candidate.feet = _feet(box)
        else:
            if rolling and touch is None and (owner is None or owner.track_id != track_id):
                # The ball rolls past this player unchanged: not received yet.
                candidate = None
                continue
            candidate = _Control(track_id, team, t, t, _feet(box), height)
        if touch is not None:
            candidate.samples = max(candidate.samples, settings.control_confirm_samples)
        if candidate.samples < settings.control_confirm_samples:
            continue
        if owner is not None and owner.track_id == candidate.track_id:
            owner.last_seconds, owner.feet = t, candidate.feet
            continue

        # 3. Control changed: write the event.
        new = candidate
        if owner is not None:
            swap = (
                new.team == owner.team
                and new.first_seconds - owner.last_seconds <= settings.identity_swap_gap_seconds
                and hypot(new.feet[0] - owner.feet[0], new.feet[1] - owner.feet[1])
                <= settings.identity_swap_radius_heights * max(new.height, 1.0)
            )
            if not swap:
                same_team = new.team == owner.team
                result.events.append(
                    {
                        "event_type": "pass_candidate" if same_team else "turnover_candidate",
                        "clip_seconds": round(owner.last_seconds, 3),
                        "completion_seconds": round(new.first_seconds, 3),
                        "team": owner.team,
                        "from_player_track_id": owner.track_id,
                        "to_player_track_id": new.track_id,
                        "details": "chronological control change",
                    }
                )
        owner = _Control(new.track_id, new.team, new.first_seconds, t, new.feet, new.height, new.samples)

    result.match_state.append(MatchStateChange(last_seconds, state, "segment_end"))
    return result


def _scaled_goal_areas(
    calibration_path: Path, ball_tracks_path: Path, video: Path
) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Calibrated goal areas (Law 16 goal kicks), in the ball image space."""
    from football_poc.image_space import ball_coordinate_size, scale_factors, video_size

    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    sx, sy = scale_factors(
        calibration,
        ball_coordinate_size(
            json.loads(ball_tracks_path.read_text(encoding="utf-8")), video_size(video)
        ),
    )
    return tuple(
        tuple((x * sx, y * sy) for x, y in area) for area in goal_areas_from_calibration(calibration)
    )


def goal_areas_from_calibration(
    calibration: dict[str, Any],
) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Manually calibrated goal areas (Law 1), in calibration image space.

    Only marked ``{side}_goal_area`` polygons are used; a missing goal area
    is not guessed.
    """
    features = calibration.get("features", {})
    return tuple(
        tuple((float(x), float(y)) for x, y in features.get(f"{side}_goal_area", []))
        for side in ("left", "right")
        if len(features.get(f"{side}_goal_area", [])) >= 3
    )


def main() -> None:
    from football_poc.engine.ball_evidence import _load_ball_points
    from football_poc.engine.common import exclude_players_outside_pitch, scaled_pitch_boundary
    from football_poc.engine.pipeline import _load_player_points

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analytics_data", type=Path)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--pitch-calibration", type=Path, required=True)
    args = parser.parse_args()
    data: Path = args.analytics_data
    ball_path = data / "engine-ball-tracks.json"
    manifest = Path(json.loads(ball_path.read_text(encoding="utf-8"))["manifest"])
    boundary = scaled_pitch_boundary(args.pitch_calibration, ball_path, args.video)
    players = exclude_players_outside_pitch(
        _load_player_points(data / "player-tracks.json", manifest), boundary
    )
    # The ball tracker's per-frame status is required evidence: events are read
    # from the ball track, its statuses, the player tracks and their kits together.
    states_path = data.parent / "analytics-cache" / "ball-state-estimates.json"
    if not states_path.is_file():
        raise SystemExit(f"Ball-track status file is required: {states_path}")
    balls = _load_ball_points(ball_path, manifest, state_estimates_path=states_path)
    goal_areas = _scaled_goal_areas(args.pitch_calibration, ball_path, args.video)
    out_of_play_seconds = [
        float(item["clip_seconds"])
        for item in json.loads(states_path.read_text(encoding="utf-8")).get("states", [])
        if item.get("state") == "out_of_play"
    ]
    result = run_chronological(
        players, balls, boundary, goal_areas=goal_areas, out_of_play_seconds=out_of_play_seconds
    )
    (data / "predicted-events-chrono.json").write_text(
        json.dumps(result.events, indent=2), encoding="utf-8"
    )
    (data / "match-state-chrono.json").write_text(
        json.dumps([asdict(change) for change in result.match_state], indent=2),
        encoding="utf-8",
    )
    print(f"{len(result.events)} events, {len(result.match_state)} match-state changes")


if __name__ == "__main__":
    main()
