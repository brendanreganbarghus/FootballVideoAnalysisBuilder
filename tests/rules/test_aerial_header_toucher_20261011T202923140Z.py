"""Rule: a header in the air is credited to the player whose head is at the ball.

Law 12 allows a touch with any part of the body except the hands. A ball in
the air can hang almost still in the picture and then leave fast in a new
direction: that is a header. One camera draws players who stand metres apart
on top of each other, so a ball in the air is contested only by an opponent
standing at about the same spot (feet close to the header's feet) whose head
is not below the ball.
"""

from __future__ import annotations

from football_poc.chrono_engine import ChronoSettings, _ball_deflected, _toucher

SETTINGS = ChronoSettings()


def _box(track_id, team, x1, y1, x2, y2):
    return {"track_id": track_id, "team": team, "x1": x1, "y1": y1, "x2": x2, "y2": y2}


def test_hanging_ball_that_leaves_fast_is_a_header_20261011T202923140Z():
    before, at, after = (15.8, 1528.0, 580.0), (16.0, 1528.0, 586.0), (16.2, 1495.0, 604.0)
    assert _ball_deflected(before, at, after, SETTINGS, aerial=True)
    assert not _ball_deflected(before, at, after, SETTINGS)


def test_header_not_contested_by_players_below_or_far_behind_20261011T202923141Z():
    header = _box(19, "red", 1536, 574, 1566, 648)
    below = _box(63, "black", 1520, 596, 1565, 647)  # head under the ball
    behind = _box(108, "black", 1483, 556, 1515, 606)  # metres further back
    ball = (1528.0, 586.0)
    boxes = [header, below, behind]
    assert _toucher(ball, boxes, SETTINGS, aerial=True) is header
    assert _toucher(ball, boxes, SETTINGS) is None


def test_opponent_at_the_same_spot_still_contests_header_20261011T202923142Z():
    header = _box(19, "red", 1536, 574, 1566, 648)
    beside = _box(70, "black", 1500, 580, 1530, 650)  # head level, same spot
    assert _toucher((1528.0, 586.0), [header, beside], SETTINGS, aerial=True) is None
