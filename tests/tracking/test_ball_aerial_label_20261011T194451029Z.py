"""Rule: the ball tracker labels every ball-state frame ``aerial`` true or false.

A kicked ball climbs fast in the picture and comes back down by a clear share
of its climb. A ball rolling away from the camera climbs slowly and does not
come back, so it is not in the air. Coordinates are never changed.
"""

from __future__ import annotations

from football_poc.ball.aerial_labels import label_aerial_states


def _states(ys, state="observed"):
    return [{"source_frame": i * 5, "clip_seconds": i * 0.2, "x": 500.0 + 20 * i,
             "y": float(y), "state": state} for i, y in enumerate(ys)]


PERSON = {"class_name": "person", "confidence": 0.9, "x1": 480.0, "y1": 420.0,
          "x2": 700.0, "y2": 500.0}


def _people(states):
    return {s["source_frame"]: [PERSON] for s in states}


def test_kicked_ball_is_aerial_from_climb_to_landing_20261011T194451029Z():
    states = _states([500, 500, 460, 430, 410, 400, 410, 430, 460, 500, 500])
    label_aerial_states(states, _people(states))
    assert [s["aerial"] for s in states] == [False, False, True, True, True, True,
                                             True, True, True, False, False]
    assert [s["y"] for s in states][2] == 460.0


def test_slow_roll_away_from_camera_is_not_aerial_20261011T194451030Z():
    states = _states([500, 495, 490, 485, 480, 475, 470, 465, 460, 470, 480])
    label_aerial_states(states, _people(states))
    assert not any(s["aerial"] for s in states)


def test_unseen_frames_are_not_aerial_20261011T194451031Z():
    states = _states([500, 500, 460, 430, 410, 400, 410, 430, 460, 500, 500],
                     state="interpolated")
    label_aerial_states(states, _people(states))
    assert not any(s["aerial"] for s in states)
