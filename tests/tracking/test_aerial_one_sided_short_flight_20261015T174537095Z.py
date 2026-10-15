"""Rule: a followed flight lasting 0.8 seconds is accepted from one end."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking

ANCHOR = (0, 1000.0, 600.0)


def _blobs(frames: int) -> dict[int, list[tuple[float, float]]]:
    return {
        t: [(1000.0 - 12.0 * t, 600.0 - 3.0 * t + 0.1 * t * t)]
        for t in range(1, frames + 1)
    }


def test_aerial_one_sided_short_flight_20261015T174537095Z() -> None:
    """A lofted ball is often seen for under a second before players hide it.

    The trail leaving a confirmed end is accepted once it has been followed
    for 0.8 seconds (20 frames at 25 fps); a shorter trail stays open.
    """
    track = ball_tracking._aerial_one_sided_track(ANCHOR, _blobs(20), 25.0)
    assert track is not None
    assert (track[0][0], track[-1][0]) == (1, 20)
    assert ball_tracking._aerial_one_sided_track(ANCHOR, _blobs(18), 25.0) is None
