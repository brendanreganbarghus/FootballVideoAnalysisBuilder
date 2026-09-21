from football_poc.innovation_day_snapshot.possession import (
    PredictedEvent,
    PossessionObservation,
    PossessionSegment,
    build_possession_segments,
    collapse_transient_opponent_segments,
    evaluate_events,
    infer_flight_transfer_events,
    include_supported_single_touch_senders,
    infer_direction_change_transfer_events,
    reconcile_one_touch_team_transfers,
    reconcile_intervening_opponent_aerial_contacts,
    reconcile_track_identity_team_switches,
    infer_deferred_contested_turnovers,
    propagate_deferred_possession_chains,
    reconcile_delayed_turnover_chains,
    reconcile_deflected_turnover_sequences,
    reconcile_unconfirmed_turnovers,
    refine_delayed_turnovers_to_contested_decelerations,
    refine_weak_reception_completion_times,
    refine_one_touch_acceleration_receptions,
    refine_receptions_to_sharp_contacts,
    retain_stable_possession_segments,
    infer_short_exchange_receptions,
    infer_pre_release_flight_receptions,
    infer_post_turnover_first_pass,
    infer_opening_live_reception,
    infer_sparse_control_transfer,
    split_acceleration_confirmed_one_touch_passes,
    infer_terminal_brief_reception,
    infer_delayed_first_flight_reception,
    infer_short_controlled_teammate_transfers,
    reconcile_brief_opponent_turnover_pairs,
    split_sharp_direction_change_passes,
    collapse_competing_same_sender_receptions,
    suppress_duplicate_track_handoff_passes,
    suppress_noncausal_nonreturn_passes,
    infer_pass_sender_established_turnovers,
    infer_ball_reentry_receptions,
    infer_unobserved_chain_contacts,
    suppress_redundant_retained_possession_links,
    suppress_passes_crossing_opponent_control,
    suppress_transient_proximity_receptions,
    suppress_overlapping_opponent_handoffs,
    suppress_uncontrolled_opponent_turnovers,
    filter_disconnected_low_confidence_startup,
    infer_unresolved_direction_change_receptions,
    infer_occluded_exchange_receptions,
    infer_deceleration_transfer_events,
    infer_shot_events,
    infer_transfer_events,
    infer_event_established_turnovers,
    infer_boundary_turnovers,
    filter_aerial_boundary_intervals,
    annotate_restart_releases,
    extend_restarts_through_ball_setup,
    infer_restart_passes,
    infer_initial_possession_transfer,
    filter_ambiguous_startup_transfers,
    merge_transfer_events,
    merge_transfer_events,
    _control_observations,
    _deduplicate_receptions,
    _event_released_outside,
    _smooth_teams,
)
from football_poc.innovation_day_snapshot.match_state import (
    build_match_state_timeline,
)


def test_deflection_delays_turnover_until_opponent_control() -> None:
    events = [
        PredictedEvent(
            "turnover_candidate",
            23.8,
            "red",
            109,
            109,
            0.6,
            "A linked possession chain ended at a contested direction-changing contact.",
            23.8,
        ),
        PredictedEvent(
            "pass_candidate",
            24.0,
            "red",
            109,
            None,
            0.6,
            "The incoming pass completed before the linked contested turnover.",
            24.4,
        ),
        PredictedEvent(
            "pass_candidate",
            24.0,
            "black",
            109,
            124,
            0.74,
            "Ball direction changed sharply as same-team control transferred.",
            25.4,
        ),
    ]
    segments = build_possession_segments(
        [
            observation(25.4, "black", 124, 100, 100, control_ratio=0.05),
            observation(25.6, "black", 124, 102, 102, control_ratio=0.17),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    reconciled = reconcile_deflected_turnover_sequences(events, segments)

    assert [(event.team, event.event_type) for event in reconciled] == [
        ("red", "pass_candidate"),
        ("red", "turnover_candidate"),
    ]
    assert reconciled[1].completion_seconds == 25.4
    assert reconciled[1].to_player_track_id == 124


def test_delayed_turnover_does_not_rewrite_conflicting_intermediary_pass(
    monkeypatch,
) -> None:
    intermediary = PredictedEvent(
        "pass_candidate", 2.0, "red", 10, 91, 0.7, "pass", 2.2
    )
    turnover = PredictedEvent(
        "turnover_candidate", 3.4, "red", 91, 115, 0.7, "turnover", 4.0
    )
    players = {
        50: [
            {
                "track_id": 10,
                "clip_seconds": 2.0,
                "team": "black",
                "color_scores": {"dark": 0.8},
            }
        ],
        55: [
            {
                "track_id": 91,
                "clip_seconds": 2.2,
                "team": "red",
                "color_scores": {"white": 0.4, "warm": 0.4},
            }
        ],
    }
    balls = {
        50: [
            {
                "track_id": 1,
                "source_frame": 50,
                "clip_seconds": 2.0,
                "x": 100,
                "y": 100,
            }
        ]
    }
    monkeypatch.setattr(
        "football_poc.innovation_day_snapshot.possession."
        "_ball_motion_evidence",
        lambda _: {(1, 50): (100.0, -1.0)},
    )
    monkeypatch.setattr(
        "football_poc.innovation_day_snapshot.possession._nearby_ball_teams",
        lambda *args, **kwargs: {"black"},
    )

    reconciled = reconcile_delayed_turnover_chains(
        [intermediary, turnover],
        players,
        balls,
        minimum_speed_pixels_per_second=45,
    )

    assert reconciled == [intermediary, turnover]


def test_turnover_is_suppressed_when_only_current_team_contacts_ball() -> None:
    event = PredictedEvent(
        "turnover_candidate", 1.0, "black", 75, 212, 0.67, "flight", 2.0
    )
    players = {
        50: [
            {
                "track_id": 205,
                "team": "black",
                "x1": 95,
                "y1": 80,
                "x2": 105,
                "y2": 105,
                "color_scores": {"dark": 0.6, "white": 0.0},
            },
            {
                "track_id": 212,
                "team": "red",
                "x1": 130,
                "y1": 80,
                "x2": 140,
                "y2": 105,
                "color_scores": {"dark": 0.0, "white": 0.6},
            },
        ]
    }
    balls = {
        50: [
            {
                "track_id": 1,
                "source_frame": 50,
                "clip_seconds": 2.0,
                "x": 102,
                "y": 100,
            }
        ]
    }

    following = PredictedEvent(
        "pass_candidate", 3.0, "red", 212, 216, 0.6, "flight", 3.2
    )

    corrected = suppress_uncontrolled_opponent_turnovers(
        [event, following], players, balls
    )

    assert len(corrected) == 1
    assert corrected[0].event_type == "pass_candidate"
    assert corrected[0].team == "black"


def test_jersey_corrected_turnover_survives_stale_possession_team() -> None:
    event = PredictedEvent(
        "turnover_candidate",
        1.0,
        "black",
        10,
        20,
        0.8,
        "Frame-level jersey evidence corrected a cross-team player-track "
        "identity switch.",
        1.4,
    )
    segments = build_possession_segments(
        [
            observation(1.4, "black", 20, 100, 100),
            observation(1.6, "black", 20, 102, 102),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0.75,
    )

    corrected = suppress_uncontrolled_opponent_turnovers(
        [event],
        {},
        {},
        segments,
    )

    assert corrected == [event]


def observation(
    seconds: float,
    team: str,
    player_id: int,
    player_x: float,
    ball_x: float,
    control_ratio: float = 0.5,
    *,
    player_y: float = 100,
    ball_y: float = 100,
    player_height: float = 50,
) -> PossessionObservation:
    return PossessionObservation(
        source_frame=round(seconds * 25),
        clip_seconds=seconds,
        team=team,
        player_track_id=player_id,
        player_x=player_x,
        player_y=player_y,
        player_height=player_height,
        ball_x=ball_x,
        ball_y=ball_y,
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


def test_same_team_transfer_requires_control_at_release_and_reception() -> None:
    observations = [
        observation(0.0, "red", 1, 100, 100, control_ratio=0.3),
        observation(0.2, "red", 1, 102, 102, control_ratio=1.0),
        observation(1.2, "red", 2, 300, 300, control_ratio=0.3),
        observation(1.4, "red", 2, 302, 302, control_ratio=0.3),
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

    assert events == []


def test_sustained_same_team_transfer_uses_controlled_touch_boundaries() -> None:
    observations = [
        observation(1.0, "black", 1, 100, 100, control_ratio=0.2),
        observation(1.2, "black", 1, 102, 102, control_ratio=0.3),
        observation(1.4, "black", 1, 108, 108, control_ratio=0.9),
        observation(1.6, "black", 1, 116, 116, control_ratio=1.2),
        observation(2.0, "black", 2, 250, 250, control_ratio=0.7),
        observation(2.2, "black", 2, 252, 252, control_ratio=0.2),
        observation(2.4, "black", 2, 254, 254, control_ratio=0.3),
    ]
    segments = build_possession_segments(
        observations,
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0.75,
    )

    events = infer_transfer_events(
        segments,
        maximum_transfer_seconds=3,
        minimum_transfer_heights=1.5,
    )

    assert len(events) == 1
    assert events[0].event_type == "pass_candidate"
    assert events[0].team == "black"
    assert events[0].clip_seconds == 1.2
    assert events[0].completion_seconds == 2.2


def test_co_visible_players_are_not_merged_as_continuous_dribble() -> None:
    segments = build_possession_segments(
        [
            observation(0.0, "black", 115, 100, 100, control_ratio=0.2),
            observation(0.2, "black", 115, 110, 110, control_ratio=0.2),
            observation(0.4, "black", 49, 125, 120, control_ratio=0.2),
            observation(0.6, "black", 49, 140, 130, control_ratio=0.2),
        ],
        segment_gap_seconds=0.64,
        identity_switch_radius_heights=0.75,
        co_visible_track_pairs={frozenset((49, 115))},
    )

    assert [segment.player_track_id for segment in segments] == [115, 49]


def test_smooth_same_team_owner_switch_remains_one_dribble() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "black", 1, 100, 100),
            observation(1.2, "black", 1, 110, 110),
            observation(1.4, "black", 2, 150, 150),
            observation(1.6, "black", 3, 190, 190),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    assert len(segments) == 1


def test_direction_change_still_creates_new_possession_segment() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "black", 1, 100, 100),
            observation(1.2, "black", 1, 110, 110),
            observation(1.4, "black", 2, 100, 100),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    assert [segment.player_track_id for segment in segments] == [1, 2]


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


def test_coherent_opponent_control_survives_brief_owner_classification_blip() -> None:
    segments = build_possession_segments(
        [
            observation(14.8, "black", 1, 100, 100),
            observation(15.0, "black", 1, 102, 102),
            observation(16.6, "red", 2, 200, 200, 0.5),
            observation(16.8, "red", 2, 202, 202, 0.1),
            observation(17.0, "red", 2, 204, 204, 0.4),
            observation(17.2, "red", 2, 206, 206, 0.3),
            observation(17.4, "black", 3, 208, 208, 0.2),
            observation(17.6, "red", 2, 210, 210, 0.3),
            observation(17.8, "red", 4, 212, 212, 0.5),
            observation(18.0, "red", 4, 214, 214, 0.5),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    collapsed = collapse_transient_opponent_segments(
        segments,
        maximum_transient_seconds=1.2,
    )

    assert [segment.team for segment in collapsed] == ["black", "red", "red"]
    assert collapsed[1].start_seconds == 16.6
    assert collapsed[1].end_seconds == 17.6


def test_three_observation_opponent_control_is_not_collapsed() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "black", 1, 100, 100, control_ratio=0.4),
            observation(1.2, "black", 1, 101, 100, control_ratio=0.4),
            observation(1.4, "red", 2, 102, 100, control_ratio=0.45),
            observation(1.6, "red", 2, 103, 100, control_ratio=0.7),
            observation(1.8, "red", 2, 104, 100, control_ratio=0.7),
            observation(2.0, "black", 3, 105, 100, control_ratio=0.2),
            observation(2.2, "black", 3, 106, 100, control_ratio=0.2),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )

    collapsed = collapse_transient_opponent_segments(
        segments,
        maximum_transient_seconds=1.2,
    )

    assert [segment.team for segment in collapsed] == [
        "black",
        "red",
        "black",
    ]


def test_transient_opponent_does_not_split_same_owner_dribble() -> None:
    segments = build_possession_segments(
        [
            observation(8.0, "black", 1, 100, 100),
            observation(8.2, "black", 1, 110, 110),
            observation(8.4, "red", 2, 120, 120),
            observation(8.6, "black", 1, 130, 130),
            observation(8.8, "black", 1, 140, 140),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    collapsed = collapse_transient_opponent_segments(
        segments,
        maximum_transient_seconds=1.2,
    )

    assert len(collapsed) == 1
    assert len(collapsed[0].observations) == 4


def test_single_opponent_control_is_kept_before_a_long_return_gap() -> None:
    segments = build_possession_segments(
        [
            observation(40.8, "black", 100, 100, 100),
            observation(44.2, "red", 182, 240, 100),
            observation(46.4, "black", 187, 340, 100),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    collapsed = collapse_transient_opponent_segments(
        segments,
        maximum_transient_seconds=1.2,
    )

    assert [segment.team for segment in collapsed] == [
        "black",
        "red",
        "black",
    ]


def test_short_opponent_control_is_kept_when_owner_returns_after_long_gap() -> None:
    segments = build_possession_segments(
        [
            observation(3.8, "red", 1, 100, 100),
            observation(5.0, "black", 2, 160, 100),
            observation(5.2, "black", 3, 180, 100),
            observation(5.4, "black", 3, 190, 100),
            observation(6.0, "black", 2, 220, 100),
            observation(11.8, "red", 4, 300, 100),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )

    collapsed = collapse_transient_opponent_segments(
        segments,
        maximum_transient_seconds=1.2,
        maximum_occlusion_seconds=4.0,
    )

    assert [segment.team for segment in collapsed] == [
        "red",
        "black",
        "black",
        "black",
        "red",
    ]


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


def test_opponent_transfer_requires_control_on_both_sides() -> None:
    observations = [
        observation(0.0, "red", 1, 100, 100, control_ratio=0.3),
        observation(0.2, "red", 1, 102, 102, control_ratio=1.1),
        observation(1.2, "black", 2, 300, 300, control_ratio=1.2),
        observation(1.4, "black", 2, 302, 302, control_ratio=0.3),
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

    assert events == []


def test_sustained_sender_uses_its_single_controlled_touch_for_turnover() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "red", 1, 100, 100, control_ratio=0.45),
            observation(1.2, "red", 1, 105, 100, control_ratio=0.7),
            observation(1.4, "red", 1, 110, 100, control_ratio=0.7),
            observation(1.6, "black", 2, 200, 200, control_ratio=0.2),
            observation(1.8, "black", 2, 205, 205, control_ratio=0.2),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )

    events = infer_transfer_events(
        segments,
        maximum_transfer_seconds=3,
        minimum_transfer_heights=0.5,
    )

    assert [
        (event.event_type, event.team, event.clip_seconds, event.completion_seconds)
        for event in events
    ] == [("turnover_candidate", "red", 1.0, 1.6)]


def test_sustained_opponent_transfer_uses_last_and_first_controlled_touches() -> None:
    observations = [
        observation(1.0, "black", 1, 100, 100, control_ratio=0.2),
        observation(1.2, "black", 1, 102, 102, control_ratio=0.3),
        observation(1.4, "black", 1, 108, 108, control_ratio=0.9),
        observation(1.6, "black", 1, 116, 116, control_ratio=1.2),
        observation(2.8, "red", 2, 250, 250, control_ratio=0.7),
        observation(3.0, "red", 2, 252, 252, control_ratio=0.2),
        observation(3.2, "red", 2, 254, 254, control_ratio=0.3),
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

    assert len(events) == 1
    assert events[0].event_type == "turnover_candidate"
    assert events[0].team == "black"
    assert events[0].clip_seconds == 1.2
    assert events[0].completion_seconds == 3.0


def test_completed_pass_receiver_remains_owner_until_opponent_control() -> None:
    completed_pass = PredictedEvent(
        "pass_candidate",
        1.0,
        "black",
        10,
        20,
        0.8,
        "Supported high-speed reception.",
        1.4,
    )
    segments = build_possession_segments(
        [
            observation(1.4, "black", 20, 100, 100, control_ratio=1.1),
            observation(1.6, "black", 20, 105, 100, control_ratio=1.4),
            observation(2.6, "red", 30, 180, 100, control_ratio=1.2),
            observation(2.8, "red", 30, 185, 100, control_ratio=0.3),
            observation(3.0, "red", 30, 190, 100, control_ratio=0.7),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )

    events = infer_event_established_turnovers(
        [completed_pass],
        segments,
        maximum_transfer_seconds=3.0,
    )

    assert [
        (
            event.event_type,
            event.team,
            event.from_player_track_id,
            event.to_player_track_id,
            event.clip_seconds,
            event.completion_seconds,
        )
        for event in events
    ] == [
        ("pass_candidate", "black", 10, 20, 1.0, 1.4),
        ("turnover_candidate", "black", 20, 30, 1.6, 2.8),
    ]


def test_uncontrolled_same_team_bridge_does_not_replace_established_owner() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "black", 1, 100, 100, control_ratio=0.2),
            observation(1.2, "black", 1, 105, 105, control_ratio=0.2),
            observation(1.4, "black", 1, 110, 110, control_ratio=0.3),
            observation(2.0, "black", 2, 180, 180, control_ratio=1.2),
            observation(2.2, "black", 2, 190, 190, control_ratio=1.3),
            observation(2.4, "black", 2, 200, 200, control_ratio=1.4),
            observation(3.0, "red", 3, 300, 300, control_ratio=0.2),
            observation(3.2, "red", 3, 305, 305, control_ratio=0.3),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )

    events = infer_transfer_events(
        segments,
        maximum_transfer_seconds=3,
        minimum_transfer_heights=0.5,
    )

    assert [
        (
            event.event_type,
            event.team,
            event.from_player_track_id,
            event.to_player_track_id,
            event.clip_seconds,
            event.completion_seconds,
        )
        for event in events
    ] == [("turnover_candidate", "black", 1, 3, 1.4, 3.0)]


def test_sustained_opponent_control_creates_turnover_without_ball_travel() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "black", 1, 100, 100),
            observation(1.2, "black", 1, 101, 100),
            observation(1.8, "red", 2, 102, 100),
            observation(2.0, "red", 2, 103, 100),
            observation(2.2, "red", 2, 104, 100),
            observation(2.4, "red", 2, 105, 100),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )

    events = infer_transfer_events(
        segments,
        maximum_transfer_seconds=1.0,
        minimum_transfer_heights=1.5,
    )

    assert [(event.event_type, event.team) for event in events] == [
        ("turnover_candidate", "black")
    ]


def test_single_observation_owner_return_does_not_erase_opponent_control() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "red", 1, 100, 100),
            observation(1.2, "red", 1, 101, 100),
            observation(1.4, "black", 2, 102, 100, control_ratio=0.4),
            observation(1.6, "black", 2, 103, 100, control_ratio=0.3),
            observation(1.8, "black", 2, 104, 100, control_ratio=0.3),
            observation(2.0, "black", 2, 105, 100, control_ratio=0.4),
            observation(2.2, "red", 3, 106, 100),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )

    collapsed = collapse_transient_opponent_segments(
        segments,
        maximum_transient_seconds=0.1,
        maximum_occlusion_seconds=2.0,
    )

    assert [segment.team for segment in collapsed] == [
        "red",
        "black",
        "red",
    ]


def test_returning_opponent_track_preserves_control_through_owner_blip() -> None:
    segments = build_possession_segments(
        [
            observation(54.8, "red", 210, 1196, 800, control_ratio=0.2),
            observation(55.0, "black", 219, 1214, 780, control_ratio=0.7),
            observation(55.2, "black", 219, 1218, 804, control_ratio=0.1),
            observation(55.4, "red", 210, 1202, 818, control_ratio=0.2),
            observation(55.8, "black", 306, 1206, 814, control_ratio=0.4),
            observation(56.0, "black", 306, 1200, 812, control_ratio=0.3),
            observation(56.2, "black", 219, 1238, 808, control_ratio=0.9),
            observation(56.4, "black", 219, 1250, 805, control_ratio=1.1),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
        co_visible_track_pairs={frozenset((219, 306))},
    )

    collapsed = collapse_transient_opponent_segments(
        segments,
        maximum_transient_seconds=1.2,
    )

    assert [
        (segment.team, segment.player_track_id)
        for segment in collapsed
    ] == [
        ("red", 210),
        ("black", 219),
        ("black", 306),
        ("black", 219),
    ]


def test_returning_receiver_confirms_short_control_turnover() -> None:
    segments = [
        PossessionSegment(
            "red",
            210,
            [observation(54.8, "red", 210, 1196, 800, control_ratio=0.2)],
        ),
        PossessionSegment(
            "black",
            219,
            [
                observation(55.0, "black", 219, 1214, 780, control_ratio=0.7),
                observation(55.2, "black", 219, 1218, 804, control_ratio=0.1),
            ],
        ),
        PossessionSegment(
            "black",
            306,
            [
                observation(55.8, "black", 306, 1206, 814, control_ratio=0.4),
                observation(56.0, "black", 306, 1200, 812, control_ratio=0.3),
            ],
        ),
        PossessionSegment(
            "black",
            219,
            [
                observation(56.2, "black", 219, 1238, 808, control_ratio=0.9),
                observation(56.4, "black", 219, 1250, 805, control_ratio=1.1),
            ],
        ),
    ]

    events = infer_transfer_events(
        segments,
        maximum_transfer_seconds=3,
        minimum_transfer_heights=1.5,
        control_observations=[
            observation(54.8, "red", 210, 1196, 800, control_ratio=0.2),
        ],
    )

    assert [
        (event.event_type, event.team, event.completion_seconds)
        for event in events
    ] == [("turnover_candidate", "red", 55.2)]


def test_sharp_ball_direction_change_confirms_same_team_reception() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "black", 1, 100, 100),
            observation(1.2, "black", 1, 90, 90),
            observation(1.4, "black", 2, 100, 100),
            observation(1.6, "black", 2, 110, 110),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    balls = {
        25: [{"track_id": 1, "clip_seconds": 1.0, "x": 100, "y": 100}],
        30: [{"track_id": 1, "clip_seconds": 1.2, "x": 90, "y": 100}],
        35: [{"track_id": 1, "clip_seconds": 1.4, "x": 100, "y": 100}],
    }

    events = infer_direction_change_transfer_events(
        balls,
        segments,
        maximum_transfer_seconds=1,
        minimum_speed_pixels_per_second=40,
    )

    assert len(events) == 1
    assert events[0].completion_seconds == 1.4


def test_direction_change_transfer_requires_controlled_sender_release() -> None:
    segments = build_possession_segments(
        [
            observation(
                1.0, "red", 1, 100, 100, control_ratio=0.3
            ),
            observation(
                1.2, "red", 1, 90, 90, control_ratio=1.0
            ),
            observation(
                1.4, "red", 2, 100, 100, control_ratio=0.3
            ),
            observation(
                1.6, "red", 2, 110, 110, control_ratio=0.3
            ),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    balls = {
        25: [{"track_id": 1, "clip_seconds": 1.0, "x": 100, "y": 100}],
        30: [{"track_id": 1, "clip_seconds": 1.2, "x": 90, "y": 100}],
        35: [{"track_id": 1, "clip_seconds": 1.4, "x": 100, "y": 100}],
    }

    events = infer_direction_change_transfer_events(
        balls,
        segments,
        maximum_transfer_seconds=1,
        minimum_speed_pixels_per_second=40,
    )

    assert events == []


def test_direction_change_pass_does_not_cross_intervening_opponent_control() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "red", 1, 100, 100, control_ratio=0.3),
            observation(1.2, "red", 1, 90, 90, control_ratio=0.3),
            observation(1.8, "red", 2, 100, 100, control_ratio=0.3),
            observation(2.0, "red", 2, 110, 110, control_ratio=0.3),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    balls = {
        25: [{"track_id": 1, "clip_seconds": 1.0, "x": 100, "y": 100}],
        30: [{"track_id": 1, "clip_seconds": 1.2, "x": 90, "y": 100}],
        35: [{"track_id": 1, "clip_seconds": 1.4, "x": 100, "y": 100}],
    }

    events = infer_direction_change_transfer_events(
        balls,
        segments,
        control_observations=[
            observation(1.4, "black", 3, 100, 100, control_ratio=0.3)
        ],
        maximum_transfer_seconds=1,
        minimum_speed_pixels_per_second=40,
    )

    assert events == []


def test_all_pass_inference_rejects_corroborated_intervening_opponent_control() -> None:
    event = PredictedEvent(
        "pass_candidate",
        1.2,
        "red",
        1,
        2,
        0.8,
        "same-team transfer",
        2.0,
    )
    controls = [
        observation(1.6, "black", 3, 200, 200, control_ratio=0.7),
        observation(1.8, "black", 3, 205, 205, control_ratio=0.3),
    ]

    assert suppress_passes_crossing_opponent_control([event], controls) == []


def test_isolated_opponent_proximity_does_not_erase_completed_pass() -> None:
    event = PredictedEvent(
        "pass_candidate",
        1.2,
        "red",
        1,
        2,
        0.8,
        "same-team transfer",
        2.0,
    )
    controls = [
        observation(1.8, "black", 3, 205, 205, control_ratio=0.3),
    ]

    assert suppress_passes_crossing_opponent_control([event], controls) == [
        event
    ]


def test_ball_reentry_recovers_one_touch_reception_after_tracking_gap() -> None:
    outgoing = PredictedEvent(
        "pass_candidate", 13.8, "black", 40, 42, 0.9, "following pass", 15.0
    )
    balls = {
        115: [
            {
                "track_id": 1,
                "source_frame": 115,
                "clip_seconds": 4.6,
                "x": 10,
                "y": 100,
            }
        ],
        295: [
            {
                "track_id": 1,
                "source_frame": 295,
                "clip_seconds": 11.8,
                "x": 40,
                "y": 100,
            }
        ],
        300: [
            {
                "track_id": 1,
                "source_frame": 300,
                "clip_seconds": 12.0,
                "x": 90,
                "y": 100,
            }
        ],
        305: [
            {
                "track_id": 1,
                "source_frame": 305,
                "clip_seconds": 12.2,
                "x": 150,
                "y": 100,
            }
        ],
    }

    events = infer_ball_reentry_receptions(
        [outgoing],
        [
            observation(3.8, "black", 32, 20, 20),
            observation(12.0, "black", 42, 100, 90, 0.2),
        ],
        balls,
        minimum_speed_pixels_per_second=40,
    )

    assert [(event.team, event.completion_seconds) for event in events] == [
        ("black", 12.0),
        ("black", 15.0),
    ]
    assert events[0].from_player_track_id == 32
    assert events[0].to_player_track_id == 42


def test_one_touch_contact_corrects_conflicting_outgoing_team() -> None:
    prior = PredictedEvent(
        "restart_pass_candidate", 1.0, "black", None, 8, 0.55, "restart", 1.4
    )
    outgoing = PredictedEvent(
        "pass_candidate", 2.0, "red", 9, 10, 0.7, "flight", 3.0
    )
    following = PredictedEvent(
        "turnover_candidate", 3.4, "red", 10, 12, 0.7, "turnover", 4.0
    )
    balls = {
        45: [{"track_id": 4, "source_frame": 45, "clip_seconds": 1.8, "x": 100, "y": 100}],
        50: [{"track_id": 4, "source_frame": 50, "clip_seconds": 2.0, "x": 110, "y": 100}],
        55: [{"track_id": 4, "source_frame": 55, "clip_seconds": 2.2, "x": 80, "y": 100}],
    }

    events = reconcile_one_touch_team_transfers(
        [prior, outgoing, following],
        [
            observation(2.0, "black", 11, 110, 110),
            observation(4.0, "black", 12, 200, 200),
        ],
        balls,
        minimum_speed_pixels_per_second=40,
        maximum_prior_reception_seconds=2,
    )

    assert [(event.team, event.completion_seconds) for event in events] == [
        ("black", 1.4),
        ("black", 2.0),
        ("black", 3.0),
        ("black", 4.0),
    ]
    assert events[-1].event_type == "pass_candidate"


def test_opponent_aerial_header_splits_apparent_same_team_pass() -> None:
    apparent_pass = PredictedEvent(
        "pass_candidate",
        5.2,
        "black",
        100,
        187,
        0.68,
        "Apparent same-team aerial transfer.",
        5.6,
    )
    balls = {
        80: [
            {
                "track_id": 1,
                "source_frame": 80,
                "clip_seconds": 3.2,
                "x": 100,
                "y": 100,
            }
        ],
        85: [
            {
                "track_id": 1,
                "source_frame": 85,
                "clip_seconds": 3.4,
                "x": 150,
                "y": 130,
            }
        ],
        90: [
            {
                "track_id": 1,
                "source_frame": 90,
                "clip_seconds": 3.6,
                "x": 120,
                "y": 110,
            }
        ],
    }
    events = reconcile_intervening_opponent_aerial_contacts(
        [apparent_pass],
        [
            observation(0.0, "black", 100, 0, 0),
            observation(3.4, "red", 182, 150, 150, control_ratio=0.9),
            observation(5.6, "black", 187, 240, 240),
        ],
        balls,
        minimum_speed_pixels_per_second=60,
    )

    assert [
        (
            event.event_type,
            event.team,
            event.from_player_track_id,
            event.to_player_track_id,
            event.completion_seconds,
        )
        for event in events
    ] == [
        ("turnover_candidate", "black", 100, 182, 3.4),
        ("turnover_candidate", "red", 182, 187, 5.6),
    ]


def test_sustained_opponent_control_is_not_treated_as_aerial_interception() -> None:
    apparent_pass = PredictedEvent(
        "pass_candidate",
        5.2,
        "black",
        100,
        187,
        0.68,
        "Apparent same-team aerial transfer.",
        5.6,
    )
    balls = {
        80: [
            {
                "track_id": 1,
                "source_frame": 80,
                "clip_seconds": 3.2,
                "x": 100,
                "y": 100,
            }
        ],
        85: [
            {
                "track_id": 1,
                "source_frame": 85,
                "clip_seconds": 3.4,
                "x": 150,
                "y": 130,
            }
        ],
        90: [
            {
                "track_id": 1,
                "source_frame": 90,
                "clip_seconds": 3.6,
                "x": 120,
                "y": 110,
            }
        ],
    }

    events = reconcile_intervening_opponent_aerial_contacts(
        [apparent_pass],
        [
            observation(0.0, "black", 100, 0, 0),
            observation(3.2, "red", 182, 145, 145, control_ratio=0.8),
            observation(3.4, "red", 182, 150, 150, control_ratio=0.9),
            observation(5.6, "black", 187, 240, 240),
        ],
        balls,
        minimum_speed_pixels_per_second=60,
    )

    assert events == [apparent_pass]


def test_single_weak_contact_and_immediate_return_does_not_create_turnovers() -> None:
    apparent_pass = PredictedEvent(
        "pass_candidate",
        3.2,
        "black",
        100,
        187,
        0.68,
        "Apparent same-team aerial transfer.",
        3.6,
    )
    balls = {
        80: [
            {
                "track_id": 1,
                "source_frame": 80,
                "clip_seconds": 3.2,
                "x": 100,
                "y": 100,
            }
        ],
        85: [
            {
                "track_id": 1,
                "source_frame": 85,
                "clip_seconds": 3.4,
                "x": 150,
                "y": 130,
            }
        ],
        90: [
            {
                "track_id": 1,
                "source_frame": 90,
                "clip_seconds": 3.6,
                "x": 120,
                "y": 110,
            }
        ],
    }

    events = reconcile_intervening_opponent_aerial_contacts(
        [apparent_pass],
        [
            observation(0.0, "black", 100, 0, 0),
            observation(3.4, "red", 182, 150, 150, control_ratio=0.9),
            observation(3.6, "black", 187, 120, 120),
        ],
        balls,
        minimum_speed_pixels_per_second=60,
    )

    assert events == [apparent_pass]


def test_frame_jersey_evidence_preserves_possession_through_track_switches() -> None:
    events = [
        PredictedEvent(
            "turnover_candidate", 1.4, "black", 10, 20, 0.8, "flight", 2.0
        ),
        PredictedEvent(
            "pass_candidate", 2.8, "red", 20, 30, 0.8, "flight", 3.0
        ),
        PredictedEvent(
            "pass_candidate", 3.8, "red", 30, 40, 0.8, "flight", 4.0
        ),
    ]
    players = {}
    for frame, seconds, track_id, team, scores in [
        (45, 1.8, 20, "red", {"dark": 0.5}),
        (50, 2.0, 20, "red", {"dark": 0.5}),
        (55, 2.2, 20, "red", {"dark": 0.5}),
        (70, 2.8, 30, "red", {"dark": 0.5}),
        (75, 3.0, 30, "red", {"dark": 0.5}),
        (80, 3.2, 30, "red", {"dark": 0.5}),
        (95, 3.8, 40, "red", {"white": 0.3, "warm": 0.2}),
        (100, 4.0, 40, "red", {"white": 0.3, "warm": 0.2}),
        (105, 4.2, 40, "red", {"white": 0.3, "warm": 0.2}),
    ]:
        players[frame] = [
            {
                "track_id": track_id,
                "clip_seconds": seconds,
                "team": team,
                "color_scores": scores,
            }
        ]

    corrected = reconcile_track_identity_team_switches(
        events,
        players,
        maximum_chain_seconds=2,
    )

    assert [(event.team, event.event_type) for event in corrected] == [
        ("black", "pass_candidate"),
        ("black", "pass_candidate"),
        ("black", "turnover_candidate"),
    ]


def test_track_switch_chain_requires_sender_control_at_release() -> None:
    events = [
        PredictedEvent(
            "turnover_candidate",
            1.0,
            "black",
            10,
            20,
            0.8,
            "Frame-level jersey evidence corrected a cross-team player-track "
            "identity switch.",
            1.4,
        ),
        PredictedEvent(
            "turnover_candidate", 3.0, "red", 20, 30, 0.8, "flight", 3.2
        ),
    ]
    players = {
        frame: [
            {
                "track_id": 30,
                "clip_seconds": seconds,
                "team": "black",
                "color_scores": {"dark": 0.5},
            }
        ]
        for frame, seconds in [(75, 3.0), (80, 3.2), (85, 3.4)]
    }

    corrected = reconcile_track_identity_team_switches(
        events,
        players,
        maximum_chain_seconds=2,
        control_observations=[
            observation(1.4, "red", 20, 100, 100),
            observation(2.0, "red", 20, 120, 100, control_ratio=0.8),
        ],
    )

    assert corrected == [events[0]]


def test_corrected_turnover_suppresses_impossible_intermediate_owner() -> None:
    corrected_turnover = PredictedEvent(
        "turnover_candidate",
        1.0,
        "black",
        10,
        20,
        0.8,
        "Frame-level jersey evidence corrected a cross-team player-track "
        "identity switch.",
        1.4,
    )
    impossible_black_loss = PredictedEvent(
        "turnover_candidate", 2.0, "black", 30, 40, 0.8, "control", 2.4
    )
    consistent_red_loss = PredictedEvent(
        "turnover_candidate", 3.0, "red", 50, 60, 0.8, "control", 3.2
    )

    corrected = reconcile_track_identity_team_switches(
        [corrected_turnover, impossible_black_loss, consistent_red_loss],
        {
            1: [
                {"track_id": 99, "clip_seconds": 0.0, "team": "red"},
                {"track_id": 100, "clip_seconds": 0.0, "team": "black"},
            ]
        },
        maximum_chain_seconds=2,
    )

    assert corrected == [corrected_turnover, consistent_red_loss]


def test_frame_jersey_evidence_reclassifies_false_same_team_pass() -> None:
    apparent_pass = PredictedEvent(
        "pass_candidate", 1.0, "black", 10, 20, 0.8, "flight", 1.4
    )
    players = {
        frame: [
            {
                "track_id": 20,
                "clip_seconds": seconds,
                "team": "red",
                "color_scores": {"white": 0.4, "warm": 0.2},
            }
        ]
        for frame, seconds in [(35, 1.4), (40, 1.6), (45, 1.8)]
    }

    corrected = reconcile_track_identity_team_switches(
        [apparent_pass],
        players,
        maximum_chain_seconds=2,
    )

    assert len(corrected) == 1
    assert corrected[0].team == "black"
    assert corrected[0].event_type == "turnover_candidate"


def test_stable_precontact_team_prevents_local_color_reclassification() -> None:
    apparent_turnover = PredictedEvent(
        "turnover_candidate", 1.0, "black", 10, 20, 0.8, "flight", 1.8
    )
    players = {
        frame: [{
            "track_id": 20,
            "clip_seconds": seconds,
            "team": "red",
            "color_scores": {"dark": 0.6},
        }]
        for frame, seconds in [
            (25, 1.0),
            (30, 1.2),
            (35, 1.4),
            (40, 1.6),
            (45, 1.8),
        ]
    }

    corrected = reconcile_track_identity_team_switches(
        [apparent_turnover],
        players,
        maximum_chain_seconds=2,
    )

    assert corrected == [apparent_turnover]


def test_team_flip_at_reception_suppresses_ambiguous_pass() -> None:
    apparent_pass = PredictedEvent(
        "pass_candidate", 1.0, "black", 10, 20, 0.8, "flight", 1.8
    )
    players = {
        frame: [{
            "track_id": 20,
            "clip_seconds": seconds,
            "team": "red" if seconds < 1.8 else "black",
            "color_scores": {"dark": 0.6},
        }]
        for frame, seconds in [
            (25, 1.0),
            (30, 1.2),
            (35, 1.4),
            (45, 1.8),
            (50, 2.0),
            (55, 2.2),
        ]
    }

    corrected = reconcile_track_identity_team_switches(
        [apparent_pass],
        players,
        maximum_chain_seconds=2,
    )

    assert corrected == []


def test_later_control_resolves_earlier_contested_turnover() -> None:
    spanning = PredictedEvent(
        "pass_candidate", 0.6, "black", 1, 2, 0.8, "flight", 1.4
    )
    confirmed = PredictedEvent(
        "pass_candidate", 1.6, "black", 2, 3, 0.8, "flight", 2.0
    )
    balls = {
        20: [
            {
                "track_id": 1,
                "source_frame": 20,
                "clip_seconds": 0.8,
                "x": 100,
                "y": 100,
            }
        ],
        25: [
            {
                "track_id": 1,
                "source_frame": 25,
                "clip_seconds": 1.0,
                "x": 120,
                "y": 100,
            }
        ],
        30: [
            {
                "track_id": 1,
                "source_frame": 30,
                "clip_seconds": 1.2,
                "x": 100,
                "y": 100,
            }
        ],
        45: [
            {
                "track_id": 1,
                "source_frame": 45,
                "clip_seconds": 1.8,
                "x": 200,
                "y": 100,
            }
        ],
        50: [
            {
                "track_id": 1,
                "source_frame": 50,
                "clip_seconds": 2.0,
                "x": 205,
                "y": 100,
            }
        ],
        55: [
            {
                "track_id": 1,
                "source_frame": 55,
                "clip_seconds": 2.2,
                "x": 210,
                "y": 100,
            }
        ],
    }

    def player(
        track_id: int,
        team: str,
        x: float,
        scores: dict[str, float],
        seconds: float,
    ) -> dict[str, object]:
        return {
            "track_id": track_id,
            "team": team,
            "clip_seconds": seconds,
            "x1": x - 10,
            "y1": 60,
            "x2": x + 10,
            "y2": 110,
            "color_scores": scores,
        }

    players = {
        25: [
            player(1, "black", 116, {"dark": 0.6}, 1.0),
            player(2, "red", 124, {"white": 0.3, "warm": 0.2}, 1.0),
        ],
        45: [player(3, "red", 200, {"white": 0.4, "warm": 0.2}, 1.8)],
        50: [player(3, "red", 205, {"white": 0.4, "warm": 0.2}, 2.0)],
        55: [player(3, "red", 210, {"white": 0.4, "warm": 0.2}, 2.2)],
    }

    events = infer_deferred_contested_turnovers(
        [spanning, confirmed],
        players,
        balls,
        [
            observation(0.8, "black", 1, 100, 100, control_ratio=0.3),
            observation(1.0, "black", 1, 120, 120, control_ratio=0.3),
            observation(1.8, "red", 3, 200, 200, control_ratio=0.3),
            observation(2.0, "red", 3, 205, 205, control_ratio=0.3),
        ],
        minimum_speed_pixels_per_second=45,
    )

    assert [(event.team, event.event_type) for event in events] == [
        ("black", "turnover_candidate"),
        ("red", "pass_candidate"),
    ]
    assert events[0].completion_seconds == 1.0


def test_terminal_turnover_resolves_earlier_contested_contact(
    monkeypatch,
) -> None:
    terminal_turnover = PredictedEvent(
        "turnover_candidate", 3.0, "black", 2, 3, 0.8, "control", 3.4
    )
    monkeypatch.setattr(
        "football_poc.innovation_day_snapshot.possession."
        "_receiver_team_evidence",
        lambda *args, **kwargs: ("red", 0.9, 4.0),
    )
    monkeypatch.setattr(
        "football_poc.innovation_day_snapshot.possession."
        "_contested_contact_seconds",
        lambda *args, **kwargs: 1.0,
    )

    events = infer_deferred_contested_turnovers(
        [terminal_turnover],
        {},
        {},
        [
            observation(0.8, "black", 2, 100, 100, control_ratio=0.3),
            observation(1.0, "black", 2, 100, 100, control_ratio=0.3),
            observation(3.4, "red", 3, 200, 200, control_ratio=0.3),
        ],
        minimum_speed_pixels_per_second=45,
    )

    assert len(events) == 1
    assert events[0].event_type == "turnover_candidate"
    assert events[0].team == "black"
    assert events[0].completion_seconds == 1.0


def test_deferred_turnover_requires_control_near_contested_contact(
    monkeypatch,
) -> None:
    terminal_turnover = PredictedEvent(
        "turnover_candidate", 3.0, "red", 2, 3, 0.8, "control", 3.4
    )
    monkeypatch.setattr(
        "football_poc.innovation_day_snapshot.possession."
        "_receiver_team_evidence",
        lambda *args, **kwargs: ("black", 0.9, 4.0),
    )
    monkeypatch.setattr(
        "football_poc.innovation_day_snapshot.possession."
        "_contested_contact_seconds",
        lambda *args, **kwargs: 1.0,
    )

    events = infer_deferred_contested_turnovers(
        [terminal_turnover],
        {},
        {},
        [
            observation(0.0, "red", 2, 100, 100, control_ratio=0.3),
            observation(3.4, "black", 3, 200, 200, control_ratio=0.3),
        ],
        minimum_speed_pixels_per_second=45,
    )

    assert events == [terminal_turnover]


def test_terminal_turnover_does_not_cross_intervening_team_pass(
    monkeypatch,
) -> None:
    received_at_contact = PredictedEvent(
        "pass_candidate", 0.5, "black", 9, 1, 0.8, "pass", 1.0
    )
    team_pass = PredictedEvent(
        "pass_candidate", 1.5, "black", 1, 2, 0.8, "pass", 2.0
    )
    terminal_turnover = PredictedEvent(
        "turnover_candidate", 3.0, "black", 2, 3, 0.8, "control", 3.4
    )
    monkeypatch.setattr(
        "football_poc.innovation_day_snapshot.possession."
        "_receiver_team_evidence",
        lambda _players, _balls, seconds, **_kwargs: (
            ("red", 0.9, 4.0) if seconds > 3 else ("black", 0.9, 4.0)
        ),
    )
    monkeypatch.setattr(
        "football_poc.innovation_day_snapshot.possession."
        "_contested_contact_seconds",
        lambda *args, **kwargs: 1.0,
    )

    events = infer_deferred_contested_turnovers(
        [received_at_contact, team_pass, terminal_turnover],
        {},
        {},
        minimum_speed_pixels_per_second=45,
    )

    assert events == [received_at_contact, team_pass, terminal_turnover]


def test_terminal_control_confirms_direction_change_reception(
    monkeypatch,
) -> None:
    prior = PredictedEvent(
        "pass_candidate", 0.8, "red", 7, 8, 0.8, "pass", 0.8
    )
    observations = [
        observation(2.0, "red", 9, 100, 100, control_ratio=0.4),
        observation(2.4, "red", 9, 100, 100, control_ratio=0.3),
        observation(2.8, "black", 10, 200, 100, control_ratio=1.2),
    ]
    monkeypatch.setattr(
        "football_poc.innovation_day_snapshot.possession."
        "_ball_motion_evidence",
        lambda balls: {(1, 50): (100.0, -0.5)},
    )

    events = infer_unresolved_direction_change_receptions(
        [prior],
        observations,
        {},
        minimum_speed_pixels_per_second=45,
    )

    assert [(event.team, event.completion_seconds) for event in events] == [
        ("red", 0.8),
        ("red", 2.0),
    ]


def test_opponent_jersey_evidence_blocks_false_direction_change_pass(
    monkeypatch,
) -> None:
    prior = PredictedEvent(
        "pass_candidate", 0.8, "black", 7, 8, 0.8, "pass", 0.8
    )
    controls = [
        observation(2.0, "black", 9, 100, 100, control_ratio=0.4),
        observation(2.4, "black", 9, 100, 100, control_ratio=0.3),
    ]
    monkeypatch.setattr(
        "football_poc.innovation_day_snapshot.possession."
        "_ball_motion_evidence",
        lambda balls: {(1, 50): (100.0, -0.5)},
    )
    monkeypatch.setattr(
        "football_poc.innovation_day_snapshot.possession."
        "_receiver_team_evidence",
        lambda *args, **kwargs: ("red", 0.8, 3.0),
    )

    events = infer_unresolved_direction_change_receptions(
        [prior],
        controls,
        {},
        players={50: []},
        minimum_speed_pixels_per_second=45,
    )

    assert events == [prior]


def test_outgoing_pass_alone_does_not_manufacture_incoming_pass(
    monkeypatch,
) -> None:
    outgoing = PredictedEvent(
        "pass_candidate", 2.6, "red", 39, 45, 0.8, "pass", 3.6
    )
    observations = [
        observation(2.4, "red", 39, 100, 100, control_ratio=0.3),
        observation(2.8, "red", 45, 200, 100, control_ratio=0.4),
    ]
    monkeypatch.setattr(
        "football_poc.innovation_day_snapshot.possession."
        "_ball_motion_evidence",
        lambda balls: {(1, 60): (100.0, -0.5)},
    )

    events = infer_unresolved_direction_change_receptions(
        [outgoing],
        observations,
        {},
        minimum_speed_pixels_per_second=45,
    )

    assert events == [outgoing]


def test_retained_owner_direction_change_does_not_manufacture_pass(
    monkeypatch,
) -> None:
    prior = PredictedEvent(
        "pass_candidate", 1.0, "black", 1, 2, 0.8, "incoming", 1.4
    )
    outgoing = PredictedEvent(
        "pass_candidate", 3.0, "black", 2, 3, 0.8, "outgoing", 4.0
    )
    controls = [
        observation(2.6, "black", 2, 200, 100, control_ratio=0.4),
    ]
    monkeypatch.setattr(
        "football_poc.innovation_day_snapshot.possession."
        "_ball_motion_evidence",
        lambda balls: {(1, controls[0].source_frame): (100.0, -0.5)},
    )

    events = infer_unresolved_direction_change_receptions(
        [prior, outgoing],
        controls,
        {},
        minimum_speed_pixels_per_second=45,
    )

    assert events == [prior, outgoing]


def test_controlled_release_recovers_incoming_same_team_flight() -> None:
    outgoing = PredictedEvent(
        "pass_candidate", 1.0, "black", 2, 3, 0.8, "outgoing", 2.0
    )
    events = infer_pre_release_flight_receptions(
        [outgoing],
        [
            observation(0.0, "black", 1, 0, 0, control_ratio=0.8),
            observation(0.4, "red", 9, 80, 80, control_ratio=1.2),
            observation(1.0, "black", 2, 200, 200, control_ratio=0.2),
        ],
        {
            0: [
                {
                    "track_id": 1,
                    "source_frame": 0,
                    "clip_seconds": 0.0,
                    "x": 0,
                    "y": 0,
                }
            ],
            5: [
                {
                    "track_id": 1,
                    "source_frame": 5,
                    "clip_seconds": 0.2,
                    "x": 20,
                    "y": 0,
                }
            ],
            25: [
                {
                    "track_id": 1,
                    "source_frame": 25,
                    "clip_seconds": 1.0,
                    "x": 200,
                    "y": 0,
                }
            ],
        },
        co_visible_track_pairs=set(),
        minimum_speed_pixels_per_second=45,
        maximum_sender_lookback_seconds=3,
    )

    assert [
        (
            event.team,
            event.from_player_track_id,
            event.to_player_track_id,
            event.completion_seconds,
        )
        for event in events
    ] == [
        ("black", 1, 2, 1.0),
        ("black", 2, 3, 2.0),
    ]


def test_sharp_contact_and_release_recovers_weak_proximity_reception() -> None:
    outgoing = PredictedEvent(
        "pass_candidate", 1.4, "black", 2, 3, 0.8, "outgoing", 2.0
    )
    events = infer_pre_release_flight_receptions(
        [outgoing],
        [
            observation(0.4, "black", 1, 0, 0, control_ratio=0.8),
            observation(1.0, "black", 2, 100, 100, control_ratio=1.1),
        ],
        {
            10: [
                {
                    "track_id": 4,
                    "source_frame": 10,
                    "clip_seconds": 0.4,
                    "x": 0,
                    "y": 20,
                }
            ],
            15: [
                {
                    "track_id": 4,
                    "source_frame": 15,
                    "clip_seconds": 0.6,
                    "x": 40,
                    "y": 20,
                }
            ],
            20: [
                {
                    "track_id": 4,
                    "source_frame": 20,
                    "clip_seconds": 0.8,
                    "x": 80,
                    "y": 20,
                }
            ],
            25: [
                {
                    "track_id": 4,
                    "source_frame": 25,
                    "clip_seconds": 1.0,
                    "x": 60,
                    "y": 20,
                }
            ],
            30: [
                {
                    "track_id": 4,
                    "source_frame": 30,
                    "clip_seconds": 1.2,
                    "x": 100,
                    "y": 20,
                }
            ],
        },
        co_visible_track_pairs={frozenset((1, 2))},
        minimum_speed_pixels_per_second=45,
        maximum_sender_lookback_seconds=2,
    )

    assert [
        (
            event.from_player_track_id,
            event.to_player_track_id,
            event.completion_seconds,
        )
        for event in events
    ] == [(1, 2, 1.0), (2, 3, 2.0)]


def test_opponent_control_blocks_pre_release_flight_recovery() -> None:
    outgoing = PredictedEvent(
        "pass_candidate", 1.0, "black", 2, 3, 0.8, "outgoing", 2.0
    )
    events = infer_pre_release_flight_receptions(
        [outgoing],
        [
            observation(0.0, "black", 1, 0, 0, control_ratio=0.8),
            observation(0.4, "red", 9, 40, 40, control_ratio=0.3),
            observation(1.0, "black", 2, 100, 100, control_ratio=0.2),
        ],
        {
            0: [
                {
                    "track_id": 1,
                    "source_frame": 0,
                    "clip_seconds": 0.0,
                    "x": 0,
                    "y": 0,
                }
            ],
            5: [
                {
                    "track_id": 1,
                    "source_frame": 5,
                    "clip_seconds": 0.2,
                    "x": 20,
                    "y": 0,
                }
            ],
            25: [
                {
                    "track_id": 1,
                    "source_frame": 25,
                    "clip_seconds": 1.0,
                    "x": 100,
                    "y": 0,
                }
            ],
        },
        co_visible_track_pairs={frozenset((1, 2))},
        minimum_speed_pixels_per_second=45,
        maximum_sender_lookback_seconds=3,
    )

    assert events == [outgoing]


def test_track_handoff_does_not_create_pre_release_flight_pass() -> None:
    outgoing = PredictedEvent(
        "pass_candidate", 1.0, "black", 2, 3, 0.8, "outgoing", 2.0
    )
    events = infer_pre_release_flight_receptions(
        [outgoing],
        [
            observation(0.0, "black", 1, 0, 0, control_ratio=0.8),
            observation(1.0, "black", 2, 100, 100, control_ratio=0.2),
        ],
        {
            0: [
                {
                    "track_id": 1,
                    "source_frame": 0,
                    "clip_seconds": 0.0,
                    "x": 0,
                    "y": 0,
                }
            ],
            5: [
                {
                    "track_id": 1,
                    "source_frame": 5,
                    "clip_seconds": 0.2,
                    "x": 20,
                    "y": 0,
                }
            ],
            25: [
                {
                    "track_id": 1,
                    "source_frame": 25,
                    "clip_seconds": 1.0,
                    "x": 100,
                    "y": 0,
                }
            ],
        },
        co_visible_track_pairs=set(),
        minimum_speed_pixels_per_second=45,
        maximum_sender_lookback_seconds=3,
    )

    assert events == [outgoing]


def test_existing_reception_blocks_duplicate_pre_release_flight_pass() -> None:
    prior = PredictedEvent(
        "pass_candidate", 0.2, "black", 4, 2, 0.8, "prior", 0.6
    )
    outgoing = PredictedEvent(
        "pass_candidate", 1.0, "black", 2, 3, 0.8, "outgoing", 2.0
    )
    events = infer_pre_release_flight_receptions(
        [prior, outgoing],
        [
            observation(0.0, "black", 1, 0, 0, control_ratio=0.8),
            observation(1.0, "black", 2, 200, 200, control_ratio=0.2),
        ],
        {
            0: [
                {
                    "track_id": 1,
                    "source_frame": 0,
                    "clip_seconds": 0.0,
                    "x": 0,
                    "y": 0,
                }
            ],
            5: [
                {
                    "track_id": 1,
                    "source_frame": 5,
                    "clip_seconds": 0.2,
                    "x": 20,
                    "y": 0,
                }
            ],
            25: [
                {
                    "track_id": 1,
                    "source_frame": 25,
                    "clip_seconds": 1.0,
                    "x": 200,
                    "y": 0,
                }
            ],
        },
        co_visible_track_pairs=set(),
        minimum_speed_pixels_per_second=45,
        maximum_sender_lookback_seconds=3,
    )

    assert events == [prior, outgoing]


def test_single_goalkeeper_observation_can_confirm_reception() -> None:
    segments = build_possession_segments(
        [observation(1.0, "red", 7, 100, 100)],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0.75,
    )

    assert (
        retain_stable_possession_segments(
            segments,
            minimum_observations=2,
            trusted_single_observation_track_ids={7},
        )
        == segments
    )
    assert (
        retain_stable_possession_segments(
            segments,
            minimum_observations=2,
            trusted_single_observation_track_ids=set(),
        )
        == []
    )


def test_transient_proximity_does_not_establish_reception() -> None:
    segments = build_possession_segments(
        [
            observation(1.8, "black", 7, 100, 100, control_ratio=1.05),
            observation(2.0, "black", 7, 102, 102, control_ratio=1.1),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0.75,
    )

    event = PredictedEvent(
        "pass_candidate", 1.6, "black", 1, 7, 0.6, "flight", 1.8
    )

    assert suppress_transient_proximity_receptions([event], segments, {}) == []

    high_speed_event = PredictedEvent(
        "pass_candidate", 1.6, "black", 1, 7, 0.8, "flight", 1.8
    )
    assert suppress_transient_proximity_receptions(
        [high_speed_event], segments, {}
    ) == [high_speed_event]


def test_single_touch_sender_is_retained_for_distinct_sustained_receiver() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "black", 1, 100, 100, control_ratio=0.2),
            observation(2.0, "black", 2, 300, 300, control_ratio=0.3),
            observation(2.2, "black", 2, 305, 305, control_ratio=0.2),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )
    stable = retain_stable_possession_segments(
        segments,
        minimum_observations=2,
        trusted_single_observation_track_ids=set(),
    )

    retained = include_supported_single_touch_senders(
        segments,
        stable,
        co_visible_track_pairs={frozenset((1, 2))},
        maximum_transfer_seconds=2,
        minimum_transfer_heights=1.5,
    )

    assert [segment.player_track_id for segment in retained] == [1, 2]
    events = infer_transfer_events(
        retained,
        maximum_transfer_seconds=2,
        minimum_transfer_heights=1.5,
    )
    assert len(events) == 1
    assert events[0].from_player_track_id == 1
    assert events[0].to_player_track_id == 2
    assert events[0].completion_seconds == 2.0


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


def test_ball_flight_requires_controlled_sender_at_release() -> None:
    segments = build_possession_segments(
        [
            observation(0.8, "red", 1, 100, 100, control_ratio=0.3),
            observation(1.0, "red", 1, 102, 102, control_ratio=1.1),
            observation(1.8, "black", 2, 300, 300, control_ratio=0.2),
            observation(2.0, "black", 2, 302, 302, control_ratio=0.2),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )
    balls = {
        1: [{"track_id": 1, "clip_seconds": 1.0, "x": 100, "y": 100}],
        2: [{"track_id": 1, "clip_seconds": 1.2, "x": 180, "y": 100}],
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

    assert events == []


def test_ball_flight_rejects_release_while_sender_retains_control() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "black", 1, 100, 100, control_ratio=0.3),
            observation(1.2, "black", 1, 120, 100, control_ratio=0.7),
            observation(1.4, "black", 1, 140, 100, control_ratio=0.7),
            observation(2.0, "black", 2, 300, 100, control_ratio=0.2),
            observation(2.2, "black", 2, 302, 100, control_ratio=0.2),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )
    balls = {
        1: [{"track_id": 1, "clip_seconds": 1.0, "x": 100, "y": 100}],
        2: [{"track_id": 1, "clip_seconds": 1.2, "x": 180, "y": 100}],
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

    assert events == []


def test_ball_flight_rejects_release_after_sender_control_is_stale() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "black", 1, 100, 100, control_ratio=0.3),
            observation(2.0, "black", 2, 300, 100, control_ratio=0.2),
            observation(2.2, "black", 2, 302, 100, control_ratio=0.2),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )
    balls = {
        1: [{"track_id": 1, "clip_seconds": 1.8, "x": 100, "y": 100}],
        2: [{"track_id": 1, "clip_seconds": 2.0, "x": 180, "y": 100}],
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

    assert events == []


def test_ball_flight_sender_lookback_does_not_cross_opponent_release_control() -> None:
    segments = build_possession_segments(
        [
            observation(0.8, "red", 1, 100, 100, control_ratio=0.3),
            observation(1.0, "red", 1, 102, 102, control_ratio=0.3),
            observation(1.4, "black", 3, 100, 100, control_ratio=0.3),
            observation(1.6, "black", 3, 180, 100, control_ratio=0.3),
            observation(2.0, "red", 2, 300, 300, control_ratio=0.2),
            observation(2.2, "red", 2, 302, 302, control_ratio=0.2),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )
    balls = {
        35: [
            {
                "track_id": 1,
                "source_frame": 35,
                "clip_seconds": 1.4,
                "x": 100,
                "y": 100,
            }
        ],
        40: [
            {
                "track_id": 1,
                "source_frame": 40,
                "clip_seconds": 1.6,
                "x": 180,
                "y": 100,
            }
        ],
    }

    events = infer_flight_transfer_events(
        balls,
        segments,
        control_observations=[
            observation(1.4, "black", 3, 100, 100, control_ratio=0.3)
        ],
        minimum_speed_pixels_per_second=60,
        maximum_step_seconds=0.24,
        debounce_seconds=1.2,
        sender_lookback_seconds=1,
        receiver_window_seconds=2,
    )

    assert not any(
        event.event_type == "pass_candidate"
        and event.team == "red"
        and event.to_player_track_id == 2
        for event in events
    )


def test_ball_flight_pass_does_not_cross_intervening_opponent_control() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "red", 1, 100, 100, control_ratio=0.3),
            observation(1.2, "red", 1, 102, 102, control_ratio=0.3),
            observation(1.8, "black", 3, 220, 220, control_ratio=0.3),
            observation(2.0, "red", 2, 300, 300, control_ratio=0.2),
            observation(2.2, "red", 2, 302, 302, control_ratio=0.2),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )
    balls = {
        30: [
            {
                "track_id": 1,
                "source_frame": 30,
                "clip_seconds": 1.2,
                "x": 100,
                "y": 100,
            }
        ],
        35: [
            {
                "track_id": 1,
                "source_frame": 35,
                "clip_seconds": 1.4,
                "x": 180,
                "y": 100,
            }
        ],
    }

    events = infer_flight_transfer_events(
        balls,
        segments,
        control_observations=[
            observation(1.8, "black", 3, 220, 220, control_ratio=0.3)
        ],
        minimum_speed_pixels_per_second=60,
        maximum_step_seconds=0.24,
        debounce_seconds=1.2,
        sender_lookback_seconds=1,
        receiver_window_seconds=2,
    )

    assert not any(
        event.event_type == "pass_candidate"
        and event.team == "red"
        and event.to_player_track_id == 2
        for event in events
    )


def test_delayed_turnover_is_not_retimed_to_uncontrolled_contested_contact() -> None:
    event = PredictedEvent(
        "turnover_candidate",
        8.8,
        "red",
        45,
        73,
        0.8,
        "Delayed black control.",
        10.4,
    )
    balls = {
        1: [{"track_id": 1, "clip_seconds": 7.2, "x": 0, "y": 100}],
        2: [{"track_id": 1, "clip_seconds": 7.4, "x": 100, "y": 100}],
        3: [{"track_id": 1, "clip_seconds": 7.6, "x": 105, "y": 100}],
    }
    players = {
        2: [
            {
                "track_id": 45,
                "team": "red",
                "x1": 90,
                "x2": 110,
                "y1": 50,
                "y2": 100,
            },
            {
                "track_id": 73,
                "team": "black",
                "x1": 90,
                "x2": 110,
                "y1": 50,
                "y2": 100,
            },
        ]
    }
    observations = [
        observation(6.0, "red", 45, 100, 100, control_ratio=0.2),
        observation(7.4, "black", 73, 100, 100, control_ratio=1.2),
        observation(10.4, "black", 73, 100, 100, control_ratio=0.2),
    ]

    events = refine_delayed_turnovers_to_contested_decelerations(
        [event],
        players,
        balls,
        observations,
        minimum_speed_pixels_per_second=60,
    )

    assert events == [event]


def test_delayed_turnover_retimes_to_controlled_opponent_touch() -> None:
    event = PredictedEvent(
        "turnover_candidate",
        8.8,
        "red",
        45,
        73,
        0.8,
        "Delayed black control.",
        10.4,
    )
    balls = {
        1: [{"track_id": 1, "clip_seconds": 7.2, "x": 0, "y": 100}],
        2: [{"track_id": 1, "clip_seconds": 7.4, "x": 100, "y": 100}],
        3: [{"track_id": 1, "clip_seconds": 7.6, "x": 105, "y": 100}],
    }
    players = {
        2: [
            {
                "track_id": 45,
                "team": "red",
                "x1": 90,
                "x2": 110,
                "y1": 50,
                "y2": 100,
            },
            {
                "track_id": 73,
                "team": "black",
                "x1": 90,
                "x2": 110,
                "y1": 50,
                "y2": 100,
            },
        ]
    }
    observations = [
        observation(7.2, "red", 45, 100, 100, control_ratio=0.2),
        observation(7.4, "black", 73, 100, 100, control_ratio=0.2),
    ]

    events = refine_delayed_turnovers_to_contested_decelerations(
        [event],
        players,
        balls,
        observations,
        minimum_speed_pixels_per_second=60,
    )

    assert len(events) == 1
    assert events[0].clip_seconds == 7.4
    assert events[0].completion_seconds == 7.4
    assert events[0].to_player_track_id == 73


def test_flight_reception_uses_contact_not_earlier_transient_proximity() -> None:
    segments = build_possession_segments(
        [
            observation(0.8, "black", 1, 100, 100),
            observation(1.0, "black", 1, 102, 102),
            observation(1.8, "black", 2, 180, 180, control_ratio=1.05),
            observation(2.0, "black", 2, 190, 190, control_ratio=1.1),
            observation(3.4, "black", 3, 200, 200, control_ratio=0.25),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )
    balls = {
        round(seconds * 25): [
            {
                "track_id": 1,
                "source_frame": round(seconds * 25),
                "clip_seconds": seconds,
                "x": x,
                "y": y,
            }
        ]
        for seconds, x, y in [
            (1.0, 100, 100),
            (1.2, 130, 100),
            (1.4, 160, 100),
            (1.6, 180, 100),
            (1.8, 200, 100),
            (2.0, 220, 100),
            (2.2, 240, 100),
            (2.4, 260, 100),
            (2.6, 280, 100),
            (2.8, 300, 100),
            (3.0, 305, 100),
            (3.2, 310, 100),
            (3.4, 300, 100),
        ]
    }

    events = infer_flight_transfer_events(
        balls,
        segments,
        minimum_speed_pixels_per_second=45,
        maximum_step_seconds=0.24,
        debounce_seconds=1.2,
        sender_lookback_seconds=3,
        receiver_window_seconds=3,
        minimum_receiver_observations=2,
    )

    assert len(events) == 1
    assert events[0].to_player_track_id == 3
    assert events[0].completion_seconds == 3.0


def test_reception_timing_waits_for_strong_control_after_weak_proximity() -> None:
    segments = build_possession_segments(
        [
            observation(0.8, "black", 1, 100, 100),
            observation(1.0, "black", 1, 102, 102),
            observation(1.4, "black", 2, 300, 300, control_ratio=1.2),
            observation(1.6, "black", 2, 302, 302, control_ratio=0.8),
            observation(1.8, "black", 2, 304, 304, control_ratio=0.05),
        ],
        segment_gap_seconds=0.3,
        identity_switch_radius_heights=0,
    )
    events = refine_weak_reception_completion_times(
        [
            PredictedEvent(
                "pass_candidate", 1.0, "black", 1, 2, 0.8, "flight", 1.4
            )
        ],
        segments,
    )

    assert events[0].completion_seconds == 1.8


def test_pass_reception_waits_through_extended_weak_proximity_for_control() -> None:
    segments = build_possession_segments(
        [
            observation(1.4, "black", 2, 300, 300, control_ratio=1.2),
            observation(1.8, "black", 2, 302, 302, control_ratio=0.8),
            observation(3.2, "black", 2, 304, 304, control_ratio=0.09),
            observation(3.4, "black", 2, 306, 306, control_ratio=0.08),
        ],
        segment_gap_seconds=1.5,
        identity_switch_radius_heights=0,
    )

    events = refine_weak_reception_completion_times(
        [
            PredictedEvent(
                "pass_candidate", 1.2, "black", 1, 2, 0.8, "flight", 1.4
            )
        ],
        segments,
    )

    assert events[0].completion_seconds == 3.2


def test_pass_reception_uses_first_sustained_clear_control_after_weak_proximity() -> None:
    segments = build_possession_segments(
        [
            observation(1.4, "black", 2, 300, 300, control_ratio=1.2),
            observation(1.8, "black", 2, 302, 302, control_ratio=0.8),
            observation(2.2, "black", 2, 304, 304, control_ratio=0.45),
            observation(2.4, "black", 2, 306, 306, control_ratio=0.42),
        ],
        segment_gap_seconds=1.0,
        identity_switch_radius_heights=0,
    )

    events = refine_weak_reception_completion_times(
        [
            PredictedEvent(
                "pass_candidate", 1.2, "black", 1, 2, 0.8, "flight", 1.4
            )
        ],
        segments,
    )

    assert events[0].completion_seconds == 2.4
    assert "first clear controlled touch" in events[0].details


def test_pass_reception_prefers_sharp_contact_over_later_proximity_confirmation() -> None:
    segments = build_possession_segments(
        [
            observation(1.4, "black", 2, 300, 300, control_ratio=1.2),
            observation(2.0, "black", 2, 302, 302, control_ratio=0.7),
            observation(2.2, "black", 2, 304, 304, control_ratio=0.4),
            observation(2.4, "black", 2, 306, 306, control_ratio=0.45),
            observation(2.6, "black", 2, 308, 308, control_ratio=0.42),
        ],
        segment_gap_seconds=1.0,
        identity_switch_radius_heights=0,
    )
    balls = {
        50: [
            {
                "track_id": 4,
                "source_frame": 50,
                "clip_seconds": 2.0,
                "x": 100,
                "y": 100,
            }
        ],
        55: [
            {
                "track_id": 4,
                "source_frame": 55,
                "clip_seconds": 2.2,
                "x": 120,
                "y": 100,
            }
        ],
        60: [
            {
                "track_id": 4,
                "source_frame": 60,
                "clip_seconds": 2.4,
                "x": 100,
                "y": 100,
            }
        ],
    }

    events = refine_weak_reception_completion_times(
        [
            PredictedEvent(
                "pass_candidate", 1.2, "black", 1, 2, 0.8, "flight", 1.4
            )
        ],
        segments,
        balls,
        minimum_speed_pixels_per_second=40,
    )

    assert events[0].completion_seconds == 2.2


def test_pass_reception_ignores_isolated_late_proximity() -> None:
    segments = build_possession_segments(
        [
            observation(1.4, "black", 2, 300, 300, control_ratio=1.2),
            observation(1.8, "black", 2, 302, 302, control_ratio=0.8),
            observation(2.2, "black", 2, 304, 304, control_ratio=0.45),
            observation(2.4, "black", 2, 306, 306, control_ratio=0.72),
        ],
        segment_gap_seconds=1.0,
        identity_switch_radius_heights=0,
    )

    events = refine_weak_reception_completion_times(
        [
            PredictedEvent(
                "pass_candidate", 1.2, "black", 1, 2, 0.8, "flight", 1.4
            )
        ],
        segments,
    )

    assert events[0].completion_seconds == 1.4


def test_pass_reception_does_not_backdate_from_one_immediate_proximity() -> None:
    segments = build_possession_segments(
        [
            observation(1.4, "black", 2, 300, 300, control_ratio=1.2),
            observation(1.8, "black", 2, 302, 302, control_ratio=0.4),
            observation(3.2, "black", 2, 304, 304, control_ratio=0.09),
        ],
        segment_gap_seconds=1.5,
        identity_switch_radius_heights=0,
    )

    events = refine_weak_reception_completion_times(
        [
            PredictedEvent(
                "pass_candidate", 1.2, "black", 1, 2, 0.8, "flight", 1.4
            )
        ],
        segments,
    )

    assert events[0].completion_seconds == 3.2


def test_turnover_timing_waits_longer_for_confirmed_opponent_control() -> None:
    segments = build_possession_segments(
        [
            observation(1.4, "red", 2, 300, 300, control_ratio=1.2),
            observation(2.0, "red", 2, 302, 302, control_ratio=0.8),
            observation(2.2, "red", 2, 304, 304, control_ratio=0.4),
        ],
        segment_gap_seconds=0.7,
        identity_switch_radius_heights=0,
    )
    events = refine_weak_reception_completion_times(
        [
            PredictedEvent(
                "turnover_candidate", 1.0, "black", 1, 2, 0.8, "flight", 1.4
            )
        ],
        segments,
    )

    assert events[0].completion_seconds == 2.2


def test_turnover_waits_for_immediate_release_when_proximity_never_becomes_control() -> None:
    segments = build_possession_segments(
        [
            observation(1.4, "red", 2, 300, 300, control_ratio=1.2),
            observation(2.0, "red", 2, 302, 302, control_ratio=0.8),
            observation(2.2, "red", 2, 304, 304, control_ratio=0.42),
            observation(2.6, "red", 2, 306, 306, control_ratio=0.48),
        ],
        segment_gap_seconds=0.7,
        identity_switch_radius_heights=0,
    )
    events = refine_weak_reception_completion_times(
        [
            PredictedEvent(
                "turnover_candidate", 1.0, "black", 1, 2, 0.8, "flight", 1.4
            ),
            PredictedEvent(
                "pass_candidate", 2.6, "red", 2, 3, 0.8, "release", 3.0
            ),
        ],
        segments,
    )

    assert events[0].completion_seconds == 2.6


def test_unconfirmed_opponent_proximity_does_not_create_turnover() -> None:
    turnover = PredictedEvent(
        "turnover_candidate", 1.0, "black", 8, 14, 0.8, "flight", 2.0
    )
    receiver = PossessionSegment(
        "red",
        14,
        [
            observation(2.0, "red", 14, 200, 200, control_ratio=1.2),
            observation(2.8, "red", 14, 202, 202, control_ratio=1.4),
        ],
    )

    events = reconcile_unconfirmed_turnovers([turnover], [receiver])

    assert [(event.event_type, event.team) for event in events] == [
        ("pass_candidate", "black")
    ]
    assert events[0].to_player_track_id is None


def test_confirmed_opponent_control_remains_turnover() -> None:
    turnover = PredictedEvent(
        "turnover_candidate", 1.0, "black", 8, 14, 0.8, "flight", 2.0
    )
    receiver = PossessionSegment(
        "red",
        14,
        [
            observation(2.0, "red", 14, 200, 200, control_ratio=1.2),
            observation(2.2, "red", 14, 202, 202, control_ratio=0.4),
        ],
    )

    assert reconcile_unconfirmed_turnovers([turnover], [receiver]) == [turnover]


def test_turnover_is_rejected_when_losing_team_retains_control() -> None:
    turnover = PredictedEvent(
        "turnover_candidate", 1.0, "red", 8, 14, 0.8, "flight", 2.0
    )
    delayed_pass = PredictedEvent(
        "pass_candidate", 2.2, "black", 14, 15, 0.8, "handoff", 2.4
    )
    retained = PossessionSegment(
        "red",
        8,
        [
            observation(1.8, "red", 8, 200, 200, control_ratio=0.3),
            observation(2.0, "red", 8, 202, 202, control_ratio=0.2),
            observation(2.2, "red", 8, 204, 204, control_ratio=0.2),
            observation(2.4, "red", 8, 206, 206, control_ratio=0.3),
        ],
    )

    events = suppress_uncontrolled_opponent_turnovers(
        [turnover, delayed_pass],
        {},
        {},
        [retained],
    )

    assert [(event.event_type, event.team) for event in events] == [
        ("pass_candidate", "red")
    ]
    assert events[0].details.startswith(
        "Possession continuity prevented a silent team change"
    )


def test_retained_possession_supersedes_its_immediate_inferred_handoff() -> None:
    handoff = PredictedEvent(
        "pass_candidate", 1.0, "black", 8, 14, 0.8, "handoff", 2.0
    )
    retained = PredictedEvent(
        "pass_candidate",
        2.0,
        "black",
        14,
        None,
        0.8,
        "Opponent proximity never became controlled possession.",
        3.2,
    )

    assert suppress_redundant_retained_possession_links(
        [handoff, retained]
    ) == [retained]


def test_disconnected_low_confidence_startup_chain_is_ignored() -> None:
    startup = [
        PredictedEvent(
            "pass_candidate", 1.0, "black", 1, 2, 0.51, "slow flight", 2.0
        ),
        PredictedEvent(
            "pass_candidate", 3.0, "black", 2, 3, 0.52, "slow flight", 4.0
        ),
    ]
    trusted = PredictedEvent(
        "pass_candidate", 8.0, "black", 3, 4, 0.9, "clear flight", 9.0
    )

    assert filter_disconnected_low_confidence_startup(
        [*startup, trusted]
    ) == [trusted]


def test_opponent_track_handoff_does_not_become_same_team_pass() -> None:
    event = PredictedEvent(
        "pass_candidate",
        1.0,
        "red",
        8,
        9,
        0.7,
        "Possession-chain validation prevented a silent team change.",
        1.4,
    )
    players = {
        25: [{"track_id": 8, "team": "black"}],
        35: [
            {
                "track_id": 9,
                "team": "black",
                "x1": 90,
                "y1": 50,
                "x2": 110,
                "y2": 100,
            },
            {
                "track_id": 10,
                "team": "red",
                "x1": 100,
                "y1": 50,
                "x2": 120,
                "y2": 100,
            },
        ],
    }
    balls = {
        25: [{"source_frame": 25, "clip_seconds": 1.0, "x": 100, "y": 100}],
        35: [{"source_frame": 35, "clip_seconds": 1.4, "x": 110, "y": 100}],
    }

    assert suppress_overlapping_opponent_handoffs(
        [event], players, balls
    ) == []


def test_pass_reception_moves_from_tracker_handoff_to_sharp_contact() -> None:
    event = PredictedEvent(
        "pass_candidate",
        1.0,
        "black",
        1,
        2,
        0.8,
        "Control transferred after 0.40s.",
        1.4,
    )
    balls = {
        30: [
            {
                "track_id": 1,
                "source_frame": 30,
                "clip_seconds": 1.2,
                "x": 100,
                "y": 100,
            }
        ],
        35: [
            {
                "track_id": 1,
                "source_frame": 35,
                "clip_seconds": 1.4,
                "x": 120,
                "y": 100,
            }
        ],
        40: [
            {
                "track_id": 1,
                "source_frame": 40,
                "clip_seconds": 1.6,
                "x": 140,
                "y": 100,
            }
        ],
        45: [
            {
                "track_id": 1,
                "source_frame": 45,
                "clip_seconds": 1.8,
                "x": 120,
                "y": 100,
            }
        ],
        50: [
            {
                "track_id": 1,
                "source_frame": 50,
                "clip_seconds": 2.0,
                "x": 100,
                "y": 100,
            }
        ],
    }

    events = refine_receptions_to_sharp_contacts(
        [event],
        [observation(1.6, "black", 3, 140, 140, control_ratio=0.9)],
        balls,
        minimum_speed_pixels_per_second=45,
    )

    assert events[0].to_player_track_id == 3
    assert events[0].completion_seconds == 1.6


def test_receiver_acceleration_confirms_one_touch_completion() -> None:
    event = PredictedEvent(
        "pass_candidate", 0.4, "black", 1, 2, 0.7, "flight", 1.6
    )
    players = {
        10: [
            {
                "track_id": 2,
                "team": "black",
                "x1": 10,
                "y1": 0,
                "x2": 20,
                "y2": 20,
            }
        ]
    }
    balls = {
        0: [{"track_id": 4, "source_frame": 0, "clip_seconds": 0.0, "x": 0, "y": 20}],
        5: [{"track_id": 4, "source_frame": 5, "clip_seconds": 0.2, "x": 10, "y": 20}],
        10: [{"track_id": 4, "source_frame": 10, "clip_seconds": 0.4, "x": 20, "y": 20}],
        15: [{"track_id": 4, "source_frame": 15, "clip_seconds": 0.6, "x": 60, "y": 20}],
    }

    refined = refine_one_touch_acceleration_receptions(
        [event],
        players,
        balls,
        minimum_speed_pixels_per_second=50,
    )

    assert refined[0].completion_seconds == 0.4


def test_short_exchange_is_recovered_before_existing_outgoing_pass() -> None:
    prior = PredictedEvent(
        "pass_candidate", 0.4, "black", 1, 20, 0.8, "flight", 1.0
    )
    outgoing = PredictedEvent(
        "pass_candidate", 3.0, "black", 20, 30, 0.8, "flight", 4.0
    )
    balls = {
        55: [
            {
                "track_id": 1,
                "source_frame": 55,
                "clip_seconds": 2.2,
                "x": 100,
                "y": 100,
            }
        ],
        60: [
            {
                "track_id": 1,
                "source_frame": 60,
                "clip_seconds": 2.4,
                "x": 120,
                "y": 100,
            }
        ],
        65: [
            {
                "track_id": 1,
                "source_frame": 65,
                "clip_seconds": 2.6,
                "x": 100,
                "y": 100,
            }
        ],
    }

    events = infer_short_exchange_receptions(
        [prior, outgoing],
        [
            observation(2.2, "black", 20, 100, 100, control_ratio=0.2),
            observation(2.4, "black", 21, 120, 120, control_ratio=0.05),
            observation(2.6, "black", 20, 100, 100, control_ratio=0.2),
        ],
        balls,
        minimum_speed_pixels_per_second=45,
        maximum_prior_reception_seconds=3,
    )

    assert [event.completion_seconds for event in events] == [1.0, 2.4, 4.0]


def test_first_pass_after_turnover_is_recovered_between_co_visible_players() -> None:
    turnover = PredictedEvent(
        "turnover_candidate", 0.4, "red", 10, 115, 0.8, "turnover", 1.0
    )
    outgoing = PredictedEvent(
        "pass_candidate", 3.2, "black", 49, 10, 0.8, "flight", 3.6
    )

    events = infer_post_turnover_first_pass(
        [turnover, outgoing],
        [
            observation(1.0, "black", 115, 100, 100, control_ratio=0.2),
            observation(1.6, "black", 115, 110, 110, control_ratio=0.4),
            observation(1.8, "black", 49, 130, 120, control_ratio=0.7),
            observation(2.0, "black", 49, 135, 125, control_ratio=0.3),
        ],
        co_visible_track_pairs={frozenset((49, 115))},
    )

    assert [
        (event.event_type, event.clip_seconds, event.completion_seconds)
        for event in events
    ] == [
        ("turnover_candidate", 0.4, 1.0),
        ("pass_candidate", 1.6, 1.8),
        ("pass_candidate", 3.2, 3.6),
    ]


def test_post_turnover_pass_is_not_inferred_when_first_owner_returns() -> None:
    turnover = PredictedEvent(
        "turnover_candidate", 0.4, "red", 10, 115, 0.8, "turnover", 1.0
    )
    outgoing = PredictedEvent(
        "pass_candidate", 3.2, "black", 49, 10, 0.8, "flight", 3.6
    )

    events = infer_post_turnover_first_pass(
        [turnover, outgoing],
        [
            observation(1.0, "black", 115, 100, 100, control_ratio=0.2),
            observation(1.6, "black", 115, 110, 110, control_ratio=0.4),
            observation(1.8, "black", 49, 130, 120, control_ratio=0.7),
            observation(2.2, "black", 115, 140, 130, control_ratio=0.8),
        ],
        co_visible_track_pairs={frozenset((49, 115))},
    )

    assert events == [turnover, outgoing]


def test_unobserved_chain_contact_anchors_team_when_local_jersey_is_wrong() -> None:
    prior = PredictedEvent(
        "pass_candidate", 0.4, "black", 1, 2, 0.8, "prior", 1.0
    )
    following = PredictedEvent(
        "pass_candidate", 6.0, "black", 3, 4, 0.8, "following", 7.0
    )
    balls = {
        60: [
            {"track_id": 1, "source_frame": 60, "clip_seconds": 2.4, "x": 0, "y": 0}
        ],
        65: [
            {
                "track_id": 1,
                "source_frame": 65,
                "clip_seconds": 2.6,
                "x": 100,
                "y": 0,
            }
        ],
        70: [
            {"track_id": 1, "source_frame": 70, "clip_seconds": 2.8, "x": 0, "y": 0}
        ],
    }

    events = infer_unobserved_chain_contacts(
        [prior, following],
        [observation(2.6, "red", 5, 100, 100, control_ratio=0.2)],
        balls,
        minimum_speed_pixels_per_second=45,
    )

    assert [event.completion_seconds for event in events] == [1.0, 2.6, 7.0]
    assert events[1].team == "black"


def test_unobserved_chain_contacts_use_confirmed_segment_end_control() -> None:
    prior = PredictedEvent(
        "pass_candidate", 0.4, "black", 1, 2, 0.8, "prior", 1.0
    )
    balls = {
        60: [
            {"track_id": 1, "source_frame": 60, "clip_seconds": 2.4, "x": 0, "y": 0}
        ],
        65: [
            {
                "track_id": 1,
                "source_frame": 65,
                "clip_seconds": 2.6,
                "x": 100,
                "y": 0,
            }
        ],
        70: [
            {"track_id": 1, "source_frame": 70, "clip_seconds": 2.8, "x": 0, "y": 0}
        ],
    }

    events = infer_unobserved_chain_contacts(
        [prior],
        [
            observation(2.6, "black", 5, 100, 100, control_ratio=0.2),
            observation(6.6, "black", 6, 100, 100, control_ratio=0.3),
        ],
        balls,
        minimum_speed_pixels_per_second=45,
        segment_end_seconds=7.0,
    )

    assert [event.completion_seconds for event in events] == [1.0, 2.6]


def test_unobserved_chain_contact_rejects_opponent_track() -> None:
    prior = PredictedEvent(
        "pass_candidate", 0.4, "black", 1, 2, 0.8, "prior", 1.0
    )
    following = PredictedEvent(
        "pass_candidate", 6.8, "black", 3, 4, 0.8, "following", 7.0
    )
    balls = {
        60: [
            {"track_id": 1, "source_frame": 60, "clip_seconds": 2.4, "x": 0, "y": 0}
        ],
        65: [
            {
                "track_id": 1,
                "source_frame": 65,
                "clip_seconds": 2.6,
                "x": 100,
                "y": 0,
            }
        ],
        70: [
            {"track_id": 1, "source_frame": 70, "clip_seconds": 2.8, "x": 0, "y": 0}
        ],
    }
    players = {
        frame: [
            {
                "track_id": 5,
                "clip_seconds": seconds,
                "color_scores": {"white": 0.4, "warm": 0.2},
            }
        ]
        for frame, seconds in [(65, 2.6), (70, 2.8), (75, 3.0)]
    }

    events = infer_unobserved_chain_contacts(
        [prior, following],
        [observation(2.6, "black", 5, 100, 100, control_ratio=0.2)],
        balls,
        players=players,
        minimum_speed_pixels_per_second=45,
    )

    assert events == [prior, following]


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


def test_ball_flight_does_not_treat_single_frame_teammate_proximity_as_control() -> None:
    segments = build_possession_segments(
        [
            observation(1.0, "black", 1, 100, 100),
            observation(1.2, "black", 1, 105, 105),
            observation(2.0, "black", 2, 200, 200, control_ratio=0.1),
            observation(2.8, "red", 3, 300, 300, control_ratio=0.3),
            observation(3.0, "red", 3, 305, 305, control_ratio=0.3),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    balls = {
        25: [
            {
                "track_id": 1,
                "source_frame": 25,
                "clip_seconds": 1.0,
                "x": 100,
                "y": 100,
            }
        ],
        30: [
            {
                "track_id": 1,
                "source_frame": 30,
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

    assert [(event.event_type, event.to_player_track_id) for event in events] == [
        ("turnover_candidate", 3)
    ]


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


def test_team_smoothing_preserves_repeated_causal_team_control() -> None:
    observations = [
        observation(1.0, "black", 1, 100, 100, control_ratio=0.6),
        observation(1.2, "red", 2, 105, 105, control_ratio=0.45),
        observation(1.4, "red", 2, 106, 106, control_ratio=0.45),
        observation(1.6, "red", 2, 107, 107, control_ratio=0.7),
        observation(1.8, "black", 3, 108, 108, control_ratio=0.1),
    ]

    smoothed = _smooth_teams(observations, 1.0)

    assert [
        (item.clip_seconds, item.team, item.player_track_id)
        for item in smoothed
    ] == [
        (1.0, "black", 1),
        (1.4, "red", 2),
        (1.6, "red", 2),
        (1.8, "black", 3),
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


def test_in_field_restart_does_not_create_boundary_turnover() -> None:
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
                "stoppage_kind": "stationary_ball_restart",
            }
        ],
        segments,
    )

    assert events == []


def test_restart_remains_pending_while_player_repositions_ball() -> None:
    setup = build_possession_segments(
        [
            observation(22.6, "black", 104, 100, 100),
            observation(23.2, "black", 104, 102, 100),
            observation(23.8, "black", 104, 104, 100),
            observation(24.2, "black", 104, 106, 100),
        ],
        segment_gap_seconds=0.7,
        identity_switch_radius_heights=0,
    )
    intervals = [
        {
            "start_seconds": 19.4,
            "end_seconds": 21.2,
            "duration_seconds": 1.8,
            "play_resumed_seconds": 21.2,
            "stoppage_kind": "stationary_ball_restart",
            "movement_evidence": {},
        }
    ]

    ball_points = [
        {"clip_seconds": 22.6, "x": 0, "y": 0},
        {"clip_seconds": 22.8, "x": 10, "y": 0},
        {"clip_seconds": 23.0, "x": 12, "y": 0},
        {"clip_seconds": 23.2, "x": 14, "y": 0},
        {"clip_seconds": 23.4, "x": 44, "y": 0},
        {"clip_seconds": 25.0, "x": 44, "y": 0},
        {"clip_seconds": 25.2, "x": 54, "y": 0},
        {"clip_seconds": 25.4, "x": 64, "y": 0},
        {"clip_seconds": 25.6, "x": 70, "y": 0},
        {"clip_seconds": 25.8, "x": 130, "y": 0},
        {"clip_seconds": 26.0, "x": 160, "y": 0},
    ]

    extended = extend_restarts_through_ball_setup(
        intervals, setup, ball_points
    )

    assert extended[0]["play_resumed_seconds"] == 25.6
    assert (
        extended[0]["movement_evidence"][
            "discarded_repositioning_release_seconds"
        ]
        == 21.2
    )


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


def test_pass_after_confirmed_post_reentry_control_is_not_restart_release() -> None:
    event = PredictedEvent(
        "pass_candidate",
        3.6,
        "black",
        8,
        31,
        0.65,
        "flight",
        4.8,
    )
    interval = {
        "start_seconds": 1.28,
        "resumed_seconds": 2.52,
        "play_resumed_seconds": 3.6,
        "starts_outside": False,
    }

    assert _event_released_outside(event, [interval]) is True
    assert (
        _event_released_outside(
            event,
            [interval],
            [observation(3.4, "black", 8, 100, 100)],
        )
        is False
    )


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


def test_opening_same_team_restart_does_not_create_turnover() -> None:
    segments = build_possession_segments(
        [
            observation(0.4, "black", 8, 100, 100),
            observation(1.2, "black", 8, 102, 102),
            observation(4.8, "black", 31, 300, 300),
            observation(5.0, "black", 31, 302, 302),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    interval = {
        "start_seconds": 1.28,
        "duration_seconds": 1.2,
        "play_resumed_seconds": 2.52,
        "starts_outside": False,
    }

    assert infer_boundary_turnovers(
        [interval],
        segments,
        startup_restart_max_seconds=4.0,
    ) == []


def test_opening_same_team_restart_creates_completed_restart_pass() -> None:
    segments = build_possession_segments(
        [
            observation(0.4, "black", 8, 100, 100),
            observation(1.2, "black", 8, 102, 102),
            observation(4.8, "black", 31, 300, 300),
            observation(5.0, "black", 31, 302, 302),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    interval = {
        "start_seconds": 1.28,
        "end_seconds": 2.48,
        "duration_seconds": 1.2,
        "resumed_seconds": 2.52,
        "play_resumed_seconds": 3.6,
        "starts_outside": False,
    }
    balls = {
        60: [{"clip_seconds": 2.4, "x": 100, "y": 100}],
        65: [{"clip_seconds": 2.6, "x": 142, "y": 100}],
        70: [{"clip_seconds": 2.8, "x": 144, "y": 100}],
    }

    events = infer_restart_passes(
        [interval],
        segments,
        balls=balls,
        startup_restart_max_seconds=4.0,
    )

    assert [(event.team, event.event_type) for event in events] == [
        ("black", "restart_pass_candidate")
    ]
    assert events[0].clip_seconds == 2.48
    assert events[0].completion_seconds == 2.6


def test_upper_body_boundary_control_detects_mid_segment_throw_in() -> None:
    segments = build_possession_segments(
        [
            observation(10.8, "black", 8, 100, 100, ball_y=55),
            observation(11.0, "black", 8, 102, 102, ball_y=50),
            observation(14.8, "black", 31, 300, 300),
            observation(15.0, "black", 31, 302, 302),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    interval = {
        "start_seconds": 11.28,
        "end_seconds": 12.48,
        "duration_seconds": 1.2,
        "resumed_seconds": 12.52,
        "play_resumed_seconds": 12.8,
        "starts_outside": False,
    }

    assert infer_boundary_turnovers([interval], segments) == []
    events = infer_restart_passes([interval], segments)

    assert [(event.team, event.event_type) for event in events] == [
        ("black", "restart_pass_candidate")
    ]


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


def test_restart_uses_first_raw_control_when_stable_team_is_wrong() -> None:
    segments = build_possession_segments(
        [
            observation(30.0, "black", 1, 100, 100),
            observation(30.2, "black", 1, 102, 102),
            observation(35.0, "red", 3, 300, 300),
            observation(35.2, "red", 3, 302, 302),
        ],
        segment_gap_seconds=0.5,
        identity_switch_radius_heights=0,
    )
    interval = {
        "start_seconds": 31.0,
        "end_seconds": 33.0,
        "resumed_seconds": 33.2,
        "play_resumed_seconds": 33.8,
        "starts_outside": False,
    }

    events = infer_restart_passes(
        [interval],
        segments,
        control_observations=[
            observation(34.4, "black", 2, 220, 220),
            observation(34.6, "black", 2, 222, 222),
            observation(34.8, "red", 3, 300, 300),
        ],
    )

    assert len(events) == 1
    assert events[0].team == "black"
    assert events[0].to_player_track_id == 2


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


def test_same_receiver_and_completion_counts_as_one_pass() -> None:
    first = PredictedEvent(
        "pass_candidate", 6.8, "black", 25, 8, 0.7, "first release", 8.8
    )
    duplicate = PredictedEvent(
        "pass_candidate", 8.6, "black", 44, 8, 0.6, "brief owner", 8.8
    )

    assert _deduplicate_receptions([first, duplicate]) == [first]


def test_same_receiver_on_different_frames_remains_two_passes() -> None:
    first = PredictedEvent(
        "pass_candidate", 6.8, "black", 25, 8, 0.7, "first reception", 8.8
    )
    later = PredictedEvent(
        "pass_candidate", 8.9, "black", 44, 8, 0.6, "later reception", 9.0
    )

    assert _deduplicate_receptions([first, later]) == [first, later]


def test_same_sender_reception_keeps_existing_quarter_second_deduplication() -> None:
    first = PredictedEvent(
        "pass_candidate", 6.2, "black", 46, 58, 0.9, "early flight", 8.0
    )
    refined = PredictedEvent(
        "pass_candidate", 7.4, "black", 46, 58, 0.87, "later flight", 8.2
    )

    assert _deduplicate_receptions([first, refined]) == [refined]


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


def test_startup_guard_requires_controlled_sender_at_release() -> None:
    unsupported = PredictedEvent(
        "pass_candidate", 0.6, "black", 17, 49, 0.6, "startup", 3.4
    )
    observations = [
        observation(0.6, "black", 17, 100, 100, control_ratio=0.8),
        observation(3.4, "black", 49, 200, 200, control_ratio=0.2),
    ]

    assert filter_ambiguous_startup_transfers(
        [unsupported],
        observations,
        startup_guard_seconds=4.0,
        maximum_receiver_control_ratio=1.2,
    ) == []


def test_startup_guard_accepts_recent_control_before_inferred_release() -> None:
    supported = PredictedEvent(
        "pass_candidate", 2.4, "black", 15, 6, 0.9, "flight", 3.6
    )
    observations = [
        observation(2.0, "black", 15, 100, 100, control_ratio=0.2),
        observation(3.6, "black", 6, 300, 300, control_ratio=0.2),
    ]

    assert filter_ambiguous_startup_transfers(
        [supported],
        observations,
        startup_guard_seconds=4.0,
        maximum_receiver_control_ratio=1.2,
    ) == [supported]


def test_live_opening_delivery_completes_at_first_controlled_touch() -> None:
    first = PossessionSegment(
        "black",
        15,
        [
            observation(0.8, "black", 15, 100, 100, control_ratio=0.4),
            observation(1.0, "black", 15, 100, 110, control_ratio=0.2),
            observation(1.2, "black", 15, 100, 100, control_ratio=0.3),
        ],
    )
    following = PossessionSegment(
        "black",
        6,
        [
            observation(2.0, "black", 6, 300, 300, control_ratio=0.2),
            observation(2.2, "black", 6, 302, 302, control_ratio=0.2),
        ],
    )
    balls = {
        20: [{"track_id": 1, "source_frame": 20, "clip_seconds": 0.8,
              "x": 100, "y": 100}],
        25: [{"track_id": 1, "source_frame": 25, "clip_seconds": 1.0,
              "x": 110, "y": 100}],
        30: [{"track_id": 1, "source_frame": 30, "clip_seconds": 1.2,
              "x": 100, "y": 100}],
    }

    events = infer_opening_live_reception(
        [],
        [first, following],
        balls,
        build_match_state_timeline([], duration_seconds=5.0),
        minimum_speed_pixels_per_second=45,
        maximum_transfer_seconds=3.0,
    )

    assert [(event.team, event.completion_seconds) for event in events] == [
        ("black", 1.0)
    ]


def test_sparse_direction_change_recovers_supported_pass() -> None:
    observations = [
        observation(16.0, "black", 94, 100, 100, control_ratio=0.8),
        observation(17.4, "black", 94, 110, 110, control_ratio=0.7),
        observation(18.2, "red", 7, 200, 200, control_ratio=1.2),
        observation(19.2, "black", 87, 300, 300, control_ratio=0.8),
    ]
    balls = {
        475: [{"track_id": 1, "source_frame": 475, "clip_seconds": 19.0,
               "x": 290, "y": 300}],
        480: [{"track_id": 1, "source_frame": 480, "clip_seconds": 19.2,
               "x": 300, "y": 300}],
        485: [{"track_id": 1, "source_frame": 485, "clip_seconds": 19.4,
               "x": 290, "y": 300}],
    }

    events = infer_sparse_control_transfer(
        [],
        observations,
        balls,
        co_visible_track_pairs=[frozenset((94, 87))],
        minimum_speed_pixels_per_second=45,
    )

    assert [(event.team, event.completion_seconds) for event in events] == [
        ("black", 19.2)
    ]


def test_missing_turnover_receiver_can_anchor_first_pass() -> None:
    turnover = PredictedEvent(
        "turnover_candidate", 39.2, "black", None, None, 0.6, "turnover", 39.2
    )
    outgoing = PredictedEvent(
        "pass_candidate", 41.4, "red", 107, 229, 0.7, "pass", 42.8
    )
    observations = [
        observation(39.6, "red", 173, 100, 100, control_ratio=0.6),
        observation(40.6, "red", 107, 250, 250, control_ratio=0.4),
    ]

    events = infer_post_turnover_first_pass(
        [turnover, outgoing],
        observations,
        co_visible_track_pairs=[frozenset((173, 107))],
    )

    assert any(
        event.event_type == "pass_candidate"
        and event.from_player_track_id == 173
        and event.to_player_track_id == 107
        and event.completion_seconds == 40.6
        for event in events
    )


def test_high_speed_teammate_contact_splits_one_touch_relay() -> None:
    event = PredictedEvent(
        "pass_candidate", 44.4, "red", 229, 150, 0.9, "flight", 46.0
    )
    balls = {
        1115: [{"track_id": 1, "source_frame": 1115, "clip_seconds": 44.6,
                "x": 100, "y": 100}],
        1120: [{"track_id": 1, "source_frame": 1120, "clip_seconds": 44.8,
                "x": 200, "y": 100}],
        1125: [{"track_id": 1, "source_frame": 1125, "clip_seconds": 45.0,
                "x": 360, "y": 100}],
    }
    players = {
        1120: [{
            "track_id": 5,
            "team": "red",
            "x1": 175,
            "y1": 40,
            "x2": 225,
            "y2": 100,
        }]
    }

    events = split_acceleration_confirmed_one_touch_passes(
        [event],
        players,
        balls,
        minimum_speed_pixels_per_second=45,
    )

    assert [item.completion_seconds for item in events] == [44.8, 46.0]
    assert events[1].from_player_track_id == 5


def test_terminal_brief_reception_precedes_challenged_transition() -> None:
    previous = PredictedEvent(
        "pass_candidate", 56.2, "red", None, 194, 0.55, "pass", 56.2
    )
    observations = [
        observation(57.0, "red", 194, 100, 100, control_ratio=0.3),
        observation(58.6, "black", 254, 200, 200, control_ratio=0.7),
    ]
    balls = {
        1455: [{"track_id": 1, "source_frame": 1455, "clip_seconds": 58.2,
                "x": 200, "y": 100}]
    }
    players = {
        1455: [{
            "track_id": 306,
            "team": "red",
            "x1": 175,
            "y1": 40,
            "x2": 225,
            "y2": 100,
        }]
    }

    events = infer_terminal_brief_reception(
        [previous],
        observations,
        players,
        balls,
        segment_end_seconds=60.0,
    )

    assert [event.completion_seconds for event in events] == [56.2, 58.2]


def test_delayed_first_flight_recovers_reception_and_turnover() -> None:
    receiver = {
        "track_id": 4,
        "team": "red",
        "x1": 95,
        "y1": 50,
        "x2": 105,
        "y2": 100,
    }
    balls = {
        0: [{"track_id": 1, "source_frame": 0, "clip_seconds": 0.0,
             "x": 0, "y": 100}],
        5: [{"track_id": 1, "source_frame": 5, "clip_seconds": 0.2,
             "x": 30, "y": 100}],
        10: [{"track_id": 1, "source_frame": 10, "clip_seconds": 0.4,
              "x": 60, "y": 100}],
        15: [{"track_id": 1, "source_frame": 15, "clip_seconds": 0.6,
              "x": 90, "y": 100}],
        20: [{"track_id": 1, "source_frame": 20, "clip_seconds": 0.8,
              "x": 100, "y": 100}],
    }
    opponent = PossessionSegment(
        "black",
        8,
        [
            observation(1.2, "black", 8, 120, 120, control_ratio=0.3),
            observation(1.4, "black", 8, 122, 122, control_ratio=0.2),
        ],
    )

    events = infer_delayed_first_flight_reception(
        [],
        [],
        [opponent],
        {15: [receiver]},
        balls,
        build_match_state_timeline([], duration_seconds=2.0),
        minimum_speed_pixels_per_second=45,
        minimum_flight_seconds=0.4,
    )

    assert [
        (event.event_type, event.team, event.completion_seconds)
        for event in events
    ] == [
        ("pass_candidate", "red", 0.6),
        ("turnover_candidate", "red", 1.2),
    ]


def test_short_co_visible_control_transfer_recovers_pass() -> None:
    sender = PossessionSegment(
        "black",
        8,
        [
            observation(1.0, "black", 8, 100, 100, control_ratio=0.8),
            observation(1.2, "black", 8, 100, 100, control_ratio=0.4),
        ],
    )
    receiver = PossessionSegment(
        "black",
        13,
        [
            observation(1.8, "black", 13, 110, 110, control_ratio=0.3),
            observation(2.0, "black", 13, 112, 112, control_ratio=0.4),
            observation(2.2, "black", 13, 114, 114, control_ratio=0.3),
        ],
    )
    duplicate_receiver = PossessionSegment(
        "black",
        13,
        [observation(1.4, "black", 13, 105, 105, control_ratio=0.3)],
    )
    duplicate_sender = PossessionSegment(
        "black",
        8,
        [observation(1.6, "black", 8, 108, 108, control_ratio=0.2)],
    )

    events = infer_short_controlled_teammate_transfers(
        [],
        [sender, duplicate_receiver, duplicate_sender, receiver],
        co_visible_track_pairs={frozenset((8, 13))},
        minimum_transfer_heights=0.5,
    )

    assert [(event.team, event.completion_seconds) for event in events] == [
        ("black", 1.8)
    ]


def test_brief_locally_same_team_turnover_pair_becomes_pass() -> None:
    events = [
        PredictedEvent(
            "turnover_candidate", 1.0, "black", 8, 13, 0.7, "turnover", 2.0
        ),
        PredictedEvent(
            "turnover_candidate", 2.4, "red", 13, 21, 0.7, "turnover", 3.0
        ),
    ]
    controls = [
        observation(3.0, "black", 21, 200, 200, control_ratio=0.3)
    ]
    players = {
        frame: [
            {
                "track_id": 13,
                "team": "red",
                "clip_seconds": seconds,
                "color_scores": {"dark": 0.8, "white": 0.0, "warm": 0.0},
            }
        ]
        for frame, seconds in [(45, 1.8), (50, 2.0), (55, 2.2)]
    }

    reconciled = reconcile_brief_opponent_turnover_pairs(
        events,
        controls,
        players,
    )

    assert [
        (event.event_type, event.team, event.completion_seconds)
        for event in reconciled
    ] == [("pass_candidate", "black", 3.0)]


def test_sharp_locally_same_team_contact_splits_long_pass() -> None:
    event = PredictedEvent(
        "pass_candidate", 1.0, "black", 8, 21, 0.8, "pass", 4.0
    )
    balls = {
        45: [{"track_id": 1, "source_frame": 45, "clip_seconds": 1.8,
              "x": 0, "y": 100}],
        50: [{"track_id": 1, "source_frame": 50, "clip_seconds": 2.0,
              "x": 100, "y": 100}],
        55: [{"track_id": 1, "source_frame": 55, "clip_seconds": 2.2,
              "x": 0, "y": 100}],
    }
    players = {
        frame: [
            {
                "track_id": 13,
                "team": "red",
                "clip_seconds": seconds,
                "x1": 90,
                "y1": 50,
                "x2": 110,
                "y2": 100,
                "color_scores": {"dark": 0.8, "white": 0.0, "warm": 0.0},
            }
        ]
        for frame, seconds in [(45, 1.8), (50, 2.0), (55, 2.2)]
    }

    events = split_sharp_direction_change_passes(
        [event],
        players,
        balls,
        minimum_speed_pixels_per_second=45,
    )

    assert [
        (item.from_player_track_id, item.to_player_track_id,
         item.clip_seconds, item.completion_seconds)
        for item in events
    ] == [
        (8, 13, 1.0, 2.0),
        (13, 21, 2.0, 4.0),
    ]


def test_competing_same_sender_receptions_keep_stronger_interpretation() -> None:
    weaker = PredictedEvent(
        "pass_candidate", 30.4, "black", 113, 173, 0.63, "direction", 32.0
    )
    stronger = PredictedEvent(
        "pass_candidate", 31.0, "black", 113, 171, 0.9, "flight", 31.6
    )

    assert collapse_competing_same_sender_receptions(
        [weaker, stronger]
    ) == [stronger]


def test_weak_reception_moves_to_terminal_close_control() -> None:
    receiver = PossessionSegment(
        "black",
        20,
        [
            observation(1.4, "black", 20, 100, 100, control_ratio=1.7),
            observation(1.6, "black", 20, 101, 100, control_ratio=1.2),
            observation(1.8, "black", 20, 102, 100, control_ratio=0.8),
            observation(2.0, "black", 20, 103, 100, control_ratio=0.4),
        ],
    )
    event = PredictedEvent(
        "pass_candidate", 1.0, "black", 10, 20, 0.7, "flight", 1.4
    )

    refined = refine_weak_reception_completion_times([event], [receiver])

    assert refined[0].completion_seconds == 2.0
    assert "first clear controlled touch" in refined[0].details


def test_duplicate_player_track_handoffs_do_not_create_passes() -> None:
    def point(
        frame: int,
        seconds: float,
        track_id: int,
        team: str,
        x1: float,
        x2: float,
    ) -> dict[str, object]:
        return {
            "source_frame": frame,
            "clip_seconds": seconds,
            "track_id": track_id,
            "team": team,
            "x1": x1,
            "y1": 100,
            "x2": x2,
            "y2": 200,
        }

    events = [
        PredictedEvent(
            "pass_candidate", 1.0, "black", 10, 11, 0.7, "transfer", 1.2
        ),
        PredictedEvent(
            "pass_candidate", 2.0, "red", 20, 21, 0.7, "transfer", 2.2
        ),
        PredictedEvent(
            "pass_candidate", 3.0, "black", 30, 31, 0.7, "transfer", 3.4
        ),
    ]
    players = {
        20: [point(20, 0.8, 10, "black", 98, 148)],
        25: [
            point(25, 1.0, 10, "black", 100, 150),
            point(25, 1.0, 11, "red", 101, 149),
        ],
        30: [
            point(30, 1.2, 10, "black", 103, 153),
            point(30, 1.2, 11, "black", 104, 152),
        ],
        50: [point(50, 2.0, 20, "red", 200, 250)],
        55: [
            point(55, 2.2, 20, "red", 202, 252),
            point(55, 2.2, 21, "red", 203, 251),
        ],
        60: [point(60, 2.4, 21, "red", 205, 255)],
        75: [
            point(75, 3.0, 30, "black", 300, 350),
            point(75, 3.0, 31, "black", 370, 420),
        ],
        85: [
            point(85, 3.4, 30, "black", 320, 370),
            point(85, 3.4, 31, "black", 390, 440),
        ],
    }

    filtered = suppress_duplicate_track_handoff_passes(events, players)

    assert [event.from_player_track_id for event in filtered] == [30]


def test_noncausal_reception_requires_reciprocal_return_evidence() -> None:
    source = [
        PredictedEvent(
            "pass_candidate",
            1.0,
            "black",
            10,
            20,
            0.8,
            "Initial completed pass.",
            1.4,
        ),
        PredictedEvent(
            "pass_candidate",
            2.0,
            "black",
            20,
            10,
            0.7,
            "Ball release followed by black control after -0.20s.",
            2.4,
        ),
        PredictedEvent(
            "pass_candidate",
            4.0,
            "red",
            30,
            40,
            0.7,
            "Ball release followed by red control after -0.20s.",
            4.4,
        ),
    ]

    filtered = suppress_noncausal_nonreturn_passes(source)

    assert [
        (event.from_player_track_id, event.to_player_track_id)
        for event in filtered
    ] == [(10, 20), (20, 10)]


def test_completed_pass_establishes_prior_losing_team_turnover() -> None:
    prior_owner = PossessionSegment(
        "red",
        14,
        [
            observation(14.8, "red", 14, 100, 100, control_ratio=0.4),
            observation(15.2, "red", 14, 110, 100, control_ratio=0.3),
        ],
    )
    controls = [
        *prior_owner.observations,
        observation(16.0, "black", 94, 130, 100, control_ratio=0.8),
        observation(17.2, "black", 94, 140, 100, control_ratio=1.0),
        observation(17.4, "black", 94, 145, 100, control_ratio=0.75),
    ]
    completed_pass = PredictedEvent(
        "pass_candidate",
        17.4,
        "black",
        94,
        87,
        0.6,
        "Sparse same-team control confirmed the pass.",
        19.2,
    )

    events = infer_pass_sender_established_turnovers(
        [completed_pass],
        [prior_owner],
        controls,
        maximum_transfer_seconds=3.0,
    )

    turnover = next(
        event for event in events if event.event_type == "turnover_candidate"
    )
    assert turnover.team == "red"
    assert turnover.from_player_track_id == 14
    assert turnover.to_player_track_id == 94
    assert turnover.clip_seconds == 15.2
    assert turnover.completion_seconds == 17.4


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


def test_transfer_merge_keeps_adjacent_chain_passes_with_nearby_releases() -> None:
    incoming = PredictedEvent(
        "pass_candidate", 41.0, "black", 10, 232, 0.85, "flight", 41.2
    )
    outgoing = PredictedEvent(
        "pass_candidate", 41.6, "black", 232, 10, 0.65, "segment", 42.4
    )

    merged = merge_transfer_events(
        [incoming],
        [outgoing],
        deduplication_seconds=0.8,
    )

    assert merged == [incoming, outgoing]


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
