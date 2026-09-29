from __future__ import annotations

from .settings import *  # noqa: F401,F403


CONFIRM_YOLO_MODULE = "01_confirm_yolo"

# A ball seen resting at the same spot on both sides of a short window cannot
# have been somewhere else in between: leaving and being returned to rest at the
# same spot needs several touches, which the evidence does not show.
RESTING_BALL_WINDOW_SECONDS = 3.0
RESTING_BALL_RADIUS_DIAMETERS = 3.0
MINIMUM_BALL_DIAMETER_PIXELS = 8.0


def _leaves_resting_ball(
    x: float,
    y: float,
    frame: int,
    *,
    previous: Any,
    following: Any,
    fps: float,
) -> bool:
    if previous is None or following is None or fps <= 0:
        return False
    if not previous.source_frame < frame < following.source_frame:
        return False
    if (
        following.source_frame - previous.source_frame
    ) / fps > RESTING_BALL_WINDOW_SECONDS:
        return False
    diameter = max(
        float(previous.box_diagonal or 0.0),
        float(following.box_diagonal or 0.0),
        MINIMUM_BALL_DIAMETER_PIXELS,
    )
    radius = RESTING_BALL_RADIUS_DIAMETERS * diameter
    if hypot(
        float(previous.x) - float(following.x),
        float(previous.y) - float(following.y),
    ) > radius:
        return False
    return hypot(
        x - (float(previous.x) + float(following.x)) / 2,
        y - (float(previous.y) + float(following.y)) / 2,
    ) > radius


def _confirmed_bracket(
    entries: Iterable[Any],
    frame: int,
) -> tuple[Any, Any]:
    ordered = sorted(entries, key=lambda entry: entry.source_frame)
    previous = next(
        (entry for entry in reversed(ordered) if entry.source_frame < frame),
        None,
    )
    following = next(
        (entry for entry in ordered if entry.source_frame > frame),
        None,
    )
    return previous, following


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


MOVING_CHAIN_MINIMUM_LENGTH = 3
MOVING_CHAIN_MINIMUM_PEAK_CONFIDENCE = 0.3
MOVING_CHAIN_MAXIMUM_SKIPPED_FRAMES = 1


def _moving_chain_supports(
    point: BallPoint,
    *,
    candidates_by_frame: dict[int, list[_BallCandidate]],
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
) -> bool:
    """Whether the detection belongs to a chain of moving detections.

    Links run through sampled frames in both directions, at most one missed
    frame at a time, to the closest reachable detection that is not a static
    object. A ball in flight produces such a chain; one-frame false positives
    and fixed objects do not.
    """
    if fps <= 0 or frame_step < 1:
        return False
    chain = [point]
    first_frame = min(candidates_by_frame, default=point.source_frame)
    last_frame = max(candidates_by_frame, default=point.source_frame)
    for direction in (-1, 1):
        current = point
        frame = point.source_frame
        skipped = 0
        while skipped <= MOVING_CHAIN_MAXIMUM_SKIPPED_FRAMES:
            frame += direction * frame_step
            if not first_frame <= frame <= last_frame:
                break
            elapsed = abs(frame - current.source_frame) / fps
            reachable = [
                candidate.point
                for candidate in candidates_by_frame.get(frame, [])
                if hypot(
                    candidate.point.x - current.x,
                    candidate.point.y - current.y,
                )
                <= max_speed_pixels_per_second * elapsed
                and _same_position_static_reason(
                    candidate.point,
                    candidates_by_frame=candidates_by_frame,
                    fps=fps,
                )
                is None
            ]
            if not reachable:
                skipped += 1
                continue
            current = min(
                reachable,
                key=lambda candidate: hypot(
                    candidate.x - current.x,
                    candidate.y - current.y,
                ),
            )
            chain.append(current)
            skipped = 0
    return (
        len(chain) >= MOVING_CHAIN_MINIMUM_LENGTH
        and max(candidate.confidence for candidate in chain)
        >= MOVING_CHAIN_MINIMUM_PEAK_CONFIDENCE
    )


def _reachable_from_nearest_confirmed(
    point: BallPoint,
    ledger: FrameLedger,
    *,
    fps: float,
    max_speed_pixels_per_second: float,
) -> bool:
    if fps <= 0:
        return False
    confirmed = [
        entry
        for entry in ledger.entries.values()
        if entry.status == "confirmed"
        and entry.x is not None
        and entry.y is not None
    ]
    for side in (
        [entry for entry in confirmed if entry.source_frame < point.source_frame],
        [entry for entry in confirmed if entry.source_frame > point.source_frame],
    ):
        if not side:
            continue
        nearest = min(
            side,
            key=lambda entry: abs(entry.source_frame - point.source_frame),
        )
        elapsed = abs(nearest.source_frame - point.source_frame) / fps
        if hypot(nearest.x - point.x, nearest.y - point.y) > (
            max_speed_pixels_per_second * 1.25 * elapsed
        ):
            return False
    return True


# A weak detection far off the line between the confirmed ball just before and
# just after it would need the ball to leave and come straight back within a
# fraction of a second. The detour allowance is a quarter of the maximum ball
# speed over the bracket.
DETOUR_BRACKET_STEPS = 3
DETOUR_ALLOWANCE_SPEED_FRACTION = 0.25


def _withdraw_one_frame_detours(
    ledger: FrameLedger,
    *,
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
) -> list[tuple[int, float, float]]:
    withdrawn: list[tuple[int, float, float]] = []
    if fps <= 0 or frame_step < 1:
        return withdrawn
    while True:
        confirmed = {
            entry.source_frame: entry
            for entry in ledger.entries.values()
            if entry.status == "confirmed"
        }
        worst: tuple[float, Any] | None = None
        for frame, entry in confirmed.items():
            if (
                entry.confirming_module != CONFIRM_YOLO_MODULE
                or not _is_movable_detection(entry)
            ):
                continue
            previous = next(
                (
                    confirmed[frame - offset * frame_step]
                    for offset in range(1, DETOUR_BRACKET_STEPS + 1)
                    if frame - offset * frame_step in confirmed
                ),
                None,
            )
            following = next(
                (
                    confirmed[frame + offset * frame_step]
                    for offset in range(1, DETOUR_BRACKET_STEPS + 1)
                    if frame + offset * frame_step in confirmed
                ),
                None,
            )
            if previous is None or following is None:
                continue
            # Only a detection weaker than both neighbours is the detour; a
            # stronger one means the neighbours are the doubtful points.
            if float(entry.confidence or 0.0) >= min(
                float(previous.confidence or 0.0),
                float(following.confidence or 0.0),
            ):
                continue
            elapsed = (following.source_frame - previous.source_frame) / fps
            direct = hypot(following.x - previous.x, following.y - previous.y)
            if direct > max_speed_pixels_per_second * 1.25 * elapsed:
                continue
            excess = (
                hypot(entry.x - previous.x, entry.y - previous.y)
                + hypot(following.x - entry.x, following.y - entry.y)
                - direct
            )
            allowance = (
                max_speed_pixels_per_second
                * DETOUR_ALLOWANCE_SPEED_FRACTION
                * elapsed
            )
            if excess > allowance and (worst is None or excess > worst[0]):
                worst = (excess, entry)
        if worst is None:
            return withdrawn
        entry = worst[1]
        withdrawn.append((entry.source_frame, float(entry.x), float(entry.y)))
        ledger.withdraw(
            entry.source_frame,
            CONFIRM_YOLO_MODULE,
            "detour_from_consistent_confirmed_neighbours",
        )


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
    ledger: FrameLedger | None = None,
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
    if near_feet and not require_moving_neighbour:
        return None, True
    if require_moving_neighbour and ledger is not None:
        # An unselected candidate must also be reachable from the confirmed
        # ball; being near a player's feet alone is not evidence of the ball.
        neighbour_speed = _speed_from_confirmed_neighbour(
            point,
            ledger,
            fps=fps,
            frame_step=frame_step,
        )
        if neighbour_speed > max_speed_pixels_per_second * 1.25 and any(
            entry.status == "confirmed"
            for entry in ledger.entries.values()
        ) and not (
            # Inside a gap with no confirmed ball nearby, a moving chain of
            # detections that the last and next confirmed ball can reach is
            # the ball; otherwise a gap could never be closed from inside.
            neighbour_speed == float("inf")
            and _moving_chain_supports(
                point,
                candidates_by_frame=candidates_by_frame,
                fps=fps,
                frame_step=frame_step,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            )
            and _reachable_from_nearest_confirmed(
                point,
                ledger,
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            )
        ):
            return "unreachable_from_confirmed_ball", near_feet
        # Being reachable from a farther confirmed ball is not enough when
        # the adjacent confirmed ball on either side cannot reach it.
        if not _reachable_from_nearest_confirmed(
            point,
            ledger,
            fps=fps,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        ):
            return "unreachable_from_confirmed_ball", near_feet
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
    video: Path | None = None,
) -> FrameLedger:
    best_by_frame: dict[int, BallPoint] = {}
    for point in detector_points:
        if point.source_attribution != "yolo26_observed":
            continue
        current = best_by_frame.get(point.source_frame)
        if current is None or point.confidence > current.confidence:
            best_by_frame[point.source_frame] = point

    confirmation_pass = dict(
        best_by_frame=best_by_frame,
        candidates_by_frame=candidates_by_frame,
        records_by_frame=records_by_frame,
        fps=fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
        minimum_confidence=minimum_confidence,
    )
    _confirm_unresolved_frames(
        ledger,
        ledger.unresolved_frames(),
        excluded=set(),
        **confirmation_pass,
    )
    withdrawn = _withdraw_one_frame_detours(
        ledger,
        fps=fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    if withdrawn:
        _confirm_unresolved_frames(
            ledger,
            sorted({frame for frame, _, _ in withdrawn}),
            excluded=set(withdrawn),
            require_reachable=True,
            **confirmation_pass,
        )
    _reject_confirmations_that_leave_resting_ball(ledger, fps=fps)

    if video is not None:
        _extend_resting_ball_confirmations(ledger, video=video, fps=fps)
    return ledger


def _confirm_unresolved_frames(
    ledger: FrameLedger,
    frames: Iterable[int],
    *,
    excluded: set[tuple[int, float, float]],
    require_reachable: bool = False,
    best_by_frame: dict[int, BallPoint],
    candidates_by_frame: dict[int, list[_BallCandidate]],
    records_by_frame: dict[int, dict[str, Any]],
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
    minimum_confidence: float,
) -> None:
    for frame in frames:
        if ledger.confirmed(frame) is not None:
            continue
        selected = best_by_frame.get(frame)
        options: list[tuple[BallPoint, bool]] = []
        if selected is not None:
            options.append((selected, False))
        # The selected trajectory can follow a false positive; every other
        # detector candidate in an unresolved frame gets the same checks. The
        # strongest reachable detection goes first: ranking by nearness to the
        # last confirmed point lets one weak lock-in pull a false chain along.
        for candidate in sorted(
            candidates_by_frame.get(frame, []),
            key=lambda item: (
                -item.point.confidence,
                _speed_from_confirmed_neighbour(
                    item.point,
                    ledger,
                    fps=fps,
                    frame_step=frame_step,
                ),
            ),
        ):
            if (
                candidate.point != selected
                and candidate.point.source_attribution == "yolo26_observed"
            ):
                options.append((candidate.point, True))
        options = [
            (point, alternative)
            for point, alternative in options
            if (frame, float(point.x), float(point.y)) not in excluded
        ]
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
                # A replacement for a withdrawn detour must be reachable from
                # the confirmed ball, whichever trajectory selected it.
                require_moving_neighbour=alternative or require_reachable,
                ledger=ledger,
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


# A resting ball stays where it is until a player moves it. Once two detections
# agree the ball is resting, each neighbouring frame keeps the ball at that spot
# while the pixels inside the ball disc still match the detected ball and still
# stand out from the surrounding grass. The walk stops at the first frame where
# the disc changes, which is where the ball was moved or covered.
RESTING_ANCHOR_RADIUS_DIAMETERS = 1.0
RESTING_DISC_MINIMUM_CONTRAST = 8.0
RESTING_DISC_MAXIMUM_CHANGE_RATIO = 0.5
RESTING_DISC_MINIMUM_CONTRAST_RATIO = 0.5
RESTING_STRONG_ELSEWHERE_CONFIDENCE = 0.5


def _resting_disc_masks(diameter: float) -> tuple[int, np.ndarray, np.ndarray]:
    inner_radius = max(2.0, diameter * 0.4)
    ring_inner = diameter * 0.7
    ring_outer = diameter * 1.1
    half = int(np.ceil(ring_outer)) + 1
    offsets_y, offsets_x = np.mgrid[-half : half + 1, -half : half + 1]
    distance = np.hypot(offsets_x, offsets_y)
    return (
        half,
        distance <= inner_radius,
        (distance >= ring_inner) & (distance <= ring_outer),
    )


def _resting_patch(
    grayscale: np.ndarray,
    x: float,
    y: float,
    half: int,
) -> np.ndarray | None:
    center_x = round(x)
    center_y = round(y)
    top = center_y - half
    left = center_x - half
    if (
        top < 0
        or left < 0
        or center_y + half + 1 > grayscale.shape[0]
        or center_x + half + 1 > grayscale.shape[1]
    ):
        return None
    return grayscale[
        top : center_y + half + 1,
        left : center_x + half + 1,
    ].astype(np.float32)


def _ball_still_resting(
    reference: np.ndarray,
    target: np.ndarray,
    inner: np.ndarray,
    ring: np.ndarray,
) -> bool:
    reference_contrast = float(reference[inner].mean() - reference[ring].mean())
    if abs(reference_contrast) < RESTING_DISC_MINIMUM_CONTRAST:
        return False
    target_contrast = float(target[inner].mean() - target[ring].mean())
    if (
        target_contrast * reference_contrast <= 0
        or abs(target_contrast)
        < abs(reference_contrast) * RESTING_DISC_MINIMUM_CONTRAST_RATIO
    ):
        return False
    change = float(np.abs(target - reference)[inner].mean())
    return change <= abs(reference_contrast) * RESTING_DISC_MAXIMUM_CHANGE_RATIO


def _resting_ball_anchors(
    ledger: FrameLedger,
    *,
    fps: float,
) -> list[tuple[Any, Any]]:
    detected = sorted(
        (
            entry
            for entry in ledger.entries.values()
            if entry.status == "confirmed"
            and entry.confirming_module == CONFIRM_YOLO_MODULE
            and entry.point_source_attribution == "yolo26_observed"
        ),
        key=lambda entry: entry.source_frame,
    )
    anchors: list[tuple[Any, Any]] = []
    for index, first in enumerate(detected):
        for second in detected[index + 1 :]:
            if (
                second.source_frame - first.source_frame
            ) / fps > RESTING_BALL_WINDOW_SECONDS:
                break
            diameter = max(
                float(first.box_diagonal or 0.0),
                float(second.box_diagonal or 0.0),
                MINIMUM_BALL_DIAMETER_PIXELS,
            )
            if hypot(
                float(first.x) - float(second.x),
                float(first.y) - float(second.y),
            ) <= RESTING_ANCHOR_RADIUS_DIAMETERS * diameter:
                # A stronger detection elsewhere in between means the ball
                # left and came back to the spot; it was not resting there.
                weakest = min(
                    float(first.confidence or 0.0),
                    float(second.confidence or 0.0),
                )
                rest_x = (float(first.x) + float(second.x)) / 2
                rest_y = (float(first.y) + float(second.y)) / 2
                radius = RESTING_BALL_RADIUS_DIAMETERS * diameter
                if not any(
                    first.source_frame < between.source_frame < second.source_frame
                    and float(between.confidence or 0.0) >= weakest
                    and hypot(
                        float(between.x) - rest_x,
                        float(between.y) - rest_y,
                    )
                    > radius
                    for between in detected
                ):
                    anchors.append((first, second))
                break
    return anchors


def _is_movable_detection(entry: Any) -> bool:
    return (
        entry.confirming_module == CONFIRM_YOLO_MODULE
        and float(entry.confidence or 0.0) < RESTING_STRONG_ELSEWHERE_CONFIDENCE
    )


def _extend_resting_ball_confirmations(
    ledger: FrameLedger,
    *,
    video: Path,
    fps: float,
) -> None:
    anchors = _resting_ball_anchors(ledger, fps=fps)
    if not anchors:
        return
    frames = sorted(ledger.entries)
    grayscale = _read_sampled_grayscale_frames(video, frames)
    rest_spans: list[tuple[int, int, float, float, float]] = []
    for first, second in anchors:
        diameter = max(
            float(first.box_diagonal or 0.0),
            float(second.box_diagonal or 0.0),
            MINIMUM_BALL_DIAMETER_PIXELS,
        )
        rest_x = (float(first.x) + float(second.x)) / 2
        rest_y = (float(first.y) + float(second.y)) / 2
        radius = RESTING_BALL_RADIUS_DIAMETERS * diameter
        if any(
            (current := ledger.confirmed(anchor.source_frame)) is None
            or hypot(float(current.x) - rest_x, float(current.y) - rest_y)
            > radius
            for anchor in (first, second)
        ):
            continue
        # One ball: a second resting spot inside an established rest span is
        # a stationary false positive, not the ball.
        if any(
            start <= first.source_frame <= end
            and hypot(rest_x - span_x, rest_y - span_y) > span_radius
            for start, end, span_x, span_y, span_radius in rest_spans
        ):
            for anchor in (first, second):
                current = ledger.confirmed(anchor.source_frame)
                if current is not None and _is_movable_detection(current):
                    ledger.withdraw(
                        anchor.source_frame,
                        CONFIRM_YOLO_MODULE,
                        "ball_still_resting_elsewhere",
                    )
            continue
        half, inner, ring = _resting_disc_masks(diameter)
        reference_frame = grayscale.get(first.source_frame)
        reference = (
            _resting_patch(reference_frame, rest_x, rest_y, half)
            if reference_frame is not None
            else None
        )
        if reference is None:
            continue
        evidence = {
            "resting_ball_anchor_frames": [
                first.source_frame,
                second.source_frame,
            ],
            "resting_disc_matches_detected_ball": True,
        }
        confidence = min(
            float(first.confidence or 0.0),
            float(second.confidence or 0.0),
        )
        span_start = first.source_frame
        span_end = first.source_frame
        start_index = frames.index(first.source_frame)
        for direction in (1, -1):
            last_match = first.source_frame
            covered: list[int] = []
            index = start_index + direction
            while 0 <= index < len(frames):
                frame = frames[index]
                index += direction
                if abs(frame - last_match) / fps > RESTING_BALL_WINDOW_SECONDS:
                    break
                entry = ledger.entries[frame]
                at_rest = entry.status == "confirmed" and hypot(
                    float(entry.x) - rest_x,
                    float(entry.y) - rest_y,
                ) <= radius
                if not at_rest:
                    target_frame = grayscale.get(frame)
                    target = (
                        _resting_patch(target_frame, rest_x, rest_y, half)
                        if target_frame is not None
                        else None
                    )
                    if target is None or not _ball_still_resting(
                        reference,
                        target,
                        inner,
                        ring,
                    ):
                        # Covered frames stay unresolved; they only join the
                        # rest span if the ball is seen at rest again.
                        covered.append(frame)
                        continue
                    if entry.status == "confirmed":
                        if not _is_movable_detection(entry):
                            break
                        ledger.withdraw(
                            frame,
                            CONFIRM_YOLO_MODULE,
                            "ball_still_resting_elsewhere",
                        )
                    ledger.confirm(
                        frame,
                        x=rest_x,
                        y=rest_y,
                        confirming_module=CONFIRM_YOLO_MODULE,
                        evidence=evidence,
                        confidence=confidence,
                        box_diagonal=diameter,
                        point_evidence="resting_ball_persistence",
                        point_source_attribution="temporal_detector_observed",
                    )
                for gap_frame in covered:
                    gap_entry = ledger.confirmed(gap_frame)
                    if gap_entry is not None and _is_movable_detection(gap_entry):
                        ledger.withdraw(
                            gap_frame,
                            CONFIRM_YOLO_MODULE,
                            "ball_still_resting_elsewhere",
                        )
                covered = []
                last_match = frame
            span_start = min(span_start, last_match)
            span_end = max(span_end, last_match)
        rest_spans.append((span_start, span_end, rest_x, rest_y, radius))

def _reject_confirmations_that_leave_resting_ball(
    ledger: FrameLedger,
    *,
    fps: float,
) -> None:
    """Withdraw this module's detections that contradict a resting ball.

    The check runs once all detections are known, so a ball resting at the same
    spot before and after a detection elsewhere wins over that one detection.
    """
    confirmed = [
        entry
        for entry in ledger.entries.values()
        if entry.status == "confirmed"
        and entry.confirming_module == CONFIRM_YOLO_MODULE
    ]
    for entry in confirmed:
        others = [
            other
            for other in confirmed
            if other.source_frame != entry.source_frame
        ]
        previous, following = _confirmed_bracket(others, entry.source_frame)
        if (
            previous is not None
            and following is not None
            and float(entry.confidence or 0.0)
            > min(
                float(previous.confidence or 0.0),
                float(following.confidence or 0.0),
            )
        ):
            continue
        if _leaves_resting_ball(
            float(entry.x),
            float(entry.y),
            entry.source_frame,
            previous=previous,
            following=following,
            fps=fps,
        ):
            ledger.withdraw(
                entry.source_frame,
                CONFIRM_YOLO_MODULE,
                "leaves_and_returns_to_resting_ball",
            )
