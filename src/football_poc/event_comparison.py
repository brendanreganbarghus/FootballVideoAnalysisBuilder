from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


def compare_manual_events(
    manual_events: Iterable[dict[str, Any]],
    predicted_events: Iterable[dict[str, Any]],
    *,
    tolerance_seconds: float = 1.0,
    review_tolerance_seconds: float = 3.0,
) -> dict[str, Any]:
    if tolerance_seconds < 0 or review_tolerance_seconds < tolerance_seconds:
        raise ValueError(
            "Comparison tolerances must be non-negative and review tolerance "
            "must not be smaller than strict tolerance"
        )
    manual = sorted(manual_events, key=lambda event: float(event["clip_seconds"]))
    predicted = sorted(
        (
            {
                **event,
                "comparison_type": _prediction_type(str(event["event_type"])),
                "comparison_seconds": float(
                    event.get("completion_seconds")
                    if event.get("completion_seconds") is not None
                    else event["clip_seconds"]
                ),
            }
            for event in predicted_events
            if _prediction_type(str(event.get("event_type"))) is not None
        ),
        key=lambda event: event["comparison_seconds"],
    )
    unmatched_predictions = set(range(len(predicted)))
    matches: list[dict[str, Any]] = []
    unmatched_manual: list[dict[str, Any]] = []
    for truth in manual:
        candidates = [
            index
            for index in unmatched_predictions
            if predicted[index]["comparison_type"] == truth["event_type"]
            and predicted[index].get("team") == truth.get("team")
            and abs(
                predicted[index]["comparison_seconds"]
                - float(truth["clip_seconds"])
            )
            <= tolerance_seconds
        ]
        if not candidates:
            unmatched_manual.append(truth)
            continue
        index = min(
            candidates,
            key=lambda candidate: abs(
                predicted[candidate]["comparison_seconds"]
                - float(truth["clip_seconds"])
            ),
        )
        prediction = predicted[index]
        unmatched_predictions.remove(index)
        matches.append(
            {
                "manual": truth,
                "prediction": prediction,
                "difference_seconds": round(
                    prediction["comparison_seconds"]
                    - float(truth["clip_seconds"]),
                    3,
                ),
            }
        )

    unmatched_predicted = [predicted[index] for index in sorted(unmatched_predictions)]
    review_matches: list[dict[str, Any]] = []
    unresolved_manual: list[dict[str, Any]] = []
    review_prediction_indexes = set(unmatched_predictions)
    for truth in unmatched_manual:
        candidates = [
            index
            for index in review_prediction_indexes
            if predicted[index]["comparison_type"] == truth["event_type"]
            and predicted[index].get("team") == truth.get("team")
            and abs(
                predicted[index]["comparison_seconds"]
                - float(truth["clip_seconds"])
            )
            <= review_tolerance_seconds
        ]
        if not candidates:
            unresolved_manual.append(truth)
            continue
        index = min(
            candidates,
            key=lambda candidate: abs(
                predicted[candidate]["comparison_seconds"]
                - float(truth["clip_seconds"])
            ),
        )
        review_prediction_indexes.remove(index)
        review_matches.append(
            {
                "manual": truth,
                "prediction": predicted[index],
                "difference_seconds": round(
                    predicted[index]["comparison_seconds"]
                    - float(truth["clip_seconds"]),
                    3,
                ),
            }
        )
    nearby_disagreements = []
    for truth in unmatched_manual:
        nearby = min(
            predicted,
            key=lambda event: abs(
                event["comparison_seconds"] - float(truth["clip_seconds"])
            ),
            default=None,
        )
        if (
            nearby
            and abs(nearby["comparison_seconds"] - float(truth["clip_seconds"]))
            <= tolerance_seconds
        ):
            nearby_disagreements.append(
                {
                    "manual": truth,
                    "nearby_prediction": nearby,
                    "difference_seconds": round(
                        nearby["comparison_seconds"]
                        - float(truth["clip_seconds"]),
                        3,
                    ),
                }
            )

    manual_counts = Counter(
        (str(event["team"]), str(event["event_type"])) for event in manual
    )
    predicted_counts = Counter(
        (str(event.get("team")), str(event["comparison_type"]))
        for event in predicted
    )
    match_counts = Counter(
        (
            str(match["manual"]["team"]),
            str(match["manual"]["event_type"]),
        )
        for match in matches
    )
    return {
        "tolerance_seconds": tolerance_seconds,
        "review_tolerance_seconds": review_tolerance_seconds,
        "manual_event_count": len(manual),
        "predicted_event_count": len(predicted),
        "matched_event_count": len(matches),
        "additional_review_match_count": len(review_matches),
        "manual_counts": _expand_counts(manual_counts),
        "predicted_counts": _expand_counts(predicted_counts),
        "matched_counts": _expand_counts(match_counts),
        "matches": matches,
        "unmatched_manual": unmatched_manual,
        "unmatched_predicted": unmatched_predicted,
        "review_matches": review_matches,
        "unresolved_manual_after_review": unresolved_manual,
        "nearby_disagreements": nearby_disagreements,
    }


def _prediction_type(event_type: str) -> str | None:
    return {
        "pass_candidate": "completed_pass",
        "restart_pass_candidate": "completed_pass",
        "turnover_candidate": "turnover",
    }.get(event_type)


def _expand_counts(counts: Counter[tuple[str, str]]) -> dict[str, dict[str, int]]:
    return {
        team: {
            event_type: counts.get((team, event_type), 0)
            for event_type in ("completed_pass", "turnover")
        }
        for team in ("red", "black")
    }
