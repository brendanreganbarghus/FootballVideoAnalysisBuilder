"""Chronological-engine inputs for a BAC (frozen provider) ball path.

BAC coordinates are stored in the provider panorama space, while player
tracks come from YOLO in video frame size. The chronological engine compares
the ball with player feet directly, so this writes a copy of the BAC ball in
video size (size declared) plus a ball-status file. The stored BAC file is
left unchanged for the Canvas.

BAC carries no tracker statuses: every coordinate is ``observed`` and the
engine decides out-of-play itself from the calibrated pitch (Law 9). Aerial
labels come from the same cached person detections as the ``detected`` path.

Usage::

    python -m football_poc.bac_chrono_inputs <ball-tracks.json> \
        --detections detections.jsonl --pitch-calibration pitch-calibration.json \
        --video segment.mp4 --output-dir analytics-data
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from football_poc.ball.aerial_labels import label_aerial_states, person_boxes_from_records
from football_poc.image_space import (
    ImageSize,
    PROVIDER_SPACE_SOURCE_KINDS,
    declared_size,
    video_size,
)

ENGINE_BALL_TRACKS = "bac-engine-ball-tracks.json"
BALL_STATES = "bac-ball-states.json"


def bac_ball_in_video_size(
    ball_tracks: dict[str, Any], calibration: dict[str, Any], video: ImageSize
) -> dict[str, Any]:
    """Return a copy of the BAC ball tracks converted to ``video`` size."""
    source = declared_size(ball_tracks)
    if source is None:
        if ball_tracks.get("source_kind") not in PROVIDER_SPACE_SOURCE_KINDS:
            raise ValueError("BAC chronological inputs require BAC ball tracks")
        source = declared_size(calibration)
        if source is None:
            raise ValueError("Pitch calibration must declare image_width/image_height")
    sx, sy = video[0] / source[0], video[1] / source[1]
    payload = json.loads(json.dumps(ball_tracks))
    for track in payload.get("tracks", []):
        for point in track.get("points", []):
            point["x"] = float(point["x"]) * sx
            point["y"] = float(point["y"]) * sy
            point["interpolated"] = False
    payload["image_width"], payload["image_height"] = video
    return payload


def bac_ball_states(
    ball_tracks: dict[str, Any], records: list[dict[str, Any]], cache: str
) -> dict[str, Any]:
    """All-observed status file with aerial labels; no out-of-play guess."""
    states = sorted(
        (
            {
                **point,
                "state": "observed",
                "event_evidence_eligible": True,
            }
            for track in ball_tracks.get("tracks", [])
            for point in track.get("points", [])
        ),
        key=lambda state: int(state["source_frame"]),
    )
    label_aerial_states(states, person_boxes_from_records(records))
    return {
        "manifest": ball_tracks.get("manifest", ""),
        "cache": cache,
        "policy": {
            "observed_states_are_event_evidence": True,
            "trajectory_estimates_are_event_evidence": False,
            "trajectory_estimates_are_for_continuity_and_search_only": True,
            "out_of_play_decided_by_engine": True,
        },
        "states": states,
    }


def write_bac_chrono_inputs(
    *,
    ball_tracks: Path,
    detections: Path,
    pitch_calibration: Path,
    video: Path,
    output_dir: Path,
) -> tuple[Path, Path]:
    payload = bac_ball_in_video_size(
        json.loads(ball_tracks.read_text(encoding="utf-8")),
        json.loads(pitch_calibration.read_text(encoding="utf-8")),
        video_size(video),
    )
    with detections.open(encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    output_dir.mkdir(parents=True, exist_ok=True)
    tracks_out = output_dir / ENGINE_BALL_TRACKS
    states_out = output_dir / BALL_STATES
    tracks_out.write_text(json.dumps(payload), encoding="utf-8")
    states_out.write_text(
        json.dumps(bac_ball_states(payload, records, str(tracks_out)), indent=2),
        encoding="utf-8",
    )
    return tracks_out, states_out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ball_tracks", type=Path)
    parser.add_argument("--detections", type=Path, required=True)
    parser.add_argument("--pitch-calibration", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    tracks_out, states_out = write_bac_chrono_inputs(
        ball_tracks=args.ball_tracks,
        detections=args.detections,
        pitch_calibration=args.pitch_calibration,
        video=args.video,
        output_dir=args.output_dir,
    )
    print(f"BAC chronological inputs: {tracks_out.name}, {states_out.name}")


if __name__ == "__main__":
    main()
