from __future__ import annotations

from .settings import *  # noqa: F401,F403


TIME_MACHINE_MODULE = "02_time_machine"

# A straight-line fill assumes the ball moved evenly across the gap. A ball
# held at a player's feet and then kicked does not: it sits near one gap end
# and then moves fast. When nothing ball-like is at the straight-line spot, the
# fill may move along the same line to the spot that best shows the ball
# colour learned from this video, provided that spot is not on a player's upper
# body and the speeds into and out of it match the ball's own speed just
# before and just after the gap.
KICK_TIMING_EMPTY_LINE_CONTRAST = 8.0
KICK_TIMING_SAMPLE_PIXELS = 2.0
KICK_TIMING_UPPER_BODY_FRACTION = 0.7
KICK_TIMING_SPEED_FACTOR = 1.5
KICK_TIMING_MINIMUM_SPEED_PIXELS_PER_FRAME = 2.0
KICK_TIMING_MINIMUM_MOVE_PIXELS = 3.0

# A detector sighting is a trusted gap end only when it starts a run of
# consecutive detector sightings leading away from the gap; a lone or paired
# sighting may be a wrong box. A gap between two trusted ends may be filled
# for longer than usual, because both ends pin the ball's real path.
DETECTOR_BACKED_RUN_LENGTH = 3
DETECTOR_BACKED_GAP_FACTOR = 2.0


def _detector_backed(
    confirmed_by_frame: Mapping[int, Any],
    frame: int,
    *,
    frame_step: int,
    direction: int,
) -> bool:
    if frame_step < 1:
        return False
    for step in range(DETECTOR_BACKED_RUN_LENGTH):
        entry = confirmed_by_frame.get(frame + direction * step * frame_step)
        if entry is None or entry.confirming_module not in {
            CONFIRM_YOLO_MODULE,
            LOCK_YOLO_CHAIN_MODULE,
        }:
            return False
    return True


def _kick_timing_position(
    frame: int,
    *,
    previous: FrameLedgerEntry,
    following: FrameLedgerEntry,
    anchors: list[FrameLedgerEntry],
    image: np.ndarray,
    colour_range: tuple[float, float],
    people: list[dict[str, Any]],
) -> tuple[float, float] | None:
    ax, ay = float(previous.x), float(previous.y)
    bx, by = float(following.x), float(following.y)
    alpha = (frame - previous.source_frame) / (
        following.source_frame - previous.source_frame
    )
    linear_x = ax + (bx - ax) * alpha
    linear_y = ay + (by - ay) * alpha
    diameter = max(1.0, float(previous.box_diagonal or 0.0))
    length = hypot(bx - ax, by - ay)
    steps = max(2, int(length / KICK_TIMING_SAMPLE_PIXELS))
    samples = [
        (ax + (bx - ax) * k / steps, ay + (by - ay) * k / steps)
        for k in range(steps + 1)
    ]
    nearest = min(samples, key=lambda p: hypot(p[0] - linear_x, p[1] - linear_y))
    linear_contrast = _grass_contrast(image, nearest[0], nearest[1], diameter)
    if linear_contrast is None or linear_contrast >= KICK_TIMING_EMPTY_LINE_CONTRAST:
        return None

    index = {entry.source_frame: i for i, entry in enumerate(anchors)}

    def speed(first: FrameLedgerEntry, second: FrameLedgerEntry) -> float:
        return hypot(
            float(second.x) - float(first.x), float(second.y) - float(first.y)
        ) / abs(second.source_frame - first.source_frame)

    i = index[previous.source_frame]
    j = index[following.source_frame]
    before = [
        speed(anchors[k - 1], anchors[k]) for k in (i, i - 1) if k - 1 >= 0
    ]
    # The slower of the last two steps: one wrong gap end cannot fake a fast
    # arrival.
    speed_before = min(before) if before else None
    speed_after = speed(following, anchors[j + 1]) if j + 1 < len(anchors) else None

    def allowed(observed: float, reference: float | None) -> bool:
        return reference is None or observed <= max(
            KICK_TIMING_SPEED_FACTOR * reference,
            KICK_TIMING_MINIMUM_SPEED_PIXELS_PER_FRAME,
        )

    def on_upper_body(x: float, y: float) -> bool:
        return any(
            float(person["x1"]) <= x <= float(person["x2"])
            and float(person["y1"])
            <= y
            <= float(person["y1"])
            + KICK_TIMING_UPPER_BODY_FRACTION
            * (float(person["y2"]) - float(person["y1"]))
            for person in people
        )

    colour_low, colour_high = colour_range
    best: tuple[float, float, float] | None = None
    for x, y in samples:
        chroma = _standout_chroma(image, x, y, diameter)
        if chroma is None or not colour_low <= chroma <= colour_high:
            continue
        contrast = _grass_contrast(image, x, y, diameter)
        if contrast is None or on_upper_body(x, y):
            continue
        arrival = hypot(x - ax, y - ay) / (frame - previous.source_frame)
        departure = hypot(bx - x, by - y) / (following.source_frame - frame)
        if not (allowed(arrival, speed_before) and allowed(departure, speed_after)):
            continue
        if best is None or contrast > best[2]:
            best = (x, y, contrast)
    if best is None:
        return None
    if hypot(best[0] - linear_x, best[1] - linear_y) < KICK_TIMING_MINIMUM_MOVE_PIXELS:
        return None
    return best[0], best[1]


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
    video: Path | None = None,
    colour_range: tuple[float, float] | None = None,
    records_by_frame: Mapping[int, dict[str, Any]] | None = None,
) -> FrameLedger:
    if max_one_sided_seconds is None:
        max_one_sided_seconds = max(0.1, 2 * frame_step / fps)
    anchors = ledger.confirmed_entries()
    sorted_anchors = sorted(anchors, key=lambda entry: entry.source_frame)
    anchors_by_frame = {entry.source_frame: entry for entry in anchors}

    def bounded_gap(previous: FrameLedgerEntry, following: FrameLedgerEntry) -> bool:
        gap_seconds = (following.source_frame - previous.source_frame) / fps
        if gap_seconds <= max_interpolation_seconds:
            return True
        return (
            gap_seconds <= DETECTOR_BACKED_GAP_FACTOR * max_interpolation_seconds
            and _detector_backed(
                anchors_by_frame, previous.source_frame,
                frame_step=frame_step, direction=-1,
            )
            and _detector_backed(
                anchors_by_frame, following.source_frame,
                frame_step=frame_step, direction=1,
            )
        )

    images: Mapping[int, np.ndarray] = {}
    if video is not None and colour_range is not None:
        gap_frames = []
        for frame in ledger.unresolved_frames():
            previous, following = _nearest_confirmed_entries(
                ledger, frame, anchors=anchors
            )
            if (
                previous is not None
                and following is not None
                and bounded_gap(previous, following)
            ):
                gap_frames.append(frame)
        if gap_frames:
            images = _read_sampled_color_frames(video, gap_frames)
    for frame in ledger.unresolved_frames():
        previous, following = _nearest_confirmed_entries(
            ledger,
            frame,
            anchors=anchors,
        )
        if previous is not None and following is not None:
            gap_seconds = (following.source_frame - previous.source_frame) / fps
            bounded = bounded_gap(previous, following)
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
            kick_timing: dict[str, Any] = {}
            image = images.get(frame) if bounded else None
            if image is not None and colour_range is not None:
                moved = _kick_timing_position(
                    frame,
                    previous=previous,
                    following=following,
                    anchors=sorted_anchors,
                    image=image,
                    colour_range=colour_range,
                    people=[
                        detection
                        for detection in (records_by_frame or {})
                        .get(frame, {})
                        .get("detections", [])
                        if detection.get("class_name") == "person"
                    ],
                )
                if moved is not None:
                    kick_timing = {
                        "kick_timing_moved_from": [round(x, 3), round(y, 3)],
                    }
                    x, y = moved
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
                    **kick_timing,
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
