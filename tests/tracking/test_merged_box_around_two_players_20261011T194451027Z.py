"""Rule: one weak box around two players standing one behind the other is dropped.

When two separate boxes inside it are each at least as sure as the big box,
the big box is the merge of those players, not a third player.
"""

from __future__ import annotations

from football_poc.player_tracking import PlayerPoint, _drop_piece_boxes


def _point(frame, x1, y1, x2, y2, confidence=0.8):
    return PlayerPoint(frame, frame / 25, confidence, x1, y1, x2, y2)


def test_weak_box_around_two_sure_players_is_dropped_20261011T194451027Z():
    merged = _point(0, 100, 100, 200, 180, confidence=0.3)
    left = _point(0, 100, 100, 135, 180, confidence=0.6)
    right = _point(0, 165, 100, 200, 180, confidence=0.7)

    assert _drop_piece_boxes([merged, left, right]) == [left, right]


def test_sure_box_around_two_weak_pieces_is_kept_20261011T194451028Z():
    full = _point(0, 100, 100, 200, 180, confidence=0.9)
    left = _point(0, 100, 100, 135, 180, confidence=0.3)
    right = _point(0, 165, 100, 200, 180, confidence=0.3)

    assert _drop_piece_boxes([full, left, right]) == [full]
