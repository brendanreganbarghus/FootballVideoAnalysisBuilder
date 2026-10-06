from __future__ import annotations

from .settings import *  # noqa: F401,F403


# Law 17: for a corner kick the ball is placed and stays still inside the
# corner arc. The detector often cannot see that small, still ball at a far
# corner, so the calibrated corner is searched for a ball-coloured spot that
# is new against the clip's own background (flags, boards and logos are part
# of that background) and stays in one place. Only gaps whose neighbouring
# track point is near that corner are searched: the ball must have gone out
# over that goal line. Without a pitch calibration there is nothing to search.
RESTART_SPOT_MODULE = "08_restart_spot_colour"
RESTART_SPOT_PROFILE = {
    "background_samples": 31,
    # Distances in ball diagonals (median strong-detection box diagonal).
    "search_radius_diagonals": 2.0,
    "maximum_anchor_distance_diagonals": 20.0,
    "stationary_step_diagonals": 0.75,
    "minimum_blob_pixels": 2,
    "minimum_still_seconds": 1.0,
    "confidence": 0.25,
}


def _calibrated_pitch_corners(
    calibration_path: Path | None,
    target_size: tuple[float, float],
) -> list[tuple[float, float]]:
    """Ends of both calibrated goal lines, in the video's image size."""
    features, _, scale = _calibrated_pitch_geometry(calibration_path, target_size)
    corners: list[tuple[float, float]] = []
    for name in ("left_goal_line", "right_goal_line"):
        line = features.get(name) or []
        if len(line) < 2:
            continue
        for x, y in (line[0], line[-1]):
            corners.append((float(x) * scale[0], float(y) * scale[1]))
    return corners


def _calibrated_pitch_boundary(
    calibration_path: Path | None,
    target_size: tuple[float, float],
) -> np.ndarray | None:
    """Calibrated pitch outline, in the video's image size."""
    _, boundary, scale = _calibrated_pitch_geometry(calibration_path, target_size)
    if len(boundary) < 3:
        return None
    return np.array(
        [[float(x) * scale[0], float(y) * scale[1]] for x, y in boundary],
        dtype=np.float32,
    )


def _calibrated_pitch_geometry(
    calibration_path: Path | None,
    target_size: tuple[float, float],
) -> tuple[dict[str, Any], list[Any], tuple[float, float]]:
    if calibration_path is None or not Path(calibration_path).is_file():
        return {}, [], (1.0, 1.0)
    from football_poc.image_space import scale_factors

    payload = json.loads(Path(calibration_path).read_text(encoding="utf-8"))
    return (
        payload.get("features") or {},
        payload.get("boundary") or [],
        scale_factors(payload, target_size),
    )


def _restart_spot_search_plan(
    ledger: FrameLedger,
    corners: list[tuple[float, float]],
    ball_diagonal: float,
) -> list[tuple[tuple[int, ...], tuple[float, float]]]:
    """Unresolved gaps paired with each calibrated corner next to them."""
    if not corners or ball_diagonal <= 0:
        return []
    limit = ball_diagonal * float(
        RESTART_SPOT_PROFILE["maximum_anchor_distance_diagonals"]
    )
    sampled = sorted(ledger.entries)
    plan: list[tuple[tuple[int, ...], tuple[float, float]]] = []
    index = 0
    while index < len(sampled):
        if ledger.confirmed(sampled[index]) is not None:
            index += 1
            continue
        start = index
        while index < len(sampled) and ledger.confirmed(sampled[index]) is None:
            index += 1
        gap = tuple(sampled[start:index])
        anchors = [
            ledger.confirmed(sampled[position])
            for position in (start - 1, index)
            if 0 <= position < len(sampled)
        ]
        anchors = [anchor for anchor in anchors if anchor is not None]
        for corner in corners:
            if any(
                hypot(float(anchor.x) - corner[0], float(anchor.y) - corner[1])
                <= limit
                for anchor in anchors
            ):
                plan.append((gap, corner))
    return plan


def _restart_spot_window(
    corner: tuple[float, float],
    ball_diagonal: float,
    frame_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    half = int(np.ceil(ball_diagonal * (
        float(RESTART_SPOT_PROFILE["search_radius_diagonals"]) + 1.0
    )))
    width, height = frame_size
    x0 = max(0, int(round(corner[0])) - half)
    y0 = max(0, int(round(corner[1])) - half)
    x1 = min(width, int(round(corner[0])) + half + 1)
    y1 = min(height, int(round(corner[1])) + half + 1)
    return x0, y0, x1, y1


def _restart_spot_blobs(
    window: np.ndarray,
    background_lab: np.ndarray,
    *,
    origin: tuple[int, int],
    corner: tuple[float, float],
    colour_range: tuple[float, float],
    ball_diagonal: float,
    boundary: np.ndarray | None = None,
) -> list[tuple[float, float]]:
    """Ball-coloured spots near the corner that are not clip background.

    The ball for a corner kick lies inside the corner area, so a spot off the
    calibrated pitch (a person by the flag) is not it; a ball on the line is.
    """
    lab = cv2.cvtColor(window, cv2.COLOR_BGR2LAB).astype(np.float32)
    new_colour = np.hypot(
        lab[..., 1] - background_lab[..., 1],
        lab[..., 2] - background_lab[..., 2],
    ) >= BALL_COLOUR_MINIMUM_CHROMA_DISTANCE
    ball_colour = (lab[..., 1] >= colour_range[0]) & (lab[..., 1] <= colour_range[1])
    count, _, stats, centroids = cv2.connectedComponentsWithStats(
        (new_colour & ball_colour).astype(np.uint8)
    )
    # Area of a ball whose box has the learned diagonal.
    maximum_area = np.pi / 8.0 * ball_diagonal**2
    radius = ball_diagonal * float(RESTART_SPOT_PROFILE["search_radius_diagonals"])
    blobs: list[tuple[float, float]] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if not int(RESTART_SPOT_PROFILE["minimum_blob_pixels"]) <= area <= maximum_area:
            continue
        x = origin[0] + float(centroids[label][0])
        y = origin[1] + float(centroids[label][1])
        if hypot(x - corner[0], y - corner[1]) > radius:
            continue
        if boundary is not None and cv2.pointPolygonTest(
            boundary, (x, y), True
        ) < -ball_diagonal / 2.0:
            continue
        blobs.append((x, y))
    return blobs


def _still_restart_spot_run(
    blobs_by_frame: dict[int, list[tuple[float, float]]],
    gap: list[int],
    *,
    ball_diagonal: float,
    fps: float,
) -> list[tuple[int, float, float]]:
    """The one spot that stays still for long enough, or nothing if unclear."""
    step_limit = ball_diagonal * float(
        RESTART_SPOT_PROFILE["stationary_step_diagonals"]
    )
    finished: list[list[tuple[int, float, float]]] = []
    active: list[list[tuple[int, float, float]]] = []
    for frame in gap:
        blobs = blobs_by_frame.get(frame, [])
        extended: list[list[tuple[int, float, float]]] = []
        used: set[int] = set()
        for run in active:
            _, last_x, last_y = run[-1]
            nearest = min(
                (
                    (hypot(x - last_x, y - last_y), index)
                    for index, (x, y) in enumerate(blobs)
                    if index not in used
                ),
                default=None,
            )
            if nearest is None or nearest[0] > step_limit:
                finished.append(run)
                continue
            used.add(nearest[1])
            x, y = blobs[nearest[1]]
            extended.append([*run, (frame, x, y)])
        for index, (x, y) in enumerate(blobs):
            if index not in used:
                extended.append([(frame, x, y)])
        active = extended
    finished.extend(active)
    minimum = float(RESTART_SPOT_PROFILE["minimum_still_seconds"])
    still = [run for run in finished if (run[-1][0] - run[0][0]) / fps >= minimum]
    if len(still) != 1:
        return []
    return still[0]


def _confirm_restart_spot_colour(
    ledger: FrameLedger,
    *,
    video: Path,
    corners: list[tuple[float, float]],
    colour_range: tuple[float, float] | None,
    ball_diagonal: float,
    fps: float,
    boundary: np.ndarray | None = None,
) -> FrameLedger:
    if colour_range is None or fps <= 0:
        return ledger
    plan = _restart_spot_search_plan(ledger, corners, ball_diagonal)
    if not plan:
        return ledger
    capture = cv2.VideoCapture(str(video))
    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_size = (
            int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
        if frame_count <= 0:
            return ledger
        background_frames = set(
            np.linspace(
                0, frame_count - 1, int(RESTART_SPOT_PROFILE["background_samples"])
            ).astype(int).tolist()
        )
        boxes = {
            corner: _restart_spot_window(corner, ball_diagonal, frame_size)
            for _, corner in plan
        }
        gap_frames = {frame for gap, _ in plan for frame in gap}
        wanted = background_frames | gap_frames
        windows: dict[int, dict[tuple[float, float], np.ndarray]] = {}
        for frame in range(min(max(wanted) + 1, frame_count)):
            if frame not in wanted:
                if not capture.grab():
                    break
                continue
            ok, image = capture.read()
            if not ok:
                break
            windows[frame] = {
                corner: image[y0:y1, x0:x1].copy()
                for corner, (x0, y0, x1, y1) in boxes.items()
            }
    finally:
        capture.release()
    backgrounds = {
        corner: np.median(
            np.stack(
                [
                    cv2.cvtColor(windows[frame][corner], cv2.COLOR_BGR2LAB)
                    for frame in sorted(background_frames)
                    if frame in windows
                ]
            ).astype(np.float32),
            axis=0,
        )
        for corner in boxes
    }
    for gap, corner in plan:
        x0, y0, _, _ = boxes[corner]
        blobs_by_frame = {
            frame: _restart_spot_blobs(
                windows[frame][corner],
                backgrounds[corner],
                origin=(x0, y0),
                corner=corner,
                colour_range=colour_range,
                ball_diagonal=ball_diagonal,
                boundary=boundary,
            )
            for frame in gap
            if frame in windows
        }
        run = _still_restart_spot_run(
            blobs_by_frame, gap, ball_diagonal=ball_diagonal, fps=fps
        )
        for frame, x, y in run:
            if ledger.confirmed(frame) is not None:
                continue
            ledger.confirm(
                frame,
                x=x,
                y=y,
                confirming_module=RESTART_SPOT_MODULE,
                evidence={
                    "reason": "still_ball_colour_spot_at_calibrated_corner",
                    "corner": [round(corner[0], 1), round(corner[1], 1)],
                    "still_from_frame": run[0][0],
                    "still_to_frame": run[-1][0],
                },
                confidence=float(RESTART_SPOT_PROFILE["confidence"]),
                box_diagonal=ball_diagonal,
                point_evidence="restart_spot_colour",
                point_source_attribution="restart_spot_colour",
            )
    return ledger
