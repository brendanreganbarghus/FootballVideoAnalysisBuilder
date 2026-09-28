from __future__ import annotations

from .settings import *  # noqa: F401,F403


CONFIRM_YOLO_MODULE = "01_confirm_yolo"


def _same_position_static_reason(
    point: BallPoint,
    *,
    candidates_by_frame: dict[int, list[_BallCandidate]],
    fps: float,
    radius_pixels: float = 6.0,
    minimum_points: int = 6,
    minimum_duration_seconds: float = 2.0,
) -> str | None:
    nearby: list[_BallCandidate] = []
    for candidates in candidates_by_frame.values():
        nearby.extend(
            candidate
            for candidate in candidates
            if hypot(candidate.point.x - point.x, candidate.point.y - point.y)
            <= radius_pixels
        )
    if len(nearby) < minimum_points:
        return None
    frames = [candidate.point.source_frame for candidate in nearby]
    duration = (max(frames) - min(frames)) / fps if fps > 0 else 0.0
    if duration >= minimum_duration_seconds:
        return "static_object_without_player_or_motion_support"
    return None


def _detector_neighbour_support(
    point: BallPoint,
    *,
    candidates_by_frame: dict[int, list[_BallCandidate]],
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
    neighbourhood_steps: int = 3,
) -> bool:
    if fps <= 0 or frame_step < 1:
        return False
    maximum_speed = max_speed_pixels_per_second * 1.25
    for offset in range(1, neighbourhood_steps + 1):
        for frame in (
            point.source_frame - offset * frame_step,
            point.source_frame + offset * frame_step,
        ):
            elapsed = abs(frame - point.source_frame) / fps
            if elapsed <= 0:
                continue
            for candidate in candidates_by_frame.get(frame, []):
                distance = hypot(
                    candidate.point.x - point.x,
                    candidate.point.y - point.y,
                )
                if distance / elapsed <= maximum_speed:
                    return True
    return False


def _confirm_yolo_detections(
    ledger: FrameLedger,
    detector_points: Iterable[BallPoint],
    *,
    candidates_by_frame: dict[int, list[_BallCandidate]],
    records_by_frame: dict[int, dict[str, Any]],
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
    minimum_confidence: float = 0.10,
) -> FrameLedger:
    best_by_frame: dict[int, BallPoint] = {}
    for point in detector_points:
        if point.source_attribution != "yolo26_observed":
            continue
        current = best_by_frame.get(point.source_frame)
        if current is None or point.confidence > current.confidence:
            best_by_frame[point.source_frame] = point

    for frame in ledger.unresolved_frames():
        point = best_by_frame.get(frame)
        if point is None:
            ledger.reject(frame, CONFIRM_YOLO_MODULE, "no_yolo_candidate")
            continue
        if point.confidence < minimum_confidence:
            ledger.reject(frame, CONFIRM_YOLO_MODULE, "low_detector_confidence")
            continue
        record = records_by_frame.get(frame, {})
        if _inside_player_upper_body(point, record):
            ledger.reject(frame, CONFIRM_YOLO_MODULE, "inside_player_upper_body")
            continue
        static_reason = _same_position_static_reason(
            point,
            candidates_by_frame=candidates_by_frame,
            fps=fps,
        )
        if static_reason is not None:
            ledger.reject(frame, CONFIRM_YOLO_MODULE, static_reason)
            continue
        same_frame_candidates = candidates_by_frame.get(frame, [])
        near_feet = any(
            candidate.point == point and candidate.near_player_feet
            for candidate in same_frame_candidates
        )
        if not near_feet and not _detector_neighbour_support(
            point,
            candidates_by_frame=candidates_by_frame,
            fps=fps,
            frame_step=frame_step,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        ):
            ledger.reject(
                frame,
                CONFIRM_YOLO_MODULE,
                "no_neighbouring_motion_or_player_support",
            )
            continue
        ledger.confirm(
            frame,
            x=point.x,
            y=point.y,
            confirming_module=CONFIRM_YOLO_MODULE,
            evidence={
                "detector_confidence": point.confidence,
                "near_player_feet": near_feet,
                "neighbour_motion_support": True,
            },
            confidence=point.confidence,
            clip_seconds=point.clip_seconds,
            box_diagonal=point.box_diagonal,
            point_evidence=point.evidence,
            point_source_attribution=point.source_attribution,
            temporal_score=point.temporal_score,
        )
    return ledger
