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


def _speed_from_confirmed_neighbour(
    point: BallPoint,
    ledger: FrameLedger,
    *,
    fps: float,
    frame_step: int,
    neighbourhood_steps: int = 3,
) -> float:
    if fps <= 0 or frame_step < 1:
        return float("inf")
    entries = ledger.entries
    speeds = [
        hypot(entry.x - point.x, entry.y - point.y)
        / (abs(frame - point.source_frame) / fps)
        for offset in range(1, neighbourhood_steps + 1)
        for frame in (
            point.source_frame - offset * frame_step,
            point.source_frame + offset * frame_step,
        )
        if (entry := entries.get(frame)) is not None
        and entry.status == "confirmed"
        and entry.x is not None
        and entry.y is not None
    ]
    return min(speeds, default=float("inf"))


def _candidate_rejection_reason(
    point: BallPoint,
    *,
    record: dict[str, Any],
    candidates_by_frame: dict[int, list[_BallCandidate]],
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
    minimum_confidence: float,
    require_moving_neighbour: bool,
) -> tuple[str | None, bool]:
    if point.confidence < minimum_confidence:
        return "low_detector_confidence", False
    if _inside_player_upper_body(point, record):
        return "inside_player_upper_body", False
    static_reason = _same_position_static_reason(
        point,
        candidates_by_frame=candidates_by_frame,
        fps=fps,
    )
    if static_reason is not None:
        return static_reason, False
    near_feet = any(
        candidate.point == point and candidate.near_player_feet
        for candidate in candidates_by_frame.get(point.source_frame, [])
    )
    if near_feet:
        return None, True
    neighbours = candidates_by_frame
    if require_moving_neighbour:
        neighbours = {
            frame: [
                candidate
                for candidate in candidates
                if _same_position_static_reason(
                    candidate.point,
                    candidates_by_frame=candidates_by_frame,
                    fps=fps,
                )
                is None
            ]
            for frame, candidates in candidates_by_frame.items()
            if abs(frame - point.source_frame) <= 3 * frame_step
        }
    if not _detector_neighbour_support(
        point,
        candidates_by_frame=neighbours,
        fps=fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    ):
        return "no_neighbouring_motion_or_player_support", False
    return None, False


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
        selected = best_by_frame.get(frame)
        options: list[tuple[BallPoint, bool]] = []
        if selected is not None:
            options.append((selected, False))
        # The selected trajectory can follow a false positive; every other
        # detector candidate in an unresolved frame gets the same checks.
        for candidate in sorted(
            candidates_by_frame.get(frame, []),
            key=lambda item: (
                _speed_from_confirmed_neighbour(
                    item.point,
                    ledger,
                    fps=fps,
                    frame_step=frame_step,
                ),
                -item.point.confidence,
            ),
        ):
            if (
                candidate.point != selected
                and candidate.point.source_attribution == "yolo26_observed"
            ):
                options.append((candidate.point, True))
        if not options:
            ledger.reject(frame, CONFIRM_YOLO_MODULE, "no_yolo_candidate")
            continue
        record = records_by_frame.get(frame, {})
        rejection: str | None = None
        confirmed = False
        for point, alternative in options:
            reason, near_feet = _candidate_rejection_reason(
                point,
                record=record,
                candidates_by_frame=candidates_by_frame,
                fps=fps,
                frame_step=frame_step,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
                minimum_confidence=minimum_confidence,
                require_moving_neighbour=alternative,
            )
            if reason is not None:
                if rejection is None:
                    rejection = reason
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
                    "selected_trajectory_candidate": not alternative,
                },
                confidence=point.confidence,
                clip_seconds=point.clip_seconds,
                box_diagonal=point.box_diagonal,
                point_evidence=point.evidence,
                point_source_attribution=point.source_attribution,
                temporal_score=point.temporal_score,
            )
            confirmed = True
            break
        if not confirmed:
            ledger.reject(
                frame,
                CONFIRM_YOLO_MODULE,
                rejection or "no_yolo_candidate",
            )
    return ledger
