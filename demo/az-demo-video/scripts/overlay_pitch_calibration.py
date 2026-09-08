"""Draw the saved Alfheim camera calibration onto demo screenshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


REPO = Path(__file__).resolve().parents[3]
CALIBRATION = (
    REPO / "benchmarks" / "alfheim" / "window-555" / "pitch-calibration.json"
)

COLORS = {
    "near_touchline": "#ffd33d",
    "far_touchline": "#ffd33d",
    "left_goal_line": "#ff9f1c",
    "right_goal_line": "#ff9f1c",
    "left_goal_mouth": "#00e5ff",
    "right_goal_mouth": "#00e5ff",
}


def project(
    point: list[int],
    *,
    source_width: int,
    source_height: int,
    media_box: tuple[int, int, int, int],
) -> tuple[float, float]:
    left, top, width, height = media_box
    return (
        left + point[0] * width / source_width,
        top + point[1] * height / source_height,
    )


def draw_calibration(
    image_path: Path,
    media_box: tuple[int, int, int, int],
) -> None:
    calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    source_width = int(calibration["image_width"])
    source_height = int(calibration["image_height"])

    for feature, color in COLORS.items():
        points = [
            project(
                point,
                source_width=source_width,
                source_height=source_height,
                media_box=media_box,
            )
            for point in calibration["features"][feature]
        ]
        if feature.endswith("goal_mouth"):
            points.append(points[0])
        draw.line(points, fill=color, width=3, joint="curve")
        for x, y in points[:-1] if feature.endswith("goal_mouth") else points:
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=color)

    image.save(image_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument(
        "--media-box",
        nargs=4,
        type=int,
        metavar=("LEFT", "TOP", "WIDTH", "HEIGHT"),
        required=True,
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    draw_calibration(args.image, tuple(args.media_box))
