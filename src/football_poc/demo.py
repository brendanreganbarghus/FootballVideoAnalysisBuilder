from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

import cv2


def build_demo(
    *,
    aggregate_path: Path,
    evaluation_path: Path,
    simulation_path: Path,
    events_path: Path,
    output: Path,
    video_url: str = "tracking-verification.webm",
    clip_title: str = "Primary benchmark minute",
    teams: tuple[str, str] = ("blue", "white"),
    labelled_actions: bool = True,
    ground_truth_ball: bool = False,
    manual_comparison_path: Path | None = None,
    manual_review_image_url: str | None = None,
) -> Path:
    aggregate = _load_json(aggregate_path) if labelled_actions else None
    if labelled_actions:
        _load_json(evaluation_path)
    simulation = _load_json(simulation_path)
    events = _load_json(events_path)
    manual_comparison = (
        _load_json(manual_comparison_path)
        if manual_comparison_path is not None
        else None
    )
    if not isinstance(events, list):
        raise ValueError("Demo events must be a JSON list")

    pass_metrics = aggregate["micro_average"]["pass"] if aggregate else {}
    shot_metrics = aggregate["micro_average"]["shot"] if aggregate else {}
    chunks_json = json.dumps(simulation["chunks"]).replace("</", "<\\/")
    events_json = json.dumps(events).replace("</", "<\\/")
    teams_json = json.dumps(teams).replace("</", "<\\/")
    chunk_rows = "\n".join(
        _chunk_row(chunk) for chunk in simulation["chunks"]
    )
    event_rows = "\n".join(_event_row(event) for event in events)
    timeline = "\n".join(_timeline_event(event) for event in events)
    team_cards = "\n".join(_team_card(team) for team in teams)
    detection_stage = (
        "Detector finds players; dataset labels supply the ball path"
        if ground_truth_ball
        else "Football model finds players and the tiny ball"
    )
    event_stage = (
        "Possession transfers, pass candidates and turnovers"
        if ground_truth_ball
        else "Possession transfers, passes, turnovers and shots"
    )
    limitation_text = (
        "This diagnostic isolates player/team/pass logic by using the labelled "
        "ball path. Candidate events still require manual video review."
        if ground_truth_ball
        else "Recall is limited by tiny-ball visibility; shot outcomes need "
        "behind-goal cameras and more labeled examples."
    )
    comparison_html = ""
    if manual_comparison:
        comparison_rows = "\n".join(
            _comparison_row(team, event_type, manual_comparison)
            for team in ("red", "black")
            for event_type in ("completed_pass", "turnover")
        )
        comparison_image = (
            f'<img class="comparison-image" src="{escape(manual_review_image_url)}" '
            'alt="Ball-centred manual event review crops">'
            if manual_review_image_url
            else ""
        )
        comparison_html = f"""
  <h2>Manual receiver-touch comparison</h2>
  <p><strong>{manual_comparison["matched_event_count"]} of
    {manual_comparison["manual_event_count"]}</strong> manual events matched by
    completion time, team, and event type within
    {manual_comparison["tolerance_seconds"]:.1f}s.
    <strong>{manual_comparison.get("additional_review_match_count", 0)}</strong>
    additional events are likely matches within the
    {manual_comparison.get("review_tolerance_seconds", 3.0):.1f}s manual-review
    tolerance.</p>
  <table>
    <thead><tr><th>Team</th><th>Event</th><th>Manual</th>
      <th>AI</th><th>Exact matches</th></tr></thead>
    <tbody>{comparison_rows}</tbody>
  </table>
  {comparison_image}
  <p class="muted">Red circles show the supplied ball location. “Wrong class”
    means the AI saw a nearby transfer but assigned the wrong team or event
    type; “missed” means no nearby transfer was produced.</p>
"""
    if labelled_actions:
        metric_cards = (
            _metric_card(
                "Pass precision",
                _percent(pass_metrics["precision"]),
                f'{pass_metrics["true_positives"]} correct predictions',
            )
            + _metric_card(
                "Pass recall",
                _percent(pass_metrics["recall"]),
                f'{pass_metrics["ground_truth"]} labeled passes',
            )
            + _metric_card(
                "Shot precision",
                _percent(shot_metrics["precision"]),
                "Three-window baseline",
            )
        )
        benchmark_summary = f"""<p>Across three independent one-minute windows,
    fixed thresholds produce
    <strong>{pass_metrics["true_positives"]}/{pass_metrics["predicted"]}</strong>
    correct pass predictions against {pass_metrics["ground_truth"]} labels.
    Shot results are {shot_metrics["true_positives"]}/{shot_metrics["predicted"]}
    correct predictions against {shot_metrics["ground_truth"]} labels.</p>"""
    else:
        pass_count = sum(
            event.get("event_type") == "pass_candidate" for event in events
        )
        shot_count = sum(
            event.get("event_type") == "shot_candidate" for event in events
        )
        metric_cards = (
            _metric_card("Pass candidates", str(pass_count), "Not action-labelled")
            + _metric_card("Shot candidates", str(shot_count), "Not action-labelled")
            + _metric_card("Accuracy score", "N/A", "Manual review required")
        )
        ball_note = (
            " Dataset ball coordinates are used to isolate player/team/pass logic."
            if ground_truth_ball
            else ""
        )
        benchmark_summary = (
            "<p>This clip does not include pass or shot action labels, so the "
            "candidate totals cannot be presented as accuracy results."
            f"{ball_note}</p>"
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Football Analytics POC</title>
  <style>
    :root {{ color-scheme: dark; --blue:#39a0ff; --green:#56d364;
      --orange:#ffb454; --panel:#161b22; --muted:#8b949e; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font:16px/1.5 system-ui,sans-serif;
      background:#0d1117; color:#f0f6fc; }}
    header, main {{ max-width:1200px; margin:auto; padding:28px; }}
    header {{ padding-bottom:12px; }}
    h1 {{ margin:0; font-size:2.25rem; }}
    h2 {{ margin-top:38px; }}
    .muted {{ color:var(--muted); }}
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
      gap:14px; }}
    .team-scoreboard {{ display:grid; grid-template-columns:repeat(2,minmax(260px,1fr));
      gap:14px; }}
    .team-card {{ padding:18px; background:var(--panel); border:2px solid;
      border-radius:10px; }}
    .team-card.blue {{ border-color:var(--blue); }}
    .team-card.white {{ border-color:#f0f6fc; }}
    .team-stats {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
    .team-stat strong {{ display:block; font-size:2rem; color:var(--green); }}
    .card, .stage, table {{ background:var(--panel); border:1px solid #30363d;
      border-radius:10px; }}
    .card {{ padding:18px; }}
    .metric {{ font-size:2rem; font-weight:700; color:var(--green); }}
    .pipeline {{ display:flex; gap:9px; align-items:stretch; overflow-x:auto; }}
    .stage {{ min-width:145px; padding:14px; }}
    .arrow {{ align-self:center; color:var(--blue); font-size:1.5rem; }}
    video {{ width:100%; border-radius:10px; background:#000; }}
    .comparison-image {{ width:100%; margin-top:18px; border-radius:10px;
      border:1px solid #30363d; }}
    .video-wrap {{ position:relative; }}
    .video-label {{ position:absolute; top:12px; left:12px; z-index:1;
      padding:7px 10px; border-radius:6px; background:#0d1117dd;
      border:1px solid var(--blue); font-weight:700; pointer-events:none; }}
    table {{ width:100%; border-collapse:collapse; overflow:hidden; }}
    th, td {{ padding:9px 12px; border-bottom:1px solid #30363d; text-align:left; }}
    th {{ color:var(--muted); }}
    .timeline {{ position:relative; height:88px; background:var(--panel);
      border:1px solid #30363d; border-radius:10px; }}
    .event {{ position:absolute; top:16px; width:8px; height:55px;
      background:var(--blue); border-radius:4px; }}
    .event.shot_candidate {{ background:var(--orange); }}
    .event.turnover_candidate {{ background:#d2a8ff; }}
    tr.processed {{ background:#132a1a; }}
    .live-status {{ padding:12px 0; color:var(--muted); }}
    progress {{ width:100%; height:12px; accent-color:var(--green); }}
    code {{ color:#a5d6ff; }}
    @media (max-width:650px) {{
      .team-scoreboard {{ grid-template-columns:1fr; }}
    }}
  </style>
</head>
<body>
<header>
  <h1>AI Football Analytics POC</h1>
  <p class="muted">Fixed panoramic video to incremental amateur-club statistics</p>
</header>
<main>
  <section class="cards">
    {metric_cards}
    {_metric_card("Chunk replay", "PASS",
                  f'{simulation["validation"]["duplicates_suppressed"]} duplicates suppressed')}
  </section>

  <h2>How the algorithm fits together</h2>
  <section class="pipeline">
    {_stage("1. Ingest", "Timestamped panoramic chunks with overlap")}
    <div class="arrow">-&gt;</div>
    {_stage("2. Tiled detection", detection_stage)}
    <div class="arrow">-&gt;</div>
    {_stage("3. Tracking", "Link identities and interpolate short ball gaps")}
    <div class="arrow">-&gt;</div>
    {_stage("4. Teams", f"Classify {teams[0]}, {teams[1]} and officials")}
    <div class="arrow">-&gt;</div>
    {_stage("5. Events", event_stage)}
    <div class="arrow">-&gt;</div>
    {_stage("6. Report", "Provisional chunk stats and final reviewed totals")}
  </section>

  <h2>Annotated benchmark</h2>
  <div class="video-wrap">
    <div class="video-label">{escape(clip_title)}</div>
    <video id="demo-video" controls preload="metadata"
      src="{escape(video_url)}"></video>
  </div>
  <div id="video-status" class="live-status">Loading annotated video...</div>

  <h2>Live detected-event replay</h2>
  <section class="cards">
    {_metric_card("Processed chunk", "0", "Updates during playback", value_id="live-chunk")}
    {_metric_card("Detected events", "0", "Synchronized to video", value_id="live-events")}
  </section>
  <section class="team-scoreboard">
    {team_cards}
  </section>
  <div id="live-status" class="live-status">Press play to begin chunk replay.</div>
  <progress id="live-progress" max="60" value="0"></progress>

  <h2>Incremental event timeline</h2>
  <div class="timeline">{timeline}</div>
  <p class="muted">Timeline colours: blue pass, orange shot, purple turnover. Scale: 60 seconds.</p>

  <h2>Live-style chunk replay</h2>
  <table>
    <thead><tr><th>Chunk</th><th>Range</th><th>New</th><th>Duplicates</th>
      <th>Provisional total</th><th>Queue wait</th></tr></thead>
    <tbody>{chunk_rows}</tbody>
  </table>

  <h2>Detected events in the demo window</h2>
  <table>
    <thead><tr><th>Time</th><th>Type</th><th>Team</th>
      <th>Confidence</th></tr></thead>
    <tbody>{event_rows}</tbody>
  </table>

  <h2>What the benchmark currently says</h2>
  {benchmark_summary}
  <p class="muted">This is a precision-first technical POC. It is not a
    production accuracy claim. {limitation_text}</p>
  {comparison_html}

  <h2>Demo runbook</h2>
  <ol>
    <li>Show the original panoramic camera view and explain fixed-camera input.</li>
    <li>Play the annotated video to show player teams and ball trajectory.</li>
    <li>Walk left-to-right through the six pipeline stages.</li>
    <li>Show provisional totals changing after each overlapping chunk.</li>
    <li>Finish with measured results, limitations, and the four-camera roadmap.</li>
  </ol>
</main>
<script>
  const chunks = {chunks_json};
  const events = {events_json};
  const teams = {teams_json};
  const video = document.getElementById("demo-video");
  const progress = document.getElementById("live-progress");
  const status = document.getElementById("live-status");
  const videoStatus = document.getElementById("video-status");
  const value = (id, number) => document.getElementById(id).textContent = number;

  function updateLiveStats(seconds) {{
    progress.value = Math.min(60, seconds);
    const replayed = events.filter(event => event.clip_seconds <= seconds + 0.05);
    const completed = chunks.filter(chunk => chunk.end_seconds <= seconds + 0.05);
    const latest = completed.length ? completed[completed.length - 1] : null;
    value("live-chunk", latest ? latest.index + 1 : 0);
    value("live-events", replayed.length);
    for (const team of teams) {{
      const teamEvents = replayed.filter(event => event.team === team);
      value(`live-${{team}}-passes`,
        teamEvents.filter(event => event.event_type === "pass_candidate").length);
      value(`live-${{team}}-shots`,
        teamEvents.filter(event => event.event_type === "shot_candidate").length);
      value(`live-${{team}}-turnovers`,
        teamEvents.filter(event => event.event_type === "turnover_candidate").length);
    }}
    document.querySelectorAll("tr[data-chunk]").forEach(row => {{
      row.classList.toggle(
        "processed",
        latest !== null && Number(row.dataset.chunk) <= latest.index
      );
    }});
    const eventMessage = `${{replayed.length}} detected event(s) through ` +
      `${{seconds.toFixed(1)}}s. `;
    status.textContent = latest
      ? eventMessage + `Chunk ${{latest.index + 1}} published through ` +
        `${{latest.end_seconds.toFixed(0)}}s; ` +
        `${{latest.duplicates_suppressed}} overlap duplicate(s) suppressed.`
      : eventMessage + `The first chunk publishes at ` +
        `${{chunks[0].end_seconds.toFixed(0)}}s.`;
  }}

  ["loadedmetadata", "timeupdate", "seeked", "ended"].forEach(name =>
    video.addEventListener(name, () => updateLiveStats(video.currentTime))
  );
  video.addEventListener("loadedmetadata", () => {{
    videoStatus.textContent = "Video ready. Press play to run the chunk replay.";
  }});
  video.addEventListener("playing", () => {{
    videoStatus.textContent = "Annotated benchmark playing.";
  }});
  video.addEventListener("error", () => {{
    const code = video.error ? video.error.code : "unknown";
    videoStatus.textContent = `Video could not be loaded (media error ${{code}}).`;
  }});
  updateLiveStats(0);
</script>
</body>
</html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output


def prepare_demo_video(
    *,
    source: Path,
    output: Path,
    maximum_width: int = 1920,
) -> Path:
    if not source.is_file():
        raise FileNotFoundError(f"Demo video input does not exist: {source}")
    if (
        output.is_file()
        and output.stat().st_mtime_ns >= source.stat().st_mtime_ns
    ):
        return output

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open demo video input: {source}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if width <= 0 or height <= 0 or fps <= 0:
        capture.release()
        raise RuntimeError(f"Demo video has invalid metadata: {source}")

    scale = min(1.0, maximum_width / width)
    output_width = max(2, int(width * scale) // 2 * 2)
    output_height = max(2, int(height * scale) // 2 * 2)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f"{output.stem}.partial{output.suffix}")
    writer = cv2.VideoWriter(
        str(temporary),
        cv2.VideoWriter_fourcc(*"VP80"),
        fps,
        (output_width, output_height),
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError("OpenCV could not initialize the VP8/WebM writer")

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if (output_width, output_height) != (width, height):
                frame = cv2.resize(
                    frame,
                    (output_width, output_height),
                    interpolation=cv2.INTER_AREA,
                )
            writer.write(frame)
    finally:
        writer.release()
        capture.release()

    if not temporary.is_file() or temporary.stat().st_size == 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("VP8/WebM demo video encoding produced no output")
    temporary.replace(output)
    return output


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Demo input does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _percent(value: float) -> str:
    return f"{float(value) * 100:.1f}%"


def _metric_card(
    title: str,
    value: str,
    detail: str,
    *,
    value_id: str | None = None,
) -> str:
    id_attribute = f' id="{escape(value_id)}"' if value_id else ""
    return (
        f'<article class="card"><div class="muted">{escape(title)}</div>'
        f'<div class="metric"{id_attribute}>{escape(value)}</div>'
        f'<div>{escape(detail)}</div></article>'
    )


def _team_stat(title: str, value_id: str) -> str:
    return (
        '<div class="team-stat">'
        f'<strong id="{escape(value_id)}">0</strong>'
        f'<span>{escape(title)}</span></div>'
    )


def _team_card(team: str) -> str:
    border = {
        "blue": "#39a0ff",
        "white": "#f0f6fc",
        "red": "#ff4d4d",
        "black": "#6e7681",
    }.get(team, "#56d364")
    team_id = "".join(character for character in team.lower() if character.isalnum())
    return (
        f'<article class="team-card" style="border-color:{border}">'
        f"<h3>{escape(team.title())} team</h3>"
        '<div class="team-stats">'
        f'{_team_stat("Completed pass candidates", f"live-{team_id}-passes")}'
        f'{_team_stat("Shot candidates", f"live-{team_id}-shots")}'
        f'{_team_stat("Turnovers lost", f"live-{team_id}-turnovers")}'
        "</div></article>"
    )


def _comparison_row(
    team: str, event_type: str, comparison: dict[str, Any]
) -> str:
    label = "Completed pass" if event_type == "completed_pass" else "Turnover"
    return (
        f"<tr><td>{escape(team.title())}</td><td>{label}</td>"
        f'<td>{comparison["manual_counts"][team][event_type]}</td>'
        f'<td>{comparison["predicted_counts"][team][event_type]}</td>'
        f'<td>{comparison["matched_counts"][team][event_type]}</td></tr>'
    )


def _stage(title: str, detail: str) -> str:
    return (
        f'<article class="stage"><strong>{escape(title)}</strong>'
        f'<div class="muted">{escape(detail)}</div></article>'
    )


def _chunk_row(chunk: dict[str, Any]) -> str:
    state = chunk["state_out"]
    return (
        f'<tr data-chunk="{chunk["index"]}"><td>{chunk["index"] + 1}</td>'
        f"<td>{chunk['start_seconds']:.0f}-{chunk['end_seconds']:.0f}s</td>"
        f"<td>{chunk['new_events']}</td>"
        f"<td>{chunk['duplicates_suppressed']}</td>"
        f"<td>{state['accepted_event_count']}</td>"
        f"<td>{chunk['queue_wait_seconds']:.1f}s</td></tr>"
    )


def _event_row(event: dict[str, Any]) -> str:
    return (
        f"<tr><td>{float(event['clip_seconds']):.2f}s</td>"
        f"<td>{escape(str(event['event_type']))}</td>"
        f"<td>{escape(str(event.get('team') or '-'))}</td>"
        f"<td>{float(event.get('confidence', 0)):.2f}</td></tr>"
    )


def _timeline_event(event: dict[str, Any]) -> str:
    left = max(0.0, min(100.0, float(event["clip_seconds"]) / 60 * 100))
    event_type = escape(str(event["event_type"]))
    return (
        f'<span class="event {event_type}" style="left:{left:.2f}%" '
        f'title="{event_type} at {float(event["clip_seconds"]):.2f}s"></span>'
    )
