"""Rule: the player who moved with the ball while it was hidden had it.

A dribbler hides the ball behind his own body. Across that short hidden gap
he covers the same path as the ball, while players standing nearby do not,
even when one camera draws their feet a little closer to the ball.
"""

from __future__ import annotations

from football_poc.chrono_engine import ChronoSettings, _moved_with_hidden_ball, run_chronological

SETTINGS = ChronoSettings()
BOUNDARY = ((0.0, 0.0), (1000.0, 0.0), (1000.0, 1000.0), (0.0, 1000.0))


def _box(track_id, team, feet_x, feet_y, height=40.0):
    return {
        "track_id": track_id,
        "team": team,
        "x1": feet_x - 12.0,
        "y1": feet_y - height,
        "x2": feet_x + 12.0,
        "y2": feet_y,
    }


def test_dribbler_who_moves_with_hidden_ball_has_it_20261011T205816985Z():
    before, after = (560.0, 890.0), (500.0, 900.0)
    dribbler_then = _box(4, "red", 580.0, 930.0)
    dribbler_now = _box(4, "red", 522.0, 935.0)
    standing_then = _box(411, "black", 505.0, 903.0)  # still: ball arrives at him
    standing_now = _box(411, "black", 503.0, 903.0)
    found = _moved_with_hidden_ball(
        before, [dribbler_then, standing_then], after, [dribbler_now, standing_now], SETTINGS
    )
    assert found is dribbler_now


def test_nobody_carries_when_the_ball_did_not_move_or_two_players_did_20261011T205816986Z():
    still = _moved_with_hidden_ball(
        (560.0, 890.0), [_box(4, "red", 580.0, 930.0)], (562.0, 890.0), [_box(4, "red", 582.0, 930.0)], SETTINGS
    )
    assert still is None
    both = _moved_with_hidden_ball(
        (560.0, 890.0),
        [_box(4, "red", 580.0, 930.0), _box(9, "black", 545.0, 925.0)],
        (500.0, 900.0),
        [_box(4, "red", 520.0, 940.0), _box(9, "black", 485.0, 935.0)],
        SETTINGS,
    )
    assert both is None


def test_hidden_carry_becomes_a_pass_from_the_moment_ball_was_hidden_20261011T205816987Z():
    players, balls = {}, {}
    # Red 98 has the ball, the ball leaves him and is hidden behind red 4
    # (no seen frames between 1.2 s and 1.8 s); black 411 stands where the
    # ball reappears.
    seen = [(0.0, 300.0, 890.0), (0.2, 300.0, 890.0), (0.4, 300.0, 890.0), (1.2, 560.0, 890.0), (1.8, 500.0, 900.0)]
    for t, x, y in seen:
        frame = round(t * 25)
        balls[frame] = [{"clip_seconds": t, "x": x, "y": y, "state": "observed", "confidence": 0.9}]
    for t, x4 in ((0.0, 700.0), (0.2, 680.0), (0.4, 660.0), (1.2, 580.0), (1.8, 522.0)):
        frame = round(t * 25)
        players[frame] = [
            dict(_box(98, "red", 300.0, 915.0), clip_seconds=t),
            dict(_box(4, "red", x4, 930.0 if t < 1.8 else 935.0), clip_seconds=t),
            dict(_box(411, "black", 503.0, 903.0), clip_seconds=t),
        ]
    result = run_chronological(players, balls, BOUNDARY, SETTINGS)
    passes = [e for e in result.events if e["event_type"] == "pass_candidate"]
    assert [(e["from_player_track_id"], e["to_player_track_id"]) for e in passes] == [(98, 4)]
    assert passes[0]["completion_seconds"] == 1.2
    assert not [e for e in result.events if e["event_type"] == "turnover_candidate"]
