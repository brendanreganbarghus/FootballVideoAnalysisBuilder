from football_poc.engine.common import PredictedEvent
from football_poc.engine.pass_cleanup import suppress_releases_from_shadowed_senders


def _box(x, track, team="black", height=50):
    return {"track_id": track, "team": team, "x1": x - 10, "x2": x + 10, "y1": 100 - height, "y2": 100}


def _setup(keeper_x):
    balls = {f: [{"track_id": 1, "source_frame": f, "clip_seconds": f / 25, "x": 100, "y": 100}] for f in (20, 25, 30)}
    players = {f: [_box(140, 7)] for f in balls}
    unclassified = {f: [_box(keeper_x, 9, team="unknown")] for f in balls}
    event = PredictedEvent("pass_candidate", 1.3, "black", 7, 9, 0.6, "release", completion_seconds=1.6)
    return [event], players, unclassified, balls


def test_shadowed_sender_by_unreadable_kit_20261005T013513256Z():
    assert suppress_releases_from_shadowed_senders(*_setup(102)) == []


def test_sender_closer_than_unreadable_kit_is_kept_20261005T013513265Z():
    assert len(suppress_releases_from_shadowed_senders(*_setup(170))) == 1
