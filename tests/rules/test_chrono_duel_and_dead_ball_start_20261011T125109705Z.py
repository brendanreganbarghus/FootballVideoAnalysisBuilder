"""Chronological engine: duels make no events; a dead ball at the start waits for its restart."""

from football_poc.chrono_engine import run_chronological

BOUNDARY = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 1000.0), (0.0, 1000.0))


def _box(track_id, team, x, y):
    return {"track_id": track_id, "team": team, "role": "player",
            "x1": x - 15, "x2": x + 15, "y1": y - 80, "y2": y}


def _ball(frame, x, y):
    return [{"source_frame": frame, "clip_seconds": frame / 25, "x": x, "y": y,
             "confidence": 0.9, "event_evidence_eligible": True}]


def test_duel_alternation_makes_no_turnover_20261011T125109705Z():
    players, balls = {}, {}
    for i, frame in enumerate(range(0, 200, 5)):
        x = 500 + i * 2
        players[frame] = [_box(1, "red", x, 500), _box(2, "black", x + 10, 500)]
        balls[frame] = _ball(frame, x + (12 if i % 2 else -2), 495)
    assert run_chronological(players, balls, BOUNDARY).events == []


def test_dead_ball_at_start_waits_for_restart_20261011T125109706Z():
    players, balls = {}, {}
    for frame in range(0, 100, 5):
        players[frame] = [_box(1, "red", 300, 500), _box(2, "black", 330, 500)]
        balls[frame] = _ball(frame, 310, 495)
    for i, frame in enumerate(range(100, 160, 5)):
        balls[frame] = _ball(frame, 310 + (i + 1) * 60, 495)
    result = run_chronological(players, balls, BOUNDARY)
    assert result.match_state[0].state == "out_of_play"
    assert result.match_state[1].state == "in_play"
    assert abs(result.match_state[1].seconds - 3.8) < 0.01
    assert result.events == []
