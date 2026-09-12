from football_poc.match_initialization import (
    MatchInitialization,
    TeamDirection,
    TrackInitializationEvidence,
    detect_halftime_side_switch,
    infer_match_initialization,
)


def evidence(
    track_id: int,
    color_bgr: tuple[int, int, int],
    x: float,
    *,
    duration: float = 20.0,
) -> TrackInitializationEvidence:
    return TrackInitializationEvidence(
        track_id=track_id,
        color_bgr=color_bgr,
        sample_count=8,
        start_seconds=0.0,
        end_seconds=duration,
        normalized_positions=tuple((x, 0.55) for _ in range(8)),
    )


def test_initialization_discovers_teams_goalkeepers_official_and_directions() -> None:
    tracks = [
        evidence(1, (205, 55, 30), 0.32),
        evidence(2, (198, 50, 35), 0.38),
        evidence(3, (210, 60, 28), 0.43),
        evidence(4, (195, 48, 32), 0.46),
        evidence(5, (225, 225, 225), 0.56),
        evidence(6, (215, 220, 225), 0.61),
        evidence(7, (230, 225, 220), 0.66),
        evidence(8, (218, 218, 218), 0.7),
        evidence(9, (30, 220, 225), 0.1),
        evidence(10, (35, 35, 210), 0.9),
        evidence(11, (25, 25, 25), 0.52),
    ]

    result = infer_match_initialization(
        tracks,
        half=1,
        source_start_seconds=0.0,
        starts_at_kickoff=True,
    )

    assert result.status == "complete"
    assert {team.team for team in result.teams} == {"blue", "white"}
    assert result.official_track_ids == (11,)
    assert {goalkeeper.track_id for goalkeeper in result.goalkeepers} == {9, 10}
    directions = {
        direction.team: direction.attacks_towards
        for direction in result.directions
    }
    assert directions == {"blue": "right", "white": "left"}


def test_initialization_abstains_from_direction_for_mid_half_segment() -> None:
    tracks = [
        evidence(1, (205, 55, 30), 0.3),
        evidence(2, (198, 50, 35), 0.4),
        evidence(3, (210, 60, 28), 0.45),
        evidence(4, (195, 48, 32), 0.48),
        evidence(5, (225, 225, 225), 0.55),
        evidence(6, (215, 220, 225), 0.6),
        evidence(7, (230, 225, 220), 0.65),
        evidence(8, (218, 218, 218), 0.7),
    ]

    result = infer_match_initialization(
        tracks,
        half=1,
        source_start_seconds=1267.04,
        starts_at_kickoff=False,
    )

    assert result.status == "partial"
    assert result.directions == ()
    assert "segment_does_not_begin_at_kickoff" in result.abstention_reasons


def test_initialization_abstains_when_kits_are_ambiguous() -> None:
    tracks = [
        evidence(index, (120 + index, 120 + index, 120 + index), 0.5)
        for index in range(1, 7)
    ]

    result = infer_match_initialization(
        tracks,
        half=1,
        source_start_seconds=0.0,
        starts_at_kickoff=True,
    )

    assert result.status == "abstained"
    assert result.teams == ()
    assert result.abstention_reasons == (
        "two_outfield_kit_clusters_not_confident",
    )


def test_halftime_switch_requires_both_teams_to_change_defended_goal() -> None:
    first = MatchInitialization(
        half=1,
        source_start_seconds=0.0,
        starts_at_kickoff=True,
        status="complete",
        teams=(),
        official_track_ids=(),
        goalkeepers=(),
        directions=(
            TeamDirection("blue", "left", "right", 0.9),
            TeamDirection("white", "right", "left", 0.9),
        ),
        abstention_reasons=(),
    )
    second = MatchInitialization(
        half=2,
        source_start_seconds=0.0,
        starts_at_kickoff=True,
        status="complete",
        teams=(),
        official_track_ids=(),
        goalkeepers=(),
        directions=(
            TeamDirection("blue", "right", "left", 0.9),
            TeamDirection("white", "left", "right", 0.9),
        ),
        abstention_reasons=(),
    )

    assert detect_halftime_side_switch(first, second) is True
