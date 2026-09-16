from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SOURCE = PROJECT_ROOT / "src"
if str(LOCAL_SOURCE) not in sys.path:
    sys.path.insert(0, str(LOCAL_SOURCE))

from football_poc.artifact_store import discover_artifact_root

STANDARD_ARTIFACTS = (
    "analysis-status.json",
    "runtime-manifest.json",
    "manifest.json",
    "manual-reference.json",
    "analytics-cache/detection-summary.json",
    "analytics-data/match-initialization.json",
    "analytics-data/possession.json",
    "analytics-data/predicted-events.json",
    "analytics-data/chunk-simulation.json",
    "analytics-data/performance-report.json",
)
CACHE_ARTIFACTS = (
    "analytics-cache/detections.jsonl",
    "analytics-cache/ball-tracks.json",
    "analytics-data/player-tracks.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def git_value(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments],
        cwd=PROJECT_ROOT,
        text=True,
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish one local segment run to the shared team catalog."
    )
    parser.add_argument("segment_root", type=Path)
    parser.add_argument("--dataset", required=True)
    parser.add_argument(
        "--status",
        choices=("provisional", "passed", "failed"),
        default="provisional",
    )
    parser.add_argument(
        "--include-cache",
        action="store_true",
        help="Include large detections and tracks for a deliberate debug handoff.",
    )
    args = parser.parse_args()
    segment = args.segment_root.resolve()
    performance_path = segment / "analytics-data" / "performance-report.json"
    if not performance_path.is_file():
        raise FileNotFoundError(
            "A cold-run performance-report.json is required before publication"
        )
    performance = json.loads(performance_path.read_text(encoding="utf-8"))
    if (
        performance.get("mode") != "cold_raw_video"
        or performance.get("cache_reuse") is not False
        or performance.get("input_provenance", {}).get(
            "prior_artifacts_used"
        ) is not False
    ):
        raise ValueError("Only a proven cold raw-video run can be published")
    if args.status == "passed" and not (segment / "manual-reference.json").is_file():
        raise FileNotFoundError(
            "A passed run requires the published manual-reference.json"
        )

    artifact_root = discover_artifact_root()
    if artifact_root is None:
        raise FileNotFoundError("Set FOOTBALL_ARTIFACT_ROOT before publication")
    run_id = str(performance["run_id"])
    destination = (
        artifact_root
        / "40-team-runs"
        / args.dataset
        / segment.name
        / run_id
    )
    if destination.exists():
        raise FileExistsError(f"Shared run already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    artifacts = list(STANDARD_ARTIFACTS)
    if args.include_cache:
        artifacts.extend(CACHE_ARTIFACTS)
    staging = Path(tempfile.mkdtemp(
        prefix=f"{run_id}-",
        dir=destination.parent,
    ))
    try:
        copied: list[Path] = []
        for relative_name in artifacts:
            source = segment / relative_name
            if not source.is_file():
                continue
            target = staging / relative_name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(target)
        metadata = {
            "schema_version": 1,
            "run_id": run_id,
            "dataset": args.dataset,
            "segment": segment.name,
            "status": args.status,
            "git_commit": git_value("rev-parse", "HEAD"),
            "git_branch": git_value("branch", "--show-current"),
            "cache_included": args.include_cache,
            "performance_receipt": "analytics-data/performance-report.json",
        }
        metadata_path = staging / "run.json"
        metadata_path.write_text(
            json.dumps(metadata, indent=2) + "\n",
            encoding="utf-8",
        )
        copied.append(metadata_path)
        checksums = "\n".join(
            f"{sha256(path)} *{path.relative_to(staging).as_posix()}"
            for path in sorted(copied)
        )
        (staging / "checksums.sha256").write_text(
            checksums + "\n",
            encoding="utf-8",
        )
        staging.rename(destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    print(f"Published shared run: {destination}")


if __name__ == "__main__":
    main()
