from __future__ import annotations

import json
from collections import Counter, defaultdict
from math import floor, hypot
from pathlib import Path
from typing import Any

from football_poc.pitch_geometry import (
    PitchCalibration,
    load_metric_pitch_calibration,
    project_pitch_points,
)


def build_pilot_metrics(
    *,
    player_tracks_path: Path,
    possession_path: Path,
    events_path: Path,
    calibration_path: Path,
    output_path: Path,
    block_seconds: float = 60.0,
    heatmap_columns: int = 12,
    heatmap_rows: int = 8,
    maximum_track_gap_seconds: float = 1.0,
) -> Path:
    if block_seconds <= 0 or heatmap_columns < 1 or heatmap_rows < 1:
        raise ValueError("Block duration and heatmap dimensions must be positive")
    calibration = load_metric_pitch_calibration(calibration_path)
    tracks = _load_json(player_tracks_path)["tracks"]
    possession = _load_json(possession_path)["observations"]
    events = _load_json(events_path)
    if not isinstance(events, list):
        raise ValueError("Events input must be a JSON list")

    projected_tracks = _project_tracks(tracks, calibration)
    duration = max(
        [
            float(point["clip_seconds"])
            for track in projected_tracks
            for point in track["points"]
        ]
        + [float(item["clip_seconds"]) for item in possession]
        + [float(item["clip_seconds"]) for item in events]
        + [0.0]
    )
    block_count = max(1, floor(duration / block_seconds) + 1)
    blocks = [
        _summarize_block(
            index=index,
            start=index * block_seconds,
            end=(index + 1) * block_seconds,
            tracks=projected_tracks,
            possession=possession,
            events=events,
            calibration=calibration,
            heatmap_columns=heatmap_columns,
            heatmap_rows=heatmap_rows,
            maximum_track_gap_seconds=maximum_track_gap_seconds,
        )
        for index in range(block_count)
    ]
    payload = {
        "schema_version": 1,
        "status": "provisional_ai_statistics",
        "block_seconds": block_seconds,
        "pitch_dimensions_metres": {
            "length": calibration.length_metres,
            "width": calibration.width_metres,
        },
        "blocks": blocks,
        "limitations": [
            "Possession is the share of controlled observations, not every video frame.",
            "Distance and speed require a fixed calibrated camera and stable track IDs.",
            "Four-point homography assumes a planar view; stitched panoramas may need piecewise calibration.",
            "Events remain reviewable candidates until validated by an operator.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return output_path


def _project_tracks(
    tracks: list[dict[str, Any]], calibration: PitchCalibration
) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for track in tracks:
        points = sorted(track["points"], key=lambda item: item["clip_seconds"])
        feet = [
            ((float(point["x1"]) + float(point["x2"])) / 2, float(point["y2"]))
            for point in points
        ]
        pitch_points = project_pitch_points(feet, calibration)
        projected.append(
            {
                "track_id": int(track["track_id"]),
                "team": str(track.get("team", "unknown")),
                "points": [
                    {
                        "clip_seconds": float(point["clip_seconds"]),
                        "x_metres": pitch[0],
                        "y_metres": pitch[1],
                    }
                    for point, pitch in zip(points, pitch_points, strict=True)
                ],
            }
        )
    return projected


def _summarize_block(
    *,
    index: int,
    start: float,
    end: float,
    tracks: list[dict[str, Any]],
    possession: list[dict[str, Any]],
    events: list[dict[str, Any]],
    calibration: PitchCalibration,
    heatmap_columns: int,
    heatmap_rows: int,
    maximum_track_gap_seconds: float,
) -> dict[str, Any]:
    controlled = Counter(
        str(item["team"])
        for item in possession
        if start <= float(item["clip_seconds"]) < end
        and str(item.get("team", "unknown")) != "unknown"
    )
    controlled_total = sum(controlled.values())
    event_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for event in events:
        seconds = float(event.get("completion_seconds") or event["clip_seconds"])
        if start <= seconds < end and event.get("team"):
            event_counts[str(event["team"])][str(event["event_type"])] += 1

    team_heatmaps: dict[str, list[list[int]]] = {}
    player_metrics: list[dict[str, Any]] = []
    team_points: dict[str, list[dict[str, float]]] = defaultdict(list)
    for track in tracks:
        points = [
            point
            for point in track["points"]
            if start <= float(point["clip_seconds"]) < end
            and _inside_pitch(point, calibration)
        ]
        if not points:
            continue
        distance_metres = 0.0
        speeds: list[float] = []
        for first, second in zip(points, points[1:]):
            elapsed = second["clip_seconds"] - first["clip_seconds"]
            if elapsed <= 0 or elapsed > maximum_track_gap_seconds:
                continue
            travelled = hypot(
                second["x_metres"] - first["x_metres"],
                second["y_metres"] - first["y_metres"],
            )
            distance_metres += travelled
            speeds.append(travelled / elapsed)
        team = track["team"]
        team_points[team].extend(points)
        player_metrics.append(
            {
                "track_id": track["track_id"],
                "team": team,
                "distance_metres": round(distance_metres, 2),
                "maximum_speed_metres_per_second": round(max(speeds, default=0.0), 2),
                "sample_count": len(points),
            }
        )
    for team, points in team_points.items():
        grid = [[0 for _ in range(heatmap_columns)] for _ in range(heatmap_rows)]
        for point in points:
            column = min(
                heatmap_columns - 1,
                floor(point["x_metres"] / calibration.length_metres * heatmap_columns),
            )
            row = min(
                heatmap_rows - 1,
                floor(point["y_metres"] / calibration.width_metres * heatmap_rows),
            )
            grid[row][column] += 1
        team_heatmaps[team] = grid

    teams = sorted(set(controlled) | set(event_counts) | set(team_points))
    return {
        "index": index,
        "start_seconds": start,
        "end_seconds": end,
        "teams": {
            team: {
                "possession_percent": round(
                    100 * controlled[team] / controlled_total, 1
                )
                if controlled_total
                else 0.0,
                "controlled_samples": controlled[team],
                "pass_candidates": event_counts[team]["pass_candidate"],
                "turnovers_lost": event_counts[team]["turnover_candidate"],
                "heatmap": team_heatmaps.get(
                    team,
                    [[0 for _ in range(heatmap_columns)] for _ in range(heatmap_rows)],
                ),
            }
            for team in teams
        },
        "players": sorted(player_metrics, key=lambda item: item["track_id"]),
    }


def _inside_pitch(point: dict[str, float], calibration: PitchCalibration) -> bool:
    return (
        0 <= point["x_metres"] <= calibration.length_metres
        and 0 <= point["y_metres"] <= calibration.width_metres
    )


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Pilot metrics input does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
