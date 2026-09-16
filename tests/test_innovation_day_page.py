from pathlib import Path


ROOT = Path(__file__).parents[1]
PRODUCT = ROOT / "index.html"
SHOWCASE = ROOT / "showcase" / "innovation-day"
LANDING = SHOWCASE / "index.html"
GUIDE = SHOWCASE / "developer-guide" / "index.html"
BOARD = SHOWCASE / "board" / "index.html"
PLATFORM_BOARD = ROOT / "showcase" / "platform-board" / "index.html"
REVIEW_WORKFLOW = ROOT / "showcase" / "review-workflow" / "index.html"
VIDEO_BUILDER = ROOT / "demo" / "az-demo-video" / "scripts" / "build_demo_video.py"
EXECUTIVE_SCENES = ROOT / "demo" / "az-demo-video" / "scripts" / "executive_scenes.json"
EXECUTIVE_BUILDER = ROOT / "demo" / "az-demo-video" / "scripts" / "build_executive_video.py"
EXECUTIVE_ARCHITECTURE = ROOT / "demo" / "landing" / "executive-architecture.html"


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
    assert "Football_AI_Platform_Demo_4m48s.mp4" in html
    assert "Open Live Review Canvas" in html
    assert 'href="review-canvas?theme=default"' in html
    assert "How to Use the Canvas" in html
    assert 'href="showcase/platform-board/"' in html
    assert 'href="showcase/review-workflow/"' in html
    assert 'class="skip"' in html
    assert "prefers-reduced-motion" in html
    assert "object-fit: cover" not in html


def test_innovation_landing_links_to_current_surfaces() -> None:
    html = LANDING.read_text(encoding="utf-8")

    assert 'href="developer-guide/"' in html
    assert '<a class="button" href="board/">Innovation board</a>' in html
    assert 'href="../../"' in html
    assert "Football_AI_Platform_Demo_4m48s.mp4" in html
    assert "Open the live Review Canvas" in html
    assert '../../review-canvas?theme=innovation' in html
    assert "One review workspace. Two independent conclusions." in html
    assert "Query By Probability" in html
    assert "What the Football Rules Engine Contains" in html
    assert "MATCH_LAW_PROFILE" in html
    assert "Evidence Adapters" in html
    assert "Match-State Machine" in html
    assert "Analytics Definitions" in html
    assert "Event State Machines" in html
    assert "Validation Guards" in html
    assert 'href="../review-workflow/"' in html
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
    assert "40-team-runs\\" in html
    assert "benchmarks\\alfheim\\generated\\" in html
    assert "benchmarks\\custom-cameras\\" in html
    assert "verify-innovation-workspace.py" in html
    assert "publish-segment-run.py" in html
    assert "cold raw-video AI pipeline" in html
    assert "Own separate event families and segments" in html
    assert "A goal implies on-target" in html
    assert "Serial merge gate" in html
    assert "Full-match upload and team locking are not implemented yet" in html
    assert "feature/pass-shot-validation" in html
    assert "segment-0180-020" in html
    assert "event-review-state-innovation" in html
    assert "event-review-state-live" in html
    assert "separate engines" in html
    assert "BAC-assisted testing" in html
    assert "Do not inspect locked blind references" in html
    assert "evaluation-only" in html
    assert "app-native Copilot panel" in html
    assert "You do not need to ask Copilot each time" in html
    assert "one-time recovery prompt" in html
    assert "Live review prompt" in html
    assert "Innovation review prompt" in html
    assert 'id="copilot-review"' in html
    assert "Use Copilot as an independent reviewer" in html
    assert "be copied into the repository" in html
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
    assert "review-canvas-timeline-calibrated.png" in html
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


def test_executive_video_preserves_claim_boundaries_and_existing_demo() -> None:
    scenes = EXECUTIVE_SCENES.read_text(encoding="utf-8")
    builder = EXECUTIVE_BUILDER.read_text(encoding="utf-8")
    architecture = EXECUTIVE_ARCHITECTURE.read_text(encoding="utf-8")

    assert "next-stage capabilities, not completed claims" in scenes
    assert "controlled pilot target is at least ninety-five percent" in scenes
    assert "Planning target, not a quotation" in builder
    assert "future Query By Probability concept" in scenes
    assert 'DEFAULT_OUTPUT = DEMO_DIR / "Football_AI_Executive_Pitch_4min.mp4"' in builder
    assert 'parser.add_argument("--audio-key", default="executive")' in builder
    assert 'from build_demo_video import (' in builder
    assert "Football_AI_Platform_Demo.mp4" not in builder
    assert "FOOTBALL_EXECUTIVE_MATCH_VIDEO" in builder
    assert "RAW_MATCH_MP4" not in builder
    assert "TRACKING_MP4" not in builder
    assert "tests-105-passed.png" not in builder
    assert "AZ Alkmaar" not in scenes
    assert "AZ Alkmaar" not in builder
    assert "Proposed Professional Architecture" in architecture
    assert "Main Long-Side Panoramic" in architecture
    assert "Passing lane legend" in architecture
    assert "Clubhouse Security Office" in architecture


def test_review_workflow_board_explains_every_guard_and_opens_chat() -> None:
    html = REVIEW_WORKFLOW.read_text(encoding="utf-8")

    assert "@page { size: A3 landscape; margin: 0; }" in html
    assert "Review Canvas in 4 Steps" in html
    assert "Inspect the Evidence" in html
    assert "Copilot Decides Independently" in html
    assert "How Canvas, Copilot &amp; the Repository Connect" in html
    assert "current GitHub Copilot session" in html
    assert "selected segment, event, timestamp, evidence scope" in html
    assert "current branch’s rules, cached evidence, tests, and review state" in html
    assert "MATCH_LAW_PROFILE" in html
    assert "project’s analytics definitions" in html
    assert "Refuses to invent a touch, player, control state, or referee decision" in html
    assert "Inside the Rules Engine" in html
    assert "Match-State Machine — What Is Its Purpose?" in html
    assert "Possible Stoppage" in html
    assert "Restart Pending" in html
    assert "Analytics Event Machines" in html
    assert "Deterministic Output" in html
    assert "Regression Protection" in html
    assert "Play the AI Pipeline" in html
    assert 'id="pipeline-dialog"' in html
    assert "How the Frameworks Work Together" in html
    assert "Ultralytics YOLO11" in html
    assert "PyTorch" in html
    assert "Open and decode football video files" in html
    assert "Extract jersey-colour samples" in html
    assert "Apply pitch calibration and homography" in html
    assert "Draw player boxes, tracks, pitch overlays, and labels" in html
    assert "Create tracking-verification videos" in html
    assert "ByteTrack Route" in html
    assert "Possible future use:" in html
    assert "ByteTrack for local continuity plus jersey number, team, appearance, roster, and spatial evidence for durable identity" in html
    assert "Jersey recognition strengthens tracking; it does not replace tracking" in html
    assert "Number recognition is not implemented" in html
    assert "YOLO detects the player; ByteTrack links detections over time" in html
    assert "A future number detector or OCR model—not ByteTrack" in html
    assert "their ball trajectory comes from supplied labels" in html
    assert "Licensing Gate Before a Paid Pilot" in html
    assert "Commercial Sign-Off Required" in html
    assert "AGPL-3.0 / Enterprise" in html
    assert "Apache-2.0" in html
    assert "BSD-3-Clause" in html
    assert "BSD-2-Clause" in html
    assert "ByteTrack" in html and "MIT" in html
    assert "Exporting a model to ONNX does not remove its original obligations" in html
    assert "training-data provenance" in html
    assert "player privacy" in html
    assert "MATCH_LAW_PROFILE" in html
    assert "predicted-events.json" in html
    assert 'aria-live="polite"' in html
    assert "prefers-reduced-motion: reduce" in html
    assert "Pause" in html
    assert "#ai-pipeline" in html
    assert "You Make the Decision" in html
    assert "Verify the Engine" in html
    assert "No Change" in html
    assert "Change Required" in html
    assert "Keep Separate" in html
    assert "Every proposal has a decision" in html
    assert "Source and output hashes are current" in html
    assert "Protected regressions pass" in html
    assert "Event counts and matches are exact" in html
    assert 'href="../../review-canvas?theme=default"' in html
    assert 'class="skip"' in html
    assert "prefers-reduced-motion" in html
