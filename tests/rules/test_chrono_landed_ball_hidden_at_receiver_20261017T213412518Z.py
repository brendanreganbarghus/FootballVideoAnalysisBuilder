"""Chronological engine: a ball that lands at one player and stays out of
sight until it is seen again at his feet was received where it landed.

The tracker's flight path ends at one clear player; nobody else contests it.
The ball is then hidden (at his feet, behind his body) and is next seen still
within his control reach, so he had it from the landing.
"""

from football_poc.chrono_engine import run_chronological

BOUNDARY = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 1000.0), (0.0, 1000.0))


def _box(track_id, team, x, y):
    return {"track_id": track_id, "team": team, "role": "player",
            "x1": x - 15, "x2": x + 15, "y1": y - 80, "y2": y}


def _ball(frame, x, y, state="observed"):
    return [{"source_frame": frame, "clip_seconds": frame / 25, "x": x, "y": y,
             "confidence": 0.9, "state": state, "aerial": False,
             "event_evidence_eligible": True}]


def _long_ball_landing(opponent_at_landing):
    players, balls = {}, {}
    for frame in range(0, 260, 5):
        black = (1130, 500) if opponent_at_landing and frame <= 145 else (1700, 900)
        players[frame] = [
            _box(1, "red", 300, 500), _box(2, "red", 1100, 500), _box(9, "black", *black),
        ]
    for frame in range(0, 100, 5):
        balls[frame] = _ball(frame, 305, 497)
    for i, frame in enumerate(range(100, 145, 5)):
        balls[frame] = _ball(frame, 305 + (i + 1) * 80, 497, "visually_reacquired")
    balls[145] = _ball(145, 1090, 497, "trajectory_estimated_flight_path")
    for frame in range(180, 260, 5):
        balls[frame] = _ball(frame, 1110, 505)
    return run_chronological(players, balls, BOUNDARY)


def test_ball_landing_at_one_player_then_hidden_is_received_there_20261017T213412518Z():
    result = _long_ball_landing(opponent_at_landing=False)
    assert [(e["from_player_track_id"], e["to_player_track_id"], e["completion_seconds"])
            for e in result.events] == [(1, 2, 5.8)]


def test_contested_landing_waits_for_control_at_the_feet_20261017T213412519Z():
    result = _long_ball_landing(opponent_at_landing=True)
    assert [(e["from_player_track_id"], e["to_player_track_id"], e["completion_seconds"])
            for e in result.events] == [(1, 2, 7.2)]
