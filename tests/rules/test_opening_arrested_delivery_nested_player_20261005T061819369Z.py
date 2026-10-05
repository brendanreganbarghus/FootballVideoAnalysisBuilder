"""Rule: when the clip opens with a moving ball that is stopped at one player's
feet, and that player is split by the detector into a legs-only box nested
inside his full-body box, the two owner fragments are one player. The arrest
(incoming speed kept at most 25%) is his first controlled reception, credited
to the full-body track; sustained team control and a later teammate owner
follow."""

from football_poc.engine.common import (
    PossessionObservation,
    PossessionSegment,
    PredictedEvent,
)
from football_poc.engine.flight_receptions import infer_opening_live_reception


class _OpenPlay:
    def allows_event(self, *_args):
        return True


BALL_PATH = [
    (0.0, 2162, 804), (0.2, 2160, 816), (0.4, 2138, 862), (0.6, 2146, 874),
    (0.8, 2126, 904), (1.0, 2124, 920), (1.2, 2124, 918), (1.4, 2140, 924),
    (1.6, 2140, 944), (1.8, 2142, 954), (2.0, 2146, 958), (2.2, 2320, 1006),
]


def _balls():
    return {
        index: [{
            "track_id": 1, "source_frame": index, "clip_seconds": t,
            "x": x, "y": y,
        }]
        for index, (t, x, y) in enumerate(BALL_PATH)
    }


def _frame(seconds):
    return int(round(seconds / 0.2))


def _observation(seconds, track, ratio):
    return PossessionObservation(
        _frame(seconds), seconds, "black", track, 2090, 932, 95,
        2124, 920, ratio,
    )


def _segments():
    legs = PossessionSegment("black", 11, [
        _observation(t, 11, r)
        for t, r in ((1.0, 0.78), (1.2, 0.69), (1.4, 1.08), (1.6, 0.99))
    ])
    body = PossessionSegment("black", 50, [
        _observation(1.8, 50, 0.45), _observation(2.0, 50, 0.29),
    ])
    teammate = PossessionSegment("black", 94, [
        _observation(t, 94, 0.1) for t in (4.0, 4.2, 4.4)
    ])
    return [legs, body, teammate]


def _players(legs_y1):
    frames = {}
    for t in (1.0, 1.2, 1.4, 1.6, 1.8):
        frames[_frame(t)] = [
            {"track_id": 11, "team": "black", "clip_seconds": t,
             "x1": 2070, "y1": legs_y1, "x2": 2112, "y2": 932},
            {"track_id": 50, "team": "black", "clip_seconds": t,
             "x1": 2066, "y1": 838, "x2": 2116, "y2": 932},
        ]
    return frames


def _run(players):
    return infer_opening_live_reception(
        [], _segments(), _balls(), _OpenPlay(),
        minimum_speed_pixels_per_second=60.0,
        maximum_transfer_seconds=3.0,
        players=players,
    )


def test_arrested_opening_delivery_to_nested_player_20261005T061819369Z():
    events = _run(_players(888))
    assert len(events) == 1
    opening = events[0]
    assert isinstance(opening, PredictedEvent)
    assert (opening.event_type, opening.team) == ("pass_candidate", "black")
    assert opening.to_player_track_id == 50
    assert opening.completion_seconds == 1.0


def test_two_separate_players_not_merged_20261005T061819370Z():
    # Same-height boxes side by side are two players, not one split player.
    players = {
        frame: [
            {**box, "x1": box["x1"] + (80 if box["track_id"] == 11 else 0),
             "x2": box["x2"] + (80 if box["track_id"] == 11 else 0),
             "y1": 838}
            for box in boxes
        ]
        for frame, boxes in _players(888).items()
    }
    assert _run(players) == []
