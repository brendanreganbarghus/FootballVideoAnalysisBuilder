import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import football_poc.ball_tracking as ball_tracking

from football_poc.ball_tracking import (
    BallPoint,
    _BidirectionalTemplateBridge,
    _ForwardTemplatePlan,
    _MotionBridge,
    _PlayerAttentionCone,
    _RawMotionProposal,
    _TemplateBridge,
    _associate_tracks,
    _extract_ball_template,
    _inside_player_upper_body,
    _has_sustained_detector_confirmation,
    _near_player_feet,
    _near_static_cell,
    _player_anchored_cells,
    _player_context_allows_ball,
    _restore_plausible_detector_points,
    _records_in_analysis_window,
    _discard_unanchored_static_fragments,
    _discard_temporal_upper_body_points,
    _deduplicate_track_frames,
    _dense_optical_flow_path,
    _unanchored_static_clusters,
    _near_unanchored_static_cluster,
    _BallCandidate,
    _static_cells,
    _supported_ball_tracks,
    _bidirectional_template_bridge_plans,
    _bidirectional_template_points,
    _template_consensus_point,
    _template_match,
    _motion_circle_bridge_point,
    _add_kalman_guided_reacquisitions,
    _adjacent_appearance_consistency,
    _attention_advantage_is_decisive,
    _attention_convergence,
    _kalman_missing_frame_predictions,
    _raw_motion_frame_proposals,
    _select_raw_motion_proposals,
    _sampled_ball_state_estimates,
    _partial_bidirectional_template_points,
    _forward_template_consensus_points,
    _forward_template_plans,
    _write_summary,
    BallTrack,
    interpolate_track_gaps,
    select_single_ball_trajectory,
)


def point(frame: int, seconds: float, x: float, y: float = 200) -> BallPoint:
    return BallPoint(frame, seconds, 0.8, x, y)


def test_static_cells_require_repeated_frame_occupancy() -> None:
    static = _static_cells(
        [
            point(1, 0.0, 100),
            point(2, 0.1, 102),
            point(3, 0.2, 98),
            point(1, 0.0, 500),
        ],
        frame_count=4,
        cell_size=20,
        occupancy=0.75,
    )

    assert static == {(5, 10)}


def test_focused_multiscale_inference_batches_crop_variants_by_size() -> None:
    class EmptyResult:
        boxes = ()
        names = {}

    class RecordingModel:
        def __init__(self) -> None:
            self.calls: list[tuple[int, int]] = []

        def predict(self, crops, *, imgsz, conf, verbose):
            self.calls.append((imgsz, len(crops)))
            return [EmptyResult() for _ in crops]

    model = RecordingModel()

    candidate = ball_tracking._focused_multiscale_ball_reacquisition(
        model=model,
        frame=np.zeros((400, 400, 3), dtype=np.uint8),
        source_frame=5,
        clip_seconds=0.2,
        expected_x=200,
        expected_y=200,
        reference_diameter=12,
    )

    assert candidate is None
    assert model.calls == [(640, 7)]


def test_raw_motion_does_not_override_frame_with_detector_candidate(
    monkeypatch,
) -> None:
    searched_frames: list[int] = []
    records = [
        {"source_frame": frame, "clip_seconds": frame / 25, "detections": []}
        for frame in (0, 5, 10)
    ]
    track = BallTrack(
        1,
        [
            BallPoint(0, 0.0, 0.8, 100, 200, box_diagonal=12),
            BallPoint(10, 0.4, 0.8, 140, 200, box_diagonal=12),
        ],
    )
    false_detector_candidate = BallPoint(
        5,
        0.2,
        0.8,
        500,
        200,
        box_diagonal=12,
    )

    monkeypatch.setattr(
        ball_tracking,
        "_read_sampled_grayscale_frames",
        lambda _video, frames: {
            frame: np.zeros((20, 20), dtype=np.uint8) for frame in frames
        },
    )

    def record_search(**kwargs):
        searched_frames.append(kwargs["source_frame"])
        return (), Counter()

    monkeypatch.setattr(
        ball_tracking,
        "_raw_motion_frame_proposals",
        record_search,
    )

    ball_tracking._add_raw_motion_proposals(
        (track,),
        records=records,
        video=Path("unused.mp4"),
        width=20,
        height=20,
        fps=25,
        frame_step=5,
        max_speed_pixels_per_second=1600,
        detector_candidates=(false_detector_candidate,),
    )

    assert searched_frames == []


def test_player_supported_stationary_cell_is_not_static_clutter() -> None:
    candidates = [
        _BallCandidate(point(0, 0.0, 100, 200), near_player_feet=True),
        _BallCandidate(point(5, 0.2, 101, 200), near_player_feet=True),
        _BallCandidate(point(10, 0.4, 100, 201), near_player_feet=False),
    ]
    static = _static_cells(
        (candidate.point for candidate in candidates),
        frame_count=3,
        cell_size=20,
        occupancy=0.75,
    )

    static -= _player_anchored_cells(candidates, cell_size=20)

    assert static == frozenset()


def test_limits_cached_records_to_explicit_analysis_window() -> None:
    records = [
        {"source_frame": 0, "clip_seconds": 0.0},
        {"source_frame": 495, "clip_seconds": 19.8},
        {"source_frame": 500, "clip_seconds": 20.0},
    ]

    selected = _records_in_analysis_window(
        records,
        start_seconds=0.0,
        end_seconds=20.0,
    )

    assert [record["source_frame"] for record in selected] == [0, 495]


def test_tracker_connects_motion_across_short_gap() -> None:
    tracks = _associate_tracks(
        [
            point(1, 0.0, 100),
            point(2, 0.08, 120),
            point(5, 0.32, 180),
        ],
        max_gap_seconds=0.4,
        max_speed_pixels_per_second=500,
    )

    assert len(tracks) == 1
    assert [item.x for item in tracks[0].points] == [100, 120, 180]


def test_tracker_rejects_implausible_jump() -> None:
    tracks = _associate_tracks(
        [point(1, 0.0, 100), point(2, 0.08, 500)],
        max_gap_seconds=0.4,
        max_speed_pixels_per_second=500,
    )

    assert len(tracks) == 2


def test_sustained_detector_sequence_anchors_clip_start() -> None:
    points = [
        BallPoint(
            frame,
            frame / 25,
            0.2,
            100,
            200,
            source_attribution="yolo26_observed",
        )
        for frame in (0, 5, 10)
    ]

    assert _has_sustained_detector_confirmation(
        points,
        point_index=0,
        frame_step=5,
    )


def test_static_suppression_covers_neighboring_cell_edge() -> None:
    assert _near_static_cell(
        point(1, 0.0, 109, 200),
        frozenset({(5, 10)}),
        20,
    )


def test_rejects_ball_candidate_inside_player_upper_body() -> None:
    candidate = point(1, 0.0, 120, 130)
    record = {
        "detections": [
            {
                "class_name": "person",
                "confidence": 0.8,
                "x1": 100,
                "y1": 100,
                "x2": 140,
                "y2": 200,
            }
        ]
    }

    assert _inside_player_upper_body(candidate, record)


def test_preserves_ball_candidate_near_player_feet() -> None:
    candidate = point(1, 0.0, 120, 185)
    record = {
        "detections": [
            {
                "class_name": "person",
                "confidence": 0.8,
                "x1": 100,
                "y1": 100,
                "x2": 140,
                "y2": 200,
            }
        ]
    }

    assert not _inside_player_upper_body(candidate, record)


def test_foot_context_overrides_overlapping_upper_body_box() -> None:
    candidate = point(1, 0.0, 120, 185)
    record = {
        "detections": [
            {
                "class_name": "person",
                "confidence": 0.8,
                "x1": 100,
                "y1": 100,
                "x2": 140,
                "y2": 200,
            },
            {
                "class_name": "person",
                "confidence": 0.8,
                "x1": 115,
                "y1": 160,
                "x2": 125,
                "y2": 210,
            },
        ]
    }

    assert _inside_player_upper_body(candidate, record)
    assert _near_player_feet(candidate, record)
    assert _player_context_allows_ball(candidate, record)


def test_same_player_body_and_foot_overlap_rejects_candidate() -> None:
    candidate = point(1, 0.0, 120, 165)
    record = {
        "detections": [
            {
                "class_name": "person",
                "confidence": 0.8,
                "x1": 100,
                "y1": 100,
                "x2": 140,
                "y2": 200,
            }
        ]
    }

    assert _inside_player_upper_body(candidate, record)
    assert _near_player_feet(candidate, record)
    assert not _player_context_allows_ball(candidate, record)


def test_identifies_candidate_near_player_feet() -> None:
    record = {
        "detections": [
            {
                "class_name": "person",
                "confidence": 0.8,
                "x1": 100,
                "y1": 100,
                "x2": 140,
                "y2": 200,
            }
        ]
    }

    assert _near_player_feet(point(1, 0.0, 120, 185), record)
    assert not _near_player_feet(point(1, 0.0, 120, 130), record)


def test_rejects_unanchored_static_candidate_cluster() -> None:
    candidates = [
        _BallCandidate(point(1, 0.0, 100, 200), near_player_feet=False),
        _BallCandidate(point(2, 2.0, 101, 200), near_player_feet=False),
        _BallCandidate(point(3, 4.1, 100, 201), near_player_feet=False),
        _BallCandidate(point(4, 4.2, 100, 200), near_player_feet=True),
    ]

    clusters = _unanchored_static_clusters(
        candidates,
        cell_size=20,
    )

    assert len(clusters) == 1
    assert _near_unanchored_static_cluster(
        point(5, 5.0, 100, 200),
        clusters,
        cell_size=20,
    )


def test_preserves_static_candidate_cluster_near_player_feet() -> None:
    candidates = [
        _BallCandidate(point(1, 0.0, 100, 200), near_player_feet=True),
        _BallCandidate(point(2, 2.0, 101, 200), near_player_feet=True),
        _BallCandidate(point(3, 4.1, 100, 201), near_player_feet=True),
    ]

    clusters = _unanchored_static_clusters(
        candidates,
        cell_size=20,
    )

    assert clusters == ()


def test_preserves_stationary_cluster_with_repeated_foot_support() -> None:
    candidates = [
        _BallCandidate(point(1, 0.0, 100, 200), near_player_feet=False),
        _BallCandidate(point(2, 0.2, 101, 200), near_player_feet=True),
        _BallCandidate(point(3, 0.4, 100, 201), near_player_feet=False),
        _BallCandidate(point(4, 0.6, 101, 201), near_player_feet=True),
    ]

    clusters = _unanchored_static_clusters(
        candidates,
        cell_size=20,
    )

    assert clusters == ()


def test_preserves_continuous_unanchored_slow_ball_path() -> None:
    candidates = [
        _BallCandidate(point(1, 0.0, 100, 200), near_player_feet=False),
        _BallCandidate(point(2, 0.2, 102, 200), near_player_feet=False),
        _BallCandidate(point(3, 0.4, 104, 200), near_player_feet=False),
        _BallCandidate(point(4, 0.6, 106, 200), near_player_feet=False),
    ]

    clusters = _unanchored_static_clusters(
        candidates,
        cell_size=20,
        maximum_continuous_gap_seconds=0.56,
    )

    assert clusters == ()


def test_discards_unanchored_static_fragment_by_ball_scale() -> None:
    static = BallTrack(
        1,
        [
            BallPoint(0, 0.0, 0.8, 100, 200, box_diagonal=10),
            BallPoint(5, 0.2, 0.8, 101, 200, box_diagonal=10),
            BallPoint(10, 0.4, 0.8, 100, 201, box_diagonal=10),
        ],
    )

    retained, discarded = _discard_unanchored_static_fragments(
        [static],
        [],
    )

    assert retained == ()
    assert discarded == 1


def test_preserves_slow_fragment_that_travels_more_than_half_ball_diameter() -> None:
    moving = BallTrack(
        1,
        [
            BallPoint(0, 0.0, 0.8, 100, 200, box_diagonal=10),
            BallPoint(5, 0.2, 0.8, 103, 200, box_diagonal=10),
            BallPoint(10, 0.4, 0.8, 106, 200, box_diagonal=10),
        ],
    )

    retained, discarded = _discard_unanchored_static_fragments(
        [moving],
        [],
    )

    assert retained == (moving,)
    assert discarded == 0


def test_interpolates_short_gaps_with_provenance() -> None:
    track = BallTrack(
        1,
        [
            point(100, 0.0, 100),
            point(106, 0.24, 160),
        ],
    )

    result = interpolate_track_gaps(
        track,
        frame_step=2,
        fps=25,
        maximum_gap_seconds=0.56,
    )

    assert [item.source_frame for item in result.points] == [100, 102, 104, 106]
    assert [item.interpolated for item in result.points] == [
        False,
        True,
        True,
        False,
    ]
    assert result.points[1].evidence == "interpolated"
    assert result.points[1].source_attribution == "interpolated"


def test_sampled_ball_states_separate_observations_from_estimates() -> None:
    tracks = [
        BallTrack(
            1,
            [
                BallPoint(0, 0.0, 0.8, 20, 40, box_diagonal=10),
                BallPoint(
                    10,
                    0.4,
                    0.7,
                    40,
                    50,
                    box_diagonal=12,
                    evidence="full_rate_motion_streak",
                    source_attribution="raw_motion_micro_crop_supported",
                ),
            ],
        )
    ]
    states = _sampled_ball_state_estimates(
        tracks,
        records=[{"source_frame": frame} for frame in (0, 5, 10)],
        fps=25,
        frame_step=5,
        width=100,
        height=100,
        max_speed_pixels_per_second=1600,
    )

    assert [state["state"] for state in states] == [
        "observed",
        "trajectory_estimated_bidirectional",
        "visually_reacquired",
    ]
    assert states[1]["x"] == 30
    assert states[1]["y"] == 45
    assert states[1]["event_evidence_eligible"] is False
    assert states[0]["event_evidence_eligible"] is True
    assert states[2]["event_evidence_eligible"] is True


def test_sampled_ball_states_extrapolate_terminal_motion_as_continuity_only() -> None:
    tracks = [
        BallTrack(
            1,
            [
                BallPoint(0, 0.0, 0.8, 20, 40, box_diagonal=10),
                BallPoint(5, 0.2, 0.8, 30, 45, box_diagonal=10),
            ],
        )
    ]
    states = _sampled_ball_state_estimates(
        tracks,
        records=[{"source_frame": frame} for frame in (0, 5, 10)],
        fps=25,
        frame_step=5,
        width=100,
        height=100,
        max_speed_pixels_per_second=1600,
    )

    assert states[-1]["state"] == "trajectory_estimated_forward"
    assert states[-1]["x"] == 40
    assert states[-1]["y"] == 50
    assert states[-1]["event_evidence_eligible"] is False
    assert states[-1]["uncertainty_radius_pixels"] > 10


def test_deduplicates_frames_in_favor_of_stronger_visual_evidence() -> None:
    stationary = BallPoint(
        5,
        0.2,
        0.7,
        100,
        200,
        evidence="stationary_bidirectional_template",
        temporal_score=0.98,
        source_attribution="temporal_detector_observed",
    )
    raw_motion = BallPoint(
        5,
        0.2,
        0.6,
        103,
        202,
        evidence="raw_motion_trajectory_corridor",
        temporal_score=0.75,
        source_attribution="raw_motion_micro_crop_supported",
    )

    result = _deduplicate_track_frames(
        [BallTrack(1, [stationary, raw_motion])]
    )

    assert result == (BallTrack(1, [raw_motion]),)


def test_template_consensus_recovers_visually_supported_gap() -> None:
    frames = {
        frame: _synthetic_ball_frame(x, 40)
        for frame, x in ((0, 30), (5, 32), (10, 34), (15, 36), (20, 38))
    }
    history = tuple(
        BallPoint(
            frame,
            frame / 25,
            0.8,
            x,
            40,
            box_diagonal=10,
        )
        for frame, x in ((0, 30), (5, 32), (10, 34))
    )
    plan = _TemplateBridge(
        track_index=0,
        first=history[-1],
        second=BallPoint(20, 0.8, 0.8, 38, 40, box_diagonal=10),
        target_frame=15,
        template_points=history,
    )
    templates = [
        (point, _extract_ball_template(frames[point.source_frame], point))
        for point in history
    ]

    recovered = _template_consensus_point(
        plan,
        [
            (point, template)
            for point, template in templates
            if template is not None
        ],
        frames[15],
        fps=25,
    )

    assert recovered is not None
    assert recovered.evidence == "template_consensus"
    assert recovered.temporal_score is not None
    assert recovered.temporal_score >= 0.45
    assert recovered.source_frame == 15
    assert recovered.x == 36
    assert recovered.y == 40


def test_template_consensus_requires_multiple_visual_matches() -> None:
    frames = {
        frame: _synthetic_ball_frame(x, 40)
        for frame, x in ((0, 30), (5, 32), (10, 34), (15, 36), (20, 38))
    }
    history = tuple(
        BallPoint(
            frame,
            frame / 25,
            0.8,
            x,
            40,
            box_diagonal=10,
        )
        for frame, x in ((0, 30), (5, 32), (10, 34))
    )
    plan = _TemplateBridge(
        track_index=0,
        first=history[-1],
        second=BallPoint(20, 0.8, 0.8, 38, 40, box_diagonal=10),
        target_frame=15,
        template_points=history,
    )
    templates = [
        (point, _extract_ball_template(frames[point.source_frame], point))
        for point in history[:2]
    ]

    assert (
        _template_consensus_point(
            plan,
            [
                (point, template)
                for point, template in templates
                if template is not None
            ],
            frames[15],
            fps=25,
        )
        is None
    )


def test_bidirectional_templates_recover_short_visible_gap() -> None:
    frames = {
        frame: _synthetic_ball_frame(x, 40)
        for frame, x in ((0, 30), (5, 32), (10, 34), (15, 36))
    }
    plan = _BidirectionalTemplateBridge(
        track_index=0,
        frame_step=5,
        previous=None,
        first=BallPoint(0, 0.0, 0.8, 30, 40, box_diagonal=10),
        second=BallPoint(15, 0.6, 0.8, 36, 40, box_diagonal=10),
        following=None,
    )

    recovered = _bidirectional_template_points(
        plan,
        frames,
        fps=25,
    )

    assert [point.source_frame for point in recovered] == [5, 10]
    assert [point.evidence for point in recovered] == [
        "bidirectional_template",
        "bidirectional_template",
    ]
    assert [point.x for point in recovered] == [32, 34]
    assert all(point.temporal_score is not None for point in recovered)


def test_bidirectional_templates_reject_missing_visual_evidence() -> None:
    frames = {
        frame: _synthetic_ball_frame(x, 40)
        for frame, x in ((0, 30), (5, 32), (10, 34), (15, 36))
    }
    frames[10] = np.full((80, 80), 80, dtype=np.uint8)
    plan = _BidirectionalTemplateBridge(
        track_index=0,
        frame_step=5,
        previous=None,
        first=BallPoint(0, 0.0, 0.8, 30, 40, box_diagonal=10),
        second=BallPoint(15, 0.6, 0.8, 36, 40, box_diagonal=10),
        following=None,
    )

    assert _bidirectional_template_points(plan, frames, fps=25) == ()


def test_short_stationary_template_recovers_focused_detector_gap(
    monkeypatch,
) -> None:
    frames = {
        frame: _synthetic_ball_frame(40, 40)
        for frame in (0, 5, 10)
    }
    monkeypatch.setattr(
        ball_tracking,
        "_read_sampled_grayscale_frames",
        lambda *_args: frames,
    )
    tracks = ball_tracking._add_short_stationary_template_recoveries(
        (
            BallTrack(
                1,
                [
                    BallPoint(
                        0,
                        0.0,
                        0.8,
                        40,
                        40,
                        box_diagonal=10,
                        evidence="focused_multiscale_detector",
                        source_attribution="yolo26_focused_multiscale",
                    ),
                    BallPoint(
                        10,
                        0.4,
                        0.8,
                        40,
                        40,
                        box_diagonal=10,
                        evidence="focused_multiscale_detector",
                        source_attribution="yolo26_focused_multiscale",
                    ),
                ],
            ),
        ),
        video=Path("unused.mp4"),
        fps=25,
        frame_step=5,
    )

    assert [point.source_frame for point in tracks[0].points] == [0, 5, 10]
    assert tracks[0].points[1].evidence == "stationary_bidirectional_template"
    assert tracks[0].points[1].temporal_score is not None
    assert tracks[0].points[1].temporal_score > 0.99


def test_short_stationary_template_requires_direct_visual_anchors(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        ball_tracking,
        "_read_sampled_grayscale_frames",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("ineligible anchors must not read video")
        ),
    )
    track = BallTrack(
        1,
        [
            BallPoint(
                0,
                0.0,
                0.8,
                40,
                40,
                box_diagonal=10,
                evidence="interpolated",
                source_attribution="interpolated",
            ),
            BallPoint(
                10,
                0.4,
                0.8,
                40,
                40,
                box_diagonal=10,
                evidence="interpolated",
                source_attribution="interpolated",
            ),
        ],
    )

    assert ball_tracking._add_short_stationary_template_recoveries(
        (track,),
        video=Path("unused.mp4"),
        fps=25,
        frame_step=5,
    ) == (track,)


def test_long_stationary_template_bridge_requires_stable_detector_anchors() -> None:
    stable = BallTrack(
        1,
        [
            BallPoint(95, 3.8, 0.8, 100, 200, box_diagonal=10),
            BallPoint(100, 4.0, 0.8, 100, 200, box_diagonal=10),
            BallPoint(105, 4.2, 0.8, 101, 200, box_diagonal=10),
            BallPoint(115, 4.6, 0.8, 100, 201, box_diagonal=10),
            BallPoint(175, 7.0, 0.8, 101, 200, box_diagonal=10),
        ],
    )

    plans = _bidirectional_template_bridge_plans(
        stable,
        track_index=0,
        fps=25,
        frame_step=5,
        maximum_gap_seconds=0.56,
    )

    long_plans = [plan for plan in plans if plan.second.source_frame == 175]
    assert len(long_plans) == 1
    assert long_plans[0].first.source_frame == 115
    assert long_plans[0].bridge_kind == "long_stationary"


def test_long_stationary_template_bridge_rejects_moving_endpoints() -> None:
    moving = BallTrack(
        1,
        [
            BallPoint(95, 3.8, 0.8, 100, 200, box_diagonal=10),
            BallPoint(100, 4.0, 0.8, 100, 200, box_diagonal=10),
            BallPoint(105, 4.2, 0.8, 101, 200, box_diagonal=10),
            BallPoint(115, 4.6, 0.8, 100, 201, box_diagonal=10),
            BallPoint(175, 7.0, 0.8, 140, 220, box_diagonal=10),
        ],
    )

    plans = _bidirectional_template_bridge_plans(
        moving,
        track_index=0,
        fps=25,
        frame_step=5,
        maximum_gap_seconds=0.56,
    )

    assert all(plan.second.source_frame != 175 for plan in plans)


def test_long_stationary_template_bridge_requires_sustained_history() -> None:
    brief_history = BallTrack(
        1,
        [
            BallPoint(100, 4.00, 0.8, 100, 200, box_diagonal=10),
            BallPoint(101, 4.04, 0.8, 100, 200, box_diagonal=10),
            BallPoint(102, 4.08, 0.8, 100, 200, box_diagonal=10),
            BallPoint(103, 4.12, 0.8, 100, 200, box_diagonal=10),
            BallPoint(163, 6.52, 0.8, 100, 200, box_diagonal=10),
        ],
    )

    plans = _bidirectional_template_bridge_plans(
        brief_history,
        track_index=0,
        fps=25,
        frame_step=1,
        maximum_gap_seconds=0.56,
    )

    assert all(plan.second.source_frame != 163 for plan in plans)


def test_long_stationary_template_bridge_keeps_visual_provenance() -> None:
    frames = {
        frame: _synthetic_ball_frame(40, 40)
        for frame in range(0, 61, 5)
    }
    history = [
        BallPoint(frame, frame / 25, 0.8, 40, 40, box_diagonal=10)
        for frame in (0, 5, 10, 15)
    ]
    endpoint = BallPoint(60, 2.4, 0.8, 40, 40, box_diagonal=10)
    plans = _bidirectional_template_bridge_plans(
        BallTrack(1, [*history, endpoint]),
        track_index=0,
        fps=25,
        frame_step=5,
        maximum_gap_seconds=0.56,
    )
    long_plan = next(
        plan for plan in plans if plan.bridge_kind == "long_stationary"
    )

    recovered = _bidirectional_template_points(
        long_plan,
        frames,
        fps=25,
    )

    assert [point.source_frame for point in recovered] == list(range(20, 60, 5))
    assert all(
        point.evidence == "stationary_bidirectional_template"
        for point in recovered
    )
    assert all(
        point.source_attribution == "temporal_detector_observed"
        for point in recovered
    )


def test_partial_bidirectional_templates_keep_supported_frames_only() -> None:
    frames = {
        frame: _synthetic_ball_frame(x, 40)
        for frame, x in ((0, 30), (5, 32), (10, 34), (15, 36))
    }
    plan = _BidirectionalTemplateBridge(
        track_index=0,
        frame_step=5,
        previous=None,
        first=BallPoint(0, 0.0, 0.8, 30, 40, box_diagonal=10),
        second=BallPoint(15, 0.6, 0.8, 36, 40, box_diagonal=10),
        following=None,
    )

    recovered = _partial_bidirectional_template_points(
        plan,
        frames,
        fps=25,
    )

    assert [point.source_frame for point in recovered] == [5, 10, 15]
    assert [point.evidence for point in recovered] == [
        "partial_bidirectional_template",
        "partial_bidirectional_template",
        "template_validated_detector",
    ]


def test_forward_template_consensus_propagates_visual_matches() -> None:
    frames = {
        frame: _synthetic_ball_frame(x, 40)
        for frame, x in (
            (0, 30),
            (5, 32),
            (10, 34),
            (15, 36),
            (20, 38),
            (25, 40),
        )
    }
    history = tuple(
        BallPoint(
            frame,
            frame / 25,
            0.8,
            x,
            40,
            box_diagonal=10,
        )
        for frame, x in ((0, 30), (5, 32), (10, 34))
    )
    plan = _ForwardTemplatePlan(
        track_index=0,
        frame_step=5,
        previous=history[-2],
        seed=history[-1],
        template_points=history,
        target_frames=(15, 20),
    )

    recovered = _forward_template_consensus_points(
        plan,
        frames,
        fps=25,
    )

    assert [point.source_frame for point in recovered] == [15, 20]
    assert all(
        point.evidence == "forward_template_consensus"
        for point in recovered
    )
    assert all(
        point.source_attribution == "temporal_detector_observed"
        for point in recovered
    )


def test_forward_template_propagation_requires_supported_terminal_seed() -> None:
    history = [
        BallPoint(0, 0.0, 0.8, 30, 40, box_diagonal=10),
        BallPoint(5, 0.2, 0.8, 32, 40, box_diagonal=10),
        BallPoint(
            10,
            0.4,
            0.8,
            34,
            40,
            box_diagonal=10,
            evidence="template_validated_detector",
            temporal_score=0.8,
            source_attribution="temporal_detector_observed",
        ),
        BallPoint(30, 1.2, 0.8, 44, 40, box_diagonal=10),
    ]

    plans = _forward_template_plans(
        BallTrack(1, history),
        track_index=0,
        fps=25,
        frame_step=5,
        maximum_gap_seconds=0.56,
    )

    assert len(plans) == 1
    assert plans[0].seed == history[2]
    raw_seed = BallTrack(
        1,
        [history[0], history[1], BallPoint(10, 0.4, 0.8, 34, 40), history[3]],
    )
    assert _forward_template_plans(
        raw_seed,
        track_index=0,
        fps=25,
        frame_step=5,
        maximum_gap_seconds=0.56,
    ) == ()


def test_forward_template_allows_one_step_after_stable_detector_history() -> None:
    history = [
        BallPoint(
            frame,
            7.2 + frame / 25,
            0.8,
            30,
            40,
            box_diagonal=10,
            evidence=(
                "detector"
                if frame in {0, 15, 50}
                else "stationary_bidirectional_template"
            ),
            temporal_score=None if frame in {0, 15, 50} else 0.9,
            source_attribution=(
                "yolo26_observed"
                if frame in {0, 15, 50}
                else "temporal_detector_observed"
            ),
        )
        for frame in (0, 5, 10, 15, 50)
    ]

    plans = _forward_template_plans(
        BallTrack(1, history),
        track_index=0,
        fps=25,
        frame_step=5,
        maximum_gap_seconds=0.56,
    )

    assert len(plans) == 1
    assert plans[0].seed == history[3]
    assert plans[0].target_frames == (20, 25, 30, 35)


def test_full_rate_motion_streak_candidates_accept_motion_blur() -> None:
    previous = np.zeros((80, 120), dtype=np.uint8)
    current = previous.copy()
    following = previous.copy()
    cv2.rectangle(current, (40, 35), (57, 40), 220, -1)

    candidates = ball_tracking._full_rate_motion_streak_candidates(
        previous=previous,
        current=current,
        following=following,
        source_frame=10,
        reference_diameter=10,
    )

    assert len(candidates) == 1
    assert candidates[0].width > candidates[0].height * 2


def test_full_rate_motion_streak_consensus_recovers_only_visual_samples() -> None:
    seed = BallPoint(
        0,
        0.0,
        0.8,
        20,
        100,
        box_diagonal=10,
        evidence="detector",
        source_attribution="yolo26_observed",
    )
    candidates = {
        frame: (
            ball_tracking._MotionStreakCandidate(
                source_frame=frame,
                x=20 + frame * 5,
                y=100 - frame * 2 + frame**2 * 0.03,
                width=12,
                height=6,
                area=40,
                visual_score=0.8,
            ),
        )
        for frame in range(10, 36)
        if frame != 25
    }

    recovered = ball_tracking._full_rate_motion_streak_consensus(
        candidates,
        seed=seed,
        fps=25,
        frame_step=5,
        reference_diameter=10,
        max_speed_pixels_per_second=1600,
    )

    assert [point.source_frame for point in recovered] == [
        10,
        15,
        20,
        30,
        35,
    ]
    assert all(point.evidence == "full_rate_motion_streak" for point in recovered)
    assert all(
        point.source_attribution == "raw_motion_micro_crop_supported"
        for point in recovered
    )


def test_motion_streak_forward_search_prior_uses_recent_velocity() -> None:
    history = [
        BallPoint(frame, frame / 25, 0.8, 100 + frame * 2, 200)
        for frame in (0, 5, 10)
    ]

    x, y, radius = ball_tracking._motion_streak_forward_search_prior(
        history,
        target_frame=15,
        fps=25,
        reference_diameter=10,
        max_speed_pixels_per_second=1600,
    )

    assert x == 130
    assert y == 200
    assert 20 <= radius < 100


def test_full_rate_motion_streak_consensus_rejects_outside_search_prior() -> None:
    seed = BallPoint(0, 0.0, 0.8, 20, 100, box_diagonal=10)
    candidates = {
        frame: (
            ball_tracking._MotionStreakCandidate(
                source_frame=frame,
                x=500 + frame,
                y=100,
                width=12,
                height=6,
                area=40,
                visual_score=0.8,
            ),
        )
        for frame in range(10, 36)
    }

    recovered = ball_tracking._full_rate_motion_streak_consensus(
        candidates,
        seed=seed,
        history=(seed,),
        fps=25,
        frame_step=5,
        reference_diameter=10,
        max_speed_pixels_per_second=1600,
    )

    assert recovered == ()


def test_full_rate_motion_streak_consensus_rejects_ambiguous_coordinates() -> None:
    seed = BallPoint(0, 0.0, 0.8, 20, 100, box_diagonal=10)
    candidates = {
        frame: tuple(
            ball_tracking._MotionStreakCandidate(
                source_frame=frame,
                x=20 + frame * 5,
                y=100 + direction * (45 + frame),
                width=12,
                height=6,
                area=40,
                visual_score=0.8,
            )
            for direction in (-1, 1)
        )
        for frame in range(10, 36)
    }

    recovered = ball_tracking._full_rate_motion_streak_consensus(
        candidates,
        seed=seed,
        fps=25,
        frame_step=5,
        reference_diameter=10,
        max_speed_pixels_per_second=1600,
    )

    assert recovered == ()


def test_full_rate_trajectory_corridor_requires_matching_appearance() -> None:
    history = [
        BallPoint(frame, frame / 25, 0.8, 20 + frame * 5, 60, box_diagonal=10)
        for frame in (-3, -2, -1, 0)
    ]
    color_frames = {
        frame: np.full((120, 160, 3), (40, 120, 40), dtype=np.uint8)
        for frame in range(10)
    }
    color_frames[0][57:64, 17:24] = (0, 140, 255)
    candidates = {}
    for frame in range(1, 10):
        x = 20 + frame * 5
        color_frames[frame][57:64, x - 3 : x + 4] = (0, 140, 255)
        color_frames[frame][87:94, x - 3 : x + 4] = (15, 15, 15)
        candidates[frame] = (
            ball_tracking._MotionStreakCandidate(
                frame,
                x,
                60,
                10,
                6,
                30,
                0.8,
            ),
            ball_tracking._MotionStreakCandidate(
                frame,
                x,
                90,
                10,
                6,
                30,
                0.9,
            ),
        )

    recovered = ball_tracking._full_rate_trajectory_corridor_point(
        candidates,
        color_frames=color_frames,
        history=history,
        target_frame=5,
        fps=25,
        reference_diameter=10,
        max_speed_pixels_per_second=1600,
    )

    assert recovered is not None
    assert recovered.source_frame == 5
    assert recovered.x == 45
    assert recovered.y == 60
    assert recovered.evidence == "full_rate_trajectory_corridor"


def test_full_rate_trajectory_corridor_rejects_occluded_target() -> None:
    history = [
        BallPoint(frame, frame / 25, 0.8, 20 + frame * 5, 60, box_diagonal=10)
        for frame in (-3, -2, -1, 0)
    ]
    color_frames = {
        frame: np.full((120, 160, 3), (40, 120, 40), dtype=np.uint8)
        for frame in range(10)
    }
    color_frames[0][57:64, 17:24] = (0, 140, 255)
    candidates = {}
    for frame in range(1, 10):
        if frame == 5:
            candidates[frame] = ()
            continue
        x = 20 + frame * 5
        color_frames[frame][57:64, x - 3 : x + 4] = (0, 140, 255)
        candidates[frame] = (
            ball_tracking._MotionStreakCandidate(
                frame,
                x,
                60,
                10,
                6,
                30,
                0.8,
            ),
        )

    assert (
        ball_tracking._full_rate_trajectory_corridor_point(
            candidates,
            color_frames=color_frames,
            history=history,
            target_frame=5,
            fps=25,
            reference_diameter=10,
            max_speed_pixels_per_second=1600,
        )
        is None
    )


def test_bounded_color_frame_reader_discards_frames_before_window(
    monkeypatch,
) -> None:
    class FakeCapture:
        def __init__(self, _video: str) -> None:
            self.position = 0

        def isOpened(self) -> bool:
            return True

        def read(self):
            frame = np.full((2, 2, 3), self.position, dtype=np.uint8)
            self.position += 1
            return True, frame

        def set(self, _property: int, value: int) -> bool:
            self.position = int(value)
            return True

        def release(self) -> None:
            pass

    monkeypatch.setattr(ball_tracking.cv2, "VideoCapture", FakeCapture)

    with ball_tracking._BoundedColorFrameReader(Path("unused.mp4")) as reader:
        first = reader.read_range(10, 15)
        second = reader.read_range(14, 19)

        assert tuple(first) == tuple(range(10, 16))
        assert tuple(second) == tuple(range(14, 20))
        assert tuple(reader.frames) == tuple(range(14, 20))


def test_motion_circle_bridge_recovers_unique_moving_ball() -> None:
    frames = {
        frame: _synthetic_ball_frame(x, 40)
        for frame, x in ((0, 30), (5, 34), (10, 38))
    }
    plan = _MotionBridge(
        track_index=0,
        first=BallPoint(0, 0.0, 0.8, 30, 40, box_diagonal=10),
        second=BallPoint(10, 0.4, 0.8, 38, 40, box_diagonal=10),
    )

    recovered = _motion_circle_bridge_point(plan, frames, fps=25)

    assert recovered is not None
    assert recovered.evidence == "motion_circle"
    assert recovered.source_frame == 5
    assert abs(recovered.x - 34) <= 1
    assert abs(recovered.y - 40) <= 1


def test_motion_circle_bridge_rejects_ambiguous_circles(monkeypatch) -> None:
    frames = {
        frame: _synthetic_ball_frame(x, 40)
        for frame, x in ((0, 30), (5, 34), (10, 38))
    }
    monkeypatch.setattr(
        ball_tracking,
        "_nearby_circles",
        lambda *_args, **_kwargs: (
            ball_tracking._CircleCandidate(32, 40, 4),
            ball_tracking._CircleCandidate(36, 40, 4),
        ),
    )
    monkeypatch.setattr(
        ball_tracking,
        "_compact_motion_centers",
        lambda *_args, **_kwargs: ((32, 40), (36, 40)),
    )
    plan = _MotionBridge(
        track_index=0,
        first=BallPoint(0, 0.0, 0.8, 30, 40, box_diagonal=10),
        second=BallPoint(10, 0.4, 0.8, 38, 40, box_diagonal=10),
    )

    assert _motion_circle_bridge_point(plan, frames, fps=25) is None


def test_discards_temporal_point_inside_player_upper_body() -> None:
    detector = BallPoint(0, 0.0, 0.8, 120, 185)
    temporal = BallPoint(
        5,
        0.2,
        0.8,
        120,
        130,
        evidence="motion_circle",
    )
    tracks, discarded = _discard_temporal_upper_body_points(
        [BallTrack(1, [detector, temporal])],
        records_by_frame={
            5: {
                "detections": [
                    {
                        "class_name": "person",
                        "confidence": 0.8,
                        "x1": 100,
                        "y1": 100,
                        "x2": 140,
                        "y2": 200,
                    }
                ]
            }
        },
    )

    assert tracks == (BallTrack(1, [detector]),)
    assert discarded == 1


def test_preserves_multiscale_detector_inside_player_upper_body() -> None:
    detector = BallPoint(
        5,
        0.2,
        0.2,
        120,
        130,
        evidence="focused_multiscale_detector",
        source_attribution="yolo26_focused_multiscale",
    )

    tracks, discarded = _discard_temporal_upper_body_points(
        [BallTrack(1, [detector])],
        records_by_frame={
            5: {
                "detections": [
                    {
                        "class_name": "person",
                        "confidence": 0.8,
                        "x1": 100,
                        "y1": 100,
                        "x2": 140,
                        "y2": 200,
                    }
                ]
            }
        },
    )

    assert tracks == (BallTrack(1, [detector]),)
    assert discarded == 0


def test_preserves_motion_confirmed_ball_inside_player_upper_body() -> None:
    confirmed = BallPoint(
        5,
        0.2,
        0.8,
        120,
        130,
        evidence="full_rate_motion_streak",
        source_attribution="raw_motion_micro_crop_supported",
    )

    tracks, discarded = _discard_temporal_upper_body_points(
        [BallTrack(1, [confirmed])],
        records_by_frame={
            5: {
                "detections": [
                    {
                        "class_name": "person",
                        "confidence": 0.8,
                        "x1": 100,
                        "y1": 100,
                        "x2": 140,
                        "y2": 200,
                    }
                ]
            }
        },
    )

    assert tracks == (BallTrack(1, [confirmed]),)
    assert discarded == 0


def test_deduplication_prefers_validated_ball_over_raw_detector() -> None:
    raw = BallPoint(5, 0.2, 0.99, 500, 200)
    validated = BallPoint(
        5,
        0.2,
        0.4,
        120,
        200,
        evidence="template_validated_detector",
        source_attribution="temporal_detector_observed",
    )

    tracks = _deduplicate_track_frames(
        (BallTrack(1, [raw, validated]),)
    )

    assert tracks == (BallTrack(1, [validated]),)


def test_template_match_rejects_searches_outside_the_frame() -> None:
    match = _template_match(
        np.zeros((8, 8), dtype=np.uint8),
        np.zeros((9, 9), dtype=np.uint8),
        predicted_x=-10,
        predicted_y=-10,
        search_radius=4,
    )

    assert match.score == -1


def test_summary_counts_all_template_evidence_as_supported(
    tmp_path: Path,
) -> None:
    tracks = (
        BallTrack(
            1,
            [
                BallPoint(0, 0.0, 0.8, 10, 10),
                BallPoint(
                    5,
                    0.2,
                    0.7,
                    12,
                    10,
                    evidence="template_consensus",
                    temporal_score=0.8,
                    source_attribution="temporal_detector_observed",
                ),
                BallPoint(
                    10,
                    0.4,
                    0.7,
                    14,
                    10,
                    evidence="bidirectional_template",
                    temporal_score=0.8,
                    source_attribution="temporal_detector_observed",
                ),
            ],
        ),
    )

    _write_summary(
        output=tmp_path,
        records=[{}, {}, {}, {}, {}],
        raw_candidates=[],
        pitch_candidate_count=0,
        filtered_candidates=[],
        candidate_conflict_frames=0,
        conflicting_candidates=0,
        upper_body_rejections=0,
        global_static_rejections=0,
        unanchored_static_rejections=0,
        tracks=tracks,
        unanchored_static_clusters=(),
        associated_track_fragments=1,
        supported_track_fragments=1,
        discarded_static_fragments=0,
        discarded_temporal_upper_body_points=0,
        analysis_start_seconds=None,
        analysis_end_seconds=None,
    )

    summary = json.loads(
        (tmp_path / "ball-tracking-summary.json").read_text(encoding="utf-8")
    )
    assert summary["observed_track_points"] == 1
    assert summary["temporally_supported_track_points"] == 2
    assert summary["tracked_frames"] == 3
    assert summary["tracked_frame_coverage"] == 0.6
    assert summary["point_source_attribution"] == {
        "yolo26_observed": 1,
        "temporal_detector_observed": 2,
        "optical_flow_propagated": 0,
        "raw_motion_micro_crop_supported": 0,
        "kalman_guided_visual_reacquired": 0,
        "interpolated": 0,
    }


def test_raw_motion_proposal_uses_scale_aware_foot_roi() -> None:
    previous = _synthetic_ball_frame(24, 40)
    current = _synthetic_ball_frame(40, 40)
    following = _synthetic_ball_frame(56, 40)
    record = {
        "source_frame": 5,
        "clip_seconds": 0.2,
        "detections": [
            {
                "class_name": "person",
                "confidence": 0.8,
                "x1": 30,
                "y1": 10,
                "x2": 50,
                "y2": 45,
            }
        ],
    }

    proposals, _ = _raw_motion_frame_proposals(
        previous=previous,
        current=current,
        following=following,
        record=record,
        source_frame=5,
        clip_seconds=0.2,
        width=80,
        height=80,
        reference_diameter=10,
        trusted=[],
        frame_step=5,
    )

    assert len(proposals) == 1
    assert proposals[0].mode == "near_feet"
    assert proposals[0].point.evidence == "raw_motion_near_feet"
    assert (
        proposals[0].point.source_attribution
        == "raw_motion_micro_crop_supported"
    )


def test_global_motion_requires_support_on_both_adjacent_frames() -> None:
    proposals = {
        frame: [
            _RawMotionProposal(
                BallPoint(
                    frame,
                    frame / 25,
                    0.8,
                    20 + frame,
                    40,
                    box_diagonal=10,
                    evidence="raw_motion_global_fallback",
                    source_attribution="raw_motion_micro_crop_supported",
                ),
                "global_fallback",
                40,
                verification_score=0.9,
                trajectory_score=0.9,
            )
        ]
        for frame in (0, 5, 10)
    }

    selected, _ = _select_raw_motion_proposals(
        proposals,
        trusted=[],
        frame_step=5,
        fps=25,
        reference_diameter=10,
        max_speed_pixels_per_second=1600,
    )

    assert [proposal.point.source_frame for proposal in selected] == [5]




def test_near_feet_motion_requires_visual_verification() -> None:
    proposals = {
        5: [
            _RawMotionProposal(
                BallPoint(
                    5,
                    0.2,
                    0.8,
                    20,
                    40,
                    box_diagonal=10,
                    evidence="raw_motion_near_feet",
                    source_attribution="raw_motion_micro_crop_supported",
                ),
                "near_feet",
                40,
                verification_score=0.2,
            )
        ],
        10: [
            _RawMotionProposal(
                BallPoint(
                    10,
                    0.4,
                    0.8,
                    25,
                    40,
                    box_diagonal=10,
                    evidence="raw_motion_near_feet",
                    source_attribution="raw_motion_micro_crop_supported",
                ),
                "near_feet",
                40,
                verification_score=0.2,
            )
        ],
    }

    selected, _ = _select_raw_motion_proposals(
        proposals,
        trusted=[BallPoint(0, 0.0, 0.8, 15, 40)],
        frame_step=5,
        fps=25,
        reference_diameter=10,
        max_speed_pixels_per_second=1600,
    )

    assert selected == ()


def test_detector_outlier_requires_combined_visual_support(
    monkeypatch,
) -> None:
    records = [
        {"source_frame": frame, "clip_seconds": frame / 25, "detections": []}
        for frame in (0, 5, 10)
    ]
    frames = {
        frame: np.zeros((40, 40), dtype=np.uint8)
        for frame in (0, 5, 10)
    }
    monkeypatch.setattr(
        ball_tracking,
        "_read_sampled_grayscale_frames",
        lambda *_args, **_kwargs: frames,
    )
    points = [
        BallPoint(
            0,
            0.0,
            0.8,
            0,
            0,
            box_diagonal=5,
            source_attribution="yolo26_observed",
        ),
        BallPoint(
            5,
            0.2,
            0.8,
            100,
            100,
            box_diagonal=5,
            source_attribution="yolo26_observed",
        ),
        BallPoint(
            10,
            0.4,
            0.8,
            20,
            0,
            box_diagonal=5,
            source_attribution="yolo26_observed",
        ),
    ]
    support = 1.79
    monkeypatch.setattr(
        ball_tracking,
        "_detector_point_visual_support",
        lambda point, **_kwargs: support if point.source_frame == 5 else 3.0,
    )

    filtered, rejected = ball_tracking._discard_unsupported_detector_outliers(
        [BallTrack(1, points)],
        records=records,
        video=Path("unused.mp4"),
        fps=25,
        frame_step=5,
        max_gap_seconds=1.0,
        max_speed_pixels_per_second=5000,
    )

    assert [point.source_frame for point in filtered[0].points] == [0, 10]
    assert rejected == frozenset({5})


def test_final_trajectory_integrity_demotes_isolated_contradiction() -> None:
    points = [
        BallPoint(0, 0.0, 0.9, 0, 0),
        BallPoint(5, 0.2, 0.9, 20, 0),
        BallPoint(10, 0.4, 0.2, 500, 200),
        BallPoint(15, 0.6, 0.9, 60, 0),
    ]

    filtered, rejected = ball_tracking._discard_final_trajectory_conflicts(
        (BallTrack(1, points),),
        fps=25,
        max_speed_pixels_per_second=1000,
        max_acceleration_pixels_per_second_squared=10000,
    )

    assert [point.source_frame for point in filtered[0].points] == [0, 5, 15]
    assert rejected == frozenset({10})


def test_final_trajectory_integrity_preserves_coherent_fast_path() -> None:
    points = [
        BallPoint(0, 0.0, 0.8, 0, 0),
        BallPoint(5, 0.2, 0.8, 100, 0),
        BallPoint(10, 0.4, 0.8, 200, 0),
        BallPoint(15, 0.6, 0.8, 300, 0),
    ]

    filtered, rejected = ball_tracking._discard_final_trajectory_conflicts(
        (BallTrack(1, points),),
        fps=25,
        max_speed_pixels_per_second=600,
        max_acceleration_pixels_per_second_squared=10000,
    )

    assert filtered[0].points == points
    assert rejected == frozenset()


def test_final_trajectory_integrity_demotes_recovered_return_excursion() -> None:
    points = [
        BallPoint(0, 0.0, 0.9, 100, 100, box_diagonal=10),
        BallPoint(5, 0.2, 0.9, 101, 100, box_diagonal=10),
        BallPoint(
            25,
            1.0,
            0.8,
            700,
            80,
            box_diagonal=10,
            evidence="raw_motion_attention_convergence_near_feet",
            source_attribution="raw_motion_micro_crop_supported",
        ),
        BallPoint(45, 1.8, 0.9, 102, 100, box_diagonal=10),
        BallPoint(50, 2.0, 0.9, 101, 100, box_diagonal=10),
    ]

    filtered, rejected = ball_tracking._discard_final_trajectory_conflicts(
        (BallTrack(1, points),),
        fps=25,
        max_speed_pixels_per_second=1600,
        max_acceleration_pixels_per_second_squared=12000,
    )

    assert [point.source_frame for point in filtered[0].points] == [
        0,
        5,
        45,
        50,
    ]
    assert rejected == frozenset({25})


def test_sampled_state_uses_bounded_vertical_curve_between_flight_anchors() -> None:
    records = [
        {"source_frame": frame}
        for frame in (0, 5, 10, 15, 20, 25)
    ]
    track = BallTrack(
        1,
        [
            BallPoint(0, 0.0, 0.9, 0, 100, box_diagonal=10),
            BallPoint(20, 0.8, 0.9, 200, 60, box_diagonal=10),
            BallPoint(25, 1.0, 0.9, 250, 55, box_diagonal=10),
        ],
    )

    states = ball_tracking._sampled_ball_state_estimates(
        (track,),
        records=records,
        fps=25,
        frame_step=5,
        width=1000,
        height=500,
        max_speed_pixels_per_second=1600,
    )

    middle = next(state for state in states if state["source_frame"] == 10)
    assert middle["x"] == 100
    assert middle["y"] == 75
    assert middle["state"] == "trajectory_estimated_bidirectional_curved"
    assert middle["event_evidence_eligible"] is False


def test_short_motion_bridge_accepts_coherent_endpoint_bounded_chain(
    monkeypatch,
) -> None:
    records = {
        frame: {"source_frame": frame, "clip_seconds": frame / 25}
        for frame in (0, 5, 10, 15)
    }
    grayscale = {
        frame: np.zeros((40, 40), dtype=np.uint8)
        for frame in records
    }

    def proposals(**kwargs):
        frame = kwargs["source_frame"]
        return (
            (
                _RawMotionProposal(
                    BallPoint(frame, frame / 25, 0.8, frame * 2, 10),
                    "near_feet",
                    10,
                    verification_score=0.5,
                    trajectory_score=0.7,
                ),
            ),
            Counter(),
        )

    monkeypatch.setattr(
        ball_tracking,
        "_raw_motion_frame_proposals",
        proposals,
    )
    tracks = ball_tracking._add_endpoint_bounded_short_motion_bridges(
        (
            BallTrack(
                1,
                [
                    BallPoint(0, 0.0, 0.8, 0, 10, box_diagonal=10),
                    BallPoint(15, 0.6, 0.8, 30, 10, box_diagonal=10),
                ],
            ),
        ),
        records_by_frame=records,
        grayscale=grayscale,
        width=40,
        height=40,
        fps=25,
        frame_step=5,
        max_speed_pixels_per_second=1600,
    )

    assert [point.source_frame for point in tracks[0].points] == [0, 5, 10, 15]


def test_low_confidence_global_fallback_outliers_are_preserved_without_reacquisition(
    monkeypatch,
) -> None:
    points = [
        BallPoint(0, 0.0, 0.8, 0, 0),
        BallPoint(
            5,
            0.2,
            0.6,
            5,
            60,
            evidence="raw_motion_global_fallback",
        ),
        BallPoint(10, 0.4, 0.8, 10, 0),
        BallPoint(
            15,
            0.6,
            0.8,
            15,
            60,
            evidence="raw_motion_global_fallback",
        ),
        BallPoint(20, 0.8, 0.8, 20, 0),
        BallPoint(
            25,
            1.0,
            0.6,
            25,
            40,
            evidence="raw_motion_global_fallback",
        ),
        BallPoint(30, 1.2, 0.8, 30, 0),
    ]

    monkeypatch.setattr(
        ball_tracking,
        "_read_sampled_color_frames",
        lambda *_args, **_kwargs: {},
    )
    tracks = ball_tracking._replace_low_confidence_global_fallback_outliers(
        (BallTrack(1, points),),
        video=Path("unused.mp4"),
    )

    assert [point.source_frame for point in tracks[0].points] == [
        0,
        5,
        10,
        15,
        20,
        25,
        30,
    ]


def test_multiscale_detection_consensus_requires_independent_variants() -> None:
    detections = [
        ball_tracking._FocusedBallDetection(
            30 + offset,
            40,
            confidence,
            variant,
            8,
            7,
        )
        for offset, confidence, variant in [
            (-0.5, 0.1, (80, 640)),
            (0.0, 0.2, (100, 640)),
            (0.5, 0.15, (120, 960)),
        ]
    ]
    detections.extend(
        [
            ball_tracking._FocusedBallDetection(
                70,
                70,
                0.9,
                (80, 640),
                8,
                7,
            ),
            ball_tracking._FocusedBallDetection(
                70,
                70,
                0.8,
                (80, 640),
                8,
                7,
            ),
        ]
    )

    consensus = ball_tracking._multiscale_detection_consensus(
        detections,
        expected_x=35,
        expected_y=40,
        reference_diameter=10,
    )

    assert len(consensus) == 3
    assert {detection.variant for detection in consensus} == {
        (80, 640),
        (100, 640),
        (120, 960),
    }


def test_focused_missing_points_accepts_bracketed_and_supported_pair(
    monkeypatch,
) -> None:
    tracks = (
        BallTrack(
            1,
            [
                BallPoint(0, 0.0, 0.8, 0, 0, box_diagonal=10),
                BallPoint(20, 0.8, 0.8, 100, 0, box_diagonal=10),
            ],
        ),
    )
    records = [
        {"source_frame": frame, "clip_seconds": frame / 25}
        for frame in (0, 5, 10, 15, 20, 25)
    ]
    candidates = {
        5: BallPoint(
            5,
            0.2,
            0.1,
            25,
            0,
            box_diagonal=10,
            evidence="focused_multiscale_detector",
        ),
        10: BallPoint(
            10,
            0.4,
            0.1,
            27,
            0,
            box_diagonal=10,
            evidence="focused_multiscale_detector",
        ),
        15: BallPoint(
            15,
            0.6,
            0.1,
            29,
            0,
            box_diagonal=10,
            evidence="focused_multiscale_detector",
        ),
    }
    monkeypatch.setattr(
        ball_tracking,
        "_read_sampled_color_frames",
        lambda _video, frames: {
            frame: np.zeros((40, 40, 3), dtype=np.uint8)
            for frame in frames
        },
    )
    monkeypatch.setattr(
        ball_tracking,
        "_focused_multiscale_ball_reacquisition",
        lambda **kwargs: candidates.get(kwargs["source_frame"]),
    )

    recovered = ball_tracking._add_focused_multiscale_missing_points(
        tracks,
        records=records,
        video=Path("unused.mp4"),
        model=object(),
        fps=25,
        frame_step=5,
    )

    assert [point.source_frame for point in recovered[0].points] == [
        0,
        5,
        10,
        15,
        20,
    ]


def test_weak_detector_point_is_eligible_for_focused_replacement(
    monkeypatch,
) -> None:
    weak = BallPoint(
        5,
        0.2,
        0.1,
        5,
        20,
        box_diagonal=10,
    )
    replacement = BallPoint(
        5,
        0.2,
        0.08,
        5,
        2,
        box_diagonal=10,
        evidence="focused_multiscale_detector",
    )
    tracks = (
        BallTrack(
            1,
            [
                BallPoint(0, 0.0, 0.8, 0, 0, box_diagonal=10),
                weak,
                BallPoint(10, 0.4, 0.8, 10, 0, box_diagonal=10),
            ],
        ),
    )
    monkeypatch.setattr(
        ball_tracking,
        "_read_sampled_color_frames",
        lambda *_args, **_kwargs: {5: np.zeros((20, 20, 3), dtype=np.uint8)},
    )
    monkeypatch.setattr(
        ball_tracking,
        "_focused_multiscale_ball_reacquisition",
        lambda **_kwargs: replacement,
    )

    recovered = ball_tracking._replace_low_confidence_global_fallback_outliers(
        tracks,
        video=Path("unused.mp4"),
        model=object(),
    )

    assert recovered[0].points[1] == replacement


def test_terminal_focused_points_require_continuous_anchor_chain(
    monkeypatch,
) -> None:
    tracks = (
        BallTrack(
            1,
            [
                BallPoint(0, 0.0, 0.8, 0, 0, box_diagonal=10),
            ],
        ),
    )
    records = [
        {"source_frame": frame, "clip_seconds": frame / 25}
        for frame in (0, 5, 10)
    ]
    candidates = {
        frame: BallPoint(
            frame,
            frame / 25,
            0.1,
            frame,
            0,
            box_diagonal=10,
            evidence="focused_multiscale_detector",
        )
        for frame in range(1, 7)
    }
    candidates[7] = BallPoint(
        7,
        7 / 25,
        0.1,
        100,
        0,
        box_diagonal=10,
        evidence="focused_multiscale_detector",
    )
    monkeypatch.setattr(
        ball_tracking,
        "_read_sampled_color_frames",
        lambda _video, frames: {
            frame: np.zeros((20, 20, 3), dtype=np.uint8)
            for frame in frames
        },
    )
    monkeypatch.setattr(
        ball_tracking,
        "_focused_multiscale_ball_reacquisition",
        lambda **kwargs: candidates.get(kwargs["source_frame"]),
    )

    recovered = ball_tracking._add_focused_multiscale_terminal_points(
        tracks,
        records=records,
        video=Path("unused.mp4"),
        model=object(),
        fps=25,
    )

    assert [point.source_frame for point in recovered[0].points] == [0, 5]


def test_short_motion_bridge_rejects_unanchored_singleton(
    monkeypatch,
) -> None:
    records = {
        frame: {"source_frame": frame, "clip_seconds": frame / 25}
        for frame in (0, 5, 10)
    }
    grayscale = {
        frame: np.zeros((40, 40), dtype=np.uint8)
        for frame in records
    }
    monkeypatch.setattr(
        ball_tracking,
        "_raw_motion_frame_proposals",
        lambda **kwargs: (
            (
                _RawMotionProposal(
                    BallPoint(
                        kwargs["source_frame"],
                        0.2,
                        0.8,
                        10,
                        10,
                    ),
                    "near_feet",
                    10,
                    verification_score=0.9,
                    trajectory_score=0.9,
                ),
            ),
            Counter(),
        ),
    )

    tracks = ball_tracking._add_endpoint_bounded_short_motion_bridges(
        (
            BallTrack(
                1,
                [
                    BallPoint(0, 0.0, 0.8, 0, 10, box_diagonal=10),
                    BallPoint(10, 0.4, 0.8, 20, 10, box_diagonal=10),
                ],
            ),
        ),
        records_by_frame=records,
        grayscale=grayscale,
        width=40,
        height=40,
        fps=25,
        frame_step=5,
        max_speed_pixels_per_second=1600,
    )

    assert [point.source_frame for point in tracks[0].points] == [0, 10]


def test_short_motion_bridge_accepts_unique_strong_corridor_singleton(
    monkeypatch,
) -> None:
    records = {
        frame: {"source_frame": frame, "clip_seconds": frame / 25}
        for frame in (0, 5, 10)
    }
    grayscale = {
        frame: np.zeros((40, 40), dtype=np.uint8)
        for frame in records
    }
    monkeypatch.setattr(
        ball_tracking,
        "_raw_motion_frame_proposals",
        lambda **kwargs: (
            (
                _RawMotionProposal(
                    BallPoint(
                        kwargs["source_frame"],
                        0.2,
                        0.8,
                        10,
                        10,
                    ),
                    "trajectory_corridor",
                    10,
                    verification_score=0.6,
                    trajectory_score=0.7,
                ),
            ),
            Counter(),
        ),
    )

    tracks = ball_tracking._add_endpoint_bounded_short_motion_bridges(
        (
            BallTrack(
                1,
                [
                    BallPoint(0, 0.0, 0.8, 0, 10, box_diagonal=10),
                    BallPoint(10, 0.4, 0.8, 20, 10, box_diagonal=10),
                ],
            ),
        ),
        records_by_frame=records,
        grayscale=grayscale,
        width=40,
        height=40,
        fps=25,
        frame_step=5,
        max_speed_pixels_per_second=1600,
    )

    assert [point.source_frame for point in tracks[0].points] == [0, 5, 10]


def test_short_motion_bridge_refuses_long_gap(monkeypatch) -> None:
    records = {
        frame: {"source_frame": frame, "clip_seconds": frame / 25}
        for frame in range(0, 45, 5)
    }
    grayscale = {
        frame: np.zeros((40, 40), dtype=np.uint8)
        for frame in records
    }
    monkeypatch.setattr(
        ball_tracking,
        "_raw_motion_frame_proposals",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("long gaps must not generate proposals")
        ),
    )

    tracks = ball_tracking._add_endpoint_bounded_short_motion_bridges(
        (
            BallTrack(
                1,
                [
                    BallPoint(0, 0.0, 0.8, 0, 10, box_diagonal=10),
                    BallPoint(40, 1.6, 0.8, 20, 10, box_diagonal=10),
                ],
            ),
        ),
        records_by_frame=records,
        grayscale=grayscale,
        width=40,
        height=40,
        fps=25,
        frame_step=5,
        max_speed_pixels_per_second=1600,
    )

    assert [point.source_frame for point in tracks[0].points] == [0, 40]


def test_complete_short_motion_bridge_accepts_supported_turning_path() -> None:
    first = BallPoint(0, 0.0, 0.8, 0, 0)
    second = BallPoint(20, 0.8, 0.8, 20, 0)
    proposals = {
        5: [
            _RawMotionProposal(
                BallPoint(5, 0.2, 0.8, 15, 10),
                "global_fallback",
                10,
                verification_score=0.8,
                attention_score=0.5,
            )
        ],
        10: [
            _RawMotionProposal(
                BallPoint(10, 0.4, 0.8, 25, 12),
                "global_fallback",
                10,
                verification_score=0.7,
                attention_score=0.5,
            )
        ],
        15: [
            _RawMotionProposal(
                BallPoint(15, 0.6, 0.8, 28, 5),
                "global_fallback",
                10,
                verification_score=0.7,
                attention_score=0.5,
            )
        ],
    }

    selected = ball_tracking._select_complete_short_motion_bridge(
        first,
        second,
        proposals_by_frame=proposals,
        local_diameter=10,
        fps=25,
        frame_step=5,
        max_speed_pixels_per_second=1600,
    )

    assert [proposal.point.source_frame for proposal in selected] == [5, 10, 15]


def test_constant_velocity_kalman_predicts_missing_sample() -> None:
    trusted = [
        BallPoint(0, 0.0, 0.8, 10, 40, box_diagonal=10),
        BallPoint(5, 0.2, 0.8, 20, 40, box_diagonal=10),
        BallPoint(15, 0.6, 0.8, 40, 40, box_diagonal=10),
    ]

    predictions = _kalman_missing_frame_predictions(
        trusted,
        ordered_frames=[0, 5, 10, 15],
        fps=25,
    )

    assert 10 in predictions
    assert abs(predictions[10].x - 30) < 2
    assert predictions[10].covariance[0, 0] > 0


def test_kalman_reacquisition_publishes_only_visual_candidate(
    monkeypatch,
) -> None:
    frames = {
        frame: np.zeros((80, 80), dtype=np.uint8)
        for frame in range(5)
    }
    monkeypatch.setattr(
        ball_tracking,
        "_read_sampled_grayscale_frames",
        lambda *_args, **_kwargs: frames,
    )
    monkeypatch.setattr(
        ball_tracking,
        "_raw_motion_frame_proposals",
        lambda **_kwargs: ((), Counter()),
    )
    trusted = [
        BallPoint(0, 0.0, 0.8, 10, 40, box_diagonal=10),
        BallPoint(1, 0.2, 0.8, 20, 40, box_diagonal=10),
        BallPoint(3, 0.6, 0.8, 40, 40, box_diagonal=10),
        BallPoint(4, 0.8, 0.8, 50, 40, box_diagonal=10),
    ]
    records = [
        {"source_frame": frame, "clip_seconds": frame / 5, "detections": []}
        for frame in range(5)
    ]

    tracks, diagnostics = _add_kalman_guided_reacquisitions(
        [BallTrack(1, trusted)],
        detector_candidates=[
            BallPoint(2, 0.4, 0.7, 30, 40, box_diagonal=10)
        ],
        records=records,
        video=Path("unused.mp4"),
        width=80,
        height=80,
        fps=5,
        frame_step=1,
    )

    recovered = next(
        point for point in tracks[0].points if point.source_frame == 2
    )
    assert recovered.source_attribution == "kalman_guided_visual_reacquired"
    assert recovered.evidence == "kalman_guided_yolo_trajectory_corridor"
    assert diagnostics.successes == 1


def test_dense_optical_flow_tracks_every_raw_frame_between_endpoints() -> None:
    frames = {}
    for frame in range(11):
        image = np.full((80, 80), 80, dtype=np.uint8)
        center = (30 + frame, 40)
        cv2.circle(image, center, 5, 235, -1)
        cv2.line(
            image,
            (center[0] - 3, center[1]),
            (center[0] + 3, center[1]),
            30,
            1,
        )
        cv2.line(
            image,
            (center[0], center[1] - 3),
            (center[0], center[1] + 3),
            30,
            1,
        )
        frames[frame] = image
    seed = BallPoint(0, 0.0, 0.8, 30, 40, box_diagonal=10)

    path, rejection = _dense_optical_flow_path(
        frames,
        seed=seed,
        target_frame=10,
        fps=25,
        width=80,
        height=80,
    )

    assert rejection is None
    assert list(path) == list(range(11))
    assert abs(path[10].x - 40) <= 1
    assert all(sample.confidence >= 0 for sample in path.values())


def test_micro_crop_requires_consistent_adjacent_appearance() -> None:
    frames = [
        _synthetic_ball_frame(x, 40)
        for x in (30, 34, 38)
    ]
    point = BallPoint(5, 0.2, 0.8, 34, 40, box_diagonal=10)

    score = _adjacent_appearance_consistency(
        frames[0],
        frames[1],
        frames[2],
        point,
        reference_diameter=10,
    )

    assert score > 0


def test_attention_convergence_requires_independent_player_cones() -> None:
    point = BallPoint(5, 0.2, 0.8, 100, 100)
    cones = (
        _PlayerAttentionCone(20, 90, 1, 0.1, 0.8, 40),
        _PlayerAttentionCone(180, 90, -1, 0.1, 0.7, 40),
    )

    support, score = _attention_convergence(point, cones)

    assert support == 2
    assert score > 0


def test_attention_advantage_requires_large_support_and_score_margin() -> None:
    assert _attention_advantage_is_decisive(
        alternative_support=11,
        alternative_score=2.396,
        selected_support=4,
        selected_score=1.078,
    )
    assert not _attention_advantage_is_decisive(
        alternative_support=6,
        alternative_score=1.7,
        selected_support=4,
        selected_score=1.1,
    )


def _synthetic_ball_frame(x: int, y: int) -> np.ndarray:
    frame = np.full((80, 80), 80, dtype=np.uint8)
    cv2.circle(frame, (x, y), 4, 235, -1)
    cv2.circle(frame, (x, y), 1, 30, -1)
    return frame


def test_does_not_interpolate_across_direction_reversal() -> None:
    track = BallTrack(
        1,
        [
            point(100, 0.0, 100),
            point(102, 0.08, 140),
            point(106, 0.24, 110),
        ],
    )

    result = interpolate_track_gaps(
        track,
        frame_step=2,
        fps=25,
        maximum_gap_seconds=0.56,
    )

    assert [item.source_frame for item in result.points] == [100, 102, 106]


def test_selects_one_continuous_ball_candidate_per_frame() -> None:
    continuous = BallTrack(
        1,
        [
            BallPoint(0, 0.0, 0.6, 100, 200),
            BallPoint(5, 0.2, 0.6, 120, 200),
            BallPoint(10, 0.4, 0.6, 140, 200),
        ],
    )
    competing = BallTrack(
        2,
        [
            BallPoint(5, 0.2, 0.9, 800, 400),
            BallPoint(10, 0.4, 0.9, 820, 400),
        ],
    )

    selected = select_single_ball_trajectory(
        [continuous, competing],
        max_gap_seconds=0.56,
        max_speed_pixels_per_second=500,
    )

    assert len(selected) == 1
    assert [point.x for point in selected[0].points] == [100, 120, 140]


def test_selector_prefers_reachable_lower_confidence_continuation() -> None:
    first = BallTrack(1, [BallPoint(0, 0.0, 0.8, 100, 200)])
    continuation = BallTrack(2, [BallPoint(5, 0.2, 0.4, 130, 200)])
    distant = BallTrack(
        3,
        [
            BallPoint(5, 0.2, 0.9, 800, 200),
            BallPoint(10, 0.4, 0.9, 820, 200),
            BallPoint(15, 0.6, 0.9, 840, 200),
        ],
    )

    selected = select_single_ball_trajectory(
        [first, continuation, distant],
        max_gap_seconds=0.56,
        max_speed_pixels_per_second=500,
    )

    assert [point.x for point in selected[0].points[:2]] == [100, 130]


def test_selector_rejects_discontinuous_same_track_reversal() -> None:
    discontinuous = BallTrack(
        1,
        [
            BallPoint(0, 0.0, 0.8, 100, 200),
            BallPoint(5, 0.2, 0.8, 300, 200),
            BallPoint(10, 0.4, 0.8, -100, 200),
        ],
    )
    detector_continuation = BallTrack(
        2,
        [BallPoint(10, 0.4, 0.3, 500, 200)],
    )

    selected = select_single_ball_trajectory(
        [discontinuous, detector_continuation],
        max_gap_seconds=0.56,
        max_speed_pixels_per_second=2500,
    )

    assert [point.x for point in selected[0].points] == [100, 300, 500]


def test_restores_unique_detector_candidate_on_plausible_path() -> None:
    selected = (
        BallTrack(
            1,
            [
                BallPoint(0, 0.0, 0.8, 100, 200),
                BallPoint(5, 0.2, 0.8, 120, 200),
                BallPoint(15, 0.6, 0.8, 160, 200),
            ],
        ),
    )
    detector_candidate = BallPoint(
        10,
        0.4,
        0.2,
        140,
        200,
        evidence="detector",
        source_attribution="yolo26_observed",
    )

    restored = _restore_plausible_detector_points(
        selected,
        detector_candidates=[
            _BallCandidate(detector_candidate, near_player_feet=False)
        ],
        frame_step=5,
        fps=25,
        max_speed_pixels_per_second=1600,
    )

    assert [point.x for point in restored[0].points] == [100, 120, 140, 160]
    assert restored[0].points[2].evidence == "trajectory_validated_detector"
    assert (
        restored[0].points[2].source_attribution
        == "temporal_detector_observed"
    )


def test_restores_repeated_isolated_detector_points_in_anchored_cell() -> None:
    selected = (
        BallTrack(
            1,
            [
                BallPoint(0, 0.0, 0.2, 100, 200),
                BallPoint(5, 0.2, 0.2, 100, 200),
                BallPoint(10, 0.4, 0.2, 101, 200),
            ],
        ),
    )
    candidates = [
        _BallCandidate(selected[0].points[0], near_player_feet=True),
        _BallCandidate(selected[0].points[1], near_player_feet=True),
        _BallCandidate(selected[0].points[2], near_player_feet=False),
        _BallCandidate(
            BallPoint(25, 1.0, 0.15, 101, 200),
            near_player_feet=False,
        ),
        _BallCandidate(
            BallPoint(30, 1.2, 0.15, 100, 201),
            near_player_feet=False,
        ),
        _BallCandidate(
            BallPoint(25, 1.0, 0.8, 500, 200),
            near_player_feet=False,
        ),
    ]

    restored = _restore_plausible_detector_points(
        selected,
        detector_candidates=candidates,
        frame_step=5,
        fps=25,
        max_speed_pixels_per_second=1600,
    )

    assert [point.source_frame for point in restored[0].points] == [
        0,
        5,
        10,
        25,
        30,
    ]


def test_restores_supported_foot_point_into_missing_frame() -> None:
    selected = (
        BallTrack(
            1,
            [
                BallPoint(0, 0.0, 0.8, 100, 200),
                BallPoint(5, 0.2, 0.8, 120, 200),
            ],
        ),
    )
    contact = BallPoint(10, 0.4, 0.12, 140, 200)

    restored = _restore_plausible_detector_points(
        selected,
        detector_candidates=[
            _BallCandidate(contact, near_player_feet=True)
        ],
        frame_step=5,
        fps=25,
        max_speed_pixels_per_second=500,
        supported_foot_points=frozenset({contact}),
    )

    assert restored[0].points[-1] == replace(
        contact,
        evidence="trajectory_validated_detector",
        source_attribution="temporal_detector_observed",
    )


def test_leaves_conflicted_frame_when_multiple_candidates_are_plausible() -> None:
    selected = (
        BallTrack(
            1,
            [
                BallPoint(5, 0.2, 0.8, 120, 200),
                BallPoint(15, 0.6, 0.8, 160, 200),
            ],
        ),
    )

    restored = _restore_plausible_detector_points(
        selected,
        detector_candidates=[
            _BallCandidate(
                BallPoint(10, 0.4, 0.4, 138, 200),
                near_player_feet=False,
            ),
            _BallCandidate(
                BallPoint(10, 0.4, 0.5, 142, 200),
                near_player_feet=False,
            ),
        ],
        frame_step=5,
        fps=25,
        max_speed_pixels_per_second=500,
    )

    assert restored == selected


def test_conflicted_frame_stays_unresolved_with_one_plausible_candidate() -> None:
    selected = (
        BallTrack(
            1,
            [
                BallPoint(5, 0.2, 0.8, 120, 200),
                BallPoint(15, 0.6, 0.8, 160, 200),
            ],
        ),
    )
    ball = BallPoint(10, 0.4, 0.4, 140, 200)
    false_positive = BallPoint(10, 0.4, 0.9, 800, 200)

    restored = _restore_plausible_detector_points(
        selected,
        detector_candidates=[
            _BallCandidate(ball, near_player_feet=True),
            _BallCandidate(false_positive, near_player_feet=False),
        ],
        frame_step=5,
        fps=25,
        max_speed_pixels_per_second=500,
    )

    assert all(
        point.source_frame != ball.source_frame
        for track in restored
        for point in track.points
    )


def test_supported_foot_contact_can_be_validated_on_player_overlap() -> None:
    selected = (
        BallTrack(
            1,
            [
                BallPoint(5, 0.2, 0.8, 120, 200),
                BallPoint(15, 0.6, 0.8, 160, 200),
            ],
        ),
    )
    overlapping_candidate = BallPoint(10, 0.4, 0.4, 140, 200)

    restored = _restore_plausible_detector_points(
        selected,
        detector_candidates=[
            _BallCandidate(overlapping_candidate, near_player_feet=True)
        ],
        frame_step=5,
        fps=25,
        max_speed_pixels_per_second=500,
        supported_foot_points=frozenset({overlapping_candidate}),
    )

    assert restored[0].points[1] == replace(
        overlapping_candidate,
        evidence="trajectory_validated_detector",
        source_attribution="temporal_detector_observed",
    )


def test_restored_candidate_does_not_seed_later_restoration() -> None:
    selected = (
        BallTrack(
            1,
            [
                BallPoint(0, 0.0, 0.8, 100, 200),
                BallPoint(5, 0.2, 0.8, 120, 200),
            ],
        ),
    )
    first_missing = BallPoint(10, 0.4, 0.4, 140, 200)
    second_missing = BallPoint(15, 0.6, 0.4, 160, 200)

    restored = _restore_plausible_detector_points(
        selected,
        detector_candidates=[
            _BallCandidate(first_missing, near_player_feet=False),
            _BallCandidate(second_missing, near_player_feet=False),
        ],
        frame_step=5,
        fps=25,
        max_speed_pixels_per_second=500,
    )

    assert [point.source_frame for point in restored[0].points] == [0, 5, 10]


def test_does_not_restore_foot_point_across_expired_gap() -> None:
    selected = (
        BallTrack(
            1,
            [
                BallPoint(0, 0.0, 0.8, 100, 200),
                BallPoint(5, 0.2, 0.8, 120, 200),
            ],
        ),
    )
    distant_contact = BallPoint(20, 0.8, 0.8, 180, 200)

    restored = _restore_plausible_detector_points(
        selected,
        detector_candidates=[
            _BallCandidate(distant_contact, near_player_feet=True)
        ],
        frame_step=5,
        fps=25,
        max_speed_pixels_per_second=500,
        supported_foot_points=frozenset({distant_contact}),
    )

    assert restored == selected


def test_rejects_bracketed_foot_contact_with_conflicting_trajectory() -> None:
    contact = BallPoint(10, 0.4, 0.12, 140, 200)
    selected = (
        BallTrack(
            1,
            [
                BallPoint(5, 0.2, 0.8, 400, 200),
                BallPoint(15, 0.6, 0.8, 500, 200),
            ],
        ),
    )

    restored = _restore_plausible_detector_points(
        selected,
        detector_candidates=[
            _BallCandidate(contact, near_player_feet=True)
        ],
        frame_step=5,
        fps=25,
        max_speed_pixels_per_second=500,
        supported_foot_points=frozenset({contact}),
    )

    assert restored == selected


def test_selector_leaves_missing_frame_instead_of_forcing_distant_candidate() -> None:
    first = BallTrack(1, [BallPoint(0, 0.0, 0.8, 100, 200)])
    distant = BallTrack(2, [BallPoint(5, 0.2, 0.9, 800, 200)])

    selected = select_single_ball_trajectory(
        [first, distant],
        max_gap_seconds=0.56,
        max_speed_pixels_per_second=500,
    )

    assert [point.source_frame for point in selected[0].points] == [0]


def test_selector_rejects_weak_supported_fragment() -> None:
    strong = BallTrack(
        1,
        [
            BallPoint(0, 0.0, 0.4, 100, 200),
            BallPoint(5, 0.2, 0.4, 120, 200),
            BallPoint(10, 0.4, 0.4, 140, 200),
        ],
    )
    weak = BallTrack(
        2,
        [
            BallPoint(25, 1.0, 0.04, 500, 200),
            BallPoint(30, 1.2, 0.04, 520, 200),
            BallPoint(35, 1.4, 0.04, 540, 200),
        ],
    )

    selected = select_single_ball_trajectory(
        [strong, weak],
        max_gap_seconds=0.56,
        max_speed_pixels_per_second=500,
    )

    assert [point.source_frame for point in selected[0].points] == [0, 5, 10]


def test_isolated_candidate_is_removed_before_selection() -> None:
    tracks = _associate_tracks(
        [
            BallPoint(0, 0.0, 0.99, 800, 200),
            BallPoint(0, 0.0, 0.5, 100, 200),
            BallPoint(5, 0.2, 0.5, 120, 200),
            BallPoint(10, 0.4, 0.5, 140, 200),
        ],
        max_gap_seconds=0.56,
        max_speed_pixels_per_second=500,
    )
    accepted = [track for track in tracks if len(track.points) >= 3]

    selected = select_single_ball_trajectory(
        accepted,
        max_gap_seconds=0.56,
        max_speed_pixels_per_second=500,
    )

    assert [point.x for point in selected[0].points] == [100, 120, 140]


def test_promotes_confident_moving_two_point_fragment() -> None:
    moving_pair = BallTrack(
        1,
        [
            BallPoint(0, 0.0, 0.3, 100, 200),
            BallPoint(5, 0.2, 0.3, 160, 200),
        ],
    )

    accepted = _supported_ball_tracks(
        [moving_pair],
        minimum_track_points=3,
        max_speed_pixels_per_second=500,
    )

    assert accepted == (moving_pair,)


def test_promotes_low_confidence_detector_pair_with_foot_support() -> None:
    moving_pair = BallTrack(
        1,
        [
            BallPoint(0, 0.0, 0.12, 100, 200),
            BallPoint(5, 0.2, 0.11, 180, 200),
        ],
    )

    accepted = _supported_ball_tracks(
        [moving_pair],
        minimum_track_points=3,
        max_speed_pixels_per_second=1600,
        foot_supported_points=frozenset({moving_pair.points[-1]}),
    )

    assert accepted == (moving_pair,)


def test_does_not_restart_after_gap_from_two_point_fragment() -> None:
    opening_track = BallTrack(
        1,
        [
            BallPoint(0, 0.0, 0.8, 100, 200),
            BallPoint(5, 0.2, 0.8, 105, 200),
            BallPoint(10, 0.4, 0.8, 110, 200),
        ],
    )
    unsupported_restart = BallTrack(
        2,
        [
            BallPoint(30, 1.2, 0.7, 140, 200),
            BallPoint(35, 1.4, 0.7, 145, 200),
        ],
    )
    sustained_restart = BallTrack(
        3,
        [
            BallPoint(50, 2.0, 0.6, 150, 200),
            BallPoint(55, 2.2, 0.6, 155, 200),
            BallPoint(60, 2.4, 0.6, 160, 200),
        ],
    )

    selected = select_single_ball_trajectory(
        [opening_track, unsupported_restart, sustained_restart],
        max_gap_seconds=0.56,
        max_speed_pixels_per_second=500,
    )

    assert [point.source_frame for point in selected[0].points] == [
        0,
        5,
        10,
        50,
        55,
        60,
    ]


def test_does_not_promote_weak_or_static_two_point_fragment() -> None:
    weak_pair = BallTrack(
        1,
        [
            BallPoint(0, 0.0, 0.1, 100, 200),
            BallPoint(5, 0.2, 0.1, 180, 200),
        ],
    )
    static_pair = BallTrack(
        2,
        [
            BallPoint(0, 0.0, 0.8, 100, 200),
            BallPoint(5, 0.2, 0.8, 102, 200),
        ],
    )

    accepted = _supported_ball_tracks(
        [weak_pair, static_pair],
        minimum_track_points=3,
        max_speed_pixels_per_second=500,
    )

    assert accepted == ()
