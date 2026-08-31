from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from football_poc.alfheim_profile import ALFHEIM_POSSESSION_ARGUMENTS
from football_poc.demo import prepare_demo_video


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build cached player tracking and events for an Alfheim segment."
    )
    parser.add_argument("segment", type=Path)
    args = parser.parse_args()
    segment = args.segment.resolve()
    manifest = segment / "manifest.json"
    labels = segment / "ball-ground-truth.csv"
    cache = segment / "analytics-cache"
    results = segment / "analytics-data"
    ball_tracks = segment / "ground-truth-ball-tracks.json"
    boundary_events = segment / "boundary-events.json"
    status_path = segment / "analysis-status.json"
    workspace = Path.cwd().resolve()

    def status(stage: str, message: str) -> None:
        status_path.write_text(
            json.dumps({"stage": stage, "message": message}, indent=2),
            encoding="utf-8",
        )

    def run(*arguments: str) -> None:
        subprocess.run(
            [sys.executable, *arguments],
            cwd=workspace,
            check=True,
        )

    try:
        status("detecting", "Detecting players on every fifth video frame.")
        run(
            "-m",
            "football_poc.benchmark_cli",
            str(manifest),
            "--output",
            str(cache),
            "--model",
            r".\yolo11n.pt",
            "--confidence",
            "0.12",
            "--image-size",
            "960",
            "--stride",
            "5",
            "--tile-width",
            "1484",
            "--overlap",
            "0.1",
        )
        status("ball_track", "Converting supplied ball labels.")
        run(
            str(workspace / "scripts" / "build-alfheim-ball-track.py"),
            "--manifest",
            str(manifest),
            "--ground-truth",
            str(labels),
            "--output",
            str(ball_tracks),
            "--stride",
            "5",
        )
        status("boundary", "Applying the saved camera pitch calibration.")
        run(
            str(workspace / "scripts" / "analyze-alfheim-boundary.py"),
            "--ground-truth",
            str(labels),
            "--calibration",
            str(
                workspace
                / "benchmarks"
                / "alfheim"
                / "window-555"
                / "pitch-calibration.json"
            ),
            "--output",
            str(boundary_events),
        )
        status("tracking", "Associating players and classifying teams.")
        run(
            "-m",
            "football_poc.player_tracking_cli",
            str(manifest),
            "--player-cache",
            str(cache / "detections.jsonl"),
            "--ball-tracks",
            str(ball_tracks),
            "--output",
            str(results),
            "--confidence",
            "0.2",
            "--max-gap",
            "0.5",
            "--max-speed",
            "700",
            "--minimum-track-points",
            "3",
            "--team-profile",
            "red-black",
            "--goalkeeper-affiliations",
            str(
                workspace
                / "benchmarks"
                / "alfheim"
                / "window-555"
                / "goalkeeper-affiliations.json"
            ),
        )
        status("events", "Inferring possession, passes, and turnovers.")
        run(
            "-m",
            "football_poc.possession_cli",
            str(manifest),
            "--player-tracks",
            str(results / "player-tracks.json"),
            "--ball-tracks",
            str(ball_tracks),
            "--output",
            str(results),
            *ALFHEIM_POSSESSION_ARGUMENTS,
            "--boundary-events",
            str(boundary_events),
        )
        status("publishing", "Preparing browser tracking video and live chunks.")
        run(
            "-m",
            "football_poc.chunk_simulator_cli",
            str(manifest),
            "--events",
            str(results / "predicted-events.json"),
            "--output",
            str(results / "chunk-simulation.json"),
        )
        prepare_demo_video(
            source=results / "tracking-verification.mp4",
            output=results / "tracking-verification.webm",
        )
        status("ready", "AI tracking and event counters are ready.")
    except Exception as error:
        status("failed", str(error))
        raise


if __name__ == "__main__":
    main()
