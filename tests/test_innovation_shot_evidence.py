from __future__ import annotations

import json
from pathlib import Path

import pytest

from football_poc.innovation_day_snapshot import shots_on_target as sot
from football_poc.innovation_day_snapshot.goal_calibration import (
    GoalCalibrationError,
    MONOCULAR_DEPTH_MARGIN_M,
    build_goal_face,
    load_goal_faces,
)
from football_poc.innovation_day_snapshot.shot_evidence_adapter import (
    attacking_goals,
    build_evidence,
)


# Synthetic static camera: right goal mouth 150px wide, 60px tall.
RIGHT_MOUTH = [[3560, 786], [3580, 726], [3730, 726], [3710, 786]]
RIGHT_LINE = [[3400, 786], [3900, 786]]
LEFT_MOUTH = [[700, 786], [720, 726], [870, 726], [850, 786]]
LEFT_LINE = [[500, 786], [1000, 786]]
AFFILIATIONS = {"affiliations": [{"goal": "left", "team": "black"}]}


def calibration_file(tmp_path: Path) -> Path:
    path = tmp_path / "pitch-calibration.json"
    path.write_text(json.dumps({
        "camera_id": "synthetic",
        "features": {
            "right_goal_mouth": RIGHT_MOUTH,
            "right_goal_line": RIGHT_LINE,
            "left_goal_mouth": LEFT_MOUTH,
            "left_goal_line": LEFT_LINE,
        },
    }), encoding="utf-8")
    return path


def ball_tracks(points: list[tuple[float, float, float]]) -> dict:
    return {"tracks": [{"points": [
        {"source_frame": round(t * 25), "clip_seconds": t, "x": x, "y": y}
        for t, x, y in points
    ]}]}


def player(track_id: int, team: str, role: str, points: list[tuple[float, float, float]]) -> dict:
    return {"track_id": track_id, "team": team, "role": role, "points": [
        {"source_frame": round(t * 25), "clip_seconds": t,
         "x1": x - 10, "x2": x + 10, "y1": y - 60, "y2": y, "team": team}
        for t, x, y in points
    ]}


def shot_path(end_x: float, end_y: float) -> list[tuple[float, float, float]]:
    start_x, start_y = 3200.0, 900.0
    flight = [
        (10.0 + 0.2 * step,
         start_x + (end_x - start_x) * step / 5,
         start_y + (end_y - start_y) * step / 5)
        for step in range(6)
    ]
    rest = [(11.0 + 0.2 * step, end_x + step, end_y) for step in range(1, 16)]
    return flight + rest


def build(tmp_path: Path, path, players) -> dict:
    faces, provenance = load_goal_faces(calibration_file(tmp_path))
    return build_evidence(
        ball_tracks=ball_tracks(path),
        player_tracks={"tracks": players},
        affiliations=AFFILIATIONS,
        faces=faces,
        calibration_provenance=provenance,
    )


def classify(evidence: dict, match_state: dict | None = None) -> list[sot.Attempt]:
    return sot.classify_attempts(
        sot.parse_evidence(evidence),
        match_state or {"initial_state": "in_play", "intervals": [
            {"state": "in_play", "start_seconds": 0.0, "end_seconds": 30.0}]},
        duration_seconds=30.0,
    )


def test_goal_face_maps_frame_corners_to_law_one_dimensions(tmp_path: Path) -> None:
    faces, provenance = load_goal_faces(calibration_file(tmp_path))
    right = faces["right"]
    assert right.post_y == (30.34, 37.66)
    assert right.project((3560, 786)) == pytest.approx((30.34, 0.0), abs=1e-3)
    assert right.project((3730, 726)) == pytest.approx((37.66, 2.44), abs=1e-3)
    assert right.image_distance((3645, 760)) < 0 < right.image_distance((3645, 700))
    assert right.uncertainty_m > MONOCULAR_DEPTH_MARGIN_M
    assert provenance["uncertainty_m"]["right"] == pytest.approx(right.uncertainty_m, abs=1e-3)


def test_goal_face_rejects_post_bases_off_the_goal_line() -> None:
    with pytest.raises(GoalCalibrationError):
        build_goal_face("right", [(3560, 700), (3580, 640), (3730, 640), (3710, 700)], RIGHT_LINE)


def test_attacking_direction_comes_from_static_goalkeeper_roles() -> None:
    assert attacking_goals(AFFILIATIONS) == {"black": "right", "red": "left"}
    assert attacking_goals({"affiliations": []}) == {}


def test_arrest_inside_goal_face_with_live_play_is_on_target(tmp_path: Path) -> None:
    evidence = build(tmp_path, shot_path(3645, 770), [
        player(8, "black", "player", [(10.0, 3200, 900)]),
    ])
    assert sot.readiness(evidence).status == "ready"
    assert [item["intent"] for item in evidence["releases"]] == ["scoring_attempt"]
    assert len(evidence["goal_face_arrivals"]) == 1
    (attempt,) = classify(evidence)
    assert (attempt.resolution, attempt.reason) == ("on_target", "stopped_at_goal_face")
    assert attempt.team == "black" and attempt.target_goal == "right"
    assert attempt.outcome_seconds == pytest.approx(11.0, abs=0.21)
    event = sot.attempt_event(attempt)
    assert event["confidence"] == 0.65


def test_arrest_followed_by_stoppage_is_not_counted_without_goal_evidence(tmp_path: Path) -> None:
    evidence = build(tmp_path, shot_path(3645, 770), [
        player(8, "black", "player", [(10.0, 3200, 900)]),
    ])
    stopped = {"initial_state": "in_play", "intervals": [
        {"state": "in_play", "start_seconds": 0.0, "end_seconds": 12.0},
        {"state": "restart_pending", "start_seconds": 12.0, "end_seconds": 30.0},
    ]}
    (attempt,) = classify(evidence, stopped)
    assert attempt.resolution == "unresolved"
    assert attempt.reason == "goal_entry_without_goal_confirmation"


def test_arrest_beside_the_frame_then_out_of_play_is_off_target(tmp_path: Path) -> None:
    evidence = build(tmp_path, shot_path(3755, 760), [
        player(8, "black", "player", [(10.0, 3200, 900)]),
    ])
    stopped = {"initial_state": "in_play", "intervals": [
        {"state": "in_play", "start_seconds": 0.0, "end_seconds": 12.0},
        {"state": "restart_pending", "start_seconds": 12.0, "end_seconds": 30.0},
    ]}
    (attempt,) = classify(evidence, stopped)
    assert (attempt.resolution, attempt.reason) == ("off_target", "wide_or_high")


def test_goalkeeper_contact_at_the_face_is_a_save(tmp_path: Path) -> None:
    evidence = build(tmp_path, shot_path(3645, 770), [
        player(8, "black", "player", [(10.0, 3200, 900)]),
        player(40, "red", "goalkeeper", [(11.0, 3645, 790)]),
    ])
    assert [item["kind"] for item in evidence["contacts"]] == ["goalkeeper"]
    (attempt,) = classify(evidence)
    assert (attempt.resolution, attempt.reason) == ("on_target", "goalkeeper_save")


def test_slow_roll_into_the_face_is_not_an_attempt(tmp_path: Path) -> None:
    slow = [(10.0 + 0.2 * step, 3600 + 8 * step, 790) for step in range(20)]
    evidence = build(tmp_path, slow, [player(8, "black", "player", [(10.0, 3600, 790)])])
    assert evidence["goal_face_arrivals"] == []
    assert classify(evidence) == []


def test_defending_team_play_toward_own_goal_is_not_a_scoring_attempt(tmp_path: Path) -> None:
    evidence = build(tmp_path, shot_path(3645, 770), [
        player(9, "red", "player", [(10.0, 3200, 900)]),
    ])
    assert [item["intent"] for item in evidence["releases"]] == ["clearance"]
    assert classify(evidence) == []


def test_match_state_goal_transition_becomes_a_valid_goal_fact(tmp_path: Path) -> None:
    faces, provenance = load_goal_faces(calibration_file(tmp_path))
    evidence = build_evidence(
        ball_tracks=ball_tracks(shot_path(3645, 770)),
        player_tracks={"tracks": [player(8, "black", "player", [(10.0, 3200, 900)])]},
        affiliations=AFFILIATIONS,
        faces=faces,
        calibration_provenance=provenance,
        match_state={"transitions": [
            {"clip_seconds": 11.4, "trigger": "goal_requires_kick_off"}]},
    )
    assert evidence["goals"][0]["goal_side"] == "right"
    stopped = {"initial_state": "in_play", "intervals": [
        {"state": "in_play", "start_seconds": 0.0, "end_seconds": 11.4},
        {"state": "restart_pending", "start_seconds": 11.4, "end_seconds": 30.0},
    ]}
    (attempt,) = classify(evidence, stopped)
    assert (attempt.resolution, attempt.reason) == ("on_target", "valid_goal")
