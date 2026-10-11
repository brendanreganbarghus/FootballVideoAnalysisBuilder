"""Chronological engine reads the ball tracker's status: only seen ball frames
are control evidence, the tracker's out-of-play status stops play, and a team
whose controlled ball goes out of play loses it (Laws 15-17)."""

from football_poc.chrono_engine import run_chronological

BOUNDARY = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 1000.0), (0.0, 1000.0))


def _box(track_id, team, x, feet_y=500):
    return {"track_id": track_id, "team": team, "role": "player",
            "x1": x - 15, "x2": x + 15, "y1": feet_y - 80, "y2": feet_y}


def _ball(frame, x, state="observed"):
    return [{"source_frame": frame, "clip_seconds": frame / 25, "x": x, "y": 500.0,
             "confidence": 0.9, "state": state, "source_attribution": "yolo26_observed"}]


def _pass(reception_state, step=50):
    """Red 1 holds the ball, passes it to red 2, who holds it."""
    players, balls = {}, {}
    path = [100] * 4 + list(range(100 + step, 600, step)) + [600] * 4
    for i, x in enumerate(path):
        frame = i * 5
        players[frame] = [_box(1, "red", 100), _box(2, "red", 600)]
        received = i >= len(path) - 4
        balls[frame] = _ball(frame, x, reception_state if received else "observed")
    return players, balls


def _summary(events):
    return [(e["event_type"], e["team"], e["from_player_track_id"], e["to_player_track_id"])
            for e in events]


def test_seen_reception_is_control_evidence_20261011T154600000Z():
    players, balls = _pass("visually_reacquired")
    events = run_chronological(players, balls, BOUNDARY).events
    assert _summary(events) == [("pass_candidate", "red", 1, 2)]


def test_trajectory_estimate_is_not_control_evidence_20261011T154600001Z():
    players, balls = _pass("trajectory_estimated_bidirectional")
    events = run_chronological(players, balls, BOUNDARY).events
    assert events == []


def test_tracker_out_of_play_is_a_turnover_for_the_last_owner_20261011T154600002Z():
    """Red 1 controls the ball; the tracker then reports it out of play. The
    ball is later carried slowly to red 2, but play is stopped, so no pass is
    completed."""
    players, balls = _pass("observed", step=20)
    out_at = 3 * 5 / 25 + 0.1
    result = run_chronological(players, balls, BOUNDARY, out_of_play_seconds=[out_at])
    assert _summary(result.events) == [("turnover_candidate", "red", 1, None)]
    assert result.events[0]["completion_seconds"] == round(out_at, 3)
    assert ("out_of_play", "ball_tracker_out_of_play") in {
        (change.state, change.reason) for change in result.match_state
    }
