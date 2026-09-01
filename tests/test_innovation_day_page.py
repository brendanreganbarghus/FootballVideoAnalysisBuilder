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


def test_landing_page_links_to_developer_setup_and_themed_labs() -> None:
    html = LANDING.read_text(encoding="utf-8")

    assert 'href="developer-guide/"' in html
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
