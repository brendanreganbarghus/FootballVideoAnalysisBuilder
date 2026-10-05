"""Rule: when a pass is cut at a later contested contact, the recovered
receiver touch must come after the release. The sender's own presence at the
release frame is not a receiver touch, so no receiver-less pass is kept."""

from football_poc.engine.common import PredictedEvent
from football_poc.possession import infer_deferred_contested_turnovers


def _run(monkeypatch, ball_seconds):
    monkeypatch.setattr(
        "football_poc.possession._receiver_team_evidence",
        lambda *args, **kwargs: ("red", 0.9, 4.0),
    )
    monkeypatch.setattr(
        "football_poc.possession._contested_contact_seconds",
        lambda *args, **kwargs: 1.0,
    )
    monkeypatch.setattr(
        "football_poc.possession._nearby_ball_teams",
        lambda *args, **kwargs: {"black"},
    )
    spanning = PredictedEvent("pass_candidate", 0.5, "black", 1, 2, 0.8, "", 2.0)
    terminal = PredictedEvent("turnover_candidate", 3.0, "black", 2, 3, 0.8, "", 3.4)
    balls = {
        round(s * 25): [{"track_id": 1, "clip_seconds": s, "x": 0, "y": 0}]
        for s in ball_seconds
    }
    return infer_deferred_contested_turnovers(
        [spanning, terminal], {}, balls, minimum_speed_pixels_per_second=45
    )


def _recovered(events):
    return [e for e in events if e.details.startswith("Receiver validation")]


def test_release_frame_is_not_receiver_touch_20261005T051907600Z(monkeypatch):
    assert _recovered(_run(monkeypatch, [0.5])) == []


def test_touch_after_release_is_recovered_20261005T051907601Z(monkeypatch):
    recovered = _recovered(_run(monkeypatch, [0.5, 0.8]))
    assert [e.completion_seconds for e in recovered] == [0.8]
