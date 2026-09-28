"""Timestamped detected-ball confirmation cascade rule tests."""

from __future__ import annotations

import pytest

import football_poc.ball_tracking as ball_tracking


def _candidate(
    frame: int,
    *,
    x: float,
    y: float,
    confidence: float = 0.8,
    near_feet: bool = False,
) -> ball_tracking._BallCandidate:
    return ball_tracking._BallCandidate(
        ball_tracking.BallPoint(frame, frame / 5, confidence, x, y),
        near_player_feet=near_feet,
    )


def test_yolo_confirmation_locks_supported_detection_20260928T194758281Z() -> None:
    """YOLO detections lock only when confidence and neighbouring motion agree."""
    ledger = ball_tracking.FrameLedger([(0, 0.0), (1, 0.2)])
    first = _candidate(0, x=100, y=100, confidence=0.7)
    second = _candidate(1, x=104, y=102, confidence=0.8)
    candidates = {0: [first], 1: [second]}

    ball_tracking._confirm_yolo_detections(
        ledger,
        [first.point, second.point],
        candidates_by_frame=candidates,
        records_by_frame={
            0: {"source_frame": 0, "detections": []},
            1: {"source_frame": 1, "detections": []},
        },
        fps=5,
        frame_step=1,
        max_speed_pixels_per_second=1600,
    )

    assert ledger.confirmed(0).confirming_module == "01_confirm_yolo"
    assert ledger.confirmed(1).confidence == pytest.approx(0.8)


def test_static_object_rejected_20260928T194758282Z() -> None:
    """Long-span fixed detector clusters are rejected before they can lock."""
    frames = [(frame, frame / 5) for frame in range(8)]
    ledger = ball_tracking.FrameLedger(frames)
    candidates = {
        frame: [_candidate(frame, x=300.0, y=220.0, confidence=0.7)]
        for frame, _seconds in frames
    }

    ball_tracking._confirm_yolo_detections(
        ledger,
        [candidate.point for group in candidates.values() for candidate in group],
        candidates_by_frame=candidates,
        records_by_frame={
            frame: {"source_frame": frame, "detections": []}
            for frame, _seconds in frames
        },
        fps=2,
        frame_step=1,
        max_speed_pixels_per_second=1600,
    )

    assert ledger.confirmed(3) is None
    assert any(
        reason["reason"] == "static_object_without_player_or_motion_support"
        for reason in ledger.entries[3].rejection_reasons
    )


def test_time_machine_interpolates_only_between_confirmed_bounds_20260928T194758283Z() -> None:
    """The time machine interpolates unresolved frames between confirmed bounds."""
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in range(5))
    ledger.confirm(
        0,
        x=10,
        y=20,
        confirming_module="01_confirm_yolo",
        evidence={"kind": "anchor"},
        confidence=0.8,
        box_diagonal=8,
    )
    ledger.confirm(
        4,
        x=30,
        y=40,
        confirming_module="01_confirm_yolo",
        evidence={"kind": "anchor"},
        confidence=0.8,
        box_diagonal=8,
    )

    ball_tracking._confirm_time_machine_estimates(
        ledger,
        fps=5,
        frame_step=1,
        width=100,
        height=100,
        max_speed_pixels_per_second=1600,
    )

    assert ledger.confirmed(2).confirming_module == "02_time_machine"
    assert ledger.confirmed(2).x == pytest.approx(20)
    assert ledger.confirmed(2).y == pytest.approx(30)


def test_time_machine_gives_every_frame_a_possible_region_20260928T221719638Z() -> None:
    """Frames beyond the bounded estimate get a reachable-region estimate."""
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in range(6))
    ledger.confirm(
        3,
        x=50,
        y=60,
        confirming_module="01_confirm_yolo",
        evidence={"kind": "anchor"},
        confidence=0.8,
        box_diagonal=8,
    )

    ball_tracking._confirm_time_machine_estimates(
        ledger,
        fps=5,
        frame_step=1,
        width=100,
        height=100,
        max_speed_pixels_per_second=1600,
        max_one_sided_seconds=0.2,
    )

    bounded = ledger.confirmed(2)
    region = ledger.confirmed(0)
    assert bounded.evidence["mode"] == "bounded_one_sided_hold"
    assert region.evidence["mode"] == "possible_region_one_sided_hold"
    assert region.point_evidence == "trajectory_estimated_possible_region"
    assert (region.x, region.y) == (50, 60)
    assert region.evidence["uncertainty_radius_pixels"] == pytest.approx(
        min(1600 * 0.6, (100**2 + 100**2) ** 0.5 / 2), abs=1e-3
    )
    assert ledger.unresolved_frames() == ()
    assert region.to_point().interpolated is True


def test_visual_recovery_modules_count_as_direct_evidence_20260928T221719639Z() -> None:
    """Visual recovery counts as direct evidence; time-machine frames never do."""
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in range(3))
    for frame, module in ((0, "01_confirm_yolo"), (1, "03_motion_and_optical_flow")):
        ledger.confirm(
            frame,
            x=10 + frame,
            y=20,
            confirming_module=module,
            evidence={"kind": "visual"},
            confidence=0.8,
            box_diagonal=8,
            point_source_attribution=(
                "yolo26_observed" if frame == 0 else "raw_motion_micro_crop_supported"
            ),
        )
    ball_tracking._confirm_time_machine_estimates(
        ledger, fps=5, frame_step=1, width=100, height=100,
        max_speed_pixels_per_second=1600,
    )

    states = ball_tracking._sampled_ball_state_estimates(
        ledger.to_tracks(),
        records=[{"source_frame": frame} for frame in range(3)],
        fps=5, frame_step=1, width=100, height=100,
        max_speed_pixels_per_second=1600, ledger=ledger,
    )

    assert [state["event_evidence_eligible"] for state in states] == [True, True, False]
    assert [state["state"] for state in states] == [
        "observed", "visually_reacquired", "trajectory_estimated_forward",
    ]
    assert states[1]["interpolated"] is False


def test_later_modules_cannot_change_confirmed_frame_20260928T194758285Z() -> None:
    """Ledger locks reject any later attempt to change a confirmed frame."""
    ledger = ball_tracking.FrameLedger([(0, 0.0)])
    ledger.confirm(
        0,
        x=10,
        y=20,
        confirming_module="01_confirm_yolo",
        evidence={"kind": "anchor"},
        confidence=0.8,
    )

    with pytest.raises(ValueError, match="already confirmed"):
        ledger.confirm(
            0,
            x=12,
            y=22,
            confirming_module="02_time_machine",
            evidence={"kind": "attempt"},
            confidence=0.4,
        )


def test_unselected_yolo_candidate_confirms_when_trajectory_is_static_20260928T214010077Z() -> None:
    """Unselected YOLO candidates are checked when the selected track is static."""
    frames = [(frame, frame / 2) for frame in range(10)]
    ledger = ball_tracking.FrameLedger(frames)
    static = {
        frame: _candidate(frame, x=300.0, y=220.0, confidence=0.4)
        for frame, _seconds in frames
    }
    ball = {
        0: _candidate(0, x=50.0, y=50.0, confidence=0.11),
        1: _candidate(1, x=51.0, y=50.0, confidence=0.10),
    }
    distractors = {
        1: _candidate(1, x=900.0, y=600.0, confidence=0.5),
        2: _candidate(2, x=902.0, y=600.0, confidence=0.5),
    }
    candidates = {
        frame: [
            static[frame],
            *([ball[frame]] if frame in ball else []),
            *([distractors[frame]] if frame in distractors else []),
        ]
        for frame, _seconds in frames
    }

    ball_tracking._confirm_yolo_detections(
        ledger,
        [candidate.point for candidate in static.values()],
        candidates_by_frame=candidates,
        records_by_frame={
            frame: {"source_frame": frame, "detections": []}
            for frame, _seconds in frames
        },
        fps=2,
        frame_step=1,
        max_speed_pixels_per_second=1600,
    )

    assert (ledger.confirmed(0).x, ledger.confirmed(0).y) == (50.0, 50.0)
    assert (ledger.confirmed(1).x, ledger.confirmed(1).y) == (51.0, 50.0)
    assert ledger.confirmed(0).evidence["selected_trajectory_candidate"] is False
    assert ledger.confirmed(5) is None
