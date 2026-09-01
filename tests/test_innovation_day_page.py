from pathlib import Path


ROOT = Path(__file__).parents[1]
LANDING = ROOT / "showcase" / "innovation-day" / "index.html"
GUIDE = (
    ROOT
    / "showcase"
    / "innovation-day"
    / "developer-guide"
    / "index.html"
)
BOARD = ROOT / "showcase" / "innovation-day" / "board" / "index.html"


def test_landing_page_links_to_developer_setup_and_themed_labs() -> None:
    html = LANDING.read_text(encoding="utf-8")

    assert 'href="developer-guide/"' in html
    assert 'href="board/"' in html
    assert "manual-review/?theme=innovation" in html
    assert "validation-lab/?theme=innovation" in html


def test_developer_guide_documents_local_artifact_flow() -> None:
    html = GUIDE.read_text(encoding="utf-8")

    assert "Verify-Artifacts.ps1" in html
    assert "FOOTBALL_ALFHEIM_PANO" in html
    assert "10-master-data\\alfheim\\pano" in html
    assert "20-approved-models" in html
    assert "30-shared-baselines\\v41" in html
    assert "benchmarks\\alfheim\\generated\\" in html
    assert "innovation-day-showcase" in html
    assert "Do not inspect locked blind references" in html
    assert "28:45–29:45" in html
    assert "29:45–30:45" in html
    assert "30:45–31:45" in html
    assert "not copied from OneDrive" in html


def test_developer_guide_links_back_to_all_innovation_surfaces() -> None:
    html = GUIDE.read_text(encoding="utf-8")

    assert 'id="shared-v41-baseline"' in html
    assert 'href="../"' in html
    assert "manual-review/?theme=innovation" in html
    assert "validation-lab/?theme=innovation" in html


def test_landscape_board_tells_the_innovation_story() -> None:
    html = BOARD.read_text(encoding="utf-8")

    assert "aspect-ratio: 16 / 9" in html
    assert "@page { size: A3 landscape; margin: 0; }" in html
    assert "Ultralytics YOLO" in html
    assert "Completed passes" in html
    assert "Possession changes" in html
    assert "Shots on target" in html
    assert "Shots off target" in html
    assert "Corners taken" in html
    assert "Reduce hours of manual match review" in html
    assert "Working local prototype" in html
    assert "Next: affordable multi-camera" in html
    assert "Live match snapshot" in html
    assert "Illustrative values" in html
    assert "<span>Passes</span><b>87</b>" in html
    assert "<span>Turnovers</span><b>14</b>" in html
    assert "<span>On target</span><b>3</b>" in html
    assert "<span>Off target</span><b>2</b>" in html


def test_landscape_board_uses_supplied_product_images() -> None:
    html = BOARD.read_text(encoding="utf-8")
    assets = BOARD.parent / "assets"

    assert 'src="assets/match-lab.png"' in html
    assert 'src="assets/validation-lab.png"' in html
    assert 'src="assets/innovation-overview.png"' in html
    assert (assets / "match-lab.png").is_file()
    assert (assets / "validation-lab.png").is_file()
    assert (assets / "innovation-overview.png").is_file()
