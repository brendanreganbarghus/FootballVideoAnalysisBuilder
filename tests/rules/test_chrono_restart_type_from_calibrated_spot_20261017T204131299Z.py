"""Chronological engine: a placed ball names its restart from calibrated spots.

Laws 8, 13-17: a kick-off is taken from the centre spot, a penalty from a
penalty mark and a corner from a corner. Any other placed ball well inside the
pitch is a free kick, but only once the centre spot and both penalty marks
are calibrated.
"""

from football_poc.chrono_engine import (
    ChronoSettings,
    restart_spots_from_calibration,
    run_chronological,
)

BOUNDARY = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 1000.0), (0.0, 1000.0))
SPOTS = {
    "corner": ((0.0, 0.0), (0.0, 1000.0), (2000.0, 0.0), (2000.0, 1000.0)),
    "centre_spot": ((1000.0, 500.0),),
    "left_penalty_mark": ((220.0, 500.0),),
    "right_penalty_mark": ((1780.0, 500.0),),
}


def _box(track_id, team, x, y):
    return {"track_id": track_id, "team": team, "role": "player",
            "x1": x - 15, "x2": x + 15, "y1": y - 80, "y2": y}


def _ball(frame, x, y):
    return [{"source_frame": frame, "clip_seconds": frame / 25, "x": x, "y": y,
             "confidence": 0.9, "event_evidence_eligible": True}]


def _restart(x, y, spots):
    players, balls = {}, {}
    for frame in range(0, 100, 5):
        players[frame] = [_box(1, "red", x - 10, y + 5)]
        balls[frame] = _ball(frame, x, y)
    step = -60 if x > 1000 else 60
    for i, frame in enumerate(range(100, 160, 5)):
        balls[frame] = _ball(frame, x + (i + 1) * step, y)
    result = run_chronological(players, balls, BOUNDARY, restart_spots=spots)
    assert result.match_state[1].state == "in_play"
    return result.match_state[1].reason


def test_placed_ball_away_from_spots_is_free_kick_20261017T204131299Z():
    assert _restart(600, 300, SPOTS) == "free_kick_taken"


def test_free_kick_needs_all_three_spots_calibrated_20261017T204131300Z():
    for missing in ("centre_spot", "left_penalty_mark", "right_penalty_mark"):
        spots = {name: points for name, points in SPOTS.items() if name != missing}
        assert _restart(600, 300, spots) == "restart_taken_type_unknown"
    assert _restart(600, 300, None) == "restart_taken_type_unknown"


def test_ball_on_a_spot_names_that_restart_20261017T204131301Z():
    assert _restart(1000, 500, SPOTS) == "kick_off_taken"
    assert _restart(220, 500, SPOTS) == "penalty_kick_taken"
    assert _restart(1780, 500, SPOTS) == "penalty_kick_taken"
    assert _restart(30, 30, SPOTS) == "corner_kick_taken"


def test_ball_near_touchline_is_not_named_free_kick_20261017T204131302Z():
    # A placed ball within reach of the touchline may be a throw-in.
    assert _restart(600, 40, SPOTS) == "restart_taken_type_unknown"


def test_spot_tolerance_scales_with_taker_height_20261017T204131303Z():
    # 100 px from the centre spot; the taker is 80 px tall.
    assert _restart(1100, 500, SPOTS) == "free_kick_taken"
    wide = ChronoSettings(restart_spot_tolerance_heights=1.5)
    players, balls = {}, {}
    for frame in range(0, 100, 5):
        players[frame] = [_box(1, "red", 1090, 505)]
        balls[frame] = _ball(frame, 1100, 500)
    for i, frame in enumerate(range(100, 160, 5)):
        balls[frame] = _ball(frame, 1100 - (i + 1) * 60, 500)
    result = run_chronological(players, balls, BOUNDARY, wide, restart_spots=SPOTS)
    assert result.match_state[1].reason == "kick_off_taken"


def test_spots_read_from_calibration_20261017T204131304Z():
    calibration = {"features": {
        "left_goal_line": [[10, 20], [12, 500], [15, 980]],
        "right_goal_line": [[1990, 15], [1985, 990]],
        "centre_spot": [[1000, 500]],
        "left_penalty_mark": [[220, 500], [221, 501]],
    }}
    spots = restart_spots_from_calibration(calibration)
    assert spots["corner"] == ((10.0, 20.0), (15.0, 980.0), (1990.0, 15.0), (1985.0, 990.0))
    assert spots["centre_spot"] == ((1000.0, 500.0),)
    # A spot is one click; anything else is not guessed.
    assert "left_penalty_mark" not in spots
    assert "right_penalty_mark" not in spots
