from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MatchStateExportSettings:
    minimum_restart_speed_pixels_per_second: float = 200.0
    boundary_ownership_lookback_seconds: float = 2.0
    include_events: bool = True


def run(results_dir: Path, settings: MatchStateExportSettings = MatchStateExportSettings()) -> dict[str, Any]:
    import json
    match_state = json.loads((results_dir / "match-state-events.json").read_text(encoding="utf-8"))
    predicted = json.loads((results_dir / "predicted-events.json").read_text(encoding="utf-8"))
    return {
        "stage": "match_state_export",
        "match_state": match_state if settings.include_events else {},
        "event_count": len(predicted),
        "event_types": [event.get("event_type") for event in predicted],
    }
