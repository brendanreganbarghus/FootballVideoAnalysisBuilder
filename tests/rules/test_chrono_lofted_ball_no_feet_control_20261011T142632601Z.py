"""Chronological engine: a lofted ball cannot be controlled at the feet of a player behind it."""

from football_poc.chrono_engine import ChronoSettings, run_chronological

BOUNDARY = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 1000.0), (0.0, 1000.0))


def _box(track_id, team, x, feet_y):
    return {"track_id": track_id, "team": team, "role": "player",
            "x1": x - 15, "x2": x + 15, "y1": feet_y - 80, "y2": feet_y}


def _ball(frame, x, y):
    return [{"source_frame": frame, "clip_seconds": frame / 25, "x": x, "y": y,
             "confidence": 0.9, "event_evidence_eligible": True}]


def _lob_over_opponent():
    """Red 1 lobs the ball to red 2; in the image it passes black 9's feet at its peak."""
    players, balls = {}, {}
    flight = [460, 430, 410, 400, 400, 410, 430, 460, 500]
    path = [(100, 500)] * 3
    path += [(100 + 50 * k, y) for k, y in enumerate(flight, start=1)]
    path += [(550, 500)] * 3
    for i, (x, y) in enumerate(path):
        frame = i * 5
        players[frame] = [_box(1, "red", 100, 500), _box(9, "black", 300, 400),
                          _box(2, "red", 550, 500)]
        balls[frame] = _ball(frame, x, y)
    return players, balls


def test_lofted_ball_is_not_controlled_at_feet_behind_it_20261011T142632601Z():
    players, balls = _lob_over_opponent()
    events = run_chronological(players, balls, BOUNDARY).events
    assert [(e["event_type"], e["team"], e["from_player_track_id"], e["to_player_track_id"])
            for e in events] == [("pass_candidate", "red", 1, 2)]


def test_low_arc_is_not_a_flight_20261011T142632602Z():
    players, balls = _lob_over_opponent()
    no_lob = ChronoSettings(lofted_min_rise_heights=10.0)
    events = run_chronological(players, balls, BOUNDARY, no_lob).events
    assert 9 in {e["to_player_track_id"] for e in events}
