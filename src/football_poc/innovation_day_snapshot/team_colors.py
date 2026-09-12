from __future__ import annotations

from math import dist
from typing import Mapping

import cv2
import numpy as np


def dominant_jersey_color(
    jersey_crop: np.ndarray, *, clusters: int = 3
) -> tuple[int, int, int]:
    if jersey_crop.size == 0:
        raise ValueError("Jersey crop cannot be empty")
    pixels = jersey_crop.reshape(-1, 3).astype(np.float32)
    cluster_count = min(clusters, len(pixels))
    if cluster_count < 1:
        raise ValueError("K-Means cluster count must be positive")
    _, labels, centers = cv2.kmeans(
        pixels,
        cluster_count,
        None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5),
        5,
        cv2.KMEANS_PP_CENTERS,
    )
    counts = np.bincount(labels.reshape(-1), minlength=cluster_count)
    dominant = centers[int(np.argmax(counts))]
    return tuple(int(round(channel)) for channel in dominant)


def assign_color_group(
    color_bgr: tuple[int, int, int],
    reference_colors_bgr: Mapping[str, tuple[int, int, int]],
) -> str:
    if not reference_colors_bgr:
        raise ValueError("At least one reference jersey color is required")
    return min(
        reference_colors_bgr,
        key=lambda label: dist(color_bgr, reference_colors_bgr[label]),
    )
