import json
from argparse import Namespace
from pathlib import Path

import pytest

from football_poc.ball_validation_cli import (
    Console,
    _compare_detection_outputs,
    _compare_tracking_outputs,
    _match_points,
    _parse_source_frames,
    _reject_protected_output,
    _resolve_models,
    _resolve_run_paths,
    build_parser,
)


def _write_detection_cache(
    path: Path,
    frames: dict[int, list[tuple[float, float, float]]],
    *,
    target_source_frames: list[int] | None = None,
) -> None:
    lines = [
        json.dumps(
            {
                "type": "metadata",
                "stride": 5,
                "target_source_frames": target_source_frames,
            }
        )
    ]
    for frame, detections in sorted(frames.items()):
        lines.append(
            json.dumps(
                {
                    "type": "frame",
                    "source_frame": frame,
                    "detections": [
                        {
                            "track_id": -1,
                            "class_name": "sports ball",
                            "confidence": confidence,
                            "x1": x - 2,
                            "y1": y - 2,
                            "x2": x + 2,
                            "y2": y + 2,
                        }
                        for x, y, confidence in detections
                    ],
                }
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_states(path: Path, states: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"states": states}), encoding="utf-8")


def test_parser_defaults_to_isolated_twenty_second_yolo_run() -> None:
    args = build_parser().parse_args(["yolo"])

    assert args.segment == "segment-0540-020"
    assert args.models == "n"
    assert args.stride == 5
    assert args.tile_width == 960
    assert args.tile_height == 960
    assert args.confidence == 0.10
    assert args.ball_only is False


def test_yolo_parser_supports_explicit_ball_only_screening() -> None:
    args = build_parser().parse_args(["yolo", "--ball-only"])

    assert args.ball_only is True


def test_sparse_source_frames_are_parsed_for_targeted_yolo() -> None:
    assert _parse_source_frames("505, 820,1285") == (505, 820, 1285)

    with pytest.raises(ValueError, match="comma-separated integers"):
        _parse_source_frames("505,nope")


def test_model_aliases_expand_all_yolo26_sizes() -> None:
    assert _resolve_models("all") == (
        "yolo26n.pt",
        "yolo26s.pt",
        "yolo26m.pt",
        "yolo26l.pt",
        "yolo26x.pt",
    )
    assert _resolve_models("n,m,C:\\weights\\custom.pt") == (
        "yolo26n.pt",
        "yolo26m.pt",
        "C:\\weights\\custom.pt",
    )


def test_protected_live_namespace_is_never_a_run_output(tmp_path: Path) -> None:
    live = tmp_path / "segment" / "live"

    with pytest.raises(ValueError, match="protected live namespace"):
        _reject_protected_output(live / "analytics-cache", live)

    _reject_protected_output(tmp_path / "segment" / "developer-runs", live)


def test_bare_segment_name_is_resolved_under_segment_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    segment_root = tmp_path / "generated"
    segment = segment_root / "segment-0540-020"
    cache = segment / "live" / "analytics-cache"
    cache.mkdir(parents=True)
    (segment / "live" / "runtime-manifest.json").touch()
    unrelated = tmp_path / "segment-0540-020"
    unrelated.mkdir()
    monkeypatch.chdir(tmp_path)

    paths = _resolve_run_paths(
        Namespace(
            segment="segment-0540-020",
            segment_root=segment_root,
            output_root=None,
            run_name="test-run",
        )
    )

    assert paths.segment == segment.resolve()
    assert paths.output_root == (segment / "developer-runs" / "test-run").resolve()


def test_point_matching_is_one_to_one_with_tolerance() -> None:
    matched, missing, gained = _match_points(
        [{"x": 10.0, "y": 10.0}, {"x": 100.0, "y": 100.0}],
        [{"x": 12.0, "y": 11.0}, {"x": 200.0, "y": 200.0}],
        tolerance=5.0,
    )

    assert (matched, missing, gained) == (1, 1, 1)


def test_yolo_comparison_reports_match_missing_gain_and_change(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.jsonl"
    current = tmp_path / "current.jsonl"
    report_path = tmp_path / "report.json"
    _write_detection_cache(
        baseline,
        {
            0: [(10.0, 10.0, 0.5)],
            5: [(20.0, 20.0, 0.4)],
            10: [],
            15: [(40.0, 40.0, 0.3)],
        },
    )
    _write_detection_cache(
        current,
        {
            0: [(12.0, 11.0, 0.6)],
            5: [],
            10: [(30.0, 30.0, 0.2)],
            15: [(80.0, 80.0, 0.3)],
        },
    )

    report = _compare_detection_outputs(
        current,
        baseline,
        report_path,
        tolerance=5.0,
        show_all=False,
        console=Console(enabled=False),
    )

    assert report["counts"] == {
        "CHANGED": 1,
        "GAINED": 1,
        "MATCH": 1,
        "MISSING": 1,
    }
    assert report["comparison_is_post_prediction_only"] is True
    assert json.loads(report_path.read_text(encoding="utf-8")) == report


def test_yolo_comparison_limits_partial_run_to_targeted_frames(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.jsonl"
    current = tmp_path / "current.jsonl"
    report_path = tmp_path / "report.json"
    _write_detection_cache(
        baseline,
        {0: [(10.0, 10.0, 0.5)], 5: [(20.0, 20.0, 0.4)]},
    )
    _write_detection_cache(
        current,
        {5: [(20.0, 20.0, 0.6)]},
        target_source_frames=[5],
    )

    report = _compare_detection_outputs(
        current,
        baseline,
        report_path,
        tolerance=5.0,
        show_all=False,
        console=Console(enabled=False),
    )

    assert report["counts"] == {"MATCH": 1}
    assert [row["source_frame"] for row in report["frames"]] == [5]


def test_tracking_comparison_reports_coordinate_and_provenance_changes(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    report_path = tmp_path / "report.json"
    _write_states(
        baseline,
        [
            {
                "source_frame": 0,
                "x": 10.0,
                "y": 10.0,
                "state": "observed",
                "source_attribution": "yolo26_observed",
            },
            {
                "source_frame": 5,
                "x": 20.0,
                "y": 20.0,
                "state": "observed",
                "source_attribution": "yolo26_observed",
            },
            {"source_frame": 10, "x": 30.0, "y": 30.0},
        ],
    )
    _write_states(
        current,
        [
            {
                "source_frame": 0,
                "x": 11.0,
                "y": 11.0,
                "state": "observed",
                "source_attribution": "yolo26_observed",
            },
            {
                "source_frame": 5,
                "x": 21.0,
                "y": 21.0,
                "state": "visually_reacquired",
                "source_attribution": "temporal_detector_observed",
            },
            {"source_frame": 15, "x": 40.0, "y": 40.0},
        ],
    )

    report = _compare_tracking_outputs(
        current,
        baseline,
        report_path,
        tolerance=5.0,
        show_all=False,
        console=Console(enabled=False),
    )

    assert report["counts"] == {
        "GAINED": 1,
        "MATCH": 1,
        "MISSING": 1,
        "PROVENANCE": 1,
    }
