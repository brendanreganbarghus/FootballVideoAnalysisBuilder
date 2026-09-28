from football_poc.match_state import (
    MATCH_LAW_PROFILE,
    RESTART_LAW_REFERENCES,
    LawReference,
    MatchPlayState,
    RestartType,
    build_match_state_timeline,
    coalesce_stoppage_candidates,
    detect_stationary_ball_restarts,
    partition_continuous_flight_candidates,
    partition_fragmented_boundary_candidates,
)


def test_boundary_exit_moves_through_restart_states() -> None:
    timeline = build_match_state_timeline(
        [
            {
                "start_seconds": 10.0,
                "resumed_seconds": 12.0,
                "play_resumed_seconds": 14.0,
                "starts_outside": False,
            }
        ],
        duration_seconds=20.0,
    )

    assert [
        (transition.clip_seconds, transition.state)
        for transition in timeline.transitions
    ] == [
        (10.0, MatchPlayState.OUT_OF_PLAY),
        (12.0, MatchPlayState.RESTART_PENDING),
        (14.0, MatchPlayState.IN_PLAY),
    ]
    assert timeline.state_at(9.9) == MatchPlayState.IN_PLAY
    assert timeline.state_at(10.0) == MatchPlayState.OUT_OF_PLAY
    assert timeline.state_at(12.0) == MatchPlayState.RESTART_PENDING
    assert timeline.state_at(14.0) == MatchPlayState.IN_PLAY


def test_unreleased_restart_remains_pending() -> None:
    timeline = build_match_state_timeline(
        [
            {
                "start_seconds": 4.0,
                "resumed_seconds": 6.0,
                "play_resumed_seconds": None,
                "starts_outside": False,
            }
        ],
        duration_seconds=10.0,
    )

    assert timeline.state_at(5.0) == MatchPlayState.OUT_OF_PLAY
    assert timeline.state_at(8.0) == MatchPlayState.RESTART_PENDING


def test_clip_opening_outside_stays_unknown_until_detected_release() -> None:
    timeline = build_match_state_timeline(
        [
            {
                "start_seconds": 0.0,
                "resumed_seconds": 2.0,
                "play_resumed_seconds": 3.0,
                "starts_outside": True,
            }
        ],
        duration_seconds=10.0,
    )

    assert timeline.state_at(1.0) == MatchPlayState.UNKNOWN
    assert timeline.state_at(3.0) == MatchPlayState.IN_PLAY
    assert not timeline.allows_event("pass_candidate", 1.0, 2.0)


def test_late_ball_tracking_outside_disables_processing_until_release() -> None:
    timeline = build_match_state_timeline(
        [
            {
                "start_seconds": 2.0,
                "resumed_seconds": 3.0,
                "play_resumed_seconds": 4.0,
                "starts_outside": True,
            }
        ],
        duration_seconds=10.0,
    )

    assert timeline.state_at(1.0) == MatchPlayState.IN_PLAY
    assert timeline.state_at(2.0) == MatchPlayState.UNKNOWN
    assert timeline.state_at(4.0) == MatchPlayState.IN_PLAY


def test_state_policy_gates_regular_events_but_preserves_restart_events() -> None:
    timeline = build_match_state_timeline(
        [
            {
                "start_seconds": 10.0,
                "resumed_seconds": 12.0,
                "play_resumed_seconds": 14.0,
                "starts_outside": False,
            }
        ],
        duration_seconds=20.0,
    )

    assert not timeline.allows_event("pass_candidate", 11.0, 11.5)
    assert not timeline.allows_event("turnover_candidate", 13.0, 13.0)
    assert timeline.allows_event("turnover_candidate", 10.0, 10.0)
    assert timeline.allows_event("restart_pass_candidate", 12.0, 14.5)
    assert timeline.allows_event("pass_candidate", 15.0, 16.0)


def test_state_report_keeps_rejected_boundary_evidence_separate() -> None:
    timeline = build_match_state_timeline([], duration_seconds=20.0)
    rejected = [{"start_seconds": 4.0, "reason": "aerial_continuation"}]

    report = timeline.to_dict(rejected_boundary_candidates=rejected)

    assert report["schema_version"] == 2
    assert report["law_profile"]["profile_id"] == (
        "ifab-laws-latest-observable-v1"
    )
    assert report["initial_state"] == "in_play"
    assert report["intervals"] == [
        {"state": "in_play", "start_seconds": 0.0, "end_seconds": 20.0}
    ]
    assert report["rejected_boundary_candidates"] == rejected


def test_law_profile_separates_match_laws_from_analytics_definitions() -> None:
    assert MATCH_LAW_PROFILE.reviewed_at == "2026-09-06"
    assert any(
        "the-ball-in-and-out-of-play" in source
        for source in MATCH_LAW_PROFILE.sources
    )
    assert "Completed passes" in MATCH_LAW_PROFILE.analytics_definition
    assert set(RESTART_LAW_REFERENCES) == set(RestartType)


def test_observed_foul_stops_events_until_free_kick_release() -> None:
    timeline = build_match_state_timeline(
        [
            {
                "law_event": "offence",
                "start_seconds": 4.0,
                "advantage_applied": False,
                "play_resumed_seconds": 8.0,
                "restart_type": "direct_free_kick",
            }
        ],
        duration_seconds=12.0,
    )

    assert timeline.state_at(4.0) == MatchPlayState.RESTART_PENDING
    assert not timeline.allows_event("turnover_candidate", 5.0, 5.2)
    assert timeline.state_at(8.0) == MatchPlayState.IN_PLAY
    assert timeline.transitions[0].law_reference == (
        LawReference.REFEREE_AND_ADVANTAGE
    )
    assert timeline.transitions[1].restart_type == RestartType.DIRECT_FREE_KICK


def test_advantage_keeps_the_ball_in_play() -> None:
    timeline = build_match_state_timeline(
        [
            {
                "law_event": "offence",
                "start_seconds": 4.0,
                "advantage_applied": True,
            }
        ],
        duration_seconds=12.0,
    )

    assert timeline.transitions == ()
    assert timeline.state_at(6.0) == MatchPlayState.IN_PLAY
    assert timeline.allows_event("pass_candidate", 5.0, 6.0)


def test_uncertain_offence_suppresses_events_until_play_continues() -> None:
    timeline = build_match_state_timeline(
        [
            {
                "law_event": "offence",
                "start_seconds": 4.0,
                "competitive_play_continued_seconds": 5.0,
            }
        ],
        duration_seconds=12.0,
    )

    assert timeline.state_at(4.5) == MatchPlayState.POSSIBLE_STOPPAGE
    assert not timeline.allows_event("pass_candidate", 4.2, 4.8)
    assert timeline.state_at(5.0) == MatchPlayState.IN_PLAY


def test_goal_and_other_referee_stoppages_use_law_restart_families() -> None:
    goal = build_match_state_timeline(
        [
            {
                "law_event": "goal",
                "start_seconds": 3.0,
                "play_resumed_seconds": 7.0,
            }
        ],
        duration_seconds=10.0,
    )
    dropped_ball = build_match_state_timeline(
        [
            {
                "law_event": "other_referee_stoppage",
                "start_seconds": 2.0,
                "play_resumed_seconds": 6.0,
            }
        ],
        duration_seconds=10.0,
    )

    assert goal.transitions[0].restart_type == RestartType.KICK_OFF
    assert dropped_ball.transitions[0].restart_type == RestartType.DROPPED_BALL
    assert goal.state_at(5.0) == MatchPlayState.RESTART_PENDING
    assert dropped_ball.state_at(4.0) == MatchPlayState.RESTART_PENDING


def test_period_end_permanently_suppresses_later_events() -> None:
    timeline = build_match_state_timeline(
        [{"law_event": "period_end", "start_seconds": 8.0}],
        duration_seconds=10.0,
    )

    assert timeline.state_at(9.0) == MatchPlayState.PERIOD_ENDED
    assert not timeline.allows_event("shot_candidate", 8.5, 9.0)


def test_continuous_directional_flight_is_not_a_boundary_stoppage() -> None:
    points = [
        {
            "clip_seconds": index * 0.2,
            "x": index * 40,
            "y": 100 - index * 10,
            "interpolated": False,
        }
        for index in range(13)
    ]
    interval = {
        "start_seconds": 0.4,
        "end_seconds": 2.8,
        "duration_seconds": 2.4,
        "minimum_signed_distance_px": -120.0,
        "resumed_seconds": 3.0,
    }

    accepted, rejected = partition_continuous_flight_candidates(
        [interval], points
    )

    assert accepted == []
    assert rejected[0]["reason"] == "continuous_flight"


def test_slow_outside_ball_remains_a_stoppage_candidate() -> None:
    points = [
        {
            "clip_seconds": index * 0.2,
            "x": 100 + index,
            "y": 100,
            "interpolated": False,
        }
        for index in range(13)
    ]
    interval = {
        "start_seconds": 0.4,
        "end_seconds": 2.8,
        "duration_seconds": 2.4,
        "minimum_signed_distance_px": -120.0,
        "resumed_seconds": 3.0,
    }

    accepted, rejected = partition_continuous_flight_candidates(
        [interval], points
    )

    assert accepted == [interval]
    assert rejected == []


def test_fragmented_boundary_candidates_form_one_stoppage() -> None:
    intervals = [
        {
            "start_frame": 10,
            "end_frame": 20,
            "start_seconds": 1.0,
            "end_seconds": 2.0,
            "duration_seconds": 1.0,
            "minimum_signed_distance_px": -20.0,
            "resumed_seconds": 2.1,
            "starts_outside": False,
        },
        {
            "start_frame": 24,
            "end_frame": 40,
            "start_seconds": 2.4,
            "end_seconds": 4.0,
            "duration_seconds": 1.6,
            "minimum_signed_distance_px": -30.0,
            "resumed_seconds": 4.1,
            "starts_outside": False,
        },
    ]

    merged = coalesce_stoppage_candidates(intervals)

    assert len(merged) == 1
    assert merged[0]["start_seconds"] == 1.0
    assert merged[0]["end_seconds"] == 4.0
    assert merged[0]["resumed_seconds"] == 4.1
    assert merged[0]["coalesced_candidate_count"] == 2


def test_fragmented_shallow_boundary_with_interior_control_is_rejected() -> None:
    accepted, rejected = partition_fragmented_boundary_candidates(
        [
            {
                "start_seconds": 6.0,
                "end_seconds": 18.0,
                "resumed_seconds": 18.1,
                "minimum_signed_distance_px": -35.0,
                "coalesced_candidate_count": 6,
            }
        ],
        [{"start_seconds": 11.0, "end_seconds": 12.0}],
    )

    assert accepted == []
    assert rejected[0]["reason"] == "competitive_possession_inside_boundary"


def test_stationary_ball_and_player_reaction_confirm_free_kick_restart() -> None:
    ball_points = [
        {
            "clip_seconds": seconds,
            "x": x,
            "y": 100.0,
            "interpolated": False,
        }
        for seconds, x in [
            (0.0, 90.0),
            (0.2, 102.0),
            (0.4, 102.0),
            (0.6, 102.0),
            (0.8, 110.0),
            (1.0, 120.0),
            (1.2, 125.0),
            (1.4, 225.0),
            (1.6, 275.0),
            (1.8, 325.0),
        ]
    ]
    player_points = []
    for track_id in range(1, 7):
        for index, seconds in enumerate(
            [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8]
        ):
            setup_x = 90.0 + track_id * 5
            reaction_offset = max(0, index - 5) * 15
            center_x = setup_x + reaction_offset
            player_points.append(
                {
                    "track_id": track_id,
                    "team": "black",
                    "clip_seconds": seconds,
                    "x1": center_x - 5,
                    "x2": center_x + 5,
                    "y1": 80.0,
                    "y2": 120.0,
                }
            )

    candidates = detect_stationary_ball_restarts(
        ball_points,
        player_points,
        minimum_release_speed_pixels_per_second=300.0,
    )

    assert len(candidates) == 1
    assert candidates[0]["start_seconds"] == 0.2
    assert candidates[0]["play_resumed_seconds"] == 1.2
    assert candidates[0]["restart_type"] == "free_kick"
    timeline = build_match_state_timeline(candidates, duration_seconds=2.0)
    assert timeline.state_at(0.5) == MatchPlayState.RESTART_PENDING
    assert timeline.state_at(1.2) == MatchPlayState.IN_PLAY


def test_stationary_ball_without_player_reaction_is_not_a_restart() -> None:
    ball_points = [
        {
            "clip_seconds": seconds,
            "x": x,
            "y": 100.0,
            "interpolated": False,
        }
        for seconds, x in [
            (0.0, 100.0),
            (0.2, 100.0),
            (0.4, 100.0),
            (0.6, 100.0),
            (0.8, 100.0),
            (1.0, 200.0),
            (1.2, 250.0),
        ]
    ]
    player_points = [
        {
            "track_id": track_id,
            "team": "black",
            "clip_seconds": seconds,
            "x1": 80.0 + track_id,
            "x2": 90.0 + track_id,
            "y1": 80.0,
            "y2": 120.0,
        }
        for track_id in range(1, 5)
        for seconds in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2]
    ]

    assert detect_stationary_ball_restarts(ball_points, player_points) == []
