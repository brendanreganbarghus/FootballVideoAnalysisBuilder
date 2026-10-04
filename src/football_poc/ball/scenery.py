from __future__ import annotations

from .settings import *  # noqa: F401,F403


SCENERY_MODULE = "07_scenery_check"
SCENERY_PROFILE = {
    # Frames sampled evenly across the clip to build its median background.
    "background_samples": 31,
    "patch_radius": 6,
    # Mean absolute grey-level difference below which the patch is the same
    # as the clip background: a spare ball, line mark or post that stays put
    # for most of the clip, not the match ball.
    "maximum_background_difference": 5.0,
    # Once a spot is proven to be scenery, other points on that same spot
    # are scenery too unless they clearly differ from the background.
    "scenery_spot_radius": 8.0,
    "scenery_spot_difference": 10.0,
    # A ball in flight is a small blur that also looks like its background,
    # and chain locks are already proven by motion, so only single-frame
    # visual recoveries are checked.
    "checked_modules": (
        "01_confirm_yolo",
        "03_motion_and_optical_flow",
        "04_focused_multiscale",
        "05_short_stationary",
        "06_time_machine_region_search",
    ),
}


def _scenery_background_differences(
    gray_frames: dict[int, np.ndarray],
    background: np.ndarray,
    points: dict[int, tuple[float, float]],
) -> dict[int, float]:
    radius = int(SCENERY_PROFILE["patch_radius"])
    differences: dict[int, float] = {}
    for frame, (x, y) in points.items():
        gray = gray_frames.get(frame)
        if gray is None:
            continue
        cx, cy = int(round(x)), int(round(y))
        y1, y2, x1, x2 = cy - radius, cy + radius + 1, cx - radius, cx + radius + 1
        if y1 < 0 or x1 < 0 or y2 > gray.shape[0] or x2 > gray.shape[1]:
            continue
        patch = gray[y1:y2, x1:x2].astype(np.int16)
        reference = background[y1:y2, x1:x2].astype(np.int16)
        differences[frame] = float(np.abs(patch - reference).mean())
    return differences


def _confirm_scenery_check(
    ledger: FrameLedger,
    *,
    video: Path,
) -> FrameLedger:
    checked = set(SCENERY_PROFILE["checked_modules"])
    points = {
        entry.source_frame: (float(entry.x), float(entry.y))
        for entry in ledger.confirmed_entries()
        if entry.confirming_module in checked
    }
    if not points:
        return ledger
    capture = cv2.VideoCapture(str(video))
    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count <= 0:
            return ledger
        samples = set(
            np.linspace(
                0, frame_count - 1, int(SCENERY_PROFILE["background_samples"])
            ).astype(int).tolist()
        )
        last = max(max(samples), max(points))
        sampled: list[np.ndarray] = []
        grays: dict[int, np.ndarray] = {}
        for frame in range(last + 1):
            if frame not in samples and frame not in points:
                if not capture.grab():
                    break
                continue
            ok, image = capture.read()
            if not ok:
                break
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            if frame in samples:
                sampled.append(gray)
            if frame in points:
                grays[frame] = gray
    finally:
        capture.release()
    if len(sampled) < 3:
        return ledger
    background = np.median(np.stack(sampled), axis=0).astype(np.uint8)
    limit = float(SCENERY_PROFILE["maximum_background_difference"])
    differences = _scenery_background_differences(grays, background, points)
    scenery_spots = [
        points[frame]
        for frame, difference in differences.items()
        if difference < limit
    ]
    spot_radius = float(SCENERY_PROFILE["scenery_spot_radius"])
    spot_limit = float(SCENERY_PROFILE["scenery_spot_difference"])
    for frame, difference in differences.items():
        x, y = points[frame]
        on_spot = difference < spot_limit and any(
            hypot(x - sx, y - sy) <= spot_radius for sx, sy in scenery_spots
        )
        if difference < limit or on_spot:
            ledger.veto(
                frame,
                SCENERY_MODULE,
                f"patch matches clip background (difference {difference:.1f})",
            )
    return ledger
