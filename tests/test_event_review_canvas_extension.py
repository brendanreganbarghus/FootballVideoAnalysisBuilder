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
PUBLICATION_GATE = EXTENSION.with_name("publication-gate.mjs")
LIVE_EXTENSION = (
    Path(__file__).parents[1]
    / ".github"
    / "extensions"
    / "football-event-review-live"
    / "extension.mjs"
)
LIVE_RENDERER = LIVE_EXTENSION.with_name("renderer.mjs")
LIVE_PUBLICATION_GATE = LIVE_EXTENSION.with_name("publication-gate.mjs")


def test_canvas_reviews_the_prepared_segment_catalog() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'id: "football-event-review"' in extension
    assert "/api/alfheim/segments" in extension
    assert "segment.validated" in extension
    assert 'validationStatus = segment.validated' in extension
    assert 'id="segment-select"' in renderer
    assert "20–60 second Alfheim segments · BAC assisted" in renderer
    assert "Event 1 of 1" in renderer
    assert "Previous Event" in renderer
    assert "Next Event" in renderer
    assert "Football Event Review" in renderer
    assert "Test 3 Event Review" not in renderer
    assert "Copilot Draft" not in renderer
    assert "Rules Engine" not in renderer


def test_innovation_canvas_is_alfheim_only_and_uses_shared_calibration() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'id="source-select"' in renderer
    assert "Dataset / camera" in renderer
    assert "segment.datasetId === selected.datasetId" in renderer
    assert 'candidate.datasetId === sourceSelect.value' in renderer
    assert 'state.segment.calibrationId + "-geometry-v1"' in renderer
    assert '"/api/calibration?segment="' in renderer
    assert '`${localServer}/api/alfheim/segments?workflow=innovation`' in extension
    assert "/api/alfheim/innovation/status" in extension
    assert "/api/alfheim/innovation/analyze" in extension


def test_canvas_locks_review_controls_until_ai_is_ready() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert renderer.count("data-ai-gated") >= 2
    assert 'const ready = state.segment.state === "ready"' in renderer
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

    assert 'theme: { type: "string", enum: ["default", "innovation"] }' in extension
    assert 'const theme = "innovation"' in extension
    assert 'url.searchParams.get("theme") === "innovation"' in extension
    assert 'renderHtml({ theme = "innovation" } = {})' in renderer
    assert 'data-app-theme="${appTheme}"' in renderer
    assert "Back to Product Home" in renderer
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
    assert '"analytics-cache", "ball-tracks.json"' in extension
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
    assert "async function loadDetectedBallTrack(segment)" in extension
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

    assert "const minimumReviewDurationSeconds = 30" in extension
    assert "const maximumReviewDurationSeconds = 60" in extension
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
    assert "const reviewDurationSeconds = [20, 30, 60]" in extension
    assert "const cameraSampleDurationSeconds = [30, 60]" in extension


def test_canvas_runs_ai_only_after_explicit_action() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'url.pathname === "/api/analyze"' in extension
    assert '"/api/alfheim/innovation/analyze"' in extension
    assert 'id="process-segment"' in renderer
    assert 'fetch("/api/analyze"' in renderer
    assert 'processButton.addEventListener("click"' in renderer
    assert "Starting a cold raw-video run." in renderer


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
    assert "selected.stageTiming = await liveStageTiming(selected)" in extension
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

    assert 'id: "football-event-review-live"' in live
    assert 'displayName: "Live Football Event Review"' in live
    assert 'title: audit ? "Ball Trajectory Audit" : "Live Football Event Review"' in live
    assert "Live Iteration-25 Football Event Review" not in live
    assert 'const defaultSegment = "segment-0540-020"' in live
    assert 'const theme = "grassroots"' in live
    assert "let launcherRegistryUpdate = Promise.resolve();" in live
    assert "await writeJsonAtomically(launcherRegistryPath, registry);" in live
    assert 'data-app-theme="grassroots"' in live_renderer
    assert 'themeColor = "#080d14"' in live_renderer
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
    assert 'return join(preparedSegmentRoot(segment), "live")' in live
    assert '"/api/alfheim/live/analyze"' in live
    assert "/api/alfheim/live/status" in live
    assert '"event-review-state-live"' in live
    assert '"src/football_poc/ball_tracking.py"' in live
    assert '"src/football_poc/innovation_day_snapshot/match_state.py"' in innovation
    assert 'return join(preparedSegmentRoot(segment), "innovation")' in innovation
    assert 'join(preparedSegmentRoot(segment), "copilot-review.json")' in live
    assert 'join(preparedSegmentRoot(segment), "copilot-review.json")' in innovation
    assert 'id="process-segment"' in live_renderer
    assert "football-event-review add_" not in live
    assert "football-event-review update_" not in live
    assert "football-event-review accept_" not in live
    assert "football-event-review publish_" not in live
    assert "football-event-review refresh_" not in live
    assert "football-event-review confirm_" not in live
    assert "football-event-review-live" not in innovation


def test_review_state_and_prompts_carry_hard_workflow_identity() -> None:
    innovation = EXTENSION.read_text(encoding="utf-8")
    live = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert 'const workflowId = "innovation_day_bac"' in innovation
    assert 'const canvasId = "football-event-review"' in innovation
    assert 'const workflowId = "live_iteration_25"' in live
    assert 'const canvasId = "football-event-review-live"' in live
    for extension in (innovation, live):
        assert "state.workflowId && state.workflowId !== workflowId" in extension
        assert "state.canvasId && state.canvasId !== canvasId" in extension
        assert '"review_workflow_mismatch"' in extension
        assert "state.workflowId = workflowId" in extension
        assert "state.canvasId = canvasId" in extension
        assert "`Workflow ID: ${workflowId}. Canvas ID: ${canvasId}.`" in extension

    assert "This is the BAC-assisted Innovation workflow." in innovation
    assert "Never invoke live Canvas " in innovation
    assert "actions, read live review state" in innovation
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
    assert "matchingStoredSnapshot(current, state)" in extension
    assert "return {current, reused: true, stale: false}" in extension
    assert '"innovation_regression_failed"' in extension
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


def test_live_engine_conversation_has_explicit_general_clip_return() -> None:
    extension = EXTENSION.read_text(encoding="utf-8")
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'id="show-general-clip-conversation"' in renderer
    assert "Back to General Clip" in renderer
    assert "function showGeneralClipConversation()" in renderer
    assert "selectedEngineIndex = null;" in renderer
    assert '"click",\n      showGeneralClipConversation' in renderer
    assert 'mode === "autopilot" ? "autopilot" : "plan"' in extension
    assert 'body.scope === "current_time"' in extension
    assert "Evidence scope: the entire prepared clip." in extension
    assert "local ±2-second window" in extension
    assert "A supported missing event still requires the " in extension
    assert 'fetch("/api/confirm-missing-event"' in renderer
    assert "Manual review reference" in renderer
    assert "Review it, then accept or reject it." in renderer


def test_live_general_conversation_can_create_manual_c_proposal() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert 'id="toggle-manual-review"' in renderer
    assert "Add Manual Review" in renderer
    assert 'id="manual-review-team"' in renderer
    assert 'id="manual-review-type"' in renderer
    assert 'id="manual-review-second"' in renderer
    assert 'id="manual-review-frame"' in renderer
    assert 'id="manual-review-time"' in renderer
    assert 'id="create-manual-review"' in renderer
    assert 'id="manual-review-note"' in renderer
    assert 'const noteInput = document.getElementById("manual-review-note");' in renderer
    assert "Evidence note (required)" in renderer
    assert 'const noteInput = document.getElementById("clip-message");' in renderer
    assert "--panel-border: #315f86;" in renderer
    assert "--nested-panel-border: #497ca6;" in renderer
    assert "Create Manual M# at " in renderer
    assert "function selectedManualReviewFrame()" in renderer
    assert "function initializeManualReviewTime()" in renderer
    assert "if (secondValue === \"\" || frameValue === \"\") return null;" in renderer
    assert "Choose both the event second and millisecond frame." in renderer
    assert "Choose Time to Create Manual M#" in renderer
    assert "const seconds = selectedFrame / REVIEW_FPS;" in renderer
    assert 'String(frame * 40).padStart(3, "0")' in renderer
    assert 'fetch("/api/manual-review-event"' in renderer
    assert "note\n          })" in renderer
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
    assert "<strong>Red C-only</strong>: verify C# to trigger" in renderer
    assert "<strong>Red E-only</strong>: ask the clip conversation first." in renderer


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
    assert 'id="clip-conversation-panel"' in renderer
    assert 'id="conversation-panel"' in renderer
    assert "segmentBuilderPanel.open =" in renderer
    assert "Copilot for Event 1" in renderer


def test_copilot_chat_is_embedded_and_scoped_to_the_selected_event() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")

    assert 'class="conversation" id="conversation-panel"' in renderer
    assert "This conversation contains only messages for the selected event." in renderer
    assert "message => message.eventIndex === selectedIndex" in renderer
    assert '"Innovation Copilot for Event " + (selectedIndex + 1)' in renderer
    live_renderer = LIVE_RENDERER.read_text(encoding="utf-8")
    assert '"Live Copilot for " + selectedReference' in live_renderer
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
    assert ".comparison-row.has-review-actions { min-height: 48px; }" in renderer
    assert 'item.classList.add("has-review-actions")' in renderer
    assert "function comparisonReviewCell(row)" in renderer
    assert "function comparisonActionIcon(kind)" in renderer
    assert '"Verify and accept Copilot proposal C" + (row.reviewIndex + 1)' in renderer
    assert 'accept.setAttribute("aria-label", acceptLabel)' in renderer
    assert "accept.title = acceptLabel" in renderer
    assert 'accept.append(comparisonActionIcon("accept"))' in renderer
    assert "await requestCopilotAcceptance(row.reviewIndex)" in renderer
    assert '"Reject Copilot proposal C" + (row.reviewIndex + 1)' in renderer
    assert 'reject.setAttribute("aria-label", rejectLabel)' in renderer
    assert "reject.title = rejectLabel" in renderer
    assert 'reject.append(comparisonActionIcon("reject"))' in renderer
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


def test_live_main_conversations_wait_for_coordinate_finalization() -> None:
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")

    assert "function ballCoordinateReviewCanBeVerified(selected)" in extension
    assert 'label: "Ball coordinate gate passed"' in extension
    assert "Choose Finalize to proceed now, or continue reviewing" in extension
    assert "!ballCoordinateReviewCanBeVerified(context.selected)" in extension
    assert 'return "Ball coordinate gate passed";' in renderer
    assert 'state?.coordinateReview?.status' in renderer
    assert '"coordinate-verified"' in renderer
    assert 'id="proceed-after-coordinate-gate"' in renderer
    assert 'id="continue-coordinate-review"' in renderer
    assert "Proceed to event review" in renderer
    assert '"Continue reviewing "' in renderer
    assert "() => void finalizeBallCoordinateReview()" in renderer
    assert 'selectedBatch?.status === "ready" && initialFrames.length' in renderer
    assert "Integrity-demoted only" in renderer
    assert "Download audit JSON" in renderer
    assert 'requestedReviewAudience === "trajectory-audit"' in renderer
    assert '"needs_more_checking"' in renderer
    assert "integrityRejectedFrames" in extension
    assert "yoloCandidates" in extension
    assert '<section class="fullscreen-event-chat" data-ai-gated' in renderer
    assert (
        '<section class="missing-event conversation" id="clip-conversation-panel"\n'
        "            data-ai-gated"
    ) in renderer
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
    assert "selected.recoveryAvailable = Boolean(" in LIVE_EXTENSION.read_text(
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
    assert '"Decision saved"' in renderer
    assert '"Awaiting review"' in renderer
    assert 'review.textContent = "Read-only"' in renderer
    assert "flaggedFrames: [...flaggedBallFrames].sort" in renderer
    assert '" flagged ball frame"' in renderer
    assert "User-flagged ball-coordinate source frames for this batch review" in extension
    assert "manual review selections, not inference evidence" in extension
    assert "function visibleBallStates()" in renderer
    assert "state.segment.ballTrackAvailable && !segmentRunActive()" in renderer
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
    assert '"Review frame " + selectedBallTargetFrame' in renderer
    assert '"Viewing raw frame " + selectedRawBallFrame' in renderer
    assert 'class="ball-frame-modal-status"' in renderer
    assert "Coordinate review active" in renderer
    assert '"Decision already recorded for review frame "' in renderer
    assert '"Decision saved for review frame "' in renderer
    assert '" is in coordinate review and awaiting a decision."' in renderer
    assert "lastBallCoordinateDecision = {" in renderer
    assert "showRawBallFrame(reviewedFrame, true);" in renderer
    assert 'result.textContent = "Custom coordinate awaiting confirmation"' in renderer
    assert '"✓ Confirmed · engine coordinate"' in renderer
    assert '"✓ Confirmed · custom "' in renderer
    assert '"✓ Confirmed · ball not visible"' in renderer
    assert '"⚠ Needs more checking"' in renderer
    assert 'result.className = "coordinate-review-result "' in renderer
    assert ".ball-frame-modal-marker.trajectory-audit" in renderer
    assert 'marker.setAttribute("r", trajectoryAuditMode ? "11" : "7");' in renderer
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
    assert "trajectoryAuditMode && !showEngineBallMarker" in renderer
    assert "trajectoryAuditMode && !showYoloBallMarkers" in renderer
    assert "&& showEngineBallMarker" in renderer
    assert "crosshair.hidden = marker.hidden || trajectoryAuditMode;" in renderer
    assert "Trajectory audit · red ring: engine · blue rings: cached YOLO" in renderer
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
    assert "...(state.trajectoryAudit?.observations || {})" in renderer
    assert renderer.index("...localAuditObservations") < renderer.index(
        "...(state.trajectoryAudit?.observations || {})"
    )
    assert 'fetch("/api/trajectory-audit-draft"' in renderer
    assert "evaluation_only_ball_trajectory_audit" in renderer
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
    assert '"Open batch review (" +' in renderer
    assert '"Send batch once to Copilot (" + flaggedBallFrames.size' in renderer
    assert 'document.getElementById("ball-coordinate-review-modal").showModal()' in renderer
    assert '? "Query mode · review finalized"' in renderer
    assert 'review.textContent = "Read-only"' in renderer
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

    assert "--background-color-default: #080d14" in renderer
    assert "--background-color-subtle: #101923" in renderer
    assert "--panel-border: #315f86" in renderer
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
    assert "initializeBallFrameControls();" in renderer
    assert renderer.count(
        'document.getElementById("previous-ball-frame").addEventListener('
    ) == 1
    assert "coordinateObservations: flaggedFrames" in renderer
    assert "function recordBallCoordinateDecision(observation, description)" in renderer
    assert '{decision: "agree", x: point.x, y: point.y}' in renderer
    assert '{decision: "undefined"}' in renderer
    assert "delete ballCoordinateObservations[String(frame)]" in renderer
    assert "evaluation-only observations" in LIVE_EXTENSION.read_text(
        encoding="utf-8"
    )
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")
    assert '["agree", "undefined", "specified"].includes(' in extension
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
    assert "row.engineIndex," in renderer
    assert "let stateRefreshQueued = false;" in renderer
    assert "stateRefreshQueued = true;" in renderer
    assert "} while (stateRefreshQueued);" in renderer


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
    assert 'document.getElementById("clip-conversation-panel").scrollIntoView({' in renderer


def test_live_review_controls_follow_c_and_e_workflow_state() -> None:
    renderer = LIVE_RENDERER.read_text(encoding="utf-8")
    extension = LIVE_EXTENSION.read_text(encoding="utf-8")

    assert 'id="fullscreen-primary-action"' in renderer
    assert 'id="fullscreen-workflow-note"' in renderer
    assert 'id="clip-conversation-note"' in renderer
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
    assert 'const reviewFocus = textarea?.value.trim() || "";' in renderer
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
    assert '" not confirmed"' in renderer
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
    assert 'path("scripts", "process-alfheim-segment.py")' in renderer
    assert '" --artifact-namespace live --events-only"' in renderer
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
    assert "const crossedCopilot = state?.drafts" in renderer
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
