from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BallEvidenceSettings:
    include_summary: bool = True


def run(results_dir: Path, settings: BallEvidenceSettings = BallEvidenceSettings()) -> dict[str, Any]:
    import json
    possession = json.loads((results_dir / "possession.json").read_text(encoding="utf-8"))
    observations = possession.get("observations", [])
    return {
        "stage": "ball_evidence",
        "observation_count": len(observations),
        "has_ball_state_estimates": "ball_evidence_summary" in possession,
        "ball_evidence_summary": possession.get("ball_evidence_summary", {}) if settings.include_summary else {},
        "evidence_values": sorted({item.get("ball_evidence", "detector") for item in observations}),
        "state_values": sorted({item.get("ball_state", "observed") for item in observations}),
    }
