"""Rule: a turn or speed-up is a touch only when it is larger than the ball's wobble.

Every ball source places the ball with some position error. On a slow ball a
few pixels of error already look like a sharp turn, which would credit a
touch (Law 12) to whoever stands nearby. The engine estimates the ball
track's own wobble from all its seen samples and only accepts a change in
movement clearly larger than that wobble as touch evidence. A track that
is too short to estimate keeps the plain turn/speed test.
"""

from __future__ import annotations

import random

from football_poc.chrono_engine import ChronoSettings, _ball_deflected, _position_noise_px

SETTINGS = ChronoSettings()


def _track(jitter: float, samples: int = 40, seed: int = 7):
    rng = random.Random(seed)
    return [
        (i * 5, i * 0.2, 500.0 + 20.0 * i + rng.gauss(0, jitter), 800.0 + rng.gauss(0, jitter))
        for i in range(samples)
    ]


def test_wobble_is_estimated_from_the_track_itself_20261012T012951368Z():
    assert _position_noise_px(_track(0.0), SETTINGS) < 0.5
    assert 3.0 < _position_noise_px(_track(5.0), SETTINGS) < 8.0


def test_short_track_has_no_wobble_estimate_20261012T012951369Z():
    assert _position_noise_px(_track(5.0, samples=8), SETTINGS) == 0.0


def test_turn_within_the_wobble_is_not_a_touch_20261012T012951370Z():
    before, at, after = (0.0, 0.0, 0.0), (0.2, 15.0, 0.0), (0.4, 25.0, 10.0)
    assert _ball_deflected(before, at, after, SETTINGS)
    assert not _ball_deflected(before, at, after, SETTINGS, noise_px=4.0)


def test_clear_kick_is_still_a_touch_on_a_wobbly_track_20261012T012951371Z():
    before, at, after = (0.0, 0.0, 0.0), (0.2, 15.0, 0.0), (0.4, 15.0, 60.0)
    assert _ball_deflected(before, at, after, SETTINGS, noise_px=4.0)
