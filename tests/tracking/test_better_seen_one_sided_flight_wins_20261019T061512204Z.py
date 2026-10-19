"""Rule: the better-seen one-sided flight wins where both searches overlap.

The one-sided flight search follows the ball forwards from the last sighting
and backwards from the next one. Both can return a flight over the same
frames, for example when the forward search locks on a smear one frame behind
the ball. The flight whose ball blob was seen on more of its frames is the
better evidence, so it gives the position, whichever search found it.
"""

from __future__ import annotations

from pathlib import Path

import football_poc.ball as aerial
import football_poc.ball_tracking as ball_tracking


def _run(monkeypatch, forward_frames, backward_frames):
    ledger = ball_tracking.FrameLedger((f, f / 25) for f in range(0, 31))
    for frame, x in ((0, 0.0), (30, 300.0)):
        ledger.confirm(
            frame, x=x, y=100.0,
            confirming_module=ball_tracking.CONFIRM_YOLO_MODULE,
            evidence={}, confidence=0.8, box_diagonal=8.0,
        )

    monkeypatch.setattr(aerial, "_aerial_streamed_blobs", lambda *a, **k: {})
    monkeypatch.setattr(aerial, "_aerial_player_height_at", lambda records: None)

    def one_sided(seed, blobs, fps, height_at=None):
        if seed[0] == 0 and seed[1] == 0.0:
            # Forward: one frame behind the ball.
            return [(f, 10.0 * (f - 1), 100.0) for f in forward_frames]
        # Backward search works on mirrored frames (30 - f), on the ball.
        return [(30 - f, 10.0 * f, 100.0) for f in reversed(backward_frames)]

    monkeypatch.setattr(aerial, "_aerial_one_sided_track", one_sided)
    return aerial._confirm_one_sided_aerial_flights(
        ledger, records_by_frame={0: {}}, video=Path("unused.mp4"),
        fps=25.0, max_speed_pixels_per_second=1600.0,
    )


def test_better_seen_one_sided_flight_wins_20261019T061512204Z(monkeypatch) -> None:
    """A dense backward flight beats a patchy forward flight one frame behind."""
    patchy = [f for f in range(2, 29) if f % 3]
    dense = list(range(2, 29))
    ledger = _run(monkeypatch, patchy, dense)
    entry = ledger.entries[15]
    assert entry.status == "confirmed"
    assert entry.x == 150.0


def test_better_seen_forward_flight_still_wins_20261019T061512205Z(monkeypatch) -> None:
    """A dense forward flight keeps its place over a patchy backward one."""
    patchy = [f for f in range(2, 29) if f % 3]
    dense = list(range(2, 29))
    ledger = _run(monkeypatch, dense, patchy)
    assert ledger.entries[14].x == 130.0
