"""Rule: a ball-out-of-pitch spell found from the runtime ball file stops
play (Law 9). A ball carried or handed back in to a player who then sets it
up is only relocated, not restarted, so a "pass" completed during that setup
(for example by a ball boy) is not allowed; play resumes at the later kick."""

from football_poc.engine.boundary_restart import (
    annotate_restart_releases,
    extend_restarts_through_ball_setup,
)
from football_poc.engine.common import (
    PossessionSegment,
    runtime_ball_boundary_intervals,
)
from football_poc.match_state import build_match_state_timeline
from rule_builders import observation

PITCH = ((0.0, 0.0), (1000.0, 0.0), (1000.0, 1000.0), (0.0, 1000.0))


def _ball_track():
    xs = {}
    for step in range(0, 5):
        xs[step * 0.2] = -100.0
    xs[1.0] = 50.0
    xs[1.2] = 200.0
    for step in range(7, 21):
        xs[step * 0.2] = 300.0
    xs[4.2] = 600.0
    xs[4.4] = 800.0
    xs[4.6] = 950.0
    return {
        round(seconds * 25): [
            {"clip_seconds": round(seconds, 3), "x": x, "y": 500.0, "confidence": 0.9}
        ]
        for seconds, x in xs.items()
    }


def _timeline(balls):
    intervals = runtime_ball_boundary_intervals(balls, PITCH)
    intervals = annotate_restart_releases(
        intervals, balls, minimum_speed_pixels_per_second=200.0
    )
    setup = PossessionSegment(
        "black",
        19,
        [observation(seconds / 10, "black", 19, 300, 300) for seconds in range(14, 38, 2)],
    )
    ball_points = [point for points in balls.values() for point in points]
    intervals = extend_restarts_through_ball_setup(intervals, [setup], ball_points)
    return build_match_state_timeline(intervals, duration_seconds=6.0)


def test_runtime_ball_out_spell_is_detected_20261005T134728452Z():
    intervals = runtime_ball_boundary_intervals(_ball_track(), PITCH)
    assert [(i["start_seconds"], i["resumed_seconds"]) for i in intervals] == [
        (0.0, 1.0)
    ]


def test_relocation_to_setup_player_is_not_a_pass_20261005T134728453Z():
    timeline = _timeline(_ball_track())
    assert not timeline.allows_event("pass_candidate", 1.0, 1.4)


def test_play_resumes_at_kick_after_setup_20261005T134728454Z():
    timeline = _timeline(_ball_track())
    assert timeline.allows_event("pass_candidate", 4.2, 4.6)
