import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "evaluate_alfheim_ball_tracks",
    ROOT / "scripts" / "evaluate-alfheim-ball-tracks.py",
)
assert SPEC and SPEC.loader
EVALUATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVALUATION)


def test_coordinate_evaluation_matches_only_nearby_frozen_points() -> None:
    predictions = {
        0: [{"x": 10, "y": 10, "source_attribution": "detector"}],
        5: [
            {"x": 102, "y": 101, "source_attribution": "flow"},
            {"x": 400, "y": 400, "source_attribution": "detector"},
        ],
    }
    reference = {
        frame: (10.0, 10.0) if frame == 0 else (100.0, 100.0)
        for frame in range(10)
    }

    report = EVALUATION.evaluate(
        predictions,
        reference,
        stride=5,
        max_distance=32,
    )

    assert report["evaluated_sampled_frames"] == 2
    assert report["tracked_sampled_frames"] == 2
    assert report["matched_sampled_frames"] == 2
    assert report["false_positive_track_points"] == 1
    assert report["coordinate_match_recall"] == 1.0
    assert report["coordinate_match_precision"] == 0.6667
    assert report["missing_prediction_frames"] == 0
    assert report["wrong_coordinate_frames"] == 0
    assert report["median_matched_distance_px"] == 1.118
    assert report["p90_matched_distance_px"] == 2.012
    assert report["matched_source_attribution"] == {
        "detector": 1,
        "flow": 1,
    }


def test_evaluation_reports_player_foot_association_preservation() -> None:
    record = {
        "detections": [
            {
                "class_name": "person",
                "confidence": 0.8,
                "x1": 80,
                "y1": 50,
                "x2": 120,
                "y2": 150,
            }
        ]
    }

    report = EVALUATION.evaluate(
        {0: [{"x": 103, "y": 140}]},
        {0: (100.0, 145.0)},
        stride=5,
        max_distance=32,
        detections_by_frame={0: record},
    )

    association = report["player_foot_association"]
    assert association["tracked_reference_near_feet"] == 1
    assert association["tracked_prediction_near_feet"] == 1
    assert association["reference_near_feet_preserved"] == 1


def test_evaluation_separates_detector_success_from_selector_failure() -> None:
    reference = {
        0: (100.0, 100.0),
        5: (200.0, 100.0),
        10: (300.0, 100.0),
        15: (400.0, 100.0),
    }
    predictions = {
        0: [{"x": 102, "y": 100, "source_attribution": "yolo26_observed"}],
        5: [
            {
                "x": 600,
                "y": 100,
                "source_attribution": "raw_motion_micro_crop_supported",
            }
        ],
        15: [
            {
                "x": 405,
                "y": 100,
                "source_attribution": "raw_motion_micro_crop_supported",
            }
        ],
    }
    detections = {
        0: {
            "detections": [
                {
                    "class_name": "sports ball",
                    "confidence": 0.8,
                    "x1": 98,
                    "y1": 98,
                    "x2": 102,
                    "y2": 102,
                }
            ]
        },
        5: {
            "detections": [
                {
                    "class_name": "sports ball",
                    "confidence": 0.2,
                    "x1": 197,
                    "y1": 98,
                    "x2": 201,
                    "y2": 102,
                },
                {
                    "class_name": "sports ball",
                    "confidence": 0.9,
                    "x1": 698,
                    "y1": 98,
                    "x2": 702,
                    "y2": 102,
                },
            ]
        },
        10: {"detections": []},
        15: {"detections": []},
    }

    report = EVALUATION.evaluate(
        predictions,
        reference,
        stride=5,
        max_distance=32,
        detections_by_frame=detections,
    )

    assert report["selected_coordinate_error_bands"] == {
        "precise_match": 2,
        "borderline_32_to_50_px": 0,
        "review_50_to_100_px": 0,
        "unreliable_100_to_250_px": 0,
        "wrong_object_over_250_px": 1,
        "not_visible": 1,
    }
    assert report["detector_stage"] == {
        "frames_with_sports_ball_candidates": 2,
        "frames_with_matching_candidate": 2,
        "candidate_recall": 0.5,
        "top_confidence_matches": 1,
        "selector_matches_when_detector_matched": 1,
        "selector_wrong_when_detector_matched": 1,
        "selector_missing_when_detector_matched": 0,
        "recovery_matches_without_detector_match": 1,
    }


def test_coordinate_transform_preserves_aspect_ratio() -> None:
    source_width, source_height = 4450, 2000
    prediction_width, prediction_height = 3840, 1726

    transformed = (
        2225 * prediction_width / source_width,
        1000 * prediction_height / source_height,
    )

    assert transformed == (1920.0, 863.0)


def test_evaluation_rejects_labelled_runtime_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"ball_ground_truth": "labels.csv"}),
        encoding="utf-8",
    )
    prediction = tmp_path / "prediction"
    prediction.mkdir()
    for name, content in (
        ("detections.jsonl", '{"stride": 5}\n'),
        ("ball-tracks.json", '{"tracks": []}\n'),
    ):
        (prediction / name).write_text(content, encoding="utf-8")
    freeze = {
        "predictions_frozen": True,
        "manifest_sha256": EVALUATION.sha256(manifest),
        "artifacts": {
            name: EVALUATION.sha256(prediction / name)
            for name in ("detections.jsonl", "ball-tracks.json")
        },
    }
    (prediction / "prediction-freeze.json").write_text(
        json.dumps(freeze),
        encoding="utf-8",
    )

    try:
        EVALUATION.load_frozen_predictions(prediction, manifest)
    except ValueError as error:
        assert "evaluation data" in str(error)
    else:
        raise AssertionError("Labelled runtime manifest should be rejected")
