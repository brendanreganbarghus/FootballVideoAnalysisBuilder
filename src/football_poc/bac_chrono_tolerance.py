"""BAC-only allowances for the chronological events engine.

Frozen BAC ball coordinates sit a few pixels (sometimes 20-30 px) away from
where the ball is in the video, and they wobble more than the Live tracker's
coordinates. Near a player that is enough to put a real touch just outside
the touch reach. This module gives the BAC flow some room for that offset.

It runs only in the BAC flow (``scripts/process-alfheim-segment.py`` calls it
instead of ``football_poc.chrono_engine`` when ``ball_source == "bac"``). The
Live flow never imports it, so Live output is unchanged.

The allowance is the track's own measured wobble times the engine's existing
touch noise multiple. Nothing in it comes from M#, BAC agreement or a segment.
"""

from __future__ import annotations

from typing import Any, Iterable

from football_poc import chrono_engine
from football_poc.chrono_engine import TEAMS, ChronoSettings, _box_distance, _toucher


def bac_toucher(
    ball: tuple[float, float],
    boxes: Iterable[dict[str, Any]],
    settings: ChronoSettings,
    *,
    aerial: bool = False,
    noise_px: float = 0.0,
) -> dict[str, Any] | None:
    """The engine's touch check, with the BAC position wobble as extra reach.

    The normal check runs first. Only when it credits nobody is each player's
    distance to the ball shortened by the wobble allowance; the touch reach
    and the duel margin against an opponent still apply.
    """
    boxes = list(boxes)
    touch = _toucher(ball, boxes, settings, aerial=aerial)
    if touch is not None or noise_px <= 0:
        return touch
    allowance = settings.touch_noise_multiple * noise_px
    ranked: list[tuple[float, dict[str, Any]]] = []
    for box in boxes:
        if box.get("role") == "official" or box.get("team") not in TEAMS:
            continue
        height = float(box["y2"]) - float(box["y1"])
        if height <= 0:
            continue
        ranked.append((max(_box_distance(ball, box) - allowance, 0.0) / height, box))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0])
    ratio, best = ranked[0]
    if ratio > settings.touch_radius_heights:
        return None
    for other_ratio, other in ranked[1:]:
        if other["team"] != best["team"]:
            if other_ratio - ratio < settings.duel_margin_heights:
                return None
            break
    return best


def main(argv: list[str] | None = None) -> None:
    """Same command line as ``football_poc.chrono_engine``, with the BAC allowance."""
    chrono_engine.main(argv, toucher=bac_toucher)


if __name__ == "__main__":
    main()
