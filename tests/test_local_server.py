import importlib.util
import json
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
        (analytics / "tracking-verification.webm").touch()


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
