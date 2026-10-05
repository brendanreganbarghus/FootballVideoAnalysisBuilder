from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from math import hypot
from pathlib import Path
from typing import Any, Iterable

import cv2

from football_poc.benchmark import BenchmarkManifest
from football_poc.match_state import (
    MatchStateTimeline,
    build_match_state_timeline,
    coalesce_stoppage_candidates,
    detect_stationary_ball_restarts,
    partition_continuous_flight_candidates,
    partition_fragmented_boundary_candidates,
)
from football_poc.player_tracking import (
    classify_color_scores,
)
from football_poc.image_space import ball_coordinate_size, scale_factors, video_size
from football_poc.pitch_geometry import (
    detect_boundary_intervals,
    load_pitch_boundary,
    signed_pitch_distance,
)

LEGACY_NAMESPACES = frozenset({"innovation", "live"})


def scaled_pitch_boundary(
    calibration_path: Path, ball_tracks_path: Path, video: Path
) -> tuple[tuple[float, float], ...]:
    """Calibrated pitch boundary in the image space of the runtime positions."""
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    ball_payload = json.loads(ball_tracks_path.read_text(encoding="utf-8"))
    sx, sy = scale_factors(
        calibration, ball_coordinate_size(ball_payload, video_size(video))
    )
    return tuple(
        (x * sx, y * sy) for x, y in load_pitch_boundary(calibration_path)
    )


def runtime_ball_boundary_intervals(
    balls: dict[int, list[dict[str, Any]]],
    boundary: Iterable[tuple[float, float]],
    *,
    outside_margin_px: float = 12.0,
    minimum_outside_seconds: float = 0.4,
) -> list[dict[str, Any]]:
    """Ball-out-of-pitch candidates from the runtime ball file (Law 9).

    Only frozen runtime inputs are used: the active ball coordinates and the
    calibrated pitch. An airborne ball can project outside the lines; the
    match-state guards decide whether a candidate is a real stoppage.
    """
    points = [
        {
            "frame": frame,
            "seconds": float(best["clip_seconds"]),
            "x": float(best["x"]),
            "y": float(best["y"]),
        }
        for frame, frame_points in balls.items()
        if frame_points
        for best in [
            max(frame_points, key=lambda point: float(point.get("confidence", 0)))
        ]
    ]
    if not points:
        return []
    return [
        asdict(interval)
        for interval in detect_boundary_intervals(
            points,
            boundary=boundary,
            outside_margin_px=outside_margin_px,
            minimum_outside_seconds=minimum_outside_seconds,
        )
    ]


def exclude_players_outside_pitch(
    players: dict[int, list[dict[str, Any]]],
    boundary: Iterable[tuple[float, float]],
) -> dict[int, list[dict[str, Any]]]:
    """Keep only player boxes whose feet are inside the calibrated pitch.

    People beyond the calibrated lines (ball boys, staff, substitutes)
    take no part in play, so the event rules never see them. The ball
    itself is not filtered: an airborne ball may project outside.
    """
    polygon = tuple(boundary)
    return {
        frame: [
            player
            for player in frame_players
            if signed_pitch_distance(
                (
                    (float(player["x1"]) + float(player["x2"])) / 2,
                    float(player["y2"]),
                ),
                polygon,
            )
            >= 0
        ]
        for frame, frame_players in players.items()
    }


@dataclass(frozen=True)
class PossessionObservation:
    source_frame: int
    clip_seconds: float
    team: str
    player_track_id: int
    player_x: float
    player_y: float
    player_height: float
    ball_x: float
    ball_y: float
    control_ratio: float
    ball_interpolated: bool = False
    ball_evidence: str = "detector"
    ball_state: str = "observed"
    ball_uncertainty_radius_pixels: float | None = None
    ball_event_evidence_eligible: bool = True

@dataclass
class PossessionSegment:
    team: str
    player_track_id: int
    observations: list[PossessionObservation]

    @property
    def start_seconds(self) -> float:
        return self.observations[0].clip_seconds

    @property
    def end_seconds(self) -> float:
        return self.observations[-1].clip_seconds

@dataclass(frozen=True)
class PredictedEvent:
    event_type: str
    clip_seconds: float
    team: str | None
    from_player_track_id: int | None
    to_player_track_id: int | None
    confidence: float
    details: str
    completion_seconds: float | None = None

from dataclasses import dataclass


@dataclass(frozen=True)
class BallEvidenceSettings:
    include_summary: bool = True


@dataclass(frozen=True)
class BallControlSettings:
    control_radius_heights: float = 1.2
    maximum_flyby_speed_pixels_per_second: float | None = None
    maximum_flyby_speed_heights_per_second: float | None = None
    minimum_flyby_direction_cosine: float = 0.85
    maximum_ground_contact_height_ratio: float | None = None
    maximum_aerial_contact_direction_cosine: float = 0.5
    future_control_confirmation_seconds: float = 0.0
    sample_limit: int = 8


@dataclass(frozen=True)
class PossessionLedgerSettings:
    smoothing_seconds: float = 0.24
    segment_gap_seconds: float = 0.64
    identity_switch_radius_heights: float = 0.75
    co_visible_track_return_seconds: float = 0.0
    minimum_segment_observations: int = 2
    transient_opponent_max_seconds: float = 1.2
    occluded_owner_max_seconds: float | None = None
    occluded_owner_max_speed_heights_per_second: float = 3.0
    occluded_owner_min_direction_cosine: float | None = None
    include_segments: bool = True


@dataclass(frozen=True)
class CompletedPassSettings:
    maximum_transfer_seconds: float = 3.0
    minimum_transfer_heights: float = 1.5
    minimum_pass_speed_pixels_per_second: float = 60.0
    maximum_pass_step_seconds: float = 0.24
    pass_flight_debounce_seconds: float = 1.2
    pass_sender_lookback_seconds: float = 1.0
    pass_receiver_window_seconds: float = 2.0
    transfer_deduplication_seconds: float = 0.8
    startup_guard_seconds: float = 4.0
    startup_receiver_control_radius_heights: float = 1.2
    event_type: str = "pass_candidate"


@dataclass(frozen=True)
class TurnoverSettings:
    turnover_smoothing_seconds: float | None = None
    turnover_control_radius_heights: float | None = None
    maximum_transfer_seconds: float = 3.0
    minimum_transfer_heights: float = 1.5
    transfer_deduplication_seconds: float = 0.8
    event_type: str = "turnover_candidate"


@dataclass(frozen=True)
class ShotSettings:
    minimum_shot_speed_pixels_per_second: float = 200.0
    minimum_shot_goal_cosine: float = 0.92
    infer_shots: bool = True
    prefixes: tuple[str, ...] = ("shot",)


@dataclass(frozen=True)
class MatchStateExportSettings:
    minimum_restart_speed_pixels_per_second: float = 200.0
    boundary_ownership_lookback_seconds: float = 2.0
    include_events: bool = True


def read_stage_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
