from __future__ import annotations

from football_poc.engine.bootstrap import EXPORTS
from football_poc.engine.stage_pipeline import STAGES, collect_stage_results

globals().update(EXPORTS)

__all__ = ["STAGES", "collect_stage_results", *sorted(EXPORTS)]
