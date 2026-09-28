from __future__ import annotations

from football_poc.engine.common import *

def infer_shot_events(
    balls: dict[int, list[dict[str, Any]]],
    possession_segments: Iterable[PossessionSegment],
    *,
    width: int,
    height: int,
    minimum_speed_pixels_per_second: float,
    minimum_goal_cosine: float,
    maximum_step_seconds: float = 0.8,
    debounce_seconds: float = 2.0,
    receiver_window_seconds: float = 0.8,
    prior_events: Iterable[PredictedEvent] = (),
) -> list[PredictedEvent]:
    tracks: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame_points in balls.values():
        for point in frame_points:
            tracks[int(point["track_id"])].append(point)

    goal_centers = {
        "left": (width * 0.18, height * 0.27),
        "right": (width * 0.95, height * 0.27),
    }
    candidates: list[tuple[float, float, str]] = []
    for points in tracks.values():
        ordered = sorted(
            (
                point
                for point in points
                if not point.get("interpolated", False)
            ),
            key=lambda point: float(point["clip_seconds"]),
        )
        for first, second in zip(ordered, ordered[1:]):
            elapsed = float(second["clip_seconds"]) - float(first["clip_seconds"])
            if elapsed <= 0 or elapsed > maximum_step_seconds:
                continue
            start_x = float(first["x"])
            start_y = float(first["y"])
            movement_x = float(second["x"]) - start_x
            movement_y = float(second["y"]) - start_y
            movement = hypot(movement_x, movement_y)
            speed = movement / elapsed
            if speed < minimum_speed_pixels_per_second:
                continue
            if start_x >= width * 0.6:
                goal_side = "right"
            elif start_x <= width * 0.4:
                goal_side = "left"
            else:
                continue
            goal_x, goal_y = goal_centers[goal_side]
            goal_x -= start_x
            goal_y -= start_y
            goal_distance = hypot(goal_x, goal_y)
            cosine = (
                (movement_x * goal_x + movement_y * goal_y)
                / (movement * goal_distance)
                if movement > 0 and goal_distance > 0
                else -1.0
            )
            if cosine < minimum_goal_cosine:
                continue
            candidates.append(
                (
                    (float(first["clip_seconds"]) + float(second["clip_seconds"]))
                    / 2,
                    speed,
                    goal_side,
                )
            )

    grouped_candidates: list[tuple[float, float, str]] = []
    for candidate in sorted(candidates):
        if (
            grouped_candidates
            and candidate[0] - grouped_candidates[-1][0] < debounce_seconds
        ):
            if candidate[1] > grouped_candidates[-1][1]:
                grouped_candidates[-1] = candidate
            continue
        grouped_candidates.append(candidate)

    events: list[PredictedEvent] = []
    segments = list(possession_segments)
    confirmed_events = list(prior_events)
    for timestamp, speed, goal_side in grouped_candidates:
        if any(
            0 <= segment.start_seconds - timestamp <= receiver_window_seconds
            and sum(
                not observation.ball_interpolated
                for observation in segment.observations
            )
            >= 2
            for segment in segments
        ):
            continue
        prior = [
            segment
            for segment in segments
            if segment.end_seconds <= timestamp
            and timestamp - segment.end_seconds <= 3.0
        ]
        owner = max(prior, key=lambda segment: segment.end_seconds) if prior else None
        confirmed_prior = [
            event
            for event in confirmed_events
            if event.team in {"blue", "white"}
            and event.clip_seconds <= timestamp
            and timestamp - event.clip_seconds <= 3.0
        ]
        confirmed_owner = (
            max(confirmed_prior, key=lambda event: event.clip_seconds)
            if confirmed_prior
            else None
        )
        team = confirmed_owner.team if confirmed_owner else owner.team if owner else None
        player_track_id = (
            (
                confirmed_owner.to_player_track_id
                or confirmed_owner.from_player_track_id
            )
            if confirmed_owner
            else owner.player_track_id if owner else None
        )
        events.append(
            PredictedEvent(
                event_type="shot_candidate",
                clip_seconds=round(timestamp, 3),
                team=team,
                from_player_track_id=player_track_id,
                to_player_track_id=None,
                confidence=round(
                    min(0.95, 0.45 + speed / 1200),
                    4,
                ),
                details=(
                    f"Ball speed {speed:.2f} pixels/second toward {goal_side} goal."
                ),
            )
        )
    return events

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



def run(results_dir: Path, settings: ShotSettings = ShotSettings()) -> dict[str, Any]:
    events = read_stage_json(results_dir / "predicted-events.json")
    shots = [
        event for event in events
        if any(str(event.get("event_type", "")).startswith(prefix) for prefix in settings.prefixes)
    ]
    return {"stage": "shot", "count": len(shots), "events": shots}
