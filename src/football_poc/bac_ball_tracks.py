from __future__ import annotations

import json
from pathlib import Path


def load_alfheim_bac_coordinates(
    pano: Path,
    *,
    source_start_seconds: float,
    duration_seconds: float,
    fps: int = 25,
    source_segment_seconds: int = 3,
) -> dict[int, tuple[float, float]]:
    frames_per_source_segment = fps * source_segment_seconds
    source_files = {
        int(path.name.split("_", 1)[0]): path
        for path in pano.glob("*.h264")
    }
    first_absolute_frame = round(source_start_seconds * fps)
    frame_count = round(duration_seconds * fps)
    coordinates: dict[int, tuple[float, float]] = {}
    rows_by_segment: dict[int, list[str]] = {}
    for clip_frame in range(frame_count):
        absolute_frame = first_absolute_frame + clip_frame
        source_segment = absolute_frame // frames_per_source_segment
        source_frame = absolute_frame % frames_per_source_segment
        if source_segment not in rows_by_segment:
            video = source_files.get(source_segment)
            if video is None:
                raise FileNotFoundError(
                    f"Alfheim source segment is missing: {source_segment}"
                )
            track = pano / "track" / f"{video.name}_track.txt"
            rows_by_segment[source_segment] = track.read_text(
                encoding="utf-8"
            ).splitlines()
        rows = rows_by_segment[source_segment]
        if source_frame >= len(rows):
            raise ValueError(
                "Provider coordinate is missing for source frame "
                f"{absolute_frame}"
            )
        _, x, y, *_ = rows[source_frame].split()
        coordinates[clip_frame] = (float(x), float(y))
    return coordinates


def write_bac_ball_tracks(
    *,
    runtime_manifest: Path,
    pano: Path,
    output: Path,
    source_start_seconds: float,
    duration_seconds: float,
    stride: int = 5,
) -> Path:
    coordinates = load_alfheim_bac_coordinates(
        pano,
        source_start_seconds=source_start_seconds,
        duration_seconds=duration_seconds,
    )
    points = [
        {
            "source_frame": frame,
            "clip_seconds": frame / 25,
            "confidence": 1.0,
            "x": x,
            "y": y,
            "interpolated": False,
            "box_diagonal": 0.0,
            "evidence": "evaluation_only_provider_coordinate",
            "temporal_score": None,
            "source_attribution": "evaluation_only_provider_coordinates",
        }
        for frame, (x, y) in sorted(coordinates.items())
        if frame % stride == 0
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "manifest": str(runtime_manifest.resolve()),
                "source": str((pano / "track").resolve()),
                "source_kind": "evaluation_only_provider_coordinates",
                "pipeline_mode": "innovation_day_bac_assisted",
                "tracks": [{"track_id": 1, "points": points}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output
