"""Rule: a ball that turns while out of sight was touched where its paths meet.

A first-time pass is often played in the one sample the detector misses: the
ball arrives on one straight line and leaves on another. The two lines meet
where it was touched, and the player standing there on the unseen frame
touched it, when the ball's own speeds bring it there and away again in the
unseen time. A ball that keeps its line across the gap was not touched.
"""

from __future__ import annotations

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


def _seen():
    # Red 1 holds the ball at (700, 500), plays it left at 400 px/s; it turns
    # at red 2's feet (300, 500) at 1.4 s, unseen, and leaves upwards.
    seen = [(0.0, 700.0, 500.0), (0.2, 700.0, 500.0), (0.4, 700.0, 500.0)]
    seen += [(0.4 + 0.2 * i, 700.0 - 80.0 * i, 500.0) for i in range(1, 5)]
    seen += [(1.6, 300.0, 420.0), (1.8, 300.0, 340.0), (2.0, 300.0, 260.0)]
    return seen


def _run(seen, receiver_x=300.0):
    players, balls = {}, {}
    for i in range(11):
        t = round(0.2 * i, 1)
        frame = round(t * 25)
        players[frame] = [
            dict(_box(1, "red", 700.0, 500.0), clip_seconds=t),
            dict(_box(2, "red", receiver_x, 500.0), clip_seconds=t),
        ]
    for t, x, y in seen:
        frame = round(t * 25)
        balls[frame] = [{"clip_seconds": t, "x": x, "y": y, "state": "observed", "confidence": 0.9}]
    return run_chronological(players, balls, BOUNDARY, SETTINGS)


def test_turn_point_found_between_unseen_samples_20261014T174238135Z():
    track = [(round(t * 25), t, x, y) for t, x, y in _seen()]
    turned = _hidden_turn(track, 7, SETTINGS, noise_px=1.0)
    assert turned is not None
    seconds, x, y = turned
    assert abs(seconds - 1.4) < 0.01 and abs(x - 300.0) < 1.0 and abs(y - 500.0) < 1.0


def test_ball_keeping_its_line_across_the_gap_has_no_turn_20261014T174238136Z():
    straight = [(round(0.2 * i * 25), 0.2 * i, 700.0 - 80.0 * i, 500.0) for i in range(8) if i != 5]
    assert _hidden_turn(straight, 5, SETTINGS, noise_px=1.0) is None


def test_player_at_hidden_turn_receives_the_pass_20261014T174238137Z():
    result = _run(_seen())
    passes = [e for e in result.events if e["event_type"] == "pass_candidate"]
    assert [(e["from_player_track_id"], e["to_player_track_id"]) for e in passes] == [(1, 2)]
    assert passes[0]["completion_seconds"] == 1.6


def test_nobody_credited_when_no_player_stands_at_the_turn_20261014T174238138Z():
    result = _run(_seen(), receiver_x=150.0)
    assert not result.events
