"""Chronological engine: when the ball track carries the tracker's ``aerial``
label, the engine uses it instead of its own shape guess."""

from football_poc.chrono_engine import ChronoSettings, run_chronological

BOUNDARY = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 1000.0), (0.0, 1000.0))
# Switch off the engine's own guess and the rolling-past rule.
NO_GUESS = ChronoSettings(lofted_min_rise_heights=10.0, rolling_turn_degrees=0.0)


def _box(track_id, team, x, feet_y):
    return {"track_id": track_id, "team": team, "role": "player",
            "x1": x - 15, "x2": x + 15, "y1": feet_y - 80, "y2": feet_y}


def _lob(aerial_label):
    """Red 1 lobs the ball to red 2; in the image it passes black 9's feet at its peak."""
    players, balls = {}, {}
    flight = [460, 430, 410, 400, 400, 410, 430, 460, 500]
    path = [(100, 500, False)] * 3
    path += [(100 + 50 * k, y, True) for k, y in enumerate(flight, start=1)]
    path += [(550, 500, False)] * 3
    for i, (x, y, in_air) in enumerate(path):
        frame = i * 5
        players[frame] = [_box(1, "red", 100, 500), _box(9, "black", 300, 400),
                          _box(2, "red", 550, 500)]
        balls[frame] = [{"source_frame": frame, "clip_seconds": frame / 25, "x": x, "y": y,
                         "confidence": 0.9, "event_evidence_eligible": True,
                         "aerial": in_air and aerial_label}]
    return players, balls


def _summary(events):
    return [(e["event_type"], e["team"], e["from_player_track_id"], e["to_player_track_id"])
            for e in events]


def test_tracker_aerial_label_stops_feet_control_20261011T194451032Z():
    players, balls = _lob(aerial_label=True)
    events = run_chronological(players, balls, BOUNDARY, NO_GUESS).events
    assert _summary(events) == [("pass_candidate", "red", 1, 2)]


def test_tracker_not_aerial_label_is_trusted_20261011T194451033Z():
    players, balls = _lob(aerial_label=False)
    events = run_chronological(players, balls, BOUNDARY, ChronoSettings(rolling_turn_degrees=0.0)).events
    assert 9 in {e["to_player_track_id"] for e in events}
