"""Rule: a long turnover whose ball leaves a stationary owner, nearly stops
and is then played on faster than before with no detected player within
control distance was won by an undetected opponent at the release, so the
completion moves back to the release. A sender who follows the ball, or a
single decaying kick, keeps the later detected completion."""

from football_poc.engine.common import PredictedEvent
from football_poc.engine.pass_reconciliation import (
    backdate_unseen_carrier_dispossessions,
)

BALL = [(0.0, 1000, 500), (0.2, 980, 500), (0.4, 976, 500), (0.6, 940, 500),
        (0.8, 890, 500), (1.0, 860, 500)]
DECAY = [(0.0, 1000, 500), (0.2, 980, 500), (0.4, 976, 500), (0.6, 974, 500),
         (0.8, 973, 500), (1.0, 972, 500)]


def _balls(path):
    return {
        index: [{"track_id": 1, "source_frame": index, "clip_seconds": t,
                 "x": x, "y": y}]
        for index, (t, x, y) in enumerate(path)
    }


def _players(sender_moves):
    frames = {}
    for index in range(6):
        shift = index * 30 if sender_moves else 0
        frames[index] = [{
            "track_id": 7, "clip_seconds": round(index * 0.2, 1),
            "x1": 1040 - shift, "y1": 400, "x2": 1080 - shift, "y2": 500,
        }]
    return frames


def _run(path, sender_moves=False):
    event = PredictedEvent(
        "turnover_candidate", 0.0, "red", 7, 9, 0.7, "transfer", 1.0
    )
    return backdate_unseen_carrier_dispossessions(
        [event], _players(sender_moves), _balls(path),
        minimum_speed_pixels_per_second=60.0,
    )[0].completion_seconds


def test_unseen_retouch_backdates_turnover_20261005T073700674Z():
    assert _run(BALL) == 0.0


def test_moving_sender_keeps_completion_20261005T073700675Z():
    assert _run(BALL, sender_moves=True) == 1.0


def test_decaying_ball_keeps_completion_20261005T073700676Z():
    assert _run(DECAY) == 1.0
