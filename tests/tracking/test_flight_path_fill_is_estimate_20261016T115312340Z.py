"""Rule: a frame filled on a fitted flight path is an estimate, not a sighting.

A flight module sees the ball in some frames of its trail and fills the
frames between them with points on the fitted path. The ball was not seen
in those frames, so they reach the rules engine as trajectory estimates
with trust "estimate" or "hidden", while trail frames stay "seen".
"""

from __future__ import annotations

from football_poc import ball_tracking


def test_flight_path_fill_is_estimate_20261016T115312340Z():
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in range(3))
    for frame, kind in ((0, "aerial_motion_blob"), (1, "aerial_flight_path"), (2, "aerial_motion_blob")):
        ledger.confirm(
            frame, x=100.0 + 10 * frame, y=200.0,
            confirming_module="07_aerial_one_sided_flight",
            evidence={"kind": kind}, confidence=0.9,
            point_evidence=kind, point_source_attribution="motion_flight_path",
        )
    seen, filled, seen_again = ball_tracking._sampled_ball_state_estimates(
        ledger.to_tracks(),
        records=[{"source_frame": frame} for frame in range(3)],
        fps=5.0, frame_step=1, width=3840, height=1726,
        max_speed_pixels_per_second=3000.0, ledger=ledger,
    )

    assert seen["state"] == seen_again["state"] == "visually_reacquired"
    assert seen["trust"] == "seen"
    assert filled["state"] == "trajectory_estimated_flight_path"
    assert filled["trust"] == "estimate"
    assert filled["x"] == 110.0
    assert filled["event_evidence_eligible"] is False
