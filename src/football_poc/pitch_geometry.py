from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


@dataclass(frozen=True)
class BoundaryInterval:
    start_frame: int
    end_frame: int
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    minimum_signed_distance_px: float
    resumed_seconds: float | None
    starts_outside: bool


@dataclass(frozen=True)
class PitchCalibration:
    image_points: tuple[tuple[float, float], ...]
    pitch_points_metres: tuple[tuple[float, float], ...]
    width_metres: float
    length_metres: float

    @property
    def matrix(self) -> np.ndarray:
        matrix, _ = cv2.findHomography(
            np.asarray(self.image_points, dtype=np.float32),
            np.asarray(self.pitch_points_metres, dtype=np.float32),
            method=0,
        )
        if matrix is None:
            raise ValueError("Pitch points do not produce a valid homography")
        return matrix


def load_metric_pitch_calibration(path: Path) -> PitchCalibration:
    payload = json.loads(path.read_text(encoding="utf-8"))
    image_points = _calibration_points(payload.get("image_points"), "image")
    pitch_points = _calibration_points(
        payload.get("pitch_points_metres"), "pitch"
    )
    if len(image_points) != len(pitch_points) or len(image_points) < 4:
        raise ValueError(
            "Metric pitch calibration requires at least four matched point pairs"
        )
    dimensions = payload.get("pitch_dimensions_metres", {})
    width = float(dimensions.get("width", 0))
    length = float(dimensions.get("length", 0))
    if width <= 0 or length <= 0:
        raise ValueError("Pitch dimensions must be positive")
    return PitchCalibration(image_points, pitch_points, width, length)


def project_pitch_points(
    points: Iterable[tuple[float, float]], calibration: PitchCalibration
) -> list[tuple[float, float]]:
    source = np.asarray(tuple(points), dtype=np.float32)
    if source.size == 0:
        return []
    projected = cv2.perspectiveTransform(
        source.reshape(-1, 1, 2), calibration.matrix
    ).reshape(-1, 2)
    return [(float(point[0]), float(point[1])) for point in projected]


def _calibration_points(
    value: object, label: str
) -> tuple[tuple[float, float], ...]:
    if not isinstance(value, list):
        raise ValueError(f"Metric pitch calibration requires {label} points")
    try:
        return tuple((float(point[0]), float(point[1])) for point in value)
    except (IndexError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid {label} calibration point") from error


def load_pitch_boundary(path: Path) -> tuple[tuple[float, float], ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    points = payload.get("boundary")
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError("Pitch calibration requires at least three boundary points")
    return tuple((float(point[0]), float(point[1])) for point in points)


def signed_pitch_distance(
    point: tuple[float, float],
    boundary: Iterable[tuple[float, float]],
) -> float:
    polygon = np.asarray(tuple(boundary), dtype=np.float32)
    if len(polygon) < 3:
        raise ValueError("Pitch boundary requires at least three points")
    return float(cv2.pointPolygonTest(polygon, point, True))


def detect_boundary_intervals(
    points: Iterable[dict[str, float | int]],
    *,
    boundary: Iterable[tuple[float, float]],
    outside_margin_px: float = 12.0,
    minimum_outside_seconds: float = 0.4,
) -> list[BoundaryInterval]:
    if outside_margin_px < 0 or minimum_outside_seconds < 0:
        raise ValueError("Boundary margins and durations must be non-negative")
    ordered = sorted(points, key=lambda point: int(point["frame"]))
    polygon = tuple(boundary)
    outside_groups: list[list[tuple[dict[str, float | int], float]]] = []
    current: list[tuple[dict[str, float | int], float]] = []
    for point in ordered:
        distance = signed_pitch_distance(
            (float(point["x"]), float(point["y"])), polygon
        )
        if distance < -outside_margin_px:
            current.append((point, distance))
            continue
        if current:
            outside_groups.append(current)
            current = []
    if current:
        outside_groups.append(current)

    intervals: list[BoundaryInterval] = []
    for group in outside_groups:
        first, last = group[0][0], group[-1][0]
        start_seconds = float(first["seconds"])
        end_seconds = float(last["seconds"])
        duration = end_seconds - start_seconds
        if duration + 1e-9 < minimum_outside_seconds:
            continue
        end_frame = int(last["frame"])
        resumed = next(
            (
                float(point["seconds"])
                for point in ordered
                if int(point["frame"]) > end_frame
                and signed_pitch_distance(
                    (float(point["x"]), float(point["y"])), polygon
                )
                >= -outside_margin_px
            ),
            None,
        )
        intervals.append(
            BoundaryInterval(
                start_frame=int(first["frame"]),
                end_frame=end_frame,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                duration_seconds=round(duration, 3),
                minimum_signed_distance_px=round(
                    min(distance for _, distance in group), 2
                ),
                resumed_seconds=resumed,
                starts_outside=int(first["frame"]) == int(ordered[0]["frame"]),
            )
        )
    return intervals


def write_boundary_report(
    path: Path,
    *,
    calibration_path: Path,
    intervals: Iterable[BoundaryInterval],
    outside_margin_px: float,
    minimum_outside_seconds: float,
) -> None:
    path.write_text(
        json.dumps(
            {
                "calibration": str(calibration_path.resolve()),
                "status": "possible_out_of_bounds_candidates",
                "outside_margin_px": outside_margin_px,
                "minimum_outside_seconds": minimum_outside_seconds,
                "intervals": [asdict(interval) for interval in intervals],
                "limitations": [
                    "The static image-space boundary is manually calibrated.",
                    "A crossing is a review trigger, not a confirmed referee decision.",
                    "Occlusion and annotation loss can mimic an out-of-bounds interval.",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
