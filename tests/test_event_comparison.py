from football_poc.event_comparison import compare_manual_events


def test_comparison_uses_completion_time_and_team() -> None:
    manual = [
        {"clip_seconds": 5.1, "team": "red", "event_type": "completed_pass"},
        {"clip_seconds": 8.0, "team": "black", "event_type": "turnover"},
    ]
    predicted = [
        {
            "clip_seconds": 3.0,
            "completion_seconds": 5.0,
            "team": "red",
            "event_type": "pass_candidate",
        },
        {
            "clip_seconds": 7.9,
            "completion_seconds": 8.1,
            "team": "red",
            "event_type": "turnover_candidate",
        },
    ]

    report = compare_manual_events(manual, predicted, tolerance_seconds=0.25)

    assert report["matched_event_count"] == 1
    assert report["matches"][0]["prediction"]["comparison_seconds"] == 5.0
    assert len(report["unmatched_manual"]) == 1


def test_comparison_reports_likely_review_match_separately() -> None:
    manual = [
        {"clip_seconds": 11.7, "team": "black", "event_type": "completed_pass"}
    ]
    predicted = [
        {
            "clip_seconds": 8.6,
            "completion_seconds": 9.6,
            "team": "black",
            "event_type": "pass_candidate",
        }
    ]

    report = compare_manual_events(manual, predicted)

    assert report["matched_event_count"] == 0
    assert report["additional_review_match_count"] == 1
    assert report["review_matches"][0]["difference_seconds"] == -2.1


def test_restart_pass_counts_as_completed_pass() -> None:
    report = compare_manual_events(
        [
            {
                "clip_seconds": 32.4,
                "team": "black",
                "event_type": "completed_pass",
            }
        ],
        [
            {
                "clip_seconds": 29.2,
                "completion_seconds": 32.4,
                "team": "black",
                "event_type": "restart_pass_candidate",
            }
        ],
    )

    assert report["matched_event_count"] == 1


def test_comparison_maximizes_chronological_matches_before_time_proximity() -> None:
    manual = [
        {"clip_seconds": 21.76, "team": "black", "event_type": "completed_pass"},
        {"clip_seconds": 22.66, "team": "black", "event_type": "completed_pass"},
    ]
    predicted = [
        {
            "clip_seconds": 20.6,
            "completion_seconds": 20.8,
            "team": "black",
            "event_type": "pass_candidate",
        },
        {
            "clip_seconds": 22.2,
            "completion_seconds": 22.6,
            "team": "black",
            "event_type": "pass_candidate",
        },
    ]

    report = compare_manual_events(manual, predicted, tolerance_seconds=1.0)

    assert report["matched_event_count"] == 2
    assert report["unmatched_manual"] == []
    assert report["unmatched_predicted"] == []
    assert [
        match["prediction"]["comparison_seconds"] for match in report["matches"]
    ] == [20.8, 22.6]
