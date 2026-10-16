"""Rule: pieces of one blurred ball streak are one ball, not rival flights."""

from __future__ import annotations

import football_poc.ball.aerial as aerial

ANCHOR = (0, 1000.0, 600.0)


def _ball(t: float) -> tuple[float, float]:
    return 1000.0 + 30.0 * t, 600.0 + 12.0 * t


def _blobs() -> dict[int, list[tuple[float, float]]]:
    # A fast ball blurs into a streak that breaks into pieces; the front
    # piece is where the ball will be one and a half frames later.
    return {t: [_ball(t), _ball(t + 1.5)] for t in range(1, 31)}


def test_aerial_streak_copy_not_rival_20261016T105827697Z() -> None:
    """A trail along the front pieces runs on the same line, offset in time.

    At the same frame it is more than the rival separation from the trail
    along the ball itself, yet it never leaves that path, so it is the same
    ball and the flight is accepted. A trail beside the path is still a
    rival.
    """
    best_at = {t: _ball(t) for t in range(1, 31)}
    copy = [(t, *_ball(t + 1.5)) for t in range(1, 31)]
    assert not aerial._aerial_runs_apart(best_at, copy, 30.0)
    beside = [(t, x, y - 40.0) for t, x, y in copy]
    assert aerial._aerial_runs_apart(best_at, beside, 30.0)

    track = aerial._aerial_one_sided_track(ANCHOR, _blobs(), 25.0)
    assert track is not None
    assert track[-1][0] >= 29
