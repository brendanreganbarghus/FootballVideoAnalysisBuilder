from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CompletedPassSettings:
    maximum_transfer_seconds: float = 3.0
    minimum_transfer_heights: float = 1.5
    minimum_pass_speed_pixels_per_second: float = 60.0
    maximum_pass_step_seconds: float = 0.24
    pass_flight_debounce_seconds: float = 1.2
    pass_sender_lookback_seconds: float = 1.0
    pass_receiver_window_seconds: float = 2.0
    transfer_deduplication_seconds: float = 0.8
    startup_guard_seconds: float = 4.0
    startup_receiver_control_radius_heights: float = 1.2
    event_type: str = "pass_candidate"


def run(results_dir: Path, settings: CompletedPassSettings = CompletedPassSettings()) -> dict[str, Any]:
    import json
    events = json.loads((results_dir / "predicted-events.json").read_text(encoding="utf-8"))
    passes = [event for event in events if event.get("event_type") == settings.event_type]
    return {"stage": "completed_pass", "count": len(passes), "events": passes}
