from __future__ import annotations

import json
from pathlib import Path

import pytest

from football_poc.engine.pipeline import STAGES

SEGMENTS = (
    "segment-0080-020",
    "segment-0120-020",
    "segment-0240-020",
    "segment-0260-020",
)


def _short_diff(expected: object, actual: object) -> str:
    if isinstance(expected, dict) and isinstance(actual, dict):
        keys = sorted(set(expected) | set(actual))
        for key in keys:
            if expected.get(key) != actual.get(key):
                return f"key {key!r}: expected {expected.get(key)!r}, got {actual.get(key)!r}"
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return f"list length: expected {len(expected)}, got {len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            if left != right:
                return f"index {index}: expected {left!r}, got {right!r}"
    return f"expected {expected!r}, got {actual!r}"


@pytest.mark.parametrize("segment", SEGMENTS)
def test_engine_stage_golden_outputs(segment: str) -> None:
    results = Path("benchmarks") / "alfheim" / "generated" / segment / "analytics-data"
    golden_dir = Path(__file__).with_name("golden") / segment
    for stage_name, runner in STAGES:
        expected = json.loads((golden_dir / f"{stage_name}.json").read_text(encoding="utf-8"))
        actual = runner(results)
        if actual != expected:
            pytest.fail(
                f"first differing stage: {stage_name}; {_short_diff(expected, actual)}"
            )
