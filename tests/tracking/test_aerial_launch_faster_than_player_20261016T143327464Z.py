"""Rule: a one-sided flight must leave faster than a player can run."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking

ANCHOR = (0, 1000.0, 600.0)


def _trail(step: float, frames: int = 60) -> dict[int, list[tuple[float, float]]]:
    return {
        t: [(1000.0 - step * t, 600.0 - 0.4 * step * t + 0.01 * t * t)]
        for t in range(1, frames + 1)
    }


def _records(height: float) -> dict[int, dict]:
    # Players get taller towards the bottom of the image.
    return {
        0: {
            "detections": [
                {"class_name": "person", "confidence": 0.9,
                 "x1": 0.0, "x2": 20.0, "y1": 400.0 - 0.8 * height, "y2": 400.0},
                {"class_name": "person", "confidence": 0.9,
                 "x1": 0.0, "x2": 20.0, "y1": 800.0 - 1.2 * height, "y2": 800.0},
            ]
        }
    }


def test_aerial_launch_faster_than_player_20261016T143327464Z() -> None:
    """A trail slower than a jogging player is the player, not a kicked ball.

    The one-sided flight finder follows any straight motion trail leaving a
    confirmed ball. A player's legs or kit moving at running pace leave such a
    trail too. A kicked aerial ball leaves far faster, so the trail's launch
    speed must be at least three player heights per second, with the height
    taken from the people detected at that image row so the near and far side
    of the pitch are judged alike.
    """
    height_at = ball_tracking._aerial_player_height_at(_records(80.0))
    assert height_at is not None
    assert abs(height_at(600.0) - 80.0) < 1e-6

    # 5 px a frame is 125 px/s: about 1.6 player heights a second.
    slow = _trail(5.0)
    assert ball_tracking._aerial_one_sided_track(ANCHOR, slow, 25.0) is not None
    assert ball_tracking._aerial_one_sided_track(
        ANCHOR, slow, 25.0, height_at=height_at
    ) is None

    # 12 px a frame is 300 px/s: about 3.8 player heights a second.
    fast = _trail(12.0)
    track = ball_tracking._aerial_one_sided_track(
        ANCHOR, fast, 25.0, height_at=height_at
    )
    assert track is not None
    assert (track[0][0], track[-1][0]) == (1, 60)

    # Without people there is no scale, so the speed is not judged.
    assert ball_tracking._aerial_player_height_at({0: {"detections": []}}) is None
