"""Rule: a thin sliver inside a player's box is a piece of that player.

YOLO sometimes boxes a narrow vertical sliver of a player who already has a
full box in the same frame. Such a sliver must be dropped before tracking, so
a nearby track whose own player was missed cannot jump onto it.
"""

from __future__ import annotations

from football_poc.player_tracking import PlayerPoint, _drop_piece_boxes


def _point(frame, x1, y1, x2, y2, confidence=0.8):
    return PlayerPoint(frame, frame / 25, confidence, x1, y1, x2, y2)


def test_thin_sliver_inside_wider_box_is_dropped_20261011T160000000Z():
    full = _point(0, 100, 100, 146, 166)
    sliver = _point(0, 100, 101, 107, 141, confidence=0.2)

    assert _drop_piece_boxes([full, sliver]) == [full]


def test_two_players_in_one_merged_box_are_kept_20261011T160000001Z():
    merged = _point(0, 100, 100, 160, 180)
    left_player = _point(0, 100, 102, 130, 180)

    assert _drop_piece_boxes([merged, left_player]) == [merged, left_player]
