"""Rule: a still ball that is later played away is a dead ball, not an object.

A ball can rest anywhere on the pitch for a free kick or kick-off with no
player at its feet. It is kept when it is seen continuously at one spot and the
spot then stays empty for the rest of the clip. A fixed object that is seen on
and off, or that is still there at the end of the clip, is not kept.
"""

from __future__ import annotations

from football_poc.ball_tracking import BallPoint
from football_poc.ball.dead_ball import departed_dead_ball


def _points(frames, x=3250.0, y=918.0):
    return [BallPoint(frame, frame / 25, 0.6, x, y) for frame in frames]


def test_departed_dead_ball_is_kept_20261015T104532734Z():
    resting = _points(range(0, 245, 5))
    elsewhere = _points(range(250, 1500, 5), x=2000.0, y=700.0)

    assert departed_dead_ball(
        resting,
        all_points=[*resting, *elsewhere],
        radius_pixels=6.0,
        clip_end_seconds=59.8,
    )


def test_object_still_present_at_clip_end_is_not_dead_ball_20261015T104532735Z():
    resting = _points(range(0, 245, 5))
    later = _points(range(1200, 1500, 5))

    assert not departed_dead_ball(
        resting,
        all_points=[*resting, *later],
        radius_pixels=6.0,
        clip_end_seconds=59.8,
    )


def test_intermittent_object_is_not_dead_ball_20261015T104532736Z():
    resting = _points([0, 5, 10, 100, 105, 110])

    assert not departed_dead_ball(
        resting,
        all_points=resting,
        radius_pixels=6.0,
        clip_end_seconds=59.8,
    )


def test_still_run_without_time_to_see_spot_empty_is_not_dead_ball_20261015T104532737Z():
    resting = _points(range(1300, 1495, 5))

    assert not departed_dead_ball(
        resting,
        all_points=resting,
        radius_pixels=6.0,
        clip_end_seconds=59.8,
    )
