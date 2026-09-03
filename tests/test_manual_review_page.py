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

    assert "Your live reference" in html
    assert "AI calibrated baseline" in html
    assert 'fetch("../analytics-data/predicted-events.json"' in html
    assert "manual clicks never alter" in html
    assert html.count("Red/white completed passes") == 2
    assert html.count("Black completed passes") == 2
    assert "ai-red-passes" in html
    assert "manual-red-passes" in html
    assert 'id="ai-red-on-target">0' in html
    assert 'id="ai-black-on-target">0' in html


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

    assert "Your timestamped clicks" in html
    assert "AI timestamped events" in html
    assert 'id="ai-events"' in html
    assert "event.completion_seconds ?? event.clip_seconds" in html
    assert "data-seek-manual" in html
    assert "data-seek-ai" in html
    assert "including throw-ins, goal kicks, free kicks, and other restarts" in html
    assert "events.map(event =>" in html
    assert "aiEvents.map(event =>" in html


def test_seeking_keeps_all_manual_and_ai_events_visible() -> None:
    html = PAGE.read_text(encoding="utf-8")
    render = html.split("function render()", 1)[1].split(
        "\n  function eventLabel", 1
    )[0]

    assert "events.filter(" not in render
    assert "aiEvents.filter(" not in render
    assert "count(events, team" in render
    assert "count(aiEvents, team" in render
    assert "events.map(event =>" in render
    assert "aiEvents.map(event =>" in render


def test_fullscreen_video_keeps_live_ai_overlay() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'id="video-stage"' in html
    assert 'aria-label="Live AI and manual statistics"' in html
    assert 'id="show-live-overlay"' in html
    assert 'id="overlay-ai-red-passes">0' in html
    assert 'id="overlay-ai-black-turnovers">0' in html
    assert 'id="fullscreen">Full screen with stats' in html
    assert "videoStage.requestFullscreen()" in html
    assert "document.fullscreenElement === videoStage" in html
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
    assert 'data-review-action="undo"' in video_stage
    assert 'data-review-action="clear"' in video_stage
    assert "Clear all entries" in video_stage
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
    assert ".video-stage:fullscreen .fullscreen-review-controls { display: grid; }" in html
    assert 'document.querySelectorAll("[data-review-action]")' in html
    assert 'if (action === "clear") clearManualEvents()' in html


def test_manual_event_buttons_are_grouped_by_team() -> None:
    html = PAGE.read_text(encoding="utf-8")
    controls = html.split(
        '<section class="controls" '
        'aria-label="Manual event tracking">', 1
    )[1].split("</section>", 1)[0]

    red_group, black_group = controls.split(
        '<fieldset class="team-event-group black-team">', 1
    )
    assert red_group.count('data-team="red"') == 4
    assert 'data-team="black"' not in red_group
    assert black_group.count('data-team="black"') == 4
    assert 'data-team="red"' not in black_group


def test_counting_rules_cover_foul_free_kick_restarts() -> None:
    html = PAGE.read_text(encoding="utf-8")
    normalized = " ".join(html.split())

    assert "Foul and free-kick rule:" in normalized
    assert "play stops without a turnover" in normalized
    assert "Ignore loose-ball movement after the foul" in normalized
    assert "record one completed pass only when a teammate first" in normalized
    assert "A foul stops play without a turnover" in html
    assert "resume tracking from the restart kick" in html


def test_assisted_review_pauses_and_refines_event_by_frame() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'id="assist-toggle">Assisted review: ON' in html
    assert 'id="frame-back">← Previous frame' in html
    assert 'id="confirm-resume">Enter · Confirm and resume' in html
    assert "video.currentTime + direction / 25" in html
    assert "(nextTime - clipStartSeconds).toFixed(3)" in html
    assert 'event.key === "ArrowLeft"' in html
    assert 'event.key === "Enter"' in html
    assert "video.playbackRate = 0.5" in html


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


def test_match_lab_lists_prepared_segments_with_time_and_ai_state() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert "function preparedSegmentLabel(segment)" in html
    assert "preparedStateLabel(segment.state)" in html
    assert 'ready: "AI ready"' in html
    assert 'prepared: "video ready · AI not run"' in html
    assert '" · protected v41 reel"' in html
    assert 'preparedSegmentSelect.addEventListener("change"' in html
    assert "prepareSegmentButton.click()" in html


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
