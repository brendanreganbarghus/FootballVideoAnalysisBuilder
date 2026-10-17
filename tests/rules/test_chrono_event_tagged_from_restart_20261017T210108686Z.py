"""Chronological engine: the event played straight from a named restart carries it.

Laws 13-17: the restart taker may not touch the ball again until another
player has, so the taker's pass or turnover is played from the restart. The
tag is on that one event; no extra event is written, so nothing is counted
twice.
"""

from football_poc.chrono_engine import run_chronological

BOUNDARY = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 1000.0), (0.0, 1000.0))
SPOTS = {
    "corner": ((0.0, 0.0), (0.0, 1000.0), (2000.0, 0.0), (2000.0, 1000.0)),
    "centre_spot": ((1500.0, 800.0),),
    "left_penalty_mark": ((150.0, 800.0),),
    "right_penalty_mark": ((1850.0, 800.0),),
}


def _box(track_id, team, x, y):
    return {"track_id": track_id, "team": team, "role": "player",
            "x1": x - 15, "x2": x + 15, "y1": y - 80, "y2": y}


def _ball(frame, x, y):
    return [{"source_frame": frame, "clip_seconds": frame / 25, "x": x, "y": y,
             "confidence": 0.9, "event_evidence_eligible": True}]


def _restart_then_two_passes(spots):
    players, balls = {}, {}
    for frame in range(0, 300, 5):
        players[frame] = [
            _box(1, "red", 300, 500), _box(2, "red", 1100, 500), _box(3, "red", 1100, 900),
        ]
    for frame in range(0, 100, 5):
        balls[frame] = _ball(frame, 305, 497)
    for i, frame in enumerate(range(100, 160, 5)):
        balls[frame] = _ball(frame, min(305 + (i + 1) * 80, 1105), 497)
    for frame in range(160, 200, 5):
        balls[frame] = _ball(frame, 1105, 497)
    for i, frame in enumerate(range(200, 240, 5)):
        balls[frame] = _ball(frame, 1105, min(497 + (i + 1) * 80, 897))
    for frame in range(240, 300, 5):
        balls[frame] = _ball(frame, 1105, 897)
    return run_chronological(players, balls, BOUNDARY, restart_spots=spots)


def test_pass_from_free_kick_is_tagged_once_20261017T210108686Z():
    result = _restart_then_two_passes(SPOTS)
    assert result.match_state[1].reason == "free_kick_taken"
    assert [(e["from_player_track_id"], e["to_player_track_id"], e.get("restart_type"))
            for e in result.events] == [(1, 2, "free_kick"), (2, 3, None)]


def test_unnamed_restart_tags_nothing_20261017T210108687Z():
    result = _restart_then_two_passes(None)
    assert result.match_state[1].reason == "restart_taken_type_unknown"
    assert [e.get("restart_type") for e in result.events] == [None, None]
