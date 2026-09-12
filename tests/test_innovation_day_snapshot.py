from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from football_poc.innovation_day_snapshot.player_tracking import (
    PlayerPoint,
    PlayerTrack,
    _stabilize_track_team_causally,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "src" / "football_poc" / "innovation_day_snapshot"


def test_innovation_engine_manifest_matches_source_hashes() -> None:
    manifest = json.loads(
        (SNAPSHOT_ROOT / "snapshot-manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["engine_id"] == "innovation-day-engine-v1"
    assert manifest["input_mode"] == "evaluation_only_provider_coordinates"
    assert manifest["independent_evolution"] is True
    assert manifest["files"] == {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(SNAPSHOT_ROOT.glob("*.py"))
    }


def test_innovation_engine_does_not_import_live_engine_modules() -> None:
    allowed_prefix = "football_poc.innovation_day_snapshot"

    for path in SNAPSHOT_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("football_poc"):
                    assert node.module.startswith(allowed_prefix), (
                        f"{path.name} imports live module {node.module}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("football_poc"):
                        assert alias.name.startswith(allowed_prefix), (
                            f"{path.name} imports live module {alias.name}"
                        )


def test_causal_team_stabilization_is_prefix_invariant() -> None:
    def track(labels: list[str]) -> PlayerTrack:
        return PlayerTrack(
            track_id=75,
            points=[
                PlayerPoint(
                        source_frame=index * 5,
                        clip_seconds=index / 5,
                        confidence=0.9,
                        x1=0,
                        y1=0,
                        x2=10,
                        y2=20,
                        team=label,
                )
                for index, label in enumerate(labels)
            ],
        )

    prefix_labels = ["black", *("red" for _ in range(38))]
    short = track(prefix_labels)
    full = track([*prefix_labels, *("black" for _ in range(164))])

    _stabilize_track_team_causally(short)
    _stabilize_track_team_causally(full)

    assert [point.team for point in short.points] == [
        point.team for point in full.points[: len(short.points)]
    ]
    assert short.points[0].team == "black"
    assert full.points[0].team == "black"
