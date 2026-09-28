from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TurnoverSettings:
    turnover_smoothing_seconds: float | None = None
    turnover_control_radius_heights: float | None = None
    maximum_transfer_seconds: float = 3.0
    minimum_transfer_heights: float = 1.5
    transfer_deduplication_seconds: float = 0.8
    event_type: str = "turnover_candidate"


def run(results_dir: Path, settings: TurnoverSettings = TurnoverSettings()) -> dict[str, Any]:
    import json
    events = json.loads((results_dir / "predicted-events.json").read_text(encoding="utf-8"))
    turnovers = [event for event in events if event.get("event_type") == settings.event_type]
    return {"stage": "turnover", "count": len(turnovers), "events": turnovers}
