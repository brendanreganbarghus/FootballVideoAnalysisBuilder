"""Rule: a cached event rebuild reuses player tracks only when nothing they
depend on changed.

Player tracking reads the cached detections, the ball tracks, the camera
files, its settings and the football_poc modules player_tracking_cli imports.
An events-engine change alone must not rebuild player tracks; any change to
those inputs must. The events engine is not part of that code.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "process_alfheim_segment", ROOT / "scripts" / "process-alfheim-segment.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_player_tracks_reuse_fingerprint_20261018T103034157Z(tmp_path: Path) -> None:
    script = _script()
    code = {
        path.name for path in script.local_module_closure("player_tracking_cli")
    }
    assert "player_tracking.py" in code
    assert "team_colors.py" in code
    assert "chrono_engine.py" not in code

    detections = tmp_path / "detections.jsonl"
    ball = tmp_path / "ball-tracks.json"
    detections.write_text("a", encoding="utf-8")
    ball.write_text("b", encoding="utf-8")
    first = script.player_tracks_input_fingerprint([detections, ball], ["x"])
    assert first == script.player_tracks_input_fingerprint(
        [detections, ball], ["x"]
    )
    assert first != script.player_tracks_input_fingerprint(
        [detections, ball], ["y"]
    )
    ball.write_text("c", encoding="utf-8")
    assert first != script.player_tracks_input_fingerprint(
        [detections, ball], ["x"]
    )

    source = (ROOT / "scripts" / "process-alfheim-segment.py").read_text(
        encoding="utf-8"
    )
    assert "track_players(active_ball_tracks, reuse_unchanged=True)" in source
    assert "results / PLAYER_TRACKS_INPUTS_FILE_NAME," in source
