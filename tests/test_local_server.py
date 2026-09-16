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
    segment_count = int(root.name.rsplit("-", 1)[1])
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "video": str(root / "alfheim-window-playable.mp4"),
                "start_frame": 0,
                "end_frame": segment_count * 75,
                "duration_seconds": segment_count * 3,
            }
        ),
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
            "raw_video_only": True,
            "ball_track_available": False,
            "validated": False,
            "protected": True,
            "video_url": (
                "/benchmarks/alfheim/generated/segment-0575-020/"
                "alfheim-window-playable.mp4"
            ),
            "labels_url": None,
        },
        {
            "cache_key": "segment-0700-010",
            "source_start_seconds": 2100,
            "duration_seconds": 30,
            "state": "prepared",
            "raw_video_only": True,
            "ball_track_available": False,
            "validated": False,
            "protected": False,
            "video_url": (
                "/benchmarks/alfheim/generated/segment-0700-010/"
                "alfheim-window-playable.mp4"
            ),
            "labels_url": None,
        },
    ]


def test_review_segment_list_keeps_datasets_and_calibrations_separate(
    tmp_path: Path, monkeypatch
) -> None:
    generated = tmp_path / "benchmarks" / "alfheim" / "generated"
    write_prepared_segment(generated / "segment-0575-020", ai_ready=True)
    soccertrack = tmp_path / "benchmarks" / "soccertrack-117093-preview"
    soccertrack.mkdir(parents=True)
    (
        soccertrack / "soccertrack-117093-1267-1327-panorama.mp4"
    ).touch()
    monkeypatch.chdir(tmp_path)

    handler = object.__new__(SERVE_LOCAL.RangeRequestHandler)
    segments = handler._review_segments()

    assert [segment["dataset_id"] for segment in segments] == [
        "alfheim",
        "soccertrack-v2",
    ]
    assert segments[0]["calibration_id"] == "alfheim-camera-setting-2"
    assert segments[0]["camera_id"] == (
        "f7a5f35d-9c61-5e9c-b6f3-795742c2c8f1"
    )
    assert segments[0]["recording_id"] == "alfheim-pano-camera-setting-2"
    assert segments[0]["serial_source"] == "assigned_test_identifier"
    assert segments[1]["calibration_id"] == "soccertrack-117093-panorama"
    assert segments[1]["camera_id"] == (
        "6bf49dd4-eac0-57f3-9005-3020789c3a84"
    )
    assert segments[1]["recording_id"] == "soccertrack-117093-first-half"
    assert segments[1]["calibration_status"] == "not_calibrated"
    assert segments[1]["processing_supported"] is False
    assert segments[1]["labels_url"] is None


def test_custom_camera_uses_its_own_sample_and_calibration_state(
    tmp_path: Path, monkeypatch
) -> None:
    custom = tmp_path / "shared" / "custom-home-main"
    custom.mkdir(parents=True)
    sample = custom / "sample.mp4"
    sample.touch()
    (custom / "camera.json").write_text(
        json.dumps(
            {
                "camera_name": "Home main camera",
                "camera_id": "custom-home-main",
                "video_filename": "sample.mp4",
                "image_width": 64,
                "image_height": 36,
                "duration_seconds": 30,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        SERVE_LOCAL,
        "CUSTOM_CAMERA_SOURCE_ROOT",
        custom.parent,
    )
    monkeypatch.setattr(
        SERVE_LOCAL,
        "CUSTOM_CAMERA_RUN_ROOT",
        tmp_path / "runs",
    )
    class FakeCapture:
        def isOpened(self) -> bool:
            return True

        def get(self, property_id: int) -> float:
            return (
                25.0
                if property_id == SERVE_LOCAL.cv2.CAP_PROP_FPS
                else 750.0
            )

        def release(self) -> None:
            pass

    monkeypatch.setattr(SERVE_LOCAL.cv2, "VideoCapture", lambda _: FakeCapture())
    monkeypatch.chdir(tmp_path)

    handler = object.__new__(SERVE_LOCAL.RangeRequestHandler)
    segments = handler._review_segments()

    assert len(segments) == 1
    assert segments[0]["dataset_id"] == "custom-home-main"
    assert segments[0]["video_url"] == (
        "/shared-custom/custom-home-main/sample.mp4"
    )
    assert segments[0]["calibration_status"] == "not_calibrated"
    assert segments[0]["processing_supported"] is False
    assert segments[0]["labels_url"] is None


def test_ai_execution_accepts_only_30_or_60_second_segments() -> None:
    assert SERVE_LOCAL.require_review_duration(30) == 30
    assert SERVE_LOCAL.require_review_duration(60.1) == 60

    for invalid in (0, 29.7, 31, 59, 60.3, 300, float("nan")):
        try:
            SERVE_LOCAL.require_review_duration(invalid)
        except ValueError as error:
            assert "exact 30- or 60-second" in str(error)
        else:
            raise AssertionError(f"{invalid} should not be AI-eligible")


def test_label_referenced_manifest_is_not_ai_eligible(
    tmp_path: Path, monkeypatch
) -> None:
    root = (
        tmp_path
        / "benchmarks"
        / "alfheim"
        / "generated"
        / "segment-0100-020"
    )
    write_prepared_segment(root, ai_ready=True)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest["ball_ground_truth"] = str(root / "ball-ground-truth.csv")
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    handler = object.__new__(SERVE_LOCAL.RangeRequestHandler)
    segment = handler._prepared_segments()[0]

    assert segment["state"] == "invalid_input"
    assert segment["raw_video_only"] is False
    assert segment["validated"] is False


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


def test_review_canvas_launcher_redirects_to_registered_local_url(
    tmp_path: Path, monkeypatch
) -> None:
    generated = tmp_path / "benchmarks" / "alfheim" / "generated"
    generated.mkdir(parents=True)
    (generated / ".football-event-review-urls.json").write_text(
        json.dumps(
            {
                "default": (
                    "http://127.0.0.1:54321/"
                    "?segment=segment-0300-020&theme=default"
                )
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(SERVE_LOCAL, "PROJECT_ROOT", tmp_path)

    handler = object.__new__(SERVE_LOCAL.RangeRequestHandler)
    handler.path = "/review-canvas?theme=default"
    response: dict[str, object] = {}
    handler.send_response = lambda status: response.update(status=status)
    handler.send_header = (
        lambda name, value: response.setdefault("headers", []).append(
            (name, value)
        )
    )
    handler.end_headers = lambda: None

    handler.do_GET()

    assert response["status"] == 302
    assert (
        "Location",
        "http://127.0.0.1:54321/"
        "?segment=segment-0300-020&theme=default",
    ) in response["headers"]
