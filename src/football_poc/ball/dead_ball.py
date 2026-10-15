"""A dead ball rests still, then leaves its spot.

A ball can rest anywhere on the pitch for a free kick, a kick-off or any other
restart, with no player at its feet for many seconds. A fixed object (a pitch
marking, a sprinkler, an object beside the pitch) also stays still, but it
never leaves: it is detected again at the same spot later in the clip, or it is
seen on and off. A still object therefore counts as a dead ball only when it is
seen continuously and the spot then stays empty for the rest of the clip, with
enough clip left to observe that.
"""

from __future__ import annotations

from math import hypot
from typing import Iterable

from .types import BallPoint

DEAD_BALL_MAXIMUM_GAP_SECONDS = 0.56
DEAD_BALL_MINIMUM_EMPTY_SECONDS = 1.0


def departed_dead_ball(
    resting: Iterable[BallPoint],
    *,
    all_points: Iterable[BallPoint],
    radius_pixels: float,
    clip_end_seconds: float,
) -> bool:
    """Return True when a still run of detections is a ball that left.

    Every detection at the run's spot over the whole clip must form one
    continuous run that ends at least the minimum empty time before the clip
    ends, so the spot is seen empty afterwards.
    """
    resting = list(resting)
    if len(resting) < 2:
        return False
    center_x = sum(point.x for point in resting) / len(resting)
    center_y = sum(point.y for point in resting) / len(resting)
    at_spot = sorted(
        {
            *resting,
            *(
                point
                for point in all_points
                if hypot(point.x - center_x, point.y - center_y)
                <= radius_pixels
            ),
        },
        key=lambda point: point.clip_seconds,
    )
    if any(
        second.clip_seconds - first.clip_seconds > DEAD_BALL_MAXIMUM_GAP_SECONDS
        for first, second in zip(at_spot, at_spot[1:])
    ):
        return False
    return clip_end_seconds - at_spot[-1].clip_seconds >= (
        DEAD_BALL_MINIMUM_EMPTY_SECONDS
    )
