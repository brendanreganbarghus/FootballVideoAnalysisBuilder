import json
from collections import Counter
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


def test_forward_template_propagation_requires_verified_terminal_seed() -> None:
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
    assert restored[0].points[2].source_attribution == "yolo26_observed"


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

    assert restored[0].points[-1] == contact


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


def test_restores_bracketed_foot_contact_despite_conflicting_neighbors() -> None:
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

    assert restored[0].points[1] == contact


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
