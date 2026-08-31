from __future__ import annotations

import argparse
import json
from pathlib import Path

from football_poc.event_comparison import compare_manual_events


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare manual Alfheim completion times with AI events."
    )
    parser.add_argument(
        "--manual",
        type=Path,
        default=Path(
            "benchmarks/alfheim/window-555/manual-events.json"
        ),
    )
    parser.add_argument(
        "--predicted",
        type=Path,
        default=Path(
            "benchmarks/alfheim/window-555/analytics-data/predicted-events.json"
        ),
    )
    parser.add_argument(
        "--boundary-events",
        type=Path,
        default=Path("benchmarks/alfheim/window-555/boundary-events.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "benchmarks/alfheim/window-555/analytics-data/manual-comparison.json"
        ),
    )
    parser.add_argument("--tolerance", type=float, default=1.0)
    args = parser.parse_args()

    manual_payload = json.loads(args.manual.read_text(encoding="utf-8"))
    predictions = json.loads(args.predicted.read_text(encoding="utf-8"))
    report = compare_manual_events(
        manual_payload["events"],
        predictions,
        tolerance_seconds=args.tolerance,
    )
    boundary = json.loads(args.boundary_events.read_text(encoding="utf-8"))
    report["manual_boundary_context"] = [
        {
            **event,
            "boundary_state": _boundary_state(
                float(event["clip_seconds"]), boundary["intervals"]
            ),
        }
        for event in manual_payload["events"]
    ]
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"Matched {report['matched_event_count']}/{report['manual_event_count']} "
        f"manual events; report written to {args.output.resolve()}"
    )


def _boundary_state(seconds: float, intervals: list[dict[str, object]]) -> str:
    restart_context_seconds = 2.0
    for interval in intervals:
        if float(interval["start_seconds"]) <= seconds <= float(
            interval["end_seconds"]
        ):
            return "possible_out"
        resumed = interval.get("resumed_seconds")
        if (
            resumed is not None
            and float(resumed) <= seconds < float(resumed) + restart_context_seconds
        ):
            return "recently_resumed"
    return "inside"


if __name__ == "__main__":
    main()
