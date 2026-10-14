"""Rule: a one-sample blip on a ball's unbroken line is not a touch.

The ball keeps its heading and pace from two samples before to two after;
only the one sample between is off the line. That change is position wobble,
not a touch: a touch changes where the ball goes next. A player chasing the
rolling ball who stands at the blip is not credited, so the ball rolling on
to his goalkeeper is not a pass from him.
"""

from __future__ import annotations

from football_poc.chrono_engine import (
    ChronoSettings,
    _ball_deflected,
    _blip_on_unbroken_line,
    run_chronological,
)

SETTINGS = ChronoSettings()
BOUNDARY = ((0.0, 0.0), (1000.0, 0.0), (1000.0, 1000.0), (0.0, 1000.0))


def _box(track_id, team, feet_x, feet_y, height=40.0):
    return {
        "track_id": track_id,
        "team": team,
        "x1": feet_x - 12.0,
        "y1": feet_y - height,
        "x2": feet_x + 12.0,
        "y2": feet_y,
    }


def _rolling(blip_y=520.0):
    seen = [(round(0.2 * i, 1), 800.0 - 30.0 * i, 500.0) for i in range(11)]
    seen[3] = (0.6, 710.0, blip_y)
    seen += [(2.2, 500.0, 500.0), (2.4, 500.0, 500.0), (2.6, 500.0, 500.0)]
    return seen


def test_blip_on_unbroken_line_is_not_a_touch_20261014T175446581Z():
    track = [(round(t * 25), t, x, y) for t, x, y in _rolling()]
    assert _ball_deflected(track[2][1:], track[3][1:], track[4][1:], SETTINGS)
    assert _blip_on_unbroken_line(track, 3, SETTINGS)


def test_ball_that_leaves_on_a_new_line_is_not_a_blip_20261014T175446582Z():
    track = [(round(t * 25), t, x, y) for t, x, y in _rolling()]
    for i in range(4, len(track)):
        frame, seconds, x, _ = track[i]
        track[i] = (frame, seconds, x, 500.0 + 40.0 * (i - 3))
    assert not _blip_on_unbroken_line(track, 3, SETTINGS)


def test_chaser_at_blip_does_not_pass_to_keeper_20261014T175446583Z():
    players, balls = {}, {}
    for t, x, y in _rolling():
        frame = round(t * 25)
        balls[frame] = [{"clip_seconds": t, "x": x, "y": y, "state": "observed", "confidence": 0.9}]
        boxes = [dict(_box(15, "black", 500.0, 505.0), clip_seconds=t)]
        if t == 0.6:
            boxes.append(dict(_box(11, "black", 720.0, 530.0), clip_seconds=t))
        players[frame] = boxes
    result = run_chronological(players, balls, BOUNDARY, SETTINGS)
    assert not result.events
