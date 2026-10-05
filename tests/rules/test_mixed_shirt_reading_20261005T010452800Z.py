from football_poc.engine.pass_reconciliation import reconcile_track_identity_team_switches
from football_poc.possession import PredictedEvent

RED = {"white": 0.4, "warm": 0.05, "yellow": 0.15}
BLACK = {"dark": 0.4}


def _run(early_scores):
    event = PredictedEvent("turnover_candidate", 1.0, "red", 1, 2, 0.8, "flight", 2.0)
    players = {}
    for seconds, scores in [(0.6, early_scores), (0.8, early_scores), (1.0, early_scores),
                            (1.6, RED), (1.8, RED), (2.2, RED)]:
        players[round(seconds * 25)] = [
            {"track_id": 2, "clip_seconds": seconds, "team": "black", "color_scores": scores}
        ]
    return reconcile_track_identity_team_switches([event], players, maximum_chain_seconds=2)


def test_mixed_shirt_reading_keeps_turnover_20261005T010452800Z() -> None:
    assert [(e.team, e.event_type) for e in _run(BLACK)] == [("red", "turnover_candidate")]


def test_consistent_opponent_shirt_still_corrects_switch_20261005T010452833Z() -> None:
    assert [(e.team, e.event_type) for e in _run(RED)] == [("red", "pass_candidate")]
