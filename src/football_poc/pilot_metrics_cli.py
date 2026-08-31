from __future__ import annotations

import argparse
from pathlib import Path

from football_poc.pilot_metrics import build_pilot_metrics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish compact per-minute grassroots pilot statistics."
    )
    parser.add_argument("--player-tracks", type=Path, required=True)
    parser.add_argument("--possession", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--block-seconds", type=float, default=60.0)
    args = parser.parse_args()
    destination = build_pilot_metrics(
        player_tracks_path=args.player_tracks,
        possession_path=args.possession,
        events_path=args.events,
        calibration_path=args.calibration,
        output_path=args.output,
        block_seconds=args.block_seconds,
    )
    print(f"Pilot metrics written to {destination.resolve()}")


if __name__ == "__main__":
    main()
