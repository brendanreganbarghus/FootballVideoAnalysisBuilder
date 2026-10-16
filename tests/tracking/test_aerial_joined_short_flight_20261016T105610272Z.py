"""Rule: a flight under 0.8 seconds counts when a trail joins both gap ends."""

from __future__ import annotations

import football_poc.ball.aerial as aerial

START = (0, 500.0, 700.0)


def _flight(t: int) -> tuple[float, float]:
    u = t - 8
    return 540.0 + 15.0 * u, 660.0 - 25.0 * u + 1.0 * u * u


END = (20, *_flight(20))


def _blobs(with_roll: bool) -> dict[int, list[tuple[float, float]]]:
    blobs = {t: [_flight(t)] for t in range(9, 20)}
    for t in range(1, 9):
        blobs[t] = [(500.0 + 5.0 * t, 700.0 - 5.0 * t)] if with_roll else []
    return blobs


def test_aerial_joined_short_flight_20261016T105610272Z() -> None:
    """A ball rolled to a player and kicked up flies under a second.

    The flight seen from the later confirmed end lasts only 0.44 seconds,
    too short to stand alone. It is accepted because the trail follower
    joins its kick point to the earlier confirmed end; without that trail
    the gap stays open.
    """
    blobs = _blobs(with_roll=True)
    assert aerial._aerial_one_sided_track(
        (0, END[1], END[2]), {END[0] - t: c for t, c in blobs.items()}, 25.0,
    ) is None
    tracks = aerial._aerial_joined_tracks(START, END, blobs, blobs, 25.0)
    assert len(tracks) == 1
    frames = [t for t, _, _ in tracks[0]]
    assert frames[0] <= 2 and frames[-1] == 19
    (x, y), _ = aerial._aerial_track_position(tracks[0], 14)
    assert abs(x - _flight(14)[0]) < 1.0 and abs(y - _flight(14)[1]) < 1.0

    lonely = _blobs(with_roll=False)
    assert aerial._aerial_joined_tracks(START, END, lonely, lonely, 25.0) == []
