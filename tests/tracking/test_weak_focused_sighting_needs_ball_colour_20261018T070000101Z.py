"""Rules: weak focused sightings need the ball's colour wherever they are,
and a colour walk may pass beside a head but never jumps off its path."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking
from football_poc.ball_tracking import BallPoint, BallTrack, FrameLedger


def _confirm(colour_ok: bool):
    ledger = FrameLedger((f, f / 25.0) for f in range(650, 695, 5))
    ledger.confirm(650, x=1026.0, y=635.0, confirming_module="00", evidence={}, confidence=0.8)
    point = BallPoint(670, 670 / 25.0, 0.03, 841.0, 762.0, box_diagonal=11.0)
    records = {670: {"detections": [{
        "class_name": "person", "confidence": 0.12,
        "x1": 820.0, "y1": 750.0, "x2": 860.0, "y2": 850.0,
    }]}}

    def matches(point: BallPoint) -> bool:
        return colour_ok

    matches.far_from_ball = lambda point: False
    return ball_tracking._confirm_track_points_from_module(
        ledger, "04", [BallTrack(1, [point])], records_by_frame=records,
        fps=25.0, max_speed_pixels_per_second=1600.0, ball_colour_matches=matches,
    )


def test_weak_focused_sighting_needs_ball_colour_anywhere_20261018T070000101Z() -> None:
    """A faint focused sighting at a player's head, not his feet, that does
    not have the ball's colour is a head, not the ball. With the ball's
    colour the same sighting is kept."""
    ledger = _confirm(colour_ok=False)
    assert ledger.confirmed(670) is None
    assert ledger.entries[670].rejection_reasons[-1]["reason"] == "colour_differs_from_ball"
    assert _confirm(colour_ok=True).confirmed(670) is not None


def test_colour_walk_spot_beside_head_is_not_shirt_20261018T070000352Z() -> None:
    """A ball-coloured spot in the empty top corner beside a head is behind
    the player, not on his shirt; a spot on the chest still is the shirt."""
    record = {"detections": [{
        "class_name": "person", "confidence": 0.9,
        "x1": 80.0, "y1": 80.0, "x2": 120.0, "y2": 180.0,
    }]}
    assert not ball_tracking._on_person_upper_body(83.0, 84.0, record)
    assert ball_tracking._on_person_upper_body(100.0, 120.0, record)
    assert ball_tracking._on_person_upper_body(100.0, 84.0, record)


def test_colour_walk_stops_at_a_jump_20261018T070000617Z() -> None:
    """The walk follows spots close to where the ball's movement predicts.
    A spot far from that prediction, though within the window, is another
    object: the walk stops there instead of jumping onto it."""
    spots = {5: [(110.0, 100.0)], 10: [(120.0, 100.0)], 15: [(130.0, 160.0)]}

    def blobs_near(frame, centre, half):
        return spots.get(frame, [])

    def walk(diagonal):
        return ball_tracking._colour_walk(
            (0, 100.0, 100.0), [5, 10, 15], blobs_near, velocity=(2.0, 0.0),
            fps=25.0, max_speed_pixels_per_second=2000.0, ball_diagonal=diagonal,
        )

    assert sorted(walk(14.0)) == [5, 10]
    assert sorted(walk(None)) == [5, 10, 15]
