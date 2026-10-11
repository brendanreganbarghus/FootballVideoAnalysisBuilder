"""Chronological engine: a clear deflection at a player's body (e.g. a header) is a touch."""

from football_poc.chrono_engine import ChronoSettings, run_chronological

BOUNDARY = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 1000.0), (0.0, 1000.0))


def _box(track_id, team, x, y):
    return {"track_id": track_id, "team": team, "role": "player",
            "x1": x - 15, "x2": x + 15, "y1": y - 80, "y2": y}


def _ball(frame, x, y):
    return [{"source_frame": frame, "clip_seconds": frame / 25, "x": x, "y": y,
             "confidence": 0.9, "event_evidence_eligible": True}]


def _header_then_reception():
    players, balls = {}, {}
    path = [(100 + 60 * i, 410) for i in range(8)]
    path += [(520 + 60 * k, 410 - 60 * k) for k in range(1, 6)]
    path += [(820, 110)] * 6
    for i, (x, y) in enumerate(path):
        frame = i * 5
        players[frame] = [_box(1, "red", 520, 500), _box(2, "red", 820, 120)]
        balls[frame] = _ball(frame, x, y)
    return players, balls


def test_header_deflection_is_a_touch_20261011T141158850Z():
    players, balls = _header_then_reception()
    events = run_chronological(players, balls, BOUNDARY).events
    assert [(e["event_type"], e["team"], e["from_player_track_id"], e["to_player_track_id"])
            for e in events] == [("pass_candidate", "red", 1, 2)]
    assert events[0]["clip_seconds"] == 1.4


def test_straight_ball_past_head_is_not_a_touch_20261011T141158851Z():
    players, balls = _header_then_reception()
    no_turn = ChronoSettings(touch_turn_degrees=180.0, touch_speed_ratio=1e9)
    assert run_chronological(players, balls, BOUNDARY, no_turn).events == []


