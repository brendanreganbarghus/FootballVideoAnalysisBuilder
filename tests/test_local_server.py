import importlib.util
import json
import os
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "serve_local", ROOT / "scripts" / "serve-local.py"
)
assert SPEC and SPEC.loader
SERVE_LOCAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVE_LOCAL)


def write_prepared_segment(root: Path, *, ai_ready: bool) -> None:
    root.mkdir(parents=True)
    (root / "alfheim-window-playable.mp4").touch()
    (root / "ball-ground-truth.csv").touch()
    (root / "manifest.json").write_text(
        json.dumps({"start_frame": 0, "end_frame": 1500}),
        encoding="utf-8",
    )
    if ai_ready:
        analytics = root / "analytics-data"
        analytics.mkdir()
        (analytics / "predicted-events.json").write_text("[]", encoding="utf-8")


def test_prepared_segment_list_reports_times_protection_and_ai_state(
    tmp_path: Path, monkeypatch
) -> None:
    generated = tmp_path / "benchmarks" / "alfheim" / "generated"
    write_prepared_segment(generated / "segment-0575-020", ai_ready=True)
    write_prepared_segment(generated / "segment-0700-010", ai_ready=False)
    monkeypatch.chdir(tmp_path)

    handler = object.__new__(SERVE_LOCAL.RangeRequestHandler)
    segments = handler._prepared_segments()

    assert segments == [
        {
            "cache_key": "segment-0575-020",
            "source_start_seconds": 1725,
            "duration_seconds": 60,
            "state": "ready",
            "validated": False,
            "protected": True,
            "video_url": (
                "/benchmarks/alfheim/generated/segment-0575-020/"
                "alfheim-window-playable.mp4"
            ),
            "labels_url": (
                "/benchmarks/alfheim/generated/segment-0575-020/"
                "ball-ground-truth.csv"
            ),
        },
        {
            "cache_key": "segment-0700-010",
            "source_start_seconds": 2100,
            "duration_seconds": 30,
            "state": "prepared",
            "validated": False,
            "protected": False,
            "video_url": (
                "/benchmarks/alfheim/generated/segment-0700-010/"
                "alfheim-window-playable.mp4"
            ),
            "labels_url": (
                "/benchmarks/alfheim/generated/segment-0700-010/"
                "ball-ground-truth.csv"
            ),
        },
    ]


def test_workspace_environment_prioritizes_current_worktree(
    tmp_path: Path, monkeypatch
) -> None:
    previous = str(tmp_path / "other-checkout" / "src")
    monkeypatch.setenv("PYTHONPATH", previous)

    environment = SERVE_LOCAL.workspace_environment(tmp_path)

    assert environment["PYTHONPATH"].split(os.pathsep) == [
        str((tmp_path / "src").resolve()),
        previous,
    ]


def test_html_and_json_responses_disable_browser_caching() -> None:
    handler = object.__new__(SERVE_LOCAL.RangeRequestHandler)
    handler.path = "/benchmarks/example.json"
    handler.headers = {}
    headers: list[tuple[str, str]] = []
    handler.send_header = lambda name, value: headers.append((name, value))
    handler.wfile = None

    original = SERVE_LOCAL.SimpleHTTPRequestHandler.end_headers
    SERVE_LOCAL.SimpleHTTPRequestHandler.end_headers = lambda self: None
    try:
        handler.end_headers()
    finally:
        SERVE_LOCAL.SimpleHTTPRequestHandler.end_headers = original

    assert (
        "Cache-Control",
        "no-store, no-cache, must-revalidate",
    ) in headers
