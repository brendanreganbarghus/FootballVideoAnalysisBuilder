from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
EXT = ROOT / ".github" / "extensions" / "football-event-review"
SHARED = EXT / "shared"
LIVE_EXT = ROOT / ".github" / "extensions" / "football-event-review-live"
ADAPTER = SHARED / "workflow-adapters.mjs"
EXTENSION = EXT / "extension.mjs"
RENDERER = EXT / "renderer.mjs"
SHARED_EXTENSION = SHARED / "review-extension.mjs"
SHARED_RENDERER = SHARED / "review-renderer.mjs"
PUBLICATION_GATE = EXT / "publication-gate.mjs"
FRESHNESS = EXT / "engine-freshness.mjs"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_single_canvas_adapter_contract() -> None:
    adapter = read(ADAPTER)
    extension = read(EXTENSION)
    renderer = read(RENDERER)

    assert not LIVE_EXT.exists()
    assert 'workflowId: "football_review"' in adapter
    assert 'canvasId: "football-event-review"' in adapter
    assert 'displayName: "Football Event Review"' in adapter
    assert 'theme: "grassroots"' in adapter
    assert 'homeUrl: "http://127.0.0.1:8080/"' in adapter
    assert 'homeLabel: "Back to Product Home"' in adapter
    assert 'export const reviewWorkflow' in adapter
    assert 'export const innovationWorkflow' not in adapter
    assert 'export const liveWorkflow' not in adapter
    assert 'await import("./shared/review-extension.mjs")' in extension
    assert 'reviewWorkflow' in renderer


def test_adapter_uses_single_api_and_flat_artifacts() -> None:
    adapter = read(ADAPTER)
    extension = read(SHARED_EXTENSION)

    assert 'statusPath: "/api/alfheim/status"' in adapter
    assert 'analyzePath: "/api/alfheim/analyze"' in adapter
    assert 'artifactNamespace' not in adapter
    assert 'stateDirectory' not in adapter
    assert '/api/alfheim/innovation' not in extension
    assert '/api/alfheim/live' not in extension
    assert 'function segmentRoot(segment) {\n  return preparedSegmentRoot(segment);\n}' in extension
    assert '/api/alfheim/segments`' in extension
    assert '/api/alfheim/segments?workflow=' not in extension


def test_engine_fingerprints_and_regression_contract() -> None:
    adapter = read(ADAPTER)

    for path in [
        '"src/football_poc/match_state.py"',
        '"src/football_poc/player_tracking.py"',
        '"src/football_poc/possession.py"',
        '"src/football_poc/possession_cli.py"',
        '"src/football_poc/shots_on_target.py"',
        '"src/football_poc/goal_calibration.py"',
        '"src/football_poc/shot_evidence_adapter.py"',
        '"src/football_poc/bac_ball_tracks.py"',
        '"src/football_poc/ball_tracking.py"',
        '"scripts/process-alfheim-segment.py"',
    ]:
        assert path in adapter
    assert 'regressionRegistry: "review-regressions.json"' in adapter
    assert 'launcherRegistry: ".football-event-review-urls.json"' in adapter
    for test in [
        'tests/test_shots_on_target.py',
        'tests/test_shot_evidence.py',
        'tests/test_possession_regression.py',
        'tests/test_match_state_regression.py',
        'tests/test_review_regressions.py',
        'tests/rules',
        'tests/tracking',
        'tests/test_rule_index.py',
    ]:
        assert test in adapter
    assert 'rulesRegressionScopeFiles: [' in adapter
    assert 'trackerRegressionTests: [\n    "tests/tracking",\n    "tests/test_ball_tracking.py",' in adapter
    extension = read(SHARED_EXTENSION)
    assert 'coverage: "rule_unit_tests"' in extension
    assert "queuePublishedReviewRegression(\n          publishedSegment.key" not in extension


def test_ball_source_selector_and_analyze_payload() -> None:
    renderer = read(SHARED_RENDERER)
    extension = read(SHARED_EXTENSION)

    assert 'id="ball-source-select"' in renderer
    assert 'BAC coordinates (frozen Alfheim BAC, diagnostic)' in renderer
    assert 'Detected ball (our detector, raw video)' in renderer
    assert '<button id="process-segment" type="button">Run segment</button>' in renderer
    assert '"prepare-bac": "Prepare BAC + player context"' in renderer
    assert '"resume-detected": segment.ballTrackAvailable\n              ? "Run ball coordinates again"' in renderer
    assert "detection_only: true" in extension
    assert '<button id="process-ai" type="button" hidden disabled>Process AI</button>' in renderer
    assert "void finalizeBallCoordinateReview();" in renderer
    assert "90% is the minimum gate" not in renderer
    assert "prepareEvidenceButton.hidden = true;" in renderer
    assert 'return ballSourceSelect?.value || state.segment.ballSource || "bac";' in renderer
    assert 'ball_source: requestedBallSource' in extension
    assert 'requestedBallSource === "bac"' in extension
    assert 'requestedBallSource === "detected"' in extension
    assert 'BAC-assisted diagnostic' in extension
    assert 'raw-video cold run' in extension


def test_capabilities_are_merged() -> None:
    adapter = read(ADAPTER)
    extension = read(SHARED_EXTENSION)
    renderer = read(SHARED_RENDERER)
    gate = read(PUBLICATION_GATE)

    assert 'manualReferenceEnabled: true' in adapter
    assert 'evidencePreparationEnabled: true' in adapter
    assert 'coordinateReviewEnabled: true' in adapter
    assert 'coordinateCorrectionEnabled: true' in adapter
    assert '"shot_on_target"' in adapter
    assert 'shotsOnTargetCapable: true' in adapter
    assert 'update_ball_coordinate_batch' in extension
    assert 'reject_ball_coordinate_review' in extension
    assert 'confirm_ball_coordinate_review' in extension
    assert '/api/prepare-evidence' in renderer
    assert '/api/approve-coordinate-layer' in renderer
    assert 'shotsOnTarget' in gate


def test_review_state_uses_coordination_only() -> None:
    extension = read(SHARED_EXTENSION)
    load_state = extension[
        extension.index('async function loadState('):
        extension.index('function coordinationKey(')
    ]
    save_state = extension[
        extension.index('async function saveState('):
        extension.index('function canonicalType(')
    ]

    assert '/api/coordination/state?workflow=' in load_state
    assert 'state = null;' in load_state
    assert 'readReviewState' not in extension
    assert 'statePath' not in extension
    assert 'legacyStatePath' not in extension
    assert 'coordination.mode !== "available"' in save_state
    assert 'coordination_unavailable' in save_state
    assert 'writeFile(path, content' not in save_state
    assert '30-shared-baselines' not in load_state


def test_user_visible_workflow_split_removed() -> None:
    combined = "\n".join([
        read(ADAPTER),
        read(SHARED_EXTENSION),
        read(SHARED_RENDERER),
        read(EXTENSION),
        read(RENDERER),
    ])
    # Retired labels may appear only where stored snapshots are normalized.
    combined = "\n".join(
        line for line in combined.splitlines()
        if not line.startswith(("const LEGACY_WORKFLOW_IDS", "const LEGACY_CANVAS_IDS"))
    )

    assert 'id="workflow-adapter"' not in combined
    for forbidden in [
        'Innovation Day',
        'Back to Innovation Day',
        'Innovation workflow',
        'Live workflow',
        'football-event-review-live',
    ]:
        assert forbidden not in combined


def test_legacy_snapshot_labels_and_ball_source_gate() -> None:
    extension = read(SHARED_EXTENSION)
    assert '"innovation_day_bac", "live_iteration_25"' in extension
    assert 'LEGACY_CANVAS_IDS.has(state.canvasId)' in extension
    detected = extension[extension.index("async function loadDetectedBallTrack"):]
    detected = detected[:detected.index("\n}\n")]
    assert 'if (segment.ballSource !== "detected") {' in detected
    assert '"innovation_day_bac_assisted"' in detected
    assert '"reviewer_corrected_innovation_coordinates"' in detected


def test_segment_picker_and_header_show_ball_source_badges() -> None:
    renderer = read(SHARED_RENDERER)
    extension = read(SHARED_EXTENSION)

    assert 'ballSource: segment.ball_source || null' in extension
    assert 'id="segment-ball-source"' in renderer
    assert 'class="ball-source-badge"' in renderer
    assert 'function ballSourceLabel(source)' in renderer
    assert 'segment.timeLabel,\n          ballSourceLabel(segment.ballSource),' in renderer
    assert 'sourceBadge.hidden = !sourceLabel' in renderer
    assert 'sourceBadge.textContent = sourceLabel' in renderer
    assert 'sourceBadge.className = "ball-source-badge " + (selected.ballSource || "")' in renderer


def test_ball_source_switch_requires_confirmation_and_reports_errors() -> None:
    renderer = read(SHARED_RENDERER)
    extension = read(SHARED_EXTENSION)

    assert 'id="change-ball-source"' in renderer
    assert 'id="ball-source-switch-modal"' in renderer
    assert 'Switching to " + ballSourceLabel(next)' in renderer
    assert 'removes this segment\'s current artifacts (E# output, "' in renderer
    assert 'ball/player/possession caches, C# proposals and decisions, "' in renderer
    assert 'E# confirmations, M↔E links and Passed status); only the M# "' in renderer
    assert 'golden set and the prepared video remain.' in renderer
    assert 'changeBallSourceButton.hidden = true;' in renderer
    assert 'fetch("/api/switch-ball-source"' in renderer
    assert 'confirm: true' in renderer
    assert 'status.textContent = error.message' in renderer
    assert 'url.pathname === "/api/switch-ball-source"' in extension
    assert 'body.confirm !== true' in extension
    assert 'Confirm required before switching ball source.' in extension
    assert 'lease?.leaseToken' in extension
    assert 'Start working on this segment before changing its ball source.' in extension
    assert 'localJson("/api/alfheim/switch-ball-source"' in extension
    assert 'ball_source: ballSource' in extension
    assert 'error.status || 400' in extension


def test_ball_source_switch_resets_review_state_but_keeps_manual_reference() -> None:
    extension = read(SHARED_EXTENSION)
    reset = extension[
        extension.index('function preservedManualReferenceForSourceSwitch'):
        extension.index('async function saveState(')
    ]

    assert 'const preserved = structuredClone(reference);' in reset
    assert 'preserved.mappings = {};' in reset
    assert 'preserved.approved.mappings = {};' in reset
    assert 'comparisonValidation = null' in reset
    assert 'decisions: {}' in reset
    assert 'engineBefore: withheldEngineSnapshot()' in reset
    assert 'engineAfter: null' in reset
    assert 'regression: null' in reset
    assert 'conversation: []' in reset
    assert 'proposalOverrides: {}' in reset
    assert 'additionalProposals: []' in reset
    assert 'engineEventReviews: {}' in reset
    assert 'engineEventReviewAuthorizations: {}' in reset
    assert 'publicationAuthorization: null' in reset
    assert 'publishedReference: null' in reset
    assert 'manualReference: preservedManualReferenceForSourceSwitch(state.manualReference)' in reset
    assert 'needsReview: true' in reset
    assert 'await saveState(segment, resetState, {allowAutoAcquire: false})' in extension


def test_engine_snapshot_prefers_coordination_outputs() -> None:
    extension = read(SHARED_EXTENSION)
    snapshot = extension[
        extension.index('async function coordinationOutputRecord'):
        extension.index('const SHOTS_ON_TARGET_SUMMARY_FILE')
    ]

    assert '/api/coordination/outputs?workflow=' in snapshot
    assert 'const stored = fromFiles ? null : await coordinationOutputRecord(segment);' in snapshot
    assert 'outputRecordFile(stored, "predicted-events.json", [])' in snapshot
    assert 'outputRecordFile(stored, "match-state-events.json", {intervals: []})' in snapshot
    assert 'stored?.outputSha256 || stored?.output_sha256' in snapshot
    assert 'fingerprint.contentHash = stored.engineSha256' not in snapshot
    assert 'const fingerprint = {...(knownFingerprint || await engineFingerprint())};' in snapshot
    assert 'outputSource: stored ? "coordination_outputs" : "artifact_files"' in snapshot


def test_publication_gate_keeps_manual_and_shot_checks() -> None:
    script = """
      import assert from "node:assert/strict";
      const {buildPublicationPlan} = await import(process.argv[1]);
      const current = {fingerprint: {contentHash: "code"}, outputHash: "output"};
      const receipt = {status: "already_agrees", engineContentHash: "code", outputHash: "output"};
      const verificationIsCurrent = candidate => candidate?.engineContentHash === "code" && candidate?.outputHash === "output";
      const plan = buildPublicationPlan({
        drafts: [{seconds: 1, team: "black", type: "completed_pass", source: "manual_review"}],
        decisions: {"0": {status: "accepted", engineVerification: receipt}},
        engineEvents: [{seconds: 1, team: "black", type: "completed_pass", reviewKey: "e1"}],
        engineEventReviews: {},
        current,
        snapshotMatches: true,
        verificationIsCurrent,
        regressionFresh: true,
        shotsOnTarget: {analysis_status: "complete"},
      });
      assert.equal(plan.ready, true);
      const blocked = buildPublicationPlan({...{
        drafts: [], decisions: {}, engineEvents: [], engineEventReviews: {}, current,
        snapshotMatches: true, verificationIsCurrent, regressionFresh: true,
      }, shotsOnTarget: {analysis_status: "unavailable"}});
      assert.equal(blocked.ready, false);
      assert.match(blocked.blockers.join(" "), /Shots-on-target/);
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, PUBLICATION_GATE.resolve().as_uri()],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_edited_mjs_files_have_valid_syntax() -> None:
    for path in [
        ADAPTER,
        EXTENSION,
        RENDERER,
        PUBLICATION_GATE,
        FRESHNESS,
        SHARED_EXTENSION,
        SHARED_RENDERER,
    ]:
        result = subprocess.run(
            ["node", "--check", str(path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


def test_client_review_workflow_injects_every_property_the_page_reads() -> None:
    import re

    renderer = read(SHARED_RENDERER)
    block = re.search(
        r"const reviewWorkflow = \$\{JSON\.stringify\(\{([\s\S]*?)\}\)\};",
        renderer,
    )
    assert block, "client reviewWorkflow injection block not found"
    injected = set(re.findall(r"(\w+):", block.group(1)))
    used = set(re.findall(r"reviewWorkflow\.([A-Za-z]+)", renderer))
    assert used <= injected, f"not injected into the page: {sorted(used - injected)}"

def test_each_ball_source_prepares_its_own_window_copy_with_m_golden_set() -> None:
    renderer = read(SHARED_RENDERER)
    extension = read(SHARED_EXTENSION)

    assert "ball_source: selectedBallSource()" in renderer
    assert "selectedBallSource() === state.segment.ballSource" in renderer
    assert "ball_source: String(body.ball_source)" in extension
    assert "await copySiblingManualReference(prepared.cache_key);" in extension
    assert "preservedManualReferenceForSourceSwitch(source.manualReference)" in extension
    assert 'replace(/-(?:bac|detected)$/, "")' in extension


def test_bac_copy_is_read_only_auto_agreed() -> None:
    renderer = read(SHARED_RENDERER)

    assert "function bacReadOnly()" in renderer
    assert 'status.textContent = "Auto-agreed";' in renderer
    assert '? ["BAC imported · confirmed", "confirmed"]' in renderer
    assert 'review.textContent = "No review available";' in renderer
    assert "const inspectionOnly = bacReadOnly()" in renderer


def test_our_rules_copy_can_start_the_ball_check_again() -> None:
    extension = read(SHARED_EXTENSION)
    renderer = read(SHARED_RENDERER)

    assert '"/api/restart-ball-coordinate-review"' in extension
    assert '"/api/cancel-ball-coordinate-restart"' in extension
    assert 'if (context.selected.ballSource !== "detected") {' in extension
    assert "hideEngineEvents: true," in extension
    assert "if (restart.rerunStarted) {" in extension
    assert "review.state.coordinateReviewRestart.rerunStarted = true;" in extension
    assert "state.coordinateReviewRestart = null;" in extension
    assert "engineEvents: state.coordinateReviewRestart?.hideEngineEvents" in extension
    assert 'id="restart-ball-coordinate-review"' in renderer
    assert 'id="cancel-ball-coordinate-restart"' in renderer
    assert "function renderBallCheckRestart()" in renderer
    assert "state.coordinateReviewRestart\n          && state.coordinateReview?.status !== \"finalized\"" in renderer


def test_our_rules_engine_run_rechecks_the_bac_copy() -> None:
    extension = read(SHARED_EXTENSION)
    renderer = read(SHARED_RENDERER)

    assert "async function startBacSiblingRecheck(segment, state)" in extension
    assert "await startBacSiblingRecheck(segment, context.state)" in extension
    assert '"/api/bac-recheck"' in extension
    assert 'id="bac-recheck-summary"' in renderer
    assert '"M# found · Our rules "' in renderer

def test_our_rules_copy_shows_saved_decisions_and_ball_check_score() -> None:
    extension = read(SHARED_EXTENSION)
    renderer = read(SHARED_RENDERER)

    assert "async function ballCheckScore(selected, track, observations)" in extension
    assert "const BALL_CHECK_MATCH_PX = 25;" in extension
    assert "ballCheck,\n    shotsOnTarget" in extension
    assert ".filter((ballState) => ballState.direct).length" in extension
    assert "...(selectedBatch ? {} : state.trajectoryAudit?.observations || {})," in renderer
    assert "|| state.trajectoryAudit?.observations?.[String(point.frame)];" in renderer
    assert '<option value="ball-check-left" hidden>Not matching yet</option>' in renderer
    assert '"Our rules correct "' in renderer


def test_reviewer_can_accept_the_tracker_point_as_a_known_limit() -> None:
    extension = read(SHARED_EXTENSION)
    renderer = read(SHARED_RENDERER)

    assert 'if (decision?.decision === "accept_tracker") {' in extension
    assert "if (near(point, decision)) acceptedFrames.push(frame);" in extension
    assert "const scored = correct + acceptedFrames.length + left.length;" in extension
    assert extension.count('"accept_tracker",') == 3
    assert 'id="accept-tracker-point"' in renderer
    assert '{decision: "accept_tracker", x: point.engineX, y: point.engineY}' in renderer
    assert 'return "accepted";' in renderer
    assert '" · accepted tracker point "' in renderer


def test_reviewer_can_mark_the_ball_out_of_play() -> None:
    extension = read(SHARED_EXTENSION)
    renderer = read(SHARED_RENDERER)

    assert 'hit = trackerOutOfPlay.has(frame);' in extension
    assert 'if (ownOutOfPlay.has(state.frame)) state.engineOutOfPlay = true;' in extension
    assert extension.count('"out_of_play",') == 3
    assert 'id="ball-out-of-play"' in renderer
    assert '{decision: "out_of_play"}' in renderer
    assert 'out_of_play: ["Ball out of play", "confirmed"]' in renderer
