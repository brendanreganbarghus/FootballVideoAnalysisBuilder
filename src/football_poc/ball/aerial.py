from __future__ import annotations

from .settings import *  # noqa: F401,F403


AERIAL_MODULE = "02_aerial_flight"

# A ball in the air is too small and blurred for the detector, but it still
# moves. Between two confirmed positions this module reads every video frame,
# keeps small moving blobs that are not on a player, links them into short
# tracks and fits one smooth flight path through both confirmed ends. The path
# is accepted only when it is clearly supported by many frames and no other
# path comes close; otherwise the gap stays unresolved.
AERIAL_PROFILE = FrozenProfile({
    "minimum_gap_frames": 15,
    "maximum_gap_frames": 125,
    "difference_threshold": 12,
    "minimum_blob_area": 3,
    # A fast ball is a blur streak up to the maximum side long; lying
    # diagonally it fills about half of that square.
    "maximum_blob_area": 800,
    "maximum_blob_side": 40,
    # A longer blob is still the ball when it is a thin streak no longer than
    # one frame of the fastest ball travel plus the ball itself.
    "streak_length_allowance_pixels": 20.0,
    "streak_maximum_thickness_pixels": 16.0,
    "link_distance_pixels": 40.0,
    "link_prediction_pixels": 12.0,
    "minimum_tracklet_frames": 5,
    "inlier_pixels": 10.0,
    "minimum_inlier_frames": 8,
    "minimum_inlier_fraction": 0.4,
    "rival_separation_pixels": 30.0,
    "rival_minimum_apart_frames": 3,
    "rival_inlier_ratio": 0.7,
    "fill_reach_frames": 5,
    # A real flight leaves a continuous motion trail from launch to landing.
    # A longer blank stretch means the path jumped between unrelated movers
    # (for example an undetected distant player) and only the curve fit
    # joined them, so the whole flight is refused.
    "maximum_unsupported_frames": 10,
    "launch_reach_pixels": 20.0,
    # A kicked ball travels between launch and landing. When the confirmed
    # ends of a gap barely moved, any fitted arc is moving players or noise.
    "minimum_end_to_end_pixels_per_frame": 1.0,
    # A ball in the air is drawn straight above its ground line between the
    # two ends. A path further than this outside their sideways span or below
    # their line is a player's foot or shadow, not the ball.
    "flat_path_tolerance_pixels": 20.0,
    "person_minimum_confidence": 0.25,
    # Empty-pitch spots: a rolling background (median of nearby frames) is
    # subtracted so a ball that is standing still also leaves a spot. Only
    # the upper body of a player box is ignored, so a ball at the feet stays.
    "empty_pitch_spots": False,
    "background_step_frames": 15,
    "background_reach_frames": 75,
    "background_threshold": 30,
    "spot_minimum_area": 8,
    "spot_maximum_area": 160,
    "spot_maximum_side": 18,
    "spot_minimum_fill": 0.35,
    "spot_maximum_aspect": 2.2,
    "player_body_fraction": 0.75,
})


def _aerial_path(s, e, params, t):
    u = (t - s[0]) / (e[0] - s[0])
    w = u * (1.0 - u)
    a, b, c, d = params
    return (
        s[1] + (e[1] - s[1]) * u + w * (a + b * u),
        s[2] + (e[2] - s[2]) * u + w * (c + d * u),
    )


def _aerial_fit(s, e, points):
    if len(points) < 2:
        return None
    rows, xs, ys = [], [], []
    for t, x, y in points:
        u = (t - s[0]) / (e[0] - s[0])
        w = u * (1.0 - u)
        rows.append((w, w * u))
        xs.append(x - (s[1] + (e[1] - s[1]) * u))
        ys.append(y - (s[2] + (e[2] - s[2]) * u))
    matrix = np.asarray(rows)
    if np.linalg.matrix_rank(matrix) < 2:
        return None
    (a, b), *_ = np.linalg.lstsq(matrix, np.asarray(xs), rcond=None)
    (c, d), *_ = np.linalg.lstsq(matrix, np.asarray(ys), rcond=None)
    return (float(a), float(b), float(c), float(d))


def _aerial_blob_index(blobs):
    times = sorted(blobs)
    if any(not blobs[t] for t in times):
        return None
    counts = np.asarray([len(blobs[t]) for t in times], dtype=np.int64)
    starts = np.concatenate(([0], np.cumsum(counts)[:-1]))
    coordinates = np.asarray(
        [point for t in times for point in blobs[t]], dtype=np.float64
    ).reshape(-1, 2)
    return np.asarray(times, dtype=np.int64), starts, counts, coordinates


def _aerial_inliers(s, e, params, blobs, index=None):
    tolerance = float(AERIAL_PROFILE["inlier_pixels"])
    if index is not None and blobs:
        times, starts, counts, coordinates = index
        low = int(np.searchsorted(times, min(blobs)))
        high = int(np.searchsorted(times, max(blobs), side="right"))
        if high - low == len(blobs):
            return _aerial_inliers_indexed(
                s, e, params, blobs, tolerance,
                times[low:high], starts[low:high], counts[low:high], coordinates,
            )
    inliers = {}
    for t, candidates in blobs.items():
        px, py = _aerial_path(s, e, params, t)
        best = min(
            ((hypot(x - px, y - py), x, y) for x, y in candidates),
            default=None,
        )
        if best is not None and best[0] <= tolerance:
            inliers[t] = (best[1], best[2])
    return inliers


def _aerial_inliers_indexed(
    s, e, params, blobs, tolerance, times, starts, counts, coordinates
):
    # A vectorised distance pass shortlists the frames and blobs that can
    # possibly be nearest; the exact scalar comparison then decides, so the
    # result is identical to checking every blob.
    a, b, c, d = params
    u = (times - s[0]) / (e[0] - s[0])
    w = u * (1.0 - u)
    px = s[1] + (e[1] - s[1]) * u + w * (a + b * u)
    py = s[2] + (e[2] - s[2]) * u + w * (c + d * u)
    first = int(starts[0])
    last = int(starts[-1] + counts[-1])
    points = coordinates[first:last]
    dx = points[:, 0] - np.repeat(px, counts)
    dy = points[:, 1] - np.repeat(py, counts)
    squared = dx * dx + dy * dy
    nearest = np.sqrt(np.minimum.reduceat(squared, starts - first))
    margin = 1e-6
    possible = {
        int(times[i]): i for i in np.flatnonzero(nearest <= tolerance + margin)
    }
    inliers = {}
    for t, candidates in blobs.items():
        i = possible.get(t)
        if i is None:
            continue
        begin = int(starts[i]) - first
        limit = (float(nearest[i]) + margin) ** 2
        shortlist = [
            candidates[j]
            for j in np.flatnonzero(squared[begin : begin + int(counts[i])] <= limit)
        ]
        exact_x, exact_y = _aerial_path(s, e, params, t)
        best = min(
            (hypot(x - exact_x, y - exact_y), x, y) for x, y in shortlist
        )
        if best[0] <= tolerance:
            inliers[t] = (best[1], best[2])
    return inliers


def _aerial_blobs(gray, start, end, people_by_frame, s, e, max_step):
    blobs: dict[int, list[tuple[float, float]]] = {}
    for t in range(start + 1, end):
        if t - 1 not in gray or t + 1 not in gray:
            continue
        found = _aerial_frame_blobs(
            gray[t - 1], gray[t], gray[t + 1], t, people_by_frame, s, e, max_step
        )
        if found:
            blobs[t] = found
    return blobs


def _aerial_streamed_blobs(video, start, end, people_by_frame, s, e, max_step):
    # Same blobs as reading the whole range first, but only three decoded
    # frames are kept, so several gaps can be searched side by side.
    blobs: dict[int, list[tuple[float, float]]] = {}
    capture = cv2.VideoCapture(str(video))
    window: list[tuple[int, np.ndarray]] = []
    try:
        first = max(0, start - 1)
        capture.set(cv2.CAP_PROP_POS_FRAMES, first)
        for frame in range(first, end + 1):
            ok, image = capture.read()
            if not ok:
                break
            window.append(
                (frame, cv2.GaussianBlur(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (3, 3), 0))
            )
            if len(window) > 3:
                window.pop(0)
            if len(window) < 3:
                continue
            t = window[1][0]
            if not start < t < end:
                continue
            found = _aerial_frame_blobs(
                window[0][1], window[1][1], window[2][1], t,
                people_by_frame, s, e, max_step,
            )
            if found:
                blobs[t] = found
    finally:
        capture.release()
    return blobs


def _aerial_fast_streak(area, width, height, max_step):
    """A thin smear no longer than one frame of the fastest ball travel.

    A ball kicked hard moves further in one frame than the compact blob size
    allows, so its motion difference is a long thin streak. A moving player or
    crowd patch of that length is far thicker.
    """
    profile = AERIAL_PROFILE
    length = hypot(width, height)
    if length > max_step + float(profile["streak_length_allowance_pixels"]):
        return False
    return area / max(length, 1.0) <= float(profile["streak_maximum_thickness_pixels"])


def _aerial_frame_blobs(previous, current, following, t, people_by_frame, s, e, max_step):
    profile = AERIAL_PROFILE
    difference = cv2.min(
        cv2.absdiff(current, previous),
        cv2.absdiff(current, following),
    )
    _, mask = cv2.threshold(
        difference, int(profile["difference_threshold"]), 255, cv2.THRESH_BINARY
    )
    count, _, stats, centres = cv2.connectedComponentsWithStats(mask)
    people = people_by_frame(t)
    found = []
    for index in range(1, count):
        area = int(stats[index, cv2.CC_STAT_AREA])
        width = int(stats[index, cv2.CC_STAT_WIDTH])
        height = int(stats[index, cv2.CC_STAT_HEIGHT])
        if area < int(profile["minimum_blob_area"]):
            continue
        compact = (
            area <= int(profile["maximum_blob_area"])
            and max(width, height) <= int(profile["maximum_blob_side"])
        )
        if not compact and not _aerial_fast_streak(area, width, height, max_step):
            continue
        x, y = float(centres[index][0]), float(centres[index][1])
        if hypot(x - s[1], y - s[2]) > max_step * (t - s[0]) + 20:
            continue
        if hypot(x - e[1], y - e[2]) > max_step * (e[0] - t) + 20:
            continue
        if any(x1 <= x <= x2 and y1 <= y <= y2 for x1, y1, x2, y2 in people):
            continue
        found.append((x, y))
    return found


def _read_background_samples(video: Path, start: int, end: int, step: int) -> dict[int, np.ndarray]:
    capture = cv2.VideoCapture(str(video))
    samples: dict[int, np.ndarray] = {}
    first = max(0, start)
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, first)
        for frame in range(first, end + 1):
            if frame % step:
                if not capture.grab():
                    break
                continue
            ok, image = capture.read()
            if not ok:
                break
            samples[frame] = cv2.GaussianBlur(
                cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (3, 3), 0
            )
    finally:
        capture.release()
    return samples


def _aerial_empty_pitch_spots(gray, samples, start, end, people_by_frame, s, e, max_step):
    profile = AERIAL_PROFILE
    step = int(profile["background_step_frames"])
    reach = int(profile["background_reach_frames"])
    body = float(profile["player_body_fraction"])
    backgrounds: dict[int, np.ndarray | None] = {}
    spots: dict[int, list[tuple[float, float]]] = {}
    for t in range(start + 1, end):
        if t not in gray:
            continue
        block = t // step
        if block not in backgrounds:
            centre = block * step + step // 2
            nearby = [
                image for frame, image in samples.items()
                if step // 2 < abs(frame - centre) <= reach
            ]
            backgrounds[block] = (
                np.median(np.stack(nearby), axis=0).astype(np.uint8)
                if len(nearby) >= 4 else None
            )
        background = backgrounds[block]
        if background is None:
            continue
        _, mask = cv2.threshold(
            cv2.absdiff(gray[t], background),
            int(profile["background_threshold"]),
            255,
            cv2.THRESH_BINARY,
        )
        count, _, stats, centres = cv2.connectedComponentsWithStats(mask)
        people = people_by_frame(t)
        found = []
        for index in range(1, count):
            area = int(stats[index, cv2.CC_STAT_AREA])
            width = int(stats[index, cv2.CC_STAT_WIDTH])
            height = int(stats[index, cv2.CC_STAT_HEIGHT])
            if not (
                int(profile["spot_minimum_area"]) <= area <= int(profile["spot_maximum_area"])
            ):
                continue
            if max(width, height) > int(profile["spot_maximum_side"]):
                continue
            if area / float(width * height) < float(profile["spot_minimum_fill"]):
                continue
            if max(width, height) > float(profile["spot_maximum_aspect"]) * min(width, height):
                continue
            x, y = float(centres[index][0]), float(centres[index][1])
            if hypot(x - s[1], y - s[2]) > max_step * (t - s[0]) + 20:
                continue
            if hypot(x - e[1], y - e[2]) > max_step * (e[0] - t) + 20:
                continue
            if any(
                x1 <= x <= x2 and y1 <= y <= y1 + body * (y2 - y1)
                for x1, y1, x2, y2 in people
            ):
                continue
            found.append((x, y))
        if found:
            spots[t] = found
    return spots


def _merge_spots(blobs, spots, separation=3.0):
    merged = {t: list(found) for t, found in blobs.items()}
    for t, found in spots.items():
        current = merged.setdefault(t, [])
        for x, y in found:
            if all(hypot(x - cx, y - cy) > separation for cx, cy in current):
                current.append((x, y))
    return merged


def _aerial_tracklets(blobs):
    profile = AERIAL_PROFILE
    link = float(profile["link_distance_pixels"])
    predict = float(profile["link_prediction_pixels"])
    open_tracks: list[list[tuple[int, float, float]]] = []
    finished = []
    for t in sorted(blobs):
        extended = []
        used = set()
        for track in open_tracks:
            last = track[-1]
            if last[0] != t - 1:
                finished.append(track)
                continue
            if len(track) >= 2:
                vx, vy = last[1] - track[-2][1], last[2] - track[-2][2]
                target, radius = (last[1] + vx, last[2] + vy), predict
            else:
                target, radius = (last[1], last[2]), link
            options = [
                (hypot(x - target[0], y - target[1]), i)
                for i, (x, y) in enumerate(blobs[t])
                if i not in used
            ]
            best = min(options, default=None)
            if best is None or best[0] > radius:
                finished.append(track)
                continue
            used.add(best[1])
            x, y = blobs[t][best[1]]
            extended.append([*track, (t, x, y)])
        for i, (x, y) in enumerate(blobs[t]):
            if i not in used:
                extended.append([(t, x, y)])
        open_tracks = extended
    finished.extend(open_tracks)
    minimum = int(profile["minimum_tracklet_frames"])
    return [track for track in finished if len(track) >= minimum]


def _aerial_flight_window(s, e, points):
    # The ball can rest at the kicker's feet before it is struck and at the
    # receiver after it lands. Extend the observed flight backwards and
    # forwards and take off/land where it meets the confirmed positions.
    if len(points) < 5:
        return s[0], e[0]
    times = np.asarray([p[0] for p in points], dtype=float)
    fx = np.polyfit(times, [p[1] for p in points], 2)
    fy = np.polyfit(times, [p[2] for p in points], 2)
    reach = float(AERIAL_PROFILE["launch_reach_pixels"])

    def meet(anchor, candidates):
        best = None
        for t in candidates:
            distance = hypot(
                float(np.polyval(fx, t)) - anchor[1],
                float(np.polyval(fy, t)) - anchor[2],
            )
            if best is None or distance < best[0]:
                best = (distance, t)
        if best is None or best[0] > reach:
            return anchor[0]
        return best[1]

    first, last = int(times.min()), int(times.max())
    return meet(s, range(s[0], first)), meet(e, range(last + 1, e[0] + 1))


def _aerial_position(model, t):
    s, e, params = model
    if t <= s[0]:
        return s[1], s[2]
    if t >= e[0]:
        return e[1], e[2]
    return _aerial_path(s, e, params, t)


def _aerial_model(s, e, points, blobs, window=None, index=None):
    launch, landing = window or _aerial_flight_window(s, e, points)
    s2 = (launch, s[1], s[2])
    e2 = (landing, e[1], e[2])
    inside = [p for p in points if launch < p[0] < landing]
    params = _aerial_fit(s2, e2, inside)
    if params is None:
        return None
    flight_blobs = {t: c for t, c in blobs.items() if launch < t < landing}
    inliers = _aerial_inliers(s2, e2, params, flight_blobs, index)
    return (s2, e2, params), inliers


def _aerial_best_path(s, e, blobs):
    best = _aerial_curve_path(s, e, blobs)
    if best is not None:
        return best
    return _aerial_followed_path(s, e, blobs)


def _aerial_followed_path(s, e, blobs):
    """The flight followed from the left end that arrives at the right end.

    This is the same trail follower used when only one end is known. With
    both ends known the followed trail must also reach the other end, and no
    other followed trail or motion track joining both ends may run apart
    from it.
    """
    reach = float(AERIAL_PROFILE["link_distance_pixels"])
    dropout = int(AERIAL_ONE_SIDED_PROFILE["maximum_dropout_frames"])
    separation = float(AERIAL_PROFILE["rival_separation_pixels"])
    inside = {t: c for t, c in blobs.items() if s[0] < t < e[0]}
    flights = _aerial_trail_flights(s, inside)
    arriving = [
        flight for flight in flights
        if flight[-1][0] >= e[0] - 1 - dropout
        and hypot(flight[-1][1] - e[1], flight[-1][2] - e[2]) <= reach
    ]
    if not arriving:
        return None
    arriving.sort(key=lambda flight: -len(flight))
    best = arriving[0]
    best_at = {t: (x, y) for t, x, y in best}
    joining = [
        track for track in _aerial_tracklets(inside)
        if track[0][0] <= s[0] + 1 + dropout
        and track[-1][0] >= e[0] - 1 - dropout
        and hypot(track[0][1] - s[1], track[0][2] - s[2]) <= reach
        and hypot(track[-1][1] - e[1], track[-1][2] - e[2]) <= reach
    ]
    # A second complete trail between the ends is a second ball candidate,
    # however close it runs.
    tolerance = float(AERIAL_PROFILE["inlier_pixels"])
    rivals = [(flight, separation) for flight in arriving[1:]]
    rivals += [(track, tolerance) for track in joining]
    for rival, allowed in rivals:
        if _aerial_runs_apart(best_at, rival, allowed):
            return None
    return len(best_at), (s, e, (0.0, 0.0, 0.0, 0.0)), best_at


def _aerial_runs_apart(best_at, rival, allowed):
    """Whether ``rival`` keeps more than ``allowed`` pixels from the best path.

    Distance is measured to the line of the best path, not to its point at
    the same frame: a fast ball's blurred streak breaks into pieces, and a
    trail along the front or back of the streak runs the same line a frame
    or two ahead or behind. A trail that leaves from launch clutter for a
    frame and then joins the best path is the same ball; only a rival apart
    for several frames is a second candidate.
    """
    times = sorted(best_at)
    line = [best_at[t] for t in times]
    apart = sum(
        1
        for t, x, y in rival
        if times[0] <= t <= times[-1]
        and _aerial_distance_to_line(x, y, line) > allowed
    )
    return apart >= int(AERIAL_PROFILE["rival_minimum_apart_frames"])


def _aerial_distance_to_line(x, y, line):
    if len(line) == 1:
        return hypot(x - line[0][0], y - line[0][1])
    nearest = float("inf")
    for (ax, ay), (bx, by) in zip(line, line[1:]):
        dx, dy = bx - ax, by - ay
        length = dx * dx + dy * dy
        u = 0.0 if length == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length))
        nearest = min(nearest, hypot(x - ax - u * dx, y - ay - u * dy))
    return nearest


def _aerial_curve_path(s, e, blobs):
    profile = AERIAL_PROFILE
    models = []
    index = _aerial_blob_index(blobs)
    tracks = _aerial_tracklets(blobs)
    windows = [_aerial_flight_window(s, e, track) for track in tracks]
    launches = sorted({s[0], *(w[0] for w in windows)})
    landings = sorted({e[0], *(w[1] for w in windows)})
    for track in tracks:
        options = []
        for launch in launches:
            for landing in landings:
                if not (launch < track[0][0] and track[-1][0] < landing):
                    continue
                fitted = _aerial_model(s, e, track, blobs, (launch, landing), index)
                if fitted is not None:
                    options.append(fitted)
        if not options:
            continue
        model, inliers = max(options, key=lambda option: len(option[1]))
        for _ in range(2):
            (launch, *_), (landing, *_), _ = model
            refined = _aerial_model(
                s,
                e,
                [(t, x, y) for t, (x, y) in sorted(inliers.items())],
                blobs,
                (launch, landing),
                index,
            )
            if refined is None or len(refined[1]) < len(inliers):
                break
            model, inliers = refined
        models.append((len(inliers), model, inliers))
    if not models:
        return None
    models.sort(key=lambda model: -model[0])
    best = models[0]
    span = best[1][1][0] - best[1][0][0] - 1
    if best[0] < max(
        int(profile["minimum_inlier_frames"]),
        float(profile["minimum_inlier_fraction"]) * span,
    ):
        return None
    supported = [best[1][0][0], *sorted(best[2]), best[1][1][0]]
    if max(b - a for a, b in zip(supported, supported[1:])) > int(
        profile["maximum_unsupported_frames"]
    ):
        return None
    times = range(s[0] + 1, e[0])
    for count, model, _ in models[1:]:
        separation = max(
            hypot(
                _aerial_position(model, t)[0] - _aerial_position(best[1], t)[0],
                _aerial_position(model, t)[1] - _aerial_position(best[1], t)[1],
            )
            for t in times
        )
        if (
            separation > float(profile["rival_separation_pixels"])
            and count >= float(profile["rival_inlier_ratio"]) * best[0]
        ):
            return None
    return best


def _aerial_rises_above_ground_line(s, e, inliers):
    """Whether every path point lies between the ends and on or above their line.

    Height lifts a ball straight up in the image, so a ball travelling from
    one end to the other stays within their sideways span and never sinks
    below the line joining them, whenever it is kicked.
    """
    tolerance = float(AERIAL_PROFILE["flat_path_tolerance_pixels"])
    (_, sx, sy), (_, ex, ey) = s, e
    for x, y in inliers.values():
        if x < min(sx, ex) - tolerance or x > max(sx, ex) + tolerance:
            return False
        if abs(ex - sx) > tolerance:
            line_y = sy + (ey - sy) * (x - sx) / (ex - sx)
        else:
            line_y = max(sy, ey)
        if y > line_y + tolerance:
            return False
    return True


def _read_gray_range(video: Path, start: int, end: int) -> dict[int, np.ndarray]:
    capture = cv2.VideoCapture(str(video))
    frames: dict[int, np.ndarray] = {}
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, start))
        for frame in range(max(0, start), end + 1):
            ok, image = capture.read()
            if not ok:
                break
            frames[frame] = cv2.GaussianBlur(
                cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (3, 3), 0
            )
    finally:
        capture.release()
    return frames


def _confirm_aerial_flights(
    ledger: FrameLedger,
    *,
    records_by_frame: dict[int, dict[str, Any]],
    video: Path,
    fps: float,
    max_speed_pixels_per_second: float,
) -> FrameLedger:
    profile = AERIAL_PROFILE
    entries = ledger.entries
    frames = sorted(entries)
    sampled = sorted(records_by_frame)
    max_step = max_speed_pixels_per_second / fps

    def people_by_frame(t):
        nearest = min(sampled, key=lambda f: abs(f - t))
        return [
            (float(d["x1"]), float(d["y1"]), float(d["x2"]), float(d["y2"]))
            for d in records_by_frame[nearest].get("detections", [])
            if d.get("class_name") == "person"
            and float(d["confidence"]) >= float(profile["person_minimum_confidence"])
        ]

    confirmed = [
        frame for frame in frames
        if entries[frame].status == "confirmed" and entries[frame].x is not None
    ]
    plans: list[tuple[list[int], tuple, tuple, bool]] = []
    for left, right in zip(confirmed, confirmed[1:]):
        gap = [f for f in frames if left < f < right]
        if not gap or right - left < int(profile["minimum_gap_frames"]):
            continue
        if right - left > int(profile["maximum_gap_frames"]):
            continue
        if any(entries[f].status == "confirmed" for f in gap):
            continue
        s = (left, float(entries[left].x), float(entries[left].y))
        e = (right, float(entries[right].x), float(entries[right].y))
        travelled = hypot(e[1] - s[1], e[2] - s[2]) >= float(
            profile["minimum_end_to_end_pixels_per_frame"]
        ) * (right - left)
        plans.append((gap, s, e, travelled))

    def search(plan):
        _, s, e, travelled = plan
        if not travelled:
            return None
        left, right = s[0], e[0]
        if not profile["empty_pitch_spots"]:
            blobs = _aerial_streamed_blobs(
                video, left, right, people_by_frame, s, e, max_step
            )
            return _aerial_best_path(s, e, blobs)
        gray = _read_gray_range(video, left - 1, right + 1)
        blobs = _aerial_blobs(gray, left, right, people_by_frame, s, e, max_step)
        reach_frames = int(profile["background_reach_frames"])
        samples = _read_background_samples(
            video,
            left - reach_frames,
            right + reach_frames,
            int(profile["background_step_frames"]),
        )
        spots = _aerial_empty_pitch_spots(
            gray, samples, left, right, people_by_frame, s, e, max_step
        )
        del gray
        return _aerial_best_path(s, e, _merge_spots(blobs, spots))

    # Gaps are independent and touch only their own frames, so they are
    # searched side by side and their results applied in clip order.
    searches = (
        _ordered_parallel_map(search, plans)
        if not profile["empty_pitch_spots"]
        else [search(plan) for plan in plans]
    )
    for (gap, s, e, travelled), best in zip(plans, searches):
        left, right = s[0], e[0]
        if not travelled:
            for frame in gap:
                ledger.reject(frame, AERIAL_MODULE, "aerial_ends_did_not_travel")
            continue
        if best is None:
            for frame in gap:
                ledger.reject(frame, AERIAL_MODULE, "aerial_no_unique_flight_path")
            continue
        count, model, inliers = best
        if not _aerial_rises_above_ground_line(s, e, inliers):
            for frame in gap:
                ledger.reject(frame, AERIAL_MODULE, "aerial_path_not_above_ground_line")
            continue
        (launch, *_), (landing, *_), _ = model
        reach = int(profile["fill_reach_frames"])
        for frame in gap:
            if frame <= launch:
                x, y = s[1], s[2]
                evidence = "aerial_rest_before_launch"
            elif frame >= landing:
                x, y = e[1], e[2]
                evidence = "aerial_rest_after_landing"
            elif frame in inliers:
                x, y = inliers[frame]
                evidence = "aerial_motion_blob"
            elif any(abs(frame - t) <= reach for t in inliers):
                x, y = _aerial_position(model, frame)
                evidence = "aerial_flight_path"
            else:
                ledger.reject(frame, AERIAL_MODULE, "aerial_frame_not_supported")
                continue
            record = records_by_frame.get(frame, {})
            ledger.confirm(
                frame,
                x=x,
                y=y,
                confirming_module=AERIAL_MODULE,
                evidence={
                    "inlier_frames": count,
                    "gap": [left, right],
                    "kind": evidence,
                },
                confidence=min(1.0, count / max(1, right - left - 1)),
                clip_seconds=float(record.get("clip_seconds", frame / fps)),
                point_evidence=evidence,
                point_source_attribution="motion_flight_path",
            )
    return ledger


AERIAL_ONE_SIDED_MODULE = "07_aerial_one_sided_flight"

# A long lofted ball can land far from the next confirmed position, so no
# flight joins both ends of the gap. The ball still leaves a motion trail as
# it leaves (or arrives at) a confirmed position. A kicked ball first moves in
# a near straight line, which a player's feet or body never do for long. That
# straight seed is followed with a curve fitted over its recent points, so a
# single stray blob beside a player cannot pull the track off the ball. The
# kick itself is often hidden in clutter at the player's feet, and the ball
# can rest there for a few frames before it is struck, so a flight may also
# start from two fast blobs whose line points straight back to the anchor.
# A fast ball's motion streak wobbles more than a slow one, so the catch
# radius grows with the ball's speed and the curve bends from four points. A
# followed track lasting at least 0.8 seconds is the flight (a lofted ball is
# often hidden behind players for the rest of its fall); only the frames it
# covers are filled and the rest of the gap stays open.
AERIAL_ONE_SIDED_PROFILE = FrozenProfile({
    "minimum_track_seconds": 0.8,
    # A shorter flight counts only when a followed trail joins its open end
    # to the confirmed point at the other end of the gap.
    "joined_minimum_track_seconds": 0.4,
    # A ball can vanish for a frame or two against the stand or a line.
    "maximum_dropout_frames": 2,
    "search_frames": 125,
    "seed_points": 8,
    "seed_straightness_pixels": 2.0,
    "seed_minimum_pixels_per_frame": 3.0,
    # The long window smooths a wobbling streak; the short one follows the
    # sharp bend at the top of a high flight seen through the lens.
    "follow_window_points": 8,
    "follow_short_window_points": 5,
    "follow_curve_minimum_points": 4,
    "follow_radius_pixels": 6.0,
    "follow_radius_speed_fraction": 0.25,
    "kick_line_search_frames": 10,
    "kick_line_distance_pixels": 8.0,
    "follow_radius_growth_pixels": 2.0,
    "still_blob_frames": 3,
    "still_blob_pixels": 3.0,
    "still_blob_minimum_frames": 2,
    "follow_maximum_misses": 5,
    # A kicked ball leaves faster than a player can run. Measured in the
    # height of a player standing at the launch spot, so the near and far
    # side of the pitch are judged alike, a slower trail is a player's legs
    # or kit, not the ball.
    "minimum_launch_player_heights_per_second": 3.0,
    "launch_points": 8,
})

def _aerial_bridged_tracklets(blobs, maximum_dropout):
    """Motion tracks that may skip up to ``maximum_dropout`` empty frames."""
    profile = AERIAL_PROFILE
    link = float(profile["link_distance_pixels"])
    predict = float(profile["link_prediction_pixels"])
    open_tracks: list[list[tuple[int, float, float]]] = []
    finished = []
    for t in sorted(blobs):
        kept = []
        used = set()
        for track in open_tracks:
            last = track[-1]
            elapsed = t - last[0]
            if elapsed > 1 + maximum_dropout:
                finished.append(track)
                continue
            if len(track) >= 2:
                before = track[-2]
                step = last[0] - before[0]
                vx = (last[1] - before[1]) / step
                vy = (last[2] - before[2]) / step
                target = (last[1] + vx * elapsed, last[2] + vy * elapsed)
                radius = predict * elapsed
            else:
                target, radius = (last[1], last[2]), link * elapsed
            options = [
                (hypot(x - target[0], y - target[1]), i)
                for i, (x, y) in enumerate(blobs[t])
                if i not in used
            ]
            best = min(options, default=None)
            if best is None or best[0] > radius:
                if elapsed < 1 + maximum_dropout:
                    kept.append(track)
                else:
                    finished.append(track)
                continue
            used.add(best[1])
            x, y = blobs[t][best[1]]
            kept.append([*track, (t, x, y)])
        for i, (x, y) in enumerate(blobs[t]):
            if i not in used:
                kept.append([(t, x, y)])
        open_tracks = kept
    finished.extend(open_tracks)
    return finished


def _aerial_straight_seed(track):
    """The track's first points when they form a fast, near straight line."""
    profile = AERIAL_ONE_SIDED_PROFILE
    count = int(profile["seed_points"])
    if len(track) < count:
        return None
    seed = np.array(track[:count], dtype=float)
    t = seed[:, 0]
    residual = np.hypot(
        *(seed[:, k] - np.polyval(np.polyfit(t, seed[:, k], 1), t) for k in (1, 2))
    )
    if float(residual.max()) > float(profile["seed_straightness_pixels"]):
        return None
    speed = hypot(seed[-1, 1] - seed[0, 1], seed[-1, 2] - seed[0, 2]) / (t[-1] - t[0])
    if speed < float(profile["seed_minimum_pixels_per_frame"]):
        return None
    return list(track[:count])


def _aerial_moving_blobs(blobs):
    """``blobs`` without those that stay put, as scenery or a player does.

    A ball in flight moves several pixels each frame, so it cannot be found
    at the same spot in two other frames close in time.
    """
    profile = AERIAL_ONE_SIDED_PROFILE
    frames = int(profile["still_blob_frames"])
    radius = float(profile["still_blob_pixels"])
    needed = int(profile["still_blob_minimum_frames"])
    cells = {
        t: {
            (int(x // radius), int(y // radius))
            for x, y in points
        }
        for t, points in blobs.items()
    }
    near = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
    moving = {}
    for t, points in blobs.items():
        kept = []
        for x, y in points:
            cx, cy = int(x // radius), int(y // radius)
            hits = 0
            for other in range(t - frames, t + frames + 1):
                if other == t or other not in cells:
                    continue
                if not any((cx + dx, cy + dy) in cells[other] for dx, dy in near):
                    continue
                if any(
                    hypot(ox - x, oy - y) <= radius
                    for ox, oy in blobs[other]
                ):
                    hits += 1
            if hits < needed:
                kept.append((x, y))
        moving[t] = kept
    return moving


def _aerial_follow_flight(seed, blobs, last_frame):
    """Follow a seed through ``blobs`` with a curve fitted to its recent points."""
    profile = AERIAL_ONE_SIDED_PROFILE
    windows = (
        int(profile["follow_window_points"]),
        int(profile["follow_short_window_points"]),
    )
    radius = float(profile["follow_radius_pixels"])
    fraction = float(profile["follow_radius_speed_fraction"])
    curve_points = int(profile["follow_curve_minimum_points"])
    growth = float(profile["follow_radius_growth_pixels"])
    allowed = int(profile["follow_maximum_misses"])
    track = list(seed)
    t = track[-1][0]
    misses = 0
    while t < last_frame:
        t += 1
        predictions = []
        for window in windows:
            recent = np.array(track[-window:], dtype=float)
            degree = 2 if len(recent) >= curve_points else 1
            predictions.append((
                float(np.polyval(np.polyfit(recent[:, 0], recent[:, 1], degree), t)),
                float(np.polyval(np.polyfit(recent[:, 0], recent[:, 2], degree), t)),
            ))
        # A curve bent by one noisy point overshoots across a dropout, so a
        # straight line through the long window is the last fallback.
        recent = np.array(track[-windows[0]:], dtype=float)
        predictions.append((
            float(np.polyval(np.polyfit(recent[:, 0], recent[:, 1], 1), t)),
            float(np.polyval(np.polyfit(recent[:, 0], recent[:, 2], 1), t)),
        ))
        before, last = track[-2], track[-1]
        speed = hypot(last[1] - before[1], last[2] - before[2]) / (last[0] - before[0])
        reach = max(radius, fraction * speed) + growth * (t - last[0] - 1)
        # Shorter or straighter predictions are asked only when the long curve
        # finds nothing, so clutter beside a smooth flight cannot pull it away.
        best = None
        moving = blobs.get(t, [])
        for px, py in predictions:
            best = min(
                ((hypot(x - px, y - py), x, y) for x, y in moving),
                default=None,
            )
            if best is not None and best[0] <= reach:
                break
        if best is not None and best[0] <= reach:
            track.append((t, best[1], best[2]))
            misses = 0
            continue
        misses += 1
        if misses > allowed:
            break
    return track


def _aerial_kick_line_seeds(anchor, blobs):
    """Pairs of fast blobs whose line of flight points back to ``anchor``.

    The ball may rest at the anchor before it is struck, so the pair's line
    must pass the anchor at a kick time no earlier than the anchor frame.
    """
    profile = AERIAL_ONE_SIDED_PROFILE
    frames = int(profile["kick_line_search_frames"])
    offset = float(profile["kick_line_distance_pixels"])
    minimum_speed = float(profile["seed_minimum_pixels_per_frame"])
    t0, x0, y0 = anchor
    seeds = []
    for t1 in range(t0 + 1, t0 + frames + 1):
        for x1, y1 in blobs.get(t1, []):
            for t2 in (t1 + 1, t1 + 2):
                for x2, y2 in blobs.get(t2, []):
                    vx = (x2 - x1) / (t2 - t1)
                    vy = (y2 - y1) / (t2 - t1)
                    speed = hypot(vx, vy)
                    if speed < minimum_speed:
                        continue
                    bx, by = x1 - x0, y1 - y0
                    along = (bx * vx + by * vy) / speed
                    if along <= 0 or abs(bx * vy - by * vx) / speed > offset:
                        continue
                    if t1 - along / speed < t0 - 1:
                        continue
                    seeds.append([(t1, x1, y1), (t2, x2, y2)])
    return seeds


def _aerial_trail_flights(anchor, blobs):
    """Every flight followed from a fast straight trail leaving ``anchor``.

    This one trail follower serves every aerial ball: a seed is a fast near
    straight trail starting beside the anchor, or two fast blobs whose line
    points back to it, and each seed is followed with a curve fitted to its
    recent points.
    """
    profile = AERIAL_ONE_SIDED_PROFILE
    dropout = int(profile["maximum_dropout_frames"])
    reach = float(AERIAL_PROFILE["link_distance_pixels"])
    seeds = []
    for track in _aerial_bridged_tracklets(blobs, dropout):
        if track[0][0] > anchor[0] + 1 + dropout:
            continue
        if hypot(track[0][1] - anchor[1], track[0][2] - anchor[2]) > reach:
            continue
        seed = _aerial_straight_seed(track)
        if seed is not None:
            seeds.append(seed)
    seeds.extend(_aerial_kick_line_seeds(anchor, blobs))
    last_frame = max(blobs, default=anchor[0])
    moving = _aerial_moving_blobs(blobs)
    return [_aerial_follow_flight(seed, moving, last_frame) for seed in seeds]


def _aerial_player_height_at(records_by_frame):
    """Player height in pixels as a straight function of the feet's image row.

    Returns None when the detections cannot give a scale.
    """
    minimum = float(AERIAL_PROFILE["person_minimum_confidence"])
    feet, heights = [], []
    for record in records_by_frame.values():
        for d in record.get("detections", []):
            if d.get("class_name") != "person" or float(d["confidence"]) < minimum:
                continue
            feet.append(float(d["y2"]))
            heights.append(float(d["y2"]) - float(d["y1"]))
    if len(feet) < 2 or max(feet) - min(feet) <= 0:
        return None
    slope, offset = np.polyfit(feet, heights, 1)
    floor = float(np.median(heights)) * 0.25

    def height_at(y):
        return max(floor, float(slope * y + offset))

    return height_at


def _aerial_launch_fast_enough(flight, anchor, fps, height_at):
    if height_at is None:
        return True
    profile = AERIAL_ONE_SIDED_PROFILE
    launch = flight[: int(profile["launch_points"])]
    if len(launch) < 2 or launch[-1][0] == launch[0][0]:
        return False
    speed = hypot(
        launch[-1][1] - launch[0][1], launch[-1][2] - launch[0][2]
    ) / (launch[-1][0] - launch[0][0]) * fps
    needed = float(profile["minimum_launch_player_heights_per_second"])
    return speed >= needed * height_at(anchor[2])


def _aerial_one_sided_track(anchor, blobs, fps, minimum_seconds=None, height_at=None):
    """The unique flight track leaving ``anchor`` (time, x, y) forwards in time."""
    if minimum_seconds is None:
        minimum_seconds = float(AERIAL_ONE_SIDED_PROFILE["minimum_track_seconds"])
    minimum_frames = float(minimum_seconds) * fps
    flights = _aerial_trail_flights(anchor, blobs)
    flights = [
        flight for flight in flights
        if flight[-1][0] - flight[0][0] + 1 >= minimum_frames
        and _aerial_launch_fast_enough(flight, anchor, fps, height_at)
    ]
    if not flights:
        return None
    # The trail that finds the ball in the most frames is the ball; a trail
    # skipping along the edges of a blurred streak covers fewer frames.
    flights.sort(key=lambda flight: (-len(flight), -(flight[-1][0] - flight[0][0])))
    best = flights[0]
    best_at = {t: (x, y) for t, x, y in best}
    separation = float(AERIAL_PROFILE["rival_separation_pixels"])
    for rival in flights[1:]:
        # A trail lost while the best one is followed for at least another
        # whole flight was clutter that could not be followed.
        if best[-1][0] - rival[-1][0] >= minimum_frames:
            continue
        if not any(t in best_at for t, _, _ in rival):
            return None
        if _aerial_runs_apart(best_at, rival, separation):
            return None
    return best


def _aerial_joined_tracks(s, e, forward, backward, fps, height_at=None):
    """Short flights from either end of a gap that a followed trail joins.

    ``forward`` holds the blobs searched from ``s`` and ``backward`` those
    searched from ``e``, in video time. A flight too short to stand alone is
    kept only when the trail follower links its open end to the confirmed
    point at the other end, so the ball is followed between both ends.
    """
    shortest = float(AERIAL_ONE_SIDED_PROFILE["joined_minimum_track_seconds"])
    right = e[0]
    found = []
    track = _aerial_one_sided_track(s, forward, fps, shortest, height_at)
    if track is not None:
        open_end = track[-1]
        inside = {t: c for t, c in backward.items() if open_end[0] < t < right}
        joined = _aerial_followed_path(open_end, e, inside)
        if joined is not None:
            found.append(track + sorted((t, x, y) for t, (x, y) in joined[2].items()))
    mirrored = {right - t: c for t, c in backward.items()}
    track = _aerial_one_sided_track((0, e[1], e[2]), mirrored, fps, shortest, height_at)
    if track is not None:
        track = [(right - t, x, y) for t, x, y in reversed(track)]
        open_end = track[0]
        inside = {t: c for t, c in forward.items() if s[0] < t < open_end[0]}
        joined = _aerial_followed_path(s, open_end, inside)
        if joined is not None:
            found.append(sorted((t, x, y) for t, (x, y) in joined[2].items()) + track)
    return found


def _aerial_track_position(track, frame):
    points = {t: (x, y) for t, x, y in track}
    if frame in points:
        return points[frame], "aerial_motion_blob"
    before = max(t for t in points if t < frame)
    after = min(t for t in points if t > frame)
    u = (frame - before) / (after - before)
    return (
        points[before][0] + (points[after][0] - points[before][0]) * u,
        points[before][1] + (points[after][1] - points[before][1]) * u,
    ), "aerial_flight_path"


def _confirm_one_sided_aerial_flights(
    ledger: FrameLedger,
    *,
    records_by_frame: dict[int, dict[str, Any]],
    video: Path,
    fps: float,
    max_speed_pixels_per_second: float,
) -> FrameLedger:
    profile = AERIAL_ONE_SIDED_PROFILE
    entries = ledger.entries
    frames = sorted(entries)
    sampled = sorted(records_by_frame)
    max_step = max_speed_pixels_per_second / fps
    search = int(profile["search_frames"])

    def people_by_frame(t):
        nearest = min(sampled, key=lambda f: abs(f - t))
        return [
            (float(d["x1"]), float(d["y1"]), float(d["x2"]), float(d["y2"]))
            for d in records_by_frame[nearest].get("detections", [])
            if d.get("class_name") == "person"
            and float(d["confidence"])
            >= float(AERIAL_PROFILE["person_minimum_confidence"])
        ]

    height_at = _aerial_player_height_at(records_by_frame)
    confirmed = [
        frame for frame in frames
        if entries[frame].status == "confirmed" and entries[frame].x is not None
    ]
    plans = []
    for left, right in zip(confirmed, confirmed[1:]):
        gap = [f for f in frames if left < f < right]
        if right - left < int(AERIAL_PROFILE["minimum_gap_frames"]):
            continue
        if not gap or any(entries[f].status == "confirmed" for f in gap):
            continue
        plans.append((left, right, gap))

    def search_gap(plan):
        left, right, _ = plan
        s = (left, float(entries[left].x), float(entries[left].y))
        e = (right, float(entries[right].x), float(entries[right].y))
        found = []
        # Forwards from the left end, then backwards from the right end. The
        # far end of each search window is placed so it never limits reach.
        end = min(right, left + search)
        forward = _aerial_streamed_blobs(
            video, left, end, people_by_frame, s,
            (left + 2 * (end - left), s[1], s[2]), max_step,
        )
        track = _aerial_one_sided_track(s, forward, fps, height_at=height_at)
        if track is not None:
            found.append(track)
        start = max(left, right - search)
        backward = _aerial_streamed_blobs(
            video, start, right, people_by_frame,
            (right - 2 * (right - start), e[1], e[2]), e, max_step,
        )
        mirrored = {right - t: blobs for t, blobs in backward.items()}
        track = _aerial_one_sided_track((0, e[1], e[2]), mirrored, fps, height_at=height_at)
        if track is not None:
            found.append([(right - t, x, y) for t, x, y in reversed(track)])
        if not found:
            found = _aerial_joined_tracks(s, e, forward, backward, fps, height_at)
        return found

    results = _ordered_parallel_map(search_gap, plans)
    for (left, right, gap), tracks in zip(plans, results):
        if not tracks:
            for frame in gap:
                ledger.reject(frame, AERIAL_ONE_SIDED_MODULE, "aerial_no_one_sided_flight")
            continue
        for frame in gap:
            if ledger.confirmed(frame) is not None:
                continue
            track = next(
                (track for track in tracks if track[0][0] <= frame <= track[-1][0]),
                None,
            )
            if track is None:
                ledger.reject(frame, AERIAL_ONE_SIDED_MODULE, "aerial_frame_not_covered")
                continue
            (x, y), evidence = _aerial_track_position(track, frame)
            record = records_by_frame.get(frame, {})
            ledger.confirm(
                frame,
                x=x,
                y=y,
                confirming_module=AERIAL_ONE_SIDED_MODULE,
                evidence={
                    "track_frames": [track[0][0], track[-1][0]],
                    "gap": [left, right],
                    "kind": evidence,
                },
                confidence=min(1.0, len(track) / max(1, track[-1][0] - track[0][0] + 1)),
                clip_seconds=float(record.get("clip_seconds", frame / fps)),
                point_evidence=evidence,
                point_source_attribution="motion_flight_path",
            )
    return ledger
