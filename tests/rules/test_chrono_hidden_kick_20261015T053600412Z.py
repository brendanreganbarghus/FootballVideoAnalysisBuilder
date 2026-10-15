"""Rule: a ball that leaves an unseen gap much faster on its own line was kicked.

A ball rolling on its own only slows down. When the detector misses the
moment a player strikes it, the ball arrives slowly and leaves at least
``touch_speed_ratio`` times faster on nearly the same line. The kick point
splits the gap so the two speeds fill the unseen time, and the player at
that point on the unseen frame touched it. A ball that keeps or loses speed
across the gap was not kicked.
"""

from __future__ import annotations

from dataclasses import replace

from football_poc.chrono_engine import ChronoSettings, _hidden_turn, run_chronological

SETTINGS = ChronoSettings()
BOUNDARY = ((0.0, 0.0), (1000.0, 0.0), (1000.0, 1000.0), (0.0, 1000.0))


def _box(track_id, team, feet_x, feet_y, height=40.0):
    return {
        "track_id": track_id,
        "team": team,
        "x1": feet_x - 12.0,
        "y1": feet_y - height,
        "x2": feet_x + 12.0,
        "y2": feet_y,
    }


def _track(after_speed):
    # Rolling left at 100 px/s; unseen at 0.4 and 0.6; kicked at 0.4.
    points = [(0.0, 520.0), (0.2, 500.0), (0.6, 480.0 - after_speed * 0.2), (0.8, 480.0 - after_speed * 0.4)]
    return [(round(t * 25), t, x, 500.0) for t, x in points]


def test_kick_point_found_when_ball_speeds_up_unseen_20261015T053600413Z():
    kicked = _hidden_turn(_track(400.0), 2, SETTINGS, noise_px=1.0)
    assert kicked is not None
    seconds, x, y = kicked
    assert abs(seconds - 0.4) < 0.01 and abs(x - 480.0) < 1.0 and abs(y - 500.0) < 1.0


def test_no_kick_when_ball_keeps_or_loses_speed_20261015T053600414Z():
    assert _hidden_turn(_track(100.0), 2, SETTINGS, noise_px=1.0) is None
    assert _hidden_turn(_track(40.0), 2, SETTINGS, noise_px=1.0) is None


def test_hidden_kick_can_be_switched_off_20261015T053600415Z():
    off = replace(SETTINGS, hidden_kick=False)
    assert _hidden_turn(_track(400.0), 2, off, noise_px=1.0) is None


def _run(after_speed):
    # Black 1 holds the ball at (900, 500) and lets it roll left at 100 px/s.
    # Red 2 stands at (480, 500); the ball reaches him unseen at 4.6 s.
    seen = [(0.0, 900.0), (0.2, 900.0), (0.4, 900.0)]
    seen += [(round(0.4 + 0.2 * i, 1), 900.0 - 20.0 * i) for i in range(1, 20)]  # to 4.2 s
    seen += [(4.8, 480.0 - after_speed * 0.2), (5.0, 480.0 - after_speed * 0.4), (5.2, 480.0 - after_speed * 0.6)]
    players, balls = {}, {}
    for i in range(27):
        t = round(0.2 * i, 1)
        frame = round(t * 25)
        players[frame] = [
            dict(_box(1, "black", 900.0, 500.0), clip_seconds=t),
            dict(_box(2, "red", 480.0, 500.0), clip_seconds=t),
        ]
    for t, x in seen:
        frame = round(t * 25)
        balls[frame] = [{"clip_seconds": t, "x": x, "y": 500.0, "state": "observed", "confidence": 0.9}]
    return run_chronological(players, balls, BOUNDARY, SETTINGS)


def test_unseen_kick_gives_the_kicker_the_ball_20261015T053600416Z():
    events = _run(400.0).events
    assert [(e["event_type"], e["from_player_track_id"], e["to_player_track_id"]) for e in events] == [
        ("turnover_candidate", 1, 2)
    ]


def test_ball_rolling_past_unseen_is_not_a_kick_20261015T053600417Z():
    assert _run(100.0).events == []
