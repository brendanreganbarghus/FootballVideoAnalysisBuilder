from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from football_poc.engine import ball_control, ball_evidence, completed_pass, match_state_export, possession_ledger, shot, turnover

StageRunner = Callable[[Path], dict[str, Any]]

STAGES: tuple[tuple[str, StageRunner], ...] = (
    ("01_ball_evidence", ball_evidence.run),
    ("02_ball_control_touch", ball_control.run),
    ("03_possession_ledger", possession_ledger.run),
    ("04_completed_pass", completed_pass.run),
    ("05_turnover", turnover.run),
    ("06_shot", shot.run),
    ("07_match_state_export", match_state_export.run),
)


def collect_stage_results(results_dir: Path) -> dict[str, dict[str, Any]]:
    return {name: runner(results_dir) for name, runner in STAGES}
