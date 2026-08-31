from __future__ import annotations

import argparse
from pathlib import Path

from football_poc.chunk_simulator import simulate_event_chunks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay batch events as overlapping live-style chunks."
    )
    parser.add_argument(
        "manifest",
        type=Path,
        nargs="?",
        default=Path("benchmarks/soccertrack-117093-window.json"),
    )
    parser.add_argument(
        "--events",
        type=Path,
        default=Path(
            "benchmarks/soccertrack-117093-fused/predicted-events.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "benchmarks/soccertrack-117093-fused/chunk-simulation.json"
        ),
    )
    parser.add_argument("--chunk-seconds", type=float, default=20.0)
    parser.add_argument("--overlap-seconds", type=float, default=2.0)
    parser.add_argument(
        "--processing-seconds",
        type=float,
        default=20.0,
        help="Synthetic worker time for each full-size chunk.",
    )
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--max-chunks", type=int, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output = simulate_event_chunks(
        manifest_path=args.manifest,
        events_path=args.events,
        output=args.output,
        chunk_seconds=args.chunk_seconds,
        overlap_seconds=args.overlap_seconds,
        processing_seconds_per_chunk=args.processing_seconds,
        state_path=args.state,
        max_chunks=args.max_chunks,
    )
    print(f"Chunk simulation written to {output.resolve()}")


if __name__ == "__main__":
    main()
