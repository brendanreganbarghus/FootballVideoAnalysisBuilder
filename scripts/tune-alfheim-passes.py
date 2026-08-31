from __future__ import annotations

import argparse
import contextlib
import io
import itertools
import json
import tempfile
from pathlib import Path

from football_poc.event_comparison import compare_manual_events
from football_poc.possession import infer_cached_possession


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tune possession parameters against manual Alfheim events."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("benchmarks/alfheim/window-555/manifest.json"),
    )
    parser.add_argument(
        "--player-tracks",
        type=Path,
        default=Path(
            "benchmarks/alfheim/window-555/analytics-data/player-tracks.json"
        ),
    )
    parser.add_argument(
        "--ball-tracks",
        type=Path,
        default=Path(
            "benchmarks/alfheim/window-555/ground-truth-ball-tracks.json"
        ),
    )
    parser.add_argument(
        "--manual",
        type=Path,
        default=Path("benchmarks/alfheim/window-555/manual-events.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "benchmarks/alfheim/window-555/analytics-data/tuning-results.json"
        ),
    )
    args = parser.parse_args()
    manual = json.loads(args.manual.read_text(encoding="utf-8"))["events"]
    configurations = itertools.product(
        (1.8, 2.1, 2.4, 2.7, 3.0),
        (0.8, 1.0, 1.2),
        (0.25, 0.5, 1.0),
        (0.3, 0.6, 0.9, 1.2),
        (2.0, 3.0),
        (3.0, 4.0),
    )
    results = []
    with tempfile.TemporaryDirectory(prefix="alfheim-tuning-") as temporary:
        root = Path(temporary)
        for index, (
            control_radius,
            smoothing,
            minimum_transfer,
            debounce,
            receiver_window,
            maximum_transfer,
        ) in enumerate(configurations):
            output = root / str(index)
            with contextlib.redirect_stdout(io.StringIO()):
                infer_cached_possession(
                    manifest_path=args.manifest,
                    player_tracks_path=args.player_tracks,
                    ball_tracks_path=args.ball_tracks,
                    output=output,
                    control_radius_heights=control_radius,
                    smoothing_seconds=smoothing,
                    minimum_transfer_heights=minimum_transfer,
                    minimum_pass_speed_pixels_per_second=45.0,
                    pass_flight_debounce_seconds=debounce,
                    pass_receiver_window_seconds=receiver_window,
                    maximum_transfer_seconds=maximum_transfer,
                    infer_shots=False,
                )
            predictions = json.loads(
                (output / "predicted-events.json").read_text(encoding="utf-8")
            )
            comparison = compare_manual_events(
                manual, predictions, tolerance_seconds=1.0
            )
            pass_matches = sum(
                match["manual"]["event_type"] == "completed_pass"
                for match in comparison["matches"]
            )
            turnover_matches = sum(
                match["manual"]["event_type"] == "turnover"
                for match in comparison["matches"]
            )
            results.append(
                {
                    "parameters": {
                        "control_radius_heights": control_radius,
                        "smoothing_seconds": smoothing,
                        "minimum_transfer_heights": minimum_transfer,
                        "minimum_pass_speed_pixels_per_second": 45.0,
                        "pass_flight_debounce_seconds": debounce,
                        "pass_receiver_window_seconds": receiver_window,
                        "maximum_transfer_seconds": maximum_transfer,
                    },
                    "pass_matches": pass_matches,
                    "turnover_matches": turnover_matches,
                    "total_matches": comparison["matched_event_count"],
                    "predicted_events": comparison["predicted_event_count"],
                }
            )
    ranked = sorted(
        results,
        key=lambda item: (
            item["total_matches"],
            item["pass_matches"],
            -abs(item["predicted_events"] - len(manual)),
        ),
        reverse=True,
    )
    args.output.write_text(
        json.dumps(
            {
                "configuration_count": len(results),
                "scoring_tolerance_seconds": 1.0,
                "top_results": ranked[:20],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"Evaluated {len(results)} configurations. "
        f"Best matched {ranked[0]['total_matches']}/{len(manual)} events."
    )


if __name__ == "__main__":
    main()
