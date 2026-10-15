"""Rule: a ball that rolls into a player's reach and stops dead was trapped.

Grass slows a rolling ball gently. When the ball rolls up to one player and
on the very next sample stops or turns sharply, a body stopped it: the player
it rolled to received it, even when the camera loses his box at that moment.
A teammate drawn at the ball does not contest it; an opponent at the ball
does, so then nobody is credited.
"""

from __future__ import annotations

from football_poc.chrono_engine import ChronoSettings, _trapped_next, run_chronological

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


def _play(stop_box=None):
    """Black 1 dribbles, then passes along the ground to black 2, who traps it."""
    players, balls = {}, {}
    samples = []
    for i in range(6):
        samples.append((round(0.2 * i, 1), 950.0 - 14.0 * i, 500.0 + (3.0 if i % 2 else 0.0)))
    for k in range(1, 9):
        samples.append((round(1.0 + 0.2 * k, 1), 880.0 - 30.0 * k, 500.0))
    samples += [(2.8, 615.0, 500.0), (3.0, 613.0, 501.0), (3.2, 612.0, 500.0), (3.4, 612.0, 501.0)]
    for t, x, y in samples:
        frame = round(t * 25)
        balls[frame] = [{"clip_seconds": t, "x": x, "y": y, "state": "observed", "confidence": 0.9}]
        boxes = []
        dribbling = t <= 1.0
        boxes.append(dict(_box(1, "black", x if dribbling else 880.0, 505.0), clip_seconds=t))
        if t <= 2.6:
            boxes.append(dict(_box(2, "black", 640.0, 505.0), clip_seconds=t))
        elif stop_box is not None:
            boxes.append(dict(stop_box, clip_seconds=t))
        players[frame] = boxes
    track = [(frame, rows[0]["clip_seconds"], rows[0]["x"], rows[0]["y"]) for frame, rows in sorted(balls.items())]
    return players, balls, track


def test_ball_stopping_dead_after_rolling_in_is_a_trap_20261015T041857355Z():
    players, balls, track = _play()
    index = next(i for i, sample in enumerate(track) if sample[1] == 2.6)
    receiver = _box(2, "black", 640.0, 505.0)
    assert _trapped_next(track, index, receiver, players[track[index + 1][0]], SETTINGS, 0.0)
    result = run_chronological(players, balls, BOUNDARY, SETTINGS)
    passes = [e for e in result.events if e["event_type"] == "pass_candidate"]
    assert [(e["from_player_track_id"], e["to_player_track_id"]) for e in passes] == [(1, 2)]


def test_ball_rolling_on_is_not_a_trap_20261015T041857356Z():
    _, _, track = _play()
    index = next(i for i, sample in enumerate(track) if sample[1] == 2.4)
    receiver = _box(2, "black", 640.0, 505.0)
    assert not _trapped_next(track, index, receiver, [], SETTINGS, 0.0)


def test_opponent_at_stopped_ball_blocks_the_trap_20261015T041857357Z():
    opponent = _box(9, "red", 615.0, 505.0)
    players, balls, track = _play(stop_box=opponent)
    index = next(i for i, sample in enumerate(track) if sample[1] == 2.6)
    receiver = _box(2, "black", 640.0, 505.0)
    assert not _trapped_next(track, index, receiver, players[track[index + 1][0]], SETTINGS, 0.0)


def test_teammate_at_stopped_ball_does_not_block_the_trap_20261015T041857358Z():
    teammate = _box(3, "black", 615.0, 505.0)
    players, _, track = _play(stop_box=teammate)
    index = next(i for i, sample in enumerate(track) if sample[1] == 2.6)
    receiver = _box(2, "black", 640.0, 505.0)
    assert _trapped_next(track, index, receiver, players[track[index + 1][0]], SETTINGS, 0.0)
