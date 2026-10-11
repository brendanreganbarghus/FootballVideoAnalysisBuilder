"""Chronological engine: a player box that suddenly grows much taller than
its own track's usual height (merged with a neighbour or stretched over the
ball) does not show where that player's feet are, so it cannot take control."""

from football_poc.chrono_engine import run_chronological

BOUNDARY = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 1000.0), (0.0, 1000.0))


def _box(track_id, team, x, frame, feet_y=500.0, height=80.0):
    return {"track_id": track_id, "team": team, "role": "player", "clip_seconds": frame / 25,
            "x1": x - 15, "x2": x + 15, "y1": feet_y - height, "y2": feet_y}


def _scene(stretched_height):
    """Red 1 holds the ball, then it rolls slowly past black 3 (feet 60 px
    above the ball's line) to red 2. On two frames black 3's box reaches
    down onto the ball."""
    players, balls = {}, {}
    path = [100.0] * 4 + [300.0, 400.0, 500.0, 600.0, 650.0, 700.0] + [800.0] * 4
    for i, x in enumerate(path):
        frame = i * 5
        black_height = stretched_height if x in (600.0, 650.0) else 80.0
        black_feet = 440.0 + (black_height - 80.0)
        players[frame] = [
            _box(1, "red", 100, frame),
            _box(3, "black", x if x in (600.0, 650.0) else 625, frame, black_feet, black_height),
            _box(2, "red", 800, frame),
        ]
        balls[frame] = [{"source_frame": frame, "clip_seconds": frame / 25, "x": x, "y": 500.0,
                         "confidence": 0.9, "state": "observed",
                         "source_attribution": "yolo26_observed"}]
    return players, balls


def _changes(events):
    return [(e["from_player_track_id"], e["to_player_track_id"]) for e in events]


def test_stretched_box_over_ball_cannot_win_it_20261011T180000000Z():
    players, balls = _scene(stretched_height=140.0)
    events = run_chronological(players, balls, BOUNDARY).events
    assert _changes(events) == [(1, 2)]
    assert events[0]["event_type"] == "pass_candidate"


def test_normal_box_at_ball_still_wins_it_20261011T180000001Z():
    players, balls = _scene(stretched_height=80.0)
    for frame, boxes in players.items():
        for box in boxes:
            if box["track_id"] == 3 and balls[frame][0]["x"] in (600.0, 650.0):
                box["y1"], box["y2"] = 420.0, 500.0
    events = run_chronological(players, balls, BOUNDARY).events
    assert (1, 3) in _changes(events)
