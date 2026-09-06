from pathlib import Path


PAGE = (
    Path(__file__).parents[1]
    / "benchmarks"
    / "alfheim"
    / "review-studio"
    / "index.html"
)


def test_review_studio_is_fixed_to_test_three() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert "Test 3 Review Workspace" in html
    assert "15:00–16:00" in html
    assert 'const SEGMENT_KEY = "segment-0300-020"' in html
    assert 'const MANUAL_STORAGE_KEY = "alfheim-900-60-manual-events-v1"' in html
    assert "Fixed to 1 minute" in html
    assert "prepared-segment" not in html
    assert "process-segment" not in html


def test_review_studio_keeps_three_sources_independent() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert "Copilot Draft" in html
    assert "Your Reference" in html
    assert "Rules Engine" in html
    assert "never change your manual clicks or the rules-engine output" in html
    assert "const copilotEvents = [" in html
    assert "localStorage.getItem(MANUAL_STORAGE_KEY)" in html
    assert "await fetch(engineUrl, {cache: \"no-store\"})" in html


def test_review_studio_supports_synchronized_event_review() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'id="review-video"' in html
    assert 'id="review-timeline"' in html
    assert 'id="previous-frame"' in html
    assert 'id="next-frame"' in html
    assert "video.currentTime = selected.seconds" in html
    assert 'data-decision="accepted"' in html
    assert 'data-decision="review"' in html
    assert 'data-decision="rejected"' in html
    assert "DECISION_STORAGE_KEY" in html


def test_review_studio_can_enlarge_video_review() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'id="enlarge-review"' in html
    assert "Enlarge Review" in html
    assert "videoCard.requestFullscreen()" in html
    assert "document.exitFullscreen()" in html
    assert 'document.addEventListener("fullscreenchange"' in html
    assert ".video-card:fullscreen video" in html


def test_review_studio_includes_test_three_foul_context() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert 'type: "foul_encountered"' in html
    assert "Play has stopped; later ball repositioning is not a pass." in html
    assert "Genuine free-kick restart reaches a black teammate." in html


def test_match_lab_links_to_test_three_review_workflow() -> None:
    match_lab = (
        Path(__file__).parents[1]
        / "benchmarks"
        / "alfheim"
        / "window-555"
        / "manual-review"
        / "index.html"
    ).read_text(encoding="utf-8")

    assert 'id="review-workflow-link"' in match_lab
    assert 'href="../../review-studio/"' in match_lab
