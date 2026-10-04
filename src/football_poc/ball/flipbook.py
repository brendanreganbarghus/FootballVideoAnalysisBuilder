from __future__ import annotations

from .settings import *  # noqa: F401,F403


FLIPBOOK_MODULE = "02_flipbook_time_machine"

# The flip-book walks the sampled frames page by page outwards from every
# confirmed ball. Each page predicts the ball from its last known velocity and
# looks there first: the cached detections and an upscaled detector pass over a
# small window. When the ball is not on its path a player has it, so the feet of
# the nearest players within reach are searched next. A candidate is accepted
# only when it is the right size, outside a player's upper body and not a fixed
# pitch object. The walk stops after a few empty pages. Frames reached from both
# sides must agree, otherwise they stay unresolved.
# Only permanent chain locks are trusted as starting pages; a single-frame
# confirmation can be a false positive and must not be extended.
FLIPBOOK_ANCHOR_MODULES = ("00_lock_yolo_chains", FLIPBOOK_MODULE)

FLIPBOOK_PROFILE = FrozenProfile({
    "minimum_confidence": 0.10,
    "window_base_half_size_pixels": 32.0,
    "window_growth_pixels_per_second": 150.0,
    "window_max_half_size_pixels": 96.0,
    "crop_upscale_size": 640,
    "detection_crop_half_sizes": (96.0, 128.0, 160.0),
    "player_minimum_confidence": 0.5,
    "players_searched": 0,
    "player_feet_half_size_pixels": 64.0,
    "maximum_missed_pages": 2,
    "velocity_anchor_max_frames": 15,
    "minimum_diameter_ratio": 0.5,
    "maximum_diameter_ratio": 2.0,
    "agreement_diameters": 2.0,
    "static_radius_pixels": 6.0,
    "static_minimum_seconds": 10.0,
    "bracket_max_gap_frames": 15,
})


def _off_bracketed_path(
    frame: int,
    chosen: tuple[float, float, float, float],
    by_frame: dict[int, Any],
    ordered: list[int],
    profile: Any,
) -> bool:
    """True when a short gap between two confirmed frames gives a nearby
    line the ball must follow, and the proposal lies too far from it."""
    position = 0
    while position < len(ordered) and ordered[position] < frame:
        position += 1
    if position == 0 or position >= len(ordered):
        return False
    before, after = by_frame[ordered[position - 1]], by_frame[ordered[position]]
    gap = after.source_frame - before.source_frame
    if gap > int(profile["bracket_max_gap_frames"]):
        return False
    alpha = (frame - before.source_frame) / gap
    expected_x = float(before.x) + (float(after.x) - float(before.x)) * alpha
    expected_y = float(before.y) + (float(after.y) - float(before.y)) * alpha
    tolerance = float(profile["agreement_diameters"]) * max(
        float(before.box_diagonal or 0.0),
        float(after.box_diagonal or 0.0),
        chosen[2],
        MINIMUM_BALL_DIAMETER_PIXELS,
    )
    return hypot(chosen[0] - expected_x, chosen[1] - expected_y) > tolerance


def _flipbook_static_spots(
    records_by_frame: dict[int, dict[str, Any]],
    fps: float,
) -> list[tuple[float, float]]:
    boxes = [
        (frame, (d["x1"] + d["x2"]) / 2, (d["y1"] + d["y2"]) / 2)
        for frame, record in records_by_frame.items()
        for d in record.get("detections", [])
        if d.get("class_name") == "sports ball"
    ]
    radius = float(FLIPBOOK_PROFILE["static_radius_pixels"])
    minimum = float(FLIPBOOK_PROFILE["static_minimum_seconds"]) * fps
    spots: list[tuple[float, float]] = []
    for _, x, y in boxes:
        if any(hypot(x - sx, y - sy) <= radius for sx, sy in spots):
            continue
        frames = [f for f, bx, by in boxes if hypot(bx - x, by - y) <= radius]
        if max(frames) - min(frames) >= minimum:
            spots.append((x, y))
    return spots


def _flipbook_detect(
    model: Any,
    image: np.ndarray,
    centers: list[tuple[float, float, float]],
) -> list[tuple[float, float, float, float]]:
    height, width = image.shape[:2]
    crops = []
    offsets = []
    for cx, cy, half in centers:
        left = int(max(0, min(width - 2 * half, cx - half)))
        top = int(max(0, min(height - 2 * half, cy - half)))
        right = int(min(width, left + 2 * half))
        bottom = int(min(height, top + 2 * half))
        if right - left < 8 or bottom - top < 8:
            continue
        crops.append(image[top:bottom, left:right])
        offsets.append((left, top))
    if not crops:
        return []
    results = model.predict(
        crops,
        imgsz=int(FLIPBOOK_PROFILE["crop_upscale_size"]),
        conf=float(FLIPBOOK_PROFILE["minimum_confidence"]),
        verbose=False,
    )
    found = []
    for result, (left, top) in zip(results, offsets, strict=True):
        for box in result.boxes:
            if result.names[int(box.cls[0])] != "sports ball":
                continue
            x1, y1, x2, y2 = (float(value) for value in box.xyxy[0])
            found.append(
                (left + (x1 + x2) / 2, top + (y1 + y2) / 2,
                 hypot(x2 - x1, y2 - y1), float(box.conf[0]))
            )
    return found


def _flipbook_walk(
    start: Any,
    previous: Any | None,
    direction: int,
    *,
    frames: list[int],
    stop_frames: set[int],
    page: Any,
) -> dict[int, tuple[float, float, float, float]]:
    """Walk from a confirmed entry one sampled frame at a time."""
    profile = FLIPBOOK_PROFILE
    proposals: dict[int, tuple[float, float, float, float]] = {}
    index = frames.index(start.source_frame)
    last = (start.source_frame, float(start.x), float(start.y))
    velocity = (0.0, 0.0)
    if (
        previous is not None
        and previous.source_frame != start.source_frame
        and abs(start.source_frame - previous.source_frame)
        <= int(profile["velocity_anchor_max_frames"])
    ):
        dt = (start.source_frame - previous.source_frame)
        velocity = (
            (float(start.x) - float(previous.x)) / dt,
            (float(start.y) - float(previous.y)) / dt,
        )
    diameter = float(start.box_diagonal or 0.0)
    missed = 0
    while missed < int(profile["maximum_missed_pages"]):
        index += direction
        if not 0 <= index < len(frames):
            break
        frame = frames[index]
        if frame in stop_frames:
            break
        steps = frame - last[0]
        predicted = (last[1] + velocity[0] * steps, last[2] + velocity[1] * steps)
        found = page(frame, last, predicted, abs(steps), diameter)
        if found is None:
            missed += 1
            continue
        missed = 0
        proposals[frame] = found
        velocity = ((found[0] - last[1]) / steps, (found[1] - last[2]) / steps)
        last = (frame, found[0], found[1])
        if found[2] > 0:
            diameter = found[2]
    return proposals


def _confirm_flipbook_time_machine(
    ledger: FrameLedger,
    *,
    records_by_frame: dict[int, dict[str, Any]],
    video: Path,
    model_path: Path,
    fps: float,
    max_speed_pixels_per_second: float,
    model: Any | None = None,
    color_frames: dict[int, np.ndarray] | None = None,
) -> FrameLedger:
    profile = FLIPBOOK_PROFILE
    frames = sorted(ledger.entries)
    unresolved = set(ledger.unresolved_frames())
    anchors = [
        entry for entry in ledger.confirmed_entries()
        if entry.x is not None and entry.y is not None
        and entry.confirming_module in FLIPBOOK_ANCHOR_MODULES
    ]
    if not anchors or not unresolved:
        return ledger
    if model is None:
        from ultralytics import YOLO

        model = YOLO(str(model_path))
    if color_frames is None:
        color_frames = _read_sampled_color_frames(video, unresolved)
    static_spots = _flipbook_static_spots(records_by_frame, fps)
    confirmed_frames = {entry.source_frame for entry in anchors}
    page_cache: dict[tuple, Any] = {}

    def acceptable(frame, x, y, size, reference, last, steps):
        if hypot(x - last[1], y - last[2]) > max_speed_pixels_per_second * steps / fps:
            return False
        if reference > 0 and size > 0 and not (
            float(profile["minimum_diameter_ratio"])
            <= size / reference
            <= float(profile["maximum_diameter_ratio"])
        ):
            return False
        if any(
            hypot(x - sx, y - sy) <= float(profile["static_radius_pixels"])
            for sx, sy in static_spots
        ):
            return False
        point = BallPoint(
            source_frame=frame, clip_seconds=frame / fps, confidence=0.0,
            x=x, y=y, box_diagonal=size,
        )
        return not _inside_player_upper_body(point, records_by_frame.get(frame, {}))

    def page(frame, last, predicted, steps, reference):
        record = records_by_frame.get(frame, {})
        half = min(
            float(profile["window_max_half_size_pixels"]),
            float(profile["window_base_half_size_pixels"])
            + float(profile["window_growth_pixels_per_second"]) * steps / fps,
        )
        detections = record.get("detections", [])
        cached = [
            ((d["x1"] + d["x2"]) / 2, (d["y1"] + d["y2"]) / 2,
             hypot(d["x2"] - d["x1"], d["y2"] - d["y1"]), float(d["confidence"]))
            for d in detections
            if d.get("class_name") == "sports ball"
            and float(d["confidence"]) >= float(profile["minimum_confidence"])
        ]
        image = color_frames.get(frame)

        def best_near(center, radius, extra):
            options = [
                c for c in cached + extra
                if abs(c[0] - center[0]) <= radius and abs(c[1] - center[1]) <= radius
                and acceptable(frame, c[0], c[1], c[2], reference, last, steps)
            ]
            if not options:
                return None
            return min(options, key=lambda c: hypot(c[0] - center[0], c[1] - center[1]))

        key = (frame, round(predicted[0]), round(predicted[1]), round(half))
        if key not in page_cache:
            page_cache[key] = (
                _flipbook_detect(model, image, [
                    (predicted[0], predicted[1], crop)
                    for crop in profile["detection_crop_half_sizes"]
                ])
                if image is not None else []
            )
        found = best_near(predicted, half, page_cache[key])
        if found is not None:
            return found
        reach = max_speed_pixels_per_second * steps / fps
        players = sorted(
            (
                ((d["x1"] + d["x2"]) / 2, float(d["y2"]))
                for d in detections
                if d.get("class_name") == "person"
                and float(d["confidence"]) >= float(profile["player_minimum_confidence"])
                and hypot((d["x1"] + d["x2"]) / 2 - last[1], float(d["y2"]) - last[2]) <= reach
            ),
            key=lambda feet: hypot(feet[0] - predicted[0], feet[1] - predicted[1]),
        )[: int(profile["players_searched"])]
        feet_half = float(profile["player_feet_half_size_pixels"])
        for feet in players:
            key = (frame, round(feet[0]), round(feet[1]), round(feet_half))
            if key not in page_cache:
                page_cache[key] = (
                    _flipbook_detect(model, image, [(feet[0], feet[1], feet_half)])
                    if image is not None else []
                )
            found = best_near(feet, feet_half, page_cache[key])
            if found is not None:
                return found
        return None

    by_frame = {entry.source_frame: entry for entry in anchors}
    forward: dict[int, tuple] = {}
    backward: dict[int, tuple] = {}
    ordered = sorted(by_frame)
    for position, frame in enumerate(ordered):
        entry = by_frame[frame]
        index = frames.index(frame)
        if index + 1 < len(frames) and frames[index + 1] in unresolved:
            earlier = by_frame.get(ordered[position - 1]) if position > 0 else None
            for f, found in _flipbook_walk(
                entry, earlier, 1, frames=frames,
                stop_frames=confirmed_frames, page=page,
            ).items():
                forward.setdefault(f, found)
        if index > 0 and frames[index - 1] in unresolved:
            later = by_frame.get(ordered[position + 1]) if position + 1 < len(ordered) else None
            for f, found in _flipbook_walk(
                entry, later, -1, frames=frames,
                stop_frames=confirmed_frames, page=page,
            ).items():
                backward.setdefault(f, found)

    for frame in sorted(unresolved):
        a, b = forward.get(frame), backward.get(frame)
        if a is None and b is None:
            ledger.reject(frame, FLIPBOOK_MODULE, "flipbook_found_no_candidate")
            continue
        if a is not None and b is not None:
            tolerance = float(profile["agreement_diameters"]) * max(
                a[2], b[2], MINIMUM_BALL_DIAMETER_PIXELS
            )
            if hypot(a[0] - b[0], a[1] - b[1]) > tolerance:
                ledger.reject(frame, FLIPBOOK_MODULE, "flipbook_directions_disagree")
                continue
        chosen = a if a is not None else b
        if _off_bracketed_path(frame, chosen, by_frame, ordered, profile):
            ledger.reject(frame, FLIPBOOK_MODULE, "flipbook_off_bracketed_path")
            continue
        record = records_by_frame.get(frame, {})
        ledger.confirm(
            frame,
            x=chosen[0],
            y=chosen[1],
            confirming_module=FLIPBOOK_MODULE,
            evidence={
                "detector_confidence": chosen[3],
                "forward": a is not None,
                "backward": b is not None,
            },
            confidence=chosen[3],
            clip_seconds=float(record.get("clip_seconds", frame / fps)),
            box_diagonal=chosen[2],
            point_evidence="flipbook_detector",
            point_source_attribution="yolo26_focused_multiscale",
        )
    return ledger


