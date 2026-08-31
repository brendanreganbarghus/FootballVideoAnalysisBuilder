import json
from pathlib import Path

from football_poc.aggregate import aggregate_evaluations


def write_evaluation(
    path: Path,
    *,
    predicted: int,
    ground_truth: int,
    true_positives: int,
) -> None:
    metric = {
        "predicted": predicted,
        "ground_truth": ground_truth,
        "true_positives": true_positives,
        "false_positives": predicted - true_positives,
        "false_negatives": ground_truth - true_positives,
    }
    path.write_text(
        json.dumps({"pass": metric, "shot": metric}),
        encoding="utf-8",
    )


def test_aggregates_micro_metrics(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_evaluation(first, predicted=4, ground_truth=5, true_positives=3)
    write_evaluation(second, predicted=2, ground_truth=3, true_positives=1)

    output = aggregate_evaluations(
        [first, second], tmp_path / "aggregate.json"
    )
    report = json.loads(output.read_text(encoding="utf-8"))

    assert report["window_count"] == 2
    assert report["micro_average"]["pass"] == {
        "predicted": 6,
        "ground_truth": 8,
        "true_positives": 4,
        "false_positives": 2,
        "false_negatives": 4,
        "precision": 0.6667,
        "recall": 0.5,
    }
