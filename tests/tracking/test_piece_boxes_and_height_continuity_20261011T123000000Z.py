"""Rule: a cut-off piece of a person is not a separate player.

YOLO sometimes boxes only the legs or head of a player who already has a full
box in the same frame. Such a short box lying inside the taller box is dropped
before tracking, and a track prefers the next box of a similar height so a
cut-off piece cannot take over a full player's track.
"""

from __future__ import annotations

from football_poc.player_tracking import (
    PlayerPoint,
    _associate_players,
    _drop_piece_boxes,
)


def _point(frame, x1, y1, x2, y2, confidence=0.8):
    return PlayerPoint(frame, frame / 25, confidence, x1, y1, x2, y2)


def test_short_box_inside_taller_box_is_dropped_20261011T123000000Z():
    full = _point(0, 100, 100, 130, 180)
    legs = _point(0, 102, 150, 128, 180)
    other = _point(0, 300, 100, 330, 180)

    kept = _drop_piece_boxes([full, legs, other])

    assert kept == [full, other]


def test_two_overlapping_full_players_are_both_kept_20261011T123000001Z():
    front = _point(0, 100, 100, 130, 180)
    behind = _point(0, 110, 95, 140, 172)

    assert _drop_piece_boxes([front, behind]) == [front, behind]


def test_track_follows_full_box_not_closer_cut_off_piece_20261011T123000002Z():
    start = [_point(frame, 100, 100, 130, 180) for frame in (0, 5)]
    # The legs piece has the closer foot; the full box is a few pixels away.
    legs = _point(10, 101, 160, 129, 181, confidence=0.6)
    full = _point(10, 85, 101, 113, 182, confidence=0.6)

    tracks = _associate_players(
        [*start, legs, full],
        max_gap_seconds=0.5,
        max_speed_pixels_per_second=700,
    )

    first = next(track for track in tracks if track.points[0] is start[0])
    assert first.points[-1] is full
