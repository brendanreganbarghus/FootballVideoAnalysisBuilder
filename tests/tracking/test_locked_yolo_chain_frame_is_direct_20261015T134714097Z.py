"""Rule: a frame locked by a moving YOLO chain is direct detector evidence.

The chain lock keeps the detector's own box in every frame it covers, so its
coordinate comes straight from that frame's image. Time-machine estimates
between sightings stay indirect.
"""

from __future__ import annotations

from football_poc import ball_tracking


def _states(module: str) -> list[dict]:
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in range(2))
    ledger.confirm(
        0, x=100.0, y=200.0, confirming_module=module,
        evidence={}, confidence=0.4, box_diagonal=12.0,
    )
    ledger.confirm(
        1, x=110.0, y=200.0, confirming_module="02_time_machine",
        evidence={}, confidence=0.0, point_evidence="trajectory_estimated_bidirectional",
        point_source_attribution="interpolated",
    )
    return ball_tracking._sampled_ball_state_estimates(
        ledger.to_tracks(),
        records=[{"source_frame": 0}, {"source_frame": 1}],
        fps=5.0,
        frame_step=1,
        width=3840,
        height=1726,
        max_speed_pixels_per_second=3000.0,
        ledger=ledger,
    )


def test_locked_yolo_chain_frame_is_direct_20261015T134714097Z():
    locked, estimated = _states(ball_tracking.LOCK_YOLO_CHAIN_MODULE)

    assert locked["event_evidence_eligible"] is True
    assert estimated["event_evidence_eligible"] is False
