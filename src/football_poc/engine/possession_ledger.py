from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PossessionLedgerSettings:
    smoothing_seconds: float = 0.24
    segment_gap_seconds: float = 0.64
    identity_switch_radius_heights: float = 0.75
    co_visible_track_return_seconds: float = 0.0
    minimum_segment_observations: int = 2
    transient_opponent_max_seconds: float = 1.2
    occluded_owner_max_seconds: float | None = None
    occluded_owner_max_speed_heights_per_second: float = 3.0
    occluded_owner_min_direction_cosine: float | None = None
    include_segments: bool = True


def run(results_dir: Path, settings: PossessionLedgerSettings = PossessionLedgerSettings()) -> dict[str, Any]:
    import json
    possession = json.loads((results_dir / "possession.json").read_text(encoding="utf-8"))
    segments = possession.get("segments", [])
    return {
        "stage": "possession_ledger",
        "segment_count": len(segments),
        "segments": segments if settings.include_segments else [],
        "team_order": [segment.get("team") for segment in segments],
        "player_order": [segment.get("player_track_id") for segment in segments],
    }
