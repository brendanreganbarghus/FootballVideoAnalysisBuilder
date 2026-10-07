from __future__ import annotations

from typing import Callable

from .settings import *  # noqa: F401,F403

# Uses _colour_walk, _colour_walk_blobs, _colour_walk_velocity (colour_walk.py)
# and RESTART_SPOT_MODULE (restart_spot.py) from the shared package namespace.


# Law 17: a corner kick is only taken after the whole ball has crossed the goal
# line, so a gap that ends at a ball placed still on a corner arc contains the
# moment the ball went out. Law 9: once the whole ball is over the boundary it
# is out of play and has no live position until the restart. The ball is
# followed by its own colour forwards from the last point before the gap;
# points still inside the calibrated pitch are kept, the first point wholly
# outside is the crossing, and every frame from the crossing until the
# restart is out of play, held at the last in-play point.
OUT_OF_PLAY_MODULE = "10_out_of_play"
OUT_OF_PLAY_PROFILE = {
    # The whole ball is over the line when its centre is outside the
    # calibrated outline by more than half a ball diagonal.
    "outside_margin_diagonals": 0.5,
    "confidence": 0.25,
}


def _restart_gaps(ledger: FrameLedger) -> list[tuple[int, int, tuple[int, ...]]]:
    """Unresolved runs whose following confirmed point is a corner restart."""
    sampled = sorted(ledger.entries)
    gaps: list[tuple[int, int, tuple[int, ...]]] = []
    index = 0
    while index < len(sampled):
        if ledger.confirmed(sampled[index]) is not None:
            index += 1
            continue
        start = index
        while index < len(sampled) and ledger.confirmed(sampled[index]) is None:
            index += 1
        if start == 0 or index >= len(sampled):
            continue
        right = ledger.confirmed(sampled[index])
        if right is None or right.confirming_module != RESTART_SPOT_MODULE:
            continue
        gap = tuple(
            frame for frame in sampled[start:index] if ledger.entries[frame].status == "unresolved"
        )
        if gap:
            gaps.append((sampled[start - 1], sampled[index], gap))
    return gaps


def _split_at_crossing(
    walked: dict[int, tuple[float, float]],
    gap: tuple[int, ...],
    signed_distance: Callable[[float, float], float],
    outside_margin: float,
) -> tuple[dict[int, tuple[float, float]], int | None]:
    """Walked points still in play, and the first frame wholly outside."""
    in_play: dict[int, tuple[float, float]] = {}
    for frame in gap:
        if frame not in walked:
            return in_play, None
        x, y = walked[frame]
        if signed_distance(x, y) < -outside_margin:
            return in_play, frame
        in_play[frame] = (x, y)
    return in_play, None


def _mark_out_of_play(
    ledger: FrameLedger,
    *,
    video: Path,
    records_by_frame: dict[int, dict[str, Any]],
    boundary: np.ndarray | None,
    colour_range: tuple[float, float] | None,
    ball_diagonal: float,
    fps: float,
    max_speed_pixels_per_second: float,
) -> FrameLedger:
    if boundary is None or fps <= 0 or ball_diagonal <= 0:
        return ledger
    gaps = _restart_gaps(ledger)
    if not gaps:
        return ledger
    sampled = sorted(ledger.entries)
    outline = np.asarray(boundary, dtype=np.float32).reshape(-1, 1, 2)
    outside_margin = ball_diagonal * float(OUT_OF_PLAY_PROFILE["outside_margin_diagonals"])

    def signed_distance(x: float, y: float) -> float:
        return float(cv2.pointPolygonTest(outline, (float(x), float(y)), True))

    capture = cv2.VideoCapture(str(video)) if colour_range is not None else None
    position = 0
    try:
        for left, right, gap in gaps:
            anchor = ledger.confirmed(left)
            if anchor is None:
                continue
            walked: dict[int, tuple[float, float]] = {}
            if capture is not None:
                images: dict[int, np.ndarray] = {}
                for frame in gap:
                    while position < frame:
                        if not capture.grab():
                            break
                        position += 1
                    ok, image = capture.read()
                    if not ok:
                        break
                    position += 1
                    images[frame] = image

                def blobs_near(
                    frame: int, centre: tuple[float, float], half: float
                ) -> list[tuple[float, float]]:
                    if frame not in images:
                        return []
                    return _colour_walk_blobs(
                        images[frame],
                        centre,
                        half,
                        colour_range=colour_range,
                        ball_diagonal=ball_diagonal,
                        record=records_by_frame.get(frame),
                    )

                walked = _colour_walk(
                    (left, float(anchor.x), float(anchor.y)),
                    list(gap),
                    blobs_near,
                    velocity=_colour_walk_velocity(ledger, sampled, left, 1),
                    fps=fps,
                    max_speed_pixels_per_second=max_speed_pixels_per_second,
                )
            in_play, crossing = _split_at_crossing(
                walked, gap, signed_distance, outside_margin
            )
            # Without a seen crossing the walked points are not trusted: the
            # whole gap is out of play, held at the last confirmed point.
            if crossing is None:
                in_play = {}
            for frame, (x, y) in in_play.items():
                ledger.confirm(
                    frame,
                    x=x,
                    y=y,
                    confirming_module=OUT_OF_PLAY_MODULE,
                    evidence={
                        "reason": "ball_colour_followed_to_boundary_crossing",
                        "from_frame": left,
                        "crossing_frame": crossing,
                        "restart_frame": right,
                    },
                    confidence=float(OUT_OF_PLAY_PROFILE["confidence"]),
                    box_diagonal=ball_diagonal,
                    point_evidence="colour_walk",
                    point_source_attribution="colour_walk",
                )
            held_frame = max(in_play) if in_play else left
            held_x, held_y = in_play[held_frame] if in_play else (float(anchor.x), float(anchor.y))
            for frame in gap:
                if frame in in_play:
                    continue
                ledger.mark_out_of_play(
                    frame,
                    x=held_x,
                    y=held_y,
                    module=OUT_OF_PLAY_MODULE,
                    evidence={
                        "reason": (
                            "ball_wholly_crossed_boundary_before_restart"
                            if crossing is not None
                            else "restart_follows_gap_crossing_not_seen"
                        ),
                        "held_from_frame": held_frame,
                        "crossing_frame": crossing,
                        "restart_frame": right,
                    },
                )
    finally:
        if capture is not None:
            capture.release()
    return ledger
