from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def aggregate_evaluations(
    evaluation_paths: Iterable[Path], output: Path
) -> Path:
    windows: list[dict[str, Any]] = []
    for path in evaluation_paths:
        if not path.is_file():
            raise FileNotFoundError(f"Evaluation does not exist: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        windows.append(
            {
                "evaluation": str(path.resolve()),
                "pass": payload["pass"],
                "shot": payload["shot"],
            }
        )
    if not windows:
        raise ValueError("At least one evaluation is required")

    aggregate = {
        event_type: _aggregate_event(
            [window[event_type] for window in windows]
        )
        for event_type in ("pass", "shot")
    }
    report = {
        "window_count": len(windows),
        "windows": windows,
        "micro_average": aggregate,
        "interpretation": [
            "Micro metrics sum predictions and labels across all windows.",
            "Windows were selected before inference and use identical thresholds.",
            "These match-specific results are a POC baseline, not production accuracy.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output


def _aggregate_event(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    predicted = sum(int(item["predicted"]) for item in metrics)
    ground_truth = sum(int(item["ground_truth"]) for item in metrics)
    true_positives = sum(int(item["true_positives"]) for item in metrics)
    false_positives = sum(int(item["false_positives"]) for item in metrics)
    false_negatives = sum(int(item["false_negatives"]) for item in metrics)
    return {
        "predicted": predicted,
        "ground_truth": ground_truth,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": (
            round(true_positives / predicted, 4) if predicted else 0.0
        ),
        "recall": (
            round(true_positives / ground_truth, 4)
            if ground_truth
            else 0.0
        ),
    }
