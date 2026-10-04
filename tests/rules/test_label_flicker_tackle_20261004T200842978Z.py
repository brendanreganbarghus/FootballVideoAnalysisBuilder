"""Rule: during a tackle where one player's box flips team colour, the
possession change counts once. A turnover whose receiver wears the losing
colour and immediately loses the ball again, and a very short same-team pass
starting where the tackle ends, are rejected only when that colour flicker is
observed; without it a turnover followed by a quick pass is kept."""

from football_poc.engine.common import PredictedEvent
from football_poc.engine.pass_cleanup import suppress_label_flicker_tackle_artifacts


def _players(labels):
    players = {}
    for track_id, points in labels.items():
        for seconds, team in points:
            frame = round(seconds * 25)
            players.setdefault(frame, []).append(
                {"track_id": track_id, "clip_seconds": seconds, "team": team}
            )
    return players


def _labels(track_id, start, end, team):
    count = round((end - start) / 0.2) + 1
    return [(round(start + index * 0.2, 1), team) for index in range(count)]


def _tackle_events():
    return [
        PredictedEvent("turnover_candidate", 48.0, "black", None, 7, 0.65, "", 48.0),
        PredictedEvent("turnover_candidate", 48.8, "red", 7, 9, 0.65, "", 50.6),
        PredictedEvent("pass_candidate", 50.6, "black", 9, 11, 0.7, "", 50.8),
        PredictedEvent("pass_candidate", 50.8, "black", 11, 12, 0.8, "", 52.4),
    ]


def test_flickering_tackle_counts_once_20261004T200842978Z():
    flicker = _labels(7, 47.8, 48.4, "black") + _labels(7, 48.6, 50.2, "red")
    flicker += _labels(7, 50.4, 51.0, "black")
    players = _players(
        {
            7: flicker,
            9: _labels(9, 48.0, 51.0, "black"),
            11: _labels(11, 48.0, 53.0, "black"),
        }
    )
    kept = suppress_label_flicker_tackle_artifacts(_tackle_events(), players)
    assert [(event.event_type, event.team, event.clip_seconds) for event in kept] == [
        ("turnover_candidate", "red", 48.8),
        ("pass_candidate", "black", 50.8),
    ]


def test_stable_colours_keep_turnover_and_quick_pass_20261004T200842979Z():
    players = _players(
        {
            7: _labels(7, 47.8, 51.0, "red"),
            9: _labels(9, 48.0, 51.0, "black"),
            11: _labels(11, 48.0, 53.0, "black"),
        }
    )
    events = _tackle_events()[1:]
    kept = suppress_label_flicker_tackle_artifacts(events, players)
    assert kept == events
