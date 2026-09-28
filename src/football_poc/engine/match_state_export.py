from __future__ import annotations

from football_poc.engine.common import *

def gate_events_by_match_state(
    events: Iterable[PredictedEvent],
    timeline: MatchStateTimeline,
) -> list[PredictedEvent]:
    return [
        event
        for event in events
        if timeline.allows_event(
            event.event_type,
            event.clip_seconds,
            event.completion_seconds,
        )
    ]

def evaluate_events(
    predictions: Iterable[PredictedEvent],
    ground_truth: list[dict[str, Any]],
    *,
    tolerance_seconds: float,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for event_type in ("pass", "shot"):
        predicted = [
            event
            for event in predictions
            if event.event_type == f"{event_type}_candidate"
        ]
        truth = [
            event
            for event in ground_truth
            if event.get("event_type") == event_type
        ]
        unmatched_truth = set(range(len(truth)))
        matches: list[dict[str, Any]] = []
        for event in sorted(predicted, key=lambda item: item.clip_seconds):
            candidates = [
                (
                    abs(event.clip_seconds - float(truth[index]["clip_seconds"])),
                    index,
                )
                for index in unmatched_truth
                if abs(
                    event.clip_seconds - float(truth[index]["clip_seconds"])
                )
                <= tolerance_seconds
            ]
            if not candidates:
                continue
            error, truth_index = min(candidates)
            unmatched_truth.remove(truth_index)
            matches.append(
                {
                    "predicted_seconds": event.clip_seconds,
                    "ground_truth_seconds": truth[truth_index]["clip_seconds"],
                    "absolute_error_seconds": round(error, 3),
                }
            )
        true_positives = len(matches)
        false_positives = len(predicted) - true_positives
        false_negatives = len(truth) - true_positives
        precision = (
            true_positives / len(predicted) if predicted else 0.0
        )
        recall = true_positives / len(truth) if truth else 0.0
        results[event_type] = {
            "predicted": len(predicted),
            "ground_truth": len(truth),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "matches": matches,
        }
    results["tolerance_seconds"] = tolerance_seconds
    results["limitations"] = [
        "Pass candidates combine observed ball flight with sender/receiver control.",
        "High passes are evaluated as passes because height is not calibrated.",
        "Shot candidates use manually calibrated normalized goal centers.",
    ]
    return results



def run(results_dir: Path, settings: MatchStateExportSettings = MatchStateExportSettings()) -> dict[str, Any]:
    match_state = read_stage_json(results_dir / "match-state-events.json")
    predicted = read_stage_json(results_dir / "predicted-events.json")
    return {
        "stage": "match_state_export",
        "match_state": match_state if settings.include_events else {},
        "event_count": len(predicted),
        "event_types": [event.get("event_type") for event in predicted],
    }
