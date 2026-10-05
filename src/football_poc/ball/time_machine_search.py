from __future__ import annotations

from .settings import *  # noqa: F401,F403


TIME_MACHINE_SEARCH_MODULE = "06_time_machine_region_search"

# The time machine says where the ball can be: within reach, at the maximum
# ball speed, of the confirmed frames before and after. This module looks for
# the ball there with the detector at full resolution, so a small ball is not
# shrunk away. It only confirms a real detection inside that region; when it
# finds nothing the frame stays for the time machine to estimate.
TIME_MACHINE_SEARCH_PROFILE = FrozenProfile({
    "maximum_region_half_size_pixels": 480.0,
    "minimum_region_half_size_pixels": 48.0,
    "tile_size_pixels": 640,
    # Checked against the video: region detections below 0.5 were mostly
    # coloured boots and pitch markings, so only strong detections count.
    "minimum_detector_confidence": 0.5,
    "minimum_diameter_ratio": 0.5,
    "maximum_diameter_ratio": 2.0,
    "maximum_passes": 3,
    "research_shrink_ratio": 0.7,
})


@dataclass(frozen=True)
class _SearchRegion:
    center_x: float
    center_y: float
    half_size: float
    anchors: tuple[Any, ...]
    reference_diameter: float


def _time_machine_search_region(
    ledger: FrameLedger,
    frame: int,
    *,
    fps: float,
    width: int,
    height: int,
    max_speed_pixels_per_second: float,
) -> _SearchRegion | None:
    previous, following = _confirmed_bracket(ledger.confirmed_entries(), frame)
    anchors = tuple(entry for entry in (previous, following) if entry is not None)
    if not anchors or fps <= 0:
        return None
    reaches = [
        max_speed_pixels_per_second * abs(frame - anchor.source_frame) / fps
        for anchor in anchors
    ]
    if previous is not None and following is not None:
        span = following.source_frame - previous.source_frame
        alpha = (frame - previous.source_frame) / span
        center_x = float(previous.x) + (float(following.x) - float(previous.x)) * alpha
        center_y = float(previous.y) + (float(following.y) - float(previous.y)) * alpha
    else:
        center_x = float(anchors[0].x)
        center_y = float(anchors[0].y)
    profile = TIME_MACHINE_SEARCH_PROFILE
    half_size = max(
        float(profile["minimum_region_half_size_pixels"]),
        min(reaches),
    )
    if half_size > float(profile["maximum_region_half_size_pixels"]):
        return None
    diameters = [
        float(anchor.box_diagonal)
        for anchor in anchors
        if anchor.box_diagonal and anchor.box_diagonal > 0
    ]
    return _SearchRegion(
        center_x=min(max(center_x, 0.0), float(width - 1)),
        center_y=min(max(center_y, 0.0), float(height - 1)),
        half_size=half_size,
        anchors=anchors,
        reference_diameter=median(diameters) if diameters else 0.0,
    )


def _inside_reach_of_anchors(
    x: float,
    y: float,
    frame: int,
    region: _SearchRegion,
    *,
    fps: float,
    max_speed_pixels_per_second: float,
) -> bool:
    return all(
        hypot(x - float(anchor.x), y - float(anchor.y))
        <= max_speed_pixels_per_second * abs(frame - anchor.source_frame) / fps
        + max(region.reference_diameter, MINIMUM_BALL_DIAMETER_PIXELS)
        for anchor in region.anchors
    )


def _region_tiles(
    region: _SearchRegion,
    *,
    width: int,
    height: int,
) -> list[tuple[int, int, int, int]]:
    tile = int(TIME_MACHINE_SEARCH_PROFILE["tile_size_pixels"])
    left = max(0, int(region.center_x - region.half_size))
    right = min(width, int(region.center_x + region.half_size) + 1)
    top = max(0, int(region.center_y - region.half_size))
    bottom = min(height, int(region.center_y + region.half_size) + 1)
    tiles: list[tuple[int, int, int, int]] = []
    y = top
    while True:
        tile_top = max(0, min(y, bottom - tile))
        x = left
        while True:
            tile_left = max(0, min(x, right - tile))
            tiles.append(
                (
                    tile_left,
                    tile_top,
                    min(width, tile_left + tile),
                    min(height, tile_top + tile),
                )
            )
            if x + tile >= right:
                break
            x += tile
        if y + tile >= bottom:
            break
        y += tile
    return sorted(set(tiles))


def _detect_in_region(
    model: Any,
    image: np.ndarray,
    frame: int,
    region: _SearchRegion,
    *,
    ledger: FrameLedger,
    record: dict[str, Any],
    clip_seconds: float,
    fps: float,
    max_speed_pixels_per_second: float,
) -> BallPoint | None:
    profile = TIME_MACHINE_SEARCH_PROFILE
    height, width = image.shape[:2]
    tiles = _region_tiles(region, width=width, height=height)
    crops = [image[top:bottom, left:right] for left, top, right, bottom in tiles]
    results = model.predict(
        crops,
        imgsz=int(profile["tile_size_pixels"]),
        conf=float(profile["minimum_detector_confidence"]),
        verbose=False,
    )
    best: BallPoint | None = None
    for result, (left, top, _right, _bottom) in zip(results, tiles, strict=True):
        for box in result.boxes:
            if result.names[int(box.cls[0])] != "sports ball":
                continue
            x1, y1, x2, y2 = (float(value) for value in box.xyxy[0])
            x = left + (x1 + x2) / 2
            y = top + (y1 + y2) / 2
            diameter = hypot(x2 - x1, y2 - y1)
            if region.reference_diameter > 0 and not (
                float(profile["minimum_diameter_ratio"])
                <= diameter / region.reference_diameter
                <= float(profile["maximum_diameter_ratio"])
            ):
                continue
            if not _inside_reach_of_anchors(
                x,
                y,
                frame,
                region,
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            ):
                continue
            confidence = float(box.conf[0])
            candidate = BallPoint(
                source_frame=frame,
                clip_seconds=clip_seconds,
                confidence=round(confidence, 6),
                x=x,
                y=y,
                box_diagonal=diameter,
                evidence="time_machine_region_detector",
                source_attribution="yolo26_focused_multiscale",
            )
            if not _proposal_allowed_by_confirmed_neighbours(
                ledger,
                candidate,
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            ):
                continue
            if _inside_player_upper_body(candidate, record):
                continue
            if best is None or confidence > best.confidence:
                best = candidate
    return best


def _confirm_time_machine_region_search(
    ledger: FrameLedger,
    *,
    records_by_frame: dict[int, dict[str, Any]],
    video: Path,
    model_path: Path,
    fps: float,
    width: int,
    height: int,
    max_speed_pixels_per_second: float,
    model: Any | None = None,
    color_frames: dict[int, np.ndarray] | None = None,
) -> FrameLedger:
    """Search each unresolved frame inside its time-machine region.

    Frames with the smallest region go first; every new confirmation narrows
    the regions of its neighbours, so a pass can reach frames that were too
    uncertain before. A frame is searched again only after its region shrinks.
    """
    profile = TIME_MACHINE_SEARCH_PROFILE
    searchable = [
        frame
        for frame in ledger.unresolved_frames()
        if _time_machine_search_region(
            ledger,
            frame,
            fps=fps,
            width=width,
            height=height,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        )
        is not None
    ]
    if not searchable:
        return ledger
    if model is None:
        from football_poc.ball.predict_cache import load_ball_crop_model

        model = load_ball_crop_model(model_path)
    if color_frames is None:
        color_frames = _read_sampled_color_frames(video, ledger.unresolved_frames())
    searched: dict[int, float] = {}
    for _ in range(int(profile["maximum_passes"])):
        found = False
        regions = {
            frame: region
            for frame in ledger.unresolved_frames()
            if (
                region := _time_machine_search_region(
                    ledger,
                    frame,
                    fps=fps,
                    width=width,
                    height=height,
                    max_speed_pixels_per_second=max_speed_pixels_per_second,
                )
            )
            is not None
            and region.half_size
            < searched.get(frame, float("inf"))
            * float(profile["research_shrink_ratio"])
        }
        for frame in sorted(regions, key=lambda item: regions[item].half_size):
            region = _time_machine_search_region(
                ledger,
                frame,
                fps=fps,
                width=width,
                height=height,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            )
            image = color_frames.get(frame)
            if region is None or image is None:
                continue
            searched[frame] = region.half_size
            point = _detect_in_region(
                model,
                image,
                frame,
                region,
                ledger=ledger,
                record=records_by_frame.get(frame, {}),
                clip_seconds=float(
                    records_by_frame.get(frame, {}).get(
                        "clip_seconds",
                        frame / fps,
                    )
                ),
                fps=fps,
                max_speed_pixels_per_second=max_speed_pixels_per_second,
            )
            if point is None:
                ledger.reject(
                    frame,
                    TIME_MACHINE_SEARCH_MODULE,
                    "no_acceptable_detection_in_time_machine_region",
                )
                continue
            ledger.confirm(
                frame,
                x=point.x,
                y=point.y,
                confirming_module=TIME_MACHINE_SEARCH_MODULE,
                evidence={
                    "detector_confidence": point.confidence,
                    "search_region_center": [
                        round(region.center_x, 3),
                        round(region.center_y, 3),
                    ],
                    "search_region_half_size_pixels": round(region.half_size, 3),
                    "anchor_frames": [
                        anchor.source_frame for anchor in region.anchors
                    ],
                },
                confidence=point.confidence,
                clip_seconds=point.clip_seconds,
                box_diagonal=point.box_diagonal,
                point_evidence=point.evidence,
                point_source_attribution=point.source_attribution,
            )
            found = True
        if not found:
            break
    return ledger
