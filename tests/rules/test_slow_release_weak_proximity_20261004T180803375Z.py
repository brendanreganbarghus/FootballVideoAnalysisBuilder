"""Rule: a pass whose receiver was only near the ball before the inferred
release is kept; only a controlled receiver touch before the release makes the
pass non-causal."""

from football_poc.engine.common import PredictedEvent
from football_poc.engine.pass_cleanup import suppress_noncausal_nonreturn_passes
from rule_builders import observation


def _filtered(receiver_ratio_before_release):
    event = PredictedEvent(
        "pass_candidate",
        4.6,
        "black",
        17,
        43,
        0.6,
        "Ball release at 129.25 pixels/second followed by black control "
        "after -0.20s.",
        4.8,
    )
    observations = [
        observation(3.4, "black", 17, 0.0, 0.0, 0.6),
        observation(3.6, "black", 17, 0.0, 0.0, 1.0),
        observation(4.4, "black", 43, 100.0, 80.0, receiver_ratio_before_release),
        observation(4.8, "black", 43, 100.0, 100.0, 0.2),
    ]
    return suppress_noncausal_nonreturn_passes([event], observations=observations)


def test_weak_proximity_before_slow_release_keeps_pass_20261004T180803375Z():
    assert [(e.from_player_track_id, e.to_player_track_id) for e in _filtered(1.18)] == [
        (17, 43)
    ]


def test_controlled_touch_before_release_still_suppresses_pass_20261004T180803376Z():
    assert _filtered(0.5) == []
