from football_poc.actions import ActionEngine, Detection


def person(track_id: int, x: float, y: float = 0) -> Detection:
    return Detection(track_id, "person", 0.9, x, y, x + 20, y + 100)


def ball(x: float, y: float) -> Detection:
    return Detection(100, "sports ball", 0.8, x, y, x + 8, y + 8)


def test_person_motion_states_use_normalized_image_speed() -> None:
    engine = ActionEngine()

    states, _ = engine.update(0.0, [person(1, 0), person(2, 0)])
    assert states == {1: "unknown", 2: "unknown"}

    states, _ = engine.update(1.0, [person(1, 2), person(2, 200)])
    assert states[1] == "stationary"
    assert states[2] == "running"


def test_ball_departure_creates_reviewable_candidate() -> None:
    engine = ActionEngine()

    _, initial_events = engine.update(0.0, [person(1, 0), ball(6, 92)])
    assert [event.event_type for event in initial_events] == [
        "ball_control_candidate"
    ]

    _, departure_events = engine.update(0.2, [person(1, 0), ball(206, 92)])
    assert [event.event_type for event in departure_events] == [
        "pass_or_shot_candidate"
    ]
    assert departure_events[0].actor_track_id == 1


def test_missing_ball_does_not_invent_an_event() -> None:
    engine = ActionEngine()
    engine.update(0.0, [person(1, 0), ball(6, 92)])

    _, events = engine.update(0.2, [person(1, 0)])

    assert events == []

