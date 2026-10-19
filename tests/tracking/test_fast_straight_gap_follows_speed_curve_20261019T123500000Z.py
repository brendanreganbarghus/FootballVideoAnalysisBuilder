"""Rule: a fast ball that keeps its line across a long gap follows a speed curve.

A gap longer than the plain interpolation limit stays a possible region,
unless the ball leaves one end fast (300 px/s or more) and every fast end
points along the line between the two ends (within 30 degrees). Then the gap
is filled by a curve that keeps each end's speed, never faster than the
maximum ball speed. A ball that turns or stops in the gap is not filled.
"""

from __future__ import annotations

import football_poc.ball as ball

FPS = 25.0
STEP = 5
SPEED = 600.0  # px/s along x
FRAMES = range(0, 95, STEP)
FAR = (80, 85, 90)  # 2.8 s after frame 10: past the 2.4 s plain limit


def _x(frame: int) -> float:
    return 500.0 + SPEED * frame / FPS


def _modes_after(after: dict[int, tuple[float, float]]) -> dict[int, str]:
    ledger = ball.FrameLedger((frame, frame / FPS) for frame in FRAMES)
    before = {frame: (_x(frame), 500.0) for frame in (0, 5, 10)}
    for frame, (x, y) in {**before, **after}.items():
        ledger.confirm(frame, x=x, y=y, confirming_module=ball.LOCK_YOLO_CHAIN_MODULE,
                       evidence={}, confidence=0.6)
    ball._confirm_time_machine_estimates(
        ledger, fps=FPS, frame_step=STEP, width=3840, height=1600,
        max_speed_pixels_per_second=1600.0,
    )
    return {
        frame: str((entry.evidence or {}).get("mode"))
        for frame, entry in ledger.entries.items()
        if 10 < frame < 80 and entry.status == "confirmed"
    }


def test_fast_straight_gap_follows_speed_curve_20261019T123500000Z() -> None:
    after = {frame: (_x(frame), 500.0) for frame in FAR}

    modes = _modes_after(after)

    assert set(modes) == set(range(15, 80, STEP))
    assert set(modes.values()) == {"speed_curve_interpolation"}


def test_turned_ball_is_not_curve_filled_20261019T123500001Z() -> None:
    # The far end comes back the other way: a 180 degree turn in the gap.
    after = {80: (_x(80), 500.0), 85: (_x(80) - 120, 500.0), 90: (_x(80) - 240, 500.0)}

    assert "speed_curve_interpolation" not in _modes_after(after).values()


def test_slow_ball_is_not_curve_filled_20261019T123500002Z() -> None:
    ledger = ball.FrameLedger((frame, frame / FPS) for frame in FRAMES)
    for frame in (0, 5, 10, *FAR):
        ledger.confirm(frame, x=500.0 + 2.0 * frame, y=500.0,
                       confirming_module=ball.LOCK_YOLO_CHAIN_MODULE,
                       evidence={}, confidence=0.6)
    ball._confirm_time_machine_estimates(
        ledger, fps=FPS, frame_step=STEP, width=3840, height=1600,
        max_speed_pixels_per_second=1600.0,
    )

    assert all(
        (entry.evidence or {}).get("mode") != "speed_curve_interpolation"
        for entry in ledger.entries.values()
    )
