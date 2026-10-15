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


def _aerial_end_to_end_tracklet(s, e, tracks):
    """One unbroken motion track from beside one confirmed end to the other.

    A high flight seen through the panorama lens does not follow a simple
    curve, but the ball still moves in every frame. A track linked frame by
    frame from launch to landing is then direct evidence of the flight, as
    long as no other track also joins both ends.
    """
    reach = float(AERIAL_PROFILE["link_distance_pixels"])
    joining = [
        track
        for track in tracks
        if track[0][0] == s[0] + 1
        and track[-1][0] == e[0] - 1
        and hypot(track[0][1] - s[1], track[0][2] - s[2]) <= reach
        and hypot(track[-1][1] - e[1], track[-1][2] - e[2]) <= reach
    ]
    if len(joining) != 1:
        return None
    track = joining[0]
    inliers = {t: (x, y) for t, x, y in track}
    return len(inliers), (s, e, (0.0, 0.0, 0.0, 0.0)), inliers


def _aerial_best_path(s, e, blobs):
    best = _aerial_curve_path(s, e, blobs)
    if best is not None:
        return best
    return _aerial_end_to_end_tracklet(s, e, _aerial_tracklets(blobs))


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
# single stray blob beside a player cannot pull the track off the ball. A
# followed track lasting at least 0.8 seconds is the flight (a lofted ball is
# often hidden behind players for the rest of its fall); only the frames it
# covers are filled and the rest of the gap stays open.
AERIAL_ONE_SIDED_PROFILE = FrozenProfile({
    "minimum_track_seconds": 0.8,
    # A ball can vanish for a frame or two against the stand or a line.
    "maximum_dropout_frames": 2,
    "search_frames": 125,
    "seed_points": 8,
    "seed_straightness_pixels": 2.0,
    "seed_minimum_pixels_per_frame": 3.0,
    "follow_window_points": 12,
    "follow_radius_pixels": 6.0,
    "follow_radius_growth_pixels": 2.0,
    "follow_maximum_misses": 5,
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


def _aerial_follow_flight(seed, blobs, last_frame):
    """Follow a seed through ``blobs`` with a curve fitted to its recent points."""
    profile = AERIAL_ONE_SIDED_PROFILE
    window = int(profile["follow_window_points"])
    radius = float(profile["follow_radius_pixels"])
    growth = float(profile["follow_radius_growth_pixels"])
    allowed = int(profile["follow_maximum_misses"])
    track = list(seed)
    t = track[-1][0]
    misses = 0
    while t < last_frame:
        t += 1
        recent = np.array(track[-window:], dtype=float)
        degree = 2 if len(recent) >= 6 else 1
        px = float(np.polyval(np.polyfit(recent[:, 0], recent[:, 1], degree), t))
        py = float(np.polyval(np.polyfit(recent[:, 0], recent[:, 2], degree), t))
        reach = radius + growth * (t - track[-1][0] - 1)
        best = min(
            ((hypot(x - px, y - py), x, y) for x, y in blobs.get(t, [])),
            default=None,
        )
        if best is not None and best[0] <= reach:
            track.append((t, best[1], best[2]))
            misses = 0
            continue
        misses += 1
        if misses > allowed:
            break
    return track


def _aerial_one_sided_track(anchor, blobs, fps):
    """The unique flight track leaving ``anchor`` (time, x, y) forwards in time."""
    profile = AERIAL_ONE_SIDED_PROFILE
    dropout = int(profile["maximum_dropout_frames"])
    reach = float(AERIAL_PROFILE["link_distance_pixels"])
    minimum_frames = float(profile["minimum_track_seconds"]) * fps
    seeds = []
    for track in _aerial_bridged_tracklets(blobs, dropout):
        if track[0][0] > anchor[0] + 1 + dropout:
            continue
        if hypot(track[0][1] - anchor[1], track[0][2] - anchor[2]) > reach:
            continue
        seed = _aerial_straight_seed(track)
        if seed is not None:
            seeds.append(seed)
    if not seeds:
        return None
    last_frame = max(blobs, default=anchor[0])
    flights = [_aerial_follow_flight(seed, blobs, last_frame) for seed in seeds]
    flights = [
        flight for flight in flights
        if flight[-1][0] - flight[0][0] + 1 >= minimum_frames
    ]
    if not flights:
        return None
    flights.sort(key=lambda flight: -(flight[-1][0] - flight[0][0]))
    best = flights[0]
    best_at = {t: (x, y) for t, x, y in best}
    separation = float(AERIAL_PROFILE["rival_separation_pixels"])
    for rival in flights[1:]:
        shared = [
            hypot(x - best_at[t][0], y - best_at[t][1])
            for t, x, y in rival
            if t in best_at
        ]
        if not shared or max(shared) > separation:
            return None
    return best

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
        track = _aerial_one_sided_track(s, forward, fps)
        if track is not None:
            found.append(track)
        start = max(left, right - search)
        backward = _aerial_streamed_blobs(
            video, start, right, people_by_frame,
            (right - 2 * (right - start), e[1], e[2]), e, max_step,
        )
        mirrored = {right - t: blobs for t, blobs in backward.items()}
        track = _aerial_one_sided_track((0, e[1], e[2]), mirrored, fps)
        if track is not None:
            found.append([(right - t, x, y) for t, x, y in reversed(track)])
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
