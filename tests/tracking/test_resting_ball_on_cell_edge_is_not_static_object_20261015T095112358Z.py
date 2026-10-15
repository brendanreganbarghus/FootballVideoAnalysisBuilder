"""Rule: a ball resting on a grid-cell edge is not a fixed pitch object.

A dead ball (free kick, kick-off, any restart) can rest anywhere on the pitch.
Its detections jitter by a pixel, so when it rests on the edge of the static
grid they alternate between two neighbouring cells. Each cell alone then looks
like an object seen on and off, which is the signature of a fixed marking.
Continuity is judged on every detection at the spot, so a continuously seen
resting ball stays a ball, while a truly intermittent object is still flagged.
"""

from __future__ import annotations

from football_poc.ball_tracking import (
    BallPoint,
    _BallCandidate,
    _unanchored_static_clusters,
)


def _candidates(frames, x_for):
    return [
        _BallCandidate(
            BallPoint(frame, frame / 25, 0.6, x_for(frame), 918.0),
            near_player_feet=False,
        )
        for frame in frames
    ]


def test_resting_ball_on_cell_edge_is_not_static_object_20261015T095112358Z():
    # 3249.8 rounds to cell 162 and 3250.6 to cell 163 (cell size 20).
    frames = range(0, 245, 5)
    candidates = _candidates(
        frames, lambda frame: 3249.8 if (frame // 5) % 3 else 3250.6
    )

    assert _unanchored_static_clusters(
        candidates, cell_size=20, maximum_continuous_gap_seconds=0.56
    ) == ()


def test_intermittent_object_across_cell_edge_is_still_flagged_20261015T095112359Z():
    frames = [0, 5, 10, 100, 105, 110, 200, 205, 210]
    candidates = _candidates(
        frames, lambda frame: 3249.8 if (frame // 5) % 2 else 3250.6
    )

    clusters = _unanchored_static_clusters(
        candidates, cell_size=20, maximum_continuous_gap_seconds=0.56
    )

    assert clusters
