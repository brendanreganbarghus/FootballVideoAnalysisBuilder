from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from football_poc.innovation_day_snapshot.benchmark import BenchmarkManifest
from football_poc.innovation_day_snapshot.possession import (
    infer_cached_possession,
)
from football_poc.innovation_day_snapshot.shots_on_target import (
    apply_shots_on_target,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Infer possession transfers from fused SoccerTrack caches."
    )
    parser.add_argument(
        "manifest",
        type=Path,
        nargs="?",
        default=Path("benchmarks/soccertrack-117093-window.json"),
    )
    parser.add_argument(
        "--player-tracks",
        type=Path,
        default=Path(
            "benchmarks/soccertrack-117093-fused/player-tracks.json"
        ),
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
    parser.add_argument(
        "--no-shots",
        action="store_true",
        help="Disable shot inference when goal geometry is not calibrated.",
    )
    parser.add_argument(
        "--shots-on-target",
        action="store_true",
        help=(
            "Opt in to evidence-gated shots-on-target analytics. Requires a "
            "runtime --shot-evidence file; missing evidence yields an "
            "'unavailable' summary and no events."
        ),
    )
    parser.add_argument("--shot-evidence", type=Path, default=None)
    parser.add_argument("--control-radius-heights", type=float, default=1.2)
    parser.add_argument(
        "--identity-switch-radius-heights",
        type=float,
        default=0.75,
    )
    parser.add_argument(
        "--co-visible-track-return-seconds",
        type=float,
        default=0.0,
    )
    parser.add_argument("--smoothing-seconds", type=float, default=0.24)
    parser.add_argument("--minimum-transfer-heights", type=float, default=1.5)
    parser.add_argument("--minimum-pass-speed", type=float, default=60.0)
    parser.add_argument("--pass-debounce-seconds", type=float, default=1.2)
    parser.add_argument("--turnover-smoothing-seconds", type=float, default=None)
    parser.add_argument("--turnover-control-radius-heights", type=float, default=None)
    parser.add_argument("--pass-sender-lookback-seconds", type=float, default=1.0)
    parser.add_argument("--pass-receiver-window-seconds", type=float, default=2.0)
    parser.add_argument("--maximum-flyby-speed", type=float, default=None)
    parser.add_argument(
        "--maximum-flyby-speed-heights-per-second",
        type=float,
        default=None,
    )
    parser.add_argument(
        "--maximum-ground-contact-height-ratio",
        type=float,
        default=None,
    )
    parser.add_argument(
        "--maximum-aerial-contact-direction-cosine",
        type=float,
        default=0.5,
    )
    parser.add_argument(
        "--future-control-confirmation-seconds",
        type=float,
        default=0.0,
    )
    parser.add_argument("--minimum-flyby-direction-cosine", type=float, default=0.85)
    parser.add_argument("--boundary-events", type=Path, default=None)
    parser.add_argument("--initial-possession-team", default=None)
    parser.add_argument("--startup-guard-seconds", type=float, default=4.0)
    parser.add_argument(
        "--startup-receiver-control-radius-heights",
        type=float,
        default=1.2,
    )
    parser.add_argument(
        "--transient-opponent-max-seconds",
        type=float,
        default=1.2,
    )
    parser.add_argument("--occluded-owner-max-seconds", type=float, default=None)
    parser.add_argument(
        "--occluded-owner-max-speed-heights-per-second",
        type=float,
        default=3.0,
    )
    parser.add_argument(
        "--occluded-owner-min-direction-cosine",
        type=float,
        default=None,
    )
    parser.add_argument("--minimum-restart-speed", type=float, default=200.0)
    parser.add_argument(
        "--boundary-ownership-lookback-seconds",
        type=float,
        default=2.0,
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run(args)


def run(args: Any) -> Path:
    destination = _infer(args)
    if getattr(args, "shots_on_target", False):
        manifest = BenchmarkManifest.load(args.manifest)
        apply_shots_on_target(
            args.output,
            getattr(args, "shot_evidence", None),
            duration_seconds=manifest.source_frame_count / manifest.fps,
        )
    return destination


def _infer(args: Any) -> Path:
    return infer_cached_possession(
        manifest_path=args.manifest,
        player_tracks_path=args.player_tracks,
        ball_tracks_path=args.ball_tracks,
        output=args.output,
        infer_shots=not args.no_shots,
        control_radius_heights=args.control_radius_heights,
        identity_switch_radius_heights=args.identity_switch_radius_heights,
        co_visible_track_return_seconds=args.co_visible_track_return_seconds,
        smoothing_seconds=args.smoothing_seconds,
        minimum_transfer_heights=args.minimum_transfer_heights,
        minimum_pass_speed_pixels_per_second=args.minimum_pass_speed,
        pass_flight_debounce_seconds=args.pass_debounce_seconds,
        turnover_smoothing_seconds=args.turnover_smoothing_seconds,
        turnover_control_radius_heights=args.turnover_control_radius_heights,
        pass_sender_lookback_seconds=args.pass_sender_lookback_seconds,
        pass_receiver_window_seconds=args.pass_receiver_window_seconds,
        maximum_flyby_speed_pixels_per_second=args.maximum_flyby_speed,
        maximum_flyby_speed_heights_per_second=(
            args.maximum_flyby_speed_heights_per_second
        ),
        minimum_flyby_direction_cosine=args.minimum_flyby_direction_cosine,
        maximum_ground_contact_height_ratio=(
            args.maximum_ground_contact_height_ratio
        ),
        maximum_aerial_contact_direction_cosine=(
            args.maximum_aerial_contact_direction_cosine
        ),
        future_control_confirmation_seconds=(
            args.future_control_confirmation_seconds
        ),
        boundary_events_path=args.boundary_events,
        initial_possession_team=args.initial_possession_team,
        startup_guard_seconds=args.startup_guard_seconds,
        startup_receiver_control_radius_heights=(
            args.startup_receiver_control_radius_heights
        ),
        transient_opponent_max_seconds=args.transient_opponent_max_seconds,
        occluded_owner_max_seconds=args.occluded_owner_max_seconds,
        occluded_owner_max_speed_heights_per_second=(
            args.occluded_owner_max_speed_heights_per_second
        ),
        occluded_owner_min_direction_cosine=(
            args.occluded_owner_min_direction_cosine
        ),
        minimum_restart_speed_pixels_per_second=args.minimum_restart_speed,
        boundary_ownership_lookback_seconds=(
            args.boundary_ownership_lookback_seconds
        ),
    )


if __name__ == "__main__":
    main()
