"""Separate ball check by elimination (diagnostic, not part of the tracker).

Everything on the calibrated pitch that is not the ball is removed: the
players, the grass, the painted lines and whatever matches the empty pitch
(the median of nearby frames). What is left over are ball candidates. Four
small checks each propose candidates in every frame:

1. open pitch (the plain leftovers);
2. on a painted line (hand-calibrated lines when available);
3. at a player's feet;
4. in the air above the calibrated pitch area.

One candidate per frame, or none ("behind a player"), is then chosen as the
most continuous path over the clip.

Inputs are the raw video, the pitch calibration and the cached YOLO person
boxes only. YOLO ball boxes, review decisions and provider coordinates are
never read. On 06:00-07:00 it agrees with the tracker on far fewer frames
than the tracker agrees with the reviewer, so it stays a diagnostic.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np

from football_poc.image_space import scale_factors

ELIMINATION_PROFILE = {
    # The painted touch and goal lines run along the calibrated edge.
    "pitch_edge_pixels": 12,
    "person_minimum_confidence": 0.1,
    "person_margin_pixels": 4,
    "grass_hsv_low": (30, 40, 20),
    "grass_hsv_high": (90, 255, 255),
    # Painted lines: bright thin marks forming long connected strokes.
    "line_tophat_kernel": 9,
    "line_tophat_threshold": 25,
    "line_minimum_length_pixels": 60,
    "line_margin_pixels": 3,
    # A ball-sized leftover: small, filled, roughly round and brighter
    # than the turf right around it.
    "ball_minimum_area": 10,
    "ball_maximum_area": 300,
    "ball_maximum_side": 25,
    "ball_minimum_fill": 0.4,
    "ball_maximum_aspect": 2.5,
    "ball_minimum_contrast": 40,
    "contrast_ring_pixels": 7,
    # A ball on a line is wider than the line: it survives an opening by a
    # disc the line is too thin for.
    "line_ball_disc_pixels": 5,
    # Feet region of a person box, as fractions of its width and height.
    "feet_side_fraction": 0.5,
    "feet_top_fraction": 0.6,
    "feet_below_fraction": 0.3,
    "feet_minimum_fill": 0.5,
    "feet_maximum_aspect": 1.6,
    # Aerial: a small moving blob outside the pitch area.
    "aerial_difference_threshold": 12,
    "aerial_pitch_margin_pixels": 10,
    "aerial_minimum_area": 6,
    "aerial_maximum_area": 300,
    "aerial_maximum_side": 25,
    # Empty pitch: the median of frames sampled around the frame. Players and
    # a moving ball fade out of it; lines, corners and other fixed marks stay,
    # so a leftover must differ from it to be the ball.
    "background_step_frames": 15,
    "background_reach_frames": 75,
    "background_difference": 30,
    "background_margin_pixels": 2,
    # The painted-line map is read once from the whole clip's empty pitch,
    # reaching a little past the calibrated edge for the outer lines.
    "static_line_reach_pixels": 15,
    "line_ball_minimum_value": 120,
    # Hand-calibrated markings are traced on the outer edge of the paint;
    # the band around each traced line covers the painted width.
    "calibrated_line_band_pixels": 8,
    # Continuity: a ball moves at most this far per frame; each frame behind
    # a player costs a fixed amount; each stage has its own trust cost.
    "maximum_speed_pixels_per_frame": 60,
    "distance_cost_pixels_per_frame": 30,
    "hidden_cost": 1.5,
    "maximum_hidden_samples": 12,
    "stage_cost": {"open_pitch": 0.0, "on_line": 0.5, "at_feet": 0.8, "aerial": 0.8},
}

Box = tuple[float, float, float, float]


def pitch_mask(calibration: dict[str, Any], width: int, height: int, *, edge: int = 0) -> np.ndarray:
    """The calibrated pitch area in video pixels, shrunk by ``edge`` pixels."""
    sx, sy = scale_factors(calibration, (float(width), float(height)))
    polygon = np.array(
        [[x * sx, y * sy] for x, y in calibration["boundary"]], dtype=np.int32
    )
    mask = np.zeros((height, width), np.uint8)
    cv2.fillPoly(mask, [polygon], 255)
    if edge > 0:
        mask = cv2.erode(mask, np.ones((2 * edge + 1, 2 * edge + 1), np.uint8))
    return mask


def person_boxes(record: dict[str, Any]) -> list[Box]:
    minimum = float(ELIMINATION_PROFILE["person_minimum_confidence"])
    return [
        (float(d["x1"]), float(d["y1"]), float(d["x2"]), float(d["y2"]))
        for d in record.get("detections", [])
        if d.get("class_name") == "person" and float(d["confidence"]) >= minimum
    ]


def _remove_boxes(mask: np.ndarray, boxes: Iterable[Box], margin: int) -> np.ndarray:
    out = mask.copy()
    for x1, y1, x2, y2 in boxes:
        cv2.rectangle(
            out,
            (int(x1) - margin, int(y1) - margin),
            (int(x2) + margin, int(y2) + margin),
            0,
            -1,
        )
    return out


def grass_mask(hsv: np.ndarray) -> np.ndarray:
    p = ELIMINATION_PROFILE
    return cv2.inRange(hsv, p["grass_hsv_low"], p["grass_hsv_high"])


def bright_marks(gray: np.ndarray) -> np.ndarray:
    p = ELIMINATION_PROFILE
    kernel = np.ones((p["line_tophat_kernel"],) * 2, np.uint8)
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    return (tophat > p["line_tophat_threshold"]).astype(np.uint8) * 255


def painted_line_mask(gray: np.ndarray, area: np.ndarray) -> np.ndarray:
    """Long bright strokes inside ``area``: the painted pitch markings."""
    p = ELIMINATION_PROFILE
    marks = cv2.bitwise_and(bright_marks(gray), area)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(marks)
    lines = np.zeros_like(marks)
    for index in range(1, count):
        if max(stats[index, 2], stats[index, 3]) >= p["line_minimum_length_pixels"]:
            lines[labels == index] = 255
    margin = 2 * p["line_margin_pixels"] + 1
    return cv2.dilate(lines, np.ones((margin, margin), np.uint8))


def ball_sized_blobs(
    mask: np.ndarray,
    value: np.ndarray,
    *,
    minimum_fill: float | None = None,
    maximum_aspect: float | None = None,
    minimum_contrast: float | None = None,
) -> list[tuple[float, float, int]]:
    """Ball-sized, roughly round leftovers clearly brighter than their ring."""
    p = ELIMINATION_PROFILE
    fill = p["ball_minimum_fill"] if minimum_fill is None else minimum_fill
    aspect = p["ball_maximum_aspect"] if maximum_aspect is None else maximum_aspect
    contrast = p["ball_minimum_contrast"] if minimum_contrast is None else minimum_contrast
    count, labels, stats, centres = cv2.connectedComponentsWithStats(mask)
    ring_kernel = np.ones((2 * p["contrast_ring_pixels"] + 1,) * 2, np.uint8)
    found = []
    for index in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[index])
        if not p["ball_minimum_area"] <= area <= p["ball_maximum_area"]:
            continue
        if max(w, h) > p["ball_maximum_side"]:
            continue
        if area / (w * h) < fill or max(w, h) / max(1, min(w, h)) > aspect:
            continue
        r = p["contrast_ring_pixels"]
        y0, x0 = max(0, y - r), max(0, x - r)
        local = labels[y0 : y + h + r, x0 : x + w + r] == index
        ring = cv2.dilate(local.astype(np.uint8), ring_kernel).astype(bool) & ~local
        patch = value[y0 : y + h + r, x0 : x + w + r]
        if not ring.any():
            continue
        if float(patch[local].mean()) - float(patch[ring].mean()) < contrast:
            continue
        found.append((float(centres[index][0]), float(centres[index][1]), area))
    return found


def _open(mask: np.ndarray) -> np.ndarray:
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))


def open_pitch_candidates(image, pitch, people, lines, hsv):
    """Steps 1-4: pitch, minus players, minus grass, minus painted lines."""
    p = ELIMINATION_PROFILE
    left = _remove_boxes(pitch, people, p["person_margin_pixels"])
    left = cv2.bitwise_and(left, cv2.bitwise_not(grass_mask(hsv)))
    left = cv2.bitwise_and(left, cv2.bitwise_not(lines))
    return ball_sized_blobs(_open(left), hsv[..., 2])


def feet_regions(people: Iterable[Box], width: int, height: int) -> list[tuple[int, int, int, int]]:
    p = ELIMINATION_PROFILE
    regions = []
    for x1, y1, x2, y2 in people:
        w, h = x2 - x1, y2 - y1
        regions.append((
            max(0, int(x1 - w * p["feet_side_fraction"])),
            max(0, int(y1 + h * p["feet_top_fraction"])),
            min(width, int(x2 + w * p["feet_side_fraction"])),
            min(height, int(y2 + h * p["feet_below_fraction"])),
        ))
    return regions


def feet_candidates(gray, pitch, people, hsv):
    """Inside each player's feet region: a round bright non-grass blob."""
    height, width = gray.shape
    region_mask = np.zeros_like(gray)
    for x1, y1, x2, y2 in feet_regions(people, width, height):
        region_mask[y1:y2, x1:x2] = 255
    left = cv2.bitwise_and(region_mask, pitch)
    left = cv2.bitwise_and(left, cv2.bitwise_not(grass_mask(hsv)))
    left = cv2.bitwise_and(left, bright_marks(gray))
    p = ELIMINATION_PROFILE
    return ball_sized_blobs(
        _open(left),
        hsv[..., 2],
        minimum_fill=p["feet_minimum_fill"],
        maximum_aspect=p["feet_maximum_aspect"],
    )


def aerial_candidates(previous, current, following, full_pitch, people):
    """A small moving blob above the calibrated pitch area."""
    p = ELIMINATION_PROFILE
    difference = cv2.min(cv2.absdiff(current, previous), cv2.absdiff(current, following))
    _, moving = cv2.threshold(difference, p["aerial_difference_threshold"], 255, cv2.THRESH_BINARY)
    margin = 2 * p["aerial_pitch_margin_pixels"] + 1
    outside = cv2.bitwise_not(cv2.dilate(full_pitch, np.ones((margin, margin), np.uint8)))
    # Only above the pitch: rows higher than the pitch top in that column.
    has_pitch = full_pitch.any(axis=0)
    top = np.where(has_pitch, full_pitch.argmax(axis=0), 0)
    rows = np.arange(full_pitch.shape[0])[:, None]
    above = (rows < top[None, :]).astype(np.uint8) * 255
    zone = _remove_boxes(cv2.bitwise_and(outside, above), people, ELIMINATION_PROFILE["person_margin_pixels"])
    moving = cv2.bitwise_and(moving, zone)
    count, _, stats, centres = cv2.connectedComponentsWithStats(moving)
    found = []
    for index in range(1, count):
        w, h, area = int(stats[index, 2]), int(stats[index, 3]), int(stats[index, 4])
        if not p["aerial_minimum_area"] <= area <= p["aerial_maximum_area"]:
            continue
        if max(w, h) > p["aerial_maximum_side"]:
            continue
        found.append((float(centres[index][0]), float(centres[index][1]), area))
    return found


STAGES = ("open_pitch", "on_line", "at_feet", "aerial")


def changed_from_background(gray: np.ndarray, background: np.ndarray) -> np.ndarray:
    """Pixels that differ from the empty pitch, i.e. not a fixed mark."""
    p = ELIMINATION_PROFILE
    changed = (cv2.absdiff(gray, background) > p["background_difference"]).astype(np.uint8) * 255
    margin = 2 * p["background_margin_pixels"] + 1
    return cv2.dilate(changed, np.ones((margin, margin), np.uint8))


def static_line_map(empty_pitch: np.ndarray, area: np.ndarray) -> np.ndarray:
    """The painted markings, read once from the empty pitch of the whole clip.

    Players and the ball fade out of a long median, so every long bright
    stroke left in it is a painted marking: straight lines, box corners, the
    centre circle and the arcs alike.
    """
    p = ELIMINATION_PROFILE
    reach = 2 * p["static_line_reach_pixels"] + 1
    return painted_line_mask(
        empty_pitch, cv2.dilate(area, np.ones((reach, reach), np.uint8))
    )


CALIBRATED_LINES = (
    "near_touchline",
    "far_touchline",
    "left_goal_line",
    "right_goal_line",
    "left_goal_area",
    "right_goal_area",
    "left_penalty_area",
    "right_penalty_area",
    "halfway_line",
)
CALIBRATED_LOOPS = ("centre_circle",)


def calibrated_line_map(calibration: dict[str, Any], width: int, height: int) -> np.ndarray | None:
    """The hand-calibrated painted markings as a band, or None when absent."""
    sx, sy = scale_factors(calibration, (float(width), float(height)))
    features = calibration.get("features", {})
    band = 2 * int(ELIMINATION_PROFILE["calibrated_line_band_pixels"]) + 1
    mask = np.zeros((height, width), np.uint8)
    drawn = False
    for name in (*CALIBRATED_LINES, *CALIBRATED_LOOPS):
        points = features.get(name) or []
        if len(points) < 2:
            continue
        polyline = np.array([[x * sx, y * sy] for x, y in points], np.int32)
        cv2.polylines(mask, [polyline], name in CALIBRATED_LOOPS, 255, band)
        drawn = True
    return mask if drawn else None


def line_candidates(gray, pitch, people, lines, hsv):
    """A ball on a line: bright, and different from the empty pitch there."""
    p = ELIMINATION_PROFILE
    zone = _remove_boxes(cv2.bitwise_and(lines, pitch), people, p["person_margin_pixels"])
    bright = cv2.inRange(hsv[..., 2], p["line_ball_minimum_value"], 255)
    return ball_sized_blobs(
        _open(cv2.bitwise_and(zone, bright)), hsv[..., 2], minimum_contrast=0
    )


def frame_candidates(previous, image, following, calibration, record, background, lines, line_zone=None):
    """Every stage's candidates for one frame, each tagged with its stage."""
    height, width = image.shape[:2]
    p = ELIMINATION_PROFILE
    full_pitch = pitch_mask(calibration, width, height)
    pitch = pitch_mask(calibration, width, height, edge=p["pitch_edge_pixels"])
    people = person_boxes(record)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    changed = changed_from_background(gray, background)
    moving_pitch = cv2.bitwise_and(pitch, changed)
    found = {
        "open_pitch": open_pitch_candidates(image, moving_pitch, people, lines, hsv),
        "on_line": line_candidates(gray, moving_pitch, people, lines if line_zone is None else line_zone, hsv),
        "at_feet": feet_candidates(gray, cv2.bitwise_and(full_pitch, changed), people, hsv),
        "aerial": aerial_candidates(
            cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY),
            gray,
            cv2.cvtColor(following, cv2.COLOR_BGR2GRAY),
            full_pitch,
            people,
        ),
    }
    return [
        {"stage": stage, "x": round(x, 1), "y": round(y, 1)}
        for stage in STAGES
        for x, y, _ in found[stage]
    ]


def choose_path(frames: list[tuple[int, list[dict[str, Any]]]]) -> list[dict[str, Any] | None]:
    """Pick at most one candidate per frame as the most continuous path.

    A shortest path over the sampled frames. Choosing a candidate costs its
    stage's trust cost plus the distance from the last chosen candidate per
    frame elapsed; a ball cannot move faster than the maximum speed. A frame
    without a chosen candidate (behind a player, or only false leftovers)
    costs the fixed hidden cost, and the path may stay hidden for at most
    ``maximum_hidden_samples`` frames in a row.
    """
    p = ELIMINATION_PROFILE
    stage_cost = p["stage_cost"]
    hidden = float(p["hidden_cost"])
    speed = float(p["maximum_speed_pixels_per_frame"])
    scale = float(p["distance_cost_pixels_per_frame"])
    reach = int(p["maximum_hidden_samples"])
    count = len(frames)
    # best[i][k]: (cost, back) for candidate k chosen at frame i, where back
    # is (i', k') of the previous chosen candidate or None for the start.
    best: list[list[tuple[float, tuple[int, int] | None]]] = []
    for i, (frame, options) in enumerate(frames):
        row = []
        for option in options:
            own = float(stage_cost[option["stage"]])
            choice = (hidden * i + own, None)
            for j in range(max(0, i - reach - 1), i):
                elapsed = max(1, frame - frames[j][0])
                for k, (cost, _) in enumerate(best[j]):
                    before = frames[j][1][k]
                    distance = float(np.hypot(option["x"] - before["x"], option["y"] - before["y"]))
                    if distance > speed * elapsed:
                        continue
                    total = cost + hidden * (i - j - 1) + own + distance / (scale * elapsed)
                    if total < choice[0]:
                        choice = (total, (j, k))
            row.append(choice)
        best.append(row)
    end: tuple[float, tuple[int, int] | None] = (hidden * count, None)
    for i in range(max(0, count - reach - 1), count):
        for k, (cost, _) in enumerate(best[i]):
            total = cost + hidden * (count - i - 1)
            if total < end[0]:
                end = (total, (i, k))
    picks: list[dict[str, Any] | None] = [None] * count
    at = end[1]
    while at is not None:
        i, k = at
        picks[i] = frames[i][1][k]
        at = best[i][k][1]
    return picks


def _person_records(detections: Path) -> dict[int, dict[str, Any]]:
    records = {}
    with detections.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("type") == "frame":
                records[int(row["source_frame"])] = {
                    "detections": [
                        d for d in row.get("detections", [])
                        if d.get("class_name") == "person"
                    ]
                }
    return records


def _background_samples(video: Path) -> dict[int, np.ndarray]:
    step = int(ELIMINATION_PROFILE["background_step_frames"])
    samples = {}
    capture = cv2.VideoCapture(str(video))
    index = 0
    try:
        while True:
            ok = capture.grab()
            if not ok:
                break
            if index % step == 0:
                _, image = capture.retrieve()
                samples[index] = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            index += 1
    finally:
        capture.release()
    return samples


def background_at(samples: dict[int, np.ndarray], frame: int) -> np.ndarray:
    reach = int(ELIMINATION_PROFILE["background_reach_frames"])
    near = [image for t, image in samples.items() if abs(t - frame) <= reach]
    return np.median(np.stack(near), axis=0).astype(np.uint8)


def run(
    video: Path,
    calibration_path: Path,
    detections: Path,
    output: Path,
) -> dict[str, Any]:
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    records = _person_records(detections)
    wanted = set(records)
    samples = _background_samples(video)
    clip_empty_pitch = np.median(np.stack(list(samples.values())), axis=0).astype(np.uint8)
    found: dict[int, list[dict[str, Any]]] = {}
    capture = cv2.VideoCapture(str(video))
    window: list[tuple[int, np.ndarray]] = []
    lines = None
    line_zone = None
    index = 0
    try:
        while True:
            ok, image = capture.read()
            if not ok:
                break
            if lines is None:
                height, width = image.shape[:2]
                pitch = pitch_mask(
                    calibration, width, height, edge=ELIMINATION_PROFILE["pitch_edge_pixels"]
                )
                lines = static_line_map(clip_empty_pitch, pitch)
                calibrated = calibrated_line_map(calibration, width, height)
                line_zone = calibrated
                if calibrated is not None:
                    lines = cv2.bitwise_or(lines, calibrated)
            window.append((index, image))
            if len(window) > 3:
                window.pop(0)
            if len(window) == 3 and window[1][0] in wanted:
                t = window[1][0]
                found[t] = frame_candidates(
                    window[0][1], window[1][1], window[2][1], calibration,
                    records[t], background_at(samples, t), lines, line_zone,
                )
            index += 1
    finally:
        capture.release()
    ordered = sorted(found)
    picks = choose_path([(t, found[t]) for t in ordered])
    rows = []
    for t, pick in zip(ordered, picks):
        rows.append({
            "source_frame": t,
            "outcome": pick["stage"] if pick else "behind_player",
            "x": pick["x"] if pick else None,
            "y": pick["y"] if pick else None,
            "candidates": len(found[t]),
            "options": found[t][:30],
        })
    payload = {
        "check": "ball_elimination",
        "inputs": ["video", "pitch_calibration", "yolo_person_boxes"],
        "profile": {k: list(v) if isinstance(v, tuple) else v for k, v in ELIMINATION_PROFILE.items()},
        "frames": rows,
    }
    output.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("video", type=Path)
    parser.add_argument("--pitch-calibration", type=Path, required=True)
    parser.add_argument("--detections", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = run(
        args.video,
        args.pitch_calibration,
        args.detections,
        args.output,
    )
    counts: dict[str, int] = {}
    for frame in payload["frames"]:
        counts[frame["outcome"]] = counts.get(frame["outcome"], 0) + 1
    print(json.dumps(counts, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
