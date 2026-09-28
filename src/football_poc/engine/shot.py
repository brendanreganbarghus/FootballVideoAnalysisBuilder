from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ShotSettings:
    minimum_shot_speed_pixels_per_second: float = 200.0
    minimum_shot_goal_cosine: float = 0.92
    infer_shots: bool = True
    prefixes: tuple[str, ...] = ("shot",)


def run(results_dir: Path, settings: ShotSettings = ShotSettings()) -> dict[str, Any]:
    import json
    events = json.loads((results_dir / "predicted-events.json").read_text(encoding="utf-8"))
    shots = [
        event for event in events
        if any(str(event.get("event_type", "")).startswith(prefix) for prefix in settings.prefixes)
    ]
    return {"stage": "shot", "count": len(shots), "events": shots}
