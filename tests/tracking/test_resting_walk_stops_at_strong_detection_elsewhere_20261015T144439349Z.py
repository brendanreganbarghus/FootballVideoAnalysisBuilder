"""Rule: a resting-ball walk ends at a strong detection elsewhere."""

from __future__ import annotations

import numpy as np

import football_poc.ball_tracking as ball_tracking


def _frames(ball_frames: set[int], frame_count: int) -> dict[int, np.ndarray]:
    frames = {}
    yy, xx = np.mgrid[0:80, 0:80]
    for frame in range(frame_count):
        image = np.full((80, 80), 60, dtype=np.uint8)
        if frame in ball_frames:
            image[np.hypot(xx - 40, yy - 40) <= 4] = 200
        frames[frame] = image
    return frames


def _run(monkeypatch, strong_confidence: float) -> ball_tracking.FrameLedger:
    monkeypatch.setattr(
        ball_tracking,
        "_read_sampled_grayscale_frames",
        lambda _video, _sampled: _frames({0, 1, 5}, 6),
    )
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in range(6))
    for frame in (0, 1):
        ledger.confirm(
            frame, x=40.0, y=40.0, confirming_module="01_confirm_yolo",
            evidence={}, confidence=0.12, box_diagonal=10.0,
        )
    for frame, x, confidence in ((3, 20.0, strong_confidence), (4, 12.0, 0.15)):
        ledger.confirm(
            frame, x=x, y=12.0, confirming_module="01_confirm_yolo",
            evidence={}, confidence=confidence, box_diagonal=10.0,
        )
    ball_tracking._extend_resting_ball_confirmations(
        ledger, video=ball_tracking.Path("unused.mp4"), fps=5,
    )
    return ledger


def test_resting_walk_stops_at_strong_detection_elsewhere_20261015T144439349Z(
    monkeypatch,
) -> None:
    """A strong sighting away from the rest spot shows the ball has left it.

    Later weak sightings on the ball's new path are kept even when the old
    rest spot looks like a ball again; with only weak sightings in between,
    the rest spot still wins.
    """
    left = _run(monkeypatch, strong_confidence=0.7)
    assert (left.confirmed(4).x, left.confirmed(4).y) == (12.0, 12.0)
    assert left.confirmed(5) is None

    still_resting = _run(monkeypatch, strong_confidence=0.2)
    assert still_resting.confirmed(4) is None
    assert still_resting.confirmed(5).point_evidence == "resting_ball_persistence"
