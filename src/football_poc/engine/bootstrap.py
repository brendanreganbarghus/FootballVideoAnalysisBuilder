from __future__ import annotations

from football_poc.engine import (
    advanced_passes,
    ball_control,
    ball_evidence,
    boundary_restart,
    completed_pass,
    contact_helpers,
    flight_receptions,
    live_helpers,
    live_recovery,
    live_refinement,
    live_segments,
    live_turnovers,
    match_state_export,
    pass_cleanup,
    pass_reconciliation,
    pass_recovery,
    pass_recovery_extra,
    pipeline,
    possession_ledger,
    shot,
    turnover,
    turnover_refinement,
)
from football_poc.engine import common

STAGE_MODULES = (
    common,
    ball_evidence,
    ball_control,
    possession_ledger,
    completed_pass,
    pass_reconciliation,
    turnover,
    turnover_refinement,
    contact_helpers,
    flight_receptions,
    advanced_passes,
    pass_cleanup,
    pass_recovery,
    pass_recovery_extra,
    boundary_restart,
    shot,
    live_segments,
    live_turnovers,
    live_refinement,
    live_recovery,
    live_helpers,
    match_state_export,
    pipeline,
)


def _is_exported(name: str) -> bool:
    return not name.startswith("__") and name not in {"annotations"}


class _PossessionMonkeypatchProxy:
    def __init__(self, name: str, original: object) -> None:
        self.name = name
        self.original = original

    def __call__(self, *args: object, **kwargs: object) -> object:
        import sys

        possession = sys.modules.get("football_poc.possession")
        if possession is not None:
            current = vars(possession).get(self.name)
            if current is not None and current is not self:
                return current(*args, **kwargs)
        return self.original(*args, **kwargs)  # type: ignore[misc]


def _install_possession_monkeypatch_proxies(exports: dict[str, object]) -> None:
    monkeypatched_names = {
        "_ball_motion_evidence",
        "_contested_contact_seconds",
        "_nearby_ball_teams",
        "_receiver_team_evidence",
    }
    proxies = {
        name: _PossessionMonkeypatchProxy(name, exports[name])
        for name in monkeypatched_names
        if name in exports
    }
    for module in STAGE_MODULES:
        for name, proxy in proxies.items():
            if name in module.__dict__:
                module.__dict__[name] = proxy


def wire_stage_modules() -> dict[str, object]:
    exports: dict[str, object] = {}
    for module in STAGE_MODULES:
        exports.update(
            (name, value)
            for name, value in vars(module).items()
            if _is_exported(name)
        )
    for module in STAGE_MODULES:
        module.__dict__.update(exports)
    _install_possession_monkeypatch_proxies(exports)
    return exports


EXPORTS = wire_stage_modules()
