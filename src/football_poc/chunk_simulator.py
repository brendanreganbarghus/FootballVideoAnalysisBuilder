from __future__ import annotations

import json
import hashlib
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReplayChunk:
    index: int
    start_seconds: float
    end_seconds: float

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


def make_replay_chunks(
    duration_seconds: float,
    *,
    chunk_seconds: float,
    overlap_seconds: float,
) -> list[ReplayChunk]:
    if duration_seconds <= 0 or chunk_seconds <= 0:
        raise ValueError("Duration and chunk length must be greater than zero")
    if not 0 <= overlap_seconds < chunk_seconds:
        raise ValueError("Overlap must be at least zero and shorter than a chunk")
    chunks: list[ReplayChunk] = []
    start = 0.0
    index = 0
    while start < duration_seconds:
        end = min(duration_seconds, start + chunk_seconds)
        chunks.append(ReplayChunk(index, round(start, 3), round(end, 3)))
        if end >= duration_seconds:
            break
        start = end - overlap_seconds
        index += 1
    return chunks


def simulate_event_chunks(
    *,
    manifest_path: Path,
    events_path: Path,
    output: Path,
    chunk_seconds: float = 20.0,
    overlap_seconds: float = 2.0,
    processing_seconds_per_chunk: float = 20.0,
    state_path: Path | None = None,
    max_chunks: int | None = None,
) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    events = json.loads(events_path.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise ValueError("Predicted events must be a JSON list")
    duration_value = manifest.get("duration_seconds")
    if duration_value is None:
        fps = float(manifest.get("fps", 0))
        start_frame = int(manifest.get("start_frame", 0))
        end_frame = int(manifest.get("end_frame", 0))
        if fps <= 0 or end_frame <= start_frame:
            raise ValueError(
                "Manifest must contain duration_seconds or a valid frame range and FPS"
            )
        duration_value = (end_frame - start_frame) / fps
    duration = float(duration_value)
    chunks = make_replay_chunks(
        duration,
        chunk_seconds=chunk_seconds,
        overlap_seconds=overlap_seconds,
    )
    if processing_seconds_per_chunk < 0:
        raise ValueError("Processing time cannot be negative")
    if max_chunks is not None and max_chunks < 1:
        raise ValueError("Maximum chunks must be at least one")
    checkpoint = state_path or output.with_name(f"{output.stem}-state.json")
    configuration = {
        "manifest": str(manifest_path.resolve()),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "batch_events": str(events_path.resolve()),
        "batch_events_sha256": hashlib.sha256(events_path.read_bytes()).hexdigest(),
        "chunk_seconds": chunk_seconds,
        "overlap_seconds": overlap_seconds,
        "processing_seconds_per_chunk": processing_seconds_per_chunk,
    }
    state = _load_or_create_state(checkpoint, configuration)
    accepted: dict[str, dict[str, Any]] = state["accepted"]
    chunk_results: list[dict[str, Any]] = state["chunks"]
    worker_available_at = float(state["worker_available_at"])
    duplicate_count = int(state["duplicate_count"])
    processed_this_run = 0
    for chunk in chunks[int(state["next_chunk_index"]) :]:
        is_last = chunk.index == chunks[-1].index
        incoming = [
            event
            for event in events
            if chunk.start_seconds <= float(event["clip_seconds"])
            and (
                float(event["clip_seconds"]) <= chunk.end_seconds
                if is_last
                else float(event["clip_seconds"]) < chunk.end_seconds
            )
        ]
        new_events = 0
        duplicates = 0
        for event in incoming:
            key = _event_key(event)
            if key in accepted:
                duplicates += 1
                duplicate_count += 1
            else:
                accepted[key] = event
                new_events += 1

        arrival = chunk.end_seconds
        processing_started = max(arrival, worker_available_at)
        scaled_processing = (
            processing_seconds_per_chunk
            * chunk.duration_seconds
            / chunk_seconds
        )
        processing_completed = processing_started + scaled_processing
        worker_available_at = processing_completed
        finalized_through = (
            duration
            if is_last
            else max(0.0, chunk.end_seconds - overlap_seconds)
        )
        counts = Counter(
            str(event["event_type"]) for event in accepted.values()
        )
        chunk_results.append(
            {
                **asdict(chunk),
                "arrival_seconds": round(arrival, 3),
                "processing_started_seconds": round(processing_started, 3),
                "processing_completed_seconds": round(processing_completed, 3),
                "queue_wait_seconds": round(processing_started - arrival, 3),
                "incoming_events": len(incoming),
                "new_events": new_events,
                "duplicates_suppressed": duplicates,
                "state_out": {
                    "accepted_event_count": len(accepted),
                    "finalized_through_seconds": round(finalized_through, 3),
                    "provisional_event_counts": dict(sorted(counts.items())),
                },
            }
        )
        state = {
            "configuration": configuration,
            "next_chunk_index": chunk.index + 1,
            "accepted": accepted,
            "chunks": chunk_results,
            "worker_available_at": worker_available_at,
            "duplicate_count": duplicate_count,
        }
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(json.dumps(state, indent=2), encoding="utf-8")
        processed_this_run += 1
        if max_chunks is not None and processed_this_run >= max_chunks:
            break

    expected_keys = {_event_key(event) for event in events}
    actual_keys = set(accepted)
    complete = int(state["next_chunk_index"]) >= len(chunks)
    report = {
        "manifest": str(manifest_path.resolve()),
        "batch_events": str(events_path.resolve()),
        "configuration": configuration,
        "state_checkpoint": str(checkpoint.resolve()),
        "complete": complete,
        "chunks": chunk_results,
        "final_events": sorted(
            accepted.values(), key=lambda event: float(event["clip_seconds"])
        ),
        "validation": {
            "valid": complete and expected_keys == actual_keys,
            "expected_events": len(expected_keys),
            "final_events": len(actual_keys),
            "duplicates_suppressed": duplicate_count,
            "missing_event_keys": sorted(expected_keys - actual_keys),
            "unexpected_event_keys": sorted(actual_keys - expected_keys),
        },
        "latency": {
            "match_duration_seconds": duration,
            "pipeline_completed_seconds": round(worker_available_at, 3),
            "finish_delay_seconds": round(
                max(0.0, worker_available_at - duration), 3
            ),
            "keeps_up_with_stream": complete
            and worker_available_at <= duration,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output


def _load_or_create_state(
    path: Path, configuration: dict[str, Any]
) -> dict[str, Any]:
    if not path.exists():
        return _new_state(configuration)
    state = json.loads(path.read_text(encoding="utf-8"))
    previous_configuration = state.get("configuration", {})
    hash_keys = {"manifest_sha256", "batch_events_sha256"}
    previous_settings = {
        key: value
        for key, value in previous_configuration.items()
        if key not in hash_keys
    }
    current_settings = {
        key: value for key, value in configuration.items() if key not in hash_keys
    }
    if previous_settings != current_settings:
        raise ValueError(
            "Chunk checkpoint settings differ from this run. Use another "
            "state path or restore the original settings."
        )
    if any(
        previous_configuration.get(key) != configuration.get(key)
        for key in hash_keys
    ):
        return _new_state(configuration)
    return state


def _new_state(configuration: dict[str, Any]) -> dict[str, Any]:
    return {
        "configuration": configuration,
        "next_chunk_index": 0,
        "accepted": {},
        "chunks": [],
        "worker_available_at": 0.0,
        "duplicate_count": 0,
    }


def _event_key(event: dict[str, Any]) -> str:
    return "|".join(
        [
            str(event.get("event_type")),
            f"{float(event.get('clip_seconds', 0)):.3f}",
            str(event.get("team")),
            str(event.get("from_player_track_id")),
            str(event.get("to_player_track_id")),
        ]
    )
