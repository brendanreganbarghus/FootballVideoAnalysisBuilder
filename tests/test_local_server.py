import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from football_poc.coordination import (
    DatabaseHealth,
    DatabaseMode,
    EnvironmentIdentity,
    InMemoryCoordinationRepository,
)


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "serve_local", ROOT / "scripts" / "serve-local.py"
)
assert SPEC and SPEC.loader
SERVE_LOCAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVE_LOCAL)


@pytest.fixture(autouse=True)
def isolate_shared_artifact_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        SERVE_LOCAL,
        "SHARED_ARTIFACT_ROOT",
        tmp_path / "shared-artifacts",
    )


def coordination_service() -> tuple[object, InMemoryCoordinationRepository]:
    repository = InMemoryCoordinationRepository(
        environment=EnvironmentIdentity("test", "test", 1)
    )
    identity = SimpleNamespace(
        developer_id="example\\reviewer",
        machine_id="79b0ab35-063c-44cb-b625-abdb062e7bb2",
        domain="EXAMPLE",
        username="Reviewer",
        hostname="REVIEW-PC",
        ip_address="192.0.2.1",
    )
    return SERVE_LOCAL.CoordinationService(
        repository,
        identity=identity,
    ), repository


def invoke_coordination(
    service: object,
    method: str,
    path: str,
    body: dict[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    handler = object.__new__(SERVE_LOCAL.RangeRequestHandler)
    handler.coordination_service = service
    handler.path = path
    raw = json.dumps(body).encode("utf-8") if body is not None else b""
    handler.headers = {"Content-Length": str(len(raw))}
    handler.rfile = io.BytesIO(raw)
    captured: dict[str, object] = {}
    handler._send_json = lambda status, payload: captured.update(
        status=status, payload=payload
    )
    if method == "GET":
        handler.do_GET()
    else:
        handler.do_POST()
    return int(captured["status"]), captured["payload"]


def test_coordination_handlers_use_injected_repository_and_hide_token() -> None:
    service, repository = coordination_service()

    status, acquired = invoke_coordination(
        service,
        "POST",
        "/api/coordination/acquire",
        {
            "workflow": "innovation_day_bac",
            "segment": "segment-0300-020",
            "stage": "event-review",
        },
    )
    assert status == 200
    token = acquired["lease"]["leaseToken"]

    status, catalogue = invoke_coordination(
        service,
        "GET",
        "/api/coordination/segments?workflow=innovation_day_bac",
    )
    assert status == 200
    assert catalogue["segments"][0]["segment"] == "segment-0300-020"
    assert "leaseToken" not in catalogue["segments"][0]["coordinationLease"]

    status, saved = invoke_coordination(
        service,
        "POST",
        "/api/coordination/state",
        {
            "workflow": "innovation_day_bac",
            "segment": "segment-0300-020",
            "leaseToken": token,
            "expectedVersion": 0,
            "state": {"decisions": {}},
        },
    )
    assert status == 200
    assert saved["version"] == 1
    assert repository.get_state(
        "innovation_day_bac", "segment-0300-020"
    ).state == {"decisions": {}}

    status, read = invoke_coordination(
        service,
        "GET",
        "/api/coordination/state?workflow=innovation_day_bac"
        "&segment=segment-0300-020",
    )
    assert status == 200
    assert read["version"] == 1
    assert "leaseToken" not in read["coordinationLease"]


def test_manual_reference_endpoints_populate_normalized_coordination_state() -> None:
    service, repository = coordination_service()
    _, acquired = invoke_coordination(
        service,
        "POST",
        "/api/coordination/acquire",
        {
            "workflow": "innovation_day_bac",
            "segment": "segment-0080-020",
        },
    )
    token = acquired["lease"]["leaseToken"]
    body = {
        "workflow": "innovation_day_bac",
        "segment": "segment-0080-020",
        "leaseToken": token,
        "events": [
            {
                "key": "M2",
                "timestampMs": 60000,
                "team": "red",
                "type": "completed_pass",
            },
            {
                "key": "M1",
                "timestampMs": 3030,
                "team": "black",
                "type": "completed_pass",
            },
        ],
        "mappings": {"M1": "E9"},
        "approve": False,
    }
    status, saved = invoke_coordination(
        service,
        "POST",
        "/api/coordination/manual-reference",
        body,
    )
    assert status == 200
    assert saved["reference"]["status"] == "draft"
    assert [event["key"] for event in saved["reference"]["events"]] == [
        "M2",
        "M1",
    ]
    assert saved["reference"]["events"][0]["sourceFrame"] == 1499
    assert saved["reference"]["mappings"] == {"M1": "E9"}
    assert repository.get_manual_event_revision(
        "innovation_day_bac", "segment-0080-020", "M2"
    ).timestamp_ms == 60000

    status, approved = invoke_coordination(
        service,
        "POST",
        "/api/coordination/manual-reference",
        {**body, "approve": True},
    )
    assert status == 200
    assert approved["reference"]["status"] == "approved"

    status, loaded = invoke_coordination(
        service,
        "GET",
        "/api/coordination/manual-reference?workflow=innovation_day_bac"
        "&segment=segment-0080-020",
    )
    assert status == 200
    assert loaded["approved"]["approvedAt"]
    assert loaded["approved"]["mappings"] == {"M1": "E9"}


def test_manual_reference_endpoint_requires_lease_and_one_to_one_mapping() -> None:
    service, _ = coordination_service()
    _, acquired = invoke_coordination(
        service,
        "POST",
        "/api/coordination/acquire",
        {
            "workflow": "innovation_day_bac",
            "segment": "segment-0080-020",
        },
    )
    events = [
        {
            "key": key,
            "timestampMs": index * 1000,
            "team": "black",
            "type": "turnover",
        }
        for index, key in enumerate(("M1", "M2"), start=1)
    ]
    status, missing_lease = invoke_coordination(
        service,
        "POST",
        "/api/coordination/manual-reference",
        {
            "workflow": "innovation_day_bac",
            "segment": "segment-0080-020",
            "events": events,
            "mappings": {},
        },
    )
    assert (status, missing_lease["code"]) == (400, "validation_error")

    status, duplicate = invoke_coordination(
        service,
        "POST",
        "/api/coordination/manual-reference",
        {
            "workflow": "innovation_day_bac",
            "segment": "segment-0080-020",
            "leaseToken": acquired["lease"]["leaseToken"],
            "events": events,
            "mappings": {"M1": "E1", "M2": "E1"},
        },
    )
    assert (status, duplicate["code"]) == (400, "validation_error")


def test_coordination_handlers_map_conflicts_and_validation() -> None:
    service, _ = coordination_service()
    original_identity = service.identity
    _, first = invoke_coordination(
        service,
        "POST",
        "/api/coordination/acquire",
        {
            "workflow": "innovation_day_bac",
            "segment": "segment-0300-020",
        },
    )
    status, reattached = invoke_coordination(
        service,
        "POST",
        "/api/coordination/acquire",
        {
            "workflow": "innovation_day_bac",
            "segment": "segment-0300-020",
        },
    )
    assert status == 200
    assert reattached["lease"]["leaseToken"] == first["lease"]["leaseToken"]

    service.identity = SimpleNamespace(
        **{
            **vars(service.identity),
            "developer_id": "example\\other-reviewer",
        }
    )
    status, conflict = invoke_coordination(
        service,
        "POST",
        "/api/coordination/acquire",
        {
            "workflow": "innovation_day_bac",
            "segment": "segment-0300-020",
        },
    )
    assert (status, conflict["code"]) == (423, "lease_conflict")
    service.identity = original_identity

    token = first["lease"]["leaseToken"]
    invoke_coordination(
        service,
        "POST",
        "/api/coordination/state",
        {
            "workflow": "innovation_day_bac",
            "segment": "segment-0300-020",
            "leaseToken": token,
            "expectedVersion": 0,
            "state": {},
        },
    )
    status, conflict = invoke_coordination(
        service,
        "POST",
        "/api/coordination/state",
        {
            "workflow": "innovation_day_bac",
            "segment": "segment-0300-020",
            "leaseToken": token,
            "expectedVersion": 0,
            "state": {},
        },
    )
    assert (status, conflict["code"]) == (409, "state_version_conflict")

    status, invalid = invoke_coordination(
        service,
        "POST",
        "/api/coordination/state",
        {"workflow": "wrong", "segment": "../bad"},
    )
    assert (status, invalid["code"]) == (400, "validation_error")


def test_coordination_unavailable_stays_read_only() -> None:
    class UnavailableRepository:
        def health(self) -> DatabaseHealth:
            return DatabaseHealth(DatabaseMode.UNAVAILABLE, "database offline")

        def close(self) -> None:
            pass

    service = SERVE_LOCAL.CoordinationService(UnavailableRepository())
    status, health = invoke_coordination(
        service, "GET", "/api/coordination/health"
    )
    assert status == 200
    assert health["mode"] == "unavailable"

    status, payload = invoke_coordination(
        service,
        "POST",
        "/api/coordination/acquire",
        {
            "workflow": "innovation_day_bac",
            "segment": "segment-0300-020",
        },
    )
    assert (status, payload["code"]) == (503, "coordination_unavailable")


def test_coordination_bootstrap_exception_returns_unavailable(
    monkeypatch,
) -> None:
    def fail_config() -> None:
        raise ValueError("malformed coordination config")

    monkeypatch.setattr(
        SERVE_LOCAL.CoordinationConfig,
        "from_environment",
        staticmethod(fail_config),
    )

    service = SERVE_LOCAL.CoordinationService.bootstrap()

    assert service.mode is DatabaseMode.UNAVAILABLE
    assert service.health_payload() == {
        "mode": "unavailable",
        "detail": "Coordination startup configuration failed: ValueError",
        "deployment": None,
    }
    service.close()


def test_main_bootstraps_once_attaches_service_and_closes(
    monkeypatch,
) -> None:
    calls = {"bootstrap": 0, "serve": 0, "server_close": 0, "close": 0}

    class FakeService:
        mode = DatabaseMode.DISABLED

        def close(self) -> None:
            calls["close"] += 1

    service = FakeService()

    def bootstrap() -> FakeService:
        calls["bootstrap"] += 1
        return service

    class FakeServer:
        def __init__(self, address, handler) -> None:
            self.address = address
            self.handler = handler
            self.coordination_service = None

        def serve_forever(self) -> None:
            calls["serve"] += 1
            assert self.coordination_service is service

        def server_close(self) -> None:
            calls["server_close"] += 1

    monkeypatch.setattr(
        SERVE_LOCAL.CoordinationService, "bootstrap", staticmethod(bootstrap)
    )
    monkeypatch.setattr(SERVE_LOCAL, "ThreadingHTTPServer", FakeServer)
    monkeypatch.setattr(
        sys,
        "argv",
        ["serve-local.py", "--directory", str(ROOT)],
    )

    SERVE_LOCAL.main()

    assert calls == {
        "bootstrap": 1,
        "serve": 1,
        "server_close": 1,
        "close": 1,
    }


def write_prepared_segment(
    root: Path,
    *,
    ai_ready: bool,
    review_workflows: tuple[str, ...] = (),
) -> None:
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
                "review_workflows": list(review_workflows),
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
            "evidence_ready": False,
            "validated": False,
            "protected": True,
            "video_url": (
                "/benchmarks/alfheim/generated/segment-0575-020/"
                "alfheim-window-playable.mp4"
            ),
            "prepared_root": str(
                (generated / "segment-0575-020").resolve()
            ),
            "review_workflows": [],
            "labels_url": None,
        },
        {
            "cache_key": "segment-0700-010",
            "source_start_seconds": 2100,
            "duration_seconds": 30,
            "state": "prepared",
            "raw_video_only": True,
            "ball_track_available": False,
            "evidence_ready": False,
            "validated": False,
            "protected": False,
            "video_url": (
                "/benchmarks/alfheim/generated/segment-0700-010/"
                "alfheim-window-playable.mp4"
            ),
            "prepared_root": str(
                (generated / "segment-0700-010").resolve()
            ),
            "review_workflows": [],
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


def test_dynamic_prepared_segments_stay_in_their_registered_workflow(
    tmp_path: Path, monkeypatch
) -> None:
    generated = tmp_path / "benchmarks" / "alfheim" / "generated"
    write_prepared_segment(
        generated / "segment-0080-020",
        ai_ready=False,
        review_workflows=("innovation_day_bac",),
    )
    write_prepared_segment(
        generated / "segment-0060-020",
        ai_ready=True,
        review_workflows=("innovation_day_bac",),
    )
    write_prepared_segment(
        generated / "segment-0100-020",
        ai_ready=False,
        review_workflows=("live_iteration_25",),
    )
    monkeypatch.chdir(tmp_path)

    handler = object.__new__(SERVE_LOCAL.RangeRequestHandler)
    innovation = handler._alfheim_review_segments(namespace="innovation")
    live = handler._alfheim_review_segments(namespace="live")

    assert [segment["cache_key"] for segment in innovation] == [
        "segment-0080-020"
    ]
    assert [segment["cache_key"] for segment in live] == [
        "segment-0100-020"
    ]


def test_shared_prepared_segments_are_listed_without_local_generated_copy(
    tmp_path: Path, monkeypatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    shared = (
        artifact_root
        / "15-prepared-segments"
        / "camera-1"
        / "recording-1"
        / "segment-0120-020"
    )
    run_root = shared / "innovation"
    (run_root / "analytics-cache").mkdir(parents=True)
    (run_root / "analytics-data").mkdir()
    (shared / "segment.mp4").write_bytes(b"video")
    (shared / "manifest.json").write_text(
        json.dumps(
            {
                "video": "segment.mp4",
                "start_frame": 0,
                "end_frame": 1500,
                "source_start_seconds": 360.0,
                "duration_seconds": 60.0,
                "review_workflows": ["innovation_day_bac"],
            }
        ),
        encoding="utf-8",
    )
    (shared / "segment.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "segment_id": "segment-0120-020",
                "dataset_id": "alfheim",
                "source_start_seconds": 360.0,
                "duration_seconds": 60.0,
                "video": "segment.mp4",
                "manifest": "manifest.json",
                "workflows": ["innovation_day_bac"],
                "workflow_artifacts": {
                    "innovation_day_bac": "innovation"
                },
                "camera_id": "camera-1",
                "recording_id": "recording-1",
            }
        ),
        encoding="utf-8",
    )
    (run_root / "analytics-cache" / "ball-tracks.json").write_text(
        "[]", encoding="utf-8"
    )
    (run_root / "analytics-cache" / "detections.jsonl").write_text(
        '{"stride":5}\n', encoding="utf-8"
    )
    (run_root / "analytics-data" / "player-tracks.json").write_text(
        "[]", encoding="utf-8"
    )
    (run_root / "analytics-data" / "predicted-events.json").write_text(
        "[]", encoding="utf-8"
    )
    (run_root / "manual-reference.json").write_text(
        '{"events":[]}', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        SERVE_LOCAL,
        "SHARED_ARTIFACT_ROOT",
        artifact_root,
    )
    handler = object.__new__(SERVE_LOCAL.RangeRequestHandler)

    innovation = handler._alfheim_review_segments(namespace="innovation")
    live = handler._alfheim_review_segments(namespace="live")

    assert [segment["cache_key"] for segment in innovation] == [
        "segment-0120-020"
    ]
    assert live == []
    segment = innovation[0]
    assert segment["validated"] is True
    assert segment["prepared_root"] == str(shared.resolve())
    assert segment["video_url"] == (
        "/shared-prepared/segment-0120-020/segment.mp4"
    )
    assert Path(handler.translate_path(segment["video_url"])) == (
        shared / "segment.mp4"
    ).resolve()


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
