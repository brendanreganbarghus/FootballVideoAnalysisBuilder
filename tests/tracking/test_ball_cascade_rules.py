"""Timestamped detected-ball confirmation cascade rule tests."""

from __future__ import annotations

import numpy as np
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


def _resting_frames(ball_frames: set[int], frame_count: int):
    import numpy as np

    frames = {}
    for frame in range(frame_count):
        image = np.full((80, 80), 60, dtype=np.uint8)
        if frame in ball_frames:
            yy, xx = np.mgrid[0:80, 0:80]
            image[np.hypot(xx - 40, yy - 40) <= 4] = 200
        frames[frame] = image
    return frames


def _resting_ledger(frame_count: int) -> ball_tracking.FrameLedger:
    ledger = ball_tracking.FrameLedger(
        (frame, frame / 5) for frame in range(frame_count)
    )
    for frame in (0, 1):
        ledger.confirm(
            frame,
            x=40.0,
            y=40.0,
            confirming_module="01_confirm_yolo",
            evidence={},
            confidence=0.12,
            box_diagonal=10.0,
        )
    return ledger


def test_resting_ball_persists_while_disc_matches_20260928T230831649Z(monkeypatch) -> None:
    """A detected resting ball stays at its spot until its disc changes."""
    frames = _resting_frames(set(range(6)), 9)
    monkeypatch.setattr(
        ball_tracking,
        "_read_sampled_grayscale_frames",
        lambda _video, _frames: frames,
    )
    ledger = _resting_ledger(9)

    ball_tracking._extend_resting_ball_confirmations(
        ledger,
        video=ball_tracking.Path("unused.mp4"),
        fps=5,
    )

    for frame in range(2, 6):
        entry = ledger.confirmed(frame)
        assert entry.point_evidence == "resting_ball_persistence"
        assert (entry.x, entry.y) == (40.0, 40.0)
    assert ledger.confirmed(6) is None


def test_resting_ball_replaces_weak_detection_elsewhere_20260928T230831686Z(monkeypatch) -> None:
    """A weak detection elsewhere loses to a ball still visibly at rest."""
    frames = _resting_frames(set(range(6)), 6)
    monkeypatch.setattr(
        ball_tracking,
        "_read_sampled_grayscale_frames",
        lambda _video, _frames: frames,
    )
    ledger = _resting_ledger(6)
    ledger.confirm(
        3,
        x=10.0,
        y=10.0,
        confirming_module="01_confirm_yolo",
        evidence={},
        confidence=0.2,
        box_diagonal=10.0,
    )

    ball_tracking._extend_resting_ball_confirmations(
        ledger,
        video=ball_tracking.Path("unused.mp4"),
        fps=5,
    )

    assert (ledger.confirmed(3).x, ledger.confirmed(3).y) == (40.0, 40.0)
    assert any(
        reason["reason"] == "ball_still_resting_elsewhere"
        for reason in ledger.confirmed(3).rejection_reasons
    )


def test_resting_ball_bridges_short_cover_and_drops_competing_rest_20260928T230831706Z(monkeypatch) -> None:
    """A briefly covered resting ball keeps its spot; a second rest is false."""
    frames = _resting_frames({0, 1, 2, 5, 6}, 7)
    monkeypatch.setattr(
        ball_tracking,
        "_read_sampled_grayscale_frames",
        lambda _video, _frames: frames,
    )
    ledger = _resting_ledger(7)
    for frame in (3, 4):
        ledger.confirm(
            frame,
            x=10.0,
            y=12.0,
            confirming_module="01_confirm_yolo",
            evidence={},
            confidence=0.14,
            box_diagonal=10.0,
        )

    ball_tracking._extend_resting_ball_confirmations(
        ledger,
        video=ball_tracking.Path("unused.mp4"),
        fps=5,
    )

    assert ledger.confirmed(3) is None
    assert ledger.confirmed(4) is None
    assert ledger.confirmed(5).point_evidence == "resting_ball_persistence"
    assert ledger.confirmed(6).point_evidence == "resting_ball_persistence"


def test_detection_bracketed_by_resting_ball_is_withdrawn_20260928T230916266Z() -> None:
    """A detection far away between two resting detections is not the ball."""
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in range(3))
    for frame, x in ((0, 40.0), (1, 400.0), (2, 41.0)):
        ledger.confirm(
            frame,
            x=x,
            y=40.0,
            confirming_module="01_confirm_yolo",
            evidence={},
            confidence=0.2,
            box_diagonal=10.0,
        )

    ball_tracking._reject_confirmations_that_leave_resting_ball(ledger, fps=5)

    assert ledger.confirmed(1) is None
    assert ledger.confirmed(0) is not None and ledger.confirmed(2) is not None


def test_later_module_cannot_move_resting_ball_20260928T230916282Z() -> None:
    """Motion and search modules cannot place the ball away from a rest."""
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in range(3))
    for frame in (0, 2):
        ledger.confirm(
            frame,
            x=40.0,
            y=40.0,
            confirming_module="01_confirm_yolo",
            evidence={},
            confidence=0.2,
            box_diagonal=10.0,
        )
    far = ball_tracking.BallPoint(1, 0.2, 0.5, 120.0, 40.0)
    near = ball_tracking.BallPoint(1, 0.2, 0.5, 42.0, 40.0)

    assert not ball_tracking._proposal_allowed_by_confirmed_neighbours(
        ledger, far, fps=5, max_speed_pixels_per_second=1600
    )
    assert ball_tracking._proposal_allowed_by_confirmed_neighbours(
        ledger, near, fps=5, max_speed_pixels_per_second=1600
    )



class _Box:
    def __init__(self, x1, y1, x2, y2, confidence):
        self.cls = [32]
        self.conf = [confidence]
        self.xyxy = [(x1, y1, x2, y2)]


class _Result:
    names = {32: "sports ball"}

    def __init__(self, boxes):
        self.boxes = boxes


class _BrightBlobDetector:
    """Reports each bright 10 px blob in a crop; brightness sets confidence."""

    def __init__(self):
        self.crops = []

    def predict(self, crops, conf=0.0, **_kwargs):
        results = []
        for crop in crops:
            self.crops.append(crop.shape)
            boxes = []
            for value in sorted(set(int(v) for v in np.unique(crop)) - {0}):
                if value / 250 < conf:
                    continue
                ys, xs = np.nonzero(crop[:, :, 0] == value)
                boxes.append(
                    _Box(xs.min(), ys.min(), xs.max() + 1, ys.max() + 1, value / 250)
                )
            results.append(_Result(boxes))
        return results


def _region_search_ledger():
    ledger = ball_tracking.FrameLedger((frame, frame / 5) for frame in range(3))
    for frame, x in ((0, 400.0), (2, 440.0)):
        ledger.confirm(
            frame,
            x=x,
            y=300.0,
            confirming_module="01_confirm_yolo",
            evidence={},
            confidence=0.5,
            box_diagonal=10.0,
        )
    return ledger


def _image_with_blobs(*blobs):
    image = np.zeros((600, 800, 3), dtype=np.uint8)
    for x, y, value in blobs:
        image[y - 5 : y + 5, x - 5 : x + 5] = value
    return image


def _run_region_search(ledger, image, record=None):
    return ball_tracking._confirm_time_machine_region_search(
        ledger,
        records_by_frame={1: record or {}},
        video=None,
        model_path=None,
        fps=5,
        width=800,
        height=600,
        max_speed_pixels_per_second=1600,
        model=_BrightBlobDetector(),
        color_frames={1: image},
    )


def test_region_search_confirms_ball_found_inside_reachable_region_20260929T003136671Z() -> None:
    """The time-machine region is searched at native size and is direct evidence."""
    ledger = _run_region_search(
        _region_search_ledger(), _image_with_blobs((430, 250, 200))
    )

    entry = ledger.confirmed(1)
    assert entry is not None
    assert entry.confirming_module == "06_time_machine_region_search"
    assert (round(entry.x), round(entry.y)) == (430, 250)
    assert "06_time_machine_region_search" in ball_tracking.DIRECT_EVIDENCE_MODULES


def test_region_search_ignores_weak_detections_20260929T003136672Z() -> None:
    """Weak region detections are usually boots or markings; the frame stays unresolved."""
    ledger = _run_region_search(
        _region_search_ledger(), _image_with_blobs((430, 250, 100))
    )

    assert ledger.confirmed(1) is None

def test_region_search_ignores_detection_beyond_reach_20260929T003136673Z() -> None:
    """A detection outside the reachable region stays unconfirmed."""
    ledger = _run_region_search(
        _region_search_ledger(), _image_with_blobs((700, 520, 200))
    )

    assert ledger.confirmed(1) is None
    reasons = ledger.entries[1].rejection_reasons
    assert reasons[-1]["module"] == "06_time_machine_region_search"


def _run_confirm(frames, candidates, selected, *, fps=5):
    ledger = ball_tracking.FrameLedger([(frame, frame / fps) for frame in frames])
    ball_tracking._confirm_yolo_detections(
        ledger,
        selected,
        candidates_by_frame=candidates,
        records_by_frame={
            frame: {"source_frame": frame, "detections": []} for frame in frames
        },
        fps=fps,
        frame_step=1,
        max_speed_pixels_per_second=1600,
    )
    return ledger


def test_moving_chain_inside_gap_confirms_20260929T090500001Z() -> None:
    """A moving chain of detections in a gap confirms without a near anchor."""
    frames = list(range(12))
    static = {frame: _candidate(frame, x=300.0, y=220.0, confidence=0.4) for frame in frames}
    moving = {
        0: _candidate(0, x=100.0, y=100.0, confidence=0.8),
        1: _candidate(1, x=104.0, y=100.0, confidence=0.8),
        5: _candidate(5, x=600.0, y=100.0, confidence=0.4),
        6: _candidate(6, x=640.0, y=100.0, confidence=0.3),
        7: _candidate(7, x=680.0, y=100.0, confidence=0.3),
    }
    candidates = {
        frame: [static[frame], *([moving[frame]] if frame in moving else [])]
        for frame in frames
    }

    ledger = _run_confirm(frames, candidates, [c.point for c in static.values()])

    assert (ledger.confirmed(1).x, ledger.confirmed(1).y) == (104.0, 100.0)
    assert (ledger.confirmed(5).x, ledger.confirmed(5).y) == (600.0, 100.0)
    assert (ledger.confirmed(7).x, ledger.confirmed(7).y) == (680.0, 100.0)
    assert ledger.confirmed(9) is None


def test_lone_detection_inside_gap_stays_unreachable_20260929T090500002Z() -> None:
    """A single weak detection in a gap is not a moving chain."""
    frames = list(range(12))
    static = {frame: _candidate(frame, x=300.0, y=220.0, confidence=0.4) for frame in frames}
    moving = {
        0: _candidate(0, x=100.0, y=100.0, confidence=0.8),
        1: _candidate(1, x=104.0, y=100.0, confidence=0.8),
        6: _candidate(6, x=640.0, y=100.0, confidence=0.3),
    }
    candidates = {
        frame: [static[frame], *([moving[frame]] if frame in moving else [])]
        for frame in frames
    }

    ledger = _run_confirm(frames, candidates, [c.point for c in static.values()])

    assert ledger.confirmed(6) is None


def test_weak_detour_is_replaced_by_consistent_candidate_20260929T090500003Z() -> None:
    """A weak detection far off the confirmed path is withdrawn and replaced."""
    frames = list(range(5))
    path = {
        frame: _candidate(frame, x=100.0 + 10 * frame, y=100.0, confidence=0.8)
        for frame in (0, 1, 3, 4)
    }
    detour = _candidate(2, x=700.0, y=100.0, confidence=0.15)
    on_path = _candidate(2, x=120.0, y=100.0, confidence=0.3)
    candidates = {frame: [path[frame]] for frame in path}
    candidates[2] = [detour, on_path]
    selected = [path[frame].point for frame in path] + [detour.point]

    ledger = _run_confirm(frames, candidates, selected)

    assert (ledger.confirmed(2).x, ledger.confirmed(2).y) == (120.0, 100.0)
    assert any(
        reason["reason"] == "detour_from_consistent_confirmed_neighbours"
        for reason in ledger.confirmed(2).rejection_reasons
    )

def test_strongest_reachable_alternative_wins_20260929T101500001Z() -> None:
    """Among reachable alternatives the stronger detection confirms first."""
    frames = list(range(12))
    static = {frame: _candidate(frame, x=900.0, y=600.0, confidence=0.4) for frame in frames}
    ball = {frame: _candidate(frame, x=100.0 + 40 * frame, y=100.0, confidence=0.5) for frame in frames}
    weak = {2: _candidate(2, x=150.0, y=110.0, confidence=0.12)}
    candidates = {
        frame: [static[frame], ball[frame], *([weak[frame]] if frame in weak else [])]
        for frame in frames
    }

    ledger = _run_confirm(frames, candidates, [c.point for c in static.values()])

    assert (ledger.confirmed(2).x, ledger.confirmed(2).y) == (180.0, 100.0)


def test_resting_anchor_needs_no_stronger_detection_between_20260929T101500002Z() -> None:
    """Two detections at one spot are not a rest when the ball was seen elsewhere."""
    ledger = ball_tracking.FrameLedger([(frame, frame / 5) for frame in range(4)])
    for frame, x, confidence in ((0, 100.0, 0.3), (1, 400.0, 0.6), (2, 100.0, 0.5)):
        ledger.confirm(
            frame,
            x=x,
            y=100.0,
            confirming_module="01_confirm_yolo",
            evidence={},
            confidence=confidence,
            box_diagonal=10.0,
            point_source_attribution="yolo26_observed",
        )

    assert ball_tracking._resting_ball_anchors(ledger, fps=5) == []