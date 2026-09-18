from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from football_poc.ball_tracking import track_cached_balls
from football_poc.benchmark import BenchmarkManifest, run_detection_cache


DEFAULT_SEGMENT_ROOT = Path("benchmarks/alfheim/generated")
DEFAULT_RUN_NAME = "ball-validation"
MODEL_ALIASES = {
    size: f"yolo26{size}.pt" for size in ("n", "s", "m", "l", "x")
}
ANSI = {
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "cyan": "\033[36m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}


@dataclass(frozen=True)
class RunPaths:
    segment: Path
    manifest: Path
    protected_cache: Path
    output_root: Path


class Console:
    def __init__(self, *, enabled: bool) -> None:
        self.enabled = enabled

    def color(self, text: str, color: str) -> str:
        if not self.enabled:
            return text
        return f"{ANSI[color]}{text}{ANSI['reset']}"

    def heading(self, text: str) -> None:
        print(self.color(text, "bold"))

    def status(self, label: str, text: str) -> None:
        colors = {
            "COMPLETE": "green",
            "MATCH": "green",
            "EMPTY": "green",
            "GAINED": "cyan",
            "CHANGED": "yellow",
            "MOVED": "yellow",
            "PROVENANCE": "yellow",
            "MISSING": "red",
        }
        print(f"{self.color(label.ljust(10), colors[label])} {text}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run and compare isolated YOLO and ball-coordinate stages. "
            "Evaluation references are loaded only after predictions finish."
        )
    )
    parser.add_argument(
        "--segment-root",
        type=Path,
        default=DEFAULT_SEGMENT_ROOT,
        help="Directory containing prepared segment-* directories.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors (NO_COLOR is also supported).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    yolo = subparsers.add_parser(
        "yolo",
        help="Run tiled YOLO only for one or more model sizes.",
    )
    _add_common_run_arguments(yolo)
    _add_yolo_arguments(yolo)

    track = subparsers.add_parser(
        "track",
        help="Run ball-coordinate tracking from completed YOLO caches.",
    )
    _add_common_run_arguments(track)
    _add_model_arguments(track)
    _add_tracking_arguments(track)

    pipeline = subparsers.add_parser(
        "pipeline",
        help="Run tiled YOLO followed by ball-coordinate tracking.",
    )
    _add_common_run_arguments(pipeline)
    _add_yolo_arguments(pipeline)
    _add_tracking_arguments(pipeline)

    compare = subparsers.add_parser(
        "compare",
        help="Compare existing run outputs with the protected live baseline.",
    )
    _add_common_run_arguments(compare, include_compare=False)
    _add_model_arguments(compare)
    compare.add_argument(
        "--stage",
        choices=("yolo", "track", "all"),
        default="all",
    )
    return parser


def _add_common_run_arguments(
    parser: argparse.ArgumentParser, *, include_compare: bool = True
) -> None:
    parser.add_argument(
        "--segment",
        default="segment-0540-020",
        help="Prepared segment name or path; defaults to the 20-second segment.",
    )
    parser.add_argument(
        "--run-name",
        default=DEFAULT_RUN_NAME,
        help="Isolated developer-run directory name inside the segment.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Override the isolated output root.",
    )
    if include_compare:
        parser.add_argument(
            "--compare",
            action="store_true",
            help=(
                "Compare frozen output with the segment's protected live "
                "baseline."
            ),
        )
    parser.add_argument(
        "--tolerance-pixels",
        type=float,
        default=12.0,
        help="Maximum centre distance for a coordinate match.",
    )
    parser.add_argument(
        "--show-all-frames",
        action="store_true",
        help="Print matching/empty frames as well as changed frames.",
    )


def _add_model_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--models",
        default="n",
        help=(
            "Comma-separated YOLO26 sizes (n,s,m,l,x), 'all', model names, "
            "or weight paths."
        ),
    )


def _add_yolo_arguments(parser: argparse.ArgumentParser) -> None:
    _add_model_arguments(parser)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--confidence", type=float, default=0.10)
    parser.add_argument("--image-size", type=int, default=960)
    parser.add_argument("--stride", type=int, default=5)
    parser.add_argument("--tile-width", type=int, default=960)
    parser.add_argument("--tile-height", type=int, default=960)
    parser.add_argument("--overlap", type=float, default=0.2)
    parser.add_argument("--nms-iou", type=float, default=0.5)
    parser.add_argument("--frame-batch-size", type=int, default=2)
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Diagnostic limit; omit for all 100 sampled frames.",
    )
    parser.add_argument(
        "--frames",
        default=None,
        help=(
            "Comma-separated source-frame numbers to process exactly; "
            "cannot be combined with --max-frames."
        ),
    )
    parser.add_argument(
        "--reuse-cache",
        action="store_true",
        help="Resume a matching cache; never reported as a cold run.",
    )
    parser.add_argument(
        "--ball-only",
        action="store_true",
        help=(
            "YOLO screening only: detect sports balls without people. "
            "The resulting cache cannot be used by the ball tracker."
        ),
    )


def _add_tracking_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--static-cell-size", type=int, default=20)
    parser.add_argument("--static-occupancy", type=float, default=0.25)
    parser.add_argument("--max-gap", type=float, default=0.56)
    parser.add_argument("--max-speed", type=float, default=1600.0)
    parser.add_argument("--minimum-track-points", type=int, default=3)
    parser.add_argument(
        "--reuse-decoded-frame-cache",
        action="store_true",
        help="Interrupted-run recovery only; never reported as a cold run.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    console = Console(enabled=_colors_enabled(args.no_color))
    try:
        paths = _resolve_run_paths(args)
        models = _resolve_models(args.models)
        if args.command == "pipeline" and args.ball_only:
            raise ValueError(
                "--ball-only is a YOLO screening mode and cannot be combined "
                "with the ball-tracking pipeline."
            )
        if args.command == "pipeline" and args.frames:
            raise ValueError(
                "--frames creates a partial detector experiment and cannot be "
                "combined with the ball-tracking pipeline."
            )
        _print_run_header(console, args, paths, models)
        if args.command in {"yolo", "pipeline"}:
            for model in models:
                _run_yolo(args, paths, model, console)
        if args.command in {"track", "pipeline"}:
            for model in models:
                _run_tracking(args, paths, model, console)
        if args.command == "compare":
            for model in models:
                output = _model_output(paths.output_root, model)
                if args.stage in {"yolo", "all"}:
                    _compare_detection_outputs(
                        output / "detections.jsonl",
                        paths.protected_cache / "detections.jsonl",
                        output / "yolo-comparison.json",
                        tolerance=args.tolerance_pixels,
                        show_all=args.show_all_frames,
                        console=console,
                    )
                if args.stage in {"track", "all"}:
                    _compare_tracking_outputs(
                        output / "ball-state-estimates.json",
                        paths.protected_cache / "ball-state-estimates.json",
                        output / "tracking-comparison.json",
                        tolerance=args.tolerance_pixels,
                        show_all=args.show_all_frames,
                        console=console,
                    )
        return 0
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(console.color(f"ERROR: {error}", "red"), file=sys.stderr)
        return 2


def _resolve_run_paths(args: argparse.Namespace) -> RunPaths:
    segment_value = Path(args.segment)
    segment = (
        segment_value
        if segment_value.is_absolute() or segment_value.parent != Path(".")
        else args.segment_root / segment_value
    ).resolve()
    if not segment.is_dir():
        raise FileNotFoundError(f"Prepared segment does not exist: {segment}")
    manifest = segment / "live" / "runtime-manifest.json"
    protected_cache = segment / "live" / "analytics-cache"
    if not manifest.is_file():
        raise FileNotFoundError(f"Runtime manifest does not exist: {manifest}")
    if not protected_cache.is_dir():
        raise FileNotFoundError(
            f"Protected comparison cache does not exist: {protected_cache}"
        )
    output_root = (
        args.output_root.resolve()
        if args.output_root is not None
        else (segment / "developer-runs" / args.run_name).resolve()
    )
    _reject_protected_output(output_root, segment / "live")
    return RunPaths(
        segment=segment,
        manifest=manifest,
        protected_cache=protected_cache,
        output_root=output_root,
    )


def _reject_protected_output(output: Path, live: Path) -> None:
    try:
        output.relative_to(live.resolve())
    except ValueError:
        return
    raise ValueError(
        f"Refusing to write inside the protected live namespace: {output}"
    )


def _resolve_models(value: str) -> tuple[str, ...]:
    entries = [entry.strip() for entry in value.split(",") if entry.strip()]
    if entries == ["all"]:
        entries = list(MODEL_ALIASES)
    if not entries:
        raise ValueError("--models must contain at least one model")
    models = tuple(MODEL_ALIASES.get(entry.lower(), entry) for entry in entries)
    if len(set(models)) != len(models):
        raise ValueError("--models contains duplicate model entries")
    return models


def _parse_source_frames(value: str | None) -> tuple[int, ...] | None:
    if value is None:
        return None
    try:
        frames = tuple(int(entry.strip()) for entry in value.split(","))
    except ValueError as error:
        raise ValueError("--frames must be comma-separated integers") from error
    if any(frame < 0 for frame in frames):
        raise ValueError("--frames cannot contain negative values")
    return frames


def _model_output(output_root: Path, model: str) -> Path:
    model_name = Path(model).stem
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", model_name).strip("-")
    if not slug:
        raise ValueError(f"Could not create an output name for model: {model}")
    return output_root / slug


def _print_run_header(
    console: Console,
    args: argparse.Namespace,
    paths: RunPaths,
    models: tuple[str, ...],
) -> None:
    console.heading("Ball detection validation")
    print(f"Command:            {args.command}")
    print(f"Segment:            {paths.segment}")
    print(f"Runtime manifest:   {paths.manifest}")
    print(f"Protected baseline: {paths.protected_cache}")
    print(f"Isolated output:    {paths.output_root}")
    print(f"Models:             {', '.join(models)}")
    print(
        "Comparison policy: predictions are completed and frozen before "
        "the protected baseline is loaded."
    )


def _run_yolo(
    args: argparse.Namespace,
    paths: RunPaths,
    model: str,
    console: Console,
) -> None:
    output = _model_output(paths.output_root, model)
    console.heading(f"\nYOLO: {model}")
    print(f"Output: {output}")
    started_at = time.perf_counter()
    cache = run_detection_cache(
        manifest_path=paths.manifest,
        output=output,
        model_name=model,
        confidence=args.confidence,
        image_size=args.image_size,
        device=args.device,
        stride=args.stride,
        tile_width=args.tile_width,
        tile_height=args.tile_height,
        overlap=args.overlap,
        nms_iou=args.nms_iou,
        max_frames=args.max_frames,
        frame_batch_size=args.frame_batch_size,
        reuse_cache=args.reuse_cache,
        ball_only=args.ball_only,
        source_frames=_parse_source_frames(args.frames),
    )
    wall_seconds = time.perf_counter() - started_at
    summary_path = output / "detection-summary.json"
    summary = _load_json_object(summary_path)
    _print_detection_summary(console, summary, wall_seconds)
    _write_run_report(
        output / "yolo-run-report.json",
        stage="yolo",
        model=model,
        execution_mode=(
            "interrupted_run_cache_reuse"
            if args.reuse_cache
            else "cold_raw_video"
        ),
        wall_seconds=wall_seconds,
        artifacts=[cache, summary_path],
        summary=summary,
    )
    if args.compare:
        _compare_detection_outputs(
            cache,
            paths.protected_cache / "detections.jsonl",
            output / "yolo-comparison.json",
            tolerance=args.tolerance_pixels,
            show_all=args.show_all_frames,
            console=console,
        )


def _run_tracking(
    args: argparse.Namespace,
    paths: RunPaths,
    model: str,
    console: Console,
) -> None:
    output = _model_output(paths.output_root, model)
    cache = output / "detections.jsonl"
    if not cache.is_file():
        raise FileNotFoundError(
            f"YOLO cache for {model} does not exist: {cache}. Run yolo first."
        )
    console.heading(f"\nBall tracking: {model}")
    print(f"Input cache: {cache}")
    print(f"Output:      {output}")
    started_at = time.perf_counter()
    tracks = track_cached_balls(
        manifest_path=paths.manifest,
        cache_path=cache,
        output=output,
        static_cell_size=args.static_cell_size,
        static_occupancy=args.static_occupancy,
        max_gap_seconds=args.max_gap,
        max_speed_pixels_per_second=args.max_speed,
        minimum_track_points=args.minimum_track_points,
        reuse_decoded_frame_cache=args.reuse_decoded_frame_cache,
    )
    wall_seconds = time.perf_counter() - started_at
    summary_path = output / "ball-tracking-summary.json"
    metrics_path = output / "decode-cache-metrics.json"
    states_path = output / "ball-state-estimates.json"
    summary = _load_json_object(summary_path)
    metrics = _load_json_object(metrics_path)
    manifest = BenchmarkManifest.load(paths.manifest)
    video_seconds = manifest.source_frame_count / manifest.fps
    _print_tracking_summary(
        console,
        summary,
        metrics,
        wall_seconds,
        video_seconds=video_seconds,
        source_frames=manifest.source_frame_count,
    )
    _write_run_report(
        output / "tracking-run-report.json",
        stage="ball_tracking",
        model=model,
        execution_mode=(
            "detection_cache_plus_reused_decoded_frames"
            if args.reuse_decoded_frame_cache
            else "detection_cache_plus_fresh_raw_video_decode"
        ),
        wall_seconds=wall_seconds,
        artifacts=[tracks, states_path, summary_path, metrics_path],
        summary={"tracking": summary, "timing": metrics},
    )
    if args.compare:
        _compare_tracking_outputs(
            states_path,
            paths.protected_cache / "ball-state-estimates.json",
            output / "tracking-comparison.json",
            tolerance=args.tolerance_pixels,
            show_all=args.show_all_frames,
            console=console,
        )


def _print_detection_summary(
    console: Console,
    summary: dict[str, Any],
    wall_seconds: float,
) -> None:
    run = summary.get("last_run") or {}
    timings = run.get("timing_seconds") or {}
    processed = int(summary.get("processed_frames", 0))
    expected = int(summary.get("expected_frames", 0))
    coverage = 100 * float(summary.get("ball_frame_coverage", 0.0))
    detection_counts = summary.get("detection_counts") or {}
    ball_candidates = int(detection_counts.get("sports ball", 0))
    video_seconds = _sampled_video_seconds(summary)
    stride = int((summary.get("configuration") or {}).get("stride", 0))
    source_frames = processed * stride
    console.status(
        "COMPLETE" if summary.get("complete") else "CHANGED",
        (
            f"{processed}/{expected} sampled frames; "
            f"{ball_candidates} ball candidates on {coverage:.1f}% of frames"
        ),
    )
    print(f"Wall time:          {wall_seconds:.3f}s")
    if video_seconds > 0:
        print(f"Real-time factor:   {wall_seconds / video_seconds:.3f}x")
        print(f"Achieved source FPS:{source_frames / wall_seconds:9.3f}")
    for key, label in (
        ("model_load", "Model load"),
        ("video_decode", "Video decode"),
        ("model_inference", "Model inference"),
        ("postprocess_and_write", "Postprocess/write"),
        ("other_run_overhead", "Other overhead"),
    ):
        if key in timings:
            print(f"{label + ':':19} {float(timings[key]):.3f}s")
    print(f"Summary:            {summary.get('cache')}")


def _print_tracking_summary(
    console: Console,
    summary: dict[str, Any],
    metrics: dict[str, Any],
    wall_seconds: float,
    *,
    video_seconds: float,
    source_frames: int,
) -> None:
    tracked = int(summary.get("tracked_frames", 0))
    processed = int(summary.get("processed_frames", 0))
    coverage = 100 * float(summary.get("tracked_frame_coverage", 0.0))
    console.status(
        "MATCH" if tracked == processed else "CHANGED",
        (
            f"{tracked}/{processed} Direct frames ({coverage:.1f}% coverage); "
            f"{processed - tracked} Estimated"
        ),
    )
    print(f"Wall time:          {wall_seconds:.3f}s")
    if video_seconds > 0:
        print(f"Real-time factor:   {wall_seconds / video_seconds:.3f}x")
        print(f"Achieved source FPS:{source_frames / wall_seconds:9.3f}")
    print(f"Frame-cache build:  {float(metrics.get('build_seconds', 0.0)):.3f}s")
    substages = metrics.get("substage_seconds") or {}
    measured_seconds = float(metrics.get("build_seconds", 0.0)) + sum(
        float(seconds) for seconds in substages.values()
    )
    print(f"Other overhead:     {max(0.0, wall_seconds - measured_seconds):.3f}s")
    if substages:
        console.heading("Slowest tracker substages")
        for name, seconds in sorted(
            substages.items(), key=lambda item: float(item[1]), reverse=True
        )[:10]:
            print(f"  {name:40} {float(seconds):9.3f}s")
    print(
        "Outputs:            ball-tracks.json, ball-state-estimates.json, "
        "ball-tracking-summary.json, decode-cache-metrics.json"
    )


def _sampled_video_seconds(summary: dict[str, Any]) -> float:
    configuration = summary.get("configuration") or {}
    processed = int(summary.get("processed_frames", 0))
    stride = int(configuration.get("stride", 0))
    manifest_value = summary.get("manifest")
    if not manifest_value or stride <= 0:
        return 0.0
    try:
        manifest = BenchmarkManifest.load(Path(str(manifest_value)))
    except (FileNotFoundError, ValueError):
        return 0.0
    return min(manifest.source_frame_count, processed * stride) / manifest.fps


def _compare_detection_outputs(
    current_path: Path,
    baseline_path: Path,
    report_path: Path,
    *,
    tolerance: float,
    show_all: bool,
    console: Console,
) -> dict[str, Any]:
    current = _load_ball_detections(current_path)
    baseline = _load_ball_detections(baseline_path)
    targeted_frames = _detection_target_frames(current_path)
    frames = (
        sorted(targeted_frames)
        if targeted_frames is not None
        else sorted(set(current) | set(baseline))
    )
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    console.heading("\nYOLO comparison")
    for frame in frames:
        current_points = current.get(frame, [])
        baseline_points = baseline.get(frame, [])
        matched, missing, gained = _match_points(
            baseline_points, current_points, tolerance=tolerance
        )
        if not baseline_points and not current_points:
            status = "EMPTY"
        elif baseline_points and not current_points:
            status = "MISSING"
        elif current_points and not baseline_points:
            status = "GAINED"
        elif not missing and not gained:
            status = "MATCH"
        else:
            status = "CHANGED"
        counts[status] = counts.get(status, 0) + 1
        row = {
            "source_frame": frame,
            "status": status,
            "matched_candidates": matched,
            "missing_candidates": missing,
            "gained_candidates": gained,
            "baseline_candidates": baseline_points,
            "current_candidates": current_points,
        }
        rows.append(row)
        if show_all or status not in {"MATCH", "EMPTY"}:
            console.status(
                status,
                (
                    f"frame {frame}: baseline={len(baseline_points)} "
                    f"current={len(current_points)} matched={matched}"
                ),
            )
    report = _comparison_report(
        "yolo_candidates", current_path, baseline_path, tolerance, counts, rows
    )
    _write_json(report_path, report)
    _print_comparison_totals(console, counts, report_path)
    return report


def _compare_tracking_outputs(
    current_path: Path,
    baseline_path: Path,
    report_path: Path,
    *,
    tolerance: float,
    show_all: bool,
    console: Console,
) -> dict[str, Any]:
    current = _load_ball_states(current_path)
    baseline = _load_ball_states(baseline_path)
    frames = sorted(set(current) | set(baseline))
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    console.heading("\nBall-coordinate comparison")
    for frame in frames:
        now = current.get(frame)
        before = baseline.get(frame)
        distance = None
        if before is None:
            status = "GAINED"
        elif now is None:
            status = "MISSING"
        else:
            distance = math.hypot(
                float(now["x"]) - float(before["x"]),
                float(now["y"]) - float(before["y"]),
            )
            same_provenance = (
                now.get("state") == before.get("state")
                and now.get("source_attribution")
                == before.get("source_attribution")
            )
            if distance > tolerance:
                status = "MOVED"
            elif not same_provenance:
                status = "PROVENANCE"
            else:
                status = "MATCH"
        counts[status] = counts.get(status, 0) + 1
        row = {
            "source_frame": frame,
            "status": status,
            "distance_pixels": round(distance, 3) if distance is not None else None,
            "baseline": before,
            "current": now,
        }
        rows.append(row)
        if show_all or status != "MATCH":
            distance_text = (
                f" distance={distance:.2f}px" if distance is not None else ""
            )
            console.status(status, f"frame {frame}:{distance_text}")
    report = _comparison_report(
        "ball_coordinates", current_path, baseline_path, tolerance, counts, rows
    )
    _write_json(report_path, report)
    _print_comparison_totals(console, counts, report_path)
    return report


def _load_ball_detections(path: Path) -> dict[int, list[dict[str, float]]]:
    if not path.is_file():
        raise FileNotFoundError(f"Detection cache does not exist: {path}")
    frames: dict[int, list[dict[str, float]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("type") != "frame":
            continue
        points = []
        for detection in record.get("detections", []):
            if detection.get("class_name") != "sports ball":
                continue
            points.append(
                {
                    "x": (float(detection["x1"]) + float(detection["x2"])) / 2,
                    "y": (float(detection["y1"]) + float(detection["y2"])) / 2,
                    "confidence": float(detection["confidence"]),
                }
            )
        frames[int(record["source_frame"])] = points
    return frames


def _detection_target_frames(path: Path) -> set[int] | None:
    first_line = next(
        iter(path.read_text(encoding="utf-8").splitlines()),
        None,
    )
    if first_line is None:
        return None
    metadata = json.loads(first_line)
    target_frames = metadata.get("target_source_frames")
    if not isinstance(target_frames, list):
        return None
    return {int(frame) for frame in target_frames}


def _load_ball_states(path: Path) -> dict[int, dict[str, Any]]:
    payload = _load_json_object(path)
    return {
        int(state["source_frame"]): state for state in payload.get("states", [])
    }


def _match_points(
    baseline: list[dict[str, float]],
    current: list[dict[str, float]],
    *,
    tolerance: float,
) -> tuple[int, int, int]:
    available = set(range(len(current)))
    matched = 0
    for expected in baseline:
        nearest = min(
            available,
            key=lambda index: math.hypot(
                current[index]["x"] - expected["x"],
                current[index]["y"] - expected["y"],
            ),
            default=None,
        )
        if nearest is None:
            continue
        distance = math.hypot(
            current[nearest]["x"] - expected["x"],
            current[nearest]["y"] - expected["y"],
        )
        if distance <= tolerance:
            matched += 1
            available.remove(nearest)
    return matched, len(baseline) - matched, len(current) - matched


def _comparison_report(
    kind: str,
    current_path: Path,
    baseline_path: Path,
    tolerance: float,
    counts: dict[str, int],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "kind": kind,
        "comparison_is_post_prediction_only": True,
        "current": str(current_path.resolve()),
        "baseline": str(baseline_path.resolve()),
        "tolerance_pixels": tolerance,
        "counts": dict(sorted(counts.items())),
        "frames": rows,
    }


def _print_comparison_totals(
    console: Console, counts: dict[str, int], report_path: Path
) -> None:
    totals = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    print(f"Totals:             {totals}")
    print(f"Comparison report:  {report_path.resolve()}")


def _write_run_report(
    path: Path,
    *,
    stage: str,
    model: str,
    execution_mode: str,
    wall_seconds: float,
    artifacts: Iterable[Path],
    summary: dict[str, Any],
) -> None:
    _write_json(
        path,
        {
            "stage": stage,
            "model": model,
            "execution_mode": execution_mode,
            "wall_seconds": round(wall_seconds, 3),
            "artifacts": [str(artifact.resolve()) for artifact in artifacts],
            "summary": summary,
        },
    )
    print(f"Run report:         {path.resolve()}")


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"JSON artifact does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _colors_enabled(disabled: bool) -> bool:
    return not disabled and "NO_COLOR" not in os.environ


if __name__ == "__main__":
    raise SystemExit(main())
