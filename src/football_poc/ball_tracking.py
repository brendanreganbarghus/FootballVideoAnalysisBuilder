from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from math import hypot
from pathlib import Path
from typing import Any, Iterable

import cv2

from football_poc.benchmark import BenchmarkManifest


@dataclass(frozen=True)
class BallPoint:
    source_frame: int
    clip_seconds: float
    confidence: float
    x: float
    y: float
    interpolated: bool = False


@dataclass
class BallTrack:
    track_id: int
    points: list[BallPoint]

    @property
    def last(self) -> BallPoint:
        return self.points[-1]

    def predicted_center(self, clip_seconds: float) -> tuple[float, float]:
        if len(self.points) < 2:
            return self.last.x, self.last.y
        previous, current = self.points[-2:]
        elapsed = current.clip_seconds - previous.clip_seconds
        if elapsed <= 0:
            return current.x, current.y
        future = clip_seconds - current.clip_seconds
        return (
            current.x + (current.x - previous.x) / elapsed * future,
            current.y + (current.y - previous.y) / elapsed * future,
        )


def track_cached_balls(
    *,
    manifest_path: Path,
    cache_path: Path,
    output: Path,
    static_cell_size: int = 20,
    static_occupancy: float = 0.25,
    max_gap_seconds: float = 0.56,
    max_speed_pixels_per_second: float = 1600.0,
    minimum_track_points: int = 3,
    event_tolerance_seconds: float = 0.32,
) -> Path:
    manifest = BenchmarkManifest.load(manifest_path)
    metadata, records = _load_cache(cache_path, manifest.sha256)
    _validate_options(
        static_cell_size=static_cell_size,
        static_occupancy=static_occupancy,
        max_gap_seconds=max_gap_seconds,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        minimum_track_points=minimum_track_points,
        event_tolerance_seconds=event_tolerance_seconds,
    )
    width, height = _video_dimensions(manifest.video)
    candidates = [
        point
        for record in records
        for point in _ball_points(record)
        if _inside_soccertrack_pitch(point, width, height)
    ]
    static_cells = _static_cells(
        candidates,
        frame_count=len(records),
        cell_size=static_cell_size,
        occupancy=static_occupancy,
    )
    filtered = [
        point
        for point in candidates
        if not _near_static_cell(point, static_cells, static_cell_size)
    ]
    tracks = _associate_tracks(
        filtered,
        max_gap_seconds=max_gap_seconds,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    accepted = tuple(
        track for track in tracks if len(track.points) >= minimum_track_points
    )
    frame_step = int(metadata["stride"])
    accepted = tuple(
        interpolate_track_gaps(
            track,
            frame_step=frame_step,
            fps=manifest.fps,
            maximum_gap_seconds=max_gap_seconds,
        )
        for track in accepted
    )

    output.mkdir(parents=True, exist_ok=True)
    track_path = output / "ball-tracks.json"
    track_path.write_text(
        json.dumps(
            {
                "manifest": str(manifest.path),
                "cache": str(cache_path.resolve()),
                "cache_configuration": metadata,
                "static_cells": [
                    {"x": x * static_cell_size, "y": y * static_cell_size}
                    for x, y in sorted(static_cells)
                ],
                "tracks": [
                    {
                        "track_id": track.track_id,
                        "points": [asdict(point) for point in track.points],
                    }
                    for track in accepted
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_summary(
        output=output,
        manifest=manifest,
        records=records,
        raw_candidates=candidates,
        filtered_candidates=filtered,
        tracks=accepted,
        event_tolerance_seconds=event_tolerance_seconds,
    )
    print(f"Ball tracks written to {track_path.resolve()}")
    return track_path


def _associate_tracks(
    points: Iterable[BallPoint],
    *,
    max_gap_seconds: float,
    max_speed_pixels_per_second: float,
) -> tuple[BallTrack, ...]:
    by_frame: dict[int, list[BallPoint]] = {}
    for point in points:
        by_frame.setdefault(point.source_frame, []).append(point)

    tracks: list[BallTrack] = []
    next_track_id = 1
    for frame_points in by_frame.values():
        timestamp = frame_points[0].clip_seconds
        active = [
            track
            for track in tracks
            if timestamp - track.last.clip_seconds <= max_gap_seconds
        ]
        pairs: list[tuple[float, int, int]] = []
        for track_index, track in enumerate(active):
            predicted_x, predicted_y = track.predicted_center(timestamp)
            elapsed = timestamp - track.last.clip_seconds
            max_distance = max(35.0, max_speed_pixels_per_second * elapsed)
            for point_index, point in enumerate(frame_points):
                distance = hypot(point.x - predicted_x, point.y - predicted_y)
                if distance <= max_distance:
                    pairs.append((distance, track_index, point_index))

        assigned_tracks: set[int] = set()
        assigned_points: set[int] = set()
        for _, track_index, point_index in sorted(pairs):
            if track_index in assigned_tracks or point_index in assigned_points:
                continue
            active[track_index].points.append(frame_points[point_index])
            assigned_tracks.add(track_index)
            assigned_points.add(point_index)

        for point_index, point in enumerate(frame_points):
            if point_index not in assigned_points:
                tracks.append(BallTrack(next_track_id, [point]))
                next_track_id += 1
    return tuple(tracks)


def interpolate_track_gaps(
    track: BallTrack,
    *,
    frame_step: int,
    fps: float,
    maximum_gap_seconds: float,
) -> BallTrack:
    if frame_step < 1 or fps <= 0 or maximum_gap_seconds <= 0:
        raise ValueError("Interpolation frame step, FPS, and gap must be positive")
    ordered = sorted(track.points, key=lambda point: point.source_frame)
    if len(ordered) < 2:
        return BallTrack(track.track_id, ordered)
    points: list[BallPoint] = []
    for first, second in zip(ordered, ordered[1:]):
        points.append(first)
        frame_gap = second.source_frame - first.source_frame
        time_gap = second.clip_seconds - first.clip_seconds
        if frame_gap <= frame_step or time_gap > maximum_gap_seconds + 1e-6:
            continue
        for source_frame in range(
            first.source_frame + frame_step,
            second.source_frame,
            frame_step,
        ):
            alpha = (source_frame - first.source_frame) / frame_gap
            points.append(
                BallPoint(
                    source_frame=source_frame,
                    clip_seconds=round(
                        first.clip_seconds
                        + (source_frame - first.source_frame) / fps,
                        3,
                    ),
                    confidence=round(
                        min(first.confidence, second.confidence) * 0.75,
                        6,
                    ),
                    x=first.x + (second.x - first.x) * alpha,
                    y=first.y + (second.y - first.y) * alpha,
                    interpolated=True,
                )
            )
    points.append(ordered[-1])
    return BallTrack(track.track_id, sorted(points, key=lambda point: point.source_frame))


def _load_cache(
    cache_path: Path, expected_manifest_sha256: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not cache_path.is_file():
        raise FileNotFoundError(f"Detection cache does not exist: {cache_path}")
    lines = cache_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("Detection cache is empty")
    metadata = json.loads(lines[0])
    if metadata.get("manifest_sha256") != expected_manifest_sha256:
        raise ValueError("Detection cache was created for a different manifest")
    records = [json.loads(line) for line in lines[1:]]
    records = [record for record in records if record.get("type") == "frame"]
    if not records:
        raise ValueError("Detection cache contains no frames")
    records.sort(key=lambda record: int(record["source_frame"]))
    return metadata, records


def _ball_points(record: dict[str, Any]) -> list[BallPoint]:
    points: list[BallPoint] = []
    for detection in record.get("detections", []):
        if detection.get("class_name") != "sports ball":
            continue
        points.append(
            BallPoint(
                source_frame=int(record["source_frame"]),
                clip_seconds=float(record["clip_seconds"]),
                confidence=float(detection["confidence"]),
                x=(float(detection["x1"]) + float(detection["x2"])) / 2,
                y=(float(detection["y1"]) + float(detection["y2"])) / 2,
            )
        )
    return points


def _inside_soccertrack_pitch(
    point: BallPoint, width: int, height: int
) -> bool:
    normalized_x = abs(point.x - width / 2) / (width / 2)
    top = (150 + 150 * normalized_x**2) / 1080 * height
    bottom = (640 + 65 * (1 - normalized_x**2)) / 1080 * height
    return top <= point.y <= bottom


def _static_cells(
    points: Iterable[BallPoint],
    *,
    frame_count: int,
    cell_size: int,
    occupancy: float,
) -> frozenset[tuple[int, int]]:
    cells_by_frame: dict[tuple[int, int], set[int]] = {}
    for point in points:
        cells_by_frame.setdefault(_cell(point, cell_size), set()).add(
            point.source_frame
        )
    threshold = frame_count * occupancy
    return frozenset(
        cell
        for cell, frames in cells_by_frame.items()
        if len(frames) >= threshold
    )


def _cell(point: BallPoint, cell_size: int) -> tuple[int, int]:
    return round(point.x / cell_size), round(point.y / cell_size)


def _near_static_cell(
    point: BallPoint,
    static_cells: frozenset[tuple[int, int]],
    cell_size: int,
) -> bool:
    return any(
        hypot(point.x - cell_x * cell_size, point.y - cell_y * cell_size)
        <= cell_size
        for cell_x, cell_y in static_cells
    )


def _video_dimensions(video: Path) -> tuple[int, int]:
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        capture.release()
    if width <= 0 or height <= 0:
        raise ValueError("Benchmark video dimensions are invalid")
    return width, height


def _write_summary(
    *,
    output: Path,
    manifest: BenchmarkManifest,
    records: list[dict[str, Any]],
    raw_candidates: list[BallPoint],
    filtered_candidates: list[BallPoint],
    tracks: tuple[BallTrack, ...],
    event_tolerance_seconds: float,
) -> None:
    tracked_points = [point for track in tracks for point in track.points]
    interpolated_points = [
        point for point in tracked_points if point.interpolated
    ]
    tracked_frames = {point.source_frame for point in tracked_points}
    tracked_times = [point.clip_seconds for point in tracked_points]
    support: dict[str, dict[str, float | int]] = {}
    relevant_labels = {"pass", "high_pass", "shot"}
    for label in sorted(relevant_labels):
        events = [
            float(action["clip_seconds"])
            for action in manifest.actions
            if action.get("label") == label
        ]
        supported = sum(
            any(
                abs(event_time - tracked_time) <= event_tolerance_seconds
                for tracked_time in tracked_times
            )
            for event_time in events
        )
        support[label] = {
            "supported": supported,
            "ground_truth": len(events),
            "support_rate": round(supported / len(events), 4) if events else 0.0,
        }

    summary = {
        "processed_frames": len(records),
        "raw_pitch_ball_candidates": len(raw_candidates),
        "filtered_ball_candidates": len(filtered_candidates),
        "accepted_tracks": len(tracks),
        "accepted_track_points": len(tracked_points),
        "observed_track_points": len(tracked_points) - len(interpolated_points),
        "interpolated_track_points": len(interpolated_points),
        "tracked_frames": len(tracked_frames),
        "tracked_frame_coverage": round(len(tracked_frames) / len(records), 4),
        "event_tolerance_seconds": event_tolerance_seconds,
        "ground_truth_event_detection_support": support,
        "interpretation": (
            "Support means an accepted ball track has a detection near the "
            "ground-truth timestamp. It is not pass or shot accuracy."
        ),
    }
    (output / "ball-tracking-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


def _validate_options(
    *,
    static_cell_size: int,
    static_occupancy: float,
    max_gap_seconds: float,
    max_speed_pixels_per_second: float,
    minimum_track_points: int,
    event_tolerance_seconds: float,
) -> None:
    if static_cell_size < 1:
        raise ValueError("Static cell size must be at least 1")
    if not 0 < static_occupancy <= 1:
        raise ValueError("Static occupancy must be greater than 0 and at most 1")
    if max_gap_seconds <= 0 or max_speed_pixels_per_second <= 0:
        raise ValueError("Track gap and speed limits must be greater than zero")
    if minimum_track_points < 2:
        raise ValueError("Minimum track points must be at least 2")
    if event_tolerance_seconds < 0:
        raise ValueError("Event tolerance cannot be negative")
