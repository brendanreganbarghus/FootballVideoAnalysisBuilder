from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path


def resolve_alfheim_pano(workspace: Path) -> Path:
    configured = os.environ.get("FOOTBALL_ALFHEIM_PANO", "").strip()
    if not configured:
        return (workspace / "pano").resolve()
    path = Path(os.path.expandvars(configured)).expanduser()
    if not path.is_absolute():
        path = workspace / path
    return path.resolve()


@dataclass(frozen=True)
class AlfheimSegmentPlan:
    first_segment: int
    segment_count: int
    source_start_seconds: float
    requested_start_seconds: float
    clip_start_seconds: float
    duration_seconds: float
    source_duration_seconds: float

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


def alfheim_source_info(
    pano: Path,
    *,
    segment_seconds: float = 3.0,
) -> dict[str, int | float]:
    segments = sorted(pano.glob("*.h264"))
    if not segments:
        raise FileNotFoundError(f"No Alfheim H.264 segments found in {pano}")
    return {
        "segment_count": len(segments),
        "segment_seconds": segment_seconds,
        "duration_seconds": round(len(segments) * segment_seconds, 3),
    }


def plan_alfheim_segment(
    pano: Path,
    *,
    start_seconds: float,
    duration_seconds: float,
    segment_seconds: float = 3.0,
    maximum_duration_seconds: float = 300.0,
) -> AlfheimSegmentPlan:
    if not math.isfinite(start_seconds) or start_seconds < 0:
        raise ValueError("Start time must be a non-negative number")
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("Duration must be a positive number")
    if duration_seconds > maximum_duration_seconds:
        raise ValueError(
            f"Duration must not exceed {maximum_duration_seconds:g} seconds"
        )
    info = alfheim_source_info(pano, segment_seconds=segment_seconds)
    source_duration = float(info["duration_seconds"])
    if start_seconds >= source_duration:
        raise ValueError(
            f"Start time must be before {source_duration:g} seconds"
        )
    requested_duration = min(duration_seconds, source_duration - start_seconds)
    first_segment = int(start_seconds // segment_seconds)
    source_start = first_segment * segment_seconds
    clip_start = start_seconds - source_start
    segment_count = math.ceil(
        (clip_start + requested_duration) / segment_seconds
    )
    return AlfheimSegmentPlan(
        first_segment=first_segment,
        segment_count=segment_count,
        source_start_seconds=round(source_start, 3),
        requested_start_seconds=round(start_seconds, 3),
        clip_start_seconds=round(clip_start, 3),
        duration_seconds=round(requested_duration, 3),
        source_duration_seconds=source_duration,
    )
