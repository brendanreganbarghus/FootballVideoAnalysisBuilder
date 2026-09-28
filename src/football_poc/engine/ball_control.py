from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BallControlSettings:
    control_radius_heights: float = 1.2
    maximum_flyby_speed_pixels_per_second: float | None = None
    maximum_flyby_speed_heights_per_second: float | None = None
    minimum_flyby_direction_cosine: float = 0.85
    maximum_ground_contact_height_ratio: float | None = None
    maximum_aerial_contact_direction_cosine: float = 0.5
    future_control_confirmation_seconds: float = 0.0
    sample_limit: int = 8


def run(results_dir: Path, settings: BallControlSettings = BallControlSettings()) -> dict[str, Any]:
    import json
    possession = json.loads((results_dir / "possession.json").read_text(encoding="utf-8"))
    observations = possession.get("observations", [])
    controls = [
        {
            "frame": item["source_frame"],
            "seconds": item["clip_seconds"],
            "team": item["team"],
            "track": item["player_track_id"],
            "control_ratio": item["control_ratio"],
        }
        for item in observations
    ]
    return {
        "stage": "ball_control_touch",
        "count": len(controls),
        "sample": controls[: settings.sample_limit],
        "teams": sorted({item["team"] for item in controls}),
        "tracks": sorted({item["track"] for item in controls}),
    }
