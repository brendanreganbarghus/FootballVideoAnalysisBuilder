from __future__ import annotations

import json
from pathlib import Path

import pytest

from football_poc.event_comparison import compare_manual_events
from football_poc.innovation_day_snapshot import shots_on_target as sot


FPS = 25
IN_PLAY = {"initial_state": "in_play", "intervals": [
    {"state": "in_play", "start_seconds": 0.0, "end_seconds": 30.0},
]}


def goal_geometry() -> dict:
    return {
        "left": {
            "goal_line_x": 0.0,
            "post_y": [30.34, 37.66],
            "crossbar_z": 2.44,
            "uncertainty_m": 0.15,
        },
        "right": {
            "goal_line_x": 105.0,
            "post_y": [30.34, 37.66],
            "crossbar_z": 2.44,
            "uncertainty_m": 0.15,
        },
    }


def flight(start_frame: int, points: list[tuple[float, float, float]], *,
           observed: bool = True) -> list[dict]:
    return [
        {
            "frame": start_frame + index,
            "seconds": (start_frame + index) / FPS,
            "x": x,
            "y": y,
            "z": z,
            "observed": observed,
        }
        for index, (x, y, z) in enumerate(points)
    ]


def evidence(
    *,
    releases: list[dict],
    trajectory: list[dict] | None = None,
    contacts: list[dict] | None = None,
    goals: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "source_kind": sot.EVIDENCE_SOURCE_KIND,
        "calibration": {
            "teams": ["red", "black"],
            "goals": goal_geometry(),
            "attacking_goal": {"red": "right", "black": "left"},
        },
        "ball_trajectory": trajectory or [],
        "releases": releases,
        "contacts": contacts or [],
        "goals": goals or [],
    }


def release(frame: int, team: str | None = "red", intent: str = "scoring_attempt",
            **extra) -> dict:
    return {
        "frame": frame,
        "seconds": frame / FPS,
        "team": team,
        "player_track_id": 7,
        "intent": intent,
        "evidence": "deliberate strike",
        **extra,
    }


def on_target_path(start: int) -> list[dict]:
    return flight(start, [(95, 34, 0.5), (98, 34, 0.7), (101, 34, 0.9),
                          (104, 34, 1.0), (106, 34, 1.1)])


def wide_path(start: int) -> list[dict]:
    return flight(start, [(95, 34, 0.5), (98, 38, 0.6), (101, 42, 0.7),
                          (104, 46, 0.8), (106, 48, 0.9)])


def classify(payload: dict, match_state: dict = IN_PLAY) -> list[sot.Attempt]:
    return sot.classify_attempts(
        sot.parse_evidence(payload), match_state, duration_seconds=30.0
    )


def only(attempts: list[sot.Attempt]) -> sot.Attempt:
    assert len(attempts) == 1
    return attempts[0]


def test_valid_goal_counts_once_at_goal_time() -> None:
    attempt = only(classify(evidence(
        releases=[release(100)],
        trajectory=on_target_path(100),
        goals=[{"frame": 104, "seconds": 104 / FPS, "team": "red",
                "goal_side": "right", "valid": True,
                "evidence": "ball wholly over line"}],
    )))
    assert (attempt.resolution, attempt.reason) == ("on_target", "valid_goal")
    assert attempt.outcome_frame == 104


def test_goalkeeper_save_of_goal_bound_attempt() -> None:
    attempt = only(classify(evidence(
        releases=[release(100)],
        trajectory=on_target_path(100)[:3],
        contacts=[{"frame": 102, "seconds": 102 / FPS, "kind": "goalkeeper",
                   "team": "black", "player_track_id": 1}],
    )))
    assert (attempt.resolution, attempt.reason) == ("on_target", "goalkeeper_save")


def test_last_line_defender_save() -> None:
    attempt = only(classify(evidence(
        releases=[release(100)],
        trajectory=on_target_path(100)[:3],
        contacts=[{"frame": 102, "seconds": 102 / FPS,
                   "kind": "last_line_defender", "team": "black",
                   "player_track_id": 4}],
    )))
    assert attempt.reason == "last_line_defender_save"


def test_ordinary_block_is_not_on_target() -> None:
    attempt = only(classify(evidence(
        releases=[release(100)],
        trajectory=on_target_path(100)[:3],
        contacts=[{"frame": 102, "seconds": 102 / FPS, "kind": "outfield",
                   "team": "black", "player_track_id": 5}],
    )))
    assert (attempt.resolution, attempt.reason) == ("blocked", "ordinary_block")


def test_wide_shot_and_woodwork_out_are_not_on_target() -> None:
    wide = only(classify(evidence(
        releases=[release(100)], trajectory=wide_path(100)
    )))
    assert (wide.resolution, wide.reason) == ("off_target", "wide_or_high")
    woodwork = only(classify(evidence(
        releases=[release(100)],
        trajectory=on_target_path(100)[:3],
        contacts=[{"frame": 103, "seconds": 103 / FPS, "kind": "woodwork"}],
    )))
    assert (woodwork.resolution, woodwork.reason) == ("off_target", "woodwork_out")


def test_high_shot_over_crossbar() -> None:
    attempt = only(classify(evidence(
        releases=[release(100)],
        trajectory=flight(100, [(98, 34, 2.0), (102, 34, 3.0), (106, 34, 4.0)]),
    )))
    assert attempt.reason == "wide_or_high"


def test_woodwork_then_valid_goal_counts_once() -> None:
    attempts = classify(evidence(
        releases=[release(100)],
        trajectory=on_target_path(100),
        contacts=[{"frame": 103, "seconds": 103 / FPS, "kind": "woodwork"}],
        goals=[{"frame": 105, "seconds": 105 / FPS, "team": "red",
                "goal_side": "right", "valid": True, "evidence": "in off post"}],
    ))
    summary = sot.summarize(
        attempts, readiness_result=sot.Readiness("ready"), teams=("red", "black")
    )
    assert summary["counts"] == {"red": 1, "black": 0}
    assert summary["total"] == 1


def test_cross_and_keeper_collection_without_shot_are_not_attempts() -> None:
    attempts = classify(evidence(
        releases=[release(100, intent="cross")],
        trajectory=on_target_path(100)[:3],
        contacts=[{"frame": 102, "seconds": 102 / FPS, "kind": "goalkeeper",
                   "team": "black"}],
    ))
    assert attempts == []


def test_keeper_collecting_off_target_path_is_not_a_save() -> None:
    attempt = only(classify(evidence(
        releases=[release(100)],
        trajectory=wide_path(100)[:3],
        contacts=[{"frame": 102, "seconds": 102 / FPS, "kind": "goalkeeper",
                   "team": "black"}],
    )))
    assert attempt.reason == "pre_contact_path_off_target"


def test_unsupported_goal_claim_is_unresolved() -> None:
    attempt = only(classify(evidence(
        releases=[release(100)],
        trajectory=on_target_path(100),
        goals=[{"frame": 104, "seconds": 104 / FPS, "team": "red",
                "goal_side": "right", "valid": False, "evidence": ""}],
    )))
    assert (attempt.resolution, attempt.reason) == (
        "unresolved", "unsupported_goal_claim"
    )


@pytest.mark.parametrize(
    ("payload_kwargs", "reason"),
    [
        ({"releases": [release(100)],
          "trajectory": flight(100, [(95, 34, 0.5), (101, 34, 1.0)],
                               observed=False)},
         "insufficient_observed_motion"),
        ({"releases": [release(100, team=None)],
          "trajectory": on_target_path(100)}, "unknown_attacking_team"),
        ({"releases": [release(100, intent="ambiguous")],
          "trajectory": on_target_path(100)}, "ambiguous_intent"),
        ({"releases": [release(100)],
          "trajectory": on_target_path(100)[:2]}, "flight_truncated"),
        ({"releases": [release(100)],
          "trajectory": on_target_path(100)}, "goal_entry_without_goal_confirmation"),
        ({"releases": [release(100)],
          "trajectory": on_target_path(100)[:3],
          "contacts": [{"frame": 102, "seconds": 102 / FPS, "kind": "unknown"}]},
         "contact_role_unknown"),
    ],
)
def test_missing_evidence_is_explicitly_unresolved(payload_kwargs, reason) -> None:
    attempt = only(classify(evidence(**payload_kwargs)))
    assert (attempt.resolution, attempt.reason) == ("unresolved", reason)


def test_repeated_observation_and_track_handoff_are_one_attempt() -> None:
    attempts = classify(evidence(
        releases=[
            release(100),
            {**release(101), "player_track_id": 99},
            release(102, continuation_of=100),
        ],
        trajectory=on_target_path(100)[:3],
        contacts=[{"frame": 103, "seconds": 103 / FPS, "kind": "goalkeeper",
                   "team": "black"}],
    ))
    attempt = only(attempts)
    assert attempt.duplicate_release_frames == [101, 102]


def test_shot_save_goal_and_close_rebound_are_distinct_without_double_count() -> None:
    attempts = classify(evidence(
        releases=[release(100), release(106)],
        trajectory=[*on_target_path(100)[:3], *on_target_path(106)],
        contacts=[{"frame": 102, "seconds": 102 / FPS, "kind": "goalkeeper",
                   "team": "black"}],
        goals=[{"frame": 110, "seconds": 110 / FPS, "team": "red",
                "goal_side": "right", "valid": True, "evidence": "rebound goal"}],
    ))
    assert [attempt.reason for attempt in attempts] == [
        "goalkeeper_save", "valid_goal"
    ]
    assert len({attempt.attempt_id for attempt in attempts}) == 2
    summary = sot.summarize(
        attempts, readiness_result=sot.Readiness("ready"), teams=("red", "black")
    )
    assert summary["counts"] == {"red": 2, "black": 0}


def test_dead_ball_release_excluded_and_goal_transition_outcome_allowed() -> None:
    state = {"initial_state": "in_play", "intervals": [
        {"state": "restart_pending", "start_seconds": 0.0, "end_seconds": 5.0},
        {"state": "in_play", "start_seconds": 5.0, "end_seconds": 10.0},
        {"state": "restart_pending", "start_seconds": 10.0, "end_seconds": 30.0},
    ]}
    dead = only(classify(evidence(
        releases=[release(50)], trajectory=on_target_path(50)
    ), state))
    assert dead.resolution == "excluded"
    # A legal restart release at 5.0s and its goal at the goal transition.
    legal = only(classify(evidence(
        releases=[release(125)],
        trajectory=on_target_path(245),
        goals=[{"frame": 250, "seconds": 10.0, "team": "red",
                "goal_side": "right", "valid": True, "evidence": "goal"}],
    ), state))
    assert legal.reason == "valid_goal"


def test_stoppage_before_outcome_is_unresolved() -> None:
    state = {"initial_state": "in_play", "intervals": [
        {"state": "in_play", "start_seconds": 0.0, "end_seconds": 4.1},
        {"state": "restart_pending", "start_seconds": 4.1, "end_seconds": 30.0},
    ]}
    attempt = only(classify(evidence(
        releases=[release(100)],
        trajectory=on_target_path(100),
        goals=[{"frame": 110, "seconds": 110 / FPS, "team": "red",
                "goal_side": "right", "valid": True, "evidence": "goal"}],
    ), state))
    assert attempt.reason == "play_stopped_before_outcome"


def test_unknown_match_state_is_unresolved() -> None:
    state = {"initial_state": "unknown", "intervals": [
        {"state": "unknown", "start_seconds": 0.0, "end_seconds": 30.0},
    ]}
    attempt = only(classify(evidence(
        releases=[release(100)], trajectory=on_target_path(100)
    ), state))
    assert attempt.reason == "match_state_unknown"


def test_readiness_and_invalid_configuration() -> None:
    missing = sot.readiness(None)
    assert missing.status == "unavailable"
    assert "ball_height_missing" in missing.reasons
    no_height = evidence(releases=[], trajectory=[
        {"frame": 1, "seconds": 0.04, "x": 1, "y": 1, "observed": True}
    ])
    assert "ball_height_missing" in sot.readiness(no_height).reasons
    assert sot.readiness(evidence(releases=[], trajectory=on_target_path(1))).status == "ready"
    with pytest.raises(sot.ShotEvidenceError):
        sot.readiness({**evidence(releases=[]), "source_kind": "manual_reference"})
    broken = evidence(releases=[], trajectory=on_target_path(1))
    broken["calibration"]["goals"]["right"]["crossbar_z"] = -1
    with pytest.raises(sot.ShotEvidenceError):
        sot.readiness(broken)


def test_shots_on_target_always_runs_without_opt_in() -> None:
    from football_poc.innovation_day_snapshot import possession_cli

    root = Path(__file__).resolve().parents[1]
    assert not hasattr(sot, "SETTING_FILE_NAME")
    assert not hasattr(sot, "load_setting")
    options = {
        option
        for action in possession_cli.build_parser()._actions
        for option in action.option_strings
    }
    assert "--shots-on-target" not in options
    assert "--shot-evidence" in options
    runner = (root / "scripts" / "process-alfheim-innovation-segment.py").read_text(
        encoding="utf-8"
    )
    assert "shots-on-target-setting" not in runner
    assert "SHOTS_SETTING" not in runner
    canvas = root / ".github" / "extensions" / "football-event-review" / "shared"
    renderer = (canvas / "review-renderer.mjs").read_text(encoding="utf-8")
    extension = (canvas / "review-extension.mjs").read_text(encoding="utf-8")
    assert "shots-on-target-enabled" not in renderer
    assert "/api/shots-on-target" not in renderer + extension
    assert "shots-on-target-setting" not in extension


def test_summary_statuses_distinguish_unavailable_partial_and_zero() -> None:
    unavailable = sot.summarize(None, readiness_result=sot.readiness(None))
    assert unavailable["analysis_status"] == "unavailable"
    assert unavailable["counts"] is None and unavailable["total"] is None
    zero = sot.summarize([], readiness_result=sot.Readiness("ready"),
                         teams=("red", "black"))
    assert zero["analysis_status"] == "complete" and zero["total"] == 0
    partial = sot.summarize(
        classify(evidence(releases=[release(100, team=None)],
                          trajectory=on_target_path(100))),
        readiness_result=sot.Readiness("ready"), teams=("red", "black"),
    )
    assert partial["analysis_status"] == "partial"
    assert partial["unresolved_reasons"] == {"unknown_attacking_team": 1}
    assert partial["counts"] == {"red": 0, "black": 0}


def write_outputs(tmp_path: Path, events: list[dict]) -> str:
    (tmp_path / "predicted-events.json").write_text(
        json.dumps(events, indent=2), encoding="utf-8"
    )
    (tmp_path / "match-state-events.json").write_text(
        json.dumps(IN_PLAY), encoding="utf-8"
    )
    return (tmp_path / "predicted-events.json").read_text(encoding="utf-8")


LEGACY_EVENTS = [
    {"event_type": "pass_candidate", "clip_seconds": 1.0, "team": "red",
     "from_player_track_id": 1, "to_player_track_id": 2, "confidence": 0.8,
     "details": "pass", "completion_seconds": 1.5},
    {"event_type": "turnover_candidate", "clip_seconds": 9.0, "team": "black",
     "from_player_track_id": 3, "to_player_track_id": 1, "confidence": 0.7,
     "details": "turnover", "completion_seconds": None},
]


def test_unavailable_evidence_leaves_legacy_output_byte_identical(tmp_path) -> None:
    before = write_outputs(tmp_path, LEGACY_EVENTS)
    summary = sot.apply_shots_on_target(tmp_path, None, duration_seconds=30.0)
    assert summary["analysis_status"] == "unavailable"
    assert (tmp_path / "predicted-events.json").read_text(encoding="utf-8") == before


def test_enabled_output_is_deterministic_and_adds_one_event(tmp_path) -> None:
    write_outputs(tmp_path, LEGACY_EVENTS)
    evidence_path = tmp_path / sot.EVIDENCE_FILE_NAME
    evidence_path.write_text(json.dumps(evidence(
        releases=[release(100)],
        trajectory=on_target_path(100),
        goals=[{"frame": 104, "seconds": 104 / FPS, "team": "red",
                "goal_side": "right", "valid": True, "evidence": "goal"}],
    )))
    sot.apply_shots_on_target(tmp_path, evidence_path, duration_seconds=30.0)
    first = (tmp_path / "predicted-events.json").read_text(encoding="utf-8")
    first_summary = (tmp_path / sot.SUMMARY_FILE_NAME).read_text(encoding="utf-8")
    sot.apply_shots_on_target(tmp_path, evidence_path, duration_seconds=30.0)
    assert (tmp_path / "predicted-events.json").read_text(encoding="utf-8") == first
    assert (tmp_path / sot.SUMMARY_FILE_NAME).read_text(encoding="utf-8") == first_summary
    events = json.loads(first)
    assert [event["event_type"] for event in events] == [
        "pass_candidate", "shot_on_target", "turnover_candidate"
    ]
    assert events[0] == LEGACY_EVENTS[0] and events[2] == LEGACY_EVENTS[1]
    shot = events[1]
    assert shot["attempt_id"] == "sot-v1-red-000100-right"
    assert shot["completion_seconds"] == round(104 / FPS, 3)
    summary = json.loads(first_summary)
    assert summary["counts"] == {"red": 1, "black": 0}
    assert summary["analysis_status"] == "complete"


def test_comparison_includes_sot_only_in_innovation_scope() -> None:
    manual = [{"clip_seconds": 4.3, "team": "red", "event_type": "shot_on_target"}]
    predicted = [{"event_type": "shot_on_target", "clip_seconds": 4.0,
                  "completion_seconds": 4.16, "team": "red"}]
    default = compare_manual_events(manual, predicted)
    assert default["predicted_event_count"] == 0
    assert "shot_on_target" not in default["manual_counts"]["red"]
    enabled = compare_manual_events(manual, predicted, include_shots_on_target=True)
    assert enabled["matched_event_count"] == 1
    assert enabled["matched_counts"]["red"]["shot_on_target"] == 1
    far = [{**predicted[0], "completion_seconds": 5.5}]
    assert compare_manual_events(
        manual, far, include_shots_on_target=True
    )["matched_event_count"] == 0


def test_canvas_scopes_sot_to_innovation_and_blocks_incomplete_publication() -> None:
    import subprocess

    root = Path(__file__).resolve().parents[1]
    script = """
const {workflowAdapter} = await import('./.github/extensions/football-event-review/shared/workflow-adapters.mjs');
const {buildPublicationPlan} = await import('./.github/extensions/football-event-review/publication-gate.mjs');
const base = {drafts: [], decisions: {}, engineEvents: [], engineEventReviews: {},
  current: {fingerprint: {contentHash: 'a'}, outputHash: 'b'},
  snapshotMatches: true, verificationIsCurrent: () => true, regressionFresh: true};
console.log(JSON.stringify({
  innovation: workflowAdapter('innovation').analyticsEventTypes,
  live: workflowAdapter('live').analyticsEventTypes,
  tests: workflowAdapter('innovation').regressionTests.includes('tests/test_innovation_shots.py'),
  legacy: buildPublicationPlan(base).ready,
  partial: buildPublicationPlan({...base, shotsOnTarget: {analysis_status: 'partial'}}).ready,
  complete: buildPublicationPlan({...base, shotsOnTarget: {analysis_status: 'complete'}}).ready,
}));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=root, capture_output=True, text=True, check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["innovation"] == ["completed_pass", "turnover", "shot_on_target"]
    assert payload["live"] == ["completed_pass", "turnover"]
    assert payload["tests"] is True
    assert payload["legacy"] is True
    assert payload["partial"] is False
    assert payload["complete"] is True
