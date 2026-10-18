from __future__ import annotations

from typing import Callable

from .settings import *  # noqa: F401,F403


# A ball rolling where the detector sees nothing still shows its own colour
# frame after frame. From the confirmed point on each side of a gap the ball is
# followed one sampled frame at a time: each step looks only near where the
# ball's last movement predicts it, inside the distance it can travel, and
# takes the nearest ball-coloured spot. The gap is filled only when the walk
# forwards from the earlier point and the walk backwards from the later point
# arrive at the same spot, so a walk that drifts onto a distractor (a board
# logo, a shirt, a leg) finds no partner and fills nothing.
COLOUR_WALK_MODULE = "09_colour_walk"
COLOUR_WALK_PROFILE = {
    # Minimum Lab chroma distance from the search window's own median colour.
    "minimum_chroma_distance": 12.0,
    "minimum_blob_pixels": 4,
    # Blob limits in ball diagonals (median strong-detection box diagonal).
    "maximum_blob_side_diagonals": 3.0,
    "meeting_distance_diagonals": 2.0,
    # A piece split off a larger ball-coloured region must cover at least
    # this share of a ball's area.
    "minimum_split_piece_ball_areas": 0.25,
    # Search window around the predicted point: grows with time, capped.
    "window_base_pixels": 32.0,
    "window_growth_pixels_per_second": 150.0,
    "window_maximum_pixels": 96.0,
    # A velocity seed must come from a confirmed point this close in frames.
    "velocity_seed_frames": 15,
    # A ball-coloured spot on a person's upper body is shirt or skin colour.
    "person_confidence": 0.5,
    "upper_body_fraction": 0.7,
    # A step that lands this many ball diagonals from where the ball's last
    # movement predicts it is a jump to another object, so the walk stops.
    "maximum_jump_diagonals": 2.5,
    # Following the ball by colour alone for longer is not trusted.
    "maximum_gap_seconds": 4.0,
    "confidence": 0.25,
}


def _colour_walk_gaps(
    ledger: FrameLedger, fps: float
) -> list[tuple[int, int, tuple[int, ...]]]:
    """Unresolved runs with a confirmed point on both sides, short enough to walk."""
    sampled = sorted(ledger.entries)
    limit = float(COLOUR_WALK_PROFILE["maximum_gap_seconds"]) * fps
    gaps: list[tuple[int, int, tuple[int, ...]]] = []
    index = 0
    while index < len(sampled):
        if ledger.confirmed(sampled[index]) is not None:
            index += 1
            continue
        start = index
        while index < len(sampled) and ledger.confirmed(sampled[index]) is None:
            index += 1
        if start == 0 or index >= len(sampled):
            continue
        left, right = sampled[start - 1], sampled[index]
        if right - left > limit:
            continue
        gaps.append((left, right, tuple(sampled[start:index])))
    return gaps


def _on_person_upper_body(
    x: float, y: float, record: dict[str, Any] | None
) -> bool:
    fraction = float(COLOUR_WALK_PROFILE["upper_body_fraction"])
    for detection in (record or {}).get("detections", []):
        if detection.get("class_name") != "person":
            continue
        if float(detection.get("confidence", 0.0)) < float(
            COLOUR_WALK_PROFILE["person_confidence"]
        ):
            continue
        x1, y1 = float(detection["x1"]), float(detection["y1"])
        x2, y2 = float(detection["x2"]), float(detection["y2"])
        if (
            x1 <= x <= x2
            and y1 <= y <= y1 + fraction * (y2 - y1)
            and not _beside_head(BallPoint(0, 0.0, 0.0, x, y), x1, y1, x2, y2)
        ):
            return True
    return False


def _colour_walk_blobs(
    image: np.ndarray,
    centre: tuple[float, float],
    half: float,
    *,
    colour_range: tuple[float, float],
    ball_diagonal: float,
    record: dict[str, Any] | None = None,
) -> list[tuple[float, float]]:
    """Ball-coloured spots that stand out from their surroundings near a point."""
    height, width = image.shape[:2]
    x0 = int(max(0, centre[0] - half))
    y0 = int(max(0, centre[1] - half))
    x1 = int(min(width, centre[0] + half))
    y1 = int(min(height, centre[1] + half))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return []
    lab = cv2.cvtColor(image[y0:y1, x0:x1], cv2.COLOR_BGR2LAB).astype(np.float32)
    surround = np.median(lab.reshape(-1, 3), axis=0)
    stands_out = np.hypot(lab[..., 1] - surround[1], lab[..., 2] - surround[2]) >= float(
        COLOUR_WALK_PROFILE["minimum_chroma_distance"]
    )
    ball_colour = (lab[..., 1] >= colour_range[0]) & (lab[..., 1] <= colour_range[1])
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        (stands_out & ball_colour).astype(np.uint8), connectivity=8
    )
    maximum_area = np.pi / 4.0 * (2.0 * ball_diagonal) ** 2
    maximum_side = ball_diagonal * float(
        COLOUR_WALK_PROFILE["maximum_blob_side_diagonals"]
    )
    minimum_area = int(COLOUR_WALK_PROFILE["minimum_blob_pixels"])
    minimum_piece = (
        float(COLOUR_WALK_PROFILE["minimum_split_piece_ball_areas"])
        * np.pi / 4.0 * ball_diagonal ** 2 / 2.0
    )

    def fits(stat) -> bool:
        side = max(int(stat[cv2.CC_STAT_WIDTH]), int(stat[cv2.CC_STAT_HEIGHT]))
        area = int(stat[cv2.CC_STAT_AREA])
        return minimum_area <= area <= maximum_area and side <= maximum_side

    found: list[tuple[float, float]] = []
    for label in range(1, count):
        if fits(stats[label]):
            found.append(tuple(centroids[label]))
            continue
        if int(stats[label, cv2.CC_STAT_AREA]) < minimum_area:
            continue
        # A ball touching a ball-coloured shirt or board joins it through a
        # thin edge; one erosion separates the ball-sized piece.
        part = cv2.erode(
            (labels == label).astype(np.uint8), np.ones((3, 3), np.uint8)
        )
        pieces, _, piece_stats, piece_centroids = cv2.connectedComponentsWithStats(
            part, connectivity=8
        )
        for piece in range(1, pieces):
            if int(piece_stats[piece, cv2.CC_STAT_AREA]) < minimum_piece:
                continue
            if fits(piece_stats[piece]):
                found.append(tuple(piece_centroids[piece]))
    blobs: list[tuple[float, float]] = []
    for cx, cy in found:
        x = x0 + float(cx)
        y = y0 + float(cy)
        if _on_person_upper_body(x, y, record):
            continue
        blobs.append((x, y))
    return blobs


def _colour_walk(
    start: tuple[int, float, float],
    frames: list[int],
    blobs_near: Callable[[int, tuple[float, float], float], list[tuple[float, float]]],
    *,
    velocity: tuple[float, float],
    fps: float,
    max_speed_pixels_per_second: float,
    ball_diagonal: float | None = None,
) -> dict[int, tuple[float, float]]:
    """Follow the ball through ``frames`` in order until no spot is found."""
    last_frame, last_x, last_y = start
    walked: dict[int, tuple[float, float]] = {}
    for frame in frames:
        signed = frame - last_frame
        steps = abs(signed)
        seconds = steps / fps
        reach = max_speed_pixels_per_second * seconds
        predicted = (last_x + velocity[0] * signed, last_y + velocity[1] * signed)
        half = min(
            float(COLOUR_WALK_PROFILE["window_maximum_pixels"]),
            float(COLOUR_WALK_PROFILE["window_base_pixels"])
            + float(COLOUR_WALK_PROFILE["window_growth_pixels_per_second"]) * seconds,
        )
        reachable = [
            blob
            for blob in blobs_near(frame, predicted, half)
            if hypot(blob[0] - last_x, blob[1] - last_y) <= reach
        ]
        if not reachable:
            break
        x, y = min(
            reachable, key=lambda blob: hypot(blob[0] - predicted[0], blob[1] - predicted[1])
        )
        if ball_diagonal and hypot(x - predicted[0], y - predicted[1]) > float(
            COLOUR_WALK_PROFILE["maximum_jump_diagonals"]
        ) * ball_diagonal:
            break
        walked[frame] = (x, y)
        velocity = ((x - last_x) / signed, (y - last_y) / signed)
        last_frame, last_x, last_y = frame, x, y
    return walked


def _colour_walk_meeting(
    gap: tuple[int, ...],
    forward: dict[int, tuple[float, float]],
    backward: dict[int, tuple[float, float]],
    ball_diagonal: float,
) -> dict[int, tuple[float, float]]:
    """Forward points up to where both walks meet, backward points after it."""
    limit = ball_diagonal * float(COLOUR_WALK_PROFILE["meeting_distance_diagonals"])
    meeting = next(
        (
            frame
            for frame in gap
            if frame in forward
            and frame in backward
            and hypot(
                forward[frame][0] - backward[frame][0],
                forward[frame][1] - backward[frame][1],
            )
            <= limit
        ),
        None,
    )
    if meeting is None:
        return {}
    if not all(frame in forward for frame in gap if frame <= meeting):
        return {}
    if not all(frame in backward for frame in gap if frame >= meeting):
        return {}
    return {
        frame: forward[frame] if frame <= meeting else backward[frame] for frame in gap
    }


def _colour_walk_velocity(
    ledger: FrameLedger, sampled: list[int], anchor: int, direction: int
) -> tuple[float, float]:
    """Velocity into ``anchor`` from the confirmed frame before it, if close."""
    position = sampled.index(anchor) - direction
    if not 0 <= position < len(sampled):
        return (0.0, 0.0)
    previous = sampled[position]
    if abs(previous - anchor) > int(COLOUR_WALK_PROFILE["velocity_seed_frames"]):
        return (0.0, 0.0)
    here, there = ledger.confirmed(anchor), ledger.confirmed(previous)
    if here is None or there is None:
        return (0.0, 0.0)
    return (
        (float(here.x) - float(there.x)) / (anchor - previous),
        (float(here.y) - float(there.y)) / (anchor - previous),
    )


def _confirm_colour_walk(
    ledger: FrameLedger,
    *,
    video: Path,
    records_by_frame: dict[int, dict[str, Any]],
    colour_range: tuple[float, float] | None,
    ball_diagonal: float,
    fps: float,
    max_speed_pixels_per_second: float,
) -> FrameLedger:
    if colour_range is None or fps <= 0 or ball_diagonal <= 0:
        return ledger
    gaps = _colour_walk_gaps(ledger, fps)
    if not gaps:
        return ledger
    sampled = sorted(ledger.entries)
    # Every gap is judged from the other modules' points only: points this
    # module adds are written after all walks, so one walk never seeds another.
    found: list[tuple[int, float, float, int, int]] = []
    capture = cv2.VideoCapture(str(video))
    position = 0
    try:
        for left, right, gap in gaps:
            images: dict[int, np.ndarray] = {}
            for frame in gap:
                while position < frame:
                    if not capture.grab():
                        break
                    position += 1
                ok, image = capture.read()
                if not ok:
                    break
                position += 1
                images[frame] = image
            if len(images) != len(gap):
                break

            def blobs_near(
                frame: int, centre: tuple[float, float], half: float
            ) -> list[tuple[float, float]]:
                return _colour_walk_blobs(
                    images[frame],
                    centre,
                    half,
                    colour_range=colour_range,
                    ball_diagonal=ball_diagonal,
                    record=records_by_frame.get(frame),
                )

            ends = {
                anchor: ledger.confirmed(anchor) for anchor in (left, right)
            }
            forward = _colour_walk(
                (left, float(ends[left].x), float(ends[left].y)),
                list(gap),
                blobs_near,
                velocity=_colour_walk_velocity(ledger, sampled, left, 1),
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
                ball_diagonal=ball_diagonal,
            )
            backward = _colour_walk(
                (right, float(ends[right].x), float(ends[right].y)),
                list(reversed(gap)),
                blobs_near,
                velocity=_colour_walk_velocity(ledger, sampled, right, -1),
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
                ball_diagonal=ball_diagonal,
            )
            for frame, (x, y) in _colour_walk_meeting(
                gap, forward, backward, ball_diagonal
            ).items():
                found.append((frame, x, y, left, right))
    finally:
        capture.release()
    for frame, x, y, left, right in found:
        ledger.confirm(
            frame,
            x=x,
            y=y,
            confirming_module=COLOUR_WALK_MODULE,
            evidence={
                "reason": "ball_colour_followed_from_both_neighbours",
                "from_frame": left,
                "to_frame": right,
            },
            confidence=float(COLOUR_WALK_PROFILE["confidence"]),
            box_diagonal=ball_diagonal,
            point_evidence="colour_walk",
            point_source_attribution="colour_walk",
        )
    return ledger
