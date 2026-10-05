"""Rule: a deferred contested turnover is not inferred at an earlier contact
when the event's own sender re-establishes control for >= 1 s after that
contact. A team that keeps the ball did not lose it there (e.g. a brief
opposing-colour flicker on the sender's track). Without that re-established
control, the deferred turnover is still inferred."""

from football_poc.engine.common import PredictedEvent
from football_poc.possession import infer_deferred_contested_turnovers
from rule_builders import observation


def _setup(monkeypatch):
    monkeypatch.setattr(
        "football_poc.possession._receiver_team_evidence",
        lambda *args, **kwargs: ("black", 0.9, 4.0),
    )
    monkeypatch.setattr(
        "football_poc.possession._contested_contact_seconds",
        lambda *args, **kwargs: 1.0,
    )
    return PredictedEvent("turnover_candidate", 3.0, "red", 5, 9, 0.8, "", 3.4)


def _base_controls():
    return [
        observation(0.8, "red", 5, 0, 0, control_ratio=0.3),
        observation(1.2, "black", 7, 0, 0, control_ratio=0.3),
    ]


def test_sender_reestablished_skips_deferred_turnover_20261005T051133274Z(
    monkeypatch,
):
    event = _setup(monkeypatch)
    controls = _base_controls() + [
        observation(s, "red", 5, 0, 0, control_ratio=0.3)
        for s in (1.6, 2.0, 2.4, 2.8)
    ]
    result = infer_deferred_contested_turnovers(
        [event], {}, {}, controls, minimum_speed_pixels_per_second=45
    )
    assert result == [event]


def test_without_reestablished_sender_turnover_inferred_20261005T051133275Z(
    monkeypatch,
):
    event = _setup(monkeypatch)
    controls = _base_controls() + [
        observation(1.6, "red", 5, 0, 0, control_ratio=0.3),
    ]
    result = infer_deferred_contested_turnovers(
        [event], {}, {}, controls, minimum_speed_pixels_per_second=45
    )
    assert any(
        e.event_type == "turnover_candidate" and e.completion_seconds == 1.0
        for e in result
    )
