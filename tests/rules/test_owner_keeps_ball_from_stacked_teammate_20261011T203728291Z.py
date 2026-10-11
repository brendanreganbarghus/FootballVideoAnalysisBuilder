"""Rule: the player who has the ball keeps it while he is still within reach.

One camera draws a teammate standing metres behind the dribbler right on top
of him, so that teammate's feet can look a little closer to the ball. Control
moves to the teammate only when he is clearly closer (by the duel margin) or
the owner is out of reach. Opponents are unaffected: duels keep their rule.
"""

from __future__ import annotations

from football_poc.chrono_engine import ChronoSettings, _Control, _owner_keeps

SETTINGS = ChronoSettings()
BALL = (100.0, 100.0)


def _box(track_id, team, feet_y, height=40.0):
    return {"track_id": track_id, "team": team, "x1": 90.0, "y1": feet_y - height, "x2": 110.0, "y2": feet_y}


def _owner(track_id=411, team="black"):
    return _Control(track_id, team, 40.8, 41.0, (100.0, 128.0), 40.0)


def test_owner_in_reach_keeps_ball_from_slightly_closer_teammate_20261011T203728291Z():
    owner_box = _box(411, "black", 128.0)  # 0.70 heights from the ball
    stacked = _box(12, "black", 118.0)  # 0.45 heights: only a little closer
    assert _owner_keeps(stacked, _owner(), BALL, [owner_box, stacked], SETTINGS) is owner_box


def test_clearly_closer_teammate_takes_the_ball_20261011T203728292Z():
    owner_box = _box(411, "black", 128.0)
    receiver = _box(12, "black", 102.0)  # 0.05 heights: clearly at the ball
    assert _owner_keeps(receiver, _owner(), BALL, [owner_box, receiver], SETTINGS) is receiver


def test_owner_out_of_reach_or_opponent_is_not_kept_20261011T203728293Z():
    far_owner = _box(411, "black", 140.0)  # 1.0 heights: out of reach
    stacked = _box(12, "black", 118.0)
    assert _owner_keeps(stacked, _owner(), BALL, [far_owner, stacked], SETTINGS) is stacked
    opponent = _box(9, "red", 118.0)
    owner_box = _box(411, "black", 128.0)
    assert _owner_keeps(opponent, _owner(), BALL, [owner_box, opponent], SETTINGS) is opponent
