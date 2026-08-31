from football_poc.possession import (
    PredictedEvent,
    PossessionObservation,
    build_possession_segments,
    collapse_transient_opponent_segments,
    evaluate_events,
    infer_flight_transfer_events,
    infer_deceleration_transfer_events,
    infer_shot_events,
    infer_transfer_events,
    infer_boundary_turnovers,
    filter_aerial_boundary_intervals,
    annotate_restart_releases,
    infer_restart_passes,
    infer_initial_possession_transfer,
    filter_ambiguous_startup_transfers,
    merge_transfer_events,
    merge_transfer_events,
    _control_observations,
    _smooth_teams,
)


def observation(
    seconds: float,
    team: str,
    player_id: int,
    player_x: float,
    ball_x: float,
    control_ratio: float = 0.5,
) -> PossessionObservation:
    return PossessionObservation(
        source_frame=round(seconds * 25),
        clip_seconds=seconds,
        team=team,
        player_track_id=player_id,
        player_x=player_x,
        player_y=100,
        player_height=50,
        ball_x=ball_x,
        ball_y=100,
        control_ratio=control_ratio,
    )


def test_same_team_control_transfer_creates_pass_candidate() -> None:
    observations = [
        observation(0.0, "blue", 1, 100, 100),
        observation(0.1, "blue", 1, 102, 102),
        observation(1.0, "blue", 2, 300, 300),
        observation(1.1, "blue", 2, 302, 302),
    ]
    segments = build_possession_segments(
        observations,
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0.75,
    )
    events = infer_transfer_events(
        segments,
        maximum_transfer_seconds=3,
        minimum_transfer_heights=1.5,
    )

    assert [event.event_type for event in events] == ["pass_candidate"]


def test_brief_opponent_proximity_between_same_team_control_is_collapsed() -> None:
    segments = build_possession_segments(
        [
            observation(8.0, "black", 1, 100, 100),
            observation(8.2, "black", 1, 102, 102),
            observation(9.2, "red", 2, 200, 200),
            observation(9.4, "red", 2, 202, 202),
            observation(10.6, "black", 3, 300, 300),
            observation(10.8, "black", 3, 302, 302),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    collapsed = collapse_transient_opponent_segments(
        segments, maximum_transient_seconds=1.2
    )

    assert [segment.team for segment in collapsed] == ["black", "black"]


def test_opponent_overlap_is_collapsed_when_owner_path_remains_plausible() -> None:
    segments = build_possession_segments(
        [
            observation(6.0, "black", 1, 100, 100),
            observation(7.0, "red", 2, 140, 140),
            observation(8.0, "red", 3, 180, 180),
            observation(9.4, "red", 4, 220, 220),
            observation(9.6, "black", 5, 250, 250),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    collapsed = collapse_transient_opponent_segments(
        segments,
        maximum_transient_seconds=1.2,
        maximum_occlusion_seconds=4.0,
        maximum_owner_speed_heights_per_second=3.0,
    )

    assert [segment.team for segment in collapsed] == ["black", "black"]


def test_real_opponent_possession_is_not_collapsed_across_implausible_path() -> None:
    segments = build_possession_segments(
        [
            observation(6.0, "black", 1, 100, 100),
            observation(7.0, "red", 2, 140, 140),
            observation(8.0, "red", 3, 180, 180),
            observation(9.4, "red", 4, 220, 220),
            observation(9.6, "black", 5, 900, 900),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    collapsed = collapse_transient_opponent_segments(
        segments,
        maximum_transient_seconds=1.2,
        maximum_occlusion_seconds=4.0,
        maximum_owner_speed_heights_per_second=3.0,
    )

    assert [segment.team for segment in collapsed] == [
        "black",
        "red",
        "red",
        "red",
        "black",
    ]


def test_owner_returning_against_prior_motion_does_not_hide_turnover() -> None:
    segments = build_possession_segments(
        [
            observation(5.8, "black", 1, 90, 90),
            observation(6.0, "black", 1, 100, 100),
            observation(7.0, "red", 2, 140, 140),
            observation(8.4, "red", 2, 180, 180),
            observation(9.2, "black", 3, 0, 100),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    collapsed = collapse_transient_opponent_segments(
        segments,
        maximum_transient_seconds=1.2,
        maximum_occlusion_seconds=4.0,
        maximum_owner_speed_heights_per_second=3.0,
        minimum_owner_direction_cosine=0.0,
    )

    assert [segment.team for segment in collapsed] == [
        "black",
        "red",
        "red",
        "black",
    ]


def test_alternating_nearby_tracks_are_not_merged_as_one_player() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "black", 1, 100, 100),
            observation(1.2, "black", 1, 102, 102),
            observation(1.4, "black", 2, 104, 104),
            observation(1.6, "black", 1, 106, 106),
            observation(1.8, "black", 2, 108, 108),
            observation(2.0, "black", 2, 110, 110),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0.75,
        co_visible_track_return_seconds=0.4,
    )

    assert [
        (segment.player_track_id, len(segment.observations))
        for segment in segments
    ] == [(1, 2), (2, 1), (1, 1), (2, 2)]


def test_opponent_control_transfer_creates_turnover() -> None:
    observations = [
        observation(0.0, "blue", 1, 100, 100),
        observation(0.1, "blue", 1, 102, 102),
        observation(1.0, "white", 2, 300, 300),
        observation(1.1, "white", 2, 302, 302),
    ]
    segments = build_possession_segments(
        observations,
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0.75,
    )
    events = infer_transfer_events(
        segments,
        maximum_transfer_seconds=3,
        minimum_transfer_heights=1.5,
    )

    assert [event.event_type for event in events] == ["turnover_candidate"]


def test_ball_flight_confirms_sender_and_receiver() -> None:
    segments = build_possession_segments(
        [
            observation(0.8, "blue", 1, 100, 100),
            observation(0.9, "blue", 1, 102, 102),
            observation(1.4, "blue", 2, 300, 300),
            observation(1.5, "blue", 2, 302, 302),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )
    balls = {
        1: [
            {
                "track_id": 1,
                "clip_seconds": 1.0,
                "x": 100,
                "y": 100,
            }
        ],
        2: [
            {
                "track_id": 1,
                "clip_seconds": 1.2,
                "x": 140,
                "y": 100,
            }
        ],
    }

    events = infer_flight_transfer_events(
        balls,
        segments,
        minimum_speed_pixels_per_second=60,
        maximum_step_seconds=0.24,
        debounce_seconds=1.2,
        sender_lookback_seconds=1,
        receiver_window_seconds=2,
    )

    assert [event.event_type for event in events] == ["pass_candidate"]
    assert events[0].from_player_track_id == 1
    assert events[0].to_player_track_id == 2


def test_ball_flight_ignores_single_frame_receiver() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "black", 1, 100, 100),
            observation(1.1, "black", 1, 105, 105),
            observation(2.0, "red", 2, 200, 200),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    balls = {
        1: [
            {
                "track_id": 1,
                "clip_seconds": 1.0,
                "x": 100,
                "y": 100,
            }
        ],
        2: [
            {
                "track_id": 1,
                "clip_seconds": 1.2,
                "x": 200,
                "y": 100,
            }
        ],
    }

    events = infer_flight_transfer_events(
        balls,
        segments,
        minimum_speed_pixels_per_second=100,
        maximum_step_seconds=0.24,
        debounce_seconds=1.2,
        sender_lookback_seconds=1,
        receiver_window_seconds=2,
        minimum_sender_observations=1,
        minimum_receiver_observations=2,
    )

    assert events == []


def test_sharp_deceleration_with_same_team_retention_completes_pass() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "black", 1, 100, 100),
            observation(1.2, "black", 1, 105, 105),
            observation(2.4, "black", 2, 220, 220),
            observation(2.6, "black", 2, 225, 225),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    balls = {
        1: [{"track_id": 1, "clip_seconds": 1.2, "x": 100, "y": 100}],
        2: [{"track_id": 1, "clip_seconds": 1.4, "x": 160, "y": 100}],
        3: [{"track_id": 1, "clip_seconds": 1.6, "x": 165, "y": 100}],
        4: [{"track_id": 1, "clip_seconds": 2.0, "x": 165, "y": 100}],
        5: [{"track_id": 1, "clip_seconds": 2.2, "x": 225, "y": 100}],
    }

    events = infer_deceleration_transfer_events(
        balls,
        segments,
        minimum_incoming_speed_pixels_per_second=60,
        maximum_outgoing_speed_ratio=0.35,
        sender_lookback_seconds=1,
        receiver_window_seconds=2,
        minimum_transfer_heights=0.5,
    )

    assert [(event.team, event.completion_seconds) for event in events] == [
        ("black", 1.4)
    ]


def test_high_speed_straight_flyby_does_not_assign_control() -> None:
    players = {
        2: [
            {
                "track_id": 7,
                "team": "black",
                "x1": 90,
                "x2": 110,
                "y1": 50,
                "y2": 100,
            }
        ]
    }
    balls = {
        1: [
            {
                "track_id": 1,
                "source_frame": 1,
                "clip_seconds": 0.0,
                "x": 0,
                "y": 100,
            }
        ],
        2: [
            {
                "track_id": 1,
                "source_frame": 2,
                "clip_seconds": 0.1,
                "x": 100,
                "y": 100,
            }
        ],
        3: [
            {
                "track_id": 1,
                "source_frame": 3,
                "clip_seconds": 0.2,
                "x": 200,
                "y": 100,
            }
        ],
    }

    observations = _control_observations(
        players,
        balls,
        control_radius_heights=1.8,
        maximum_flyby_speed_pixels_per_second=600,
    )

    assert observations == []


def test_high_speed_direction_change_remains_contact_candidate() -> None:
    players = {
        2: [
            {
                "track_id": 7,
                "team": "red",
                "x1": 90,
                "x2": 110,
                "y1": 50,
                "y2": 100,
            }
        ]
    }
    balls = {
        1: [
            {
                "track_id": 1,
                "source_frame": 1,
                "clip_seconds": 0.0,
                "x": 0,
                "y": 100,
            }
        ],
        2: [
            {
                "track_id": 1,
                "source_frame": 2,
                "clip_seconds": 0.1,
                "x": 100,
                "y": 100,
            }
        ],
        3: [
            {
                "track_id": 1,
                "source_frame": 3,
                "clip_seconds": 0.2,
                "x": 20,
                "y": 100,
            }
        ],
    }

    observations = _control_observations(
        players,
        balls,
        control_radius_heights=1.8,
        maximum_flyby_speed_pixels_per_second=600,
    )

    assert [observation.player_track_id for observation in observations] == [7]


def test_nearest_foot_wins_over_larger_distant_player() -> None:
    players = {
        1: [
            {
                "track_id": 1,
                "team": "red",
                "x1": 40,
                "x2": 60,
                "y1": 0,
                "y2": 100,
            },
            {
                "track_id": 2,
                "team": "black",
                "x1": 85,
                "x2": 95,
                "y1": 70,
                "y2": 100,
            },
        ]
    }
    balls = {
        1: [
            {
                "track_id": 1,
                "source_frame": 1,
                "clip_seconds": 0.0,
                "x": 100,
                "y": 100,
            }
        ]
    }

    observations = _control_observations(
        players,
        balls,
        control_radius_heights=1.8,
    )

    assert [item.player_track_id for item in observations] == [2]


def test_normalized_high_speed_straight_flyby_does_not_assign_control() -> None:
    players = {
        2: [
            {
                "track_id": 7,
                "team": "red",
                "x1": 90,
                "x2": 110,
                "y1": 75,
                "y2": 100,
            }
        ]
    }
    balls = {
        frame: [
            {
                "track_id": 1,
                "source_frame": frame,
                "clip_seconds": (frame - 1) * 0.1,
                "x": (frame - 1) * 15,
                "y": 100,
            }
        ]
        for frame in (1, 2, 3)
    }

    observations = _control_observations(
        players,
        balls,
        control_radius_heights=1.8,
        maximum_flyby_speed_pixels_per_second=500,
        maximum_flyby_speed_heights_per_second=4,
    )

    assert observations == []


def test_team_smoothing_never_reassigns_contact_to_another_timestamp() -> None:
    observations = [
        observation(1.0, "red", 1, 100, 100, control_ratio=1.2),
        observation(1.2, "black", 2, 105, 105, control_ratio=0.1),
        observation(1.4, "red", 3, 110, 110, control_ratio=1.2),
    ]

    smoothed = _smooth_teams(observations, 0.5)

    assert [(item.team, item.player_track_id) for item in smoothed] == [
        ("black", 2)
    ]


def test_elevated_overlap_requires_a_sharp_direction_change() -> None:
    players = {
        2: [
            {
                "track_id": 7,
                "team": "red",
                "x1": 90,
                "x2": 110,
                "y1": 50,
                "y2": 100,
            }
        ]
    }
    straight_balls = {
        frame: [
            {
                "track_id": 1,
                "source_frame": frame,
                "clip_seconds": (frame - 1) * 0.1,
                "x": 90 + frame * 5,
                "y": 70,
            }
        ]
        for frame in (1, 2, 3)
    }

    observations = _control_observations(
        players,
        straight_balls,
        control_radius_heights=1.8,
        maximum_ground_contact_height_ratio=0.4,
        maximum_aerial_contact_direction_cosine=0.5,
    )

    assert observations == []


def test_elevated_sharp_deflection_remains_a_contact_candidate() -> None:
    players = {
        2: [
            {
                "track_id": 7,
                "team": "red",
                "x1": 90,
                "x2": 110,
                "y1": 50,
                "y2": 100,
            }
        ]
    }
    deflected_balls = {
        1: [
            {
                "track_id": 1,
                "source_frame": 1,
                "clip_seconds": 0.0,
                "x": 80,
                "y": 70,
            }
        ],
        2: [
            {
                "track_id": 1,
                "source_frame": 2,
                "clip_seconds": 0.1,
                "x": 100,
                "y": 70,
            }
        ],
        3: [
            {
                "track_id": 1,
                "source_frame": 3,
                "clip_seconds": 0.2,
                "x": 90,
                "y": 80,
            }
        ],
    }

    observations = _control_observations(
        players,
        deflected_balls,
        control_radius_heights=1.8,
        maximum_ground_contact_height_ratio=0.4,
        maximum_aerial_contact_direction_cosine=0.5,
    )

    assert [item.player_track_id for item in observations] == [7]


def test_elevated_receiver_is_confirmed_by_later_ground_control() -> None:
    players = {
        1: [
            {
                "track_id": 6,
                "team": "black",
                "x1": -10,
                "x2": 10,
                "y1": 50,
                "y2": 100,
            }
        ],
        **{
        frame: [
            {
                "track_id": 7,
                "team": "black",
                "x1": 90,
                "x2": 110,
                "y1": 50,
                "y2": 100,
            }
        ]
        for frame in (2, 3, 4)
        },
    }
    balls = {
        1: [
            {
                "track_id": 1,
                "source_frame": 1,
                "clip_seconds": 0.0,
                "x": 0,
                "y": 95,
            }
        ],
        2: [
            {
                "track_id": 1,
                "source_frame": 2,
                "clip_seconds": 0.2,
                "x": 90,
                "y": 70,
            }
        ],
        3: [
            {
                "track_id": 1,
                "source_frame": 3,
                "clip_seconds": 0.4,
                "x": 95,
                "y": 80,
            }
        ],
        4: [
            {
                "track_id": 1,
                "source_frame": 4,
                "clip_seconds": 0.8,
                "x": 100,
                "y": 95,
            }
        ],
    }

    observations = _control_observations(
        players,
        balls,
        control_radius_heights=1.8,
        maximum_flyby_speed_pixels_per_second=300,
        maximum_ground_contact_height_ratio=0.4,
        maximum_aerial_contact_direction_cosine=0.5,
        future_control_confirmation_seconds=1.0,
    )

    assert [item.clip_seconds for item in observations] == [0.0, 0.2, 0.4, 0.8]


def test_sustained_boundary_exit_creates_turnover_for_prior_owner() -> None:
    segments = build_possession_segments(
        [
            observation(10.8, "black", 4, 100, 100),
            observation(11.0, "black", 4, 102, 102),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    events = infer_boundary_turnovers(
        [
            {
                "start_seconds": 12.0,
                "duration_seconds": 2.0,
                "starts_outside": False,
            }
        ],
        segments,
    )

    assert [event.event_type for event in events] == ["turnover_candidate"]
    assert events[0].team == "black"
    assert events[0].to_player_track_id is None


def test_long_clearance_to_touchline_uses_last_stable_owner() -> None:
    segments = build_possession_segments(
        [
            observation(18.6, "red", 4, 100, 100),
            observation(18.8, "red", 4, 102, 102),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    events = infer_boundary_turnovers(
        [
            {
                "start_seconds": 24.2,
                "duration_seconds": 4.8,
                "starts_outside": False,
            }
        ],
        segments,
        ownership_lookback_seconds=6.0,
    )

    assert [(event.team, event.event_type) for event in events] == [
        ("red", "turnover_candidate")
    ]


def test_aerial_projection_crossing_keeps_continuous_same_team_possession() -> None:
    segments = build_possession_segments(
        [
            observation(36.6, "black", 4, 100, 100),
            observation(36.8, "black", 4, 102, 102),
            observation(40.0, "black", 8, 300, 300),
            observation(40.2, "black", 8, 302, 302),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    intervals = [
        {
            "start_seconds": 37.04,
            "end_seconds": 38.96,
            "resumed_seconds": 39.0,
        }
    ]

    assert filter_aerial_boundary_intervals(intervals, segments) == []


def test_boundary_exit_with_possession_gap_remains_candidate() -> None:
    segments = build_possession_segments(
        [
            observation(42.4, "black", 4, 100, 100),
            observation(42.6, "black", 4, 102, 102),
            observation(44.6, "black", 8, 300, 300),
            observation(44.8, "black", 8, 302, 302),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    interval = {
        "start_seconds": 43.72,
        "end_seconds": 44.56,
        "resumed_seconds": 44.6,
    }

    assert filter_aerial_boundary_intervals([interval], segments) == [interval]


def test_long_stoppage_is_not_treated_as_aerial_crossing() -> None:
    segments = build_possession_segments(
        [
            observation(51.4, "black", 4, 100, 100),
            observation(51.6, "black", 4, 102, 102),
            observation(58.0, "black", 8, 300, 300),
            observation(58.2, "black", 8, 302, 302),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    interval = {
        "start_seconds": 51.8,
        "end_seconds": 56.8,
        "resumed_seconds": 56.88,
    }

    assert filter_aerial_boundary_intervals([interval], segments) == [interval]


def test_restart_requires_credible_ball_release_speed() -> None:
    interval = {
        "start_seconds": 43.7,
        "resumed_seconds": 44.6,
    }
    slow_ball = {
        1: [{"clip_seconds": 44.6, "x": 100, "y": 100}],
        2: [{"clip_seconds": 44.8, "x": 120, "y": 100}],
    }
    fast_ball = {
        1: [{"clip_seconds": 44.6, "x": 100, "y": 100}],
        2: [{"clip_seconds": 44.8, "x": 160, "y": 100}],
    }

    assert annotate_restart_releases(
        [interval], slow_ball, minimum_speed_pixels_per_second=200
    )[0]["play_resumed_seconds"] is None
    assert annotate_restart_releases(
        [interval], fast_ball, minimum_speed_pixels_per_second=200
    )[0]["play_resumed_seconds"] == 44.6


def test_boundary_exit_does_not_duplicate_nearby_confirmed_turnover() -> None:
    segments = build_possession_segments(
        [
            observation(3.0, "red", 4, 100, 100),
            observation(3.2, "red", 4, 102, 102),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    prior = PredictedEvent(
        "turnover_candidate", 5.0, "red", 4, 7, 0.8, "receiver control"
    )

    events = infer_boundary_turnovers(
        [
            {
                "start_seconds": 3.6,
                "duration_seconds": 1.2,
                "starts_outside": False,
            }
        ],
        segments,
        prior_events=[prior],
    )

    assert events == []


def test_restart_reception_is_reported_separately_from_measured_passes() -> None:
    segments = build_possession_segments(
        [
            observation(11.6, "black", 4, 100, 100),
            observation(11.8, "black", 4, 102, 102),
            observation(21.4, "red", 8, 300, 300),
            observation(21.6, "red", 8, 302, 302),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    events = infer_restart_passes(
        [
            {
                "start_seconds": 12.28,
                "resumed_seconds": 14.84,
                "starts_outside": False,
            }
        ],
        segments,
    )

    assert [event.event_type for event in events] == ["restart_pass_candidate"]
    assert events[0].team == "red"
    assert events[0].completion_seconds == 21.4


def test_restart_uses_ball_deceleration_as_first_touch() -> None:
    segments = build_possession_segments(
        [
            observation(18.6, "red", 4, 100, 100),
            observation(18.8, "red", 4, 102, 102),
            observation(32.4, "black", 8, 300, 300),
            observation(32.6, "black", 8, 302, 302),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    balls = {
        1: [{"clip_seconds": 30.6, "x": 100, "y": 100}],
        2: [{"clip_seconds": 30.8, "x": 220, "y": 100}],
        3: [{"clip_seconds": 31.0, "x": 240, "y": 100}],
    }

    events = infer_restart_passes(
        [
            {
                "start_seconds": 24.2,
                "duration_seconds": 4.8,
                "play_resumed_seconds": 29.2,
                "starts_outside": False,
            }
        ],
        segments,
        ownership_lookback_seconds=6,
        balls=balls,
    )

    assert events[0].team == "black"
    assert events[0].completion_seconds == 30.8


def test_inherited_chunk_possession_detects_first_opponent_touch() -> None:
    segments = build_possession_segments(
        [
            observation(1.8, "red", 8, 100, 100),
            observation(2.0, "red", 8, 102, 102),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    event = infer_initial_possession_transfer("black", segments)

    assert event is not None
    assert event.event_type == "turnover_candidate"
    assert event.team == "black"
    assert event.completion_seconds == 1.8


def test_inherited_chunk_possession_does_not_invent_same_team_event() -> None:
    segments = build_possession_segments(
        [
            observation(1.8, "black", 8, 100, 100),
            observation(2.0, "black", 8, 102, 102),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    assert infer_initial_possession_transfer("black", segments) is None


def test_transfer_merge_deduplicates_the_same_reception() -> None:
    flight = PredictedEvent(
        "pass_candidate", 35.0, "black", 29, 178, 0.8, "flight", 35.2
    )
    segment = PredictedEvent(
        "pass_candidate", 33.8, "black", 29, 178, 0.75, "segment", 35.2
    )

    assert merge_transfer_events(
        [flight], [segment], deduplication_seconds=0.8
    ) == [flight]


def test_startup_guard_rejects_weak_receiver_proximity() -> None:
    weak = PredictedEvent(
        "pass_candidate", 1.4, "black", 33, 21, 0.57, "weak", 2.6
    )
    strong = PredictedEvent(
        "pass_candidate", 5.8, "black", 21, 46, 0.65, "strong", 6.0
    )
    observations = [
        observation(2.6, "black", 21, 100, 170, control_ratio=1.4),
        observation(6.0, "black", 46, 100, 110, control_ratio=0.2),
    ]

    filtered = filter_ambiguous_startup_transfers(
        [weak, strong],
        observations,
        startup_guard_seconds=4.0,
        maximum_receiver_control_ratio=1.2,
    )

    assert filtered == [strong]


def test_primary_transfer_suppresses_nearby_fallback() -> None:
    primary = PredictedEvent(
        "pass_candidate", 1.0, "blue", 1, 2, 0.8, "flight"
    )
    nearby = PredictedEvent(
        "pass_candidate", 1.5, "blue", 1, 2, 0.7, "segment"
    )
    later = PredictedEvent(
        "pass_candidate", 3.0, "blue", 2, 3, 0.7, "segment"
    )

    merged = merge_transfer_events(
        [primary],
        [nearby, later],
        deduplication_seconds=0.8,
    )

    assert [event.clip_seconds for event in merged] == [1.0, 3.0]


def test_evaluation_matches_each_ground_truth_once() -> None:
    segments = [
        build_possession_segments(
            [
                observation(0.0, "blue", 1, 100, 100),
                observation(0.1, "blue", 1, 102, 102),
                observation(1.0, "blue", 2, 300, 300),
                observation(1.1, "blue", 2, 302, 302),
            ],
            segment_gap_seconds=0.5,
            identity_switch_radius_heights=0.75,
        )
    ][0]
    predictions = infer_transfer_events(
        segments,
        maximum_transfer_seconds=3,
        minimum_transfer_heights=1.5,
    )
    result = evaluate_events(
        predictions,
        [{"event_type": "pass", "clip_seconds": 0.2}],
        tolerance_seconds=0.2,
    )

    assert result["pass"]["true_positives"] == 1
    assert result["pass"]["precision"] == 1.0


def test_reacquiring_same_track_is_not_a_pass() -> None:
    segments = [
        build_possession_segments(
            [
                observation(0.0, "blue", 1, 100, 100),
                observation(0.1, "blue", 1, 102, 102),
                observation(1.0, "blue", 1, 300, 300),
                observation(1.1, "blue", 1, 302, 302),
            ],
            segment_gap_seconds=0.5,
            identity_switch_radius_heights=0.75,
        )
    ][0]

    assert (
        infer_transfer_events(
            segments,
            maximum_transfer_seconds=3,
            minimum_transfer_heights=1.5,
        )
        == []
    )


def test_fast_ball_toward_right_goal_creates_shot() -> None:
    balls = {
        1: [
            {
                "track_id": 1,
                "clip_seconds": 1.0,
                "x": 2800,
                "y": 300,
            }
        ],
        2: [
            {
                "track_id": 1,
                "clip_seconds": 1.5,
                "x": 3000,
                "y": 300,
            }
        ],
    }

    events = infer_shot_events(
        balls,
        [],
        width=4096,
        height=1080,
        minimum_speed_pixels_per_second=200,
        minimum_goal_cosine=0.92,
    )

    assert [event.event_type for event in events] == ["shot_candidate"]


def test_recent_confirmed_transfer_assigns_shot_team() -> None:
    balls = {
        1: [
            {
                "track_id": 1,
                "clip_seconds": 2.0,
                "x": 2800,
                "y": 300,
            }
        ],
        2: [
            {
                "track_id": 1,
                "clip_seconds": 2.5,
                "x": 3000,
                "y": 300,
            }
        ],
    }
    noisy_owner = build_possession_segments(
        [
            observation(2.0, "white", 9, 2800, 2800),
            observation(2.1, "white", 9, 2820, 2820),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0.75,
    )
    prior_pass = PredictedEvent(
        event_type="pass_candidate",
        clip_seconds=1.5,
        team="blue",
        from_player_track_id=1,
        to_player_track_id=2,
        confidence=0.8,
        details="confirmed blue transfer",
    )

    events = infer_shot_events(
        balls,
        noisy_owner,
        width=4096,
        height=1080,
        minimum_speed_pixels_per_second=200,
        minimum_goal_cosine=0.92,
        prior_events=[prior_pass],
    )

    assert events[0].team == "blue"
    assert events[0].from_player_track_id == 2


def test_quick_receiver_control_vetoes_shot() -> None:
    balls = {
        1: [
            {
                "track_id": 1,
                "clip_seconds": 1.0,
                "x": 2800,
                "y": 300,
            }
        ],
        2: [
            {
                "track_id": 1,
                "clip_seconds": 1.5,
                "x": 3000,
                "y": 300,
            }
        ],
    }
    receiver = build_possession_segments(
        [
            observation(1.6, "blue", 2, 3000, 3000),
            observation(1.7, "blue", 2, 3002, 3002),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0.75,
    )

    assert (
        infer_shot_events(
            balls,
            receiver,
            width=4096,
            height=1080,
            minimum_speed_pixels_per_second=200,
            minimum_goal_cosine=0.92,
        )
        == []
    )


def test_interpolated_motion_does_not_create_shot() -> None:
    balls = {
        1: [
            {
                "track_id": 1,
                "clip_seconds": 1.0,
                "x": 2800,
                "y": 300,
                "interpolated": True,
            }
        ],
        2: [
            {
                "track_id": 1,
                "clip_seconds": 1.5,
                "x": 3000,
                "y": 300,
                "interpolated": False,
            }
        ],
    }

    assert (
        infer_shot_events(
            balls,
            [],
            width=4096,
            height=1080,
            minimum_speed_pixels_per_second=200,
            minimum_goal_cosine=0.92,
        )
        == []
    )
