"""Rule: a same-team pass that stops sharply before a second flight may take
up to one second in the air, plus one ball sample of margin."""

from football_poc.engine.common import PossessionSegment
from football_poc.engine.completed_pass import infer_deceleration_transfer_events
from rule_builders import observation


def _events(flight_seconds):
    sender_end = 1.0
    stop = sender_end + flight_seconds
    receiver_start = stop + 0.8
    times = [round(0.2 * step, 3) for step in range(int(receiver_start / 0.2) + 2)]

    def ball_x(seconds):
        if seconds <= sender_end:
            return 0.0
        if seconds <= stop:
            return 200.0 * (seconds - sender_end) / flight_seconds
        if seconds <= stop + 0.6:
            return 202.0
        return 202.0 + 500.0 * (seconds - stop - 0.6)

    balls = {
        round(seconds * 25): [
            {
                "track_id": 1,
                "source_frame": round(seconds * 25),
                "clip_seconds": seconds,
                "x": ball_x(seconds),
                "y": 100.0,
            }
        ]
        for seconds in times
    }
    sender = PossessionSegment(
        "black",
        57,
        [observation(seconds, "black", 57, 0.0, 0.0) for seconds in (0.8, 1.0)],
    )
    receiver = PossessionSegment(
        "black",
        84,
        [
            observation(receiver_start, "black", 84, 400.0, 400.0),
            observation(receiver_start + 0.2, "black", 84, 400.0, 400.0),
        ],
    )
    return infer_deceleration_transfer_events(
        balls,
        [sender, receiver],
        minimum_incoming_speed_pixels_per_second=45,
        maximum_outgoing_speed_ratio=0.35,
        sender_lookback_seconds=6,
        receiver_window_seconds=3,
        minimum_transfer_heights=0.5,
    )


def test_one_second_flight_before_sharp_stop_is_a_pass_20261004T144853923Z():
    events = _events(1.0)
    assert [(event.event_type, event.team) for event in events] == [
        ("pass_candidate", "black")
    ]
    assert events[0].completion_seconds == 2.0


def test_much_longer_flight_before_stop_is_not_this_pass_20261004T144853923Z():
    assert _events(1.6) == []
