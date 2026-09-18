from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from football_poc.coordination import (
    CoordinationConfig,
    DatabaseMode,
    run_coordination_preflight,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and bootstrap PostgreSQL coordination"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit machine-readable JSON",
    )
    arguments = parser.parse_args(argv)
    try:
        config = CoordinationConfig.from_environment()
        result = run_coordination_preflight(config)
        payload = {
            "mode": result.health.mode.value,
            "writable": result.writable,
            "detail": _safe_detail(
                result.health.mode, result.writable
            ),
            "migrations_applied": list(
                result.migrations.applied_versions
                if result.migrations
                else ()
            ),
            "migrations_new": list(
                result.migrations.newly_applied_versions
                if result.migrations
                else ()
            ),
            "reconciliation": result.reconciliation.status,
        }
        exit_code = (
            1
            if config.database_url is not None
            and (
                result.health.mode is not DatabaseMode.AVAILABLE
                or not result.writable
            )
            else 0
        )
        result.repository.close()
    except Exception as error:
        payload = {
            "mode": DatabaseMode.UNAVAILABLE.value,
            "writable": False,
            "detail": f"Coordination preflight failed: {type(error).__name__}",
            "migrations_applied": [],
            "migrations_new": [],
            "reconciliation": "not_run",
        }
        exit_code = 2

    if arguments.json_output:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(
            f"coordination: {payload['mode']}; "
            f"writable={str(payload['writable']).lower()}; "
            f"{payload['detail']}"
        )
    return exit_code


def _safe_detail(mode: DatabaseMode, writable: bool) -> str:
    if mode is DatabaseMode.DISABLED:
        return "coordination is not configured"
    if mode is DatabaseMode.AVAILABLE and writable:
        return "coordination preflight passed"
    return "coordination preflight did not enable writable mode"


if __name__ == "__main__":
    raise SystemExit(main())
