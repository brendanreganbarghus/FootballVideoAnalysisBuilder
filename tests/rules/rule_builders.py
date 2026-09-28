"""Small evidence-window builders for timestamped rule unit tests.

Expected values in rule tests are assertions only; they never feed inference.
"""

from __future__ import annotations

from football_poc.possession import (
    PossessionObservation,
    build_possession_segments,
    infer_transfer_events,
)


def observation(
    seconds: float,
    team: str,
    player_id: int,
    player_x: float,
    ball_x: float,
    control_ratio: float = 0.5,
    *,
    player_y: float = 100,
    ball_y: float = 100,
    player_height: float = 50,
) -> PossessionObservation:
    return PossessionObservation(
        source_frame=round(seconds * 25),
        clip_seconds=seconds,
        team=team,
        player_track_id=player_id,
        player_x=player_x,
        player_y=player_y,
        player_height=player_height,
        ball_x=ball_x,
        ball_y=ball_y,
        control_ratio=control_ratio,
    )


def transfer_events(
    observations: list[PossessionObservation],
    *,
    segment_gap_seconds: float = 0.5,
    identity_switch_radius_heights: float = 0.75,
    maximum_transfer_seconds: float = 3,
    minimum_transfer_heights: float = 1.5,
):
    segments = build_possession_segments(
        observations,
        segment_gap_seconds=segment_gap_seconds,
        identity_switch_radius_heights=identity_switch_radius_heights,
    )
    return infer_transfer_events(
        segments,
        maximum_transfer_seconds=maximum_transfer_seconds,
        minimum_transfer_heights=minimum_transfer_heights,
    )
