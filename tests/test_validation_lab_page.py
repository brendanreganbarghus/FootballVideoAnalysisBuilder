from pathlib import Path


PAGE = (
    Path(__file__).parents[1]
    / "benchmarks"
    / "alfheim"
    / "validation-lab"
    / "index.html"
)


def test_validation_lab_separates_fixed_suites_from_match_playground() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert "Alfheim Validation Lab" in html
    assert "Match Lab playground" in html
    assert "Passes + turnovers" in html
    assert "Shots on/off target" in html
    assert "Next suite" in html


def test_validation_lab_has_five_fixed_blind_reels() -> None:
    html = PAGE.read_text(encoding="utf-8")

    for start, cache_key in [
        (180, "segment-0060-020"),
        (540, "segment-0180-020"),
        (900, "segment-0300-020"),
        (1260, "segment-0420-020"),
        (2100, "segment-0700-020"),
    ]:
        assert f"start: {start}" in html
        assert f'cacheKey: "{cache_key}"' in html


def test_validation_lab_locks_manual_before_scoring_ai() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert "Lock manual reference" in html
    assert "referenceStorageKey" in html
    assert "status.events_url" in html
    assert "candidate.team === event.team" in html
    assert "candidate.event_type === event.event_type" in html
    assert "delta <= 1" in html
    assert "overallThreshold: 0.9" in html
    assert "reelThreshold: 0.8" in html


def test_validation_lab_links_to_innovation_day_developer_setup() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert "../../../showcase/innovation-day/developer-guide/" in html


def test_validation_lab_separates_default_and_innovation_navigation() -> None:
    html = PAGE.read_text(encoding="utf-8")

    assert '.innovation-navigation { display: none; }' in html
    assert (
        'html[data-theme="innovation"] .innovation-navigation '
        "{ display: inline-block; }"
    ) in html
    assert 'id="validation-lab-link"' in html
    assert "../../../showcase/innovation-day/board/" in html
    assert 'document.getElementById("validation-lab-link").href = "?theme=innovation"' in html
    assert "../window-555/manual-review/?theme=innovation" in html
