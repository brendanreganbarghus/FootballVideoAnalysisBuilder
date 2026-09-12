from pathlib import Path

from football_poc.run_performance import (
    build_cache_rebuild_performance_report,
    build_performance_report,
    gpu_planning_guidance,
)


def test_gpu_guidance_reports_measured_speedup_and_qualification() -> None:
    guidance = gpu_planning_guidance(
        source_duration_seconds=60,
        wall_time_seconds=180,
        detection_seconds=150,
    )

    assert guidance["deadline_seconds"] == 60
    assert guidance["cpu_deadline_met"] is False
    assert guidance["required_measured_end_to_end_speedup"] == 3
    assert guidance["required_detection_speedup"] == 5
    assert guidance["minimum_vram_gb"] == 16
    assert "not a throughput guarantee" in guidance["qualification"]


def test_gpu_guidance_flags_when_non_detection_work_misses_deadline() -> None:
    guidance = gpu_planning_guidance(
        source_duration_seconds=30,
        wall_time_seconds=100,
        detection_seconds=60,
    )

    assert guidance["required_detection_speedup"] is None
    assert guidance["gpu_alone_can_meet_deadline"] is False


def test_performance_report_records_cold_input_provenance(
    tmp_path: Path,
) -> None:
    video = tmp_path / "sample.mp4"
    manifest = tmp_path / "runtime-manifest.json"
    model = tmp_path / "model.pt"
    video.write_bytes(b"raw-video")
    manifest.write_text('{"video":"sample.mp4"}', encoding="utf-8")
    model.write_bytes(b"model")

    report = build_performance_report(
        run_id="run-1",
        video=video,
        manifest=manifest,
        model=model,
        source_duration_seconds=60,
        source_fps=25,
        sampled_frames=300,
        wall_time_seconds=75,
        stage_seconds={"detection": 50, "event_inference": 4},
    )

    provenance = report["input_provenance"]
    assert report["mode"] == "cold_raw_video"
    assert report["cache_reuse"] is False
    assert provenance["prior_artifacts_used"] is False
    assert "prior ball tracks" in provenance["excluded_inputs"]
    assert "provider annotations" in provenance["excluded_inputs"]
    assert report["rules_engine_capacity"]["event_inference_seconds"] == 4


def test_cache_rebuild_report_is_not_claimed_as_cold_raw_video_speed(
    tmp_path: Path,
) -> None:
    video = tmp_path / "sample.mp4"
    manifest = tmp_path / "runtime-manifest.json"
    detections = tmp_path / "detections.jsonl"
    video.write_bytes(b"raw-video")
    manifest.write_text('{"video":"sample.mp4"}', encoding="utf-8")
    detections.write_text('{"type":"metadata"}\n', encoding="utf-8")

    report = build_cache_rebuild_performance_report(
        run_id="rebuild-1",
        video=video,
        manifest=manifest,
        detection_cache=detections,
        source_duration_seconds=60,
        source_fps=25,
        sampled_frames=300,
        wall_time_seconds=75,
        stage_seconds={"ball_tracking": 5, "event_inference": 4},
    )

    assert report["mode"] == "cache_rebuild"
    assert report["cache_reuse"] is True
    assert "not a cold raw-video" in report["timing_scope"]
    assert report["input_provenance"]["prior_artifacts_used"] == [
        "frozen detector cache"
    ]
    assert report["processing_rate"]["achieved_source_frames_per_second"] == 20
    assert (
        report["processing_rate"]["acceleration_required_to_meet_deadline"]
        == 1.25
    )
