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
from math import acos, degrees, hypot, sqrt
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable

from football_poc.pitch_geometry import signed_pitch_distance

TEAMS = frozenset({"red", "black"})


@dataclass(frozen=True)
class ChronoSettings:
    outside_margin_px: float = 12.0
    control_radius_heights: float = 0.8
    duel_margin_heights: float = 0.4
    # The player who has the ball keeps it while still within reach, unless
    # a teammate is clearly closer: one camera draws a teammate standing
    # metres behind him right on top of him.
    owner_keep_margin_heights: float = 0.4
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
    # Every ball source places the ball with some wobble. A turn or speed-up
    # is a touch only when the change in movement is clearly larger than the
    # wobble the track itself shows (estimated from all its seen samples).
    touch_noise_multiple: float = 3.0
    noise_min_samples: int = 10
    # A ball in the air that hangs almost still and then leaves this many
    # times faster than "stopped", with a turn, was headed on.
    aerial_restart_speed_ratio: float = 3.0
    # Top share of a box that is the head.
    head_zone_share: float = 0.25
    # A ball in the air is contested only by an opponent standing at about
    # the same spot: feet within this many of the toucher's heights. The
    # camera draws players metres apart on top of each other.
    aerial_contest_feet_heights: float = 0.75
    # Physics: even a hard, high kick lands within about four seconds. A
    # longer run of in-flight labels is a ball resting high in the picture.
    max_flight_seconds: float = 4.0
    lofted_min_rise_heights: float = 0.3
    lofted_min_fall_ratio: float = 0.3
    lofted_noise_px: float = 3.0
    # A kicked ball climbs fast in the picture; a ground pass rolling away
    # from the camera climbs slowly.
    lofted_min_rise_px_per_second: float = 50.0
    rolling_turn_degrees: float = 20.0
    rolling_min_speed_ratio: float = 0.7
    rolling_max_speed_ratio: float = 1.15
    stretched_box_ratio: float = 1.3
    stretched_box_window_seconds: float = 0.5
    stretched_box_min_points: int = 5
    # A dribbler hides the ball behind his own body: across a short hidden
    # gap he covers the same path as the ball, players standing still do not.
    hidden_gap_max_seconds: float = 0.8
    hidden_reach_heights: float = 1.2
    hidden_min_ball_move_heights: float = 1.0
    hidden_max_offset_change_heights: float = 0.4
    # A ball that keeps one line before and after cannot step sideways in
    # between: a lone re-found sighting off that line is something else
    # (a boot, a sock), not the ball.
    off_line_max_gap_seconds: float = 0.8


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


def _estimate_ball(points: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The tracker's trajectory estimate for a frame where it did not see the ball."""
    if _best_ball(points) is not None:
        return None
    usable = [
        p for p in points if str(p.get("state", "")).startswith("trajectory_estimated")
    ]
    return max(usable, key=lambda p: float(p.get("confidence", 0))) if usable else None


def _best_ball(points: list[dict[str, Any]]) -> dict[str, Any] | None:
    # The ball tracker's status decides: only frames where it saw the ball
    # count. Trajectory estimates, hidden and out-of-play frames do not.
    usable = [p for p in points if p.get("state", "observed") in SEEN_BALL_STATES]
    if not usable:
        return None
    return max(usable, key=lambda p: float(p.get("confidence", 0)))


def _without_stretched_boxes(
    players: dict[int, list[dict[str, Any]]], settings: ChronoSettings
) -> dict[int, list[dict[str, Any]]]:
    """Drop boxes much taller than their own track's usual height.

    A box that suddenly grows (merged with a neighbour or stretched over the
    ball) no longer shows where that player's feet are, so it cannot be
    used to decide who is at the ball.
    """
    by_track: dict[Any, list[tuple[float, float, int]]] = {}
    for frame, boxes in players.items():
        for box in boxes:
            if box.get("clip_seconds") is None:
                continue
            by_track.setdefault(box.get("track_id"), []).append(
                (float(box["clip_seconds"]), float(box["y2"]) - float(box["y1"]), id(box))
            )
    stretched: set[int] = set()
    for rows in by_track.values():
        for seconds, height, key in rows:
            window = sorted(
                h
                for s, h, _ in rows
                if abs(s - seconds) <= settings.stretched_box_window_seconds
            )
            if len(window) < settings.stretched_box_min_points:
                continue
            middle = len(window) // 2
            median = (
                window[middle]
                if len(window) % 2
                else (window[middle - 1] + window[middle]) / 2
            )
            if height > settings.stretched_box_ratio * median:
                stretched.add(key)
    return {
        frame: [box for box in boxes if id(box) not in stretched]
        for frame, boxes in players.items()
    }


def _feet(box: dict[str, Any]) -> tuple[float, float]:
    return ((float(box["x1"]) + float(box["x2"])) / 2, float(box["y2"]))


def _owner_keeps(
    box: dict[str, Any],
    owner: "_Control",
    ball: tuple[float, float],
    boxes: Iterable[dict[str, Any]],
    settings: ChronoSettings,
) -> dict[str, Any]:
    """Keep the ball with its owner unless the teammate is clearly closer."""
    if str(box["team"]) != owner.team or int(box["track_id"]) == owner.track_id:
        return box

    def ratio(item: dict[str, Any]) -> float:
        fx, fy = _feet(item)
        return hypot(ball[0] - fx, ball[1] - fy) / max(float(item["y2"]) - float(item["y1"]), 1.0)

    for item in boxes:
        if int(item.get("track_id", -1)) == owner.track_id and str(item.get("team")) == owner.team:
            kept = ratio(item)
            if (
                kept <= settings.control_radius_heights
                and kept - ratio(box) < settings.owner_keep_margin_heights
            ):
                return item
            break
    return box


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


def _moved_with_hidden_ball(
    before: tuple[float, float],
    before_boxes: Iterable[dict[str, Any]],
    ball: tuple[float, float],
    boxes: Iterable[dict[str, Any]],
    settings: ChronoSettings,
) -> dict[str, Any] | None:
    """The one player who carried the ball while it was hidden, or None."""
    earlier = {
        int(b["track_id"]): b
        for b in before_boxes
        if b.get("role") != "official" and b.get("team") in TEAMS
    }
    found: list[dict[str, Any]] = []
    for box in boxes:
        if box.get("role") == "official" or box.get("team") not in TEAMS:
            continue
        old = earlier.get(int(box["track_id"]))
        if old is None or old.get("team") != box.get("team"):
            continue
        height = (
            float(box["y2"]) - float(box["y1"]) + float(old["y2"]) - float(old["y1"])
        ) / 2
        if height <= 0:
            continue
        (fx, fy), (ox, oy) = _feet(box), _feet(old)
        if (
            hypot(ball[0] - before[0], ball[1] - before[1]) / height
            < settings.hidden_min_ball_move_heights
        ):
            continue
        if (
            hypot(ball[0] - fx, ball[1] - fy) / height > settings.hidden_reach_heights
            or hypot(before[0] - ox, before[1] - oy) / height > settings.hidden_reach_heights
        ):
            continue
        change = hypot((ball[0] - fx) - (before[0] - ox), (ball[1] - fy) - (before[1] - oy))
        if change / height <= settings.hidden_max_offset_change_heights:
            found.append(box)
    return found[0] if len(found) == 1 else None


def _box_distance(ball: tuple[float, float], box: dict[str, Any]) -> float:
    """Distance from the ball to the nearest point of the player, head to feet."""
    dx = max(float(box["x1"]) - ball[0], 0.0, ball[0] - float(box["x2"]))
    dy = max(float(box["y1"]) - ball[1], 0.0, ball[1] - float(box["y2"]))
    return hypot(dx, dy)


def _movement_change_px(
    before: tuple[float, float, float],
    at: tuple[float, float, float],
    after: tuple[float, float, float],
) -> tuple[float, float] | None:
    """How far the ball's next step departs from simply carrying on, in pixels per axis."""
    d1, d2 = at[0] - before[0], after[0] - at[0]
    if d1 <= 0 or d2 <= 0:
        return None
    scale = (d1 + d2) / 2
    return (
        ((after[1] - at[1]) / d2 - (at[1] - before[1]) / d1) * scale,
        ((after[2] - at[2]) / d2 - (at[2] - before[2]) / d1) * scale,
    )


def _position_noise_px(
    track: list[tuple[int, float, float, float]], settings: ChronoSettings
) -> float:
    """The ball track's own position wobble (one standard deviation, pixels).

    For a ball carrying on, each step repeats the previous one, so the
    change between neighbouring steps is mostly position error. The median
    of those changes over the whole track ignores the few real touches.
    """
    changes: list[float] = []
    for (_, *a), (_, *b), (_, *c) in zip(track, track[1:], track[2:]):
        if (
            b[0] - a[0] > settings.touch_neighbour_gap_seconds
            or c[0] - b[0] > settings.touch_neighbour_gap_seconds
        ):
            continue
        change = _movement_change_px(tuple(a), tuple(b), tuple(c))
        if change is not None:
            changes.extend(change)
    if len(changes) < 2 * settings.noise_min_samples:
        return 0.0
    middle = median(changes)
    # Median absolute deviation -> standard deviation; a step change mixes
    # three position errors (1 + 4 + 1 = 6 times the variance).
    return median(abs(c - middle) for c in changes) / 0.6745 / sqrt(6)


def _off_line_sightings(
    track: list[tuple[int, float, float, float]],
    reacquired: set[int],
    settings: ChronoSettings,
    noise_px: float,
) -> set[int]:
    """Indices of lone re-found sightings that sit off the ball's unbroken line.

    The ball keeps one direction before, across and after the sighting, so
    nothing touched it there; a sighting clearly off that line (more than a
    touch-sized change of the track's own wobble) cannot be the ball.
    """
    if noise_px <= 0:
        return set()
    limit = settings.touch_noise_multiple * noise_px * sqrt(6)
    gap = settings.off_line_max_gap_seconds

    def heading(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, float] | None:
        dx, dy = b[2] - a[2], b[3] - a[3]
        if b[1] <= a[1] or b[1] - a[1] > gap or hypot(dx, dy) == 0:
            return None
        return dx, dy

    def turn(u: tuple[float, float], v: tuple[float, float]) -> float:
        cos = (u[0] * v[0] + u[1] * v[1]) / (hypot(*u) * hypot(*v))
        return degrees(acos(max(-1.0, min(1.0, cos))))

    dropped: set[int] = set()
    for index in sorted(reacquired):
        if index < 2 or index > len(track) - 3:
            continue
        if {index - 1, index + 1} & reacquired:
            continue
        chord = heading(track[index - 1], track[index + 1])
        before = heading(track[index - 2], track[index - 1])
        after = heading(track[index + 1], track[index + 2])
        if chord is None or before is None or after is None:
            continue
        if max(turn(before, chord), turn(chord, after)) >= settings.rolling_turn_degrees:
            continue
        _, _, x, y = track[index]
        _, _, ax, ay = track[index - 1]
        offset = abs((x - ax) * chord[1] - (y - ay) * chord[0]) / hypot(*chord)
        if offset > limit:
            dropped.add(index)
    return dropped


def _ball_deflected(
    before: tuple[float, float, float],
    at: tuple[float, float, float],
    after: tuple[float, float, float],
    settings: ChronoSettings,
    *,
    aerial: bool = False,
    noise_px: float = 0.0,
) -> bool:
    """Law 12 touch evidence: the ball clearly turns or changes speed here.

    A ball in the air can hang almost still in the picture and then leave
    fast in a new direction: that is a header, not a still ball. A change
    no larger than the track's own position wobble is not evidence.
    """
    v1 = (at[1] - before[1], at[2] - before[2])
    v2 = (after[1] - at[1], after[2] - at[2])
    d1, d2 = at[0] - before[0], after[0] - at[0]
    if d1 <= 0 or d2 <= 0 or hypot(*v1) == 0 or hypot(*v2) == 0:
        return False
    if noise_px > 0:
        change = _movement_change_px(before, at, after)
        if change is not None and hypot(*change) < (
            settings.touch_noise_multiple * noise_px * sqrt(6)
        ):
            return False
    s1, s2 = hypot(*v1) / d1, hypot(*v2) / d2
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (hypot(*v1) * hypot(*v2))
    turn = degrees(acos(max(-1.0, min(1.0, cos))))
    stopped = settings.stopped_speed_px_per_second
    if s1 < stopped or s2 < stopped:
        return (
            aerial
            and s1 < stopped
            and s2 >= settings.aerial_restart_speed_ratio * stopped
            and turn >= settings.touch_turn_degrees
        )
    ratio = max(s1, s2) / min(s1, s2)
    return turn >= settings.touch_turn_degrees or ratio >= settings.touch_speed_ratio


def _hidden_turn(
    track: list[tuple[int, float, float, float]],
    index: int,
    settings: ChronoSettings,
    noise_px: float,
) -> tuple[float, float, float] | None:
    """Where and when the ball turned while it was out of sight.

    The ball arrives on one straight line and leaves on another, with the
    turn itself in the unseen samples between ``index - 1`` and ``index``.
    The two lines meet where it was touched; the touch is accepted only when
    the ball's own speeds bring it there and away again in the unseen time.
    Returns ``(seconds, x, y)`` of the turn, or ``None``.
    """
    if index < 2 or index > len(track) - 2:
        return None
    _, t0, x0, y0 = track[index - 2]
    _, ta, ax, ay = track[index - 1]
    _, tb, bx, by = track[index]
    _, t3, x3, y3 = track[index + 1]
    near = settings.touch_neighbour_gap_seconds
    gap = tb - ta
    if not (near < gap <= settings.hidden_gap_max_seconds):
        return None
    if not (0 < ta - t0 <= near and 0 < t3 - tb <= near):
        return None
    u = ((ax - x0) / (ta - t0), (ay - y0) / (ta - t0))
    w = ((x3 - bx) / (t3 - tb), (y3 - by) / (t3 - tb))
    s_in, s_out = hypot(*u), hypot(*w)
    stopped = settings.stopped_speed_px_per_second
    if s_in < stopped or s_out < stopped:
        return None
    cos = (u[0] * w[0] + u[1] * w[1]) / (s_in * s_out)
    if degrees(acos(max(-1.0, min(1.0, cos)))) < settings.touch_turn_degrees:
        return None
    # Where the ball would be if nothing touched it: clearly not where it is.
    miss = hypot(bx - (ax + u[0] * gap), by - (ay + u[1] * gap))
    if miss < settings.touch_noise_multiple * noise_px * sqrt(6):
        return None
    # A + a*u_hat = B - b*w_hat, with a, b >= 0 the distances to the turn.
    ux, uy, wx, wy = u[0] / s_in, u[1] / s_in, w[0] / s_out, w[1] / s_out
    det = ux * wy - uy * wx
    if abs(det) < 1e-9:
        return None
    dx, dy = bx - ax, by - ay
    a = (dx * wy - dy * wx) / det
    b = (ux * dy - uy * dx) / det
    if a < 0 or b < 0:
        return None
    arrive = a / s_in
    if abs(arrive + b / s_out - gap) > near:
        return None
    seconds = ta + min(arrive, gap)
    return seconds, ax + a * ux, ay + a * uy


def _blip_on_unbroken_line(
    track: list[tuple[int, float, float, float]],
    index: int,
    settings: ChronoSettings,
) -> bool:
    """One sample sits off a line the ball keeps before, across and after it.

    The ball's heading and pace from two samples before to two after stay
    within rolling limits, so the change seen only at this sample is
    position wobble, not a touch: a touch changes where the ball goes next.
    """
    if index < 2 or index > len(track) - 3:
        return False
    near = settings.touch_neighbour_gap_seconds
    points = [track[i][1:] for i in range(index - 2, index + 3)]
    if any(not 0 < b[0] - a[0] <= near for a, b in zip(points, points[1:])):
        return False

    def velocity(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float]:
        return (b[1] - a[1]) / (b[0] - a[0]), (b[2] - a[2]) / (b[0] - a[0])

    before = velocity(points[0], points[1])
    chord = velocity(points[1], points[3])
    after = velocity(points[3], points[4])
    stopped = settings.stopped_speed_px_per_second
    for u, w in ((before, chord), (chord, after)):
        su, sw = hypot(*u), hypot(*w)
        if su < stopped or sw < stopped:
            return False
        cos = (u[0] * w[0] + u[1] * w[1]) / (su * sw)
        if degrees(acos(max(-1.0, min(1.0, cos)))) >= settings.rolling_turn_degrees:
            return False
        if not settings.rolling_min_speed_ratio <= sw / su <= settings.rolling_max_speed_ratio:
            return False
    return True


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
    *,
    aerial: bool = False,
) -> dict[str, Any] | None:
    """The one player whose body (head to feet) is at a deflected ball.

    A touch may be with any part of the body except the hands (a header,
    for example), so the whole box counts, not just the feet. An opponent
    about as close means a contested ball, so nobody is credited. When a
    ball in the air is at one player's head and above an opponent's head,
    that opponent is not contesting it.
    """

    def ball_height(box: dict[str, Any]) -> float:
        return (ball[1] - float(box["y1"])) / (float(box["y2"]) - float(box["y1"]))

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
    headed = aerial and 0.0 <= ball_height(best) <= settings.head_zone_share
    for other_ratio, other in ranked[1:]:
        if other["team"] != best["team"]:
            if headed and ball_height(other) < 0.0:
                continue
            if aerial:
                best_feet, other_feet = _feet(best), _feet(other)
                if hypot(
                    best_feet[0] - other_feet[0], best_feet[1] - other_feet[1]
                ) > settings.aerial_contest_feet_heights * (
                    float(best["y2"]) - float(best["y1"])
                ):
                    continue
            if other_ratio - ratio < settings.duel_margin_heights:
                return None
            break
    return best


def _lofted_samples(
    track: list[tuple[int, float, float, float]],
    players: dict[int, list[dict[str, Any]]],
    settings: ChronoSettings,
) -> set[int]:
    """Indices of ball samples in flight, for ball tracks without an ``aerial`` label.

    A ball in the air is drawn at the feet of whoever stands behind it, so it
    cannot be controlled at the feet there; only a body touch (for example a
    header) counts. The shared flight check lives with the ball tracker
    (``football_poc.ball.aerial_labels``); here the nearest team player's box
    gives the height scale.
    """
    from football_poc.ball.aerial_labels import flight_indices

    def height_at(index: int) -> float | None:
        frame, _, x, y = track[index]
        boxes = [
            box
            for box in players.get(frame, [])
            if box.get("team") in TEAMS
            and box.get("role") != "official"
            and float(box["y2"]) > float(box["y1"])
        ]
        if not boxes:
            return None
        nearest = min(boxes, key=lambda box: _box_distance((x, y), box))
        return float(nearest["y2"]) - float(nearest["y1"])

    return flight_indices(
        track,
        height_at,
        min_rise_heights=settings.lofted_min_rise_heights,
        min_fall_ratio=settings.lofted_min_fall_ratio,
        noise_px=settings.lofted_noise_px,
        min_rise_px_per_second=settings.lofted_min_rise_px_per_second,
    )


def _credible_flights(
    track: list[tuple[int, float, float, float]],
    lofted: set[int],
    max_flight_seconds: float,
) -> set[int]:
    """Drop runs of in-flight samples that last longer than any real flight."""
    kept: set[int] = set()
    run: list[int] = []
    for index in [*sorted(lofted), None]:
        if run and (index is None or index != run[-1] + 1):
            if track[run[-1]][1] - track[run[0]][1] <= max_flight_seconds:
                kept.update(run)
            run = []
        if index is not None:
            run.append(index)
    return kept


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
    toucher: Callable[..., dict[str, Any] | None] | None = None,
) -> ChronoResult:
    """Walk the ball samples in time order.

    ``out_of_play_seconds`` are the times the ball tracker saw the ball out of
    play (Law 9). Those frames have no live ball position, so they arrive here
    as times only.

    ``toucher`` replaces the player-at-a-deflection check; it is called as
    ``toucher(ball, boxes, settings, aerial=..., noise_px=...)``. Only the BAC
    flow sets it (``football_poc.bac_chrono_tolerance``); the Live flow uses
    the default ``_toucher``.
    """
    result = ChronoResult()
    players = _without_stretched_boxes(players, settings)
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
    arriving: tuple[_Control, float] | None = None
    exit_path: list[tuple[float, float, float]] | None = None
    previous: tuple[float, float, float] | None = None
    previous_frame: int | None = None
    last_seconds = 0.0

    track: list[tuple[int, float, float, float]] = [
        (frame, float(b["clip_seconds"]), float(b["x"]), float(b["y"]))
        for frame in sorted(balls)
        if (b := _best_ball(balls[frame])) is not None
    ]
    noise_px = _position_noise_px(track, settings)
    reacquired = {
        index
        for index, (frame, *_rest) in enumerate(track)
        if (_best_ball(balls[frame]) or {}).get("state") == "visually_reacquired"
    }
    off_line = _off_line_sightings(track, reacquired, settings, noise_px)
    track = [sample for index, sample in enumerate(track) if index not in off_line]
    # The ball tracker labels each frame in flight; older ball tracks have no
    # label, so the same flight check runs here on the player heights.
    labelled = [_best_ball(balls[frame]) or {} for frame, *_rest in track]
    if track and all("aerial" in ball for ball in labelled):
        lofted = _credible_flights(
            track,
            {index for index, ball in enumerate(labelled) if ball["aerial"]},
            settings.max_flight_seconds,
        )
    else:
        lofted = _lofted_samples(track, players, settings)
    # Gap-filled positions are a straight guess, not evidence of a free roll.
    estimated = {
        index
        for index, (frame, *_rest) in enumerate(track)
        if (_best_ball(balls[frame]) or {}).get("source_attribution") == "interpolated"
    }
    estimates = [
        (frame, float(b["clip_seconds"]), float(b["x"]), float(b["y"]))
        for frame in sorted(balls)
        if (b := _estimate_ball(balls[frame])) is not None
    ]
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
            arriving = None
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
                if _ball_deflected(
                    before,
                    (t, x, y),
                    after,
                    settings,
                    aerial=index in lofted,
                    noise_px=noise_px,
                ) and not (
                    index not in lofted and _blip_on_unbroken_line(track, index, settings)
                ):
                    if toucher is None:
                        touch = _toucher(
                            (x, y), players.get(frame, []), settings, aerial=index in lofted
                        )
                    else:
                        touch = toucher(
                            (x, y),
                            players.get(frame, []),
                            settings,
                            aerial=index in lofted,
                            noise_px=noise_px,
                        )
                rolling = not estimated.intersection(
                    (index - 1, index, index + 1)
                ) and _rolling_through(before, (t, x, y), after, settings)
        if (
            touch is None
            and index not in lofted
            and index - 1 not in lofted
            and (turned := _hidden_turn(track, index, settings, noise_px)) is not None
        ):
            frame_a, seconds_a = track[index - 1][0], track[index - 1][1]
            target = frame_a + (turned[0] - seconds_a) * (frame - frame_a) / (t - seconds_a)
            hidden_frames = [k for k in players if frame_a < k < frame]
            if hidden_frames:
                hidden_frame = min(hidden_frames, key=lambda k: abs(k - target))
                hidden_boxes = players.get(hidden_frame, [])
                if toucher is None:
                    touch = _toucher(turned[1:], hidden_boxes, settings)
                else:
                    touch = toucher(
                        turned[1:], hidden_boxes, settings, aerial=False, noise_px=noise_px
                    )
        if touch is None and index in lofted:
            continue
        carried = None
        if touch is None and index > 0 and index - 1 not in lofted:
            before_frame, before_t, bx, by = track[index - 1]
            if (
                settings.touch_neighbour_gap_seconds
                < t - before_t
                <= settings.hidden_gap_max_seconds
            ):
                carried = _moved_with_hidden_ball(
                    (bx, by), players.get(before_frame, []), (x, y), players.get(frame, []), settings
                )
        box = touch or carried or _closest_controller(
            (x, y),
            players.get(frame, []),
            settings.control_radius_heights,
            settings.duel_margin_heights,
        )
        if box is None:
            arriving = None
            continue
        if touch is None and carried is None and owner is not None:
            box = _owner_keeps(box, owner, (x, y), players.get(frame, []), settings)
        track_id, team = int(box["track_id"]), str(box["team"])
        height = float(box["y2"]) - float(box["y1"])
        feet = _feet(box)
        reach = hypot(x - feet[0], y - feet[1]) / max(height, 1.0)
        if (
            arriving is not None
            and arriving[0].track_id == track_id
            and reach <= arriving[1]
            and t - arriving[0].last_seconds <= settings.control_confirm_gap_seconds
        ):
            arriving[0].samples += 1
            arriving[0].last_seconds, arriving[0].feet = t, feet
            arriving = (arriving[0], reach)
        else:
            arriving = (_Control(track_id, team, t, t, feet, height), reach)
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
            if index > 0 and touch is None and carried is None:
                # Trajectory estimates between the previous seen frame and
                # this one support (never start) control by the player who
                # is also clearly nearest on this seen frame.
                since = track[index - 1][1]
                support = [
                    seconds
                    for est_frame, seconds, ex, ey in estimates
                    if since < seconds < t
                    and t - seconds <= settings.control_confirm_gap_seconds
                    and (
                        near := _closest_controller(
                            (ex, ey),
                            players.get(est_frame, []),
                            settings.control_radius_heights,
                            settings.duel_margin_heights,
                        )
                    )
                    is not None
                    and int(near["track_id"]) == track_id
                ]
                if support:
                    candidate.first_seconds = min(support)
                    candidate.samples += len(support)
        if touch is not None:
            candidate.samples = max(candidate.samples, settings.control_confirm_samples)
        if carried is not None:
            # He had the ball from the moment it went out of sight.
            candidate.samples = max(candidate.samples, settings.control_confirm_samples)
            candidate.first_seconds = min(candidate.first_seconds, track[index - 1][1])
        if candidate.samples < settings.control_confirm_samples:
            continue
        if owner is not None and owner.track_id == candidate.track_id:
            owner.last_seconds, owner.feet = t, candidate.feet
            continue

        # 3. Control changed: write the event.
        new = candidate
        _control_change(result, owner, new, settings)
        owner = _Control(new.track_id, new.team, new.first_seconds, t, new.feet, new.height, new.samples)
        arriving = None

    # The clip ends while the ball is still rolling into a player's feet:
    # it kept closing in on him and is now within touching reach, so he has
    # received it even though there is no later sample to show it stop.
    if (
        state == "in_play"
        and exit_path is None
        and arriving is not None
        and arriving[0].samples >= settings.control_confirm_samples
        and arriving[1] <= settings.touch_radius_heights
        and (owner is None or owner.track_id != arriving[0].track_id)
    ):
        _control_change(result, owner, arriving[0], settings)

    result.match_state.append(MatchStateChange(last_seconds, state, "segment_end"))
    return result


def _control_change(
    result: ChronoResult,
    owner: "_Control | None",
    new: "_Control",
    settings: ChronoSettings,
) -> None:
    """Write the pass or turnover from the owner to the new controller."""
    if owner is None:
        return
    swap = (
        new.team == owner.team
        and new.first_seconds - owner.last_seconds <= settings.identity_swap_gap_seconds
        and hypot(new.feet[0] - owner.feet[0], new.feet[1] - owner.feet[1])
        <= settings.identity_swap_radius_heights * max(new.height, 1.0)
    )
    if swap:
        return
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


def main(
    argv: list[str] | None = None,
    toucher: Callable[..., dict[str, Any] | None] | None = None,
) -> None:
    from football_poc.engine.ball_evidence import _load_ball_points
    from football_poc.engine.common import exclude_players_outside_pitch, scaled_pitch_boundary
    from football_poc.engine.pipeline import _load_player_points

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analytics_data", type=Path)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--pitch-calibration", type=Path, required=True)
    parser.add_argument("--ball-tracks", type=Path, help="default: <data>/engine-ball-tracks.json")
    parser.add_argument(
        "--ball-states", type=Path, help="default: analytics-cache/ball-state-estimates.json"
    )
    args = parser.parse_args(argv)
    data: Path = args.analytics_data
    ball_path = args.ball_tracks or data / "engine-ball-tracks.json"
    manifest = Path(json.loads(ball_path.read_text(encoding="utf-8"))["manifest"])
    boundary = scaled_pitch_boundary(args.pitch_calibration, ball_path, args.video)
    players = exclude_players_outside_pitch(
        _load_player_points(data / "player-tracks.json", manifest), boundary
    )
    # The ball tracker's per-frame status is required evidence: events are read
    # from the ball track, its statuses, the player tracks and their kits together.
    states_path = args.ball_states or data.parent / "analytics-cache" / "ball-state-estimates.json"
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
        players,
        balls,
        boundary,
        goal_areas=goal_areas,
        out_of_play_seconds=out_of_play_seconds,
        toucher=toucher,
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
