"""Chronological engine: a ball rolling past a player unchanged is not received,
and a flight must fall back by a clear share of its rise."""

from football_poc.chrono_engine import ChronoSettings, _lofted_samples, run_chronological

BOUNDARY = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 1000.0), (0.0, 1000.0))


def _box(track_id, team, x, feet_y):
    return {"track_id": track_id, "team": team, "role": "player",
            "x1": x - 15, "x2": x + 15, "y1": feet_y - 80, "y2": feet_y}


def _ball(frame, x, y, source="yolo26_observed"):
    return [{"source_frame": frame, "clip_seconds": frame / 25, "x": x, "y": y,
             "confidence": 0.9, "event_evidence_eligible": True,
             "source_attribution": source}]


def _pass_past_opponent(source="yolo26_observed"):
    """Red 1 passes along the ground to red 2; the ball rolls straight past black 9's feet."""
    players, balls = {}, {}
    path = [100] * 3 + list(range(130, 550, 30)) + [550] * 3
    for i, x in enumerate(path):
        frame = i * 5
        players[frame] = [_box(1, "red", 100, 500), _box(9, "black", 300, 500),
                          _box(2, "red", 550, 500)]
        moving = 3 <= i < len(path) - 3
        balls[frame] = _ball(frame, x, 500, source if moving else "yolo26_observed")
    return players, balls


def _summary(events):
    return [(e["event_type"], e["team"], e["from_player_track_id"], e["to_player_track_id"])
            for e in events]


def test_ball_rolling_past_unchanged_is_not_received_20261011T152546139Z():
    players, balls = _pass_past_opponent()
    events = run_chronological(players, balls, BOUNDARY).events
    assert _summary(events) == [("pass_candidate", "red", 1, 2)]


def test_gap_filled_positions_are_not_evidence_of_rolling_past_20261011T152546140Z():
    players, balls = _pass_past_opponent(source="interpolated")
    events = run_chronological(players, balls, BOUNDARY).events
    assert 9 in {e["to_player_track_id"] for e in events}


def test_long_climb_with_small_dip_is_not_a_flight_20261011T152546141Z():
    """A ball rolling away from the camera climbs in the image; a small dip is not a landing."""
    climb = [500, 470, 440, 410, 380, 350, 320, 300, 330]
    track = [(i * 5, i * 0.2, 1000.0, float(y)) for i, y in enumerate(climb)]
    players = {i * 5: [_box(7, "red", 1000, 520)] for i in range(len(climb))}
    assert _lofted_samples(track, players, ChronoSettings()) == set()
    assert _lofted_samples(track, players, ChronoSettings(lofted_min_fall_ratio=0.0))
