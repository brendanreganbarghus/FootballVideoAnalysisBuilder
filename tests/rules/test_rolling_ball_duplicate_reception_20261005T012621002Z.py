from football_poc.engine.common import PredictedEvent
from football_poc.engine.pass_cleanup import merge_rolling_ball_duplicate_receptions


def _balls(xs):
    return {
        round(s * 25): [
            {"track_id": 1, "source_frame": round(s * 25), "clip_seconds": s, "x": x, "y": 100}
        ]
        for s, x in xs.items()
    }


def _events():
    return [
        PredictedEvent("pass_candidate", 1.0, "red", 7, 9, 0.7, "release", completion_seconds=1.4),
        PredictedEvent("pass_candidate", 3.0, "red", None, 9, 0.55, "touch", completion_seconds=3.0),
    ]


def test_rolling_ball_duplicate_reception_20261005T012621002Z():
    rolling = _balls({1.0: 0, 1.2: 40, 1.4: 80, 1.6: 120, 1.8: 160, 3.0: 400})
    merged = merge_rolling_ball_duplicate_receptions(_events(), rolling)
    assert len(merged) == 1
    assert merged[0].from_player_track_id == 7
    assert merged[0].completion_seconds == 3.0


def test_rolling_ball_reception_with_stop_is_kept_20261005T012621003Z():
    stopped = _balls({1.0: 0, 1.2: 40, 1.4: 80, 1.6: 84, 1.8: 86, 3.0: 90})
    assert len(merge_rolling_ball_duplicate_receptions(_events(), stopped)) == 2
