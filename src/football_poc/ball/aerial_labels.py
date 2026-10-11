"""Per-frame ``aerial`` label for the ball track.

The ball tracker writes ``aerial: true`` on every ball-state frame where the
ball is in flight, and ``false`` elsewhere, so the events engine reads it
instead of guessing. Coordinates are never changed here.

From one camera the label is read from the ball's path in the picture: a
kicked ball climbs fast, then comes back down by a clear share of its climb.
A ball rolling away from the camera only climbs, and slowly. The climb is
measured in the height of the nearest player, so far-side flights count too.

Run on an existing file to add the label without rerunning the tracker::

    python -m football_poc.ball.aerial_labels <ball-state-estimates.json> \
        --detections <detections.jsonl>
"""

from __future__ import annotations

import argparse
import json
from bisect import bisect_left
from math import hypot
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

AERIAL_LABEL_PROFILE = {
    "min_rise_heights": 0.3,
    "min_fall_ratio": 0.3,
    "noise_px": 3.0,
    # A kicked ball climbs fast in the picture; a ground pass rolling away
    # from the camera climbs slowly.
    "min_rise_px_per_second": 50.0,
    "person_minimum_confidence": 0.1,
}

SEEN_STATES = frozenset({"observed", "visually_reacquired"})

# (frame, clip_seconds, x, y)
TrackPoint = tuple[int, float, float, float]


def box_distance(point: tuple[float, float], box: dict[str, Any]) -> float:
    """Distance from a point to the nearest point of a box, head to feet."""
    dx = max(float(box["x1"]) - point[0], 0.0, point[0] - float(box["x2"]))
    dy = max(float(box["y1"]) - point[1], 0.0, point[1] - float(box["y2"]))
    return hypot(dx, dy)


def flight_indices(
    track: Sequence[TrackPoint],
    height_at: Callable[[int], float | None],
    *,
    min_rise_heights: float = AERIAL_LABEL_PROFILE["min_rise_heights"],
    min_fall_ratio: float = AERIAL_LABEL_PROFILE["min_fall_ratio"],
    noise_px: float = AERIAL_LABEL_PROFILE["noise_px"],
    min_rise_px_per_second: float = AERIAL_LABEL_PROFILE["min_rise_px_per_second"],
) -> set[int]:
    """Indices of track samples in flight: the ball rises, then falls, in the image.

    ``height_at(index)`` is the height of the player nearest the ball at that
    sample, or ``None`` when there is none. The flight lasts from the rise
    until the ball has come back down to the level it rose from, or stops
    falling. The ball must fall back by a clear share of its rise; otherwise
    it was rolling away from the camera.
    """
    lofted: set[int] = set()
    noise = noise_px
    for peak in range(1, len(track) - 1):
        y = track[peak][3]
        if not (track[peak - 1][3] > y + noise or track[peak + 1][3] > y + noise):
            continue
        if track[peak - 1][3] < y or track[peak + 1][3] < y:
            continue
        start = peak
        while start > 0 and track[start - 1][3] >= track[start][3] - noise:
            start -= 1
        end = peak
        while (
            end < len(track) - 1
            and track[end + 1][3] >= track[end][3] - noise
            and track[end][3] < track[start][3]
        ):
            end += 1
        while start < peak and track[start + 1][3] > track[start][3] - noise:
            start += 1
        while end > peak and track[end - 1][3] > track[end][3] - noise:
            end -= 1
        height = height_at(peak)
        if height is None:
            continue
        rise = track[start][3] - y
        fall = track[end][3] - y
        if min(rise, fall) < min_rise_heights * height:
            continue
        # A ball in the air comes back down. A ball rolling away from the
        # camera only climbs in the picture, so a tiny dip after a long climb
        # is not a flight.
        if fall < min_fall_ratio * rise:
            continue
        rise_seconds = track[peak][1] - track[start][1]
        if rise_seconds > 0 and rise / rise_seconds < min_rise_px_per_second:
            continue
        lofted.update(range(start + 1, end))
    return lofted


def label_aerial_states(
    states: list[dict[str, Any]],
    person_boxes: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Set ``aerial`` on every state, in place, and return the list.

    ``person_boxes`` maps a source frame to its person detections; the
    nearest sampled frame is used when a state's frame has none.
    """
    profile = AERIAL_LABEL_PROFILE
    seen = sorted(
        (
            state
            for state in states
            if state.get("state") in SEEN_STATES
            and state.get("x") is not None
            and state.get("y") is not None
        ),
        key=lambda state: int(state["source_frame"]),
    )
    track: list[TrackPoint] = [
        (
            int(state["source_frame"]),
            float(state["clip_seconds"]),
            float(state["x"]),
            float(state["y"]),
        )
        for state in seen
    ]
    frames = sorted(person_boxes)

    def height_at(index: int) -> float | None:
        if not frames:
            return None
        frame, _, x, y = track[index]
        position = bisect_left(frames, frame)
        nearby = [
            frames[i] for i in (position - 1, position) if 0 <= i < len(frames)
        ]
        nearest = min(nearby, key=lambda f: abs(f - frame))
        boxes = [
            box
            for box in person_boxes[nearest]
            if float(box["y2"]) > float(box["y1"])
            and float(box.get("confidence", 1.0))
            >= float(profile["person_minimum_confidence"])
        ]
        if not boxes:
            return None
        box = min(boxes, key=lambda box: box_distance((x, y), box))
        return float(box["y2"]) - float(box["y1"])

    in_flight = flight_indices(track, height_at)
    flight_ids = {id(seen[index]) for index in in_flight}
    for state in states:
        state["aerial"] = id(state) in flight_ids
    return states


def person_boxes_from_records(
    records: Iterable[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    return {
        int(record["source_frame"]): [
            detection
            for detection in record.get("detections", [])
            if detection.get("class_name") == "person"
        ]
        for record in records
        if record.get("type", "frame") == "frame" and "source_frame" in record
    }


def _read_detections(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("states", type=Path, help="ball-state-estimates.json")
    parser.add_argument("--detections", type=Path, required=True, help="detections.jsonl")
    args = parser.parse_args(argv)
    payload = json.loads(args.states.read_text(encoding="utf-8"))
    label_aerial_states(
        payload.get("states", []),
        person_boxes_from_records(_read_detections(args.detections)),
    )
    args.states.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    count = sum(1 for state in payload.get("states", []) if state.get("aerial"))
    print(f"{count} aerial frames labelled in {args.states}")


if __name__ == "__main__":
    main()
