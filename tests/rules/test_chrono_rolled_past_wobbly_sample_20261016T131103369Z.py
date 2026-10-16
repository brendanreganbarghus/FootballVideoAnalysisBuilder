"""Rule: a ball that leaves a player on the line and pace it came in on was not received.

A ground pass may roll past an opponent's legs over several samples. One
noisy ball position while the ball is at his feet can break the single-step
"rolls through" check. The step into his reach and the step out of it are
compared instead: if the ball leaves on the same line at the same pace, the
player did not receive it and no turnover is created. A ball that turns or
slows sharply at the player still counts as his.
"""

from __future__ import annotations

from football_poc.chrono_engine import ChronoSettings, _rolled_past, run_chronological

SETTINGS = ChronoSettings()
BOUNDARY = ((0.0, 0.0), (1200.0, 0.0), (1200.0, 1000.0), (0.0, 1000.0))
RED = (520.0, 500.0)


def _box(track_id, team, feet_x, feet_y, height=100.0):
    return {
        "track_id": track_id,
        "team": team,
        "x1": feet_x - 15.0,
        "y1": feet_y - height,
        "x2": feet_x + 15.0,
        "y2": feet_y,
    }


def _play(leave=None):
    """Black 1 dribbles, then passes along the ground past red 2 to black 3."""
    samples = [(round(0.2 * i, 1), 200.0 + 14.0 * i, 500.0 + (3.0 if i % 2 else 0.0)) for i in range(6)]
    roll = [270.0, 320.0, 370.0, 420.0, 470.0, None, 570.0, 620.0, 670.0, 720.0, 770.0]
    for k, x in enumerate(roll):
        t = round(1.2 + 0.2 * k, 1)
        # The sample at the red player's feet is noisy.
        samples.append((t, 513.0, 512.0) if x is None else (t, x, 500.0))
    if leave is not None:
        samples = [s for s in samples if s[0] <= 2.4] + leave
    else:
        samples += [(3.4, 772.0, 501.0), (3.6, 771.0, 500.0), (3.8, 772.0, 501.0)]
    players, balls = {}, {}
    for t, x, y in samples:
        frame = round(t * 25)
        balls[frame] = [{"clip_seconds": t, "x": x, "y": y, "state": "observed", "confidence": 0.9}]
        players[frame] = [
            dict(_box(1, "black", x if t <= 1.0 else 270.0, 500.0), clip_seconds=t),
            dict(_box(2, "red", *RED), clip_seconds=t),
            dict(_box(3, "black", 770.0, 500.0), clip_seconds=t),
        ]
    track = [(f, rows[0]["clip_seconds"], rows[0]["x"], rows[0]["y"]) for f, rows in sorted(balls.items())]
    return players, balls, track


def test_ball_rolling_past_with_a_wobbly_sample_is_not_received_20261016T131103369Z():
    players, balls, track = _play()
    index = next(i for i, sample in enumerate(track) if sample[1] == 2.0)
    assert _rolled_past(track, index, 2, players, SETTINGS, set()) == 2.4
    result = run_chronological(players, balls, BOUNDARY, SETTINGS)
    pairs = [(e["from_player_track_id"], e["to_player_track_id"]) for e in result.events]
    assert pairs == [(1, 3)]
    assert result.events[0]["event_type"] == "pass_candidate"


def test_ball_turning_away_at_the_player_was_received_20261016T131103370Z():
    leave = [(2.6, 540.0, 560.0), (2.8, 545.0, 610.0)]
    players, _, track = _play(leave=leave)
    index = next(i for i, sample in enumerate(track) if sample[1] == 2.0)
    assert _rolled_past(track, index, 2, players, SETTINGS, set()) is None


def test_estimated_sample_at_the_player_gives_no_pass_by_20261016T131103371Z():
    players, _, track = _play()
    index = next(i for i, sample in enumerate(track) if sample[1] == 2.0)
    wobble = next(i for i, sample in enumerate(track) if sample[1] == 2.2)
    assert _rolled_past(track, index, 2, players, SETTINGS, {wobble}) is None
