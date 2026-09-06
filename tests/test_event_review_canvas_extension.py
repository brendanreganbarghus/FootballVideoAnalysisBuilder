import subprocess
from pathlib import Path


EXTENSION = (
    Path(__file__).parents[1]
    / ".github"
    / "extensions"
    / "football-event-review"
    / "extension.mjs"
)
RENDERER = EXTENSION.with_name("renderer.mjs")
FRESHNESS = EXTENSION.with_name("engine-freshness.mjs")


def test_canvas_reviews_the_prepared_segment_catalog() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'id: "football-event-review"' in extension
    assert "/api/alfheim/segments" in extension
    assert "segment.validated" in extension
    assert 'validationStatus = segment.validated' in extension
    assert 'id="segment-select"' in renderer
    assert "30–60 second segments" in renderer
    assert "Event 1 of 1" in renderer
    assert "Previous Event" in renderer
    assert "Next Event" in renderer
    assert "Football Event Review" in renderer
    assert "Test 3 Event Review" not in renderer
    assert "Copilot Draft" not in renderer
    assert "Rules Engine" not in renderer


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
    assert "Copilot for Event" in renderer
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
    assert '"ball-ground-truth.csv"' in extension
    assert "calibration.image_width" in extension
    assert "calibration.image_height" in extension
    assert "actionFocus: actionFocuses[index]" in extension
    assert 'id="zoom-action"' in renderer
    assert "Zoom to Action" in renderer
    assert '"Zoom to C" + (selectedIndex + 1) + " Action"' in renderer
    assert "Reset Zoom" in renderer
    assert ".video-shell.action-zoom .video-media" in renderer
    assert "videoMedia.style.transformOrigin = focus" in renderer


def test_canvas_can_switch_between_normal_ball_and_ai_views() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'url.pathname === "/api/ball-track"' in extension
    assert "async function loadBallTrack(segment)" in extension
    assert "selected.trackingUrl = status.tracking_url" in extension
    assert 'data-view-mode="normal"' in renderer
    assert 'data-view-mode="ball"' in renderer
    assert 'data-view-mode="ai"' in renderer
    assert 'id="ball-overlay"' in renderer
    assert "function updateBallMarker()" in renderer
    assert 'ballOverlay.removeAttribute("hidden")' in renderer
    assert 'ballOverlay.setAttribute("hidden", "")' in renderer
    assert "Supplied labelled ball position at this frame" in renderer
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
    assert '"30-shared-baselines", "event-review-state"' in extension
    assert "legacyStatePath(segment)" in extension
    assert "async function updateSharedChecksum(path, content)" in extension
    assert "async function readReviewState(path, fallback, verifyChecksum = false)" in extension
    assert "Shared review-state checksum mismatch" in extension
    assert '"00-governance"' in extension
    assert '"checksums.sha256"' in extension
    assert "Published validated reference" in extension


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

    assert "const minimumReviewDurationSeconds = 30" in extension
    assert "const maximumReviewDurationSeconds = 60" in extension
    assert 'url.pathname === "/api/prepare"' in extension
    assert 'localJson("/api/alfheim/segment"' in extension
    assert "duration_seconds: durationSeconds" in extension
    assert 'id="segment-start-minute"' in renderer
    assert 'id="segment-start-second"' in renderer
    assert 'id="segment-duration"' in renderer
    assert 'min="30" max="60"' in renderer
    assert 'fetch("/api/prepare"' in renderer
    assert "minute * 60 + second" in renderer
    assert "duration_seconds: duration" in renderer


def test_canvas_runs_ai_only_after_explicit_action() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'url.pathname === "/api/analyze"' in extension
    assert 'localJson("/api/alfheim/analyze"' in extension
    assert 'id="process-segment"' in renderer
    assert 'fetch("/api/analyze"' in renderer
    assert 'processButton.addEventListener("click"' in renderer
    assert "Events stay hidden until it finishes" in renderer


def test_ai_candidates_appear_only_when_analysis_is_ready() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'if (segmentInfo.state !== "ready") return []' in extension
    assert 'source: "engine_output"' in extension
    assert 'source: "copilot_review"' in extension
    assert "const engineEvents = snapshotEvents(" in extension
    assert "engineEvents," in extension
    assert "Red goalkeeper completed pass to headed receiver" in extension
    assert "header is the receiving action, not a second pass." in extension
    assert 'engineCandidate = draft.source === "engine_output"' in renderer
    assert '"AI engine detected"' in renderer
    assert "Event candidates remain hidden until the run completes." in renderer
    assert "AI completed and produced no event candidates." in renderer


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
    assert 'source: "adjusted_proposal"' in extension
    assert "delete review.state.decisions[String(index)]" in extension
    assert '"Revised proposal ready"' in extension
    assert "unless that action succeeds." in extension
    assert "async function requestAdjustment()" in renderer
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
    assert "never detection or tracking" in extension
    assert "timestamp-, frame-, clip-, or segment-specific exception" in extension
    assert "engine_fix_not_verified" in extension
    assert "engine_implementation_unchanged" in extension
    assert 'afterComparison.status !== "already_agrees"' in extension
    assert "record_regression_result" in extension
    assert 'id="copilot-accept"' in renderer
    assert "Verify, Accept &amp; Sync Engine (Autopilot)" in renderer
    assert "Ask Copilot (Plan mode)" in renderer
    assert 'async function sendReviewMessage(text, mode = "plan")' in renderer
    assert "rules engine needs a general fix" in renderer
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
    assert 'source: "user_reported"' in extension
    assert 'id="send-clip-plan"' in renderer
    assert 'id="send-clip-autopilot"' in renderer
    assert 'id="missing-team"' not in renderer
    assert 'id="missing-type"' not in renderer
    assert 'id="clip-message"' in renderer
    assert "genuinely missing event" in extension
    assert "determine its team and event type" in extension
    assert "Ask Copilot about this clip" in renderer
    assert 'id="clip-message-scope"' in renderer
    assert '<option value="entire_clip" selected>Entire clip</option>' in renderer
    assert '<option value="current_time">Current time ±2s</option>' in renderer
    assert '<span class="clip-message-target">entire clip</span> (Plan mode)' in renderer
    assert '<span class="clip-message-target">entire clip</span> (Autopilot)' in renderer
    assert "function updateClipMessageTargets()" in renderer
    assert renderer.index("function updateClipMessageTargets()") < renderer.index(
        "async function confirmMissingEvent()"
    )
    assert "General clip messages stay separate" in renderer
    assert 'id="clip-messages"' in renderer
    assert "message => message.eventIndex === null" in renderer
    assert "message => message.eventIndex === selectedIndex" in renderer
    assert 'id="missing-event-plan"' in renderer
    assert 'id="confirm-missing-event"' in renderer
    assert "Add as Review Event (Autopilot)" in renderer
    assert 'fetch("/api/clip-message"' in renderer
    assert 'mode === "autopilot" ? "autopilot" : "plan"' in extension
    assert 'body.scope === "current_time"' in extension
    assert "Evidence scope: the entire prepared clip." in extension
    assert "local ±2-second window" in extension
    assert "A supported missing event still requires the " in extension
    assert 'fetch("/api/confirm-missing-event"' in renderer
    assert "User-reported candidate" in renderer
    assert "Review it, then accept or reject it." in renderer


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
    assert "<strong>Red C-only</strong>: verify C# to trigger" in renderer
    assert "<strong>Red E-only</strong>: ask the clip conversation first." in renderer


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
    assert 'id="clip-conversation-panel"' in renderer
    assert 'id="conversation-panel"' in renderer
    assert "segmentBuilderPanel.open =" in renderer
    assert "Copilot for Event 1" in renderer


def test_copilot_chat_is_embedded_and_scoped_to_the_selected_event() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'class="conversation" id="conversation-panel"' in renderer
    assert "This conversation contains only messages for the selected event." in renderer
    assert "message => message.eventIndex === selectedIndex" in renderer
    assert '"Copilot for Event " + (selectedIndex + 1)' in renderer
    assert 'id="chat-status"' in renderer
    assert 'data-state="ready"' in renderer
    assert 'setChatMode("normal")' not in renderer
    assert 'id="chat-drag-handle"' not in renderer


def test_playback_surfaces_and_selects_each_triggered_event() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'id="event-trigger"' in renderer
    assert 'id="event-trigger-label"' in renderer
    assert "left: 14px;" in renderer
    assert "background: rgb(13 17 23 / 72%);" in renderer
    assert "function playbackEventLabel(draft)" in renderer
    assert "function eventSourceLabel(draft)" in renderer
    assert '"Copilot-reviewed correction"' in renderer
    assert '"Copilot-prepared review"' in renderer
    assert "Proposal origin only; engine agreement is checked after acceptance." in renderer
    assert '"User-reported candidate"' in renderer
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
    assert "function comparisonReviewCell(row)" in renderer
    assert '"Verify & Accept C" + (row.reviewIndex + 1)' in renderer
    assert "await requestCopilotAcceptance(row.reviewIndex)" in renderer
    assert '"Reject C" + (row.reviewIndex + 1)' in renderer
    assert 'await decide("rejected", row.reviewIndex)' in renderer
    assert 'async function decide(status, targetIndex = selectedIndex)' in renderer
    assert 'accepted.textContent = "✓ Accepted"' in renderer
    assert 'rejected.textContent = "✕ Rejected"' in renderer
    assert 'item.classList.add("decision-rejected")' in renderer
    assert "const finalized = accepted || rejected;" in renderer
    assert "candidate => !candidate.decision" in renderer
    assert ".comparison-row.decision-rejected" in renderer
    assert '.filter((index) => !context.state.decisions[String(index)])' in extension
    assert "function comparisonEngineCell(row)" in renderer
    assert '"✓ Confirmed reviewed"' in renderer
    assert '"Verify E" + (row.engineIndex + 1) + " (Autopilot)"' in renderer
    assert "function requestEngineEventVerification(engineIndex)" in renderer
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
    assert '"Copilot is verifying C" + (selectedIndex + 1) + "…"' in renderer
    assert 'progress.textContent = "Verifying C" + (row.reviewIndex + 1) + "…"' in renderer
    assert 'cell.classList.add("verifying")' in renderer
    assert '"E" + (engineIndex + 1)' in renderer
    assert '" ↔ C" + (reviewIndex + 1)' in renderer
    assert ">Copilot proposal</span>" in renderer
    assert ">Rules engine output</span>" in renderer
    assert 'id="compact-engine-rail"' in renderer
    assert "state?.engineEvents || []" in renderer


def test_live_video_overlay_counts_triggered_statistics() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'class="live-stats-overlay"' in renderer
    assert 'id="live-stats-time"' in renderer
    assert 'id="live-red-passes"' in renderer
    assert 'id="live-black-turnovers"' in renderer
    assert "background: rgb(13 17 23 / 68%);" in renderer
    assert "function updateLiveStatistics(seconds)" in renderer
    assert "event.seconds <= seconds + 0.001" in renderer
    assert 'event.decision?.status === "rejected"' in renderer
    assert "updateLiveStatistics(seconds);" in renderer


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


def test_first_event_is_shown_after_video_metadata_loads() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert "let pendingReviewSeconds = null;" in renderer
    assert "const target = pendingReviewSeconds ?? position;" in renderer
    assert "seekVideo(currentDraft().seconds);" in renderer
    assert "if (video.readyState >= 1)" in renderer
    assert "video.currentTime = pendingReviewSeconds;" in renderer
