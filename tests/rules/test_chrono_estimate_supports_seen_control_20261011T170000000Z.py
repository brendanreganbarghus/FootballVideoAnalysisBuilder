"""Chronological engine: a ball-tracker trajectory estimate between two seen
frames supports (never starts) control by the player who is also nearest on
the next seen frame."""

from football_poc.chrono_engine import run_chronological

BOUNDARY = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 1000.0), (0.0, 1000.0))


def _box(track_id, team, x, feet_y=500):
    return {"track_id": track_id, "team": team, "role": "player",
            "x1": x - 15, "x2": x + 15, "y1": feet_y - 80, "y2": feet_y}


def _ball(frame, x, state):
    return [{"source_frame": frame, "clip_seconds": frame / 25, "x": x, "y": 500.0,
             "confidence": 0.9, "state": state, "source_attribution": "yolo26_observed"}]


def _pass(receiver_x_during_estimates):
    """Red 1 holds the ball and passes to red 2; the tracker only estimates the
    ball for two frames at red 2's feet, then sees it there once before it
    moves away from everyone."""
    players, balls = {}, {}
    path = [(100, "observed")] * 4 + [(x, "observed") for x in range(150, 600, 50)]
    path += [(600, "trajectory_estimated_bidirectional")] * 2 + [(600, "observed")]
    path += [(1200, "observed")] * 3
    for i, (x, state) in enumerate(path):
        frame = i * 5
        receiver = receiver_x_during_estimates if state != "observed" else 600
        players[frame] = [_box(1, "red", 100), _box(2, "red", receiver), _box(3, "red", 1200)]
        balls[frame] = _ball(frame, x, state)
    return players, balls


def _passes(events):
    return [(e["from_player_track_id"], e["to_player_track_id"]) for e in events]


def test_estimates_support_one_seen_reception_20261011T170000000Z():
    players, balls = _pass(receiver_x_during_estimates=600)
    events = run_chronological(players, balls, BOUNDARY).events
    assert _passes(events)[:1] == [(1, 2)]
    assert events[0]["completion_seconds"] == round(13 * 5 / 25, 3)


def test_estimate_near_nobody_does_not_support_control_20261011T170000001Z():
    players, balls = _pass(receiver_x_during_estimates=900)
    events = run_chronological(players, balls, BOUNDARY).events
    assert (1, 2) not in _passes(events)
