from pathlib import Path


ROOT = Path(__file__).parents[1]
PRODUCT = ROOT / "index.html"
SHOWCASE = ROOT / "showcase" / "innovation-day"
LANDING = SHOWCASE / "index.html"
GUIDE = SHOWCASE / "developer-guide" / "index.html"
BOARD = SHOWCASE / "board" / "index.html"
PLATFORM_BOARD = ROOT / "showcase" / "platform-board" / "index.html"
VIDEO_BUILDER = ROOT / "demo" / "az-demo-video" / "scripts" / "build_demo_video.py"


def test_product_landing_explains_current_review_and_future_concept() -> None:
    html = PRODUCT.read_text(encoding="utf-8")

    assert "Football Intelligence Platform" in html
    assert "Independent conclusions. One validation gate." in html
    assert "A published reference, not a polished guess." in html
    assert "14 / 14" in html
    assert "105" in html
    assert "Map the real pitch—not a generic football diagram." in html
    assert "show, redraw, undo, restore, and download" in html
    assert "Shots & Shots on Target" in html
    assert "Query By Probability" in html
    assert 'class="qbp-diagram"' in html
    assert "query-by-probability.png" not in html
    assert "Continuous Primary Stream" in html
    assert "Targeted Query Only" in html
    assert "Future architecture" in html
    assert "Secondary streams are not" in html
    assert 'href="showcase/innovation-day/"' in html
    assert "Football_AI_Platform_Demo.mp4" in html
    assert "Open Live Review Canvas" in html
    assert 'href="review-canvas?theme=default"' in html
    assert "How to Use the Canvas" in html
    assert 'href="showcase/platform-board/"' in html
    assert 'class="skip"' in html
    assert "prefers-reduced-motion" in html
    assert "object-fit: cover" not in html


def test_innovation_landing_links_to_current_surfaces() -> None:
    html = LANDING.read_text(encoding="utf-8")

    assert 'href="developer-guide/"' in html
    assert '<a class="button" href="board/">Innovation board</a>' in html
    assert 'href="../../"' in html
    assert "Football_AI_Platform_Demo.mp4" in html
    assert "Open the live Review Canvas" in html
    assert '../../review-canvas?theme=innovation' in html
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
    assert "theme innovation" in html
    assert "Do not inspect locked blind references" in html
    assert "evaluation-only" in html
    assert "app-native Copilot panel" in html
    assert "You do not need to ask Copilot each time" in html
    assert "one-time recovery prompt" in html
    assert "Default Theme Prompt" in html
    assert "Innovation Theme Prompt" in html
    assert 'id="copilot-review"' in html
    assert "Use Copilot as an independent reviewer" in html
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


def test_default_platform_board_is_distinct_and_landscape() -> None:
    html = PLATFORM_BOARD.read_text(encoding="utf-8")

    assert "aspect-ratio: 16 / 9" in html
    assert "@page { size: A3 landscape; margin: 0; }" in html
    assert "Football <em>Intelligence</em> Platform" in html
    assert "14 / 14" in html
    assert "105" in html
    assert "Query By Probability" in html
    assert "Stable Full-Pitch Frames" in html
    assert "review-canvas-timeline-accept.png" in html
    assert "Xebia" not in html


def test_demo_keeps_calibrated_stills_static_and_limits_other_motion() -> None:
    source = VIDEO_BUILDER.read_text(encoding="utf-8")

    assert "zoompan" in source
    assert "scale=3840:2160:force_original_aspect_ratio=decrease:flags=lanczos" in source
    assert "zoom_end=1.04" in source
    assert "zoom_end=1.18" not in source
    assert "force_original_aspect_ratio=decrease" in source
    assert "pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black" in source
    assert 'ImageShot(SHOTS / "review-canvas-timeline-accept.png", duration=reveal1)' in source
    assert 'ImageShot(SHOTS / "review-canvas-zoomed-action.png", duration=d4 - min(18.0, d4))' in source
