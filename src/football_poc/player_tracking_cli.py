from __future__ import annotations

import argparse
from pathlib import Path

from football_poc.player_tracking import track_cached_players


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track and classify players from cached SoccerTrack detections."
    )
    parser.add_argument(
        "manifest",
        type=Path,
        nargs="?",
        default=Path("benchmarks/soccertrack-117093-window.json"),
    )
    parser.add_argument(
        "--player-cache",
        type=Path,
        default=Path("benchmarks/soccertrack-117093-yolo/detections.jsonl"),
    )
    parser.add_argument(
        "--ball-tracks",
        type=Path,
        default=Path(
            "benchmarks/soccertrack-117093-football-model/ball-tracks.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/soccertrack-117093-fused"),
    )
    parser.add_argument("--confidence", type=float, default=0.3)
    parser.add_argument("--max-gap", type=float, default=0.4)
    parser.add_argument("--max-speed", type=float, default=500.0)
    parser.add_argument("--minimum-track-points", type=int, default=8)
    parser.add_argument(
        "--team-profile",
        choices=("auto", "blue-white", "red-black"),
        default="auto",
    )
    parser.add_argument("--goalkeeper-affiliations", type=Path, default=None)
    parser.add_argument(
        "--team-colors",
        type=Path,
        default=None,
        help="Optional BGR reference colors for K-Means jersey classification.",
    )
    parser.add_argument("--no-video", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    track_cached_players(
        manifest_path=args.manifest,
        player_cache_path=args.player_cache,
        ball_tracks_path=args.ball_tracks,
        output=args.output,
        confidence=args.confidence,
        max_gap_seconds=args.max_gap,
        max_speed_pixels_per_second=args.max_speed,
        minimum_track_points=args.minimum_track_points,
        render_video=not args.no_video,
        team_profile=args.team_profile,
        goalkeeper_affiliations_path=args.goalkeeper_affiliations,
        team_color_references_path=args.team_colors,
    )


if __name__ == "__main__":
    main()
