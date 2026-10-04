from __future__ import annotations

from .settings import *  # noqa: F401,F403


TIME_MACHINE_MODULE = "02_time_machine"


def _nearest_confirmed_entries(
    ledger: FrameLedger,
    frame: int,
    *,
    anchors: tuple[FrameLedgerEntry, ...] | None = None,
) -> tuple[FrameLedgerEntry | None, FrameLedgerEntry | None]:
    confirmed = sorted(
        anchors if anchors is not None else ledger.confirmed_entries(),
        key=lambda entry: entry.source_frame,
    )
    previous = next(
        (entry for entry in reversed(confirmed) if entry.source_frame < frame),
        None,
    )
    following = next(
        (entry for entry in confirmed if entry.source_frame > frame),
        None,
    )
    return previous, following


def _uncertainty_radius(
    *,
    bounded: bool,
    elapsed_seconds: float,
    frame_step: int,
    fps: float,
    box_diagonal: float,
    width: int,
    height: int,
    max_speed_pixels_per_second: float,
) -> float:
    """Radius around an estimate within which the ball can physically be."""
    diameter = max(1.0, box_diagonal)
    if bounded:
        steps = elapsed_seconds / (frame_step / fps)
        return round(diameter * (1 + steps), 3)
    reachable = max_speed_pixels_per_second * elapsed_seconds
    return round(min(max(diameter, reachable), hypot(width, height) / 2), 3)


def _confirm_time_machine_estimates(
    ledger: FrameLedger,
    *,
    fps: float,
    frame_step: int,
    width: int,
    height: int,
    max_speed_pixels_per_second: float,
    max_interpolation_seconds: float = 1.2,
    max_one_sided_seconds: float | None = None,
    place_possible_regions: bool = True,
) -> FrameLedger:
    if max_one_sided_seconds is None:
        max_one_sided_seconds = max(0.1, 2 * frame_step / fps)
    anchors = ledger.confirmed_entries()
    for frame in ledger.unresolved_frames():
        previous, following = _nearest_confirmed_entries(
            ledger,
            frame,
            anchors=anchors,
        )
        if previous is not None and following is not None:
            gap_seconds = (following.source_frame - previous.source_frame) / fps
            bounded = gap_seconds <= max_interpolation_seconds
            if not bounded and not place_possible_regions:
                ledger.reject(frame, TIME_MACHINE_MODULE, "gap_too_long_to_estimate")
                continue
            alpha = (
                (frame - previous.source_frame)
                / (following.source_frame - previous.source_frame)
            )
            x = float(previous.x) + (float(following.x) - float(previous.x)) * alpha
            y = float(previous.y) + (float(following.y) - float(previous.y)) * alpha
            elapsed = min(
                frame - previous.source_frame,
                following.source_frame - frame,
            ) / fps
            ledger.confirm(
                frame,
                x=min(width - 1.0, max(0.0, x)),
                y=min(height - 1.0, max(0.0, y)),
                confirming_module=TIME_MACHINE_MODULE,
                evidence={
                    "mode": (
                        "bounded_interpolation"
                        if bounded
                        else "possible_region_interpolation"
                    ),
                    "previous_frame": previous.source_frame,
                    "following_frame": following.source_frame,
                    "gap_seconds": round(gap_seconds, 3),
                    "uncertainty_radius_pixels": _uncertainty_radius(
                        bounded=bounded,
                        elapsed_seconds=elapsed,
                        frame_step=frame_step,
                        fps=fps,
                        box_diagonal=float(previous.box_diagonal or 0.0),
                        width=width,
                        height=height,
                        max_speed_pixels_per_second=max_speed_pixels_per_second,
                    ),
                },
                confidence=min(
                    0.49,
                    float(previous.confidence or 0.0)
                    * float(following.confidence or 0.0)
                    ** 0.5
                    * (0.8 ** max(1.0, elapsed / (frame_step / fps))),
                ),
                clip_seconds=frame / fps,
                box_diagonal=max(1.0, float(previous.box_diagonal or 0.0)),
                point_evidence=(
                    "trajectory_estimated_bidirectional"
                    if bounded
                    else "trajectory_estimated_possible_region"
                ),
                point_source_attribution="interpolated",
            )
            continue

        anchor = previous or following
        if not place_possible_regions and (
            anchor is None
            or abs(frame - anchor.source_frame) / fps > max_one_sided_seconds
        ):
            ledger.reject(frame, TIME_MACHINE_MODULE, "gap_too_long_to_estimate")
            continue
        if anchor is None:
            # No visual evidence anywhere in the segment: the ball could be
            # anywhere in the frame.
            ledger.confirm(
                frame,
                x=(width - 1.0) / 2,
                y=(height - 1.0) / 2,
                confirming_module=TIME_MACHINE_MODULE,
                evidence={
                    "mode": "possible_region_without_anchor",
                    "uncertainty_radius_pixels": round(hypot(width, height) / 2, 3),
                },
                confidence=0.0,
                clip_seconds=frame / fps,
                box_diagonal=1.0,
                point_evidence="trajectory_estimated_possible_region",
                point_source_attribution="interpolated",
            )
            continue
        elapsed = abs(frame - anchor.source_frame) / fps
        bounded = elapsed <= max_one_sided_seconds
        ledger.confirm(
            frame,
            x=float(anchor.x),
            y=float(anchor.y),
            confirming_module=TIME_MACHINE_MODULE,
            evidence={
                "mode": (
                    "bounded_one_sided_hold"
                    if bounded
                    else "possible_region_one_sided_hold"
                ),
                "anchor_frame": anchor.source_frame,
                "elapsed_seconds": round(elapsed, 3),
                "uncertainty_radius_pixels": _uncertainty_radius(
                    bounded=bounded,
                    elapsed_seconds=elapsed,
                    frame_step=frame_step,
                    fps=fps,
                    box_diagonal=float(anchor.box_diagonal or 0.0),
                    width=width,
                    height=height,
                    max_speed_pixels_per_second=max_speed_pixels_per_second,
                ),
            },
            confidence=min(0.35, float(anchor.confidence or 0.0) * 0.5),
            clip_seconds=frame / fps,
            box_diagonal=max(1.0, float(anchor.box_diagonal or 0.0)),
            point_evidence=(
                "trajectory_estimated_possible_region"
                if not bounded
                else "trajectory_estimated_forward"
                if previous is not None
                else "trajectory_estimated_backward"
            ),
            point_source_attribution="interpolated",
        )
    return ledger
