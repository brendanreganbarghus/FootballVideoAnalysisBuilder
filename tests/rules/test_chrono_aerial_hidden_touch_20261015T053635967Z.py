"""Rule: a ball in the air whose sideways speed changes while hidden was touched.

Gravity only bends a flying ball's up-and-down movement in the picture; its
sideways speed stays steady. When the ball disappears among players' heads
and comes back on a new line with a clearly different sideways speed (at
least ``aerial_hidden_touch_sideways_ratio`` times, or reversed), a player
touched it there, for example with a header. The player whose body is at
the point where the two lines meet is the toucher. A ball that only turns
from rising to falling, at the same sideways speed, was not touched.
"""

from __future__ import annotations

from dataclasses import replace

from football_poc.chrono_engine import ChronoSettings, _hidden_turn, run_chronological

SETTINGS = ChronoSettings()
BOUNDARY = ((0.0, 0.0), (1000.0, 0.0), (1000.0, 1000.0), (0.0, 1000.0))


def _flight(leave):
    # Rising left at (-100, -70) px/s, unseen from 0.4 to 1.0 s, then leaving
    # at velocity ``leave`` from where the arriving line meets it at 0.6 s.
    vx, vy = leave
    turn = (500.0 - 100.0 * 0.6, 500.0 - 70.0 * 0.6)
    points = [(0.0, (500.0, 500.0)), (0.4, (460.0, 472.0))]
    points += [(t, (turn[0] + vx * (t - 0.6), turn[1] + vy * (t - 0.6))) for t in (1.0, 1.2)]
    return [(round(t * 25), t, x, y) for t, (x, y) in points]


def test_header_found_when_sideways_speed_changes_unseen_20261015T053635968Z():
    turned = _hidden_turn(_flight((-200.0, 60.0)), 2, SETTINGS, 1.0, aerial=True)
    assert turned is not None
    seconds, x, y = turned
    assert abs(seconds - 0.6) < 0.05 and abs(x - 440.0) < 5.0 and abs(y - 458.0) < 5.0


def test_flight_turning_down_at_same_sideways_speed_is_not_a_touch_20261015T053635969Z():
    assert _hidden_turn(_flight((-100.0, 70.0)), 2, SETTINGS, 1.0, aerial=True) is None


def test_aerial_hidden_touch_can_be_switched_off_20261015T053635970Z():
    off = replace(SETTINGS, aerial_hidden_touch_sideways_ratio=float("inf"))
    assert _hidden_turn(_flight((-200.0, 60.0)), 2, off, 1.0, aerial=True) is None


def _box(track_id, team, feet_x, feet_y, height=40.0):
    return {
        "track_id": track_id,
        "team": team,
        "x1": feet_x - 12.0,
        "y1": feet_y - height,
        "x2": feet_x + 12.0,
        "y2": feet_y,
    }


def _run(leave):
    # Red 1 holds the ball at (900, 500) and chips it left at (-100, -70)
    # px/s from 1.0 s. It is in the air and unseen at 2.2 and 2.4 s. Red 2's
    # head is at the turn point (780, 416) at 2.2 s; red 3 waits at (560, 486).
    vx, vy = leave
    seen = [(round(0.2 * i, 1), 1020.0 - 60.0 * i, 498.0, False) for i in range(3)]
    seen += [(round(0.2 * i, 1), 900.0, 498.0, False) for i in range(3, 5)]
    seen += [(round(1.0 + 0.2 * i, 1), 900.0 - 20.0 * i, 500.0 - 14.0 * i, i > 0) for i in range(6)]
    for i in range(14):
        t = round(2.6 + 0.2 * i, 1)
        x, y = 780.0 + vx * (t - 2.2), 416.0 + vy * (t - 2.2)
        if x <= 560.0:
            x, y = 560.0, 484.0
        seen.append((t, x, y, False))
    players, balls = {}, {}
    for i in range(26):
        t = round(0.2 * i, 1)
        frame = round(t * 25)
        players[frame] = [
            dict(_box(1, "red", 900.0, 500.0), clip_seconds=t),
            dict(_box(2, "red", 780.0, 450.0), clip_seconds=t),
            dict(_box(3, "red", 560.0, 486.0), clip_seconds=t),
            dict(_box(9, "black", 300.0, 200.0), clip_seconds=t),
        ]
    for t, x, y, aerial in seen:
        balls[round(t * 25)] = [
            {"clip_seconds": t, "x": x, "y": y, "state": "observed", "confidence": 0.9, "aerial": aerial}
        ]
    return run_chronological(players, balls, BOUNDARY, SETTINGS)


def test_hidden_header_receives_the_pass_20261015T053635971Z():
    events = _run((-200.0, 60.0)).events
    passes = [(e["event_type"], e["from_player_track_id"], e["to_player_track_id"]) for e in events]
    assert passes == [("pass_candidate", 1, 2), ("pass_candidate", 2, 3)]
