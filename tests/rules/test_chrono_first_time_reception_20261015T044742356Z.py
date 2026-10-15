"""Rule: a fast pass that reaches a teammate's feet is received on one sighting.

A pass played on first time is at the receiver's feet for a moment only, so
there is no second close sighting to confirm control. When the ball was
already travelling at pass speed over the two steps before, and it is then
right at the feet of a teammate of the player in control, that teammate
received it. An opponent still needs repeated sightings; a lone jump of a
still ball is not a pass.
"""

from __future__ import annotations

from football_poc.chrono_engine import ChronoSettings, run_chronological

SETTINGS = ChronoSettings()
BOUNDARY = ((0.0, 0.0), (1200.0, 0.0), (1200.0, 1000.0), (0.0, 1000.0))


def _box(track_id, team, feet_x, feet_y, height=40.0):
    return {
        "track_id": track_id,
        "team": team,
        "x1": feet_x - 12.0,
        "y1": feet_y - height,
        "x2": feet_x + 12.0,
        "y2": feet_y,
    }


def _play(first_team="black", pass_step=60.0):
    """Black 1 dribbles and passes; the ball touches player 2 once on its way to black 3."""
    samples = [(round(0.2 * i, 1), 950.0 - 14.0 * i) for i in range(6)]
    samples += [(round(1.0 + 0.2 * k, 1), 880.0 - pass_step * k) for k in range(1, 6)]
    first_x = samples[-1][1]
    samples += [(2.4, first_x - 2 * pass_step)]  # 2.2 is hidden
    stop_x = first_x - 2 * pass_step - 55.0
    samples += [(2.6, stop_x), (2.8, stop_x - 2.0), (3.0, stop_x - 3.0), (3.2, stop_x - 3.0)]
    players, balls = {}, {}
    for t, x in samples:
        frame = round(t * 25)
        balls[frame] = [{"clip_seconds": t, "x": x, "y": 500.0, "state": "observed", "confidence": 0.9}]
        players[frame] = [
            dict(_box(1, "black", x if t <= 1.0 else 880.0, 505.0), clip_seconds=t),
            dict(_box(2, first_team, first_x, 505.0), clip_seconds=t),
            dict(_box(3, "black", stop_x, 505.0), clip_seconds=t),
        ]
    return players, balls


def _passes(result):
    return [
        (e["event_type"], e["from_player_track_id"], e["to_player_track_id"])
        for e in result.events
    ]


def test_fast_pass_touching_teammate_once_is_received_20261015T044742356Z():
    players, balls = _play()
    result = run_chronological(players, balls, BOUNDARY, SETTINGS)
    assert _passes(result) == [("pass_candidate", 1, 2), ("pass_candidate", 2, 3)]


def test_opponent_needs_more_than_one_sighting_20261015T044742357Z():
    players, balls = _play(first_team="red")
    result = run_chronological(players, balls, BOUNDARY, SETTINGS)
    assert _passes(result) == [("pass_candidate", 1, 3)]


def test_slow_ball_at_teammate_once_is_not_received_20261015T044742358Z():
    players, balls = _play(pass_step=20.0)
    result = run_chronological(players, balls, BOUNDARY, SETTINGS)
    assert ("pass_candidate", 1, 2) not in _passes(result)


def test_rule_off_keeps_two_sighting_confirmation_20261015T044742359Z():
    players, balls = _play()
    settings = ChronoSettings(first_time_reception_speed_px_per_second=0.0)
    result = run_chronological(players, balls, BOUNDARY, settings)
    assert _passes(result) == [("pass_candidate", 1, 3)]
