from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2

from football_poc.alfheim_segments import resolve_alfheim_pano


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def video_dimensions(path: Path) -> tuple[int, int]:
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open video for dimensions: {path}")
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        capture.release()
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid video dimensions: {path}")
    return width, height


def load_frozen_predictions(
    prediction_root: Path,
    manifest_path: Path,
) -> tuple[dict[str, Any], dict[int, list[dict[str, Any]]], int]:
    freeze_path = prediction_root / "prediction-freeze.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("predictions_frozen") is not True:
        raise ValueError("Ball-track predictions are not frozen")
    if freeze.get("manifest_sha256") != sha256(manifest_path):
        raise ValueError("The runtime manifest changed after prediction freeze")
    for name in ("detections.jsonl", "ball-tracks.json"):
        expected = freeze.get("artifacts", {}).get(name)
        if not expected or expected != sha256(prediction_root / name):
            raise ValueError(f"Frozen prediction hash mismatch: {name}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    forbidden = {"ball_ground_truth", "annotations", "events", "labels"}
    leaked = sorted(forbidden.intersection(manifest))
    if leaked or manifest.get("actions") or manifest.get("action_counts"):
        raise ValueError(
            "Runtime manifest contains evaluation data: "
            + ", ".join(leaked or ["actions/action_counts"])
        )

    tracks = json.loads(
        (prediction_root / "ball-tracks.json").read_text(encoding="utf-8")
    )
    points: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for track in tracks.get("tracks", []):
        for point in track.get("points", []):
            value = dict(point)
            value["track_id"] = int(track["track_id"])
            points[int(point["source_frame"])].append(value)

    metadata_line = (
        prediction_root / "detections.jsonl"
    ).read_text(encoding="utf-8").splitlines()[0]
    stride = int(json.loads(metadata_line)["stride"])
    return manifest, points, stride


def load_provider_coordinates(
    pano: Path,
    *,
    source_start_seconds: float,
    duration_seconds: float,
    fps: int = 25,
    source_segment_seconds: int = 3,
) -> dict[int, tuple[float, float]]:
    frames_per_source_segment = fps * source_segment_seconds
    source_files = {
        int(path.name.split("_", 1)[0]): path
        for path in pano.glob("*.h264")
    }
    first_absolute_frame = round(source_start_seconds * fps)
    frame_count = round(duration_seconds * fps)
    coordinates: dict[int, tuple[float, float]] = {}
    rows_by_segment: dict[int, list[str]] = {}
    for clip_frame in range(frame_count):
        absolute_frame = first_absolute_frame + clip_frame
        source_segment = absolute_frame // frames_per_source_segment
        source_frame = absolute_frame % frames_per_source_segment
        if source_segment not in rows_by_segment:
            video = source_files.get(source_segment)
            if video is None:
                raise FileNotFoundError(
                    f"Alfheim source segment is missing: {source_segment}"
                )
            track = pano / "track" / f"{video.name}_track.txt"
            rows_by_segment[source_segment] = track.read_text(
                encoding="utf-8"
            ).splitlines()
        rows = rows_by_segment[source_segment]
        if source_frame >= len(rows):
            raise ValueError(
                f"Provider coordinate is missing for source frame {absolute_frame}"
            )
        _, x, y, *_ = rows[source_frame].split()
        coordinates[clip_frame] = (float(x), float(y))
    return coordinates


def evaluate(
    predictions: dict[int, list[dict[str, Any]]],
    reference: dict[int, tuple[float, float]],
    *,
    stride: int,
    max_distance: float,
    detections_by_frame: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    evaluated = matched = false_positives = 0
    distances: list[float] = []
    nearest_candidate_distances: list[float] = []
    tracked_frames = 0
    wrong_frames = 0
    missing_frames = 0
    source_attribution: Counter[str] = Counter()
    matched_source_attribution: Counter[str] = Counter()
    wrong_source_attribution: Counter[str] = Counter()
    reference_near_feet = 0
    prediction_near_feet = 0
    preserved_near_feet = 0
    detector_frames_with_candidates = 0
    detector_frames_with_matching_candidate = 0
    detector_top_confidence_matches = 0
    selector_matches_when_detector_matched = 0
    selector_misses_when_detector_matched = 0
    selector_missing_when_detector_matched = 0
    recovery_matches_without_detector_match = 0
    error_bands = Counter[str]()
    for frame in range(0, max(reference) + 1, stride):
        if frame not in reference:
            continue
        evaluated += 1
        candidates = predictions.get(frame, [])
        if candidates:
            tracked_frames += 1
            source_attribution.update(
                str(point.get("source_attribution", "unknown"))
                for point in candidates
            )
        else:
            missing_frames += 1
        truth_x, truth_y = reference[frame]
        candidate_distances = [
            math.hypot(
                float(point["x"]) - truth_x,
                float(point["y"]) - truth_y,
            )
            for point in candidates
        ]
        nearest_index = (
            min(
                range(len(candidate_distances)),
                key=candidate_distances.__getitem__,
            )
            if candidate_distances
            else None
        )
        if nearest_index is not None:
            nearest_distance = candidate_distances[nearest_index]
            nearest_candidate_distances.append(nearest_distance)
            error_bands[_coordinate_error_band(nearest_distance, max_distance)] += 1
            nearest = candidates[nearest_index]
            source = str(nearest.get("source_attribution", "unknown"))
            if nearest_distance <= max_distance:
                matched_source_attribution[source] += 1
            else:
                wrong_source_attribution[source] += 1
                wrong_frames += 1
            if detections_by_frame is not None:
                record = detections_by_frame.get(frame, {})
                truth_at_feet = _near_player_feet(
                    truth_x,
                    truth_y,
                    record,
                )
                prediction_at_feet = _near_player_feet(
                    float(nearest["x"]),
                    float(nearest["y"]),
                    record,
                )
                reference_near_feet += int(truth_at_feet)
                prediction_near_feet += int(prediction_at_feet)
                preserved_near_feet += int(
                    truth_at_feet and prediction_at_feet
                )
        else:
            error_bands["not_visible"] += 1
        selected_matches = bool(
            candidate_distances and min(candidate_distances) <= max_distance
        )
        if selected_matches:
            matched += 1
            distances.append(min(candidate_distances))
            false_positives += max(0, len(candidates) - 1)
        else:
            false_positives += len(candidates)

        detector_matches = False
        if detections_by_frame is not None:
            detector_candidates = [
                detection
                for detection in detections_by_frame.get(
                    frame, {}
                ).get("detections", [])
                if detection.get("class_name") == "sports ball"
            ]
            if detector_candidates:
                detector_frames_with_candidates += 1
                detector_distances = [
                    math.hypot(
                        (
                            float(detection["x1"])
                            + float(detection["x2"])
                        )
                        / 2
                        - truth_x,
                        (
                            float(detection["y1"])
                            + float(detection["y2"])
                        )
                        / 2
                        - truth_y,
                    )
                    for detection in detector_candidates
                ]
                detector_matches = min(detector_distances) <= max_distance
                if detector_matches:
                    detector_frames_with_matching_candidate += 1
                top_confidence_index = max(
                    range(len(detector_candidates)),
                    key=lambda index: float(
                        detector_candidates[index].get("confidence", 0)
                    ),
                )
                detector_top_confidence_matches += int(
                    detector_distances[top_confidence_index] <= max_distance
                )
        if detector_matches:
            if selected_matches:
                selector_matches_when_detector_matched += 1
            elif candidates:
                selector_misses_when_detector_matched += 1
            else:
                selector_missing_when_detector_matched += 1
        elif selected_matches:
            recovery_matches_without_detector_match += 1
    precision_denominator = matched + false_positives
    return {
        "evaluated_sampled_frames": evaluated,
        "tracked_sampled_frames": tracked_frames,
        "matched_sampled_frames": matched,
        "missed_sampled_frames": evaluated - matched,
        "missing_prediction_frames": missing_frames,
        "wrong_coordinate_frames": wrong_frames,
        "false_positive_track_points": false_positives,
        "tracked_frame_coverage": (
            round(tracked_frames / evaluated, 4) if evaluated else 0.0
        ),
        "coordinate_match_recall": (
            round(matched / evaluated, 4) if evaluated else 0.0
        ),
        "coordinate_match_precision": (
            round(matched / precision_denominator, 4)
            if precision_denominator
            else 0.0
        ),
        "mean_matched_distance_px": (
            round(sum(distances) / len(distances), 3)
            if distances
            else 0.0
        ),
        "median_matched_distance_px": _percentile(distances, 0.5),
        "p90_matched_distance_px": _percentile(distances, 0.9),
        "median_nearest_candidate_distance_px": _percentile(
            nearest_candidate_distances,
            0.5,
        ),
        "p90_nearest_candidate_distance_px": _percentile(
            nearest_candidate_distances,
            0.9,
        ),
        "selected_coordinate_error_bands": {
            "precise_match": error_bands["precise_match"],
            "borderline_32_to_50_px": error_bands[
                "borderline_32_to_50_px"
            ],
            "review_50_to_100_px": error_bands["review_50_to_100_px"],
            "unreliable_100_to_250_px": error_bands[
                "unreliable_100_to_250_px"
            ],
            "wrong_object_over_250_px": error_bands[
                "wrong_object_over_250_px"
            ],
            "not_visible": error_bands["not_visible"],
        },
        "detector_stage": {
            "frames_with_sports_ball_candidates": (
                detector_frames_with_candidates
            ),
            "frames_with_matching_candidate": (
                detector_frames_with_matching_candidate
            ),
            "candidate_recall": (
                round(detector_frames_with_matching_candidate / evaluated, 4)
                if evaluated
                else 0.0
            ),
            "top_confidence_matches": detector_top_confidence_matches,
            "selector_matches_when_detector_matched": (
                selector_matches_when_detector_matched
            ),
            "selector_wrong_when_detector_matched": (
                selector_misses_when_detector_matched
            ),
            "selector_missing_when_detector_matched": (
                selector_missing_when_detector_matched
            ),
            "recovery_matches_without_detector_match": (
                recovery_matches_without_detector_match
            ),
        },
        "source_attribution": dict(sorted(source_attribution.items())),
        "matched_source_attribution": dict(
            sorted(matched_source_attribution.items())
        ),
        "wrong_source_attribution": dict(
            sorted(wrong_source_attribution.items())
        ),
        "player_foot_association": {
            "tracked_reference_near_feet": reference_near_feet,
            "tracked_prediction_near_feet": prediction_near_feet,
            "reference_near_feet_preserved": preserved_near_feet,
            "reference_near_feet_preservation_rate": (
                round(preserved_near_feet / reference_near_feet, 4)
                if reference_near_feet
                else None
            ),
            "interpretation": (
                "Evaluation-only comparison of the nearest frozen prediction "
                "and provider coordinate against frozen player foot ROIs."
            ),
        },
        "maximum_match_distance_px": max_distance,
    }


def _coordinate_error_band(distance: float, max_distance: float) -> str:
    if distance <= max_distance:
        return "precise_match"
    if distance <= 50:
        return "borderline_32_to_50_px"
    if distance <= 100:
        return "review_50_to_100_px"
    if distance <= 250:
        return "unreliable_100_to_250_px"
    return "wrong_object_over_250_px"


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    weight = position - lower
    return round(
        ordered[lower] * (1 - weight) + ordered[upper] * weight,
        3,
    )


def _near_player_feet(
    x: float,
    y: float,
    record: dict[str, Any],
    *,
    minimum_person_confidence: float = 0.25,
) -> bool:
    for detection in record.get("detections", []):
        if (
            detection.get("class_name") != "person"
            or float(detection["confidence"]) < minimum_person_confidence
        ):
            continue
        x1 = float(detection["x1"])
        y1 = float(detection["y1"])
        x2 = float(detection["x2"])
        y2 = float(detection["y2"])
        width = x2 - x1
        height = y2 - y1
        if (
            x1 - width * 0.5 <= x <= x2 + width * 0.5
            and y1 + height * 0.55 <= y <= y2 + height * 0.35
        ):
            return True
    return False


def load_frozen_detection_records(
    prediction_root: Path,
) -> dict[int, dict[str, Any]]:
    records: dict[int, dict[str, Any]] = {}
    for line in (
        prediction_root / "detections.jsonl"
    ).read_text(encoding="utf-8").splitlines()[1:]:
        record = json.loads(line)
        if record.get("type") == "frame":
            records[int(record["source_frame"])] = record
    return records


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate frozen raw-video Alfheim ball tracks against provider "
            "coordinates without exposing labels to prediction."
        )
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("prediction_root", type=Path)
    parser.add_argument(
        "--pano",
        type=Path,
        default=resolve_alfheim_pano(Path.cwd()),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-distance", type=float, default=32.0)
    args = parser.parse_args()
    prediction_root = args.prediction_root.resolve()
    output = args.output.resolve()
    if output.is_relative_to(prediction_root):
        raise ValueError("Evaluation output must be outside prediction storage")
    manifest, predictions, stride = load_frozen_predictions(
        prediction_root,
        args.manifest.resolve(),
    )
    reference = load_provider_coordinates(
        args.pano.resolve(),
        source_start_seconds=float(manifest["source_start_seconds"]),
        duration_seconds=float(manifest["duration_seconds"]),
    )
    source_video = sorted(args.pano.resolve().glob("*.h264"))[
        int(float(manifest["source_start_seconds"]) // 3)
    ]
    source_width, source_height = video_dimensions(source_video)
    prediction_width, prediction_height = video_dimensions(
        Path(str(manifest["video"]))
    )
    scale_x = prediction_width / source_width
    scale_y = prediction_height / source_height
    transformed_reference = {
        frame: (x * scale_x, y * scale_y)
        for frame, (x, y) in reference.items()
    }
    report = {
        "schema_version": 1,
        "prediction_frozen_before_evaluation": True,
        "runtime_manifest_sha256": sha256(args.manifest.resolve()),
        "prediction_freeze_sha256": sha256(
            prediction_root / "prediction-freeze.json"
        ),
        "reference_kind": "evaluation_only_provider_coordinates",
        "coordinate_transform": {
            "source_width": source_width,
            "source_height": source_height,
            "prediction_width": prediction_width,
            "prediction_height": prediction_height,
            "scale_x": round(scale_x, 8),
            "scale_y": round(scale_y, 8),
        },
        "metrics": evaluate(
            predictions,
            transformed_reference,
            stride=stride,
            max_distance=args.max_distance,
            detections_by_frame=load_frozen_detection_records(
                prediction_root
            ),
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
