"""Build the separate four-minute executive football intelligence pitch.

The existing technical demo remains unchanged. This cut combines real match
and review evidence with clearly labelled proposed-architecture visuals.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont

from build_demo_video import (
    BUILD,
    DEMO_DIR,
    FFMPEG,
    FONT_BOLD,
    FONT_REG,
    H,
    SHOTS,
    W,
    ImageShot,
    Scene,
    VideoShot,
    build_scene_video,
    concat_copy,
    fade_video,
    ffprobe_duration,
    make_title_card,
    normalize_wav,
    run,
    silence_wav,
)

SCRIPT_DIR = Path(__file__).resolve().parent
SCENES_PATH = SCRIPT_DIR / "executive_scenes.json"
CARDS = BUILD / "executive_cards"
DEFAULT_SRT = DEMO_DIR / "Football_AI_Executive_Pitch.srt"
DEFAULT_OUTPUT = DEMO_DIR / "Football_AI_Executive_Pitch_4min.mp4"
LICENSED_MATCH_ENV = "FOOTBALL_EXECUTIVE_MATCH_VIDEO"

INK = (248, 247, 251)
MUTED = (200, 193, 216)
PANEL = (25, 18, 48)
PURPLE = (125, 60, 255)
MINT = (84, 240, 194)
AMBER = (255, 201, 93)
BG = (9, 6, 20)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    width: int,
    text_font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    spacing: int = 10,
) -> int:
    avg_char = max(1, int(width / (text_font.size * 0.54)))
    lines = wrap(text, width=avg_char)
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=text_font, fill=fill)
        y += text_font.size + spacing
    return y


def make_columns_card(
    path: Path,
    eyebrow: str,
    title: str,
    columns: list[tuple[str, list[str], str]],
    footer: str,
) -> None:
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((70, 64, W - 70, H - 64), radius=34, fill=(15, 10, 31), outline=(65, 51, 91), width=2)
    draw.text((116, 104), eyebrow.upper(), font=font(FONT_BOLD, 24), fill=MINT)
    draw.text((116, 150), title, font=font(FONT_BOLD, 54), fill=INK)

    gap = 24
    left = 116
    top = 262
    card_width = int((W - 232 - gap * (len(columns) - 1)) / len(columns))
    for index, (heading, items, accent_name) in enumerate(columns):
        accent = {"mint": MINT, "amber": AMBER, "purple": PURPLE}[accent_name]
        x = left + index * (card_width + gap)
        draw.rounded_rectangle((x, top, x + card_width, 750), radius=22, fill=PANEL, outline=accent, width=3)
        draw.text((x + 28, top + 30), heading, font=font(FONT_BOLD, 30), fill=accent)
        y = top + 92
        for item in items:
            draw.ellipse((x + 30, y + 8, x + 40, y + 18), fill=accent)
            y = draw_wrapped(draw, item, (x + 58, y), card_width - 88, font(FONT_REG, 23), MUTED, 7) + 22

    draw.rounded_rectangle((116, 782, W - 116, 872), radius=18, fill=(23, 15, 43), outline=(67, 51, 97), width=2)
    draw_wrapped(draw, footer, (148, 805), W - 296, font(FONT_BOLD, 24), INK, 6)
    image.save(path)


def create_cards() -> dict[str, Path]:
    CARDS.mkdir(parents=True, exist_ok=True)
    review_source = SHOTS / "soccertrack-review-provisional.png"
    if not review_source.exists():
        raise RuntimeError(f"Missing SoccerTrack Review capture: {review_source}")
    review = CARDS / "soccertrack-review-provisional.png"
    review_image = Image.open(review_source).convert("RGB")
    review_draw = ImageDraw.Draw(review_image)
    review_draw.rounded_rectangle(
        (20, 18, 1430, 112),
        radius=18,
        fill=(26, 18, 9),
        outline=AMBER,
        width=3,
    )
    review_draw.text(
        (46, 34),
        "WORKFLOW PREVIEW - C#/E# ALIGNMENT IS PROVISIONAL",
        font=font(FONT_BOLD, 28),
        fill=AMBER,
    )
    review_draw.text(
        (46, 72),
        "Not independently validated. Agreement is not proof of football correctness.",
        font=font(FONT_REG, 21),
        fill=INK,
    )
    review_image.save(review)

    landscape = CARDS / "market-landscape.png"
    make_columns_card(
        landscape,
        "The current market",
        "Useful Components. A Fragmented Decision Workflow.",
        [
            ("Accessible capture", ["Record, upload, stream and review", "Commonly tied to recurring cloud plans"], "mint"),
            ("Professional services", ["Tracking, event data and analyst workflows", "Usually sold through bespoke contracts"], "purple"),
            ("The remaining gap", ["Separate capture, analysis and verification", "Cost grows as services are added", "Insight may arrive after the decision"], "amber"),
        ],
        "The opportunity is one locally controlled, traceable flow from footage to timely football evidence.",
    )

    market = CARDS / "connected-flow.png"
    make_columns_card(
        market,
        "One connected workflow",
        "From the Match to Evidence the Coach Can Use",
        [
            ("1. Capture", ["Stable panoramic match footage", "Calibrated pitch and player observations"], "mint"),
            ("2. Understand", ["Law-grounded match state", "Pass, possession, turnover and shot evidence"], "purple"),
            ("3. Deliver", ["Relevant in-match statistics", "Expanded half-time coaching view"], "amber"),
        ],
        "Every published statistic remains traceable to video evidence and the rules-engine version that produced it.",
    )

    cost = CARDS / "pilot-configurations.png"
    make_columns_card(
        cost,
        "Grassroots affordability",
        "Professional-Standard Evidence Without Professional-Scale Cost",
        [
            ("Installed core", ["One panoramic main camera", "Local GPU, storage and networking", "Target: below EUR 12,000 before tax"], "mint"),
            ("Control ongoing cost", ["No mandatory cloud processing", "No mandatory cloud video storage", "Choose support around club needs"], "purple"),
            ("Scale when valuable", ["Second panoramic and goal views optional", "Professional resilience scoped separately", "Compare complete three-year cost"], "amber"),
        ],
        "Planning target, not a quotation. Site conditions, connectivity, ongoing support and optional expansion remain separate.",
    )

    outputs = CARDS / "decision-ready-outputs.png"
    make_columns_card(
        outputs,
        "Decision-ready outputs",
        "The Evidence Expands When the Coaching Conversation Does",
        [
            ("During play", ["Current match totals", "Possession and zone indicators", "Relevant one-minute updates"], "mint"),
            ("At half-time", ["Possession won and lost by zone", "Passes, turnovers and shots", "Final-third entries and trends"], "purple"),
            ("Coach in control", ["Evidence supports the discussion", "No automatic tactical instruction", "The coaching team decides the response"], "amber"),
        ],
        "The same traceable evidence supports both the in-match view and the deeper half-time discussion.",
    )

    roadmap = CARDS / "pilot-roadmap.png"
    make_columns_card(
        roadmap,
        "Professional Football + Xebia",
        "A Staged Co-Development Pilot",
        [
            ("1. Define", ["Select decision-relevant statistics", "Agree evidence, accuracy and latency targets"], "mint"),
            ("2. Validate", ["Run controlled matches", "Measure every statistic independently", "Protect accepted behaviour"], "purple"),
            ("3. Productionise", ["Edge GPU and resilient live ingest", "Security, integration and monitoring", "Operational support at venue scale"], "amber"),
        ],
        "Trusted football intelligence while the next decision can still change the match.",
    )

    maturity = CARDS / "maturity-and-scale.png"
    make_columns_card(
        maturity,
        "Honest maturity",
        "Working Proof Today. Controlled Scale Next.",
        [
            ("Current proof", ["Offline prepared video", "Calibration and tracking", "Football state and focused event review"], "mint"),
            ("Next-stage delivery", ["Live ingest and resilient processing", "Stadium, dressing-room and dugout views", "Professional multi-camera operation"], "purple"),
            ("Future camera queries", ["Main panoramic camera remains continuous", "Query only a relevant secondary view", "Short low-confidence moment only"], "amber"),
        ],
        "Pilot target: at least 95%, measured separately for each agreed statistic against independently reviewed references.",
    )

    validation = CARDS / "validation-loop.png"
    make_columns_card(
        validation,
        "Continuous validation",
        "The Review Application Strengthens the Rules Engine",
        [
            ("Human validators", ["Inspect controlled video segments", "Judge whether available evidence supports an event"], "mint"),
            ("Copilot assistance", ["Apply football-law and analytics knowledge", "Explain evidence; never approve its own proposal"], "purple"),
            ("Reusable engine", ["Improve general rules, never one timestamp", "Run protected regressions before deployment"], "amber"),
        ],
        "The validated rules-engine version is deployed to the local GPU; manual review labels never become inference inputs.",
    )
    return {
        "market": market,
        "landscape": landscape,
        "cost": cost,
        "outputs": outputs,
        "review": review,
        "roadmap": roadmap,
        "maturity": maturity,
        "validation": validation,
    }


def split_duration(total: float, weights: list[float]) -> list[float]:
    weight_total = sum(weights)
    durations = [total * weight / weight_total for weight in weights]
    durations[-1] = total - sum(durations[:-1])
    return durations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Reuse existing completed scene clips; useful when rebuilding selected missing scenes.",
    )
    parser.add_argument("--audio-key", default="executive")
    parser.add_argument("--srt", type=Path, default=DEFAULT_SRT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    audio_dir = BUILD / "audio" / args.audio_key
    work = BUILD / "work" / args.audio_key
    licensed_match = Path(os.environ.get(LICENSED_MATCH_ENV, ""))
    if not licensed_match.is_file():
        raise RuntimeError(
            f"Set {LICENSED_MATCH_ENV} to an owned or commercially licensed "
            "football video before building the executive pitch."
        )
    tracking_video = (
        licensed_match.parent
        / "analytics-data"
        / "tracking-verification.mp4"
    )
    if not tracking_video.is_file():
        raise RuntimeError(
            "Missing SoccerTrack tracking verification video beside the "
            "licensed match clip."
        )
    scenes_json = json.loads(SCENES_PATH.read_text(encoding="utf-8"))
    titles = {scene["id"]: scene["title"] for scene in scenes_json}
    cards = create_cards()
    work.mkdir(parents=True, exist_ok=True)

    def audio(scene_id: int) -> Path:
        return audio_dir / f"scene{scene_id:02d}.wav"

    missing = [str(audio(scene["id"])) for scene in scenes_json if not audio(scene["id"]).exists()]
    if missing:
        raise RuntimeError(f"Missing executive narration audio: {', '.join(missing)}")

    architecture = SHOTS / "executive-architecture.png"
    if not architecture.exists():
        raise RuntimeError(f"Missing approved architecture capture: {architecture}")

    scenes: list[Scene] = []

    d1 = ffprobe_duration(audio(1))
    p1 = split_duration(d1, [0.7, 0.3])
    scenes.append(Scene(1, titles[1], audio(1), [
        VideoShot(licensed_match, duration=p1[0], start=4.0),
        ImageShot(cards["market"], duration=p1[1]),
    ]))

    d2 = ffprobe_duration(audio(2))
    p2 = split_duration(d2, [0.42, 0.58])
    scenes.append(Scene(2, titles[2], audio(2), [
        VideoShot(licensed_match, duration=p2[0], start=23.0),
        ImageShot(cards["landscape"], duration=p2[1]),
    ]))

    d3 = ffprobe_duration(audio(3))
    p3 = split_duration(d3, [0.55, 0.45])
    scenes.append(Scene(3, titles[3], audio(3), [
        VideoShot(tracking_video, duration=p3[0], start=3.0),
        ImageShot(cards["market"], duration=p3[1]),
    ]))

    scenes.append(Scene(4, titles[4], audio(4), [
        ImageShot(architecture, duration=ffprobe_duration(audio(4))),
    ]))

    scenes.append(Scene(5, titles[5], audio(5), [
        ImageShot(cards["maturity"], duration=ffprobe_duration(audio(5))),
    ]))

    scenes.append(Scene(6, titles[6], audio(6), [
        ImageShot(architecture, duration=ffprobe_duration(audio(6))),
    ]))

    d7 = ffprobe_duration(audio(7))
    p7 = split_duration(d7, [0.58, 0.42])
    scenes.append(Scene(7, titles[7], audio(7), [
        ImageShot(cards["review"], duration=p7[0]),
        ImageShot(cards["validation"], duration=p7[1]),
    ]))

    scenes.append(Scene(8, titles[8], audio(8), [
        ImageShot(cards["cost"], duration=ffprobe_duration(audio(8))),
    ]))

    scenes.append(Scene(9, titles[9], audio(9), [
        ImageShot(architecture, duration=ffprobe_duration(audio(9))),
    ]))

    scenes.append(Scene(10, titles[10], audio(10), [
        ImageShot(cards["roadmap"], duration=ffprobe_duration(audio(10))),
    ]))

    scene_results = []
    for scene in scenes:
        existing = work / f"scene{scene.id:02d}" / "faded.mp4"
        if args.reuse_existing and existing.exists():
            scene_results.append((existing, ffprobe_duration(scene.audio)))
            continue
        scene_results.append(build_scene_video(scene, work))

    title_video = work / "title_faded.mp4"
    make_title_card(
        [("Football Intelligence Platform", 58, INK), ("See the Match While You Can Still Change It", 34, MINT)],
        duration=4.0,
        out_path=work / "title_card.mp4",
        subtitle="Executive concept video - current proof and proposed future architecture",
    )
    fade_video(work / "title_card.mp4", title_video, 4.0, fade_in=True, fade_out=True)
    title_silence = work / "title_silence.wav"
    silence_wav(4.0, title_silence)

    closing_video = work / "closing_faded.mp4"
    make_title_card(
        [
            ("Trusted Football Intelligence", 52, INK),
            ("Professional Football + Xebia", 38, (88, 166, 255)),
            ("A staged co-development pilot", 30, MINT),
            (
                "SoccerTrack v2 footage: Scott, Uchida, Kuroda, Kim & Fujii (2025)",
                20,
                MUTED,
            ),
            (
                "CC BY 4.0 - arxiv.org/abs/2508.01802 - excerpts and overlays modified",
                18,
                MUTED,
            ),
        ],
        duration=6.0,
        out_path=work / "closing_card.mp4",
        subtitle="creativecommons.org/licenses/by/4.0",
    )
    fade_video(work / "closing_card.mp4", closing_video, 6.0, fade_in=True, fade_out=True)
    closing_silence = work / "closing_silence.wav"
    silence_wav(6.0, closing_silence)

    video_full = work / "video_full.mp4"
    concat_copy([title_video] + [video for video, _ in scene_results] + [closing_video], video_full)

    normalized_audio: list[Path] = []
    for scene in scenes:
        normalized = work / f"scene{scene.id:02d}_audio_norm.wav"
        normalize_wav(scene.audio, normalized)
        normalized_audio.append(normalized)
    audio_full = work / "audio_full.wav"
    concat_copy([title_silence] + normalized_audio + [closing_silence], audio_full)

    muxed = work / "muxed_final.mp4"
    run([
        FFMPEG, "-y", "-i", str(video_full), "-i", str(audio_full),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-shortest", str(muxed),
    ])

    if not args.srt.exists():
        raise RuntimeError(f"Missing executive captions: {args.srt}")
    srt_escaped = str(args.srt).replace("\\", "/").replace(":", "\\:")
    style = (
        "FontName=Segoe UI,FontSize=13,PrimaryColour=&H00F0F6FC,"
        "OutlineColour=&H00161B22,BackColour=&H90000000,BorderStyle=4,"
        "Outline=0,Shadow=0,MarginV=40,Alignment=2"
    )
    run([
        FFMPEG, "-y", "-i", str(muxed),
        "-vf", f"subtitles='{srt_escaped}':force_style='{style}'",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-c:a", "copy", str(args.output),
    ])
    print(f"\nFINAL EXECUTIVE VIDEO: {args.output}")
    print(f"Total duration: {ffprobe_duration(args.output):.2f}s")


if __name__ == "__main__":
    main()
