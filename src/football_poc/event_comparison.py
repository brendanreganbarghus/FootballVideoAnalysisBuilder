from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import Any, Iterable


def compare_manual_events(
    manual_events: Iterable[dict[str, Any]],
    predicted_events: Iterable[dict[str, Any]],
    *,
    tolerance_seconds: float = 1.0,
    review_tolerance_seconds: float = 3.0,
    include_shots_on_target: bool = False,
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
                "comparison_type": _prediction_type(
                    str(event["event_type"]), include_shots_on_target
                ),
                "comparison_seconds": float(
                    event.get("completion_seconds")
                    if event.get("completion_seconds") is not None
                    else event["clip_seconds"]
                ),
            }
            for event in predicted_events
            if _prediction_type(
                str(event.get("event_type")), include_shots_on_target
            )
            is not None
        ),
        key=lambda event: event["comparison_seconds"],
    )
    matched_indexes = _optimal_event_matches(
        manual,
        predicted,
        tolerance_seconds,
    )
    matched_manual_indexes = {manual_index for manual_index, _ in matched_indexes}
    matched_prediction_indexes = {
        prediction_index for _, prediction_index in matched_indexes
    }
    matches = [
        _event_match(manual[manual_index], predicted[prediction_index])
        for manual_index, prediction_index in matched_indexes
    ]
    unmatched_manual = [
        truth
        for index, truth in enumerate(manual)
        if index not in matched_manual_indexes
    ]
    unmatched_predictions = [
        index
        for index in range(len(predicted))
        if index not in matched_prediction_indexes
    ]

    unmatched_predicted = [predicted[index] for index in sorted(unmatched_predictions)]
    review_predictions = [predicted[index] for index in unmatched_predictions]
    review_indexes = _optimal_event_matches(
        unmatched_manual,
        review_predictions,
        review_tolerance_seconds,
    )
    review_matches = [
        _event_match(
            unmatched_manual[manual_index],
            review_predictions[prediction_index],
        )
        for manual_index, prediction_index in review_indexes
    ]
    review_manual_indexes = {manual_index for manual_index, _ in review_indexes}
    unresolved_manual = [
        truth
        for index, truth in enumerate(unmatched_manual)
        if index not in review_manual_indexes
    ]
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
    event_types = _event_types(include_shots_on_target)
    return {
        "tolerance_seconds": tolerance_seconds,
        "review_tolerance_seconds": review_tolerance_seconds,
        "manual_event_count": len(manual),
        "predicted_event_count": len(predicted),
        "matched_event_count": len(matches),
        "additional_review_match_count": len(review_matches),
        "manual_counts": _expand_counts(manual_counts, event_types),
        "predicted_counts": _expand_counts(predicted_counts, event_types),
        "matched_counts": _expand_counts(match_counts, event_types),
        "matches": matches,
        "unmatched_manual": unmatched_manual,
        "unmatched_predicted": unmatched_predicted,
        "review_matches": review_matches,
        "unresolved_manual_after_review": unresolved_manual,
        "nearby_disagreements": nearby_disagreements,
    }


def _event_match(
    manual: dict[str, Any],
    prediction: dict[str, Any],
) -> dict[str, Any]:
    return {
        "manual": manual,
        "prediction": prediction,
        "difference_seconds": round(
            prediction["comparison_seconds"] - float(manual["clip_seconds"]),
            3,
        ),
    }


def _optimal_event_matches(
    manual: list[dict[str, Any]],
    predicted: list[dict[str, Any]],
    tolerance_seconds: float,
) -> tuple[tuple[int, int], ...]:
    @lru_cache(maxsize=None)
    def align(
        manual_index: int,
        prediction_index: int,
    ) -> tuple[int, float, tuple[tuple[int, int], ...]]:
        if manual_index == len(manual) or prediction_index == len(predicted):
            return 0, 0.0, ()

        options = [
            align(manual_index + 1, prediction_index),
            align(manual_index, prediction_index + 1),
        ]
        truth = manual[manual_index]
        prediction = predicted[prediction_index]
        difference = abs(
            prediction["comparison_seconds"] - float(truth["clip_seconds"])
        )
        if (
            prediction["comparison_type"] == truth["event_type"]
            and prediction.get("team") == truth.get("team")
            and difference <= tolerance_seconds
        ):
            count, total_difference, pairs = align(
                manual_index + 1,
                prediction_index + 1,
            )
            options.append(
                (
                    count + 1,
                    total_difference + difference,
                    ((manual_index, prediction_index), *pairs),
                )
            )

        return min(
            options,
            key=lambda candidate: (
                -candidate[0],
                candidate[1],
                candidate[2],
            ),
        )

    return align(0, 0)[2]


def _prediction_type(
    event_type: str,
    include_shots_on_target: bool = False,
) -> str | None:
    if include_shots_on_target and event_type == "shot_on_target":
        return "shot_on_target"
    return {
        "pass_candidate": "completed_pass",
        "restart_pass_candidate": "completed_pass",
        "turnover_candidate": "turnover",
    }.get(event_type)


def _event_types(include_shots_on_target: bool) -> tuple[str, ...]:
    return (
        ("completed_pass", "turnover", "shot_on_target")
        if include_shots_on_target
        else ("completed_pass", "turnover")
    )


def _expand_counts(
    counts: Counter[tuple[str, str]],
    event_types: tuple[str, ...] = ("completed_pass", "turnover"),
) -> dict[str, dict[str, int]]:
    return {
        team: {
            event_type: counts.get((team, event_type), 0)
            for event_type in event_types
        }
        for team in ("red", "black")
    }
