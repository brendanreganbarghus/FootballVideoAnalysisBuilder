"""Image-size conversion for static camera configuration.

Camera configuration (goal faces, goalkeeper regions) is drawn once on a
reference image and declares that size with ``image_width``/``image_height``.
Runtime positions may live on a resized copy of the same view, so the
configuration is converted to the size of the positions it is compared with.
Undeclared configuration is used unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2

# Ball coordinates copied from the provider stay in the provider's own image
# space, which is the space the shared camera configuration was drawn on.
PROVIDER_SPACE_SOURCE_KINDS = frozenset(
    {
        "evaluation_only_provider_coordinates",
        "reviewer_corrected_innovation_coordinates",
    }
)

ImageSize = tuple[float, float]


def declared_size(payload: dict[str, Any]) -> ImageSize | None:
    width, height = payload.get("image_width"), payload.get("image_height")
    if width is None or height is None:
        return None
    width, height = float(width), float(height)
    if width <= 0 or height <= 0:
        raise ValueError("Declared image size must be positive")
    return width, height


def scale_factors(
    payload: dict[str, Any], target: ImageSize | None
) -> tuple[float, float]:
    """Factors converting ``payload`` coordinates to the ``target`` size."""
    source = declared_size(payload)
    if source is None or target is None:
        return 1.0, 1.0
    return float(target[0]) / source[0], float(target[1]) / source[1]


def video_size(video: Path) -> ImageSize:
    capture = cv2.VideoCapture(str(video))
    try:
        width = capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
    finally:
        capture.release()
    if width <= 0 or height <= 0:
        raise ValueError(f"Could not read video size: {video}")
    return float(width), float(height)


def ball_coordinate_size(
    ball_tracks: dict[str, Any], video: ImageSize | None
) -> ImageSize | None:
    """Image size of the ball coordinates; None means configuration space."""
    declared = declared_size(ball_tracks)
    if declared is not None:
        return declared
    if ball_tracks.get("source_kind") in PROVIDER_SPACE_SOURCE_KINDS:
        return None
    return video


def scale_goalkeeper_affiliations(
    payload: dict[str, Any], target: ImageSize | None
) -> list[dict[str, Any]]:
    sx, sy = scale_factors(payload, target)
    scaled = []
    for affiliation in payload.get("affiliations", []):
        item = dict(affiliation)
        region = affiliation.get("region")
        if isinstance(region, dict):
            item["region"] = {
                "x_min": float(region["x_min"]) * sx,
                "x_max": float(region["x_max"]) * sx,
                "y_min": float(region["y_min"]) * sy,
                "y_max": float(region["y_max"]) * sy,
            }
        scaled.append(item)
    return scaled
