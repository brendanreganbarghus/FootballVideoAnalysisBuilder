"""Camera-specific goal-face calibration for Innovation shots on target.

The Alfheim panorama is stitched, so a single pitch homography is not valid
across the image. Each goal is therefore calibrated locally: the four
user-calibrated goal-frame corners are matched to the IFAB Law 1 goal
dimensions and fitted to a goal-face homography (image -> lateral pitch y,
height z). Uncertainty is propagated from a fixed corner-click error and a
fixed monocular depth margin, both set before any event evaluation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np


CALIBRATION_VERSION = "innovation-goal-face-v1"
GOAL_WIDTH_M = 7.32
CROSSBAR_HEIGHT_M = 2.44
PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
CLICK_ERROR_PX = 4.0
MONOCULAR_DEPTH_MARGIN_M = 0.25
MAX_POST_BASE_OFFSET_PX = 15.0

Point = tuple[float, float]


class GoalCalibrationError(ValueError):
    """Raised when the goal-frame calibration is missing or implausible."""


@dataclass(frozen=True)
class GoalFace:
    side: str
    goal_line_x: float
    post_y: tuple[float, float]
    polygon: tuple[Point, ...]
    matrix: np.ndarray
    uncertainty_m: float

    def project(self, point: Point) -> tuple[float, float]:
        projected = cv2.perspectiveTransform(
            np.asarray([[point]], dtype=np.float64), self.matrix
        )[0][0]
        return float(projected[0]), float(projected[1])

    def image_distance(self, point: Point) -> float:
        """Signed distance in pixels: negative inside the goal-face polygon."""
        contour = np.asarray(self.polygon, dtype=np.float32).reshape(-1, 1, 2)
        return -float(
            cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), True)
        )

    def centroid(self) -> Point:
        xs, ys = zip(*self.polygon)
        return sum(xs) / len(xs), sum(ys) / len(ys)

    def to_contract(self) -> dict[str, Any]:
        return {
            "goal_line_x": self.goal_line_x,
            "post_y": list(self.post_y),
            "crossbar_z": CROSSBAR_HEIGHT_M,
            "uncertainty_m": round(self.uncertainty_m, 3),
        }


def _points(value: Any, name: str) -> list[Point]:
    if not isinstance(value, list) or not value:
        raise GoalCalibrationError(f"Calibration feature '{name}' is missing")
    try:
        return [(float(point[0]), float(point[1])) for point in value]
    except (IndexError, TypeError, ValueError) as error:
        raise GoalCalibrationError(f"Invalid point in '{name}'") from error


def _segment_projection(point: Point, a: Point, b: Point) -> tuple[float, float]:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    t = 0.0 if length_sq == 0 else max(
        0.0, min(1.0, ((point[0] - ax) * dx + (point[1] - ay) * dy) / length_sq)
    )
    px, py = ax + t * dx, ay + t * dy
    return float(np.hypot(point[0] - px, point[1] - py)), t


def _polyline_position(point: Point, line: Sequence[Point]) -> tuple[float, float]:
    """Return (distance to polyline, arc length from the far-touchline end)."""
    ordered = list(line) if line[0][1] <= line[-1][1] else list(reversed(line))
    best = (float("inf"), 0.0)
    travelled = 0.0
    for a, b in zip(ordered, ordered[1:]):
        segment = float(np.hypot(b[0] - a[0], b[1] - a[1]))
        distance, t = _segment_projection(point, a, b)
        if distance < best[0]:
            best = (distance, travelled + t * segment)
        travelled += segment
    return best


def _fit(image: Sequence[Point], face: Sequence[Point]) -> np.ndarray:
    matrix = cv2.getPerspectiveTransform(
        np.asarray(image, dtype=np.float32), np.asarray(face, dtype=np.float32)
    )
    if matrix is None or not np.isfinite(matrix).all():
        raise GoalCalibrationError("Goal corners do not form a valid homography")
    return matrix.astype(np.float64)


def _uncertainty(image: Sequence[Point], face: Sequence[Point]) -> float:
    base = _fit(image, face)
    probes = [*image, tuple(np.mean(np.asarray(image), axis=0))]
    reference = cv2.perspectiveTransform(
        np.asarray([probes], dtype=np.float64), base
    )[0]
    worst = 0.0
    for index in range(len(image)):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            perturbed = list(image)
            x, y = perturbed[index]
            perturbed[index] = (x + dx * CLICK_ERROR_PX, y + dy * CLICK_ERROR_PX)
            moved = cv2.perspectiveTransform(
                np.asarray([probes], dtype=np.float64), _fit(perturbed, face)
            )[0]
            worst = max(worst, float(np.max(np.linalg.norm(moved - reference, axis=1))))
    return worst + MONOCULAR_DEPTH_MARGIN_M


def build_goal_face(side: str, polygon: Sequence[Point], goal_line: Sequence[Point]) -> GoalFace:
    if len(polygon) != 4:
        raise GoalCalibrationError(f"{side} goal mouth needs four corners")
    ranked = sorted(polygon, key=lambda point: _polyline_position(point, goal_line)[0])
    bases, bars = ranked[:2], ranked[2:]
    for base in bases:
        offset = _polyline_position(base, goal_line)[0]
        if offset > MAX_POST_BASE_OFFSET_PX:
            raise GoalCalibrationError(
                f"{side} goal post base is {offset:.1f}px from the goal line"
            )
    bases = sorted(bases, key=lambda point: _polyline_position(point, goal_line)[1])
    paired_bars = [
        min(bars, key=lambda bar: np.hypot(bar[0] - base[0], bar[1] - base[1]))
        for base in bases
    ]
    if len(set(paired_bars)) != 2:
        raise GoalCalibrationError(f"{side} crossbar ends cannot be paired to posts")
    for base, bar in zip(bases, paired_bars):
        if bar[1] >= base[1]:
            raise GoalCalibrationError(f"{side} crossbar corner is below its post base")
    low = PITCH_WIDTH_M / 2 - GOAL_WIDTH_M / 2
    high = PITCH_WIDTH_M / 2 + GOAL_WIDTH_M / 2
    image = [bases[0], bases[1], paired_bars[1], paired_bars[0]]
    face = [(low, 0.0), (high, 0.0), (high, CROSSBAR_HEIGHT_M), (low, CROSSBAR_HEIGHT_M)]
    return GoalFace(
        side=side,
        goal_line_x=0.0 if side == "left" else PITCH_LENGTH_M,
        post_y=(round(low, 3), round(high, 3)),
        polygon=tuple(image),
        matrix=_fit(image, face),
        uncertainty_m=_uncertainty(image, face),
    )


def load_goal_faces(path: Path) -> tuple[dict[str, GoalFace], dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GoalCalibrationError(f"Cannot read goal calibration {path}") from error
    features = payload.get("features")
    if not isinstance(features, dict):
        raise GoalCalibrationError("Calibration has no features")
    faces = {
        side: build_goal_face(
            side,
            _points(features.get(f"{side}_goal_mouth"), f"{side}_goal_mouth"),
            _points(features.get(f"{side}_goal_line"), f"{side}_goal_line"),
        )
        for side in ("left", "right")
    }
    provenance = {
        "calibration_version": CALIBRATION_VERSION,
        "camera_id": payload.get("camera_id"),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "click_error_px": CLICK_ERROR_PX,
        "monocular_depth_margin_m": MONOCULAR_DEPTH_MARGIN_M,
        "uncertainty_m": {
            side: round(face.uncertainty_m, 3) for side, face in faces.items()
        },
    }
    return faces, provenance
