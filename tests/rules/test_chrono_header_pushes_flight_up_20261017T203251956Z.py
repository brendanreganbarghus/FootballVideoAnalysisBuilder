"""Rule: a ball in flight that is clearly pushed up the picture at a player's head was headed.

A fast long ball can be headed on with little change of direction or speed,
so the turn and speed-ratio checks miss it. Gravity only bends a flying
ball's path down the picture, so an upward change larger than a touch-sized
change of the track's own wobble needs a body touch (Law 12). It is only
credited to a player who has the ball in his head zone; a bounce at the feet
is not a header.
"""

from __future__ import annotations

import football_poc.chrono_engine as chrono
from football_poc.chrono_engine import (
    ChronoSettings,
    _ball_in_head_zone,
    _pushed_up_in_flight,
    run_chronological,
)

SETTINGS = ChronoSettings()
BOUNDARY = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 1000.0), (0.0, 1000.0))
HEADER_AT = (700.0, 410.0)


def _box(track_id, team, feet_x, feet_y, height=100.0):
    return {
        "track_id": track_id,
        "team": team,
        "x1": feet_x - 15.0,
        "y1": feet_y - height,
        "x2": feet_x + 15.0,
        "y2": feet_y,
    }


def _play():
    """Red 1 plays a long ball; red 2 heads it on to black 3."""
    samples = []
    for i in range(6):  # red 1 has the ball at his feet
        samples.append((round(0.2 * i, 1), 200.0 + i, 500.0, False))
    flight_in = [(280.0, 470.0), (360.0, 445.0), (440.0, 425.0), (520.0, 410.0), (600.0, 400.0)]
    for k, (x, y) in enumerate(flight_in):
        samples.append((round(1.2 + 0.2 * k, 1), x, y, True))
    # Arrives at red 2's head still dropping, then leaves pushed upward at
    # nearly the same direction and pace.
    samples.append((2.2, 620.0, 395.0, True))
    samples.append((2.4, HEADER_AT[0] - 0.0, HEADER_AT[1], True))
    for k, (x, y) in enumerate([(775.0, 385.0), (850.0, 370.0), (925.0, 365.0)]):
        samples.append((round(2.6 + 0.2 * k, 1), x, y, True))
    for k in range(6):  # black 3 controls it at his feet
        samples.append((round(3.2 + 0.2 * k, 1), 1000.0 + k, 500.0, False))
    players, balls = {}, {}
    for n, (t, x, y, aerial) in enumerate(samples):
        frame = round(t * 25)
        wobble = 1.0 if n % 2 else -1.0
        balls[frame] = [
            {
                "clip_seconds": t,
                "x": x + wobble,
                "y": y + wobble,
                "state": "observed",
                "confidence": 0.9,
                "aerial": aerial,
            }
        ]
        players[frame] = [
            dict(_box(1, "red", 200.0, 500.0), clip_seconds=t),
            dict(_box(2, "red", 700.0, 500.0), clip_seconds=t),
            dict(_box(3, "black", 1000.0, 500.0), clip_seconds=t),
        ]
    return players, balls


def test_header_on_a_fast_long_ball_is_a_touch_20261017T203251956Z():
    players, balls = _play()
    result = run_chronological(players, balls, BOUNDARY, SETTINGS)
    pairs = [
        (e["event_type"], e["team"], e["from_player_track_id"], e["to_player_track_id"])
        for e in result.events
    ]
    assert pairs == [
        ("pass_candidate", "red", 1, 2),
        ("turnover_candidate", "red", 2, 3),
    ]


def test_without_the_upward_push_rule_the_header_is_missed_20261017T203251957Z(monkeypatch):
    monkeypatch.setattr(chrono, "_pushed_up_in_flight", lambda *a, **k: False)
    players, balls = _play()
    result = run_chronological(players, balls, BOUNDARY, SETTINGS)
    pairs = [(e["from_player_track_id"], e["to_player_track_id"]) for e in result.events]
    assert pairs == [(1, 3)]


def test_only_an_upward_change_counts_20261017T203251958Z():
    before, at = (0.0, 0.0, 0.0), (0.2, 80.0, 15.0)
    assert _pushed_up_in_flight(before, at, (0.4, 155.0, -15.0), SETTINGS, noise_px=2.0)
    # The same size of change downward is gravity-like, not a header.
    assert not _pushed_up_in_flight(before, at, (0.4, 155.0, 75.0), SETTINGS, noise_px=2.0)
    # A small upward wobble is not evidence.
    assert not _pushed_up_in_flight(before, at, (0.4, 160.0, 25.0), SETTINGS, noise_px=2.0)
    # Without a measured wobble there is no gate, so no claim.
    assert not _pushed_up_in_flight(before, at, (0.4, 155.0, -15.0), SETTINGS, noise_px=0.0)


def test_head_zone_is_the_top_of_the_body_20261017T203251959Z():
    box = _box(2, "red", 700.0, 500.0)
    assert _ball_in_head_zone((700.0, 410.0), box, SETTINGS)
    assert not _ball_in_head_zone((700.0, 495.0), box, SETTINGS)
    assert not _ball_in_head_zone((700.0, 390.0), box, SETTINGS)
