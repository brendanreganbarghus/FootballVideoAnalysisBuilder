"""Chronological engine: when the clip ends while the ball rolls into a
player's feet, he has received it; a ball still on its way has not."""

from football_poc.chrono_engine import run_chronological

BOUNDARY = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 1000.0), (0.0, 1000.0))


def _box(track_id, team, x, feet_y):
    return {"track_id": track_id, "team": team, "role": "player",
            "x1": x - 15, "x2": x + 15, "y1": feet_y - 80, "y2": feet_y}


def _clip(last_x):
    """Red 1 holds the ball, then it rolls towards black 9 (feet at x=300) until the clip ends."""
    players, balls = {}, {}
    path = [100] * 3 + list(range(130, last_x + 1, 30))
    for i, x in enumerate(path):
        frame = i * 5
        players[frame] = [_box(1, "red", 100, 500), _box(9, "black", 300, 500)]
        balls[frame] = [{"source_frame": frame, "clip_seconds": frame / 25, "x": x, "y": 500,
                         "confidence": 0.9, "event_evidence_eligible": True,
                         "source_attribution": "yolo26_observed"}]
    return players, balls


def test_ball_rolling_into_feet_at_clip_end_is_received_20261012T080512417Z():
    events = run_chronological(*_clip(280), BOUNDARY).events
    assert [(e["event_type"], e["team"], e["from_player_track_id"], e["to_player_track_id"])
            for e in events] == [("turnover_candidate", "red", 1, 9)]


def test_ball_still_on_its_way_at_clip_end_is_not_received_20261012T080512418Z():
    assert run_chronological(*_clip(250), BOUNDARY).events == []
