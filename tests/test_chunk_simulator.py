import json
from pathlib import Path

from football_poc.chunk_simulator import (
    make_replay_chunks,
    simulate_event_chunks,
)


def test_chunks_cover_duration_with_overlap() -> None:
    chunks = make_replay_chunks(
        60, chunk_seconds=20, overlap_seconds=2
    )

    assert [
        (chunk.start_seconds, chunk.end_seconds) for chunk in chunks
    ] == [(0, 20), (18, 38), (36, 56), (54, 60)]


def test_simulator_suppresses_boundary_duplicates(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    events = tmp_path / "events.json"
    manifest.write_text(
        json.dumps({"duration_seconds": 60}), encoding="utf-8"
    )
    events.write_text(
        json.dumps(
            [
                {
                    "event_type": "pass_candidate",
                    "clip_seconds": 19.0,
                    "team": "blue",
                    "from_player_track_id": 1,
                    "to_player_track_id": 2,
                },
                {
                    "event_type": "shot_candidate",
                    "clip_seconds": 40.0,
                    "team": "blue",
                    "from_player_track_id": 2,
                    "to_player_track_id": None,
                },
            ]
        ),
        encoding="utf-8",
    )

    output = simulate_event_chunks(
        manifest_path=manifest,
        events_path=events,
        output=tmp_path / "simulation.json",
        chunk_seconds=20,
        overlap_seconds=2,
        processing_seconds_per_chunk=20,
    )
    report = json.loads(output.read_text(encoding="utf-8"))

    assert report["validation"]["valid"]
    assert report["validation"]["duplicates_suppressed"] == 1
    assert report["validation"]["final_events"] == 2
    assert not report["latency"]["keeps_up_with_stream"]


def test_simulator_resumes_from_checkpoint(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    events = tmp_path / "events.json"
    output = tmp_path / "simulation.json"
    state = tmp_path / "state.json"
    manifest.write_text(
        json.dumps({"duration_seconds": 60}), encoding="utf-8"
    )
    events.write_text(
        json.dumps(
            [
                {
                    "event_type": "pass_candidate",
                    "clip_seconds": 19.0,
                    "team": "blue",
                    "from_player_track_id": 1,
                    "to_player_track_id": 2,
                }
            ]
        ),
        encoding="utf-8",
    )

    simulate_event_chunks(
        manifest_path=manifest,
        events_path=events,
        output=output,
        state_path=state,
        chunk_seconds=20,
        overlap_seconds=2,
        processing_seconds_per_chunk=10,
        max_chunks=2,
    )
    partial = json.loads(output.read_text(encoding="utf-8"))
    assert not partial["complete"]

    simulate_event_chunks(
        manifest_path=manifest,
        events_path=events,
        output=output,
        state_path=state,
        chunk_seconds=20,
        overlap_seconds=2,
        processing_seconds_per_chunk=10,
    )
    complete = json.loads(output.read_text(encoding="utf-8"))

    assert complete["complete"]
    assert complete["validation"]["valid"]
    assert complete["validation"]["duplicates_suppressed"] == 1


def test_simulator_resets_checkpoint_when_events_change(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    events = tmp_path / "events.json"
    output = tmp_path / "simulation.json"
    state = tmp_path / "state.json"
    manifest.write_text(json.dumps({"duration_seconds": 20}), encoding="utf-8")
    events.write_text("[]", encoding="utf-8")
    simulate_event_chunks(
        manifest_path=manifest,
        events_path=events,
        output=output,
        state_path=state,
        chunk_seconds=20,
        overlap_seconds=2,
        processing_seconds_per_chunk=0,
    )
    events.write_text(
        json.dumps([{"event_type": "pass_candidate", "clip_seconds": 5}]),
        encoding="utf-8",
    )

    simulate_event_chunks(
        manifest_path=manifest,
        events_path=events,
        output=output,
        state_path=state,
        chunk_seconds=20,
        overlap_seconds=2,
        processing_seconds_per_chunk=0,
    )
    report = json.loads(output.read_text(encoding="utf-8"))

    assert report["validation"]["final_events"] == 1
