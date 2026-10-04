"""Timestamped rule tests for the per-frame ball trust label."""

from __future__ import annotations

import football_poc.ball_tracking as ball_tracking


def _state(frame: int, *, x: float | None, evidence: str, module: str | None) -> dict:
    return {
        "source_frame": frame,
        "x": x,
        "y": None if x is None else 50.0,
        "evidence": evidence,
        "confirming_module": module,
    }


def test_ball_trust_label_seen_estimate_hidden_20261004T124438584Z() -> None:
    """Found frames are seen; short two-sided fills are estimates; others hidden."""
    states = [
        _state(0, x=10, evidence="detector", module="01_confirm_yolo"),
        _state(5, x=15, evidence="trajectory_estimated_bidirectional", module="02_time_machine"),
        _state(10, x=20, evidence="flipbook_detector", module="02_flipbook_time_machine"),
        _state(15, x=25, evidence="trajectory_estimated_bidirectional", module="02_time_machine"),
        _state(20, x=30, evidence="trajectory_estimated_bidirectional", module="02_time_machine"),
        _state(25, x=35, evidence="trajectory_estimated_bidirectional", module="02_time_machine"),
        _state(30, x=40, evidence="trajectory_estimated_bidirectional", module="02_time_machine"),
        _state(35, x=45, evidence="focused_multiscale_detector", module="04_focused_multiscale"),
        _state(40, x=50, evidence="trajectory_estimated_forward", module=None),
        _state(45, x=None, evidence="unresolved", module=None),
    ]

    ball_tracking._label_ball_state_trust(states, frame_step=5)

    assert [state["trust"] for state in states] == [
        "seen",      # detector
        "estimate",  # one step between found frames
        "seen",      # flipbook find counts as found
        "hidden",    # 25-frame gap is longer than four steps
        "hidden",
        "hidden",
        "hidden",
        "seen",
        "hidden",    # filled from one side only
        "hidden",    # no position
    ]
    assert states[1]["x"] == 15
