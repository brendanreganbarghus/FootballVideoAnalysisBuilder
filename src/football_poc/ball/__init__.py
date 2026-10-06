from __future__ import annotations

from pathlib import Path

_MODULE_ORDER = (
    "settings.py",
    "types.py",
    "ledger.py",
    "confirm_yolo.py",
    "time_machine.py",
    "time_machine_search.py",
    "flipbook.py",
    "aerial.py",
    "scenery.py",
    "restart_spot.py",
    "tracker.py",
    "state_estimates.py",
    "selection.py",
    "template_support.py",
    "bidirectional_templates.py",
    "terminal_forward_templates.py",
    "full_rate_corridors.py",
    "motion_streaks.py",
    "frames.py",
    "raw_motion_selection.py",
    "outliers.py",
    "focused_multiscale.py",
    "short_motion_bridges.py",
    "kalman.py",
    "dense_flow.py",
    "motion_support.py",
    "io_filters.py",
)

_here = Path(__file__).resolve().parent
for _module_name in _MODULE_ORDER:
    _source = (_here / _module_name).read_text(encoding="utf-8")
    exec(compile(_source, str(_here / _module_name), "exec"), globals())

__all__ = [
    name
    for name in globals()
    if not name.startswith("__")
    and name not in {"Path", "_here", "_module_name", "_source", "_MODULE_ORDER"}
]
