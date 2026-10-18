"""A stronger free ball box beats a weaker trajectory pick at a player's feet."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking


def _candidate(
    frame: int, *, x: float, y: float, confidence: float, near_feet: bool
) -> ball_tracking._BallCandidate:
    return ball_tracking._BallCandidate(
        ball_tracking.BallPoint(frame, frame / 5, confidence, x, y),
        near_player_feet=near_feet,
    )


def _run(frames, candidates, selected) -> ball_tracking.FrameLedger:
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in frames)
    ball_tracking._confirm_yolo_detections(
        ledger,
        selected,
        candidates_by_frame=candidates,
        records_by_frame={
            frame: {"source_frame": frame, "detections": []} for frame in frames
        },
        fps=5,
        frame_step=1,
        max_speed_pixels_per_second=1600,
    )
    return ledger


def test_free_ball_beats_boot_pick_20261018T170512340Z() -> None:
    """A boot picked by the trajectory loses to a stronger box away from feet.

    One boot box reaches 0.35, so the boot boxes form a moving chain."""
    frames = list(range(6))
    boot = {
        frame: _candidate(
            frame,
            x=400.0 + 3 * frame,
            y=300.0,
            confidence=0.35 if frame == 2 else 0.2,
            near_feet=True,
        )
        for frame in frames
    }
    ball = {
        frame: _candidate(
            frame, x=100.0 + 10 * frame, y=100.0, confidence=0.6, near_feet=False
        )
        for frame in frames
    }
    candidates = {frame: [boot[frame], ball[frame]] for frame in frames}

    ledger = _run(frames, candidates, [c.point for c in boot.values()])

    for frame in frames:
        confirmed = ledger.confirmed(frame)
        assert (confirmed.x, confirmed.y) == (100.0 + 10 * frame, 100.0)


def test_dribbled_ball_at_feet_keeps_pick_20261018T170512341Z() -> None:
    """Without a stronger free box, the pick at the feet is still the ball."""
    frames = list(range(6))
    feet = {
        frame: _candidate(
            frame, x=400.0 + 3 * frame, y=300.0, confidence=0.4, near_feet=True
        )
        for frame in frames
    }
    weaker = {
        frame: _candidate(
            frame, x=100.0 + 10 * frame, y=100.0, confidence=0.2, near_feet=False
        )
        for frame in frames
    }
    candidates = {frame: [feet[frame], weaker[frame]] for frame in frames}

    ledger = _run(frames, candidates, [c.point for c in feet.values()])

    for frame in frames:
        confirmed = ledger.confirmed(frame)
        assert (confirmed.x, confirmed.y) == (400.0 + 3 * frame, 300.0)
