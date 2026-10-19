from __future__ import annotations

from .settings import *  # noqa: F401,F403
from math import atan2, degrees

from .dead_ball import departed_dead_ball


CONFIRM_YOLO_MODULE = "01_confirm_yolo"
LOCK_YOLO_CHAIN_MODULE = "00_lock_yolo_chains"

# Permanent locks come first and are never withdrawn. A single frame cannot
# separate the ball from boots, heads or pitch marks, so a YOLO box is locked
# only when it belongs to a long chain of YOLO boxes that moves like a ball:
# linked frame to frame within a speed limit and travelling a clear distance.
# Fixed pitch marks do not travel and isolated false positives do not chain.
# A frame where more than one box qualifies is left unresolved, never guessed.
LOCK_CHAIN_MINIMUM_CONFIDENCE = 0.10
LOCK_CHAIN_MAX_SPEED_PIXELS_PER_SECOND = 300.0
LOCK_CHAIN_MAX_MISSING_STEPS = 1
LOCK_CHAIN_MINIMUM_BOXES = 8
LOCK_CHAIN_MINIMUM_TRAVEL_PIXELS = 40.0
# Two still objects (heads in a stand, cones) a short hop apart can link into
# one chain whose ends are far apart. A ball travels over several steps, so a
# chain whose travel is mostly one jump is not locked.
LOCK_CHAIN_MAXIMUM_SINGLE_STEP_SHARE = 0.5
# A box on the chain's constant-velocity course may link from up to this
# share of the plain link limit away from the chain's last box.
LOCK_CHAIN_PREDICTED_REACH_SHARE = 1.5
# A chain's last box below this detector confidence is not locked when it has
# left the chain's constant-velocity course by more than the link limit.
LOCK_CHAIN_TAIL_MINIMUM_CONFIDENCE = 0.5
# A boot moves with a running player and so also leaves a long moving chain of
# YOLO boxes. Its colour, unlike the ball's, stays outside the ball colour
# learned from this video's confident detections. A chain whose typical colour
# is clearly outside that range is not locked; the ball's own chains vary
# around the range edge by lighting and motion blur only.
LOCK_CHAIN_COLOUR_MARGIN = 10.0


def _off_colour_chains(
    chains: dict[int, list[tuple[int, dict[str, Any]]]],
    video: Path,
    colour_range: tuple[float, float],
) -> set[int]:
    points = {
        (frame, box["x"], box["y"]): BallPoint(
            frame, 0.0, box["confidence"], box["x"], box["y"],
            box_diagonal=box["diagonal"],
        )
        for chain in chains.values()
        for frame, box in chain
    }
    by_frame: dict[int, list[BallPoint]] = defaultdict(list)
    for point in points.values():
        by_frame[point.source_frame].append(point)
    chroma = _read_standout_chroma(video, by_frame)
    colour_low, colour_high = colour_range
    off_colour = set()
    for chain_index, chain in chains.items():
        samples = [
            chroma.get((frame, float(box["x"]), float(box["y"])))
            for frame, box in chain
        ]
        samples = [sample for sample in samples if sample is not None]
        if len(samples) * 2 < len(chain):
            continue
        typical = float(np.median(samples))
        if (
            typical < colour_low - LOCK_CHAIN_COLOUR_MARGIN
            or typical > colour_high + LOCK_CHAIN_COLOUR_MARGIN
        ):
            off_colour.add(chain_index)
    return off_colour


def _lock_chain_predicted_distance(
    box: dict[str, Any], previous: dict[str, Any]
) -> float | None:
    """Distance from a box to where the chain ending at ``previous`` would be
    at the box's frame if it kept its last velocity. A rolling ball keeps its
    course, so a box on that course is the same ball even when one sample's
    travel is a little above the plain link limit."""
    before = previous.get("previous")
    if before is None:
        return None
    span = previous["frame"] - before["frame"]
    ahead = box["frame"] - previous["frame"]
    if span <= 0 or ahead <= 0:
        return None
    scale = ahead / span
    return hypot(
        box["x"] - (previous["x"] + (previous["x"] - before["x"]) * scale),
        box["y"] - (previous["y"] + (previous["y"] - before["y"]) * scale),
    )


def _lock_chain_weak_tail_off_course(
    chain: list[tuple[int, dict[str, Any]]], step_seconds: float, frame_step: int
) -> bool:
    """A chain's last box is unsafe to lock when it is a weak detection that
    has left the course the chain was on. The ball may have been played, but
    the weak box may as well be a boot beside it; later steps decide it."""
    frame, box = chain[-1]
    if box["confidence"] >= LOCK_CHAIN_TAIL_MINIMUM_CONFIDENCE:
        return False
    predicted = _lock_chain_predicted_distance(box, chain[-2][1])
    if predicted is None:
        return False
    steps = max(1, round((frame - chain[-2][0]) / frame_step))
    limit = LOCK_CHAIN_MAX_SPEED_PIXELS_PER_SECOND * step_seconds * steps
    return predicted > limit


def _lock_moving_yolo_chains(
    ledger: FrameLedger,
    *,
    records_by_frame: dict[int, dict[str, Any]],
    fps: float,
    frame_step: int,
    video: Path | None = None,
    ball_colour_range: tuple[float, float] | None = None,
) -> FrameLedger:
    step_seconds = frame_step / fps
    boxes_by_frame: dict[int, list[dict[str, Any]]] = {}
    for frame in sorted(records_by_frame):
        boxes = []
        for detection in records_by_frame[frame].get("detections", []):
            if detection.get("class_name") != "sports ball":
                continue
            confidence = float(detection.get("confidence", 0.0))
            if confidence < LOCK_CHAIN_MINIMUM_CONFIDENCE:
                continue
            x1, y1 = float(detection["x1"]), float(detection["y1"])
            x2, y2 = float(detection["x2"]), float(detection["y2"])
            boxes.append(
                {
                    "x": (x1 + x2) / 2,
                    "y": (y1 + y2) / 2,
                    "diagonal": hypot(x2 - x1, y2 - y1),
                    "confidence": confidence,
                    "chain": None,
                    "linked": False,
                    "frame": frame,
                    "previous": None,
                }
            )
        boxes.sort(key=lambda box: -box["confidence"])
        boxes_by_frame[frame] = boxes

    chains: list[list[tuple[int, dict[str, Any]]]] = []
    for frame, boxes in boxes_by_frame.items():
        for box in boxes:
            best: tuple[float, dict[str, Any]] | None = None
            for steps in range(1, LOCK_CHAIN_MAX_MISSING_STEPS + 2):
                limit = LOCK_CHAIN_MAX_SPEED_PIXELS_PER_SECOND * step_seconds * steps
                for previous in boxes_by_frame.get(frame - steps * frame_step, []):
                    if previous["linked"]:
                        continue
                    distance = hypot(
                        box["x"] - previous["x"], box["y"] - previous["y"]
                    )
                    predicted = _lock_chain_predicted_distance(box, previous)
                    if predicted is not None and distance <= (
                        LOCK_CHAIN_PREDICTED_REACH_SHARE * limit
                    ):
                        distance = min(distance, predicted)
                    if distance <= limit and (best is None or distance < best[0]):
                        best = (distance, previous)
            if best is not None:
                best[1]["linked"] = True
                box["previous"] = best[1]
                box["chain"] = best[1]["chain"]
            else:
                box["chain"] = len(chains)
                chains.append([])
            chains[box["chain"]].append((frame, box))

    moving_chains: dict[int, list[tuple[int, dict[str, Any]]]] = {}
    for chain_index, chain in enumerate(chains):
        while len(chain) >= 3 and _lock_chain_weak_tail_off_course(
            chain, step_seconds, frame_step
        ):
            chain.pop()
        if len(chain) < LOCK_CHAIN_MINIMUM_BOXES:
            continue
        first, last = chain[0][1], chain[-1][1]
        travel = hypot(last["x"] - first["x"], last["y"] - first["y"])
        if travel < LOCK_CHAIN_MINIMUM_TRAVEL_PIXELS:
            continue
        steps = [
            hypot(second["x"] - first_box["x"], second["y"] - first_box["y"])
            for (_, first_box), (_, second) in zip(chain, chain[1:])
        ]
        if max(steps) > LOCK_CHAIN_MAXIMUM_SINGLE_STEP_SHARE * sum(steps):
            continue
        moving_chains[chain_index] = chain
    off_colour = (
        _off_colour_chains(moving_chains, video, ball_colour_range)
        if video is not None and ball_colour_range is not None and moving_chains
        else set()
    )
    qualifying: dict[int, list[tuple[dict[str, Any], int]]] = defaultdict(list)
    for chain_index, chain in moving_chains.items():
        if chain_index in off_colour:
            for frame, _ in chain:
                if frame in ledger.entries and ledger.confirmed(frame) is None:
                    ledger.reject(
                        frame, LOCK_YOLO_CHAIN_MODULE, "chain_colour_differs_from_ball"
                    )
            continue
        for frame, box in chain:
            qualifying[frame].append((box, chain_index))

    entries = ledger.entries
    for frame, found in sorted(qualifying.items()):
        if frame not in entries or ledger.confirmed(frame) is not None:
            continue
        if len(found) != 1:
            ledger.reject(frame, LOCK_YOLO_CHAIN_MODULE, "several_moving_chains")
            continue
        box, chain_index = found[0]
        chain = chains[chain_index]
        ledger.confirm(
            frame,
            x=box["x"],
            y=box["y"],
            confirming_module=LOCK_YOLO_CHAIN_MODULE,
            evidence={
                "detector_confidence": box["confidence"],
                "chain_boxes": len(chain),
                "chain_first_frame": chain[0][0],
                "chain_last_frame": chain[-1][0],
                "permanent_lock": True,
            },
            confidence=box["confidence"],
            box_diagonal=box["diagonal"],
        )
    return ledger


# A fast ball blurs: YOLO then sees it only now and then, weakly, and its
# blurred colour no longer looks like the ball, so single-frame checks drop
# every box. Together the boxes still betray it: a ball keeps its course, so
# its boxes line up in one direction at a steady speed. Inside a gap where no
# ball is confirmed at all, such a chain is the ball when both confirmed ends
# of the gap can reach it. Three boxes line up by chance in clutter; four on
# one steady course do not. Fixed spots and a second competing chain in the
# same gap leave the gap to later steps.
STEADY_CHAIN_MINIMUM_BOXES = 4
STEADY_CHAIN_MAXIMUM_SKIPPED_SAMPLES = 2
STEADY_CHAIN_MINIMUM_SPEED_PIXELS_PER_SECOND = 150.0
STEADY_CHAIN_MAXIMUM_TURN_DEGREES = 20.0
STEADY_CHAIN_MAXIMUM_SPEED_RATIO = 2.0
STEADY_CHAIN_STATIC_RADIUS_PIXELS = 12.0
STEADY_CHAIN_STATIC_WINDOW_FRAMES = 250
STEADY_CHAIN_STATIC_MINIMUM_SAMPLES = 12


def _steady_course_chains(
    boxes_by_frame: Mapping[int, list[dict[str, Any]]],
    *,
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
) -> list[list[dict[str, Any]]]:
    minimum = STEADY_CHAIN_MINIMUM_SPEED_PIXELS_PER_SECOND / fps
    maximum = max_speed_pixels_per_second / fps
    reach = STEADY_CHAIN_MAXIMUM_SKIPPED_SAMPLES + 1
    found: list[list[dict[str, Any]]] = []
    for frame in sorted(boxes_by_frame):
        for first in boxes_by_frame[frame]:
            for samples in range(1, reach + 1):
                for second in boxes_by_frame.get(frame + samples * frame_step, []):
                    elapsed = second["frame"] - first["frame"]
                    speed = hypot(second["x"] - first["x"], second["y"] - first["y"]) / elapsed
                    if not minimum <= speed <= maximum:
                        continue
                    chain = [first, second]
                    while True:
                        before, last = chain[-2], chain[-1]
                        span = last["frame"] - before["frame"]
                        vx = (last["x"] - before["x"]) / span
                        vy = (last["y"] - before["y"]) / span
                        last_speed = hypot(vx, vy)
                        best: tuple[float, dict[str, Any]] | None = None
                        for ahead in range(1, reach + 1):
                            for box in boxes_by_frame.get(last["frame"] + ahead * frame_step, []):
                                elapsed = box["frame"] - last["frame"]
                                nx = (box["x"] - last["x"]) / elapsed
                                ny = (box["y"] - last["y"]) / elapsed
                                next_speed = hypot(nx, ny)
                                if not minimum <= next_speed <= maximum:
                                    continue
                                ratio = next_speed / last_speed
                                if not (
                                    1 / STEADY_CHAIN_MAXIMUM_SPEED_RATIO
                                    <= ratio
                                    <= STEADY_CHAIN_MAXIMUM_SPEED_RATIO
                                ):
                                    continue
                                turn = abs(
                                    degrees(atan2(vx * ny - vy * nx, vx * nx + vy * ny))
                                )
                                if turn > STEADY_CHAIN_MAXIMUM_TURN_DEGREES:
                                    continue
                                error = hypot(
                                    box["x"] - (last["x"] + vx * elapsed),
                                    box["y"] - (last["y"] + vy * elapsed),
                                )
                                if best is None or error < best[0]:
                                    best = (error, box)
                            if best is not None:
                                break
                        if best is None:
                            break
                        chain.append(best[1])
                    if len(chain) >= STEADY_CHAIN_MINIMUM_BOXES:
                        found.append(chain)
    return found


def _confirm_steady_course_chains(
    ledger: FrameLedger,
    *,
    records_by_frame: Mapping[int, dict[str, Any]],
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
) -> FrameLedger:
    if fps <= 0 or frame_step < 1:
        return ledger
    boxes_by_frame: dict[int, list[dict[str, Any]]] = {}
    for frame, record in records_by_frame.items():
        if frame % frame_step:
            continue
        boxes = []
        for detection in record.get("detections", []):
            if detection.get("class_name") != "sports ball":
                continue
            confidence = float(detection.get("confidence", 0.0))
            if confidence < LOCK_CHAIN_MINIMUM_CONFIDENCE:
                continue
            x1, y1 = float(detection["x1"]), float(detection["y1"])
            x2, y2 = float(detection["x2"]), float(detection["y2"])
            boxes.append(
                {
                    "frame": frame,
                    "x": (x1 + x2) / 2,
                    "y": (y1 + y2) / 2,
                    "diagonal": hypot(x2 - x1, y2 - y1),
                    "confidence": confidence,
                }
            )
        boxes_by_frame[frame] = boxes

    def fixed_spot(box: dict[str, Any]) -> bool:
        seen = sum(
            1
            for frame, boxes in boxes_by_frame.items()
            if abs(frame - box["frame"]) <= STEADY_CHAIN_STATIC_WINDOW_FRAMES
            and any(
                hypot(other["x"] - box["x"], other["y"] - box["y"])
                < STEADY_CHAIN_STATIC_RADIUS_PIXELS
                for other in boxes
            )
        )
        return seen >= STEADY_CHAIN_STATIC_MINIMUM_SAMPLES

    confirmed = sorted(
        frame
        for frame, entry in ledger.entries.items()
        if entry.status == "confirmed" and entry.x is not None and entry.y is not None
    )

    def gap_ends(chain: list[dict[str, Any]]) -> tuple[int, int] | None:
        first, last = chain[0]["frame"], chain[-1]["frame"]
        before = [frame for frame in confirmed if frame < first]
        after = [frame for frame in confirmed if frame > last]
        if not before or not after:
            return None
        if any(first <= frame <= last for frame in confirmed):
            return None
        return before[-1], after[0]

    qualifying: list[tuple[list[dict[str, Any]], tuple[int, int]]] = []
    for chain in _steady_course_chains(
        boxes_by_frame,
        fps=fps,
        frame_step=frame_step,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    ):
        ends = gap_ends(chain)
        if ends is None or any(box["frame"] not in ledger.entries for box in chain):
            continue
        reachable = all(
            hypot(
                box["x"] - float(ledger.entries[end].x),
                box["y"] - float(ledger.entries[end].y),
            )
            <= max_speed_pixels_per_second * abs(box["frame"] - end) / fps
            for box, end in ((chain[0], ends[0]), (chain[-1], ends[1]))
        )
        if not reachable or any(fixed_spot(box) for box in chain):
            continue
        qualifying.append((chain, ends))

    # A chain found from a later start is part of a longer one; keep the
    # longest. Two different chains in one gap leave the gap undecided.
    members = [{id(box) for box in chain} for chain, _ in qualifying]
    kept = [
        (chain, ends)
        for index, (chain, ends) in enumerate(qualifying)
        if not any(
            other != index and members[index] < members[other]
            for other in range(len(qualifying))
        )
    ]
    by_gap: dict[tuple[int, int], list[list[dict[str, Any]]]] = defaultdict(list)
    for chain, ends in kept:
        if chain not in by_gap[ends]:
            by_gap[ends].append(chain)
    for chains in by_gap.values():
        if len(chains) != 1:
            continue
        chain = chains[0]
        for box in chain:
            ledger.confirm(
                box["frame"],
                x=box["x"],
                y=box["y"],
                confirming_module=CONFIRM_YOLO_MODULE,
                evidence={
                    "detector_confidence": box["confidence"],
                    "steady_course_chain": True,
                    "chain_boxes": len(chain),
                    "chain_first_frame": chain[0]["frame"],
                    "chain_last_frame": chain[-1]["frame"],
                },
                confidence=box["confidence"],
                box_diagonal=box["diagonal"],
            )
    return ledger


def _merge_independent_module(
    ledger: FrameLedger,
    module_ledger: FrameLedger,
    module: str,
) -> FrameLedger:
    """Copy a module's decisions, made on its own fresh ledger, into frames
    that are still unresolved. Permanent locks are never overwritten; where the
    module disagrees with a lock, the lock wins and the disagreement is kept as
    a rejection reason."""
    for frame, entry in module_ledger.entries.items():
        current = ledger.confirmed(frame)
        if entry.status == "confirmed" and entry.confirming_module == module:
            if current is None:
                ledger.confirm(
                    frame,
                    x=float(entry.x),
                    y=float(entry.y),
                    confirming_module=module,
                    evidence=dict(entry.evidence or {}),
                    confidence=float(entry.confidence or 0.0),
                    clip_seconds=entry.clip_seconds,
                    box_diagonal=entry.box_diagonal,
                    point_evidence=entry.point_evidence,
                    point_source_attribution=entry.point_source_attribution,
                    temporal_score=entry.temporal_score,
                )
            continue
        for reason in entry.rejection_reasons:
            if reason.get("module") == module:
                ledger.reject(frame, module, reason.get("reason", ""))
    return ledger

# A ball seen resting at the same spot on both sides of a short window cannot
# have been somewhere else in between: leaving and being returned to rest at the
# same spot needs several touches, which the evidence does not show.
RESTING_BALL_WINDOW_SECONDS = 3.0
RESTING_BALL_RADIUS_DIAMETERS = 3.0
MINIMUM_BALL_DIAMETER_PIXELS = 8.0


# A weak detection at a player's feet can be a boot: boots are close to the
# ball in size and shape. The pixels that stand out from the surrounding grass
# must then have the ball's colour, learned from this video's own strong
# detections. Without enough strong detections there is no colour evidence and
# the check does not apply.
BALL_COLOUR_STRONG_CONFIDENCE = 0.5
BALL_COLOUR_WEAK_CONFIDENCE = 0.25
BALL_COLOUR_MINIMUM_SAMPLES = 5
BALL_COLOUR_CORE_DIAMETERS = 0.4
BALL_COLOUR_MINIMUM_CHROMA_DISTANCE = 12.0
BALL_COLOUR_RANGE_PERCENTILES = (5.0, 95.0)
BALL_COLOUR_MINIMUM_HALF_RANGE = 5.0
# A confident box can still be a brightly coloured boot. Its colour is then
# far outside the ball's learned range, further than lighting and motion blur
# move a real ball, so detector confidence does not excuse it.
BALL_COLOUR_FAR_MARGIN = 20.0


def _standout_chroma(
    frame: np.ndarray,
    x: float,
    y: float,
    diameter: float,
) -> float | None:
    """Red-green (Lab a) colour of the pixels whose colour differs from grass.

    Brightness is ignored: lighter grass, lines and shadows differ from the
    grass in brightness, not in colour.
    """
    diameter = max(diameter, MINIMUM_BALL_DIAMETER_PIXELS)
    half = int(np.ceil(diameter * 5))
    center_x = round(x)
    center_y = round(y)
    if (
        center_y - half < 0
        or center_x - half < 0
        or center_y + half + 1 > frame.shape[0]
        or center_x + half + 1 > frame.shape[1]
    ):
        return None
    window = frame[
        center_y - half : center_y + half + 1,
        center_x - half : center_x + half + 1,
    ]
    lab = cv2.cvtColor(window, cv2.COLOR_BGR2LAB).astype(np.float32)
    offsets_y, offsets_x = np.mgrid[-half : half + 1, -half : half + 1]
    distance = np.hypot(offsets_x, offsets_y)
    grass = np.median(
        lab[(distance >= diameter * 2.5) & (distance <= diameter * 5)],
        axis=0,
    )
    chroma_distance = np.hypot(lab[..., 1] - grass[1], lab[..., 2] - grass[2])
    standout = (distance <= diameter * BALL_COLOUR_CORE_DIAMETERS) & (
        chroma_distance >= BALL_COLOUR_MINIMUM_CHROMA_DISTANCE
    )
    if int(standout.sum()) < 2:
        return None
    strongest = chroma_distance[standout] >= np.median(chroma_distance[standout])
    return float(np.median(lab[..., 1][standout][strongest]))


def _read_standout_chroma(
    video: Path,
    points_by_frame: dict[int, list[BallPoint]],
) -> dict[tuple[int, float, float], float | None]:
    chroma: dict[tuple[int, float, float], float | None] = {}
    if not points_by_frame:
        return chroma
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        for source_frame in range(max(points_by_frame) + 1):
            points = points_by_frame.get(source_frame)
            if not points:
                if not capture.grab():
                    raise RuntimeError(
                        f"Could not skip to source frame {source_frame} in {video}"
                    )
                continue
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(
                    f"Could not read source frame {source_frame} from {video}"
                )
            for point in points:
                chroma[(source_frame, float(point.x), float(point.y))] = (
                    _standout_chroma(
                        frame,
                        float(point.x),
                        float(point.y),
                        float(point.box_diagonal or 0.0),
                    )
                )
    finally:
        capture.release()
    return chroma


def _ball_colour_range(
    samples: Iterable[float | None],
) -> tuple[float, float] | None:
    """Learned ball colour range from strong detections' stand-out colour."""
    samples = [sample for sample in samples if sample is not None]
    if len(samples) < BALL_COLOUR_MINIMUM_SAMPLES:
        return None
    colour_low, colour_high = np.percentile(samples, BALL_COLOUR_RANGE_PERCENTILES)
    # Video compression alone shifts the colour slightly.
    centre = float(np.median(samples))
    return (
        min(float(colour_low), centre - BALL_COLOUR_MINIMUM_HALF_RANGE),
        max(float(colour_high), centre + BALL_COLOUR_MINIMUM_HALF_RANGE),
    )


def _learned_ball_colour_range(
    detector_points: Iterable[BallPoint],
    video: Path,
) -> tuple[float, float] | None:
    """Ball colour range learned from every confident detector box in the video."""
    strong = [
        point
        for point in detector_points
        if point.source_attribution == "yolo26_observed"
        and point.confidence >= BALL_COLOUR_STRONG_CONFIDENCE
    ]
    if len(strong) < BALL_COLOUR_MINIMUM_SAMPLES:
        return None
    points_by_frame: dict[int, list[BallPoint]] = defaultdict(list)
    for point in strong:
        points_by_frame[point.source_frame].append(point)
    chroma = _read_standout_chroma(video, points_by_frame)
    return _ball_colour_range(
        chroma[(point.source_frame, float(point.x), float(point.y))]
        for point in strong
    )


def _ball_colour_check(
    detector_points: Iterable[BallPoint],
    points_to_check: Iterable[BallPoint],
    video: Path,
) -> Any:
    """Colour test for ``points_to_check`` against the strong detections.

    Returns ``None`` when the video has too few strong detections to learn
    the ball colour.
    """
    strong = [
        point
        for point in detector_points
        if point.source_attribution == "yolo26_observed"
        and point.confidence >= BALL_COLOUR_STRONG_CONFIDENCE
    ]
    if len(strong) < BALL_COLOUR_MINIMUM_SAMPLES:
        return None
    points_by_frame: dict[int, list[BallPoint]] = defaultdict(list)
    for point in [*strong, *points_to_check]:
        points_by_frame[point.source_frame].append(point)
    chroma = _read_standout_chroma(video, points_by_frame)
    samples = [
        chroma[(point.source_frame, float(point.x), float(point.y))]
        for point in strong
    ]
    colour_range = _ball_colour_range(samples)
    if colour_range is None:
        return None
    colour_low, colour_high = colour_range

    def matches(point: BallPoint) -> bool:
        sample = chroma.get((point.source_frame, float(point.x), float(point.y)))
        if sample is None:
            # Nothing stands out from the grass: no boot or ball colour to
            # compare, so colour is not evidence either way.
            return True
        return bool(colour_low <= sample <= colour_high)

    def far_from_ball(point: BallPoint) -> bool:
        sample = chroma.get((point.source_frame, float(point.x), float(point.y)))
        if sample is None:
            return False
        return bool(
            sample < colour_low - BALL_COLOUR_FAR_MARGIN
            or sample > colour_high + BALL_COLOUR_FAR_MARGIN
        )

    matches.far_from_ball = far_from_ball
    return matches


GRASS_CONTRAST_FRACTION_OF_STRONG = 0.55
GRASS_CONTRAST_BLUR_DIAGONALS = 1.5


def _grass_contrast(frame: np.ndarray, x: float, y: float, diameter: float) -> float | None:
    """How strongly the box centre differs in colour (any colour) from grass.

    Brightness is ignored, so lighter grass, shadows and pitch texture score
    low whatever the ball's own colour is.
    """
    diameter = max(diameter, MINIMUM_BALL_DIAMETER_PIXELS)
    half = int(np.ceil(diameter * 5))
    center_x = round(x)
    center_y = round(y)
    if (
        center_y - half < 0
        or center_x - half < 0
        or center_y + half + 1 > frame.shape[0]
        or center_x + half + 1 > frame.shape[1]
    ):
        return None
    window = frame[
        center_y - half : center_y + half + 1,
        center_x - half : center_x + half + 1,
    ]
    lab = cv2.cvtColor(window, cv2.COLOR_BGR2LAB).astype(np.float32)
    offsets_y, offsets_x = np.mgrid[-half : half + 1, -half : half + 1]
    distance = np.hypot(offsets_x, offsets_y)
    grass = np.median(
        lab[(distance >= diameter * 2.5) & (distance <= diameter * 5)],
        axis=0,
    )
    chroma_distance = np.hypot(lab[..., 1] - grass[1], lab[..., 2] - grass[2])
    core = distance <= diameter * BALL_COLOUR_CORE_DIAMETERS
    return float(np.percentile(chroma_distance[core], 90))


def _grass_contrast_check(detector_points: Iterable[BallPoint], video: Path) -> Any:
    """Reject weak boxes that do not stand out from the grass in colour.

    The required contrast is learned from this video's strong detections, so
    no ball colour is assumed. Boxes much larger than a normal ball are motion
    blur, which dilutes contrast, and are not judged.
    """
    yolo = [p for p in detector_points if p.source_attribution == "yolo26_observed"]
    strong = [p for p in yolo if p.confidence >= BALL_COLOUR_STRONG_CONFIDENCE]
    weak = [p for p in yolo if p.confidence < BALL_COLOUR_WEAK_CONFIDENCE]
    if len(strong) < BALL_COLOUR_MINIMUM_SAMPLES or not weak:
        return None
    points_by_frame: dict[int, list[BallPoint]] = defaultdict(list)
    for point in [*strong, *weak]:
        points_by_frame[point.source_frame].append(point)
    contrast: dict[tuple[int, float, float], float | None] = {}
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open benchmark video: {video}")
        for source_frame in range(max(points_by_frame) + 1):
            points = points_by_frame.get(source_frame)
            if not points:
                if not capture.grab():
                    raise RuntimeError(f"Could not skip to source frame {source_frame} in {video}")
                continue
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"Could not read source frame {source_frame} from {video}")
            for point in points:
                contrast[(source_frame, float(point.x), float(point.y))] = _grass_contrast(
                    frame, float(point.x), float(point.y), float(point.box_diagonal or 0.0)
                )
    finally:
        capture.release()
    strong_contrast = [
        value
        for point in strong
        if (value := contrast[(point.source_frame, float(point.x), float(point.y))]) is not None
    ]
    if len(strong_contrast) < BALL_COLOUR_MINIMUM_SAMPLES:
        return None
    minimum = float(np.median(strong_contrast)) * GRASS_CONTRAST_FRACTION_OF_STRONG
    strong_diagonals = [p.box_diagonal for p in strong if p.box_diagonal]
    blur_diagonal = (
        float(np.median(strong_diagonals)) * GRASS_CONTRAST_BLUR_DIAGONALS
        if strong_diagonals
        else float("inf")
    )

    def stands_out(point: BallPoint) -> bool:
        if (point.box_diagonal or 0.0) > blur_diagonal:
            return True
        value = contrast.get((point.source_frame, float(point.x), float(point.y)))
        return value is None or value >= minimum

    return stands_out


def _weak_feet_candidates(
    candidates_by_frame: dict[int, list[_BallCandidate]],
) -> list[BallPoint]:
    return [
        candidate.point
        for candidates in candidates_by_frame.values()
        for candidate in candidates
        if candidate.near_player_feet
        and candidate.point.source_attribution == "yolo26_observed"
        and candidate.point.confidence < BALL_COLOUR_WEAK_CONFIDENCE
    ]


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
        all_points = [
            candidate.point
            for candidates in candidates_by_frame.values()
            for candidate in candidates
        ]
        if departed_dead_ball(
            (candidate.point for candidate in nearby),
            all_points=all_points,
            radius_pixels=radius_pixels,
            clip_end_seconds=max(p.clip_seconds for p in all_points),
        ):
            return None
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


# A short run of weak detections far off the line between the confirmed ball
# just before and just after it would need the ball to leave and come straight
# back within a fraction of a second. The detour allowance is a quarter of the
# maximum ball speed over the bracket. Over a longer gap the ball may wander
# further, but when the bracket says the ball moved slowly, a weak run that
# can only be reached or left at more than half the maximum speed is also a
# detour: the slow ball would need two hard kicks the detector never saw.
DETOUR_BRACKET_STEPS = 16
DETOUR_MAX_RUN_LENGTH = 2
DETOUR_ALLOWANCE_SPEED_FRACTION = 0.25
DETOUR_FAST_LEG_SPEED_FRACTION = 0.5


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
        worst: tuple[float, list[Any]] | None = None
        for frame, entry in confirmed.items():
            run = [entry]
            for offset in range(1, DETOUR_MAX_RUN_LENGTH):
                member = confirmed.get(frame + offset * frame_step)
                if member is None:
                    break
                run.append(member)
            for length in range(1, len(run) + 1):
                members = run[:length]
                if any(
                    member.confirming_module != CONFIRM_YOLO_MODULE
                    or not _is_movable_detection(member)
                    for member in members
                ):
                    break
                first, last = members[0].source_frame, members[-1].source_frame
                previous = next(
                    (
                        confirmed[first - offset * frame_step]
                        for offset in range(1, DETOUR_BRACKET_STEPS + 1)
                        if first - offset * frame_step in confirmed
                    ),
                    None,
                )
                following = next(
                    (
                        confirmed[last + offset * frame_step]
                        for offset in range(1, DETOUR_BRACKET_STEPS + 1)
                        if last + offset * frame_step in confirmed
                    ),
                    None,
                )
                if previous is None or following is None:
                    continue
                # Only detections weaker than a neighbour are the detour; when
                # both neighbours are weaker, they are the doubtful points.
                # A neighbour locked as a multi-frame detector chain is not
                # doubtful: agreement across frames outweighs one score. The
                # same holds for a neighbour that continues steady confirmed
                # motion.
                strongest_member = max(
                    float(member.confidence or 0.0) for member in members
                )
                if all(
                    neighbour.confirming_module != LOCK_YOLO_CHAIN_MODULE
                    and float(neighbour.confidence or 0.0) <= strongest_member
                    and not _continues_confirmed_momentum(
                        neighbour.source_frame,
                        float(neighbour.x),
                        float(neighbour.y),
                        confirmed,
                        frame_step=frame_step,
                    )
                    for neighbour in (previous, following)
                ):
                    continue
                elapsed = (following.source_frame - previous.source_frame) / fps
                direct = hypot(following.x - previous.x, following.y - previous.y)
                if direct > max_speed_pixels_per_second * 1.25 * elapsed:
                    continue
                path = [previous, *members, following]
                excess = (
                    sum(
                        hypot(b.x - a.x, b.y - a.y)
                        for a, b in zip(path, path[1:])
                    )
                    - direct
                )
                allowance = (
                    max_speed_pixels_per_second
                    * DETOUR_ALLOWANCE_SPEED_FRACTION
                    * elapsed
                )
                fast_leg = any(
                    hypot(b.x - a.x, b.y - a.y)
                    / ((b.source_frame - a.source_frame) / fps)
                    > max_speed_pixels_per_second * DETOUR_FAST_LEG_SPEED_FRACTION
                    for a, b in ((path[0], path[1]), (path[-2], path[-1]))
                )
                slow_bracket = direct <= allowance
                detour = excess > allowance or (fast_leg and slow_bracket)
                if detour and (worst is None or excess > worst[0]):
                    worst = (excess, members)
        if worst is None:
            return withdrawn
        for entry in worst[1]:
            withdrawn.append((entry.source_frame, float(entry.x), float(entry.y)))
            ledger.withdraw(
                entry.source_frame,
                CONFIRM_YOLO_MODULE,
                "detour_from_consistent_confirmed_neighbours",
            )


def _earlier_object_reason(
    point: BallPoint,
    *,
    ledger: FrameLedger | None,
    candidates_by_frame: dict[int, list[_BallCandidate]],
    frame_step: int,
    fps: float = 0.0,
    max_speed_pixels_per_second: float = 0.0,
) -> str | None:
    # A box where the detector already saw something one sample earlier,
    # while the confirmed ball was clearly elsewhere, is that other object
    # (a boot or a mark), not the ball arriving. Further back, the other
    # object may have moved at player speed: a box within that reach of an
    # earlier detection that sat clearly apart from the confirmed ball at the
    # same moment is still that object, even if the detector missed it in
    # between. The most recent confirmed ball near the box clears it.
    if ledger is None or frame_step < 1:
        return None
    radius = EARLIER_OBJECT_RADIUS_PIXELS
    separation = EARLIER_OBJECT_BALL_SEPARATION * radius
    lookback = EARLIER_OBJECT_LOOKBACK_SAMPLES
    if fps <= 0 or max_speed_pixels_per_second <= 0:
        lookback = 1
    for samples in range(1, lookback + 1):
        earlier_frame = point.source_frame - samples * frame_step
        ball = ledger.entries.get(earlier_frame)
        if (
            ball is None
            or ball.status != "confirmed"
            or ball.x is None
            or ball.y is None
        ):
            continue
        if hypot(ball.x - point.x, ball.y - point.y) <= separation:
            return None
        reach = radius
        if samples > 1:
            reach += (
                max_speed_pixels_per_second
                * EARLIER_OBJECT_PLAYER_SPEED_FRACTION
                * samples
                * frame_step
                / fps
            )
        for candidate in candidates_by_frame.get(earlier_frame, []):
            if hypot(candidate.point.x - point.x, candidate.point.y - point.y) > reach:
                continue
            if samples == 1:
                return "same_spot_as_earlier_non_ball_detection"
            # A clearly stronger box is a better sighting than that earlier
            # object, so only a box no stronger than it is that object.
            if (
                hypot(candidate.point.x - ball.x, candidate.point.y - ball.y)
                > separation
                and point.confidence
                <= candidate.point.confidence + EARLIER_OBJECT_CONFIDENCE_MARGIN
            ):
                return "moved_on_from_earlier_non_ball_detection"
    return None


# A rolling or flying ball keeps its velocity between touches. When three
# confirmed samples in a row (on either side) show steady motion, a box on
# the next predicted spot is backed by that motion: blur may wash out its
# colour, but no static object or patch of grass follows the ball's path.
MOMENTUM_CHAIN_SAMPLES = 3
MOMENTUM_MINIMUM_STEP_PIXELS = 10.0
MOMENTUM_TOLERANCE_FRACTION = 0.35
MOMENTUM_MINIMUM_TOLERANCE_PIXELS = 8.0


def _continues_confirmed_momentum(
    source_frame: int,
    x: float,
    y: float,
    confirmed: Mapping[int, Any],
    *,
    frame_step: int,
) -> bool:
    if frame_step < 1:
        return False
    for direction in (-1, 1):
        chain = [
            confirmed.get(source_frame + direction * offset * frame_step)
            for offset in range(1, MOMENTUM_CHAIN_SAMPLES + 1)
        ]
        if any(
            entry is None or entry.x is None or entry.y is None for entry in chain
        ):
            continue
        steps = [
            (float(a.x) - float(b.x), float(a.y) - float(b.y))
            for a, b in zip(chain, chain[1:])
        ]
        length = hypot(*steps[0])
        if length < MOMENTUM_MINIMUM_STEP_PIXELS:
            continue
        tolerance = max(
            MOMENTUM_MINIMUM_TOLERANCE_PIXELS, length * MOMENTUM_TOLERANCE_FRACTION
        )
        if any(
            hypot(step[0] - steps[0][0], step[1] - steps[0][1]) > tolerance
            for step in steps[1:]
        ):
            continue
        predicted_x = float(chain[0].x) + steps[0][0]
        predicted_y = float(chain[0].y) + steps[0][1]
        if hypot(x - predicted_x, y - predicted_y) <= tolerance:
            return True
    return False


MOMENTUM_REVERSAL_LOOKAHEAD_SAMPLES = 3

# A free ball keeps its course until something touches it. A weak box at a
# player's feet that lies further from the confirmed ball's course than that
# player is tall is a boot, not the ball: the ball cannot have reached those
# feet without passing near them.
FREE_COURSE_MAXIMUM_CONFIDENCE = 0.5
FREE_COURSE_ANCHOR_SAMPLES = 2
# A weak far pick needs a detection before and after it, each at most this many
# samples away, with the pick within this share of one top-speed sample of the
# straight course between them.
COURSE_CHAIN_MAXIMUM_SAMPLES = 4
COURSE_CHAIN_TOLERANCE_SAMPLE_SHARE = 0.25


def _point_segment_distance(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    dx = bx - ax
    dy = by - ay
    length_squared = dx * dx + dy * dy
    if length_squared <= 0.0:
        return hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_squared))
    return hypot(px - (ax + t * dx), py - (ay + t * dy))


def _boot_off_free_ball_course(
    point: BallPoint,
    *,
    record: dict[str, Any],
    confirmed: Mapping[int, Any],
    frame_step: int,
) -> bool:
    if (
        frame_step < 1
        or point.source_attribution != "yolo26_observed"
        or point.confidence >= FREE_COURSE_MAXIMUM_CONFIDENCE
    ):
        return False
    player_height = _feet_player_height(point, record)
    if player_height <= 0.0:
        return False
    frame = point.source_frame
    checked = False
    for direction in (-1, 1):
        anchor = next(
            (
                (frame + direction * offset * frame_step, entry)
                for offset in range(1, FREE_COURSE_ANCHOR_SAMPLES + 1)
                if (entry := confirmed.get(frame + direction * offset * frame_step))
                is not None
                and entry.x is not None
                and entry.y is not None
            ),
            None,
        )
        if anchor is None:
            continue
        anchor_frame, anchor_entry = anchor
        previous = next(
            (
                (anchor_frame + direction * offset * frame_step, entry)
                for offset in range(1, FREE_COURSE_ANCHOR_SAMPLES + 1)
                if (
                    entry := confirmed.get(
                        anchor_frame + direction * offset * frame_step
                    )
                )
                is not None
                and entry.x is not None
                and entry.y is not None
            ),
            None,
        )
        if previous is None:
            continue
        previous_frame, previous_entry = previous
        ax, ay = float(anchor_entry.x), float(anchor_entry.y)
        span = anchor_frame - previous_frame
        vx = (ax - float(previous_entry.x)) / span
        vy = (ay - float(previous_entry.y)) / span
        ahead = frame - anchor_frame
        predicted_x = ax + vx * ahead
        predicted_y = ay + vy * ahead
        checked = True
        if (
            _point_segment_distance(
                float(point.x), float(point.y), ax, ay, predicted_x, predicted_y
            )
            <= player_height
        ):
            return False
    return checked


def _withdraw_boots_off_free_ball_course(
    ledger: FrameLedger,
    *,
    records_by_frame: Mapping[int, dict[str, Any]],
    frame_step: int,
) -> list[int]:
    """01 judges its candidates on its own ledger; recheck its picks at a
    player's feet once the locked chains around them are visible."""
    withdrawn: list[int] = []
    for frame, entry in ledger.entries.items():
        if (
            entry.status != "confirmed"
            or entry.confirming_module != CONFIRM_YOLO_MODULE
            or not (entry.evidence or {}).get("near_player_feet")
            or entry.x is None
            or entry.y is None
        ):
            continue
        if _boot_off_free_ball_course(
            entry.to_point(),
            record=records_by_frame.get(frame, {}),
            confirmed=_confirmed_by_frame(ledger, exclude=frame),
            frame_step=frame_step,
        ):
            ledger.withdraw(frame, CONFIRM_YOLO_MODULE, "boot_off_free_ball_course")
            withdrawn.append(frame)
    return withdrawn


def _withdraw_weak_long_unseen_jumps(
    ledger: FrameLedger,
    *,
    candidates_by_frame: dict[int, list[_BallCandidate]],
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
) -> list[int]:
    """A weak 01 pick farther from the nearest locked or confirmed ball than
    one top-speed sample, with no moving chain of detections to carry the
    ball there, is not the ball. 01 judged its own picks without the locks."""
    withdrawn: list[int] = []
    for frame, entry in ledger.entries.items():
        if (
            entry.status != "confirmed"
            or entry.confirming_module != CONFIRM_YOLO_MODULE
            or entry.point_source_attribution != "yolo26_observed"
            or float(entry.confidence or 0.0) >= BALL_COLOUR_WEAK_CONFIDENCE
            or entry.x is None
            or entry.y is None
        ):
            continue
        point = entry.to_point()
        if _long_unseen_jump(
            point,
            ledger,
            fps=fps,
            frame_step=frame_step,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        ) and not _course_chain_supports(
            point,
            candidates_by_frame=candidates_by_frame,
            fps=fps,
            frame_step=frame_step,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        ):
            ledger.withdraw(
                frame, CONFIRM_YOLO_MODULE, "weak_long_unseen_jump_from_locked_ball"
            )
            withdrawn.append(frame)
    return withdrawn


def _course_chain_supports(
    point: BallPoint,
    *,
    candidates_by_frame: dict[int, list[_BallCandidate]],
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
) -> bool:
    """Whether the detection lies on a steady course between a detection
    before it and one after it. A ball travelling through unseen frames keeps
    its course between sightings; clutter boxes that merely lie within top
    speed of each other wander about instead."""
    if fps <= 0 or frame_step < 1:
        return False

    def reachable(direction: int) -> list[tuple[int, BallPoint]]:
        found = []
        for samples in range(1, COURSE_CHAIN_MAXIMUM_SAMPLES + 1):
            frame = point.source_frame + direction * samples * frame_step
            reach = max_speed_pixels_per_second * samples * frame_step / fps
            for candidate in candidates_by_frame.get(frame, []):
                other = candidate.point
                if (
                    hypot(other.x - point.x, other.y - point.y) <= reach
                    and _same_position_static_reason(
                        other, candidates_by_frame=candidates_by_frame, fps=fps
                    )
                    is None
                ):
                    found.append((samples, other))
        return found

    tolerance = (
        COURSE_CHAIN_TOLERANCE_SAMPLE_SHARE
        * max_speed_pixels_per_second
        * frame_step
        / fps
    )
    for before_samples, before in reachable(-1):
        for after_samples, after in reachable(1):
            share = before_samples / (before_samples + after_samples)
            expected_x = before.x + (after.x - before.x) * share
            expected_y = before.y + (after.y - before.y) * share
            if hypot(point.x - expected_x, point.y - expected_y) <= tolerance:
                return True
    return False


def _reverses_confirmed_momentum_unsupported(
    point: BallPoint,
    confirmed: Mapping[int, Any],
    *,
    candidates_by_frame: dict[int, list[_BallCandidate]],
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
) -> bool:
    """Whether a box sends a steadily rolling ball back without later sightings.

    A touch can send the ball back, but the ball then travels on from the new
    spot and is seen there again. A box behind the run with no later sighting
    nearer to it than to the ball's last confirmed spot is another object.
    """
    if frame_step < 1 or fps <= 0:
        return False
    chain = [
        confirmed.get(point.source_frame - offset * frame_step)
        for offset in range(1, MOMENTUM_CHAIN_SAMPLES + 1)
    ]
    if any(entry is None or entry.x is None or entry.y is None for entry in chain):
        return False
    steps = [
        (float(a.x) - float(b.x), float(a.y) - float(b.y))
        for a, b in zip(chain, chain[1:])
    ]
    length = hypot(*steps[0])
    if length < MOMENTUM_MINIMUM_STEP_PIXELS:
        return False
    tolerance = max(
        MOMENTUM_MINIMUM_TOLERANCE_PIXELS, length * MOMENTUM_TOLERANCE_FRACTION
    )
    if any(
        hypot(step[0] - steps[0][0], step[1] - steps[0][1]) > tolerance
        for step in steps[1:]
    ):
        return False
    last_x, last_y = float(chain[0].x), float(chain[0].y)
    moved_x, moved_y = float(point.x) - last_x, float(point.y) - last_y
    if hypot(moved_x, moved_y) <= tolerance:
        return False
    if moved_x * steps[0][0] + moved_y * steps[0][1] >= 0:
        return False
    for offset in range(1, MOMENTUM_REVERSAL_LOOKAHEAD_SAMPLES + 1):
        frame = point.source_frame + offset * frame_step
        reach = max_speed_pixels_per_second * offset * frame_step / fps
        for candidate in candidates_by_frame.get(frame, []):
            later = candidate.point
            to_box = hypot(later.x - point.x, later.y - point.y)
            if (
                to_box <= reach
                and to_box < hypot(later.x - last_x, later.y - last_y)
                and _same_position_static_reason(
                    later,
                    candidates_by_frame=candidates_by_frame,
                    fps=fps,
                )
                is None
            ):
                return False
    return True


def _confirmed_by_frame(ledger: FrameLedger, *, exclude: int | None = None) -> dict[int, Any]:
    return {
        entry.source_frame: entry
        for entry in ledger.entries.values()
        if entry.status == "confirmed" and entry.source_frame != exclude
    }


EARLIER_OBJECT_RADIUS_PIXELS = 30.0
EARLIER_OBJECT_BALL_SEPARATION = 3.0
EARLIER_OBJECT_LOOKBACK_SAMPLES = 4
EARLIER_OBJECT_PLAYER_SPEED_FRACTION = 0.125
EARLIER_OBJECT_CONFIDENCE_MARGIN = 0.05


def _long_unseen_jump(
    point: BallPoint,
    ledger: FrameLedger,
    *,
    fps: float,
    frame_step: int,
    max_speed_pixels_per_second: float,
) -> bool:
    """Whether the nearest confirmed ball is farther than one top-speed sample.

    The ball can only get there by travelling fast through unseen frames; a
    real ball in flight leaves a chain of moving detections, while a boot or
    other ball-like object far from the ball does not.
    """
    if fps <= 0 or frame_step < 1:
        return False
    confirmed = [
        entry
        for entry in ledger.entries.values()
        if entry.status == "confirmed"
        and entry.x is not None
        and entry.y is not None
        and entry.source_frame != point.source_frame
    ]
    if not confirmed:
        return False
    nearest = min(
        confirmed,
        key=lambda entry: abs(entry.source_frame - point.source_frame),
    )
    one_sample = max_speed_pixels_per_second * frame_step / fps
    return hypot(nearest.x - point.x, nearest.y - point.y) > one_sample


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
    ball_colour_matches: Any = None,
    stands_out_from_grass: Any = None,
) -> tuple[str | None, bool]:
    if point.confidence < minimum_confidence:
        return "low_detector_confidence", False
    if (
        stands_out_from_grass is not None
        and point.source_attribution == "yolo26_observed"
        and point.confidence < BALL_COLOUR_WEAK_CONFIDENCE
        and not stands_out_from_grass(point)
        and not (
            ledger is not None
            and _continues_confirmed_momentum(
                point.source_frame,
                float(point.x),
                float(point.y),
                _confirmed_by_frame(ledger, exclude=point.source_frame),
                frame_step=frame_step,
            )
        )
    ):
        return "no_contrast_with_grass", False
    if _on_player_upper_body(point, record) and not _strong_ball_behind_player(
        point
    ):
        return "inside_player_upper_body", False
    static_reason = _same_position_static_reason(
        point,
        candidates_by_frame=candidates_by_frame,
        fps=fps,
    )
    if static_reason is not None:
        return static_reason, False
    if (
        ledger is not None
        and point.source_attribution == "yolo26_observed"
        and point.confidence < BALL_COLOUR_WEAK_CONFIDENCE
        and _reverses_confirmed_momentum_unsupported(
            point,
            _confirmed_by_frame(ledger, exclude=point.source_frame),
            candidates_by_frame=candidates_by_frame,
            fps=fps,
            frame_step=frame_step,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        )
    ):
        return "reverses_confirmed_momentum_without_later_sighting", False
    earlier_reason = _earlier_object_reason(
        point,
        ledger=ledger,
        candidates_by_frame=candidates_by_frame,
        frame_step=frame_step,
        fps=fps,
        max_speed_pixels_per_second=max_speed_pixels_per_second,
    )
    if earlier_reason is not None:
        return earlier_reason, False
    near_feet = any(
        candidate.point == point and candidate.near_player_feet
        for candidate in candidates_by_frame.get(point.source_frame, [])
    )
    if (
        near_feet
        and ledger is not None
        and _boot_off_free_ball_course(
            point,
            record=record,
            confirmed=_confirmed_by_frame(ledger, exclude=point.source_frame),
            frame_step=frame_step,
        )
    ):
        return "boot_off_free_ball_course", near_feet
    far_from_ball = getattr(ball_colour_matches, "far_from_ball", None)
    if (
        far_from_ball is not None
        and point.source_attribution == "yolo26_observed"
        and far_from_ball(point)
    ):
        return "colour_far_from_ball", near_feet
    # A weak box without ball colour is grass, a line or a sliver of kit,
    # whether or not it sits near a player's feet.
    if (
        ball_colour_matches is not None
        and point.confidence < BALL_COLOUR_WEAK_CONFIDENCE
        and not ball_colour_matches(point)
    ):
        return "colour_differs_from_ball", near_feet
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
        if _long_unseen_jump(
            point,
            ledger,
            fps=fps,
            frame_step=frame_step,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        ) and not _moving_chain_supports(
            point,
            candidates_by_frame=candidates_by_frame,
            fps=fps,
            frame_step=frame_step,
            max_speed_pixels_per_second=max_speed_pixels_per_second,
        ):
            return "long_unseen_jump_without_moving_chain", near_feet
    # A fixed object detected in nearby frames is not motion support for any
    # candidate, selected or not.
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
    detector_points = list(detector_points)
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
        ball_colour_matches=(
            _ball_colour_check(
                detector_points,
                [
                    *_weak_feet_candidates(candidates_by_frame),
                    *(
                        candidate.point
                        for candidates in candidates_by_frame.values()
                        for candidate in candidates
                        if candidate.point.source_attribution == "yolo26_observed"
                        and candidate.point.confidence >= BALL_COLOUR_WEAK_CONFIDENCE
                    ),
                ],
                video,
            )
            if video is not None
            else None
        ),
        stands_out_from_grass=(
            _grass_contrast_check(detector_points, video) if video is not None else None
        ),
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


def _feet_pick_outranked_by_free_ball(
    selected: BallPoint,
    *,
    candidates_by_frame: dict[int, list[_BallCandidate]],
    fps: float,
) -> bool:
    """A boot can look like a ball; a stronger box away from every player's
    feet in the same frame is the better ball, so the pick at the feet loses
    its lighter checks and the free box is tried first. A dribbled ball at the
    feet keeps its pick when no stronger free box exists."""
    candidates = candidates_by_frame.get(selected.source_frame, [])
    if not any(
        candidate.point == selected and candidate.near_player_feet
        for candidate in candidates
    ):
        return False
    return any(
        candidate.point != selected
        and not candidate.near_player_feet
        and candidate.point.source_attribution == "yolo26_observed"
        and candidate.point.confidence > selected.confidence
        and _same_position_static_reason(
            candidate.point,
            candidates_by_frame=candidates_by_frame,
            fps=fps,
        )
        is None
        for candidate in candidates
    )


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
    ball_colour_matches: Any = None,
    stands_out_from_grass: Any = None,
) -> None:
    for frame in frames:
        if ledger.confirmed(frame) is not None:
            continue
        selected = best_by_frame.get(frame)
        options: list[tuple[BallPoint, bool]] = []
        # The trajectory's pick keeps its lighter checks unless it is an
        # isolated detection (no moving chain) outranked by a stronger one in
        # the same frame; then it must be reachable from the confirmed ball
        # like any other candidate, and stronger candidates are tried first.
        strongest_other = max(
            (
                candidate.point.confidence
                for candidate in candidates_by_frame.get(frame, [])
                if candidate.point != selected
                and candidate.point.source_attribution == "yolo26_observed"
                and _same_position_static_reason(
                    candidate.point,
                    candidates_by_frame=candidates_by_frame,
                    fps=fps,
                )
                is None
            ),
            default=0.0,
        )
        selected_outranked = selected is not None and (
            (
                strongest_other > selected.confidence
                and not _moving_chain_supports(
                    selected,
                    candidates_by_frame=candidates_by_frame,
                    fps=fps,
                    frame_step=frame_step,
                    max_speed_pixels_per_second=max_speed_pixels_per_second,
                )
            )
            or _feet_pick_outranked_by_free_ball(
                selected,
                candidates_by_frame=candidates_by_frame,
                fps=fps,
            )
        )
        if selected is not None and not selected_outranked:
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
                (candidate.point != selected or selected_outranked)
                and candidate.point.source_attribution == "yolo26_observed"
            ):
                options.append((candidate.point, True))
        if selected_outranked and all(
            point != selected for point, _ in options
        ):
            options.append((selected, True))
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
                ball_colour_matches=ball_colour_matches,
                stands_out_from_grass=stands_out_from_grass,
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
                    # A strong detection elsewhere shows the ball has left the
                    # spot; whatever the disc shows after that is not the ball.
                    if entry.status == "confirmed" and not _is_movable_detection(
                        entry
                    ):
                        break
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
