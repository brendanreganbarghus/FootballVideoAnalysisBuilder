"""Rule: a lone re-found ball sighting off the ball's unbroken line is not the ball.

When the ball keeps one direction before, across and after a re-found
sighting, nothing touched it there; a sighting clearly off that line is
something else (a boot, for example) and is not used as a ball position.
A sighting where the ball's line really turns is kept.
"""

from __future__ import annotations

import random

from football_poc.chrono_engine import (
    ChronoSettings,
    _off_line_sightings,
    _position_noise_px,
)


def _straight_track():
    wobble = random.Random(1)
    return [
        (5 * i, 0.2 * i, 100.0 + 20 * i + wobble.uniform(-1, 1), 300.0 + wobble.uniform(-1, 1))
        for i in range(20)
    ]


def _dropped(track, reacquired):
    settings = ChronoSettings()
    noise = _position_noise_px(track, settings)
    assert noise > 0
    return _off_line_sightings(track, reacquired, settings, noise)


def test_off_line_reacquired_sighting_is_dropped_20261014T151622232Z():
    track = _straight_track()
    frame, seconds, x, y = track[8]
    track[8] = (frame, seconds, x, y + 40.0)

    assert _dropped(track, {8}) == {8}


def test_observed_or_on_line_sightings_are_kept_20261014T151622233Z():
    track = _straight_track()
    frame, seconds, x, y = track[8]
    track[8] = (frame, seconds, x, y + 40.0)

    assert _dropped(track, set()) == set()
    assert _dropped(_straight_track(), {8}) == set()


def test_sighting_where_the_ball_turns_is_kept_20261014T151622234Z():
    track = _straight_track()
    corner_x, corner_y = track[8][2], track[8][3]
    for i in range(9, 20):
        frame, seconds, _, _ = track[i]
        track[i] = (frame, seconds, corner_x, corner_y + 20.0 * (i - 8))

    assert _dropped(track, {8}) == set()
