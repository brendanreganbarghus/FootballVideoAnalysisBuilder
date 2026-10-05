"""Rule: a receiver who chases a rolling pass (weak first proximity) and is
credited on one close sample shortly afterwards has not yet received it; the
pass completes at his first sustained control (two consecutive samples within
0.5 control radius), searched up to 2.5 s after the credited completion. The
completion is never moved earlier."""

from football_poc.engine.common import PossessionSegment, PredictedEvent
from football_poc.engine.flight_receptions import (
    refine_weak_reception_completion_times,
)
from rule_builders import observation


_RATIOS = [
    (53.6, 1.4), (53.8, 0.67), (54.0, 0.21), (54.2, 0.51), (54.4, 0.84),
    (54.8, 0.65), (55.2, 0.8), (55.6, 0.51), (55.8, 0.27), (56.0, 0.54),
    (56.2, 0.3), (56.4, 0.25), (56.6, 0.19),
]


def _refine(completion):
    segment = PossessionSegment(
        "red",
        854,
        [observation(s, "red", 854, 0, 0, control_ratio=r) for s, r in _RATIOS],
    )
    event = PredictedEvent(
        "pass_candidate", 53.2, "red", 330, 854, 0.8, "transfer", completion
    )
    return refine_weak_reception_completion_times([event], [segment])[0]


def test_single_close_sample_completes_at_sustained_control_20261005T053849922Z():
    assert _refine(54.0).completion_seconds == 56.4


def test_completion_long_after_weak_start_unchanged_20261005T053849923Z():
    assert _refine(54.4).completion_seconds == 54.4
