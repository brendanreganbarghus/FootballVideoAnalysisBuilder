from __future__ import annotations

import argparse
from pathlib import Path

from football_poc.demo import build_demo, prepare_demo_video


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the self-contained football analytics team demo."
    )
    parser.add_argument(
        "--aggregate",
        type=Path,
        default=Path("benchmarks/soccertrack-117093-aggregate.json"),
    )
    parser.add_argument(
        "--evaluation",
        type=Path,
        default=Path(
            "benchmarks/soccertrack-117093-fused/event-evaluation.json"
        ),
    )
    parser.add_argument(
        "--simulation",
        type=Path,
        default=Path(
            "benchmarks/soccertrack-117093-fused/chunk-simulation.json"
        ),
    )
    parser.add_argument(
        "--events",
        type=Path,
        default=Path(
            "benchmarks/soccertrack-117093-fused/predicted-events.json"
        ),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("demo/index.html")
    )
    parser.add_argument(
        "--video-source",
        type=Path,
        default=Path(
            "benchmarks/soccertrack-117093-fused/tracking-verification.mp4"
        ),
    )
    parser.add_argument(
        "--video-output",
        type=Path,
        default=Path("demo/tracking-verification.webm"),
    )
    parser.add_argument(
        "--clip-title",
        default="Primary benchmark minute - match 21:07.0-22:07.0",
    )
    parser.add_argument("--team-a", default="blue")
    parser.add_argument("--team-b", default="white")
    parser.add_argument("--unlabelled-actions", action="store_true")
    parser.add_argument("--ground-truth-ball", action="store_true")
    parser.add_argument("--manual-comparison", type=Path, default=None)
    parser.add_argument("--manual-review-image-url", default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    video = prepare_demo_video(
        source=args.video_source,
        output=args.video_output,
    )
    output = build_demo(
        aggregate_path=args.aggregate,
        evaluation_path=args.evaluation,
        simulation_path=args.simulation,
        events_path=args.events,
        output=args.output,
        video_url=video.name,
        clip_title=args.clip_title,
        teams=(args.team_a, args.team_b),
        labelled_actions=not args.unlabelled_actions,
        ground_truth_ball=args.ground_truth_ball,
        manual_comparison_path=args.manual_comparison,
        manual_review_image_url=args.manual_review_image_url,
    )
    print(f"Browser-compatible video written to {video.resolve()}")
    print(f"Demo written to {output.resolve()}")


if __name__ == "__main__":
    main()
