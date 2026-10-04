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
    "maximum_blob_area": 400,
    "maximum_blob_side": 40,
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


def _aerial_inliers(s, e, params, blobs):
    tolerance = float(AERIAL_PROFILE["inlier_pixels"])
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


def _aerial_blobs(gray, start, end, people_by_frame, s, e, max_step):
    profile = AERIAL_PROFILE
    blobs: dict[int, list[tuple[float, float]]] = {}
    for t in range(start + 1, end):
        if t - 1 not in gray or t + 1 not in gray:
            continue
        difference = cv2.min(
            cv2.absdiff(gray[t], gray[t - 1]),
            cv2.absdiff(gray[t], gray[t + 1]),
        )
        _, mask = cv2.threshold(
            difference, int(profile["difference_threshold"]), 255, cv2.THRESH_BINARY
        )
        count, _, stats, centres = cv2.connectedComponentsWithStats(mask)
        people = people_by_frame(t)
        found = []
        for index in range(1, count):
            area = int(stats[index, cv2.CC_STAT_AREA])
            if not (
                int(profile["minimum_blob_area"])
                <= area
                <= int(profile["maximum_blob_area"])
            ):
                continue
            if max(stats[index, cv2.CC_STAT_WIDTH], stats[index, cv2.CC_STAT_HEIGHT]) > int(
                profile["maximum_blob_side"]
            ):
                continue
            x, y = float(centres[index][0]), float(centres[index][1])
            if hypot(x - s[1], y - s[2]) > max_step * (t - s[0]) + 20:
                continue
            if hypot(x - e[1], y - e[2]) > max_step * (e[0] - t) + 20:
                continue
            if any(x1 <= x <= x2 and y1 <= y <= y2 for x1, y1, x2, y2 in people):
                continue
            found.append((x, y))
        if found:
            blobs[t] = found
    return blobs


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


def _aerial_model(s, e, points, blobs, window=None):
    launch, landing = window or _aerial_flight_window(s, e, points)
    s2 = (launch, s[1], s[2])
    e2 = (landing, e[1], e[2])
    inside = [p for p in points if launch < p[0] < landing]
    params = _aerial_fit(s2, e2, inside)
    if params is None:
        return None
    flight_blobs = {t: c for t, c in blobs.items() if launch < t < landing}
    inliers = _aerial_inliers(s2, e2, params, flight_blobs)
    return (s2, e2, params), inliers


def _aerial_best_path(s, e, blobs):
    profile = AERIAL_PROFILE
    models = []
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
                fitted = _aerial_model(s, e, track, blobs, (launch, landing))
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
        if hypot(e[1] - s[1], e[2] - s[2]) < float(
            profile["minimum_end_to_end_pixels_per_frame"]
        ) * (right - left):
            for frame in gap:
                ledger.reject(frame, AERIAL_MODULE, "aerial_ends_did_not_travel")
            continue
        gray = _read_gray_range(video, left - 1, right + 1)
        blobs = _aerial_blobs(gray, left, right, people_by_frame, s, e, max_step)
        if profile["empty_pitch_spots"]:
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
            blobs = _merge_spots(blobs, spots)
        best = _aerial_best_path(s, e, blobs)
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
