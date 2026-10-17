"""Rule: a smooth gap path excuses a blurred ball colour only while at
least three of its points are not far from the ball's colour."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking
from football_poc.ball_tracking import BallPoint, BallTrack, FrameLedger

BOOTS = {1330, 1340, 1355}


def _point(frame: int, x: float, y: float, smooth: bool = True) -> BallPoint:
    return BallPoint(
        source_frame=frame,
        clip_seconds=frame / 25.0,
        confidence=0.02,
        x=x,
        y=y,
        box_diagonal=14.0,
        smooth_gap_path=smooth,
    )


def _colour(boots: set[int]):
    def matches(point: BallPoint) -> bool:
        return False

    matches.far_from_ball = lambda point: point.source_frame in boots
    return matches


def _run(boots: set[int]):
    ledger = FrameLedger((f, f / 25.0) for f in range(1315, 1370, 5))
    for frame, x in ((1315, 1019.0), (1365, 1060.0)):
        ledger.confirm(
            frame, x=x, y=1136.0, confirming_module="00", evidence={},
            confidence=0.8,
        )
    path = [_point(f, 1020.0 + (f - 1315), 1130.0) for f in (1320, 1330, 1340, 1355)]
    records = {
        f: {"detections": [{
            "class_name": "person", "confidence": 0.9,
            "x1": 1000.0, "y1": 1040.0, "x2": 1060.0, "y2": 1140.0,
        }]}
        for f in range(1315, 1370, 5)
        if f != 1320
    }
    return ball_tracking._confirm_track_points_from_module(
        ledger, "04", [BallTrack(1, path)], records_by_frame=records, fps=25.0,
        max_speed_pixels_per_second=1600.0, ball_colour_matches=_colour(boots),
    )


def test_smooth_path_needs_ball_coloured_points_20261017T162104875Z() -> None:
    """Of four faint boxes on one smooth path, three are boots far from the
    ball's colour. The fourth, away from any player's feet, is not kept: one
    box is not a path. With only one boot, the other boxes still form a path.
    """
    ledger = _run(BOOTS)
    assert ledger.confirmed(1320) is None
    reasons = [r["reason"] for r in ledger.entries[1320].rejection_reasons]
    assert reasons == ["smooth_path_mostly_boots"]

    ledger = _run({1355})
    assert ledger.confirmed(1320) is not None
