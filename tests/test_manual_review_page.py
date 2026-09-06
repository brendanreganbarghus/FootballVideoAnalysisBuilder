from pathlib import Path


PAGE = (
    Path(__file__).parents[1]
    / "benchmarks"
    / "alfheim"
    / "window-555"
    / "manual-review"
    / "index.html"
)


def test_manual_review_keeps_ai_and_manual_counters_isolated() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert "AI baseline" in html
    assert "Your clicks" in html
    assert 'fetch("../analytics-data/predicted-events.json"' in html
    assert "manual clicks never alter" in html
    assert 'id="overlay-ai-red-passes">0' in html
    assert 'id="overlay-manual-red-passes">0' in html
    assert 'id="overlay-ai-red-on-target">0' in html
    assert 'id="overlay-ai-black-on-target">0' in html
    assert 'class="scoreboards"' not in html


def test_manual_review_supports_shots_and_old_exports() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert '"7": ["red", "shot_on_target"]' in html
    assert '"8": ["black", "shot_on_target"]' in html
    assert "count(events, team, \"shot_on_target\")" in html
    assert "schema_version: 2" in html
    assert "[1, 2].includes(payload.schema_version)" in html


def test_clear_resets_video_and_manual_events() -> None:
    html = PAGE.read_text(encoding="utf-8")
    clear_handler = html.split("function clearManualEvents()", 1)[1].split(
        "\n  }", 1
    )[0]

    assert 'confirm("Clear every manual event for this video?")' in clear_handler
    assert "events = []" in clear_handler
    assert "video.pause()" in clear_handler
    assert "video.currentTime = clipStartSeconds" in clear_handler
    assert (
        'document.getElementById("clear").addEventListener'
        '("click", clearManualEvents)'
    ) in html


def test_manual_and_ai_event_tables_show_receiver_times() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert "Manual ↔ AI Event Correlation" in html
    assert 'id="correlated-events"' in html
    assert "event.completion_seconds ?? event.clip_seconds" in html
    assert "data-seek-manual" in html
    assert "data-seek-ai" in html
    assert "including throw-ins, goal kicks, free kicks, and other restarts" in html
    assert "correlateEvents()" in html
    assert "eventCompletionSeconds" in html
    assert "frame ${Math.round(seconds * 25)}" in html
    assert (
        "canonicalEventType(manual.event_type) !=="
        "\n          canonicalEventType(ai.event_type)"
    ) in html
    assert "sameTeam: manual.team === ai.team" in html
    assert (
        "Number(right.sameTeam) - Number(left.sameTeam)"
    ) in html


def test_prepared_segments_load_published_manual_reference_without_local_edits() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert "async function loadPublishedManualReference(cacheKey)" in html
    assert html.index(
        "async function loadPublishedManualReference(cacheKey)"
    ) < html.index("async function loadPreparedSegments(")
    assert '"/manual-reference.json"' in html
    assert "if (response.status === 404) return []" in html
    assert "parsedManualEvents === null" in html
    assert "!parsedManualEvents.length && !isExplicitlyEmpty" in html
    assert '`${storageKey}-explicitly-empty-v1`' in html
    assert "await loadPublishedManualReference(activeCacheKey)" in html


def test_validated_segments_are_marked_in_prepared_dropdown() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert '" · ✓ 100% validated"' in html
    assert '"validated-segment-option"' in html
    assert "#prepared-segment option.validated-segment-option" in html


def test_live_events_appear_beside_video_with_current_highlight() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'class="review-workspace"' in html
    assert 'id="live-event-list" aria-live="polite"' in html
    assert "Newest reached event first" in html
    assert "renderLiveEvents(currentReviewTime)" in html
    assert ".slice(-6)" in html
    assert ".reverse()" in html
    assert 'item.classList.add("is-current")' in html
    assert 'source: "AI"' in html
    assert 'entry.isAi ? "AI event" : "Manual event"' in html
    assert 'eventTime.className = "event-time"' in html
    assert "eventTime.append(`${entry.time.toFixed(3)}s`, eventFrame)" in html
    assert "@media (max-width: 1050px)" in html
    assert ".review-workspace { grid-template-columns: 1fr; }" in html


def test_manual_and_ai_use_consistent_event_names() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'pass_candidate: "Completed pass"' in html
    assert 'restart_pass_candidate: "Completed pass"' in html
    assert 'turnover_candidate: "Turnover"' in html
    assert 'shot_candidate: "Shot"' in html
    assert 'shot_on_target_candidate: "Shot on target"' in html
    assert "Completed-pass candidate" not in html
    assert "Restart-pass candidate" not in html


def test_seeking_keeps_full_correlation_and_replays_ai_counters() -> None:
    html = PAGE.read_text(encoding="utf-8")
    render = html.split("function render()", 1)[1].split(
        "\n  function eventLabel", 1
    )[0]

    assert "events.filter(" not in render
    assert "const reachedAiEvents = aiEvents.filter(" in render
    assert "count(events, team" in render
    assert "count(reachedAiEvents, team" in render
    assert "correlateEvents().map(pair =>" in render


def test_fullscreen_video_keeps_live_ai_overlay() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'id="video-stage"' in html
    assert 'aria-label="Live AI and manual statistics"' in html
    assert 'id="show-live-overlay"' in html
    assert 'id="overlay-ai-red-passes">0' in html
    assert 'id="overlay-ai-black-turnovers">0' in html
    assert 'id="fullscreen">Full screen with stats' in html
    assert "reviewWorkspace.requestFullscreen()" in html
    assert "document.fullscreenElement === reviewWorkspace" in html
    assert "document.getElementById(`overlay-ai-${team}-${metric}`)" in html
    assert "grid-template-rows: minmax(0, 1fr) auto auto;" in html
    assert html.index('class="video-media"') < html.index(
        'class="live-overlay"'
    )
    assert html.index("</div>", html.index('class="video-media"')) < html.index(
        'class="live-overlay"'
    )


def test_fullscreen_video_shows_manual_counts_separately() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert html.count("Your clicks") == 2
    assert 'id="overlay-manual-red-passes">0' in html
    assert 'id="overlay-manual-red-turnovers">0' in html
    assert 'id="overlay-manual-black-passes">0' in html
    assert 'id="overlay-manual-black-turnovers">0' in html
    assert "`overlay-manual-${team}-${metric}`" in html


def test_fullscreen_video_has_compact_manual_review_controls() -> None:
    html = PAGE.read_text(encoding="utf-8")
    video_stage = html.split('<section class="video-stage" id="video-stage">', 1)[1]
    video_stage = video_stage.split("</section>", 1)[0]

    assert 'aria-label="Fullscreen manual event tracking"' in video_stage
    assert video_stage.count('data-type="completed_pass"') == 2
    assert video_stage.count('data-type="turnover"') == 2
    assert '<legend>Red/white team</legend>' in video_stage
    assert '<legend>Black team</legend>' in video_stage
    assert video_stage.index('<legend>Red/white team</legend>') < video_stage.index(
        'data-team="red" data-type="turnover"'
    )
    assert video_stage.index('<legend>Black team</legend>') < video_stage.index(
        'data-team="black" data-type="turnover"'
    )
    assert 'data-review-action="frame-back"' in video_stage
    assert 'data-review-action="confirm"' in video_stage
    assert 'data-review-action="frame-forward"' in video_stage
    assert 'data-playback-action="undo"' in video_stage
    assert 'data-review-action="clear"' in video_stage
    assert "Clear All Entries" in video_stage
    assert video_stage.count('src="pass.jpeg"') == 2
    assert video_stage.count('src="slide.jpeg"') == 2
    assert video_stage.count("<span>Pass</span>") == 2
    assert video_stage.count("<span>Turnover</span>") == 2
    assert "1 · Pass" not in video_stage
    assert "2 · Pass" not in video_stage
    assert "3 · Turnover" not in video_stage
    assert "4 · Turnover" not in video_stage
    assert "flex-direction: column;" in html
    assert 'class="video-media"' in video_stage
    assert "grid-template-rows: minmax(0, 1fr) auto auto;" in html
    assert "border-top: 1px solid" in html
    assert "min-height: 44px;" in html
    assert (
        ".review-workspace:fullscreen .fullscreen-review-controls { display: grid; }"
        in html
    )
    assert 'document.querySelectorAll("[data-review-action]")' in html
    assert 'if (action === "clear") clearManualEvents()' in html


def test_fullscreen_video_supports_keyboard_accessible_zoom_and_focus() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'aria-label="Fullscreen video zoom"' in html
    assert 'data-zoom-action="out"' in html
    assert 'data-zoom-action="reset"' in html
    assert 'data-zoom-action="in"' in html
    assert 'id="zoom-focus-x"' in html
    assert 'id="zoom-focus-y"' in html
    assert 'id="zoom-status" aria-live="polite"' in html
    assert "const videoZoomLevels = [1, 1.5, 2, 3, 4]" in html
    assert "surface.style.transform = transform" in html
    assert "surface.style.transformOrigin = transformOrigin" in html
    assert 'control.addEventListener("input", updateVideoZoom)' in html
    assert "resetVideoZoom()" in html


def test_fullscreen_timeline_remains_available_while_video_is_zoomed() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'aria-label="Fullscreen playback timeline"' in html
    assert 'id="fullscreen-play-toggle"' in html
    assert 'id="fullscreen-timeline"' in html
    assert 'name="fullscreen-timeline"' in html
    assert 'id="fullscreen-timeline-status" aria-live="polite"' in html
    assert "function updateFullscreenTimeline()" in html
    assert "fullscreenTimeline.max = String(reviewDurationSeconds)" in html
    assert "clipStartSeconds + Number(fullscreenTimeline.value)" in html
    assert 'video.addEventListener(name, updateFullscreenTimeline)' in html


def test_manual_event_buttons_are_grouped_by_team() -> None:
    html = PAGE.read_text(encoding="utf-8")
    controls = html.split('<section class="controls"', 1)[1].split(
        "</section>", 1
    )[0]

    red_group, black_group = controls.split(
        '<fieldset class="team-event-group black-team">', 1
    )
    assert red_group.count('data-team="red"') == 4
    assert 'data-team="black"' not in red_group
    assert black_group.count('data-team="black"') == 4
    assert 'data-team="red"' not in black_group


def test_optional_setup_and_full_correlation_are_collapsible() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert '<details class="card state-panel" id="segment-panel">' in html
    assert "<summary>Test Segment</summary>" in html
    assert '<details class="card state-panel" id="geometry-panel">' in html
    assert "<summary>Camera Geometry</summary>" in html
    assert (
        '<details class="card correlation-details" id="ai-events-panel">' in html
    )
    assert "<summary>Manual ↔ AI Event Correlation</summary>" in html
    assert 'details.card > summary:focus-visible' in html


def test_counting_rules_cover_foul_free_kick_restarts() -> None:
    html = PAGE.read_text(encoding="utf-8")
    normalized = " ".join(html.split())

    assert "Foul and free-kick rule:" in normalized
    assert "play stops without a turnover" in normalized
    assert "Ignore loose-ball movement after the foul" in normalized
    assert "record one completed pass only when a teammate first" in normalized
    assert "A foul stops play without a turnover" in html
    assert "resume tracking from the restart kick" in html


def test_foul_marker_is_annotation_only_and_highlighted() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert html.count('data-type="foul_encountered"') == 2
    assert 'foul_encountered: "Foul encountered"' in html
    assert '"f": ["neutral", "foul_encountered"]' in html
    assert 'manual.event_type === "foul_encountered"' in html
    assert 'eventType === "foul_encountered" ? null : team' in html
    assert "Annotation only" in html
    assert 'item.classList.add("foul-event")' in html
    assert ".foul-event-group" in html
    assert ".foul-annotation" in html


def test_assisted_review_pauses_and_refines_event_by_frame() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'id="assist-toggle" data-assist-toggle aria-pressed="true"' in html
    assert 'id="frame-back" data-assisted-review' in html
    assert 'id="confirm-resume" data-assisted-review' in html
    assert "video.currentTime + direction / 25" in html
    assert "(nextTime - clipStartSeconds).toFixed(3)" in html
    assert 'event.key === "ArrowLeft"' in html
    assert 'event.key === "Enter"' in html
    assert "video.playbackRate = 0.5" in html


def test_assisted_review_toggles_all_normal_and_fullscreen_controls() -> None:
    html = PAGE.read_text(encoding="utf-8")
    video_stage = html.split('<section class="video-stage" id="video-stage">', 1)[1]
    video_stage = video_stage.split("</section>", 1)[0]

    assert html.count("data-assist-toggle") == 3
    assert 'class="fullscreen-assisted-content" data-assisted-review' in video_stage
    for action in ("back", "slower", "normal", "forward", "undo"):
        assert f'data-playback-action="{action}"' in video_stage
        assert f'data-playback-action="{action}"' in html
    assert 'document.querySelectorAll("[data-assisted-review]")' in html
    assert 'control.classList.toggle("hidden", !assistedReview)' in html
    assert 'toggle.setAttribute("aria-pressed", String(assistedReview))' in html
    assert "if (!assistedReview) return;" in html


def test_match_lab_combines_overlays_and_segment_selection() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert "Alfheim Match Lab" in html
    assert 'id="show-ball"' in html
    assert 'id="show-pitch"' in html
    assert 'id="show-goals"' in html
    assert 'id="video-mode"' in html
    assert 'id="segment-start-minute"' in html
    assert 'id="segment-start-second"' in html
    assert 'id="segment-duration"' in html
    assert 'id="prepared-segment"' in html
    assert 'id="ai-progress"' in html
    assert 'id="processing-timing"' in html
    assert 'id="process-segment"' in html
    assert "AI tracking · processing" in html
    assert 'fetch("/api/alfheim/segment"' in html
    assert 'fetch("/api/alfheim/analyze"' in html
    assert 'fetch("/api/alfheim/info"' in html
    assert 'fetch("/api/alfheim/segments"' in html
    assert "/api/alfheim/status?cache_key=" in html
    assert "source_start_seconds: sourceStartSeconds" in html
    assert "requestedMinute * 60 + requestedSecond" in html
    assert "requestedSecond > 59" in html
    assert 'pageParameters.get("prepare") === "1"' in html
    assert "selectedValidationTest !== null" in html
    assert "if (preparingBookmarkedSegment)" in html


def test_ai_processing_shows_elapsed_time_and_segment_duration() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert "function startAiProcessingTimer()" in html
    assert "function stopAiProcessingTimer()" in html
    assert "setInterval(updateProcessingTiming, 1000)" in html
    assert "`Segment ${reviewDurationSeconds.toFixed(1)}s · AI elapsed ${elapsed}`" in html
    assert "font-variant-numeric: tabular-nums" in html


def test_validation_test_parameter_selects_its_fixed_window() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert '"test-1": {start: 180, duration: 60, cacheKey: "segment-0060-020"}' in html
    assert '"test-2": {start: 540, duration: 60, cacheKey: "segment-0180-020"}' in html
    assert "validationTestWindows[pageParameters.get(\"test\")]" in html
    assert "loadPreparedSegments(selectedValidationTest?.cacheKey)" in html
    assert "selectedValidationTest.start" in html
    assert "selectedValidationTest.duration" in html


def test_match_lab_lists_prepared_segments_with_time_and_ai_state() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert "function preparedSegmentLabel(segment)" in html
    assert "preparedStateLabel(segment.state)" in html
    assert 'ready: "AI ready"' in html
    assert 'prepared: "video ready · AI not run"' in html
    assert '" · protected v41 reel"' in html
    assert 'preparedSegmentSelect.addEventListener("change"' in html
    assert "prepareSegmentButton.click()" in html


def test_match_lab_can_rerun_event_logic_without_changing_manual_clicks() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert '"Rerun AI logic"' in html
    assert 'processSegmentButton.dataset.eventsOnly = "true"' in html
    assert "events_only: eventsOnly" in html
    assert "Manual clicks are unchanged." in html
    assert 'eventUrl.searchParams.set("updated", Date.now())' in html


def test_match_lab_flags_missing_required_baseline_installation() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'id="baseline-install-status"' in html
    assert '["segment-0575-020", "28:45–29:45"]' in html
    assert '["segment-0595-020", "29:45–30:45"]' in html
    assert '["segment-0615-020", "30:45–31:45"]' in html
    assert "Installation incomplete. Prepare the missing v41 baseline videos" in html
    assert "../../../../README.md#local-alfheim-data" in html
    assert "See the local data setup." in html
    assert (
        "Installation complete: all three protected v41 baseline videos are ready."
        in html
    )


def test_match_lab_supports_per_camera_geometry_calibration() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'id="geometry-overlay"' in html
    assert '<option value="near_touchline">' in html
    assert '<option value="left_goal_mouth">' in html
    assert "geometry.features[editingFeature].push" in html
    assert "const rect = geometryCanvas.getBoundingClientRect()" in html
    assert "const rect = videoStage.getBoundingClientRect()" not in html
    assert "all four visible goal-frame corners clockwise" in html
    assert "trace the outer edge of each" in html
    assert "whole ball must cross its outer edge" in html
    assert "pitch-calibration.json" in html


def test_match_lab_locks_panels_for_preparation_and_ai_readiness() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'id="segment-panel"' in html
    assert 'id="geometry-panel"' in html
    assert 'id="ai-readiness-panel"' in html
    assert 'id="ai-events-panel"' in html
    assert "function setSegmentPreparing(preparing)" in html
    assert "function setGeometryAvailable(available)" in html
    assert "function setAiReady(ready)" in html
    assert "setSegmentPreparing(true)" in html
    assert "setGeometryAvailable(false)" in html
    assert 'if (status.state !== "ready") setAiReady(false)' in html
    assert "setAiReady(true)" in html
