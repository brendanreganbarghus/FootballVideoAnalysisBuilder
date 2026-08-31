from __future__ import annotations

import argparse
from pathlib import Path

from football_poc.aggregate import aggregate_evaluations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate multiple SoccerTrack event evaluations."
    )
    parser.add_argument("evaluations", nargs="+", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/soccertrack-117093-aggregate.json"),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output = aggregate_evaluations(args.evaluations, args.output)
    print(f"Aggregate evaluation written to {output.resolve()}")


if __name__ == "__main__":
    main()
