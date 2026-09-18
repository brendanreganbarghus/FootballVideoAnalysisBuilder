from __future__ import annotations

import subprocess
from os import PathLike
from pathlib import Path


class CanvasSource(PathLike[str]):
    def __init__(self, path: Path, workflow: str) -> None:
        self.path = path
        self.workflow = workflow

    def __fspath__(self) -> str:
        return str(self.path)

    def as_uri(self) -> str:
        return self.path.as_uri()

    def with_name(self, name: str) -> Path | "CanvasSource":
        path = self.path.with_name(name)
        if name in {"extension.mjs", "renderer.mjs"}:
            return CanvasSource(path, self.workflow)
        return path

    def read_text(self, encoding: str = "utf-8") -> str:
        source = self.path.read_text(encoding=encoding)
        shared_root = (
            Path(__file__).parents[1]
            / ".github"
            / "extensions"
            / "football-event-review"
            / "shared"
        )
        shared_name = (
            "review-extension.mjs"
            if self.path.name == "extension.mjs"
            else "review-renderer.mjs"
        )
        adapters = (shared_root / "workflow-adapters.mjs").read_text(
            encoding=encoding,
        )
        if self.workflow == "innovation":
            adapter = adapters[
                adapters.index("export const innovationWorkflow"):
                adapters.index("export const liveWorkflow")
            ]
        else:
            adapter = adapters[
                adapters.index("export const liveWorkflow"):
                adapters.index("export function workflowAdapter")
            ]
        common = adapters[:adapters.index("export const innovationWorkflow")]
        return "\n".join([
            source,
            (shared_root / shared_name).read_text(encoding=encoding),
            common,
            adapter,
        ])


EXTENSION = CanvasSource((
    Path(__file__).parents[1]
    / ".github"
    / "extensions"
    / "football-event-review"
    / "extension.mjs"
), "innovation")
RENDERER = EXTENSION.with_name("renderer.mjs")
FRESHNESS = EXTENSION.with_name("engine-freshness.mjs")
PUBLICATION_GATE = EXTENSION.with_name("publication-gate.mjs")
LIVE_EXTENSION = CanvasSource((
    Path(__file__).parents[1]
    / ".github"
    / "extensions"
    / "football-event-review-live"
    / "extension.mjs"
), "live")
LIVE_RENDERER = LIVE_EXTENSION.with_name("renderer.mjs")
LIVE_PUBLICATION_GATE = LIVE_EXTENSION.with_name("publication-gate.mjs")


def test_canonical_canvas_switches_workflow_adapters_in_one_screen() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'id="workflow-adapter"' in renderer
    assert "Innovation Day — Frozen BAC" in renderer
    assert "Live — Raw-video pipeline" in renderer
    assert 'fetch("/api/switch-workflow"' in renderer
    assert "football-review-last-segment-" in renderer
    assert "hostInstanceId" in renderer
    assert 'url.pathname === "/api/switch-workflow"' in extension
    assert 'url.pathname === "/api/agent-action"' in extension
    assert "setActiveAdapter(context.instanceId, workflow.key)" in extension
    assert "dispatchCanvasAction(action, context)" in extension
    assert "proxyCanvasAction(selectedWorkflow, action.name, context)" in extension
    assert '"#workflow-adapter"' in renderer


def test_canvas_uses_backend_authority_without_exposing_lease_tokens() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert '"/api/coordination/health"' in extension
    assert '"/api/coordination/identity"' in extension
    assert '"/api/coordination/state?workflow="' in extension
    assert '"/api/coordination/leases?workflow="' in extension
    assert '"/api/coordination/acquire"' in extension
    assert '"/api/coordination/heartbeat"' in extension
    assert '"/api/coordination/release"' in extension
    assert "expectedVersion: coordinated.version" in extension
    assert "leaseToken: coordinated.leaseToken" in extension
    assert "coordinationSessions" in extension
    assert 'await localJson("/api/coordination/heartbeat"' in extension
    assert "coordinationSessions.delete(key);" in extension
    assert "leaseToken: undefined" in extension
    assert "coordinationLease = publicLease(segment.key)" in extension
    assert "mode: coordinationHealth.mode" in extension
    assert "allowAutoAcquire: false" in extension
    assert 'coordination.mode === "unavailable"' in extension
    assert "await releaseCoordinationLease();" in renderer
    assert 'navigator.sendBeacon(' in renderer


def test_innovation_canvas_requires_its_copilot_project_session() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert "function canvasSessionConnection(" in extension
    assert 'workflow.key !== "innovation"' in extension
    assert "hostInstanceId === serverInstanceId" in extension
    assert "servers.has(serverInstanceId)" in extension
    assert 'code: "copilot_session_required"' in extension
    assert "canvasSessionConnectionFromRequest(" in extension
    assert "copilotSession," in extension
    assert 'id="copilot-session-status"' in renderer
    assert 'id="refresh-copilot-session"' in renderer
    assert "function copilotSessionConnected()" in renderer
    assert "if (!copilotSessionConnected()) return false;" in renderer
    assert '"&hostInstanceId=" + encodeURIComponent(hostInstanceId)' in renderer
    assert "renderCopilotSessionStatus();" in renderer


def test_live_canvas_does_not_enable_innovation_session_gate() -> None:
    live = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert 'if (workflow.key !== "innovation") {' in live
    assert "connected: true," in live
    assert 'workflow.key === "innovation"' in live


def test_canvas_get_paths_do_not_create_coordination_state_or_leases() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")

    load_state = extension[
        extension.index("async function loadState("):
        extension.index("function coordinationKey(")
    ]
    reconcile = extension[
        extension.index("async function reconcileCoordinateReviewBatch("):
        extension.index("async function publicState(")
    ]
    assert "await acquireCoordinationLease(segment)" not in load_state
    assert "allowAutoAcquire: false" in reconcile
    assert 'coordination.mode !== "unavailable"' in load_state
    assert "await saveState(segment, initial" in load_state


def test_available_coordination_never_falls_back_to_json_state() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    load_state = extension[
        extension.index("async function loadState("):
        extension.index("function coordinationKey(")
    ]
    shared_status = extension[
        extension.index("const sharedReviewStatus ="):
        extension.index("const workflowRegression =")
    ]

    assert "state = coordinatedSnapshot.state;" in load_state
    assert "coordinatedSnapshot?.state ||" not in load_state
    assert '} else {\n    state = await readReviewState(' in load_state
    assert 'coordinationHealth.mode === "available"' in shared_status
    assert '"/api/coordination/state?workflow="' in shared_status
    available_branch = shared_status[
        shared_status.index('coordinationHealth.mode === "available"'):
        shared_status.index("} else {", shared_status.index(
            'coordinationHealth.mode === "available"'
        ))
    ]
    assert "readReviewState(" not in available_branch


def test_read_derived_saves_require_an_existing_lease() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    save_state = extension[
        extension.index("async function saveState("):
        extension.index("function canonicalType(")
    ]
    review_context = extension[
        extension.index("async function reviewContext("):
        extension.index("function displayedActivity(")
    ]
    reconcile = extension[
        extension.index("async function reconcileCoordinateReviewBatch("):
        extension.index("async function publicState(")
    ]

    assert (
        "if (!allowAutoAcquire && !existing?.leaseToken) return;"
        in save_state
    )
    assert save_state.count("if (!allowAutoAcquire)") == 1
    assert "allowAutoAcquire: false" in review_context
    assert reconcile.count("allowAutoAcquire: false") == 3


def test_canvas_reviews_the_prepared_segment_catalog() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'canvasId: "football-event-review"' in extension
    assert "id: workflow.canvasId" in extension
    assert "/api/alfheim/segments" in extension
    assert "segment.validated" in extension
    assert 'validationStatus = segment.validated' in extension
    assert 'id="segment-select"' in renderer
    assert "Prepared Alfheim segments · BAC assisted" in renderer
    assert "Event 1 of 1" in renderer
    assert "Previous Event" in renderer
    assert "Next Event" in renderer
    assert "Football Event Review" in renderer
    assert "Test 3 Event Review" not in renderer
    assert "Copilot Draft" not in renderer
    assert "Rules Engine" not in renderer
    assert "left.startSeconds - right.startSeconds" in extension
    assert "left.durationSeconds - right.durationSeconds" in extension
    assert "left.key.localeCompare(right.key)" in extension


def test_live_canvas_blocks_interaction_while_switching_segments() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'id="segment-loading-overlay"' in renderer
    assert 'id="segment-loading-title"' in renderer
    assert 'id="segment-loading-detail"' in renderer
    assert 'id="segment-loading-elapsed"' in renderer
    assert 'aria-busy="true"' in renderer
    assert '"Loading " + segmentLabel,' in renderer
    assert "await loadState();" in renderer
    assert "await loadGeometry();" in renderer
    assert "const requestedSegmentKey = selectedSegmentKey();" in renderer
    assert "if (selectedSegmentKey() !== requestedSegmentKey)" in renderer
    assert "stateRefreshQueued = true;" in renderer
    assert "state = nextState;" in renderer
    assert "async function loadState(queueIfPending = true)" in renderer
    assert "if (queueIfPending) stateRefreshQueued = true;" in renderer
    assert "loadState(false).catch(() => {});" in renderer
    assert "setSegmentLoading(false);" in renderer
    assert '"Could not load segment"' in renderer


def test_canvas_blocks_deliberately_slow_loads() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert "position: fixed;" in renderer
    assert "inset: 0;" in renderer
    assert "z-index: 10000;" in renderer
    assert 'document.body.setAttribute("aria-busy", String(loading));' in renderer
    assert "segmentLoadingStartedAt = Date.now() -" in renderer
    assert "segmentLoadingTimer = setInterval(" in renderer
    assert "updateSegmentLoadingElapsed," in renderer
    assert "clearInterval(segmentLoadingTimer);" in renderer
    assert '"Elapsed: " + elapsed + "s"' in renderer
    assert '"Loading football review",' in renderer
    assert '"Importing camera sample",' in renderer
    assert '"Preparing " + duration + "-second review segment"' in renderer
    assert (
        '"Creating the playable clip and registering its workflow artifacts."'
        in renderer
    )
    assert '"Switching review workflow",' in renderer
    assert ").finally(() => {" in renderer


def test_innovation_hides_redundant_twenty_second_prefix_segment() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    live = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert 'hiddenSegments: ["segment-0540-020"]' in extension
    assert "const hiddenSegments = new Set(workflow.hiddenSegments || []);" in extension
    assert "!hiddenSegments.has(segment.cache_key)" in extension
    assert "const hiddenSegments = new Set(target.hiddenSegments || []);" in extension
    assert 'hiddenSegments: []' in live


def test_innovation_published_segments_offer_exact_output_regression() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'url.pathname === "/api/innovation/regression"' in extension
    assert "executePublishedInnovationRegression" in extension
    assert "queuePublishedInnovationRegression" in extension
    assert "review.selected.validated" in extension
    assert "review.state.publishedReference?.outputHash" in extension
    assert "...workflow.processorArguments" in extension
    assert "current.outputHash === baselineOutputHash" in extension
    assert "describeRegressionEvents" in extension
    assert "function matchStateBehavior(matchState)" in extension
    assert '"law_profile"' in extension
    assert '"law_reference"' in extension
    assert '"schema_version"' in extension
    assert "matchStateMetadataOnly" in extension
    assert "const passed = exactOutputMatch || matchStateMetadataOnly;" in extension
    assert '"metadata_only"' in extension
    assert '"Metadata-only mismatch"' in renderer
    assert 'passed: "Passed"' in renderer
    assert '"Passed: events and match-state behavior are unchanged;' in extension
    assert '"No events or match-state behavior changed.' in renderer
    assert '"Added"' in extension
    assert '"Missing"' in extension
    assert "baselineSnapshotForRestore" in extension
    assert "candidateOutputHash: current.outputHash" in extension
    assert 'suite: "innovation_segment"' in extension
    assert 'trigger: "manual_rerun"' in extension
    assert "queuePublishedInnovationRegression" in extension
    assert "segmentRegressionJobs" in extension
    assert "publicSegmentRegressionProgress" in extension
    assert "publishedSegments.map(async (publishedSegment)" in extension
    assert "{reuseActive: true}" in extension
    assert "await execFileAsync(" in extension
    assert "sendJson(response, 202" in extension
    assert "regressionJobs: publicSegmentRegressionProgress()" in extension
    assert 'button.textContent = regressionRunning' in renderer
    assert '"Running…"' in renderer
    assert "button.disabled = regressionRunning" in renderer
    assert "syncRegressionQueuePolling" in renderer
    assert "setInterval(() => loadState(false), 1000)" in renderer
    assert 'id="select-passed-regressions"' in renderer
    assert 'id="run-selected-regressions"' in renderer
    assert 'id="view-regression-runs"' in renderer
    assert "selectedRegressionSegments" in renderer
    assert "runPublishedSegmentRegressions" in renderer
    assert "Promise.all(segments.map(async segment" in renderer
    assert "renderRegressionDashboard" in renderer
    assert '"Regression batch complete"' in renderer
    assert "activeRegressionBatch.clear()" in renderer
    assert "setSegmentLoading(false)" in renderer
    assert '"Run cached Innovation rules engine"' in extension
    assert 'reviewWorkflow.key === "innovation"' in renderer
    assert "segment.validated" in renderer
    assert "summary.published" in renderer
    assert '".shared-review-table button"' in renderer
    assert '"Regression passed"' in renderer
    assert '"Regression mismatch"' in renderer
    assert 'id="regression-review-queue"' in renderer
    assert "state.workflowRegression" in renderer
    assert "workflowRegression?.segmentResults" in renderer
    assert "result.regressionSummary" in renderer
    assert "The candidate engine is blocked." in renderer
    assert '"Passed · Current rules differ"' in renderer
    assert '"regression-failed"' in renderer
    assert 'failed: "Current engine differs"' in renderer
    assert '"regression-diff"' in renderer
    assert 'summary.regression === "failed"' in renderer
    assert 'engineDisplayMode: showRegressionCandidate' in extension
    assert '"regression_candidate"' in extension
    assert "function engineReviewSnapshot(state, current)" in extension
    assert "engineReviewSnapshot(review.state, cachedCurrent)" in extension
    assert 'event.regressionChange === "added"' in renderer
    assert 'id="engine-output-notice"' in renderer
    assert "function regressionCandidateReviewActive()" in renderer
    assert 'name="engine-user-verdict"' in renderer
    assert "userClaimedCorrect" in extension
    assert '"Reviewer verdict: "' in renderer
    assert "Copilot not confirmed" in renderer
    assert "My professional opinion" in renderer
    assert 'value="incorrect"' in renderer
    assert 'value="unsure"' in renderer
    assert "Confirm Incorrect & Diagnose Engine (Autopilot)" in renderer
    assert "Do not spend time re-adjudicating the football event" in extension
    assert "requireReviewerVerdict = true" in renderer
    assert "openEngineVerificationModal(row.engineIndex)" in renderer
    assert "reviewWorkflow.key === \"innovation\"" in renderer
    assert 'grid-template-areas:' in renderer
    assert 'newBadge.textContent = "NEW"' in renderer
    assert 'unsupported.textContent = "✕ Not confirmed"' in renderer
    assert 'id="move-event-panel"' in renderer
    assert 'handle.addEventListener("pointerdown"' in renderer
    assert 'handle.addEventListener("keydown"' in renderer
    assert 'id="zoom-out"' in renderer
    assert 'id="zoom-in"' in renderer
    assert "manualZoom = Math.min(6, manualZoom + 0.5)" in renderer
    assert "function currentZoomFocus()" in renderer
    assert "selectedEngine.seconds * Number(ballTrack.fps" in renderer


def test_innovation_canvas_is_alfheim_only_and_uses_shared_calibration() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'id="source-select"' in renderer
    assert "Dataset / camera" in renderer
    assert "segment.datasetId === selected.datasetId" in renderer
    assert 'candidate.datasetId === sourceSelect.value' in renderer
    assert 'state.segment.calibrationId + "-geometry-v1"' in renderer
    assert '"/api/calibration?segment="' in renderer
    assert (
        "`${localServer}/api/alfheim/segments?workflow="
        "${workflow.segmentCatalogWorkflow}`"
    ) in extension
    assert 'segmentCatalogWorkflow: "innovation"' in extension
    assert "/api/alfheim/innovation/status" in extension
    assert "/api/alfheim/innovation/analyze" in extension


def test_innovation_canvas_keeps_bac_and_live_workflows_separate() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert (
        "return join(preparedSegmentRoot(segment), "
        "workflow.artifactNamespace)"
    ) in extension
    assert 'artifactNamespace: "innovation"' in extension
    assert "/api/alfheim/innovation/analyze" in extension
    assert "/api/alfheim/innovation/status" in extension
    assert "/api/alfheim/live/" not in extension
    assert 'processorScript: "process-alfheim-innovation-segment.py"' in extension
    assert 'payload.source_kind !== "evaluation_only_provider_coordinates"' in extension
    assert 'payload.pipeline_mode !== "innovation_day_bac_assisted"' in extension
    assert 'state: "frozen_bac"' in extension
    assert 'coordinateMode: "frozen_bac"' in extension
    assert "workflow.inspectionDetectionCaches || []" in extension
    assert (
        '"developer-runs/reviewed-23-ball-models/yolo26n/detections.jsonl"'
        in extension
    )
    assert "review_required: false" in extension
    assert "disabledActionNames: [" in extension
    assert '"update_ball_coordinate_batch"' in extension
    assert "workflow.disabledActionNames.includes(action.name)" in extension
    assert '"review_action_unavailable"' in extension
    assert 'selectedCoordinateBatchId = "all"' in renderer
    assert "All frames is read-only and shows persisted direct coordinates only." in renderer
    assert "function comparisonRows()" in renderer
    assert "const rows = comparisonRows();" in renderer
    assert "function renderFullscreenEvents()" in renderer
    assert "renderFullscreenEvents();" in renderer
    assert "let stateRefreshPromise = null;" in renderer
    assert "if (stateRefreshPromise)" in renderer
    assert "return stateRefreshPromise;" in renderer
    assert "return await stateRefreshPromise;" in renderer
    assert 'adapter.coordinateReviewEnabled ? "" : " hidden"' in renderer
    assert '"Frozen BAC coordinate", "pending"' in renderer
    assert '["BAC coordinate confirmed", "confirmed"]' in renderer
    assert '"Not reviewed yet", "pending"' in renderer
    assert "workflow.inspectionDetectionCaches || []" in extension
    assert "yoloCandidateSource" in extension


def test_canvas_locks_review_controls_until_ai_is_ready() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert renderer.count("data-ai-gated") >= 2
    assert ': state.segment.state === "ready"' in renderer
    assert "section.inert = !ready" in renderer
    assert 'section.classList.toggle("ai-locked", !ready)' in renderer
    assert 'section.setAttribute("aria-disabled", String(!ready))' in renderer


def test_calibration_requires_a_prepared_video_segment() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'id="geometry-availability"' in renderer
    assert "const available = Boolean(state.segment.videoUrl)" in renderer
    assert "geometryPanel.inert = !available" in renderer
    assert 'geometryPanel.classList.toggle("ai-locked", !available)' in renderer
    assert 'geometryPanel.setAttribute("aria-disabled", String(!available))' in renderer
    assert "if (!available) geometryPanel.open = false" in renderer
    assert "if (!state.segment.videoUrl)" in renderer
    assert "Prepare a video segment for this camera before calibrating it." in renderer


def test_innovation_canvas_always_uses_innovation_theme() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert "theme: { type: \"string\", enum: [workflow.theme] }" in extension
    assert "const theme = workflow.theme" in extension
    assert 'theme: "innovation"' in extension
    assert "renderHtml({ adapter } = {})" in renderer
    assert 'data-app-theme="${appTheme}"' in renderer
    assert "Back to Product Home" not in renderer
    assert "Back to Innovation Day" in renderer
    assert "http://127.0.0.1:8080/showcase/innovation-day/" in renderer
    assert 'href="${homeUrl}"' in renderer
    assert 'html[data-app-theme="innovation"]' in renderer
    assert 'id="geometry-overlay"' in renderer
    assert 'id="geometry-feature"' in renderer
    assert 'id="edit-geometry"' in renderer
    assert 'id="restore-geometry"' in renderer
    assert '"/api/calibration?segment="' in renderer
    assert 'url.pathname === "/api/calibration"' in extension
    assert ".football-event-review-urls.json" in extension
    assert "registerLauncherUrl(theme, url)" in extension
    assert "innovation-pitch-overlay" not in renderer
    assert "illustrative pitch guides" not in renderer
    assert "Xebia · Innovation Day" in renderer
    assert "const themeColor = adapter.themeColor" in renderer
    assert 'themeColor: "#100d12"' in renderer
    assert "--panel-background: ${palette.panelBackground}" in renderer
    assert "--panel-border: ${palette.panelBorder}" in renderer
    assert 'panelBackground: "#161018"' in renderer
    assert 'panelBorder: "#5b3e5f"' in renderer
    assert "#a63f98" in renderer
    assert "#e4a5da" in renderer
    assert renderer.count('id="video-shell"') == 1
    assert renderer.count('id="segment-builder-panel"') == 1


def test_engine_result_is_revealed_only_after_acceptance() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'decision?.status === "accepted"' in extension
    assert 'decision?.status === "accepted" && draft.comparison' in renderer
    assert "Engine result hidden until you accept" in renderer
    assert "Frozen before engine:" in renderer
    assert "Accepted · pending general rule implementation" in renderer
    assert "Blocked by regression:" in renderer
    assert "engineFingerprint()" in extension
    assert "outputHash" in extension


def test_canvas_messages_include_selected_event_context() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert "session.send({" in extension
    assert "displayPrompt:" in extension
    assert "Review Event ${index + 1} at" in extension
    assert "messagePrompt(" in extension
    assert "Selected proposal:" in extension
    assert "Selected event: Event ${index + 1}; canvas action index: ${index}." in extension
    assert "Video artifact:" in extension
    assert "Source window:" in extension
    assert "frame ${Math.round(draft.seconds * 25)} at 25 fps" in extension
    assert "make one targeted adjudication pass" in extension
    assert "normally ±2 seconds" in extension
    assert "Do not scan the full video" in extension
    assert "rerun detection/tracking" in extension
    assert "only after the user accepts a changed requirement" in extension
    assert "Evidence:" in extension
    assert "Rule basis:" in extension
    assert "${adapter.conversationPrefix}Event 1" in renderer
    assert 'fetch("/api/message"' in renderer
    assert 'session.on("tool.execution_start"' in extension
    assert 'name: "publish_review_response"' in extension
    assert 'id="activity" aria-live="polite"' in renderer
    assert 'events.addEventListener("activity", loadState)' in renderer
    assert "@media (prefers-reduced-motion: reduce)" in renderer


def test_canvas_separates_laws_from_analytics_definitions() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert "Universal match-state layer:" in renderer
    assert "accepted Laws of" in renderer
    assert "Project analytics layer:" in renderer
    assert "completed pass, turnover" in renderer


def test_canvas_supports_post_change_regression_verification() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")

    assert 'name: "get_review_status"' in extension
    assert 'name: "refresh_engine_snapshot"' in extension
    assert 'name: "record_regression_result"' in extension
    assert "engine_snapshot_missing" in extension
    assert "state.engineAfter = await captureEngineSnapshot(segment)" in extension
    assert "state.regression =" in extension
    assert '"engine_snapshot_stale"' in extension
    assert "verifiedAfterRerun" in extension


def test_acceptance_self_checks_engine_snapshot_freshness() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert "async function compareWithCurrentEngine(segment, draft, state)" in extension
    assert "current.fingerprint.contentHash" in extension
    assert "current.outputHash" in extension
    assert "matchingStoredSnapshot(current, state)" in extension
    assert 'status: "stale"' in extension
    assert "Rerun only the cached event-building stage" in extension
    assert "engineVerificationReceipt(" in extension
    assert "engineVerification," in extension
    assert "hasReviewHistory(state)" in extension
    assert 'source: "user_accepted"' in extension
    assert "isRegressionCurrent(" in extension
    assert "engineSnapshotFresh: Boolean(" in extension
    assert "currentOutputHash: currentEngine.outputHash" in extension
    assert "Object.entries(state.decisions).forEach(" in extension
    assert "outputHash: state.engineAfter.outputHash" in extension
    assert "Current engine verified:" in renderer
    assert "Stale engine check:" in renderer
    assert ".engine-result.stale" in renderer
    assert "Rerun required: rebuild cached events only" in renderer
    assert "Regression result is stale for the current engine/output." in renderer


def test_engine_freshness_helpers_cover_refresh_and_preservation() -> None:
    script = """
      import assert from "node:assert/strict";
      const {
        engineVerificationReceipt,
        hasReviewHistory,
        isRegressionCurrent,
        isVerificationCurrent,
        matchingStoredSnapshot,
        referenceStoredSnapshot,
        requiresEngineImplementationChange,
      } = await import(process.argv[1]);

      const snapshot = (code, output) => ({
        capturedAt: "2025-01-01T00:00:00Z",
        fingerprint: {contentHash: code, gitRevision: "abc"},
        outputHash: output,
      });
      const before = snapshot("code-a", "output-a");
      const after = snapshot("code-b", "output-b");
      const state = {engineBefore: before, engineAfter: after};

      assert.equal(matchingStoredSnapshot(after, state)[0], "after");
      assert.equal(matchingStoredSnapshot(snapshot("code-c", "output-b"), state), null);
      assert.equal(referenceStoredSnapshot(snapshot("code-b", "other"), state)[0], "after");
      assert.equal(referenceStoredSnapshot(snapshot("other", "output-a"), state)[0], "before");

      const stale = engineVerificationReceipt(
        before, before, "before", false, ["cached_output"],
      );
      assert.equal(isVerificationCurrent(stale, before), false);
      const refreshed = engineVerificationReceipt(after, after, "after");
      assert.equal(isVerificationCurrent(refreshed, after), true);
      assert.equal(isVerificationCurrent(refreshed, before), false);

      assert.equal(isRegressionCurrent({
        fingerprint: after.fingerprint,
        outputHash: after.outputHash,
      }, after), true);
      assert.equal(isRegressionCurrent({
        fingerprint: after.fingerprint,
        outputHash: "old-output",
      }, after), false);

      assert.equal(hasReviewHistory({decisions: {"2": {status: "accepted"}}}), true);
      assert.equal(hasReviewHistory({decisions: {}}), false);

      assert.equal(requiresEngineImplementationChange(
        "missing", "code-a", "code-a", stale,
      ), false);
      assert.equal(requiresEngineImplementationChange(
        "missing", "code-a", "code-a",
        {...stale, staleReasons: ["engine_code"]},
      ), true);
      assert.equal(requiresEngineImplementationChange(
        "missing", "code-a", "code-b", refreshed,
      ), false);
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, FRESHNESS.as_uri()],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_canvas_can_zoom_to_each_events_ball_coordinate() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert (
        "const actionFocuses = await loadActionFocuses("
        in extension
    )
    assert "effectiveDrafts" in extension
    assert '"analytics-cache", "ball-tracks.json"' in extension
    assert "calibration.image_width" in extension
    assert "calibration.image_height" in extension
    assert "actionFocus: actionFocuses[index]" in extension
    assert 'id="zoom-action"' in renderer
    assert "Zoom to Action" in renderer
    assert '"C" + (selectedIndex + 1)' in renderer
    assert '"E" + (selectedEngineIndex + 1)' in renderer
    assert "function currentZoomFocus()" in renderer
    assert "Reset Action Zoom" in renderer
    assert ".video-shell.action-zoom .video-media" in renderer
    assert "videoMedia.style.transformOrigin = focus" in renderer


def test_canvas_can_switch_between_normal_ball_and_ai_views() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'url.pathname === "/api/ball-track"' in extension
    assert "async function loadDetectedBallTrack(" in extension
    assert "selected.trackingUrl = status.tracking_url" in extension
    assert 'data-view-mode="normal"' in renderer
    assert 'data-view-mode="ball"' in renderer
    assert 'data-view-mode="ai"' in renderer
    assert 'id="ball-overlay"' in renderer
    assert 'id="ball-trajectory"' in renderer
    assert "function updateBallMarker()" in renderer
    assert "candidate[4] === trackId" in renderer
    assert 'ballOverlay.removeAttribute("hidden")' in renderer
    assert 'ballOverlay.setAttribute("hidden", "")' in renderer
    assert "Raw-video-derived detected ball position at this frame" in renderer
    assert "Detected ball" in renderer
    assert "Cached AI player, team, and ball tracking" in renderer
    assert "replaceVideoSource(source)" in renderer
    assert "videoMedia.style.transformOrigin = focus" in renderer


def test_canvas_uses_a_stable_session_instance_port() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")

    assert 'process.env.SESSION_ID || "copilot"' in extension
    assert "const preferredPort = 52_000 +" in extension
    assert "await listen(preferredPort)" in extension
    assert 'error?.code !== "EADDRINUSE"' in extension


def test_passed_segments_use_locked_references_and_remain_reviewable() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'source: "validated_reference"' in extension
    assert 'status: "accepted"' in extension
    assert 'source: "published_reference"' in extension
    assert 'validationStatus === "passed"' in renderer
    assert "Published reference" in renderer
    assert "Passed" in renderer
    assert "Protected" in renderer


def test_prepared_only_segments_do_not_start_processing() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'segmentInfo.state !== "ready"' in extension
    assert "No reviewed events yet" in renderer
    assert "preparation alone never starts it" in renderer
    assert "process-alfheim-segment" not in renderer
    assert "/api/process" not in extension


def test_review_state_is_namespaced_by_segment() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert '`${segment}-review-state.json`' in extension
    assert "statePath(segment)" in extension
    assert "segment: selected" in extension
    assert "segment: selectedSegmentKey()" in renderer


def test_review_state_prefers_shared_checksummed_artifact_storage() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")

    assert "process.env.FOOTBALL_ARTIFACT_ROOT" in extension
    assert 'process.env.ONEDRIVECOMMERCIAL || process.env.ONEDRIVE' in extension
    assert '"event-review-state-innovation"' in extension
    assert "legacyStatePath(segment)" in extension
    assert "async function updateSharedChecksum(path, content = null)" in extension
    assert "async function readReviewState(path, fallback, verifyChecksum = false)" in extension
    assert "Shared review-state checksum mismatch" in extension
    assert '"00-governance"' in extension
    assert '"checksums.sha256"' in extension
    assert "Published validated reference" in extension


def test_shared_review_status_exposes_approvals_and_validation_gates() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert "const sharedReviewStatus = await Promise.all(" in extension
    assert "accepted: decisions.filter(" in extension
    assert 'regression: !stored.regression' in extension
    assert "blockers: plan.blockers" in extension
    assert "const unavailableProposalData" in extension
    assert "Stored decisions reference proposal data that is no longer" in extension
    assert "captureEngineSnapshot(segment.key, currentEngine.fingerprint)" in extension
    assert "const plan = published" in extension
    assert "sharedReviewStatus," in extension
    assert "Shared approvals &amp; validation gates" in renderer
    assert 'id="shared-review-status"' in renderer
    assert "state.sharedReviewStatus || []" in renderer
    assert '" gate blocker(s)"' in renderer


def test_activity_updates_are_module_scoped() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    broadcast_start = extension.index("function broadcast(eventName)")
    activity_start = extension.index("function setActivity(", broadcast_start)
    next_function = extension.index("function messagePrompt(", activity_start)

    assert "\n}\n\nfunction setActivity(" in extension[broadcast_start:next_function]
    assert extension.count("function setActivity(") == 1


def test_canvas_prepares_only_explicit_stream_sized_segments() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert "const reviewDurationSeconds = workflow.reviewDurationSeconds" in extension
    assert "reviewDurationSeconds: [20, 30, 60]" in extension
    assert "reviewDurationSeconds.includes(durationSeconds)" in extension
    assert 'url.pathname === "/api/prepare"' in extension
    assert 'localJson("/api/alfheim/segment"' in extension
    assert "duration_seconds: durationSeconds" in extension
    assert 'id="segment-start-minute"' in renderer
    assert 'id="segment-start-second"' in renderer
    assert 'id="segment-duration"' in renderer
    assert '<option value="30">30 seconds</option>' in renderer
    assert '<option value="60" selected>60 seconds</option>' in renderer
    assert 'fetch("/api/prepare"' in renderer
    assert "minute * 60 + second" in renderer
    assert "duration_seconds: duration" in renderer
    assert "source_id: state.segment.datasetId" in renderer
    assert "source_segment: state.segment.key" in renderer
    assert "candidate.key === sourceSegment" in extension
    assert "candidate.datasetId === sourceId" in extension


def test_live_canvas_prepares_twenty_second_segments() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert '<option value="20">20 seconds</option>' in renderer
    assert "Choose a 20-, 30-, or 60-second review duration." in renderer
    assert "Review duration must be exactly 20, 30, or 60 seconds" in extension
    assert "const reviewDurationSeconds = workflow.reviewDurationSeconds" in extension
    assert "reviewDurationSeconds: [20, 30, 60]" in extension
    assert "const cameraSampleDurationSeconds = workflow.cameraSampleDurationSeconds" in extension
    assert "cameraSampleDurationSeconds: [30, 60]" in extension


def test_canvas_runs_ai_only_after_explicit_action() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'url.pathname === "/api/analyze"' in extension
    assert '"/api/alfheim/innovation/analyze"' in extension
    assert 'id="process-segment"' in renderer
    assert 'fetch("/api/analyze"' in renderer
    assert 'processButton.addEventListener("click"' in renderer
    assert "Starting BAC-assisted Innovation analysis." in renderer
    assert "The Live ball tracker is not used." in renderer


def test_live_runner_rejects_media_manifest_duration_mismatch() -> None:
    runner = (
        Path(__file__).parents[1] / "scripts" / "process-alfheim-segment.py"
    ).read_text(encoding="utf-8")

    assert "declared_frame_count = declared_end_frame - declared_start_frame" in runner
    assert "duration_frame_count = round(declared_duration * fps)" in runner
    assert "declared_start_frame < 0" in runner
    assert "declared_end_frame > frame_count" in runner
    assert "declared_frame_count != duration_frame_count" in runner
    assert "Prepared live media does not match its raw-only manifest" in runner
    assert 'prepared.get("live_video", prepared["video"])' in runner


def test_live_runner_uses_supported_player_tracking_arguments() -> None:
    runner = (
        Path(__file__).parents[1] / "scripts" / "process-alfheim-segment.py"
    ).read_text(encoding="utf-8")
    player_cli = (
        Path(__file__).parents[1] / "src" / "football_poc" / "player_tracking_cli.py"
    ).read_text(encoding="utf-8")

    assert '"--ball-state-estimates"' not in runner
    assert '"--ball-tracks"' in runner
    assert '"--ball-tracks"' in player_cli
    assert "except subprocess.CalledProcessError as error:" in runner
    assert "See analysis.log for technical details." in runner


def test_live_canvas_summarizes_raw_pipeline_failures() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "function friendlyRunFailure(message)" in renderer
    assert 'detail.includes("player_tracking_cli")' in renderer
    assert 'detail.includes("--ball-state-estimates")' in renderer
    assert "That issue is fixed; click Retry " in renderer
    assert '"AI failed: " + friendlyRunFailure(segment.statusMessage)' in renderer
    assert 'return "Ball coordinates need review"' in renderer
    assert '"Ball coordinates need review: tracking completed with "' in renderer
    assert "Recover every additional frame supported by the raw video." in renderer
    assert "90% is the minimum gate, not the target." in renderer
    assert ".activity.coordinates-review strong" in renderer
    assert ".segment-status.coordinates-review" in renderer
    assert 'ballCoordinatesNeedReview() ? " coordinates-review" : ""' in renderer
    assert '? "coordinates-review"' in renderer
    assert '"Ball coordinates need review"' in extension
    assert "recover every additional frame supported by raw-video evidence" in extension


def test_live_activity_reflects_pipeline_state_after_extension_reload() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "function displayedActivity(selected, state)" in extension
    assert 'label: "AI processing locally"' in extension
    assert 'label: "Segment prepared — AI not started"' in extension
    assert "activity: displayedActivity(selected, state)" in extension
    assert ".activity.working .activity-dot::after" in renderer
    assert "radial-gradient(circle at 50% 50%, #f2cc60" in renderer
    assert "animation: pulse 1.2s ease-in-out infinite" in renderer


def test_live_canvas_shows_stage_elapsed_time_and_benchmark_eta() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "async function liveStageTiming(selected)" in extension
    assert 'basisSegment: defaultSegment' in extension
    assert 'selected.stageTiming = workflow.key === "live"' in extension
    assert "? await liveStageTiming(selected)" in extension
    assert '" · estimated remaining: about "' in renderer
    assert '" (benchmark-based, not a deadline)."' in renderer
    assert "the benchmark estimate has been exceeded, but the local" in renderer


def test_innovation_runner_rejects_media_manifest_duration_mismatch() -> None:
    runner = (
        Path(__file__).parents[1]
        / "scripts"
        / "process-alfheim-innovation-segment.py"
    ).read_text(encoding="utf-8")

    assert "declared_frame_count = declared_end_frame - declared_start_frame" in runner
    assert "duration_frame_count = round(duration * fps)" in runner
    assert "declared_start_frame < 0" in runner
    assert "declared_end_frame > frame_count" in runner
    assert "declared_frame_count != duration_frame_count" in runner
    assert 'prepared.get("innovation_video", prepared["video"])' in runner
    assert '"start_frame": declared_start_frame' in runner
    assert '"end_frame": declared_end_frame' in runner
    assert "Prepared Innovation media does not match its raw-only manifest" in runner


def test_alfheim_runners_use_committed_jersey_profile() -> None:
    for runner_name in (
        "process-alfheim-innovation-segment.py",
        "process-alfheim-segment.py",
    ):
        runner = (
            Path(__file__).parents[1] / "scripts" / runner_name
        ).read_text(encoding="utf-8")
        assert '"--team-profile",\n                "red-black"' in runner
        assert '"--goalkeeper-affiliations"' in runner
        assert '"window-555"' in runner
        assert '"goalkeeper-affiliations.json"' in runner


def test_innovation_runner_uses_frozen_detector_profile() -> None:
    runner = (
        Path(__file__).parents[1]
        / "scripts"
        / "process-alfheim-innovation-segment.py"
    ).read_text(encoding="utf-8")

    assert '"model": "yolo11n.pt"' in runner
    assert '"confidence": 0.12' in runner
    assert '"image_size": 960' in runner
    assert '"stride": 5' in runner
    assert '"tile_width": 1484' in runner
    assert '"tile_height": None' in runner
    assert '"overlap": 0.1' in runner
    assert (
        "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"
        in runner
    )
    assert "validate_innovation_detector_model(model)" in runner
    assert '"--tile-height"' not in runner
    assert '"--device"' not in runner
    assert '"football_poc.innovation_day_detector"' in runner
    assert '"football_poc.benchmark_cli"' not in runner


def test_innovation_detector_preserves_showcase_sequential_inference() -> None:
    detector = (
        Path(__file__).parents[1]
        / "src"
        / "football_poc"
        / "innovation_day_detector.py"
    ).read_text(encoding="utf-8")

    assert (
        "from football_poc.innovation_day_snapshot.benchmark "
        "import BenchmarkManifest"
    ) in detector
    assert "from football_poc.benchmark" not in detector
    assert "from football_poc.cli" not in detector
    assert "from football_poc.actions" not in detector
    assert "for completed, source_frame in enumerate(pending_frames" in detector
    assert '"source": crops' in detector
    assert '"batch":' not in detector
    assert "horizontal_tiles(" in detector
    assert "grid_tiles(" not in detector
    assert '"detector_implementation": "innovation_showcase_sequential_v1"' in detector


def test_live_canvas_uses_separate_engine_artifacts_and_review_state() -> None:
    innovation = EXTENSION.read_text(encoding="utf-8")
    live = LIVE_EXTENSION.read_text(encoding="utf-8")
    live_renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'canvasId: "football-event-review-live"' in live
    assert 'displayName: "Live Football Event Review"' in live
    assert "title: workflow.displayName" in live
    assert "context.input?.audit" not in live
    assert "mode=trajectory-audit" not in live
    assert "Ball Trajectory Audit" not in live
    assert "Live Iteration-25 Football Event Review" not in live
    assert 'defaultSegment: "segment-0540-020"' in live
    assert 'theme: "grassroots"' in live
    assert "const theme = workflow.theme" in live
    assert "let launcherRegistryUpdate = Promise.resolve();" in live
    assert "await writeJsonAtomically(launcherRegistryPath, registry);" in live
    assert 'data-app-theme="${appTheme}"' in live_renderer
    assert 'theme: "grassroots"' in live_renderer
    assert 'themeColor: "#080d14"' in live_renderer
    assert "Raw-video ball coordinates · Current engine" in live_renderer
    assert 'id="tracker-version"' in live_renderer
    assert 'id="rules-version"' in live_renderer
    assert "trackerIteration(selected)" in live_renderer
    assert "state.componentVersions?.tracker" in live_renderer
    assert "state.componentVersions?.rulesEngine" in live_renderer
    assert "\nasync function sourceVersion(files)" in live
    assert "\nasync function componentVersions()" in live
    assert '"src/football_poc/ball_tracking.py"' in live
    assert '"src/football_poc/match_state.py"' in live
    assert '"src/football_poc/possession.py"' in live
    assert 'artifactNamespace: "live"' in live
    assert (
        "return join(preparedSegmentRoot(segment), "
        "workflow.artifactNamespace)"
    ) in live
    assert '"/api/alfheim/live/analyze"' in live
    assert "/api/alfheim/live/status" in live
    assert 'stateDirectory: "event-review-state-live"' in live
    assert '"src/football_poc/ball_tracking.py"' in live
    assert '"src/football_poc/innovation_day_snapshot/match_state.py"' in innovation
    assert 'artifactNamespace: "innovation"' in innovation
    assert 'join(preparedSegmentRoot(segment), "copilot-review.json")' in live
    assert 'join(preparedSegmentRoot(segment), "copilot-review.json")' in innovation
    assert 'id="process-segment"' in live_renderer
    assert "football-event-review add_" not in live
    assert "football-event-review update_" not in live
    assert "football-event-review accept_" not in live
    assert "football-event-review publish_" not in live
    assert "football-event-review refresh_" not in live
    assert "football-event-review confirm_" not in live
    assert (
        'globalThis.__footballReviewWorkflowKey = "innovation"'
        in innovation
    )


def test_review_state_and_prompts_carry_hard_workflow_identity() -> None:
    innovation = EXTENSION.read_text(encoding="utf-8")
    live = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert 'workflowId: "innovation_day_bac"' in innovation
    assert 'canvasId: "football-event-review"' in innovation
    assert 'workflowId: "live_iteration_25"' in live
    assert 'canvasId: "football-event-review-live"' in live
    for extension in (innovation, live):
        assert "const workflowId = workflow.workflowId" in extension
        assert "const canvasId = workflow.canvasId" in extension
    for extension in (innovation, live):
        assert "state.workflowId && state.workflowId !== workflowId" in extension
        assert "state.canvasId && state.canvasId !== canvasId" in extension
        assert '"review_workflow_mismatch"' in extension
        assert "state.workflowId = workflowId" in extension
        assert "state.canvasId = canvasId" in extension
        assert "`Workflow ID: ${workflowId}. Canvas ID: ${canvasId}.`" in extension

    assert "This is the BAC-assisted Innovation workflow." in innovation
    assert (
        "This is the BAC-assisted Innovation workflow. Never invoke Live "
        "Canvas actions, read Live review state"
    ) in innovation
    assert "Never invoke " in live
    assert "Innovation Canvas actions" in live


def test_unrelated_state_integrity_error_does_not_blank_selected_canvas() -> None:
    for extension_path in (EXTENSION, LIVE_EXTENSION):
        extension = extension_path.read_text(encoding="utf-8")
        assert 'regression: "unavailable"' in extension
        assert "integrityError: true" in extension
        assert "Review state unavailable:" in extension
        assert "String(error.message || error)" in extension


def test_comparison_labels_show_event_frame_numbers() -> None:
    for renderer_path in (RENDERER, LIVE_RENDERER):
        renderer = renderer_path.read_text(encoding="utf-8")
        assert 'frame.className = "comparison-frame"' in renderer
        assert 'event.seconds.toFixed(3) + "s · frame "' in renderer
        assert "Math.round(event.seconds * 25)" in renderer


def test_every_innovation_acceptance_checks_its_regression_receipt() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")

    assert "\nasync function ensureInnovationRegressionsCurrent(segment, state)" in extension
    assert "tests/test_innovation_day_snapshot.py" in extension
    assert "tests/test_innovation_match_state_regression.py" in extension
    assert "tests/test_innovation_possession_regression.py" in extension
    assert "tests/test_innovation_review_regressions.py" in extension
    assert extension.count("await ensureInnovationRegressionsCurrent(segment,") == 2
    assert "isRegressionCurrent(state.regression, current)" in extension
    assert 'fullReceipt?.passed' in extension
    assert "(candidate) => candidate.validated" in extension
    assert "await queuePublishedInnovationRegression(" in extension
    assert "const segmentFailures = segmentResults.filter" in extension
    assert '"Acceptance pending: "' in extension
    assert 'coverage: "all_published_segments"' in extension
    assert "registry.last_full_regression" in extension
    assert "fullReceipt.engineContentHash === current.fingerprint.contentHash" in extension
    assert 'trigger: "reused_workflow_receipt"' in extension
    assert "reused: true, stale: false, passed: true" in extension
    assert '"Acceptance pending because protected tests failed: "' in extension
    assert "regressionFailures: regressionResult?.segmentFailures || []" in extension
    assert 'suite: "innovation"' in extension
    assert 'trigger: "acceptance"' in extension


def test_engine_output_never_becomes_a_copilot_proposal() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'if (segmentInfo.state !== "ready") return []' in extension
    load_drafts = extension[
        extension.index("async function loadDrafts("):
        extension.index("async function buildReplayRuns(")
    ]
    assert 'source: "engine_output"' not in load_drafts
    assert 'source: "copilot_review"' in extension
    assert "const engineEvents = snapshotEvents(" in extension
    assert "engineEvents," in extension
    assert "Red goalkeeper completed pass to headed receiver" in extension
    assert "header is the receiving action, not a second pass." in extension
    assert 'engineCandidate = draft.source === "engine_output"' in renderer
    assert '"AI engine detected"' in renderer
    assert "Event candidates remain hidden until the run completes." in renderer
    assert "Engine completed with " in renderer
    assert "Independent Copilot proposals have not been created yet." in renderer


def test_canvas_adds_isolated_custom_camera_samples() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert '"10-master-data", "custom-cameras"' in extension
    assert 'url.pathname === "/api/custom-camera"' in extension
    assert "saveCustomCameraSample(request, url)" in extension
    assert 'id="camera-name"' in renderer
    assert 'id="camera-club"' in renderer
    assert 'id="camera-venue"' in renderer
    assert 'id="camera-position"' in renderer
    assert 'id="camera-serial"' in renderer
    assert 'id="camera-sample"' in renderer
    assert 'id="add-camera"' in renderer
    assert "Camera sample must be exactly 30 or 60 seconds" in renderer
    assert "const cameraId = randomUUID()" in extension
    assert "manufacturer_serial_number: serialNumber || null" in extension
    assert "startsWith(\"custom-\")" in renderer
    assert "No merged review segment is available for this camera." in renderer
    assert "clearVideoSource()" in renderer


def test_source_change_resolves_url_before_stale_canvas_state() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    start = renderer.index("function selectedSegmentKey()")
    selected_key = renderer[start:start + 300]
    assert selected_key.index("new URLSearchParams(location.search)") < (
        selected_key.index("state?.segment?.key")
    )
    assert 'query.set("segment", segment)' in renderer


def test_match_replay_never_mixes_disjoint_segments() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert "buildReplayRuns(segments)" in extension
    assert "left.startSeconds - right.startSeconds" in extension
    assert "current.at(-1).startSeconds + current.at(-1).durationSeconds" in extension
    assert "continuityVerified: group.every" in extension
    assert "runs.filter(run => run.continuityVerified)" in renderer
    assert "separate clips are never mixed" in renderer
    assert "Available consecutive run" in renderer


def test_adjustment_request_rechecks_and_refreshes_the_proposal() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'name: "update_review_proposal"' in extension
    assert "state.proposalOverrides ||= {}" in extension
    assert ': "adjusted_proposal"' in extension
    assert "delete review.state.decisions[String(index)]" in extension
    assert '"Revised proposal ready"' in extension
    assert "unless that action succeeds." in extension
    assert "async function requestAdjustment({" in renderer
    assert "Describe what is inaccurate in the message box first." in renderer
    assert "Please re-check this proposal against the video." in renderer
    assert "a revised proposal will refresh here" in renderer
    assert '"Copilot-reviewed correction"' in renderer
    assert "Revised proposal ready · check it again" in renderer
    assert 'events.addEventListener("state", loadState)' in renderer
    assert "docs\\\\RULES_ENGINE_ARCHITECTURE.md" in extension
    assert "not a replacement for those global rules" in extension


def test_user_can_delegate_one_event_acceptance_to_copilot() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'url.pathname === "/api/copilot-accept"' in extension
    assert "copilotAcceptanceAuthorizations" in extension
    assert "proposalFingerprint(draft)" in extension
    assert 'name: "accept_review_proposal"' in extension
    assert '"copilot_acceptance_not_authorized"' in extension
    assert 'source: "copilot_verified"' in extension
    assert "only this selected proposal" in extension
    assert 'agentMode: allowChanges ? "autopilot" : "plan"' in extension
    assert 'agentMode: "autopilot"' in extension
    assert "This is Plan mode: answer and explain only." in extension
    assert 'engineComparison.status === "already_agrees"' in extension
    assert "Rerun only the cached event-building" in extension
    assert "The Live ball tracker is not used." in extension
    assert "timestamp-, frame-, clip-, or segment-specific exception" in extension
    assert "engine_fix_not_verified" in extension
    assert "engine_implementation_unchanged" in extension
    assert 'afterComparison.status !== "already_agrees"' in extension
    assert "record_regression_result" in extension
    assert 'id="copilot-accept"' in renderer
    assert "Verify, Accept &amp; Sync Engine (Autopilot)" in renderer
    assert "Ask Copilot (Plan mode)" in renderer
    assert 'async function sendReviewMessage(text, mode = "plan")' in renderer
    assert "synchronizing a general engine rule if the proposal is" in renderer
    assert "The existing E# already matches" in renderer
    assert "async function requestCopilotAcceptance(targetIndex = selectedIndex)" in renderer
    assert 'fetch("/api/copilot-accept"' in renderer


def test_user_can_verify_and_accept_events_as_one_batch() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'url.pathname === "/api/copilot-accept-all"' in extension
    assert "function copilotBulkAcceptancePrompt(" in extension
    assert 'scope: "batch"' in extension
    assert "never accept an event merely because" in extension
    assert "Leave unsupported or uncertain proposals unaccepted" in extension
    assert "without eventIndex so the batch summary appears only in the general" in extension
    assert 'id="accept-all-events"' in renderer
    assert "Verify &amp; Accept All Events (Autopilot)" in renderer
    assert "async function requestCopilotAcceptanceAll()" in renderer
    assert 'fetch("/api/copilot-accept-all"' in renderer


def test_completed_review_can_publish_only_through_the_final_gate() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'url.pathname === "/api/publish-reference"' in extension
    assert 'name: "publish_validated_reference"' in extension
    assert "publicationAuthorization" in extension
    assert "publicationFingerprint(" in extension
    assert "buildPublicationPlan(" in extension
    assert 'blocker.includes("fresh engine receipt")' in extension
    assert "decision.engineVerification = engineVerificationReceipt(" in extension
    assert "writeJsonAtomically(path, reference)" in extension
    assert "previousReference" in extension
    assert "writeTextAtomically(path, previousReference)" in extension
    assert "publishedSegment?.validated" in extension
    assert "state.publishedReference && !selected.validated" in extension
    assert "{...selected, validated: true}" in extension
    assert "review.state.publishedReference" in extension
    assert "reference_publication_blocked" in extension
    assert 'validationStatus: "passed"' in extension
    assert 'id="publish-reference"' in renderer
    assert "Publish Validated Reference (Autopilot)" in renderer
    assert "Boolean(state.publication?.reviewComplete)" in renderer
    assert "function referenceLocked()" in renderer
    assert "const canPublish =" in renderer
    assert 'fetch("/api/publish-reference"' in renderer
    assert "Running protected regressions and the final exact-match gate" in renderer


def test_live_publication_feedback_stays_beside_publish_button() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'id="publication-status"' in renderer
    assert 'const status = document.getElementById("publication-status");' in renderer
    assert '"neither eventIndex nor engineIndex' in extension
    publication_handler = renderer[
        renderer.index("async function requestReferencePublication()"):
        renderer.index("async function decide(")
    ]
    assert "clip-conversation-panel" not in publication_handler


def test_passed_live_segment_keeps_setup_and_review_navigation_enabled() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "function applyPassedSegmentLock()" in renderer
    assert 'document.querySelectorAll("button, input, textarea, select")' in renderer
    assert 'control.title = "This segment has passed and is locked."' in renderer
    for selector in (
        "#review-audience",
        "#source-select",
        "#segment-select",
        "#segment-start-minute",
        "#segment-start-second",
        "#segment-duration",
        "#prepare-segment",
        "#process-segment",
        "#camera-sample",
        "#add-camera",
        "#geometry-feature",
        "#edit-geometry",
        "#save-geometry",
        "#previous-event",
        "#next-event",
        "#previous-frame",
        "#next-frame",
        "#timeline",
        "#playback-speed",
        "#toggle-event-panel",
        "#show-ball-frames",
        "#zoom-action",
        "#enlarge",
        "#replay-run",
        "#replay-play",
        "#replay-restart",
        "[data-view-mode]",
        ".comparison-event",
        ".ball-frame-open",
    ):
        assert f'"{selector}"' in renderer


def test_publication_gate_excludes_rejections_and_match_state_annotations() -> None:
    script = """
      import assert from "node:assert/strict";
      const {buildPublicationPlan} = await import(process.argv[1]);

      const current = {
        fingerprint: {contentHash: "code"},
        outputHash: "output",
      };
      const receipt = {
        status: "already_agrees",
        engineContentHash: "code",
        outputHash: "output",
      };
      const drafts = [
        {seconds: 10, team: "black", type: "completed_pass"},
        {seconds: 20, team: "black", type: "completed_pass"},
        {seconds: 30, team: "red", type: "foul"},
      ];
      const decisions = {
        "0": {status: "accepted", engineVerification: receipt},
        "1": {status: "rejected"},
        "2": {status: "accepted", engineVerification: receipt},
      };
      const engineEvents = [
        {
          seconds: 10,
          team: "black",
          type: "completed_pass",
          reviewKey: "pass",
        },
        {
          seconds: 22,
          team: "red",
          type: "turnover",
          reviewKey: "engine-only",
        },
      ];
      const engineEventReviews = {
        "engine-only": {
          status: "confirmed",
          engineContentHash: "code",
          outputHash: "output",
        },
      };
      const verificationIsCurrent = (candidate) =>
        candidate?.engineContentHash === "code"
        && candidate?.outputHash === "output";
      const plan = buildPublicationPlan({
        drafts,
        decisions,
        engineEvents,
        engineEventReviews,
        current,
        snapshotMatches: true,
        verificationIsCurrent,
        regressionFresh: true,
      });
      assert.equal(plan.ready, true);
      assert.equal(plan.engineEventCount, 2);
      assert.deepEqual(plan.referenceEvents, [
        {
          clip_seconds: 10,
          team: "black",
          event_type: "completed_pass",
        },
        {
          clip_seconds: 22,
          team: "red",
          event_type: "turnover",
        },
      ]);

      const staleRegression = buildPublicationPlan({
        drafts,
        decisions,
        engineEvents,
        engineEventReviews,
        current,
        snapshotMatches: true,
        verificationIsCurrent,
        regressionFresh: false,
      });
      assert.equal(staleRegression.ready, false);
      assert.match(staleRegression.blockers.join(" "), /regressions/);

      const rejectedStillEmitted = buildPublicationPlan({
        drafts,
        decisions,
        engineEvents: [
          ...engineEvents,
          {
            seconds: 20,
            team: "black",
            type: "completed_pass",
            reviewKey: "rejected",
          },
        ],
        engineEventReviews: {
          ...engineEventReviews,
          rejected: {
            status: "confirmed",
            engineContentHash: "code",
            outputHash: "output",
          },
        },
        current,
        snapshotMatches: true,
        verificationIsCurrent,
        regressionFresh: true,
      });
      assert.equal(rejectedStillEmitted.ready, false);
      assert.match(
        rejectedStillEmitted.blockers.join(" "),
        /Rejected C2 is still emitted/,
      );

    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, PUBLICATION_GATE.as_uri()],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_live_publication_prioritizes_exact_manual_reference_over_duplicate_copilot() -> None:
    script = """
      import assert from "node:assert/strict";
      const {buildPublicationPlan} = await import(process.argv[1]);
      const current = {
        fingerprint: {contentHash: "code"},
        outputHash: "output",
      };
      const receipt = {
        status: "already_agrees",
        engineContentHash: "code",
        outputHash: "output",
      };
      const verificationIsCurrent = (candidate) =>
        candidate?.engineContentHash === "code"
        && candidate?.outputHash === "output";
      const duplicateCopilotAndManual = buildPublicationPlan({
        drafts: [
          {
            seconds: 17.8,
            team: "red",
            type: "completed_pass",
            source: "adjusted_proposal",
          },
          {
            seconds: 17.8,
            team: "red",
            type: "completed_pass",
            source: "manual_review",
          },
        ],
        decisions: {
          "0": {status: "accepted", engineVerification: receipt},
          "1": {status: "accepted", engineVerification: receipt},
        },
        engineEvents: [{
          seconds: 17.8,
          team: "red",
          type: "completed_pass",
          reviewKey: "shared",
        }],
        engineEventReviews: {},
        current,
        snapshotMatches: true,
        verificationIsCurrent,
        regressionFresh: true,
      });
      assert.equal(duplicateCopilotAndManual.ready, true);
      assert.deepEqual(duplicateCopilotAndManual.referenceEvents, [{
        clip_seconds: 17.8,
        team: "red",
        event_type: "completed_pass",
      }]);

      const manualFrameMismatch = buildPublicationPlan({
        drafts: [{
          seconds: 17.84,
          team: "red",
          type: "completed_pass",
          source: "manual_review",
        }],
        decisions: {
          "0": {status: "accepted", engineVerification: receipt},
        },
        engineEvents: [{
          seconds: 17.8,
          team: "red",
          type: "completed_pass",
          reviewKey: "manual-mismatch",
        }],
        engineEventReviews: {},
        current,
        snapshotMatches: true,
        verificationIsCurrent,
        regressionFresh: true,
      });
      assert.equal(manualFrameMismatch.ready, false);
      assert.match(
        manualFrameMismatch.blockers.join(" "),
        /Accepted M1 has no unique matching engine event/,
      );
    """
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            script,
            LIVE_PUBLICATION_GATE.as_uri(),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_clip_conversation_stays_separate_and_can_report_an_omission() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'url.pathname === "/api/clip-message"' in extension
    assert "function clipConversationPrompt(" in extension
    assert "This is the segment-level conversation in Plan mode." in extension
    assert "about any event, the current frame, or the overall clip" in extension
    assert "If an existing event needs correction" in extension
    assert 'name: "recommend_missing_event"' in extension
    assert 'url.pathname === "/api/confirm-missing-event"' in extension
    assert '"missing_event_handover_not_authorized"' in extension
    assert "confirmMissingEventPrompt(" in extension
    assert "normally ±2 seconds" in extension
    assert "Do not add or accept an event" in extension
    assert 'name: "add_review_proposal"' in extension
    assert "state.additionalProposals ||= []" in extension
    assert "review.state.additionalProposals.push(proposal)" in extension
    assert "state.pendingClipRequest ||= null" in extension
    assert "const pending = review.state.pendingClipRequest" in extension
    assert "message.eventIndex = index" not in extension
    assert '"review_event_duplicate"' in extension
    assert 'source: "manual_review"' in extension
    assert "genuinely missing event" in extension
    assert "determine its team and event type" in extension
    assert 'id="clip-conversation-panel"' not in renderer
    assert 'id="clip-messages"' not in renderer
    assert 'id="clip-composer"' not in renderer
    assert 'id="fullscreen-primary-action"' in renderer
    assert 'fetch("/api/clip-message"' in renderer
    assert "message => message.eventIndex === selectedIndex" in renderer


def test_live_canvas_removes_general_clip_conversation_ui() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'id="clip-conversation-panel"' not in renderer
    assert 'id="show-general-clip-conversation"' not in renderer
    assert 'id="clip-messages"' not in renderer
    assert 'id="clip-composer"' not in renderer
    assert 'mode === "autopilot" ? "autopilot" : "plan"' in extension
    assert 'body.scope === "current_time"' in extension
    assert "Evidence scope: the entire prepared clip." in extension
    assert "local ±2-second window" in extension
    assert "A supported missing event still requires the " in extension
    assert 'id="fullscreen-primary-action"' in renderer
    assert 'id="activity" aria-live="polite"' in renderer


def test_live_canvas_removes_general_manual_proposal_form() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'id="toggle-manual-review"' not in renderer
    assert 'id="manual-review-team"' not in renderer
    assert 'id="manual-review-note"' not in renderer
    assert 'url.pathname === "/api/manual-review-event"' in extension
    assert 'source: "manual_review"' in extension
    assert '["manual_review", "user_reported"].includes(draft.source)' in extension
    assert "Math.round(draft.seconds * 25) === Math.round(seconds * 25)" in extension
    assert "An equivalent manual M# already exists on this frame" in extension
    assert "This observation still requires independent video verification." in extension
    assert "It is not accepted and must be independently verified." in extension
    assert "Math.round(seconds * 25) === Math.round(draft.seconds * 25)" in extension
    assert '["manual_review", "user_reported"].includes' in renderer
    assert '(isManualReviewEvent(event) ? "M" : "C")' in renderer


def test_professional_reviewer_can_reject_engine_event_and_fix_engine() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'url.pathname === "/api/reviewer-reject-engine"' not in extension
    assert "rejectEngineEventByProfessionalReviewer" not in extension
    assert "Reject E# & fix engine" in renderer
    assert "rerun cached engine output" in renderer
    assert "replace the old E# list" in renderer
    assert "await requestEngineEventVerification(" in renderer
    assert 'userVerdict: "incorrect"' in renderer


def test_live_acceptance_can_correct_same_event_within_review_window() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert "Treat the proposal timestamp as a search anchor." in extension
    assert "Inspect up to ±3 seconds" in extension
    assert "preserveAcceptanceAuthorization=true" in extension
    assert "preserveAcceptanceAuthorization: { type: \"boolean\" }" in extension
    assert "acceptanceCorrectionAuthorized" in extension
    assert "proposalFingerprint({" in extension


def test_current_event_header_is_prominent() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'class="current-event-label">Current Event</span>' in renderer
    assert "font-size: var(--text-title-medium, 20px);" in renderer
    assert 'draft.seconds.toFixed(3) + "s · " + teamLabel(draft.team)' in renderer


def test_canvas_explains_verification_and_acceptance_workflow() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert "How to verify and accept" in renderer
    assert "Green C↔E:" in renderer
    assert "Red C# without E#:" in renderer
    assert "Red E# without C#:" in renderer
    assert "Yellow:" in renderer
    assert "no timestamp-specific fixes" in renderer
    assert 'class="comparison-guide" aria-label="Comparison guidance"' in renderer
    assert renderer.count('class="comparison-guide-column') == 3
    assert "<strong>General</strong>" in renderer
    assert "changes save automatically" in renderer
    assert "No arrow or manual" in renderer
    assert "<strong>Unmatched E#</strong>: verify the discrepancy" in renderer


def test_copilot_proposal_can_require_same_frame_engine_review() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'url.pathname === "/api/require-same-frame-review"' in extension
    assert "state.sameFrameReviewRequirements ||= {}" in extension
    assert "draft.sameFrameEngineReview" in extension
    assert "same rounded 25-fps" in extension
    assert 'id="require-same-frame-review"' in renderer
    assert "Require Same-Frame C↔E Timing" in renderer
    assert "event?.sameFrameEngineReview" in renderer
    assert "function requiresSameFrameReview(event)" in renderer


def test_adjusted_manual_event_keeps_manual_provenance() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert '["manual_review", "user_reported"].includes(draft.source)' in extension
    assert '? "manual_review"' in extension
    assert '"manual_engine_alignment_required"' in extension
    assert "This M# cannot be accepted until a fresh rules-only engine run" in extension
    assert "Only after refresh_engine_snapshot returns already_agrees" in extension


def test_exact_manual_matches_are_assigned_before_tolerant_copilot_matches() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "const assignedEngine = new Map();" in renderer
    assert "const reviewCandidates = (state?.drafts || [])" in renderer
    assert "Number(!requiresSameFrameReview(left.draft))" in renderer
    assert "assignedEngine.set(reviewIndex, match);" in renderer


def test_review_progress_uses_source_aware_event_reference() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert '"Verifying " + reviewReference(row.review, row.reviewIndex)' in renderer
    assert '"Copilot is verifying " + reference' in renderer
    assert '"Checking the accepted " + reviewReference(draft, targetIndex)' in renderer
    assert '"Copilot conversation for " + selectedReference' in renderer
    assert '"Ask Copilot about " + selectedReference + " (Plan)"' in renderer
    assert '"Verify " + selectedReference + ", Accept & Sync Engine"' in renderer
    assert '"Request " + selectedReference + " Adjustment"' in renderer
    assert '"This " + selectedReferenceKind + " has no matching E#.' in renderer


def test_initial_event_selection_does_not_scroll_the_page() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "if (document.fullscreenElement === videoShell) {" in renderer
    assert "requestAnimationFrame(scrollSelectedComparisonIntoView);" in renderer


def test_review_control_groups_have_clear_panel_spacing() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert ".review {" in renderer
    assert "flex-direction: column;" in renderer
    assert "gap: 20px;" in renderer
    assert ".review > .segment-builder," in renderer
    assert ".review > .match-replay {" in renderer
    assert ".segment-picker {" in renderer
    assert ".event-nav {" in renderer
    assert "border-top: 1px solid" in renderer


def test_active_event_stays_beside_video_without_page_scrolling() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'class="review-workspace"' in renderer
    assert 'class="media-column"' in renderer
    assert 'class="event-rail"' in renderer
    assert "grid-template-columns: minmax(0, 1.65fr)" in renderer
    assert "position: sticky;" in renderer
    assert "max-height: calc(100vh - 24px);" in renderer
    assert 'id="segment-builder-panel"' in renderer
    assert 'id="clip-conversation-panel"' not in renderer
    assert 'id="conversation-panel"' in renderer
    assert "segmentBuilderPanel.open =" in renderer
    assert "${adapter.conversationPrefix}Event 1" in renderer


def test_copilot_chat_is_embedded_and_scoped_to_the_selected_event() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'class="conversation" id="conversation-panel"' in renderer
    assert "This conversation contains only messages for the selected event." in renderer
    assert "message => message.eventIndex === selectedIndex" in renderer
    assert "reviewWorkflow.conversationPrefix + selectedReference" in renderer
    live_renderer = LIVE_RENDERER.read_text(encoding="utf-8")
    assert "reviewWorkflow.conversationPrefix + selectedReference" in live_renderer
    assert 'conversationPrefix: "Innovation Copilot for "' in renderer
    assert 'conversationPrefix: "Live Copilot for "' in live_renderer
    assert 'id="chat-status"' in renderer
    assert 'data-state="ready"' in renderer
    assert 'setChatMode("normal")' not in renderer
    assert 'id="chat-drag-handle"' not in renderer


def test_playback_surfaces_and_selects_each_triggered_event() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'id="copilot-event-trigger"' in renderer
    assert 'id="engine-event-trigger"' in renderer
    assert "left: 14px;" in renderer
    assert "background: rgb(13 17 23 / 72%);" in renderer
    assert "function playbackEventLabel(draft)" in renderer
    assert "function eventSourceLabel(draft)" in renderer
    assert '"Copilot-reviewed correction"' in renderer
    assert '"Copilot-prepared review"' in renderer
    assert "Proposal origin only; engine agreement is checked after acceptance." in renderer
    assert '"Manual review reference"' in renderer
    assert '"Validated reference"' in renderer
    assert 'completed_pass: "pass completed"' in renderer
    assert "function followPlaybackEvents()" in renderer
    assert 'selectEvent(event.index, {seek: false, pause: false})' in renderer
    assert "requestAnimationFrame(followPlaybackEvents)" in renderer
    assert 'class="fullscreen-events"' in renderer
    assert ".video-shell:fullscreen .fullscreen-events" in renderer
    assert "function renderFullscreenEvents()" in renderer
    assert "function comparisonRows()" in renderer
    assert "function comparisonStatus(review, engine)" in renderer
    assert "function canonicalComparisonLabel(event)" in renderer
    assert 'return teamLabel(event.team) + " " + typeLabel(event.type).toLowerCase()' in renderer
    assert 'label.textContent = canonicalLabel' in renderer
    assert '"Original description: " + event.title' in renderer
    assert 'id="comparison-summary"' in renderer
    assert '"matched", totals.matched + " synchronized"' in renderer
    assert '"stoppage", totals.stoppage + " foul/stoppage"' in renderer
    assert '"off", totals.off + " difference"' in renderer
    assert '"comparison-row " + row.status' in renderer
    assert ".comparison-row.has-review-actions { min-height: 54px; }" in renderer
    assert 'item.classList.add("has-review-actions")' in renderer
    assert "function comparisonReviewCell(row)" in renderer
    assert "function comparisonActionIcon(kind)" in renderer
    assert '"Decide Copilot proposal C" + (row.reviewIndex + 1)' in renderer
    assert "openCopilotDecisionModal(row.reviewIndex)" in renderer
    assert 'id="copilot-decision-modal"' in renderer
    assert 'id="accept-copilot-decision"' in renderer
    assert 'id="reject-copilot-decision"' in renderer
    assert 'id="cancel-copilot-decision"' in renderer
    assert "await requestCopilotAcceptance(reviewIndex)" in renderer
    assert 'await decide("rejected", reviewIndex)' in renderer
    assert 'async function decide(status, targetIndex = selectedIndex)' in renderer
    assert 'accepted.textContent = "✓ Accepted"' in renderer
    assert 'rejected.textContent = "✕ Rejected"' in renderer
    assert "const finalized = accepted || rejected;" in renderer
    assert "candidate => !candidate.decision" in renderer
    assert ".comparison-row.decision-rejected" in renderer
    assert '.filter((index) => !context.state.decisions[String(index)])' in extension
    assert "function comparisonEngineCell(row)" in renderer
    assert 'reviewed.textContent =' in renderer
    assert '? "✓ Approved"' in renderer
    assert ': "✓ Confirmed"' in renderer
    assert '"Verify engine event E" + (row.engineIndex + 1)' in renderer
    assert "async function requestEngineEventVerification(" in renderer
    assert 'fetch("/api/copilot-verify-engine"' in renderer
    assert 'name: "confirm_engine_event_reviewed"' in extension
    assert "function engineEventReviewPrompt(" in extension
    assert '"engine_event_review_not_authorized"' in extension
    assert "engineEventReviewAuthorizations" in extension
    assert "engineEventReviews" in extension
    assert 'return "reviewed"' in renderer
    assert ".comparison-action.accept-action" in renderer
    assert 'id="review-progress-overlay"' in renderer
    assert 'id="review-progress-text"' in renderer
    assert '"Copilot is verifying "' in renderer
    assert "+ reviewReference(state.drafts[selectedIndex], selectedIndex)" in renderer
    assert '"Verifying " + reviewReference(row.review, row.reviewIndex)' in renderer
    assert 'cell.classList.add("verifying")' in renderer
    assert '"E" + (engineIndex + 1)' in renderer
    assert '" ↔ C" + (reviewIndex + 1)' in renderer
    assert '"Manual M#" : "Review proposal"' in renderer
    assert '"Rules engine E#" : "Rules engine output"' in renderer
    assert 'id="compact-engine-rail"' in renderer
    assert "state?.engineEvents || []" in renderer


def test_live_video_overlay_counts_triggered_statistics() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'class="live-stats-overlay"' in renderer
    assert 'aria-label="${adapter.statisticsLabel}"' in renderer
    assert "<strong>${adapter.statisticsTitle}</strong>" in renderer
    assert 'statisticsLabel: "Innovation segment statistics"' in renderer
    assert 'statisticsTitle: "Match stats"' in renderer
    assert 'id="live-stats-time"' in renderer
    assert 'id="live-red-passes"' in renderer
    assert 'id="live-black-turnovers"' in renderer
    assert "background: rgb(13 17 23 / 68%);" in renderer
    assert "function updateLiveStatistics(seconds)" in renderer
    assert "event.seconds <= seconds + 0.001" in renderer
    assert 'event.decision?.status === "rejected"' in renderer
    assert "updateLiveStatistics(seconds);" in renderer


def test_fullscreen_event_panel_can_hide_and_video_can_step_forward() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'id="toggle-event-panel"' in renderer
    assert 'aria-controls="fullscreen-events"' in renderer
    assert ".video-shell:fullscreen.events-hidden .fullscreen-events" in renderer
    assert 'videoShell.classList.toggle("events-hidden")' in renderer
    assert 'hidden ? "Show event panel" : "Hide event panel"' in renderer
    assert 'id="next-frame"' in renderer
    assert "video.currentTime + 1 / 25" in renderer


def test_fullscreen_video_supports_slow_and_fast_playback() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'id="playback-speed"' in renderer
    assert '<option value="0.25">0.25×</option>' in renderer
    assert '<option value="0.5">0.5×</option>' in renderer
    assert '<option value="1" selected>1×</option>' in renderer
    assert '<option value="2">2×</option>' in renderer
    assert "video.playbackRate = Number(event.currentTarget.value);" in renderer
    assert "const seconds = Math.min(60, Math.max(0, video.currentTime || 0));" in renderer


def test_live_canvas_shows_only_the_relevant_prepare_or_ai_action() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "function segmentInputsMatchSelection()" in renderer
    assert "prepareButton.hidden = selectedVideoPrepared" in renderer
    assert "processButton.hidden = !selectedVideoPrepared" in renderer
    assert (
        "[startMinute, startSecond, segmentDuration].forEach(control =>"
        in renderer
    )
    assert 'control.addEventListener("input", renderRunControls)' in renderer


def test_innovation_requires_evidence_before_rules_engine_processing() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")
    adapter = (
        Path(__file__).parents[1]
        / ".github"
        / "extensions"
        / "football-event-review"
        / "shared"
        / "workflow-adapters.mjs"
    ).read_text(encoding="utf-8")
    runner = (
        Path(__file__).parents[1]
        / "scripts"
        / "process-alfheim-innovation-segment.py"
    ).read_text(encoding="utf-8")

    assert "evidencePreparationEnabled: true" in adapter
    assert 'id="prepare-innovation-evidence"' in renderer
    assert 'fetch("/api/innovation/prepare-evidence"' in renderer
    assert '"Prepare BAC + player context"' in renderer
    assert '"Process AI rules engine"' in renderer
    assert "segment.evidenceReady" in renderer
    assert "preparedUrl.searchParams.set(" in renderer
    assert "innovation_evidence_required" in extension
    assert "evidence_only: true" in extension
    assert "events_only: workflow.key === \"innovation\"" in extension
    assert 'mode.add_argument("--evidence-only"' in runner
    assert '"evidence_ready"' in runner
    assert "No football events have been generated." in runner
    assert 'selected.state === "evidence_ready"' in extension
    assert '"No frozen BAC coordinate track is available"' in extension


def test_innovation_state_polling_retries_and_shows_detection_progress() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'const maximumAttempts = method === "GET" ? 3 : 1;' in extension
    assert "setTimeout(resolve, attempt * 75)" in extension
    assert "const publicStateRequests = new Map();" in extension
    assert "await coalescedPublicState(requestedSegment(url)" in extension
    assert 'segment.stage === "player_detection"' in renderer
    assert '" sampled frames. "' in renderer
    assert "Number(segment.processedFrames || 0)" in renderer
    assert "Number(segment.expectedFrames)" in renderer
    assert "function syncInnovationAnalysisModal(segment)" in renderer
    assert '"Target: " + timeLabel' in renderer
    assert '"Innovation rules engine: " + eventsStatus' in renderer
    assert '"BAC + player context complete"' in renderer
    assert '"Innovation rules engine complete"' in renderer
    assert '"Detecting player context"' in renderer
    assert '"Preparing Innovation evidence"' in extension
    assert "if (state?.segment) syncInnovationAnalysisModal(state.segment);" in renderer
    assert "applySegmentProcessingLock();\n      syncInnovationAnalysisModal(segment);" in renderer
    assert "@media (max-width: 700px)" in renderer
    assert ".ball-frame-table th:nth-child(n + 6)" in renderer
    assert '<th scope="col">Frame</th>' in renderer


def test_innovation_rules_run_does_not_start_copilot_review() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert "automaticCopilotReview: null" in extension
    assert 'code: "manual_first_workflow"' in extension
    assert (
        '"Automatic C# generation is disabled in the manual-first '
        'Innovation workflow"'
    ) in extension
    assert 'if (reviewWorkflow.key === "innovation") return;' in renderer
    assert '"Manual M# review is ready. Copilot diagnostics remain optional."' in renderer


def test_innovation_manual_reference_helpers_cover_seed_mapping_and_history() -> None:
    shared = (
        EXTENSION.path.parent / "shared" / "review-extension.mjs"
    ).read_text(encoding="utf-8")
    helpers = shared[
        shared.index("export const innovationManualSeed"):
        shared.index("let session;")
    ].replace("export const ", "const ").replace("export function ", "function ")
    normalized_helpers = shared[
        shared.index("function applyNormalizedManualReference("):
        shared.index("async function persistNormalizedManualReference(")
    ]
    public_state = shared[
        shared.index("export async function publicState("):
        shared.index("function sendJson(")
    ].replace("export async function ", "async function ", 1)
    script = """
      import assert from "node:assert/strict";
      import {createHash} from "node:crypto";
      %s
      %s
      const totals = innovationManualSeed.reduce((result, event) => {
        const key = event.team + ":" + event.type;
        result[key] = (result[key] || 0) + 1;
        return result;
      }, {});
      assert.equal(innovationManualSeed.length, 25);
      assert.deepEqual(totals, {
        "black:completed_pass": 18,
        "black:turnover": 3,
        "red:completed_pass": 2,
        "red:turnover": 2,
      });
      assert.equal(innovationManualSeed.at(-1).seconds, 60);

      const state = {additionalProposals: []};
      assert.equal(
        ensureInnovationManualReference(state, "segment-0080-020"),
        true,
      );
      assert.equal(
        ensureInnovationManualReference(state, "segment-0080-020"),
        false,
      );
      assert.equal(state.manualReference.events.length, 25);

      const reference = {
        revision: 0,
        events: [],
        mappings: {},
        audit: [],
        approved: null,
        approvalHistory: [],
      };
      mutateInnovationManualReference(reference, {
        action: "create", timestampMs: 60000, team: "red",
        eventType: "completed_pass",
      });
      assert.equal(reference.events[0].sourceFrame, 1499);
      mutateInnovationManualReference(reference, {
        action: "create", timestampMs: 10000, team: "black",
        eventType: "turnover",
      });
      assert.deepEqual(activeManualEvents(reference).map(event => event.key), [
        "M2", "M1",
      ]);
      mutateInnovationManualReference(reference, {
        action: "edit", manualKey: "M1", timestampMs: 59999,
        team: "red", eventType: "turnover",
      });
      assert.equal(reference.events[0].revision, 2);
      mutateInnovationManualReference(reference, {
        action: "delete", manualKey: "M2",
      });
      assert.equal(activeManualEvents(reference).length, 1);
      mutateInnovationManualReference(reference, {action: "undo"});
      assert.equal(activeManualEvents(reference).length, 2);
      mutateInnovationManualReference(reference, {action: "undo"});
      assert.equal(reference.events[0].timestampMs, 60000);
      assert.equal(reference.events[0].type, "completed_pass");
      assert.ok(reference.audit.some(record => record.action === "undo"));

      mutateInnovationManualReference(reference, {
        action: "reject", manualKey: "M2",
      });
      assert.equal(activeManualEvents(reference).length, 1);
      assert.equal(visibleManualEvents(reference).length, 2);
      assert.equal(reference.events[1].reviewStatus, "rejected");
      assert.equal(reference.events[1].deleted, false);
      assert.ok(reference.events[1].rejectedAt);
      assert.ok(reference.audit.some(record => record.action === "reject"));
      assert.deepEqual(
        suggestManualMappings(
          visibleManualEvents(reference),
          [{key: "E1", seconds: 10, team: "black", type: "turnover"}],
        ),
        {},
      );
      const normalizedState = {manualReference: reference};
      applyNormalizedManualReference(normalizedState, {
        draft: {
          events: activeManualEvents(reference),
          mappings: {},
          revision: 1,
        },
      });
      assert.equal(
        normalizedState.manualReference.events.find(
          event => event.key === "M2",
        ).reviewStatus,
        "rejected",
      );
      mutateInnovationManualReference(reference, {
        action: "restore", manualKey: "M2",
      });
      assert.equal(activeManualEvents(reference).length, 2);
      assert.equal(reference.events[1].reviewStatus, "active");
      assert.equal(reference.events[1].rejectedAt, null);
      assert.ok(reference.audit.some(record => record.action === "restore"));

      mutateInnovationManualReference(reference, {
        action: "map", manualKey: "M1", engineKey: "E1",
      });
      mutateInnovationManualReference(reference, {
        action: "map", manualKey: "M2", engineKey: "E1",
      });
      assert.deepEqual(reference.mappings, {M2: "E1"});
      const approved = mutateInnovationManualReference(reference, {
        action: "approve",
      });
      assert.equal(approved.events.length, 2);
      assert.equal(Object.keys(approved.mappings).length, 1);
      assert.equal(approved.fingerprint.length, 64);
      mutateInnovationManualReference(reference, {action: "reopen"});
      assert.equal(reference.approvalHistory.length, 1);
      assert.equal(reference.audit.at(-1).nonUndoable, true);
      assert.throws(
        () => mutateInnovationManualReference(reference, {action: "undo"}),
        /no manual change/,
      );

      const suggestions = suggestManualMappings(
        [{key: "M1", timestampMs: 1000, seconds: 1, team: "black",
          type: "completed_pass", active: true, deleted: false}],
        [{key: "E1", seconds: 1, team: "black", type: "completed_pass"}],
      );
      assert.equal(suggestions.M1.engineKey, "E1");
      assert.equal(suggestions.M1.highConfidence, true);
      assert.equal(suggestions.M1.exact, true);
      assert.equal(suggestions.M1.withinTolerance, true);
      assert.equal(suggestions.M1.typeConflict, false);
      const adjacentFrame = suggestManualMappings(
        [{key: "M1", timestampMs: 3030, seconds: 3.03, team: "black",
          type: "completed_pass", active: true, deleted: false}],
        [{key: "E1", seconds: 3, team: "black", type: "completed_pass"}],
      );
      assert.equal(adjacentFrame.M1.engineKey, "E1");
      assert.equal(adjacentFrame.M1.exact, false);
      assert.equal(adjacentFrame.M1.withinTolerance, true);
      assert.deepEqual(
        suggestManualMappings(
          [{key: "M1", timestampMs: 1000, seconds: 1, team: "black",
            type: "completed_pass", active: true, deleted: false}],
          [{key: "E1", seconds: 2.001, team: "black", type: "completed_pass"}],
        ),
        {},
      );
      assert.deepEqual(
        suggestManualMappings(
          [
            {key: "M1", timestampMs: 3000, seconds: 3, team: "black",
              type: "completed_pass", active: true, deleted: false},
            {key: "M2", timestampMs: 3030, seconds: 3.03, team: "black",
              type: "completed_pass", active: true, deleted: false},
          ],
          [{key: "E1", seconds: 3, team: "black", type: "completed_pass"}],
        ),
        {},
      );

      mutateInnovationManualReference(reference, {
        action: "reject", manualKey: "M2",
      });
      %s
      const publicPayload = await publicState("segment-test", {}, {
        workflowKey: "innovation",
        state: {manualReference: reference},
        copilotEvents: [{seconds: 2, team: "red", type: "turnover"}],
        engineEvents: [
          {key: "E1", seconds: 3.5, team: "red", type: "turnover"}
        ],
      });
      assert.equal(publicPayload.manualEvents.length, 1);
      assert.equal(publicPayload.rejectedManualEvents.length, 1);
      assert.equal(publicPayload.rejectedManualEvents[0].key, "M2");
      assert.deepEqual(publicPayload.manualReference.suggestions, {});
      assert.equal(publicPayload.copilotEvents[0].key, "C1");
      assert.ok(publicPayload.manualReference.suggestions);
      const livePayload = await publicState("segment-test", {}, {
        workflowKey: "live",
        state: {},
        copilotEvents: [],
        engineEvents: [],
      });
      assert.deepEqual(
        {
          manualEvents: livePayload.manualEvents,
          rejectedManualEvents: livePayload.rejectedManualEvents,
          copilotEvents: livePayload.copilotEvents,
          manualReference: livePayload.manualReference,
        },
        {
          manualEvents: [],
          rejectedManualEvents: [],
          copilotEvents: [],
          manualReference: null,
        },
      );

      const legacy = {
        additionalProposals: [],
        decisions: {"0": {status: "accepted"}},
        proposalOverrides: {"0": {seconds: 2}},
        sameFrameReviewRequirements: {"0": true},
        copilotAcceptanceAuthorizations: {"0": {authorized: true}},
      };
      ensureInnovationManualReference(legacy, "segment-0000-020");
      assert.deepEqual(legacy.decisions, {});
      assert.deepEqual(legacy.proposalOverrides, {});
      assert.deepEqual(legacy.sameFrameReviewRequirements, {});
      assert.deepEqual(legacy.copilotAcceptanceAuthorizations, {});
      assert.equal(
        legacy.legacyCopilotDiagnostics.indexState.decisions["0"].status,
        "accepted",
      );
    """ % (helpers, normalized_helpers, public_state)
    result = subprocess.run(
        ["node", "--input-type=module"],
        input=script,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_innovation_manual_first_ui_and_live_gating_contracts() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")
    live_renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    for text in (
        "Black completed pass",
        "Black turnover",
        "White/red completed pass",
        "White/red turnover",
        "Approve minute as golden",
        "Undo last change",
        "Show Copilot C# reference",
        "diagnostic only",
        "No engine match within one second",
        "Automatically matched to ",
        "changes save automatically",
    ):
        assert text in renderer
    assert 'data-manual-team="black"' in renderer
    assert 'data-manual-team="red"' in renderer
    assert renderer.count('data-manual-type="completed_pass"') >= 4
    assert renderer.count('data-manual-type="turnover"') >= 4
    assert "Add M# at the current video time:" in renderer
    assert 'id="show-bac-coordinate"' in renderer
    assert "Show BAC ball coordinate" in renderer
    assert '"BAC · frame " + frame + " · x "' in renderer
    assert "showBacCoordinate = event.currentTarget.checked" in renderer
    assert "video.pause();" in renderer
    assert 'action: "create"' in renderer
    assert 'action: "edit"' in renderer
    assert 'action: "delete"' in renderer
    assert 'action: "undo"' in renderer
    assert 'action: "approve"' in renderer
    assert 'action: "reopen"' in renderer
    assert "event.seconds.toFixed(3)" in renderer
    assert '"s · frame "' in renderer
    assert '"s · Δ"' in renderer
    assert 'details.className = "manual-editor-details"' in renderer
    assert 'summary.textContent = "Edit " + row.review.key' in renderer
    assert "time, team, event type, or delete it" in renderer
    assert 'reviewMissing.className = "comparison-action icon-action"' in renderer
    assert '"Review missing E# for " + row.review.key' in renderer
    assert 'reviewMissing.append(comparisonActionIcon("verify"))' in renderer
    assert 'id="manual-engine-review-modal"' in renderer
    assert 'name="manual-engine-review-decision"' in renderer
    assert "Correct — the engine missed this M#" in renderer
    assert "Event exists, but M# details need editing" in renderer
    assert "Reject M# — not supported by the video" in renderer
    assert "Remove M# — added in error" in renderer
    assert 'action: decision === "reject" ? "reject" : "delete"' in renderer
    assert 'action: "restore"' in renderer
    assert "excluded from golden set" in renderer
    assert "Cannot verify from this camera" in renderer
    assert "manualKey: event.key" in renderer
    assert 'context.drafts.findIndex((event) => event.key === manualKey)' in extension
    assert 'fetch(\n          "/api/copilot-review-manual-engine"' in renderer
    assert 'url.pathname === "/api/copilot-review-manual-engine"' in extension
    assert "function manualEngineDiscrepancyPrompt(" in extension
    assert "let manualEngineReviewPending = null;" in renderer
    assert 'button.textContent = "Copilot is working…"' in renderer
    assert "function syncManualEngineReviewModal()" in renderer
    assert "M#/E# rows refreshed." in renderer
    assert 'id="fullscreen-event-chat"' in renderer
    assert 'class="fullscreen-event-chat"' in renderer
    assert ".fullscreen-event-chat[hidden]" in renderer
    assert "flex: 1 1 auto;" in renderer
    assert ".fullscreen-event-chat[open]" in renderer
    assert ".fullscreen-event-chat:not([open])" in renderer
    assert "flex: 0 0 min(220px, 48%);" in renderer
    assert "new ResizeObserver(clampPanelToShell).observe(panel);" in renderer
    assert "selectedConversation.length === 0" in renderer
    assert 'time.addEventListener("change", saveImmediately)' in renderer
    assert "const manualTimeDrafts = new Map()" in renderer
    assert "let fullscreenEventsRenderSignature = null;" in renderer
    assert "renderSignature === fullscreenEventsRenderSignature" in renderer
    assert 'target.querySelectorAll(".manual-editor-details[open]")' in renderer
    assert "if (editor) editor.open = true;" in renderer
    assert "fullscreenEventsRenderSignature = renderSignature;" in renderer
    assert "forceFullscreenEventsRender = true;" in renderer
    assert "manualTimeDrafts.set(row.review.key, time.value)" in renderer
    assert "manualTimeDrafts.delete(row.review.key)" in renderer
    assert 'if (event.key !== "Enter") return;' in renderer
    assert "setTimeout(saveImmediately, 350)" not in renderer
    assert 'time.inputMode = "decimal"' in renderer
    assert 'time.placeholder = "Seconds, e.g. 18.180…"' in renderer
    assert 'time.autocomplete = "off"' in renderer
    assert "time.dataset.manualTime = row.review.key" in renderer
    assert 'document.activeElement.matches("[data-manual-time]")' in renderer
    assert "align-content: start;" in renderer
    assert "grid-template-columns: minmax(0, 1fr) minmax(100px, .62fr);" in renderer
    assert "timestampMs: Math.round(seconds * 1000)" in renderer
    assert 'team.addEventListener("change", saveImmediately)' in renderer
    assert 'type.addEventListener("change", saveImmediately)' in renderer
    assert "Map to E#" not in renderer
    assert "Replace mapping" not in renderer
    assert "Remove mapping" not in renderer
    assert 'reviewWorkflow.key === "innovation"' in renderer
    assert 'workflow.key === "innovation"' in extension
    assert "manualEvents," in extension
    assert "copilotEvents:" in extension
    assert "manualReference:" in extension
    assert "state.manualReference.mappings" in extension
    assert '"/api/coordination/manual-reference?workflow="' in extension
    assert 'localJson("/api/coordination/manual-reference"' in extension
    assert "persistNormalizedManualReference(" in extension
    assert "applyNormalizedManualReference(" in extension
    assert "additionalProposals: []" in extension
    assert '(reviewWorkflow.key === "innovation" && !selectedEngine)' in renderer
    assert "automatic matches (±1s)" in renderer
    assert "within one second" in renderer

    # Shared code is present for Live, but every new element is emitted only by
    # the Innovation template branch and the original Live acceptance remains.
    assert '${adapter.key === "innovation" ? `' in live_renderer
    assert 'url.pathname === "/api/copilot-accept-all"' in extension


def test_copilot_review_can_be_cancelled_from_the_panel() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'url.pathname === "/api/cancel-review"' in extension
    assert 'status: "cancelled"' in extension
    assert "delete review.state.engineEventReviewAuthorizations[" in extension
    assert '"automatic_review_cancelled"' in extension
    assert 'id="segment-loading-cancel"' in renderer
    assert 'id="cancel-copilot-review"' in renderer
    assert 'fetch("/api/cancel-review"' in renderer
    assert 'reviewStatus === "cancelled"' in renderer


def test_live_main_conversations_start_after_coordinate_minimum() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "function ballCoordinateReviewCanBeVerified(selected)" in extension
    assert 'label: "Ball coordinate gate passed"' in extension
    assert "Choose Finalize to proceed now, or continue reviewing" in extension
    assert "!ballCoordinateReviewCanBeVerified(context.selected)" in extension
    assert "events_only: true" in extension
    assert '"Rules engine running"' in extension
    assert (
        "Copilot must verify the current tracker code and coordinate output first"
        not in extension
    )
    assert 'return "Ball coordinate gate passed";' in renderer
    assert 'state?.coordinateReview?.status' in renderer
    assert '"coordinate-verified"' in renderer
    assert 'id="proceed-after-coordinate-gate"' in renderer
    assert 'id="continue-coordinate-review"' in renderer
    assert "Proceed to event review" in renderer
    assert "Start rules-engine run" in renderer
    assert "gateDirectCount >= Math.ceil(gateSampledCount * 0.90)" in renderer
    assert (
        "finalize.disabled = !coordinateMinimumReached || segmentRunActive();"
        in renderer
    )
    assert '"Starting the rules engine from the current coordinates…"' in renderer
    assert '"Improve coverage: review " + leftoverCoordinateFrames' in renderer
    assert "() => void finalizeBallCoordinateReview()" in renderer
    assert 'selectedBatch?.status === "ready" && initialFrames.length' in renderer
    assert "Integrity-demoted only" in renderer
    assert "Download audit JSON" not in renderer
    assert "trajectoryAuditMode" not in renderer
    assert '"needs_more_checking"' in renderer
    assert "Ball undefined / not visible" in renderer
    assert "YOLO candidate is correct" in renderer
    assert '"YOLO candidate " + (candidateIndex + 1) + " is correct"' in renderer
    modal_yolo_section = renderer[
        renderer.index("const displayedYoloCandidates"):
        renderer.index("const observation = ballCoordinateObservations")
    ]
    assert ") <= 4" not in modal_yolo_section
    assert 'decision: "yolo_candidate"' in renderer
    assert "candidateIndex," in renderer
    assert "confidence: Number(candidate.confidence || 0)" in renderer
    assert '"yolo_candidate",' in extension
    assert 'observation.decision !== "yolo_candidate"' in extension
    assert "YOLO candidate confirmed" in renderer
    assert "Use when the ball is hidden, occluded, or not visible" in renderer
    assert "User coordinate-review outcomes for independent review" in extension
    assert "specified as the claim that the " in extension
    assert "never reference " in extension
    assert "calculate " in extension
    assert '"success against them, or create frame-specific code."' in extension
    assert '"needs_more_checking",' in extension
    assert 'const lockPath = `${manifestPath}.lock`;' in extension
    assert 'lockHandle = await open(lockPath, "wx");' in extension
    assert 'id="coordinate-decision-guide"' in renderer
    assert "Choose an evidence outcome" in renderer
    assert "the proposed coordinate is supported." in renderer
    assert "the ball is visible elsewhere." in renderer
    assert "the single camera cannot show the ball, including player occlusion." in renderer
    assert "the image is ambiguous but potentially reviewable." in renderer
    assert 'document.getElementById("needs-more-checking").hidden = false;' not in renderer
    assert (
        '["undefined", "needs_more_checking"].includes(observation.decision)'
        in extension
    )
    assert (
        'document.getElementById("needs-more-checking").disabled =\n'
        "        selectedRawBallFrame !== selectedBallTargetFrame\n"
        '        || state.coordinateReview?.status === "finalized"\n'
        '        || selectedCoordinateBatch()?.status === "done";'
        in renderer
    )
    assert "integrityRejectedFrames" in extension
    assert "yoloCandidates" in extension
    assert '<details class="fullscreen-event-chat" id="fullscreen-event-chat"' in renderer
    assert 'id="clip-conversation-panel"' not in renderer
    assert (
        '<section class="conversation" id="conversation-panel" data-ai-gated'
        in renderer
    )
    assert 'state.coordinateReview?.status === "finalized"' in renderer
    assert '<aside class="event-rail" data-ai-gated' in renderer
    assert "&& !segmentPreparationPending" in renderer
    assert "&& !runStartPending" in renderer
    assert "AI and Copilot conversations are disabled." in renderer
    assert 'content: "Disabled";' in renderer
    assert "filter: grayscale(1)" in renderer


def test_live_canvas_displays_ball_coordinate_coverage_in_both_views() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert '"ball-provenance.json"' in extension
    assert "ballProvenance," in extension
    assert 'id="ball-coordinate-coverage"' in renderer
    assert 'id="fullscreen-ball-coverage"' in renderer
    assert "function ballCoordinateCoverage(provenance)" in renderer
    assert '"% · " + direct + "/" + total + " direct"' in renderer
    assert "function ballPointAtRawFrame(frame)" in renderer
    assert '"raw_frame_path_interpolation"' in renderer
    assert "const displayedPoint = ballPointAtRawFrame(selectedRawBallFrame)" in renderer
    assert '"Engine path at context frame " + selectedRawBallFrame' in renderer


def test_live_canvas_can_rerun_a_segment_with_local_progress_and_locks() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")
    runner = (
        Path(__file__).parents[1] / "scripts" / "process-alfheim-segment.py"
    ).read_text(encoding="utf-8")

    assert '"Rerun Segment from Start"' in renderer
    assert '"Retry Segment from Start"' in renderer
    assert '"Resume from Saved Detections"' in renderer
    assert "resumeAfterDetection: state.segment.recoveryAvailable" in renderer
    assert 'selected.recoveryAvailable = workflow.key === "live" && Boolean(' in LIVE_EXTENSION.read_text(
        encoding="utf-8"
    )
    assert '"--resume-after-detection"' in runner
    assert '"interrupted_run_recovery"' in runner
    assert "No cold-path performance claim was produced." in runner
    assert "function segmentRunActive()" in renderer
    assert "function applySegmentProcessingLock()" in renderer
    assert "runStartPending = true" in renderer
    assert "segmentPreparationPending = true" in renderer
    assert 'section.classList.toggle("segment-processing-locked", running)' in renderer
    assert "minimum 90%" in renderer
    assert "Step 1 of 6 — Detecting raw-video frames" in renderer
    assert "Step 4 of 6 — Validating direct ball coordinates" in renderer
    assert "Step 6 of 6 — Publishing local event output" in renderer
    assert "Next: unlock the completed segment for review." in renderer
    assert "Preparation complete. No AI has run. Next: click Start AI." in renderer
    assert "This does not invoke Copilot." in renderer
    assert 'results / "ball-provenance.json"' in runner
    assert "ball_state_estimates," in runner
    assert "validate_ball_provenance(" in runner


def test_live_canvas_has_segment_scoped_ball_frame_inspector() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert '"ball-state-estimates.json"' in extension
    assert "states: (statePayload?.states || [])" in extension
    assert 'id="ball-frame-items"' in renderer
    assert 'id="ball-frame-modal"' in renderer
    assert 'id="ball-frame-modal-video"' in renderer
    assert "function renderBallFrames()" in renderer
    assert 'id="ball-frame-filter"' in renderer
    assert '"Estimated only (" + estimated + ")"' in renderer
    assert '"Latest Round " + batch.number + " review ("' in renderer
    assert "All frames is read-only and shows persisted direct coordinates only." in renderer
    assert "function ballFrameFlagStorageKey()" in renderer
    assert "function saveBallFrameFlags()" in renderer
    assert "let ballFrameSaveQueue = Promise.resolve();" in renderer
    assert "ballFrameSaveQueue.catch(() => {}).then(async () => {" in renderer
    assert "let stateSaveQueue = Promise.resolve();" in extension
    assert "stateSaveQueue.catch(() => {}).then(async () => {" in extension
    assert '"Decision saved"' in renderer
    assert '"Pending decision"' in renderer
    assert '<th scope="col">Review status</th>' in renderer
    assert '<th scope="col">Your decision</th>' in renderer
    assert '"Agreed with coordinate", "confirmed"' in renderer
    assert '"Ball undefined / not visible", "undefined"' in renderer
    assert '"Custom coordinate confirmed"' in renderer
    assert '"Needs more checking", "checking"' in renderer
    assert 'review.textContent = rerunResult;' in renderer
    assert "review, decision);" in renderer
    assert '" · click a frame number to review"' in renderer
    assert 'review.textContent = "Review finalized"' in renderer
    assert 'review.textContent = "Inspect only"' in renderer
    assert '"Review in Round " + batch.number' in renderer
    assert '"Not in Round " + batch.number' in renderer
    assert 'flag.addEventListener("click", () => showBallFrame(index));' not in renderer
    assert "flaggedBallFrames.delete(point.frame)" not in renderer
    assert 'filter.value === "flagged" && latestReviewSelected' in renderer
    assert '"Inspection only · red ring: engine · blue rings: YOLO"' in renderer
    assert '&& selectedBatch?.status === "ready";' in renderer
    assert 'selectedCoordinateBatchId === "all";' in renderer
    assert '"Your previous decision: "' in renderer
    assert '"Result: " + resolution[0]' in renderer
    assert '"Returned from Round " + carryForward.sourceRound' in renderer
    assert 'gateInfoButton.className = "coordinate-gate-info-button";' in renderer
    assert 'gateDetail.setAttribute("popover", "auto");' in renderer
    assert 'gateInfoButton.setAttribute("popovertarget", gateDetailId);' in renderer
    assert "Open this frame to view the saved YOLO candidates as blue rings." in renderer
    assert '"Read-only BAC coordinate. Saved YOLO candidates remain "' in renderer
    assert '"Show coordinate gate details for frame " + point.frame' in renderer
    assert '"Previous-round reason: " + carryForward.reason' in renderer
    assert '"4. Competing-path margin"' in renderer
    assert "function coordinateCarryForward(batch, frames)" in extension
    assert "The reported visible ball, including possible aerial motion" in extension
    assert "carryForward: coordinateCarryForward(batch, nextFrames)" in extension
    assert 'name: "reject_ball_coordinate_review"' in extension
    assert '"disputed_direct"' in extension
    assert "createdFromRejectedReview: completed.id" in extension
    assert 'fixed: ["Resolved by rerun", "confirmed"]' in renderer
    assert 'unresolved: ["Still unresolved", "checking"]' in renderer
    assert '"Previous: " + previousDecision + " · " + rerunResult' not in renderer
    assert "selectedCoordinateBatchId = candidate.id;\n          loadBallFrameFlags();" in renderer
    assert 'id="coordinate-round-result"' in renderer
    assert '"Processing Round " + batch.number' in renderer
    assert '"Independent output review rejected"' in renderer
    assert '" visually supported fixes, "' in renderer
    assert '" disputed direct results · "' in renderer
    assert '"%) was not validated as coordinate-correct."' in renderer
    assert '"Round " + batch.number + " ready for your decisions"' in renderer
    assert 'status: "Ready"' in renderer
    assert 'notification.status || "In progress"' in renderer
    assert "approvedCount === flaggedBallFrames.size" in renderer
    assert '"Complete all decisions before sending ("' in renderer
    assert '|| !reviewComplete' in renderer
    assert 'const chip = document.createElement("span");' in renderer
    assert 'chip.className = "coordinate-review-result " + presentation[1];' in renderer
    assert 'button.className = "ball-frame-open";' not in renderer
    assert '"Copilot is reviewing the frozen evidence"' in renderer
    assert '"Copilot is implementing a general code fix"' in renderer
    assert '"Copilot is running focused and protected tests"' in renderer
    assert '"Rebuilding ball coordinates"' in renderer
    assert '"Rebuilding from runtime detections without using review labels."' in renderer
    assert '"rerun_started"' in renderer[
        renderer.index("function coordinateBatchLocked"):
        renderer.index("function coordinateBatchStatusLabel")
    ]
    assert 'lastCoordinateBatchStatus === "rerun_started"' in renderer
    assert 'frameReview.scrollIntoView({behavior: "smooth", block: "start"});' in renderer
    assert '"The 90% minimum is reached. Choose Continue to event "' in renderer
    assert 'id="improve-coordinate-coverage"' in renderer
    assert 'fetch("/api/continue-coordinate-review"' in renderer
    assert 'url.pathname === "/api/continue-coordinate-review"' in extension
    assert "continuedAfterGate: true" in extension
    assert "flaggedFrames: [...flaggedBallFrames].sort" in renderer
    assert '" flagged ball frame"' in renderer
    assert "User-flagged ball-coordinate source frames for this batch review" in extension
    assert "manual review selections, not inference evidence" in extension
    assert "function visibleBallStates()" in renderer
    assert "state.segment.ballTrackAvailable && !segmentRunActive()" in renderer
    assert 'activeCoordinateBatch?.status === "ready"' in renderer
    assert '? "flagged"' in renderer
    assert 'state.segment.state === "failed" ? "estimated" : "all"' in renderer
    assert "function showBallFrame(index)" in renderer
    assert "modalVideo.src = state.segment.videoUrl;" in renderer
    assert 'marker.setAttribute("cx", String(displayedPoint.x));' in renderer
    assert "point.direct ? \"Direct\" : \"Estimated\"" in renderer
    assert 'id="reset-ball-frame-zoom"' in renderer
    assert 'ballFrameMedia.addEventListener("click", event =>' in renderer
    assert '"--zoom-x"' in renderer
    assert '"--zoom-y"' in renderer
    assert "transform: scale(2.5)" in renderer
    assert 'showRawBallFrame(selectedRawBallFrame, true)' in renderer
    assert 'getComputedStyle(ballFrameMedia)' in renderer
    assert "(pointerX - originX) / zoomScale" in renderer
    assert 'ballFrameMedia.addEventListener("pointerdown", event =>' in renderer
    assert 'ballFrameMedia.addEventListener("pointermove", event =>' in renderer
    assert "if (ballFrameDidDrag)" in renderer
    assert 'event.target.closest("button")' in renderer
    assert 'class="raw-frame-nav previous"' in renderer
    assert 'class="raw-frame-nav next"' in renderer
    assert 'class="ball-review-navigation"' in renderer
    assert 'class="review-target-badge"' in renderer
    assert '? "Inspect frame "' in renderer
    assert ': "Review frame "' in renderer
    assert '"Viewing raw frame " + selectedRawBallFrame' in renderer
    assert 'class="ball-frame-modal-status"' in renderer
    assert "Coordinate review active" in renderer
    assert '"Decision already recorded for review frame "' in renderer
    assert '"Decision saved for review frame "' in renderer
    assert '" is in coordinate review and awaiting a decision."' in renderer
    assert "lastBallCoordinateDecision = {" in renderer
    assert "showRawBallFrame(reviewedFrame, true);" in renderer
    assert ".ball-frame-modal-marker.engine-coordinate" in renderer
    assert "fill-opacity: 0;" in renderer
    assert "stroke-width: 2;" in renderer
    assert "candidate.x - displayedPoint.x" in renderer
    assert "candidate.y - displayedPoint.y" in renderer
    assert ") <= 4" in renderer
    assert 'id="ball-frame-overlay-controls"' in renderer
    assert 'id="show-engine-ball-marker"' in renderer
    assert 'id="show-yolo-ball-markers"' in renderer
    assert "Engine ring (red)" in renderer
    assert "YOLO candidates (blue)" in renderer
    assert "marker.hidden = !hasDisplayedCoordinate || !showEngineBallMarker" in renderer
    assert "showYoloBallMarkers" in renderer
    assert "Coordinate review · red ring: engine · blue rings: YOLO" in renderer
    assert 'id="ball-frame-pointer"' in renderer
    assert 'id="ball-frame-pointer-label"' in renderer
    assert 'id="ball-frame-current-decision"' in renderer
    assert '"Your previous decision: "' in renderer
    assert '"Current decision: ") + currentDecisionLabel' in renderer
    assert '"✓ Agreed with coordinate"' in renderer
    assert '"Needs more checking"' in renderer
    assert '"Ball undefined / not visible"' in renderer
    assert '"✓ Custom coordinate confirmed"' in renderer
    assert '"Custom coordinate awaiting confirmation"' in renderer
    assert "const originalBallCoordinateAtPointer = event => {" in renderer
    assert "const coordinate = originalBallCoordinateAtPointer(event);" in renderer
    assert renderer.count("const coordinate = originalBallCoordinateAtPointer(event);") == 2
    assert '"x " + Math.round(coordinate.x)' in renderer
    assert "const sourceWidth = Number(ballTrack?.width || 4450);" in renderer
    assert "const sourceHeight = Number(ballTrack?.height || 2000);" in renderer
    assert 'url.pathname === "/api/trajectory-audit-draft"' in extension
    assert "async function readBody(request, maximumBytes = 16_384)" in extension
    assert "const body = await readBody(request, 131_072);" in extension
    assert extension.index(
        'url.pathname === "/api/trajectory-audit-draft"'
    ) > extension.index(
        'url.pathname === "/api/coordinate-batch-draft"'
    )
    assert extension.index(
        'url.pathname === "/api/trajectory-audit-draft"'
    ) < extension.index(
        'url.pathname === "/api/message"'
    )
    assert "trajectoryAudit: state.trajectoryAudit || {" in extension
    assert 'fetch("/api/trajectory-audit-draft"' not in renderer
    assert (
        'document.getElementById("ball-frame-filter").value = "estimated";'
        not in renderer
    )
    assert "point.frame > reviewedFrame" not in renderer
    assert '"you are ready to move on."' in renderer
    assert 'title="Previous raw frame (−1)"' in renderer
    assert 'title="Next raw frame (+1)"' in renderer
    assert 'aria-label="Agree with current coordinate"' in renderer
    assert 'aria-label="Ball undefined or not visible"' in renderer
    assert 'aria-label="Undo coordinate decision"' in renderer
    assert 'id="ball-coordinate-review-modal"' in renderer
    assert 'aria-controls="ball-coordinate-review-modal"' in renderer
    assert "function sendBallCoordinateReview(mode)" in renderer
    assert 'id="ball-coordinate-review-messages"' not in renderer
    assert 'id="ball-coordinate-review-message"' not in renderer
    assert "Bounded coordinate review started. Progress is shown above." in renderer
    assert '"Open batch review (" +' in renderer
    assert '"Send reviewed batch once to Copilot ("' in renderer
    assert 'document.getElementById("ball-coordinate-review-modal").showModal()' in renderer
    assert '? "Query mode · review finalized"' in renderer
    assert 'review.textContent = "Review finalized"' in renderer
    assert "ballCoordinateReviewRequired(selected)" in extension
    assert 'url.pathname === "/api/finalize-ball-coordinate-review"' in extension
    assert 'name: "confirm_ball_coordinate_review"' in extension
    assert '"finishes. Never put the segment into review; only the user can "' in extension
    assert '"finalize that transition."' in extension
    assert "const mainReviewActive = Boolean(" in renderer
    assert "mainReviewActive\n        && hasDraft" in renderer
    assert "No review events exist to publish" in extension
    assert (
        "Ball-coordinate review must be explicitly finalized before publication"
        in extension
    )


def test_live_ball_frame_inspector_stays_above_video() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    inspector = renderer.index('id="ball-frame-review"')
    video = renderer.index('id="video-shell"')
    assert inspector < video
    assert '" flagged · showing " + visible.length' in renderer
    assert "ballTrack = null" in renderer


def test_live_theme_reserves_green_for_success_states() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "--background-color-default: ${palette.backgroundDefault}" in renderer
    assert "--background-color-subtle: ${palette.backgroundSubtle}" in renderer
    assert "--panel-border: ${palette.panelBorder}" in renderer
    assert 'backgroundDefault: "#080d14"' in renderer
    assert 'backgroundSubtle: "#101923"' in renderer
    assert 'panelBorder: "#315f86"' in renderer
    assert "rgb(120 191 255 / 14%)" in renderer
    assert ".segment-status.passed {" in renderer
    assert "background: rgb(46 160 67 / 16%)" in renderer


def test_live_canvas_has_direct_ball_frame_navigation() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'id="show-ball-frames"' in renderer
    assert 'aria-controls="ball-coordinate-review-modal"' in renderer
    assert 'document.getElementById("ball-coordinate-review-modal").showModal()' in renderer
    assert 'id="target-ball-frame"' in renderer
    assert 'id="zoom-ball-frame"' in renderer
    assert "Zoom to target" in renderer
    assert "Go to target coordinate" in renderer
    assert 'id="ball-frame-modal-marker" r="7"></circle>' in renderer
    assert "fill: rgb(126 231 135 / 20%)" in renderer
    assert 'id="previous-ball-review-frame"' in renderer
    assert 'id="next-ball-review-frame"' in renderer
    assert 'id="mark-ball-location"' in renderer
    assert 'id="approve-ball-location"' in renderer
    assert 'id="agree-ball-coordinate"' in renderer
    assert 'id="undefined-ball-coordinate"' in renderer
    assert 'id="undo-ball-coordinate-decision"' in renderer
    assert "function showRawBallFrame(frame, preserveZoom = false)" in renderer
    assert "showRawBallFrame(selectedRawBallFrame - 1, true);" in renderer
    assert "showRawBallFrame(selectedRawBallFrame + 1, true);" in renderer
    assert 'preload="auto" aria-label="Enlarged selected frame"' in renderer
    assert "if (!rawBallFrameSeekPending)" in renderer
    assert '"Loading exact raw frame " + selectedRawBallFrame' in renderer
    assert 'media.setAttribute("aria-busy", "true")' in renderer
    assert "requestAnimationFrame(finishSeek);" in renderer
    assert "seekTimeout = setTimeout(finishSeek, 3000);" in renderer
    assert "modalVideo.requestVideoFrameCallback(finishSeek)" not in renderer
    assert "function showAdjacentBallReviewFrame(offset)" in renderer
    assert "() => showAdjacentBallReviewFrame(-1)" in renderer
    assert "() => showAdjacentBallReviewFrame(1)" in renderer
    assert 'const preserveZoom = media.classList.contains("zoomed");' in renderer
    assert "showRawBallFrame(selectedBallTargetFrame, preserveZoom);" in renderer
    assert "(nextPoint.x / ballTrack.width * 100)" in renderer
    assert "(nextPoint.y / ballTrack.height * 100)" in renderer
    assert "initializeBallFrameControls();" in renderer
    assert renderer.count(
        'document.getElementById("previous-ball-frame").addEventListener('
    ) == 1
    assert "coordinateObservations: flaggedFrames" in renderer
    assert "function recordBallCoordinateDecision(observation, description)" in renderer
    assert '{decision: "agree", x: point.x, y: point.y}' in renderer
    assert '{decision: "undefined"}' in renderer
    assert "delete ballCoordinateObservations[String(frame)]" in renderer
    assert "diagnostic leads only" in LIVE_EXTENSION.read_text(
        encoding="utf-8"
    )
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")
    assert '"agree",' in extension
    assert '"undefined",' in extension
    assert '"specified",' in extension
    assert '"needs_more_checking",' in extension
    assert '["undefined", "needs_more_checking"].includes(' in extension
    assert "ball undefined / not visible" in extension


def test_live_fullscreen_scrolls_to_selected_copilot_event() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "function scrollSelectedComparisonIntoView()" in renderer
    assert "'[data-event-source=\"review\"][data-event-index=\"'" in renderer
    assert 'selected?.closest(".comparison-row")?.scrollIntoView({' in renderer
    assert "requestAnimationFrame(scrollSelectedComparisonIntoView);" in renderer


def test_live_comparison_keeps_unmatched_engine_events_and_coalesces_refreshes() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "if (!usedEngine.has(engineIndex))" in renderer
    assert "requestEngineEventVerification(" in renderer
    assert "selectedEngineIndex = row.engineIndex;" in renderer
    assert '"[name=engine-user-verdict]"' in renderer
    assert "let stateRefreshQueued = false;" in renderer
    assert "stateRefreshQueued = true;" in renderer
    assert "} while (stateRefreshQueued);" in renderer


def test_innovation_engine_search_opens_guided_preflight_without_copilot() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")
    extension = EXTENSION.read_text(encoding="utf-8")
    architecture = (
        Path(__file__).parents[1] / "docs" / "RULES_ENGINE_ARCHITECTURE.md"
    ).read_text(encoding="utf-8")

    assert 'id="engine-verification-modal"' in renderer
    assert "Opening or closing" in renderer
    assert "this window does not start Copilot" in renderer
    assert "This guide applies only to the selected E#" in renderer
    assert "Correct — exact event is supported" in renderer
    assert "Event exists, but details are wrong" in renderer
    assert "Incorrect — no such event occurred" in renderer
    assert "Cannot verify from this camera" in renderer
    assert renderer.count('"#cancel-engine-verification"') >= 2
    assert '"[name=engine-verification-decision]"' in renderer
    assert 'id="confirm-engine-without-copilot"' in renderer
    assert 'id="ask-copilot-engine-review"' in renderer
    assert 'id="cancel-engine-verification"' in renderer
    assert 'id="engine-check-seconds"' in renderer
    assert 'id="seek-engine-check-time"' in renderer
    assert "Another completion time to inspect (seconds)" in renderer
    assert "function engineVerificationCheckTime()" in renderer
    assert "function seekEngineVerificationTime()" in renderer
    assert "without changing M#" in renderer
    assert "seekVideo(seconds);" in renderer
    assert "openEngineVerificationModal(row.engineIndex)" in renderer
    assert (
        renderer.index("openEngineVerificationModal(row.engineIndex)")
        < renderer.index("async function requestEngineEventVerification(")
    )
    assert 'fetch("/api/reviewer-confirm-engine"' in renderer
    assert 'userVerdict: "correct"' in renderer
    assert 'fetch("/api/copilot-verify-engine"' in renderer
    assert 'url.pathname === "/api/reviewer-confirm-engine"' in extension
    assert 'body.userVerdict !== "correct"' in extension
    assert 'reviewSource: "professional_reviewer"' in extension
    assert "Copilot escalation is a separate explicit action" in architecture
    assert "Cancel or close leaves the event" in architecture
    assert "The compact comparison table has permanent Manual `M#` and Engine `E#`" in architecture
    assert "`C#` proposals are optional, read-only Copilot diagnostic history" in architecture
    assert "Show Copilot C# reference" in renderer
    assert "Copilot C# reference · diagnostic only" in renderer
    assert 'item.className = "copilot-reference-event"' in renderer
    assert 'item.title = event.key + " · frame "' in renderer
    assert 'item.dataset.eventSource = "copilot-reference"' in renderer
    assert "selectedCopilotReferenceIndex = index;" in renderer
    assert "button.scrollIntoView({block: \"nearest\"});" in renderer
    assert "Reject E# & fix engine" in renderer
    assert "replace the old E# list" in renderer
    assert "Protected regressions run only after a rules-engine change" in architecture
    assert "No Copilot review, engine check, engine change, or" in renderer


def test_live_comparison_uses_panel_equivalent_status_and_action_labels() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert '"✓ Accepted"' in renderer
    assert '"Accepted reference"' in renderer
    assert '"✕ Rejected"' in renderer
    assert '"Rejected and excluded from the reference"' in renderer
    assert 'accept.append(comparisonActionIcon("accept"))' in renderer
    assert 'reject.append(comparisonActionIcon("reject"))' in renderer
    assert 'confirm.append(comparisonActionIcon("verify"))' in renderer
    assert 'confirm.setAttribute("aria-label", confirmLabel)' in renderer
    assert "confirm.title = confirmLabel" in renderer
    assert '"Verify stale E"' in renderer
    assert '"C↔E agreement"' in renderer
    assert '"C↔E conflict"' in renderer
    assert '"decision-" + row.review.decision.status' in renderer


def test_live_extension_records_review_work_in_canvas_conversations() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert "`Decision: Event ${index + 1} at ${event.seconds.toFixed(3)}s was `" in extension
    assert "`E${index + 1} independently confirmed at `" in extension
    assert '"Current rules-engine source and cached event output were "' in extension
    assert "`Protected regressions ${context.input.passed ? \"passed\" : \"failed\"}: `" in extension
    assert "`Validated reference published with ${reference.events.length} `" in extension
    assert "eventIndex: index" in extension
    assert "eventIndex: null" in extension


def test_live_extension_can_publish_progress_without_completing_review() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert 'name: "publish_review_progress"' in extension
    assert '"Publish an in-progress Copilot update into the Canvas conversation without completing the review."' in extension
    assert "engineIndex," in extension
    assert "completed: false," in extension


def test_final_general_review_response_clears_engine_authorization_after_reload() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert "const key = engineEventReviewKey(engineEvent);" in extension
    assert "delete review.state.engineEventReviewAuthorizations[key];" in extension
    assert "reviewRequestPending = false;" in extension


def test_live_extension_routes_engine_event_conversations_separately() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert 'url.pathname === "/api/engine-message"' in extension
    assert "engineEventConversationPrompt(review.selected, event, index, text)" in extension
    assert "engineIndex: index" in extension
    assert "`with engineIndex ${index} and without a C# eventIndex" in extension
    assert 'engineIndex: { type: "integer", minimum: 0 }' in extension


def test_live_extension_can_cancel_wrong_event_adjustment() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert 'name: "cancel_review_adjustment"' in extension
    assert 'review.state.decisions[String(index)]?.status !== "adjust"' in extension
    assert "delete review.state.decisions[String(index)];" in extension
    assert "cancelled: true, proposalChanged: false" in extension
    assert 'url.pathname === "/api/cancel-adjustment"' in extension
    assert '"review_adjustment_not_authorized"' in extension


def test_live_panels_can_stop_pending_adjustment_review() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'id="cancel-adjustment"' in renderer
    assert 'id="fullscreen-cancel-adjustment"' in renderer
    assert "async function cancelAdjustment()" in renderer
    assert 'fetch("/api/cancel-adjustment"' in renderer
    assert 'fullscreenDecision !== "adjust"' in renderer


def test_live_review_starts_ready_segments_at_zero() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "function resetReviewPlayback()" in renderer
    assert "pendingReviewSeconds = 0;" in renderer
    assert 'document.getElementById("time").textContent = "0.00s";' in renderer
    assert "previousSegmentKey !== state.segment.key" in renderer
    assert '(!previousSegmentReady && state.segment.state === "ready")' in renderer
    assert 'selectEvent(0, {seek: false, pause: false});' in renderer


def test_live_fullscreen_includes_selected_event_conversation() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'id="fullscreen-messages"' in renderer
    assert 'id="fullscreen-message"' in renderer
    assert 'id="fullscreen-send-message"' in renderer
    assert 'id="fullscreen-adjust"' in renderer
    assert '"Copilot conversation for " + selectedReference' in renderer
    assert 'renderConversationMessages(\n        "fullscreen-messages"' in renderer
    assert '"fullscreen-message",\n            "fullscreen-chat-status"' in renderer
    assert 'textareaId: "fullscreen-message"' in renderer


def test_live_fullscreen_routes_unmatched_engine_conversation() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "let selectedEngineIndex = null;" in renderer
    assert "selectedEngineIndex = eventNumber - 1;" in renderer
    assert '"Copilot conversation for E" + (selectedEngineIndex + 1)' in renderer
    assert "async function submitEngineConversationMessage()" in renderer
    assert 'fetch("/api/engine-message"' in renderer
    assert "message.engineIndex === selectedEngineIndex" in renderer
    assert 'id="clip-conversation-panel"' not in renderer


def test_live_review_controls_follow_c_and_e_workflow_state() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert 'id="fullscreen-primary-action"' in renderer
    assert 'id="fullscreen-workflow-note"' in renderer
    assert 'id="clip-conversation-note"' not in renderer
    assert 'id="accepted-engine-recheck"' in renderer
    assert '"Re-verify E" + (selectedEngineIndex + 1)' in renderer
    assert '"Verify stale E" + (selectedEngineIndex + 1)' in renderer
    assert '"Verify E" + (selectedEngineIndex + 1)' in renderer
    assert '"Verify " + selectedReference + ", Accept & Confirm ↔E"' in renderer
    assert '"Verify " + selectedReference + ", Accept & Sync Engine"' in renderer
    assert '"Request " + selectedReference + " Adjustment"' in renderer
    assert 'selectedEngine.review?.status === "confirmed"' in renderer
    assert "selectedEngine.review.fresh" in renderer
    assert "draft?.comparison?.status !== \"already_agrees\"" in renderer
    assert "independentEngineReview" in renderer
    assert 'row.review.decision?.status === "rejected"' in renderer
    assert 'fetch("/api/copilot-recheck-accepted"' in renderer
    assert 'url.pathname === "/api/copilot-recheck-accepted"' in extension
    assert "function acceptedEngineRecheckPrompt(" in extension
    assert "Only an already accepted C# can use this engine re-check" in extension
    assert "no recalculation is needed" in extension


def test_engine_reverification_includes_and_clears_typed_focus() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert 'textareaId = null' in renderer
    assert 'textarea?.value.trim() || "",' in renderer
    assert 'reviewChoice?.note || ""' in renderer
    assert '].filter(Boolean).join(" ");' in renderer
    assert 'note: reviewFocus' in renderer
    assert 'if (textarea) textarea.value = "";' in renderer
    assert '"clip-message"' in renderer
    assert '"fullscreen-message"' in renderer
    assert 'const reviewFocus = String(body.note || "").trim();' in extension
    assert "User-specified verification focus:" in extension
    assert "Verification focus: ${reviewFocus}" in extension
    assert "reviewFocus.slice(0, 180)" in extension
    assert "Verification focus must be at most 4,000 characters" in extension


def test_unconfirmed_engine_event_remains_visible_and_reviewable() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert "async function recordEngineEventNotConfirmed(" in extension
    assert 'status: "not_confirmed"' in extension
    assert "`E${index + 1} was not confirmed at `" in extension
    assert "record_engine_event_not_confirmed" in extension
    assert 'unsupported.textContent = "✕ Not confirmed"' in renderer
    assert '"The exact engine event is unsupported"' in renderer
    assert '"Not confirmed · unsupported"' in renderer
    assert '"Re-verify unsupported E"' in renderer
    assert "It remains visible as engine output" in renderer


def test_live_canvas_has_low_credit_developer_mode() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")
    architecture = (
        Path(__file__).parents[1] / "docs" / "RULES_ENGINE_ARCHITECTURE.md"
    ).read_text(encoding="utf-8")

    assert 'id="review-audience"' in renderer
    assert '<option value="developer">Developer</option>' in renderer
    assert renderer.count('data-developer-panel hidden') == 2
    assert "function developerGuidance()" in renderer
    assert "deferred possession recovery and _nearby_ball_team_track()" in renderer
    assert 'path("scripts", reviewWorkflow.processorScript)' in renderer
    assert 'processorScript: "process-alfheim-segment.py"' in renderer
    assert (
        'processorArguments: ["--artifact-namespace", "live", "--events-only"]'
        in renderer
    )
    assert "function copyDeveloperCommand(name, statusNode)" in renderer
    assert "function refreshDeveloperOutput(statusNode)" in renderer
    assert "Copying commands and refreshing output do not invoke review AI." in renderer
    assert "canCopilotImplement:" in renderer
    assert "draft?.decision?.status === \"accepted\"" in renderer
    assert "requestAcceptedEngineRecheck(selectedIndex)" in renderer
    assert "E# output cannot authorize an engine change" in renderer
    assert "Developer-mode review contract" in architecture
    assert "normal or expanded event-review controls" in architecture


def test_live_rendered_browser_script_has_valid_syntax() -> None:
    script = """
import(process.argv[1]).then(({ renderHtml }) => {
  const html = renderHtml();
  const scripts = [...html.matchAll(/<script(?:[^>]*)>([\\s\\S]*?)<\\/script>/g)];
  if (!scripts.length) throw new Error("No browser script found");
  new Function(scripts.at(-1)[1]);
});
"""

    subprocess.run(
        ["node", "-e", script, LIVE_RENDERER.as_uri()],
        check=True,
        capture_output=True,
        text=True,
    )


def test_live_playback_pings_copilot_and_engine_events_independently() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'id="copilot-event-trigger"' in renderer
    assert 'id="engine-event-trigger"' in renderer
    assert ".event-trigger.copilot" in renderer
    assert "@keyframes copilot-event-ping" in renderer
    assert ".comparison-event.review.reached" in renderer
    assert ".comparison-event.engine.reached" in renderer
    assert 'showEventTrigger("copilot", event.index)' in renderer
    assert 'showEventTrigger("engine", event.index)' in renderer
    assert "const copilotTimeline = reviewWorkflow.key === \"innovation\"" in renderer
    assert "? state?.copilotEvents" in renderer
    assert ": state?.drafts;" in renderer
    assert "const crossedManual = reviewWorkflow.key === \"innovation\"" in renderer
    assert "pulseManualEvent(event.index);" in renderer
    assert 'button.closest(".comparison-row")?.scrollIntoView({' in renderer
    assert "const crossedEngine = state?.engineEvents" in renderer


def test_live_playback_rewinds_event_progress_with_the_playhead() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "function clearEventTriggers()" in renderer
    assert 'document.querySelectorAll(".comparison-event.playback-ping")' in renderer
    assert 'video.addEventListener("seeked", () =>' in renderer
    assert "previousPlaybackSeconds = seconds;" in renderer
    assert renderer.count("updateFullscreenEventProgress(seconds);") >= 3


def test_live_matched_events_are_not_highlighted_before_playback_reaches_them() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert ".comparison-row.matched { background: transparent; }" in renderer
    assert ".comparison-event.current {" in renderer
    assert "background: rgb(110 118 129 / 14%);" in renderer
    assert ".comparison-event.review.reached {" in renderer
    assert ".comparison-event.engine.reached {" in renderer


def test_finalized_event_is_locked_and_only_adjustment_remains() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert ".proposal.accepted" in renderer
    assert ".proposal.rejected" in renderer
    assert 'classList.toggle("accepted", accepted)' in renderer
    assert 'classList.toggle("rejected", rejected)' in renderer
    assert 'getElementById("accept").hidden = finalized' in renderer
    assert 'getElementById("copilot-accept").hidden = finalized' in renderer
    assert 'getElementById("reject").hidden = finalized' in renderer
    assert 'getElementById("adjust").hidden' not in renderer
    assert "sendMessage.disabled = finalized || reviewBusy" in renderer
    assert "Accepted event locked. Enter a correction above" in renderer
    assert "Rejected event locked. Only Request Adjustment can reopen it." in renderer
    assert '"Accepted · adjustment only"' in renderer
    assert '"Rejected · adjustment only"' in renderer
    assert "This event is accepted; use Request Adjustment to reopen it" in (
        EXTENSION.read_text(encoding="utf-8")
    )


def test_canvas_hides_internal_context_and_reports_review_status() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert "let reviewRequestPending = false;" in extension
    assert "displayPrompt:" in extension
    assert "`this clip at ${seconds.toFixed(3)}s`" in extension
    assert '"the entire clip"' in extension
    assert "!reviewRequestPending" in extension
    assert 'session.on("tool.execution_start", (event) => {\n  if (!reviewRequestPending) return;' in extension
    assert 'session.on("session.error", (event) => {\n  if (!reviewRequestPending) return;' in extension
    assert '"Copilot result ready"' in extension
    assert "Open Copilot Chat to read the result" in extension
    assert 'name: "publish_review_response"' in extension
    assert "Before ending, always use the football-event-review" in extension
    assert 'role: "assistant"' in extension
    assert 'session.on("assistant.message"' not in extension
    assert 'id="chat-status"' in renderer
    assert 'current.label + "…"' in renderer


def test_copilot_reviews_are_recorded_without_acceptance_handover() -> None:
    for path in (EXTENSION, LIVE_EXTENSION):
        extension = path.read_text(encoding="utf-8")

        assert 'name: "record_copilot_proposal"' in extension
        assert 'name: "replace_copilot_review"' in extension
        assert 'source: "copilot_review"' in extension
        assert '"Copilot proposal ready"' in extension
        assert '"Copilot review ready"' in extension
        assert "copilotAcceptanceAuthorizations" not in extension[
            extension.index('name: "record_copilot_proposal"'):
            extension.index('name: "confirm_engine_event_reviewed"')
        ]


def test_first_event_is_shown_after_video_metadata_loads() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert "let pendingReviewSeconds = null;" in renderer
    assert "const target = pendingReviewSeconds ?? position;" in renderer
    assert "seekVideo(currentDraft().seconds);" in renderer
    assert "if (video.readyState >= 1)" in renderer
    assert "video.currentTime = pendingReviewSeconds;" in renderer
