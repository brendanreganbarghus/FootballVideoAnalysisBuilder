from pathlib import Path


ROOT = Path(__file__).parents[1]
PRODUCT = ROOT / "index.html"
SHOWCASE = ROOT / "showcase" / "innovation-day"
LANDING = SHOWCASE / "index.html"
GUIDE = SHOWCASE / "developer-guide" / "index.html"
BOARD = SHOWCASE / "board" / "index.html"


def test_product_landing_explains_current_review_and_future_concept() -> None:
    html = PRODUCT.read_text(encoding="utf-8")

    assert "Football Intelligence Platform" in html
    assert "Independent conclusions. One validation gate." in html
    assert "Query By Probability" in html
    assert "Future architecture" in html
    assert "Secondary streams are not" in html
    assert 'href="showcase/innovation-day/"' in html
    assert "Football_AI_Platform_Demo.mp4" in html
    assert 'class="skip"' in html
    assert "prefers-reduced-motion" in html


def test_innovation_landing_links_to_current_surfaces() -> None:
    html = LANDING.read_text(encoding="utf-8")

    assert 'href="developer-guide/"' in html
    assert '<a class="button" href="board/">Innovation board</a>' in html
    assert 'href="../../"' in html
    assert "Football_AI_Platform_Demo.mp4" in html
    assert "Open live review instructions" in html
    assert "One review workspace. Two independent conclusions." in html
    assert "Query By Probability" in html
    assert "manual-review/" not in html
    assert "validation-lab/" not in html
    assert 'class="skip-link"' in html
    assert "prefers-reduced-motion" in html


def test_developer_guide_matches_current_local_artifact_flow() -> None:
    html = GUIDE.read_text(encoding="utf-8")

    assert "Verify-Artifacts.ps1" in html
    assert "FOOTBALL_ARTIFACT_ROOT" in html
    assert "FOOTBALL_ALFHEIM_PANO" in html
    assert "10-master-data\\alfheim\\pano" in html
    assert "20-approved-models" in html
    assert "30-shared-baselines\\event-review-state" in html
    assert "benchmarks\\alfheim\\generated\\" in html
    assert "feature/pass-shot-validation" in html
    assert "segment-0300-020" in html
    assert "<code>innovation</code>" in html
    assert "Do not inspect locked blind references" in html
    assert "evaluation-only" in html
    assert "not copied from OneDrive" in html
    assert "manual-review/" not in html
    assert "validation-lab/" not in html
    assert "innovation-day-showcase" not in html


def test_developer_guide_links_to_all_current_entry_points() -> None:
    html = GUIDE.read_text(encoding="utf-8")

    assert 'id="shared-review-state"' in html
    assert 'id="review-canvas"' in html
    assert 'href="../"' in html
    assert '<a href="../board/">Innovation board</a>' in html
    assert '<a href="../../../">Product home</a>' in html
    assert '<a href="./" aria-current="page">Developer setup</a>' in html
    assert "http://127.0.0.1:8080/" in html
    assert "http://127.0.0.1:8080/showcase/innovation-day/" in html


def test_landscape_board_tells_current_innovation_story() -> None:
    html = BOARD.read_text(encoding="utf-8")

    assert "aspect-ratio: 16 / 9" in html
    assert "@page { size: A3 landscape; margin: 0; }" in html
    assert "Completed passes" in html
    assert "Possession changes" in html
    assert "Shots on target" in html
    assert "Shots off target" in html
    assert "Corners taken" in html
    assert "Working local prototype" in html
    assert "Query By Probability" in html
    assert "Future architecture" in html
    assert "Live match snapshot" in html
    assert "Illustrative values" in html
    assert "<span>Passes</span><b>87</b>" in html
    assert "<span>Turnovers</span><b>14</b>" in html


def test_landscape_board_uses_current_product_images() -> None:
    html = BOARD.read_text(encoding="utf-8")
    assets = BOARD.parent / "assets"

    assert 'src="assets/match-lab.png"' in html
    assert 'src="assets/validation-lab.png"' in html
    assert 'src="assets/innovation-overview.png"' in html
    assert "Football Event Review" in html
    assert all(
        (assets / filename).is_file()
        for filename in (
            "match-lab.png",
            "validation-lab.png",
            "innovation-overview.png",
        )
    )
