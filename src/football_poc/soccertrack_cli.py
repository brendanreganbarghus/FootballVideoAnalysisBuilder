from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from football_poc.soccertrack import ActionWindow, SoccerTrackMatch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect SoccerTrack data and create event-aligned manifests."
    )
    parser.add_argument(
        "--root", type=Path, default=Path("data") / "soccertrack-v2"
    )
    parser.add_argument("--match", default="117093")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("inspect", help="Summarize the downloaded match")

    select = subparsers.add_parser(
        "select-window", help="Select and write an event-rich benchmark window"
    )
    select.add_argument("--half", type=int, choices=(1, 2), default=1)
    select.add_argument("--duration", type=float, default=60.0)
    select.add_argument(
        "--start",
        type=float,
        default=None,
        help="Use an exact half-relative start instead of automatic selection.",
    )
    select.add_argument("--require", action="append", default=["shot"])
    select.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks") / "soccertrack-117093-window.json",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    match = SoccerTrackMatch.load(args.root, args.match)

    if args.command == "inspect":
        counts = Counter(action.label for action in match.actions)
        result = {
            "match_id": match.match_id,
            "fps": match.fps,
            "schema": match.schema_variant,
            "actions": len(match.actions),
            "halves": {
                str(half): len(match.actions_for_half(half)) for half in (1, 2)
            },
            "labels": dict(sorted(counts.items())),
        }
        print(json.dumps(result, indent=2))
        return

    if args.start is None:
        window = match.select_event_window(
            half=args.half,
            duration_seconds=args.duration,
            required_labels=args.require,
        )
    else:
        window = ActionWindow(
            half=args.half,
            start_seconds=args.start,
            duration_seconds=args.duration,
            actions=match.actions_in_window(
                half=args.half,
                start_seconds=args.start,
                duration_seconds=args.duration,
            ),
        )
    output = match.write_window_manifest(window, args.output)
    print(
        f"Selected half {window.half}, {window.start_seconds:.2f}-"
        f"{window.end_seconds:.2f}s with {len(window.actions)} actions."
    )
    print(json.dumps(window.counts, indent=2))
    print(f"Manifest written to {output.resolve()}")


if __name__ == "__main__":
    main()
