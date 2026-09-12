from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CameraStream:
    camera_id: str
    video: Path
    time_offset_seconds: float
    calibration: Path | None


@dataclass(frozen=True)
class BenchmarkManifest:
    path: Path
    video: Path
    fps: float
    start_frame: int
    end_frame: int
    camera_streams: tuple[CameraStream, ...]
    primary_camera_id: str
    half: int | None
    source_start_seconds: float
    starts_at_kickoff: bool

    @classmethod
    def load(cls, path: str | Path) -> BenchmarkManifest:
        manifest_path = Path(path)
        if not manifest_path.is_file():
            raise FileNotFoundError(
                f"Benchmark manifest does not exist: {manifest_path}"
            )
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Benchmark manifest must be a JSON object")
        _reject_evaluation_inputs(payload)
        camera_streams, primary_camera_id = _load_camera_streams(payload)
        video = next(
            stream.video
            for stream in camera_streams
            if stream.camera_id == primary_camera_id
        )
        fps = float(payload.get("fps", 0))
        start_frame = int(payload.get("start_frame", -1))
        end_frame = int(payload.get("end_frame", -1))
        if fps <= 0:
            raise ValueError("Benchmark FPS must be greater than zero")
        if start_frame < 0 or end_frame <= start_frame:
            raise ValueError("Benchmark frame range is invalid")
        return cls(
            path=manifest_path.resolve(),
            video=video.resolve(),
            fps=fps,
            start_frame=start_frame,
            end_frame=end_frame,
            camera_streams=camera_streams,
            primary_camera_id=primary_camera_id,
            half=(
                int(payload["half"])
                if payload.get("half") is not None
                else None
            ),
            source_start_seconds=float(
                payload.get("start_seconds", start_frame / fps)
            ),
            starts_at_kickoff=bool(
                payload.get(
                    "starts_at_kickoff",
                    float(payload.get("start_seconds", start_frame / fps))
                    <= 5.0,
                )
            ),
        )

    @property
    def source_frame_count(self) -> int:
        return self.end_frame - self.start_frame

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


def _reject_evaluation_inputs(payload: dict[str, Any]) -> None:
    fields = (
        "actions",
        "action_counts",
        "annotations",
        "events",
        "labels",
        "ball_ground_truth",
        "manual_reference",
    )
    present = [
        field
        for field in fields
        if payload.get(field) not in (None, "", [], {})
    ]
    if present:
        raise ValueError(
            "Runtime manifest must not contain evaluation inputs: "
            + ", ".join(present)
        )


def _load_camera_streams(
    payload: dict[str, Any],
) -> tuple[tuple[CameraStream, ...], str]:
    stream_payloads = payload.get("camera_streams")
    if stream_payloads is None:
        stream_payloads = [
            {
                "camera_id": "primary",
                "video": payload.get("video", ""),
                "time_offset_seconds": 0,
            }
        ]
    if not isinstance(stream_payloads, list) or not stream_payloads:
        raise ValueError("Benchmark camera_streams must be a non-empty list")
    streams: list[CameraStream] = []
    camera_ids: set[str] = set()
    for raw_stream in stream_payloads:
        if not isinstance(raw_stream, dict):
            raise ValueError(
                "Each benchmark camera stream must be a JSON object"
            )
        camera_id = str(raw_stream.get("camera_id", "")).strip()
        if not camera_id:
            raise ValueError("Each benchmark camera stream needs a camera_id")
        if camera_id in camera_ids:
            raise ValueError(f"Duplicate benchmark camera_id: {camera_id}")
        video = Path(str(raw_stream.get("video", "")))
        if not video.is_file():
            raise FileNotFoundError(f"Benchmark video does not exist: {video}")
        offset = float(raw_stream.get("time_offset_seconds", 0))
        if not math.isfinite(offset):
            raise ValueError("Camera time_offset_seconds must be finite")
        calibration_value = raw_stream.get("calibration")
        calibration = Path(str(calibration_value)) if calibration_value else None
        if calibration is not None and not calibration.is_file():
            raise FileNotFoundError(
                f"Camera calibration does not exist: {calibration}"
            )
        streams.append(
            CameraStream(
                camera_id=camera_id,
                video=video.resolve(),
                time_offset_seconds=offset,
                calibration=calibration.resolve() if calibration else None,
            )
        )
        camera_ids.add(camera_id)
    primary_camera_id = str(
        payload.get("primary_camera_id", streams[0].camera_id)
    ).strip()
    if primary_camera_id not in camera_ids:
        raise ValueError(
            "Primary camera is not declared in camera_streams: "
            f"{primary_camera_id}"
        )
    return tuple(streams), primary_camera_id
