import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "analyze_soccertrack_ball_coordinates",
    ROOT / "scripts" / "analyze-soccertrack-ball-coordinates.py",
)
assert SPEC and SPEC.loader
ANALYZE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYZE)


def test_reports_cache_rebuild_metrics_without_claiming_cold_timing(
    tmp_path: Path,
) -> None:
    summary = {
        "analysis_window": {"start_seconds": 0.0, "end_seconds": 20.0},
        "processed_frames": 100,
        "observed_track_points": 42,
        "temporally_supported_track_points": 20,
        "raw_motion_proposals": {
            "accepted": {
                "near_feet": 10,
                "trajectory_corridor": 2,
                "global_fallback": 1,
            },
            "generated_by_mode": {
                "near_feet": 20,
                "trajectory_corridor": 4,
                "global_fallback": 8,
            },
            "precision_rejections": {
                "verification_score": 3,
                "path_plausibility": 1,
                "alternative_margin": 2,
            },
            "trajectory_margin": {"minimum": 0.2, "mean": 0.4},
        },
        "candidate_conflicts": {
            "frames_with_multiple_candidates": 1,
            "competing_candidates": 2,
        },
        "player_attention_search_prior": {
            "accepted_coordinates": 2,
            "startup_points_rejected": 1,
        },
        "kalman_guided_reacquisition": {
            "accepted": 2,
            "expired_predictions": 4,
            "conflicts": 1,
        },
        "dense_optical_flow": {
            "accepted_points": 3,
            "successful_bridges": 1,
            "expired_bridges": 2,
        },
        "tracked_frames": 62,
        "tracked_frame_coverage": 0.62,
        "interpolated_track_points": 0,
    }
    (tmp_path / "ball-tracking-summary.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )

    result = ANALYZE._result("development-0-20", tmp_path, wall_seconds=4.2)

    assert result["cache_rebuild_wall_seconds"] == 4.2
    assert result["unsupported_interpolation_points"] == 0
    assert result["raw_motion_contributions"]["near_feet"] == 10
    assert result["kalman_guided_reacquisition"]["accepted"] == 2
    assert result["dense_optical_flow"]["accepted_points"] == 3
