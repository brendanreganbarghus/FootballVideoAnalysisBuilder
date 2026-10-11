"""Chronological engine: the restart taker owns the ball; goal areas come only from calibration."""

from football_poc.chrono_engine import goal_areas_from_calibration, run_chronological

BOUNDARY = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 1000.0), (0.0, 1000.0))


def _box(track_id, team, x, y):
    return {"track_id": track_id, "team": team, "role": "player",
            "x1": x - 15, "x2": x + 15, "y1": y - 80, "y2": y}


def _ball(frame, x, y):
    return [{"source_frame": frame, "clip_seconds": frame / 25, "x": x, "y": y,
             "confidence": 0.9, "event_evidence_eligible": True}]


def test_restart_taker_owns_ball_and_completes_pass_20261011T133803795Z():
    players, balls = {}, {}
    for frame in range(0, 200, 5):
        players[frame] = [_box(1, "red", 300, 500), _box(2, "red", 1100, 500)]
    for frame in range(0, 100, 5):
        balls[frame] = _ball(frame, 305, 497)
    for i, frame in enumerate(range(100, 160, 5)):
        balls[frame] = _ball(frame, min(305 + (i + 1) * 80, 1105), 497)
    for frame in range(160, 200, 5):
        balls[frame] = _ball(frame, 1105, 497)
    result = run_chronological(players, balls, BOUNDARY)
    assert result.match_state[1].state == "in_play"
    assert [(e["event_type"], e["team"], e["from_player_track_id"], e["to_player_track_id"])
            for e in result.events] == [("pass_candidate", "red", 1, 2)]


def test_goal_area_only_from_calibration_20261011T133803796Z():
    mouth = [[100, 450], [100, 550], [60, 550], [60, 450]]
    area = [[100, 400], [150, 400], [150, 600], [100, 600]]
    calibration = {"boundary": [list(p) for p in BOUNDARY],
                   "features": {"left_goal_mouth": mouth, "left_goal_area": area,
                                "right_goal_mouth": mouth}}
    assert goal_areas_from_calibration(calibration) == (
        ((100.0, 400.0), (150.0, 400.0), (150.0, 600.0), (100.0, 600.0)),
    )

