export function renderHtml({ theme = "grassroots" } = {}) {
  const appTheme = "grassroots";
  const themeColor = "#080d14";
  const homeUrl = "http://127.0.0.1:8080/";
  const homeLabel = "Back to Product Home";
  return `<!doctype html>
<html lang="en" data-app-theme="${appTheme}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="${themeColor}">
  <title>Live Football Event Review</title>
  <style>
    :root { color-scheme: dark; }
    html[data-app-theme="grassroots"] {
      --background-color-default: #080d14;
      --background-color-subtle: #101923;
      --background-color-muted: #162536;
      --border-color-default: #2b4a68;
      --border-color-muted: #3a6287;
      --panel-background: #0b141f;
      --panel-border: #315f86;
      --nested-panel-background: #08111b;
      --nested-panel-border: #497ca6;
      --text-color-default: #eef6ff;
      --text-color-muted: #adbecd;
      --true-color-green: #68e0aa;
      --true-color-blue: #78bfff;
      --color-focus-outline: #78bfff;
    }
    * { box-sizing: border-box; }
    [hidden] { display: none !important; }
    body {
      margin: 0;
      background: var(--background-color-default, #0d1117);
      color: var(--text-color-default, #f0f6fc);
      font-family: var(--font-sans, "Segoe UI", sans-serif);
      font-size: var(--text-body-medium, 14px);
      line-height: var(--leading-body-medium, 20px);
    }
    html[data-app-theme="grassroots"] body {
      background:
        radial-gradient(circle at 8% 8%, rgb(120 191 255 / 14%), transparent 30rem),
        radial-gradient(circle at 90% 88%, rgb(91 141 239 / 11%), transparent 32rem),
        linear-gradient(145deg, #101a27, #05080d 72%);
    }
    html[data-app-theme="grassroots"] .innovation-brand {
      display: inline-flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
      color: #78bfff;
    }
    .component-version {
      border: 1px solid rgb(120 191 255 / 42%);
      border-radius: 999px;
      padding: 3px 7px;
      color: var(--text-color-default, #f0f6fc);
      background: rgb(120 191 255 / 10%);
      font-family: var(--font-mono, Consolas, monospace);
      font-size: 10px;
      letter-spacing: .02em;
      text-transform: none;
    }
    button, textarea, input, select { font: inherit; }
    button {
      min-height: 40px;
      cursor: pointer;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 8px;
      padding: 8px 12px;
      background: var(--background-color-muted, #21262d);
      color: inherit;
      touch-action: manipulation;
    }
    button:hover { border-color: var(--text-color-muted, #8b949e); }
    button:focus-visible, textarea:focus-visible, input:focus-visible,
    select:focus-visible {
      outline: 3px solid var(--color-focus-outline, #58a6ff);
      outline-offset: 2px;
    }
    button:disabled { cursor: not-allowed; opacity: .55; }
    header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      padding: 14px 18px;
      border-bottom: 1px solid var(--border-color-default, #30363d);
    }
    .header-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: flex-end;
    }
    .review-mode-field {
      display: grid;
      gap: 3px;
      color: var(--text-color-muted, #8b949e);
      font-size: 11px;
      font-weight: var(--font-weight-semibold, 600);
    }
    .review-mode-field select {
      min-height: 40px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 8px;
      padding: 7px 30px 7px 10px;
      background: var(--background-color-muted, #21262d);
      color: var(--text-color-default, #f0f6fc);
    }
    .home-link {
      display: inline-flex;
      min-height: 40px;
      align-items: center;
      padding: 8px 12px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 8px;
      color: var(--text-color-default, #f0f6fc);
      background: var(--background-color-muted, #21262d);
      font-weight: 600;
      text-decoration: none;
      touch-action: manipulation;
    }
    .home-link:hover { border-color: var(--text-color-muted, #8b949e); }
    .home-link:focus-visible {
      outline: 3px solid var(--color-focus-outline, #58a6ff);
      outline-offset: 2px;
    }
    h1, h2, h3 { margin: 0; text-wrap: balance; }
    h1 { font-size: var(--text-title-medium, 20px); }
    h2 { font-size: var(--text-title-small, 16px); }
    h3 { font-size: var(--text-body-medium, 14px); }
    p { text-wrap: pretty; }
    .muted { color: var(--text-color-muted, #8b949e); }
    .scope {
      padding: 5px 9px;
      border: 1px solid var(--true-color-blue, #58a6ff);
      border-radius: 999px;
      color: var(--true-color-blue, #79c0ff);
      font-size: 12px;
      font-weight: var(--font-weight-semibold, 600);
      white-space: nowrap;
    }
    .innovation-brand {
      display: none;
      margin-top: 5px;
      color: #f0b7e6;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: .14em;
      text-transform: uppercase;
    }
    .activity {
      display: flex;
      gap: 9px;
      align-items: center;
      margin: 0;
      padding: 9px 18px;
      border-bottom: 1px solid var(--border-color-default, #30363d);
      background: var(--background-color-subtle, #161b22);
    }
    .activity-dot {
      width: 9px;
      height: 9px;
      flex: 0 0 auto;
      border-radius: 50%;
      background: var(--true-color-green, #3fb950);
    }
    .activity.working .activity-dot {
      width: 16px;
      height: 16px;
      background:
        radial-gradient(circle at 34% 28%, #fff4ad 0 10%, transparent 11%),
        radial-gradient(circle at 50% 50%, #f2cc60 0 55%, #b88700 100%);
      box-shadow: 0 0 0 1px #6e5600, 0 0 12px rgb(242 204 96 / 55%);
      animation: pulse 1.2s ease-in-out infinite;
    }
    .activity.working .activity-dot::after {
      content: "";
      display: block;
      width: 5px;
      height: 5px;
      margin: 5px;
      border-radius: 45%;
      background: #6e5600;
    }
    .activity.waiting .activity-dot {
      background: var(--true-color-blue, #58a6ff);
    }
    .activity.error .activity-dot {
      background: var(--true-color-red, #ff7b72);
    }
    .activity strong { margin-right: 4px; }
    .activity.coordinates-review {
      padding-block: 14px;
      border-bottom: 2px solid #d29922;
      background: rgb(187 128 9 / 20%);
      box-shadow: inset 0 -1px 0 rgb(242 204 96 / 25%);
    }
    .activity.coordinates-review .activity-dot {
      width: 14px;
      height: 14px;
      background: #f2cc60;
      box-shadow: 0 0 0 4px rgb(242 204 96 / 14%);
    }
    .activity.coordinates-review strong {
      color: #f2cc60;
      font-size: 18px;
      font-weight: 800;
      letter-spacing: 0.01em;
    }
    @keyframes pulse {
      50% { opacity: .35; transform: scale(.8); }
    }
    .layout {
      min-height: calc(100vh - 70px);
    }
    .review {
      display: flex;
      flex-direction: column;
      gap: 20px;
      width: 100%;
      max-width: 1800px;
      margin: 0 auto;
      min-width: 0;
      padding: 14px;
    }
    .review > .segment-builder,
    .review > .segment-picker,
    .review > .missing-event,
    .review > .event-nav,
    .review > .world-rules,
    .review > .match-replay {
      margin: 0;
    }
    .review-workspace {
      display: grid;
      grid-template-columns: minmax(0, 1.65fr) minmax(340px, .85fr);
      gap: 18px;
      align-items: start;
    }
    .media-column, .event-rail {
      display: flex;
      min-width: 0;
      flex-direction: column;
      gap: 14px;
    }
    .event-rail {
      position: sticky;
      top: 12px;
      max-height: calc(100vh - 24px);
      overflow-y: auto;
      overscroll-behavior: contain;
      scrollbar-gutter: stable;
    }
    body.trajectory-audit-mode #segment-builder-panel,
    body.trajectory-audit-mode #camera-import-panel,
    body.trajectory-audit-mode #geometry-panel,
    body.trajectory-audit-mode .segment-picker,
    body.trajectory-audit-mode .shared-review-card,
    body.trajectory-audit-mode .event-rail,
    body.trajectory-audit-mode #clip-conversation-panel,
    body.trajectory-audit-mode .world-rules,
    body.trajectory-audit-mode .match-replay,
    body.trajectory-audit-mode .live-stats-overlay,
    body.trajectory-audit-mode .fullscreen-events,
    body.trajectory-audit-mode .compact-engine-rail {
      display: none;
    }
    body.trajectory-audit-mode #video-shell,
    body.trajectory-audit-mode .view-modes,
    body.trajectory-audit-mode .transport {
      display: none;
    }
    body.trajectory-audit-mode .review-workspace {
      grid-template-columns: minmax(0, 1fr);
    }
    body.trajectory-audit-mode #ball-frame-review {
      display: block;
    }
    .segment-picker {
      display: grid;
      grid-template-columns: minmax(180px, 0.55fr) minmax(0, 1fr) auto;
      gap: 10px;
      align-items: end;
      padding: 12px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 12px;
      background: var(--background-color-subtle, #161b22);
    }
    .segment-builder {
      padding: 12px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 12px;
      background: var(--background-color-subtle, #161b22);
    }
    .segment-builder summary {
      cursor: pointer;
      list-style-position: outside;
    }
    .segment-builder summary {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
    }
    .segment-builder summary h2 { margin: 0; }
    .segment-builder-body { margin-top: 12px; }
    .segment-builder-grid {
      display: grid;
      grid-template-columns: minmax(100px, .7fr) minmax(100px, .7fr)
        minmax(130px, 1fr) auto auto;
      gap: 8px;
      align-items: end;
    }
    .segment-builder label, .fixed-duration {
      display: grid;
      gap: 4px;
      color: var(--text-color-muted, #8b949e);
      font-size: 12px;
    }
    .segment-builder input, .fixed-duration output {
      min-height: 40px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 8px;
      padding: 8px 10px;
      background: var(--background-color-default, #0d1117);
      color: var(--text-color-default, #f0f6fc);
    }
    .segment-run-status { margin: 9px 0 0; }
    .segment-progress {
      width: 100%;
      height: 6px;
      margin-top: 9px;
    }
    .camera-import-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(150px, 1fr));
      gap: 8px;
      align-items: end;
    }
    .camera-import-grid label {
      display: grid;
      gap: 4px;
      color: var(--text-color-muted, #8b949e);
      font-size: 12px;
    }
    .video-empty {
      position: absolute;
      inset: 0;
      z-index: 4;
      display: grid;
      place-content: center;
      padding: 32px;
      text-align: center;
      color: var(--text-color-muted, #8b949e);
      background: var(--background-color-default, #0d1117);
    }
    .video-empty[hidden] { display: none; }
    .segment-picker label {
      display: grid;
      gap: 5px;
      color: var(--text-color-muted, #8b949e);
      font-size: 12px;
    }
    .segment-picker select {
      width: 100%;
      min-height: 40px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 8px;
      padding: 7px 10px;
      background: var(--background-color-muted, #21262d);
      color: var(--text-color-default, #f0f6fc);
    }
    .segment-status {
      min-width: 92px;
      padding: 9px 12px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 999px;
      text-align: center;
      font-weight: var(--font-weight-semibold, 600);
    }
    .segment-status.passed {
      border-color: var(--true-color-green, #238636);
      color: var(--true-color-green, #7ee787);
      background: rgb(46 160 67 / 16%);
    }
    .segment-status.in_review {
      border-color: var(--true-color-blue, #1f6feb);
      color: var(--true-color-blue, #79c0ff);
    }
    .segment-status.coordinates-review {
      min-width: 220px;
      border: 2px solid #d29922;
      color: #f2cc60;
      background: rgb(187 128 9 / 20%);
      font-size: 14px;
      font-weight: 800;
      box-shadow: 0 0 0 3px rgb(242 204 96 / 10%);
    }
    .segment-status.coordinate-verified {
      border-color: var(--true-color-green, #238636);
      color: var(--true-color-green, #7ee787);
      background: rgb(46 160 67 / 16%);
    }
    .shared-review-card {
      padding: 12px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 12px;
      background: var(--background-color-subtle, #161b22);
    }
    .shared-review-card summary {
      cursor: pointer;
      font-weight: var(--font-weight-semibold, 600);
    }
    .shared-review-table {
      width: 100%;
      margin-top: 12px;
      border-collapse: collapse;
      font-size: 12px;
    }
    .shared-review-table th,
    .shared-review-table td {
      padding: 8px;
      border-bottom: 1px solid var(--border-color-muted, #21262d);
      text-align: left;
      vertical-align: top;
    }
    .shared-review-table tr.selected {
      background: var(--background-color-muted, #21262d);
    }
    [data-ai-gated].ai-locked,
    .segment-processing-locked {
      position: relative;
      opacity: 0.38;
      filter: grayscale(1);
      pointer-events: none;
      user-select: none;
      border-color: var(--border-color-muted, #484f58);
    }
    [data-ai-gated].ai-locked::before,
    .segment-processing-locked::before {
      content: "Disabled";
      position: absolute;
      z-index: 3;
      top: 10px;
      right: 10px;
      padding: 3px 8px;
      border: 1px solid var(--border-color-default, #6e7681);
      border-radius: 999px;
      color: var(--foreground-color-muted, #8c959f);
      background: var(--background-color-default, #0d1117);
      font-size: 11px;
      font-weight: var(--font-weight-semibold, 600);
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    .empty-review {
      margin: 12px 0;
      padding: 18px;
      border: 1px dashed var(--border-color-default, #30363d);
      border-radius: 12px;
      background: var(--background-color-subtle, #161b22);
    }
    .video-shell {
      overflow: hidden;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 12px;
      background: #000;
    }
    .video-media {
      position: relative;
      overflow: hidden;
      background: #000;
      transform: scale(1);
      transition: transform 160ms ease-out;
    }
    .video-shell:fullscreen {
      display: grid;
      width: 100vw;
      height: 100vh;
      grid-template-rows: minmax(0, 1fr) auto;
      border: 0;
      border-radius: 0;
    }
    video {
      display: block;
      width: 100%;
      aspect-ratio: 16 / 7;
      object-fit: contain;
      background: #000;
    }
    .ball-overlay {
      position: absolute;
      z-index: 1;
      inset: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
    }
    .ball-marker {
      fill: rgb(255 255 255 / 18%);
      stroke: var(--true-color-red, #ff3b30);
      stroke-width: 8;
      vector-effect: non-scaling-stroke;
    }
    .ball-crosshair {
      stroke: var(--color-white, #fff);
      stroke-width: 3;
      vector-effect: non-scaling-stroke;
    }
    .ball-trajectory {
      fill: none;
      stroke: var(--true-color-red, #ff3b30);
      stroke-width: 5;
      stroke-linecap: round;
      stroke-linejoin: round;
      opacity: 0.8;
      vector-effect: non-scaling-stroke;
    }
    .geometry-overlay {
      position: absolute;
      z-index: 1;
      inset: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
    }
    .geometry-overlay.editing {
      z-index: 4;
      cursor: crosshair;
      pointer-events: auto;
    }
    .calibration-tools {
      display: grid;
      grid-template-columns: minmax(180px, 1fr) repeat(5, auto);
      gap: 8px;
      align-items: end;
    }
    .calibration-visibility {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      margin-bottom: 12px;
    }
    .calibration-visibility label {
      display: inline-flex;
      gap: 7px;
      align-items: center;
    }
    .calibration-visibility input { accent-color: var(--true-color-blue, #1f6feb); }
    .calibration-rule { margin-bottom: 0; }
    @media (max-width: 900px) {
      .calibration-tools { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .calibration-tools label { grid-column: 1 / -1; }
    }
    .view-modes {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      padding: 10px;
      border-top: 1px solid var(--border-color-default, #30363d);
      background: var(--background-color-subtle, #161b22);
    }
    .view-modes button {
      min-height: 34px;
      padding: 5px 10px;
    }
    .view-modes button[aria-pressed="true"] {
      border-color: var(--true-color-blue, #1f6feb);
      background: rgb(31 111 235 / 22%);
      color: var(--true-color-blue, #79c0ff);
    }
    .view-note {
      align-self: center;
      margin-left: auto;
      font-size: 12px;
    }
    .video-shell.action-zoom .video-media { transform: scale(2.35); }
    .video-shell:fullscreen .video-media,
    .video-shell:fullscreen video { height: 100%; aspect-ratio: auto; }
    .transport {
      position: relative;
      z-index: 2;
      display: grid;
      grid-template-columns:
        auto auto minmax(120px, 1fr) auto auto auto auto auto;
      gap: 8px;
      align-items: center;
      padding: 10px;
      border-top: 1px solid var(--border-color-default, #30363d);
      background: var(--background-color-subtle, #161b22);
    }
    .transport label {
      display: grid;
      gap: 3px;
      color: var(--text-color-muted, #8b949e);
      font-size: 12px;
    }
    .transport input { width: 100%; }
    .ball-frame-review {
      margin: 0 0 12px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 12px;
      background: var(--background-color-subtle, #161b22);
    }
    .ball-frame-review summary {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 12px;
      cursor: pointer;
    }
    .ball-frame-table-wrap {
      max-height: 300px;
      overflow: auto;
      border-top: 1px solid var(--border-color-default, #30363d);
    }
    .ball-frame-table {
      width: 100%;
      border-collapse: collapse;
      font-variant-numeric: tabular-nums;
    }
    .ball-frame-table th,
    .ball-frame-table td {
      padding: 7px 9px;
      border-bottom: 1px solid var(--border-color-muted, #21262d);
      text-align: left;
      white-space: nowrap;
    }
    .ball-frame-table thead {
      position: sticky;
      z-index: 1;
      top: 0;
      background: var(--background-color-subtle, #161b22);
    }
    .ball-frame-open {
      min-height: 28px;
      padding: 3px 8px;
    }
    .ball-frame-status.direct { color: #aff5b4; }
    .ball-frame-status.estimated { color: #f2cc60; }
    .coordinate-review-result {
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 700;
    }
    .coordinate-review-result.confirmed {
      border-color: var(--true-color-green, #2ea043);
      color: var(--true-color-green, #7ee787);
      background: rgb(46 160 67 / 12%);
    }
    .coordinate-review-result.checking {
      border-color: var(--true-color-yellow, #d29922);
      color: var(--true-color-yellow, #e3b341);
      background: rgb(210 153 34 / 12%);
    }
    .coordinate-review-result.pending {
      color: var(--text-color-muted, #8b949e);
    }
    .ball-coordinate-review-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      padding: 10px 0;
    }
    .ball-coordinate-review-actions strong {
      color: #f2cc60;
    }
    #coordinate-review-tabs button.latest-review {
      border-color: #d29922;
      background: #3b2f12;
      color: #f2cc60;
      font-weight: var(--font-weight-semibold, 600);
    }
    #coordinate-review-tabs button.latest-review.current {
      box-shadow: inset 0 0 0 1px #f2cc60;
    }
    #ball-frame-filter.latest-review {
      border-color: #d29922;
      background: #3b2f12;
      color: #f2cc60;
      font-weight: var(--font-weight-semibold, 600);
    }
    #ball-frame-filter option.latest-review {
      background: #3b2f12;
      color: #f2cc60;
      font-weight: var(--font-weight-semibold, 600);
    }
    .coordinate-review-messages {
      max-height: 260px;
      overflow: auto;
      margin: 12px 0;
      padding: 0;
      list-style: none;
    }
    .coordinate-review-messages li {
      margin-bottom: 8px;
      padding: 9px 11px;
      border-radius: 8px;
      background: var(--background-color-muted, #21262d);
      white-space: pre-wrap;
    }
    .ball-coordinate-modal-frames {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      max-height: 180px;
      overflow: auto;
      padding: 10px 0;
    }
    .ball-frame-modal {
      width: min(1120px, calc(100vw - 32px));
      max-width: none;
      padding: 0;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 12px;
      background: #0d1117;
      color: #f0f6fc;
    }
    .ball-frame-modal::backdrop { background: rgb(0 0 0 / 78%); }
    .ball-frame-modal-head,
    .ball-frame-modal-actions {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      padding: 10px 12px;
    }
    .ball-frame-modal-title {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .review-target-badge {
      padding: 4px 9px;
      border: 1px solid #58a6ff;
      border-radius: 999px;
      background: rgb(31 111 235 / 24%);
      color: #79c0ff;
      font-weight: 800;
    }
    .raw-frame-context {
      color: #b1bac4;
      font-weight: 600;
    }
    .ball-frame-modal-status {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 9px 12px;
      border-block: 1px solid #1f6feb;
      background: rgb(31 111 235 / 14%);
      color: #c9d1d9;
    }
    .ball-frame-modal-status strong {
      flex: 0 0 auto;
      color: #79c0ff;
    }
    .ball-frame-modal-media {
      position: relative;
      overflow: hidden;
      background: #000;
      cursor: zoom-in;
      --zoom-x: 50%;
      --zoom-y: 50%;
      touch-action: none;
    }
    .ball-frame-modal-media video {
      width: 100%;
      aspect-ratio: 16 / 7;
      object-fit: contain;
    }
    .ball-frame-modal-overlay {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
    }
    .ball-frame-modal-media video,
    .ball-frame-modal-overlay {
      transform-origin: var(--zoom-x) var(--zoom-y);
      transition: transform 160ms ease-out;
    }
    .ball-frame-modal-media.zoomed {
      cursor: grab;
    }
    .ball-frame-modal-media.marking {
      cursor: crosshair;
    }
    .ball-frame-modal-media.panning {
      cursor: grabbing;
    }
    .ball-frame-modal-media.seeking::after {
      content: attr(data-seek-status);
      position: absolute;
      z-index: 3;
      inset: 50% auto auto 50%;
      translate: -50% -50%;
      padding: 8px 12px;
      border: 1px solid #58a6ff;
      border-radius: 8px;
      background: rgb(13 17 23 / 92%);
      color: #79c0ff;
      font-weight: 800;
      pointer-events: none;
    }
    .raw-frame-nav {
      position: absolute;
      z-index: 2;
      top: 10px;
    }
    .raw-frame-nav.previous { left: 10px; }
    .raw-frame-nav.next { right: 10px; }
    .raw-frame-nav button {
      min-width: 44px;
      background: rgb(13 17 23 / 85%);
      backdrop-filter: blur(4px);
    }
    .ball-review-navigation {
      display: flex;
      gap: 6px;
    }
    .coordinate-icon-action {
      min-width: 42px;
      padding-inline: 10px;
      font-size: 20px;
      font-weight: 800;
    }
    .coordinate-icon-action.agree { color: #7ee787; }
    .coordinate-icon-action.undefined { color: #ff7b72; }
    .ball-frame-modal-media.zoomed video,
    .ball-frame-modal-media.zoomed .ball-frame-modal-overlay {
      transform: scale(2.5);
    }
    .ball-frame-modal-marker {
      fill: rgb(126 231 135 / 20%);
      stroke: #7ee787;
      stroke-width: 2;
      vector-effect: non-scaling-stroke;
    }
    .ball-frame-modal-marker.trajectory-audit {
      fill: none;
      fill-opacity: 0;
      stroke: #ff3b30;
      stroke-width: 2;
    }
    .ball-frame-modal-crosshair {
      fill: none;
      stroke: #7ee787;
      stroke-width: 3;
      opacity: .65;
      vector-effect: non-scaling-stroke;
    }
    .ball-frame-user-marker {
      fill: rgb(242 204 96 / 25%);
      stroke: #f2cc60;
      stroke-width: 5;
      vector-effect: non-scaling-stroke;
    }
    .ball-frame-modal-details {
      padding: 0 12px 10px;
      color: #c9d1d9;
      font-family: var(--font-mono, Consolas, monospace);
    }
    .ball-frame-overlay-controls {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 16px;
      padding: 0 12px 10px;
    }
    .ball-frame-overlay-controls label {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-weight: 700;
    }
    .ball-frame-overlay-controls .engine { color: #ff6961; }
    .ball-frame-overlay-controls .yolo { color: #79c0ff; }
    .missing-event {
      padding: 12px;
      border: 1px solid var(--panel-border, #30363d);
      border-radius: 12px;
      background: var(--panel-background, #161b22);
      box-shadow: inset 0 0 0 1px rgb(104 224 170 / 4%);
    }
    .clip-conversation-head {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 8px;
      align-items: baseline;
    }
    .clip-conversation-head h2,
    .clip-conversation-head span { display: inline; }
    .clip-conversation-head-actions {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
      align-items: center;
      margin-left: auto;
    }
    .missing-event-fields {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto;
      gap: 8px;
      align-items: end;
      margin-top: 12px;
    }
    .clip-question-actions {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }
    .clip-question-actions button { min-width: 190px; }
    .manual-review-fields {
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: repeat(4, minmax(120px, 1fr));
      gap: 8px;
      align-items: end;
      padding: 10px;
      border: 1px solid var(--nested-panel-border, #30363d);
      border-radius: 8px;
      background: var(--nested-panel-background, #0d1117);
      box-shadow: inset 0 0 0 1px rgb(104 224 170 / 5%);
    }
    .manual-review-fields[hidden] { display: none; }
    .manual-review-heading,
    .manual-review-note {
      grid-column: 1 / -1;
    }
    .manual-review-heading {
      margin: 0;
      text-wrap: balance;
    }
    .manual-review-note textarea {
      min-height: 72px;
    }
    .manual-review-time {
      grid-column: 1 / -1;
      margin: 0;
    }
    .manual-review-fields button { grid-column: 1 / -1; }
    .clip-scope-field {
      min-width: 190px;
      align-self: stretch;
    }
    .missing-event-status,
    .missing-event-plan { grid-column: 1 / -1; }
    .missing-event label {
      display: grid;
      gap: 4px;
      color: var(--text-color-muted, #8b949e);
      font-size: 12px;
    }
    .missing-event select,
    .missing-event input,
    .missing-event textarea {
      min-height: 40px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 8px;
      padding: 8px 10px;
      background: var(--background-color-default, #0d1117);
      color: var(--text-color-default, #f0f6fc);
    }
    .missing-event-status {
      grid-column: 1 / -1;
      min-height: 20px;
      margin: 0;
    }
    .missing-event-plan {
      grid-column: 1 / -1;
      padding: 10px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 9px;
      background: var(--background-color-default, #0d1117);
    }
    .missing-event-plan.supported {
      border-color: var(--true-color-green, #238636);
    }
    .missing-event-plan.unsupported {
      border-color: var(--true-color-yellow, #9e6a03);
    }
    .missing-event-plan p { margin: 6px 0 0; }
    .missing-event-plan button { margin-top: 9px; }
    .time {
      font-family: var(--font-mono, Consolas, monospace);
      font-variant-numeric: tabular-nums;
    }
    .event-nav {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      padding: 10px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 12px;
      background: color-mix(
        in srgb,
        var(--background-color-subtle, #161b22) 78%,
        var(--true-color-blue-muted, #1f6feb) 22%
      );
      document.getElementById("fullscreen-cancel-adjustment").addEventListener(
        "click",
        () => cancelAdjustment().catch(error => {
          document.getElementById("fullscreen-chat-status").textContent =
            error.message;
        })
      );
    }
    .publication-status {
      grid-column: 1 / -1;
      min-height: 20px;
      margin: 0;
    }
    .event-position { text-align: center; }
    .current-event-label {
      display: block;
      margin-bottom: 3px;
      color: var(--true-color-blue, #79c0ff);
      font-size: 11px;
      font-weight: var(--font-weight-semibold, 600);
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .event-position strong {
      display: block;
      font-size: var(--text-title-medium, 20px);
      line-height: 1.2;
    }
    .event-position .muted {
      display: block;
      margin-top: 4px;
      font-size: var(--text-body-medium, 14px);
    }
    .accept-all-events {
      grid-column: 1 / -1;
      border-color: var(--true-color-green, #238636);
    }
    .publish-reference {
      grid-column: 1 / -1;
      border-color: var(--true-color-blue, #58a6ff);
      background: color-mix(
        in srgb,
        var(--background-color-muted, #21262d) 72%,
        var(--true-color-blue-muted, #1f6feb) 28%
      );
    }
    .workflow-hints {
      padding: 10px 12px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 10px;
      background: var(--background-color-default, #0d1117);
    }
    .workflow-hints summary {
      cursor: pointer;
      color: var(--true-color-blue, #79c0ff);
      font-weight: var(--font-weight-semibold, 600);
    }
    .workflow-hints ul {
      margin: 9px 0 0;
      padding-left: 20px;
      color: var(--text-color-muted, #8b949e);
      font-size: 12px;
    }
    .workflow-hints li + li { margin-top: 5px; }
    .developer-panel {
      padding: 10px 12px;
      border: 1px solid var(--true-color-blue, #58a6ff);
      border-radius: 10px;
      background: color-mix(
        in srgb,
        var(--background-color-default, #0d1117) 88%,
        var(--true-color-blue-muted, #1f6feb) 12%
      );
    }
    .developer-panel summary {
      cursor: pointer;
      color: var(--true-color-blue, #79c0ff);
      font-weight: var(--font-weight-semibold, 600);
    }
    .developer-panel h3 { margin-top: 12px; }
    .developer-panel p { margin: 7px 0; }
    .developer-panel code {
      overflow-wrap: anywhere;
      color: var(--text-color-default, #f0f6fc);
    }
    .developer-command {
      margin-top: 8px;
      padding: 9px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 8px;
      background: var(--background-color-subtle, #161b22);
    }
    .developer-command pre {
      margin: 7px 0 0;
      overflow-x: auto;
      white-space: pre-wrap;
      color: var(--text-color-muted, #8b949e);
      font-family: var(--font-mono, Consolas, monospace);
      font-size: 11px;
    }
    .developer-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }
    .developer-actions .copilot-handover {
      border-color: var(--true-color-orange, #d29922);
    }
    .developer-status {
      min-height: 18px;
      color: var(--text-color-muted, #8b949e);
      font-size: 12px;
    }
    .proposal {
      padding: 16px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 12px;
      background: var(--background-color-subtle, #161b22);
    }
    .proposal.accepted {
      border-color: var(--border-color-muted, #484f58);
      background: color-mix(
        in srgb,
        var(--background-color-subtle, #161b22) 72%,
        #6e7681 28%
      );
    }
    .proposal.accepted .proposal-title,
    .proposal.accepted .basis-grid,
    .proposal.accepted .review-flow {
      opacity: .58;
      filter: grayscale(1);
    }
    .proposal.rejected {
      border-color: var(--true-color-red, #da3633);
      background: color-mix(
        in srgb,
        var(--true-color-red-muted, #5a1d1d) 28%,
        var(--background-color-subtle, #161b22)
      );
    }
    .proposal.rejected .proposal-title,
    .proposal.rejected .basis-grid,
    .proposal.rejected .review-flow {
      opacity: .62;
    }
    .proposal-title {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
      align-items: start;
    }
    .event-time {
      color: var(--true-color-blue, #79c0ff);
      font-family: var(--font-mono, Consolas, monospace);
      font-variant-numeric: tabular-nums;
    }
    .event-source {
      display: inline-block;
      margin-top: 6px;
      padding: 3px 7px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 999px;
      color: var(--text-color-muted, #8b949e);
      font-size: 11px;
      font-weight: var(--font-weight-semibold, 600);
    }
    .event-source.engine { border-color: #1f6feb; color: #79c0ff; }
    .event-source.copilot { border-color: #8957e5; color: #d2a8ff; }
    .event-source.user { border-color: #9e6a03; color: #e3b341; }
    .event-source.reference { border-color: #238636; color: #7ee787; }
    .event-source-note {
      display: block;
      margin-top: 5px;
      max-width: 460px;
      color: var(--text-color-muted, #8b949e);
      font-size: 11px;
      line-height: 1.35;
    }
    .basis-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 14px;
    }
    .basis {
      min-width: 0;
      padding: 11px;
      border-radius: 9px;
      background: var(--background-color-default, #0d1117);
    }
    .basis h3 { margin-bottom: 5px; }
    .basis p { margin: 0; overflow-wrap: anywhere; }
    .decisions {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 14px;
    }
    .review-flow {
      margin: 12px 0 0;
      padding: 10px 10px 10px 30px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 9px;
      color: var(--text-color-muted, #8b949e);
      background: var(--background-color-default, #0d1117);
    }
    .review-flow li + li { margin-top: 5px; }
    .accept { border-color: var(--true-color-green, #238636); }
    .adjust { border-color: var(--true-color-yellow, #9e6a03); }
    .reject { border-color: var(--true-color-red, #da3633); }
    .decision-status, .engine-result, .world-rules {
      margin-top: 12px;
      padding: 11px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 9px;
      background: var(--background-color-default, #0d1117);
    }
    .decision-status:empty, .engine-result[hidden] { display: none; }
    .engine-result.already_agrees { border-color: var(--true-color-green, #238636); }
    .engine-result.missing, .engine-result.conflicting,
    .engine-result.stale {
      border-color: var(--true-color-yellow, #9e6a03);
    }
    .fingerprint {
      display: block;
      margin-top: 6px;
      color: var(--text-color-muted, #8b949e);
      font-family: var(--font-mono, Consolas, monospace);
      font-size: 11px;
      overflow-wrap: anywhere;
    }
    .world-rules summary {
      cursor: pointer;
      font-weight: var(--font-weight-semibold, 600);
    }
    .world-rules p { margin: 8px 0 0; }
    .match-replay {
      margin-top: 12px;
      padding: 14px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 12px;
      background: var(--background-color-subtle, #161b22);
    }
    .match-replay-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      margin-bottom: 10px;
    }
    .replay-readiness {
      padding: 5px 9px;
      border: 1px solid var(--true-color-yellow, #9e6a03);
      border-radius: 999px;
      color: var(--true-color-yellow, #e3b341);
      font-size: 12px;
      font-weight: var(--font-weight-semibold, 600);
    }
    .replay-readiness.complete {
      border-color: var(--true-color-green, #238636);
      color: var(--true-color-green, #7ee787);
    }
    .replay-picker {
      display: grid;
      gap: 4px;
      margin-bottom: 10px;
      color: var(--text-color-muted, #8b949e);
      font-size: 12px;
    }
    .replay-picker select {
      min-height: 40px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 8px;
      padding: 7px 10px;
      background: var(--background-color-default, #0d1117);
      color: var(--text-color-default, #f0f6fc);
    }
    .replay-layout {
      display: grid;
      grid-template-columns: minmax(0, 1.55fr) minmax(230px, .7fr);
      gap: 10px;
    }
    .replay-player {
      overflow: hidden;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 10px;
      background: #000;
    }
    .replay-player video { aspect-ratio: 16 / 7; }
    .replay-controls {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      padding: 9px;
      background: var(--background-color-default, #0d1117);
    }
    .match-board {
      display: grid;
      align-content: start;
      gap: 10px;
      padding: 13px;
      border-radius: 10px;
      background: linear-gradient(145deg, #071b12, #0d3322);
      color: #fff;
    }
    .match-clock {
      text-align: center;
      font-family: var(--font-mono, Consolas, monospace);
      font-size: 18px;
      font-weight: 700;
    }
    .scoreline {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
      gap: 8px;
      align-items: center;
      text-align: center;
    }
    .score {
      font-size: 32px;
      font-weight: 800;
      letter-spacing: .08em;
    }
    .stats-table {
      width: 100%;
      border-collapse: collapse;
      font-variant-numeric: tabular-nums;
    }
    .stats-table th, .stats-table td {
      padding: 5px 3px;
      border-top: 1px solid rgb(255 255 255 / 16%);
      text-align: center;
    }
    .stats-table th { font-size: 12px; font-weight: 500; }
    .stats-table td:first-child, .stats-table td:last-child {
      width: 40px;
      font-weight: 700;
    }
    .replay-note { margin: 9px 0 0; }
    .conversation {
      display: flex;
      margin-top: 14px;
      overflow: hidden;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 9px;
      background: var(--background-color-default, #0d1117);
      flex-direction: column;
    }
    .conversation-head {
      display: flex;
      gap: 10px;
      align-items: center;
      padding: 11px;
      border-bottom: 1px solid var(--border-color-default, #30363d);
    }
    .conversation-title-block {
      min-width: 0;
      flex: 1;
    }
    .conversation-head p { margin: 5px 0 0; }
    .chat-status {
      display: inline-block;
      margin-top: 6px;
      padding: 2px 7px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 999px;
      color: var(--text-color-muted, #8b949e);
      font-size: 11px;
      font-weight: var(--font-weight-semibold, 600);
    }
    .chat-status[data-state="working"] {
      border-color: var(--true-color-yellow, #9e6a03);
      color: var(--true-color-yellow, #e3b341);
    }
    .chat-status[data-state="error"] {
      border-color: var(--true-color-red, #da3633);
      color: var(--true-color-red, #ff7b72);
    }
    .messages {
      display: grid;
      align-content: start;
      gap: 9px;
      margin: 0;
      padding: 12px;
      max-height: min(28vh, 260px);
      overflow-y: auto;
      overscroll-behavior: contain;
      list-style: none;
    }
    .message {
      padding: 9px 10px;
      border-radius: 9px;
      background: var(--background-color-default, #0d1117);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .message.user { border-left: 3px solid var(--true-color-blue, #58a6ff); }
    .message.assistant { border-left: 3px solid var(--true-color-green, #3fb950); }
    .message.system { border-left: 3px solid var(--true-color-red, #ff7b72); }
    .message strong {
      display: block;
      margin-bottom: 3px;
      font-size: 12px;
    }
    .composer {
      display: grid;
      gap: 8px;
      padding: 12px;
      border-top: 1px solid var(--border-color-default, #30363d);
    }
    textarea {
      width: 100%;
      min-height: 92px;
      resize: vertical;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 8px;
      padding: 9px;
      background: var(--background-color-default, #0d1117);
      color: inherit;
    }
    .composer-status { min-height: 20px; margin: 0; }
    .copilot-handover {
      border-color: var(--true-color-green, #238636);
    }
    .event-trigger {
      position: absolute;
      z-index: 5;
      top: 14px;
      display: flex;
      gap: 9px;
      align-items: center;
      max-width: calc(100% - 28px);
      padding: 9px 12px;
      border: 1px solid #3fb950;
      border-radius: 999px;
      background: rgb(13 17 23 / 72%);
      color: #aff5b4;
      box-shadow: 0 0 0 0 rgb(63 185 80 / 55%);
      pointer-events: none;
    }
    .event-trigger.copilot {
      left: 14px;
      border-color: #58a6ff;
      color: #dbeafe;
      box-shadow: 0 0 0 0 rgb(88 166 255 / 65%);
    }
    .event-trigger.engine {
      right: 220px;
    }
    .event-trigger[hidden] { display: none; }
    .event-trigger.active { animation: event-ping 1.6s ease-out; }
    .event-trigger.copilot.active {
      animation-name: copilot-event-ping;
    }
    .event-trigger-dot {
      width: 10px;
      height: 10px;
      flex: 0 0 auto;
      border-radius: 50%;
      background: #3fb950;
      box-shadow: 0 0 0 5px rgb(63 185 80 / 22%);
    }
    .event-trigger.copilot .event-trigger-dot {
      background: #58a6ff;
      box-shadow: 0 0 0 5px rgb(88 166 255 / 25%);
    }
    .review-progress-overlay {
      position: absolute;
      z-index: 7;
      top: 14px;
      left: 50%;
      display: flex;
      gap: 9px;
      align-items: center;
      max-width: min(560px, calc(100% - 28px));
      padding: 9px 13px;
      border: 1px solid #d29922;
      border-radius: 999px;
      background: rgb(13 17 23 / 88%);
      color: #f2cc60;
      box-shadow: 0 8px 24px rgb(0 0 0 / 32%);
      pointer-events: none;
      transform: translateX(-50%);
    }
    .review-progress-overlay[hidden] { display: none; }
    .review-progress-dot {
      width: 10px;
      height: 10px;
      flex: 0 0 auto;
      border-radius: 50%;
      background: #d29922;
      animation: pulse 1.2s ease-in-out infinite;
    }
    .review-progress-text {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .video-shell:fullscreen .review-progress-overlay {
      top: 18px;
      max-width: min(720px, calc(100% - 28px));
      font-size: 14px;
    }
    .live-stats-overlay {
      position: absolute;
      z-index: 4;
      top: 14px;
      right: 14px;
      min-width: 190px;
      overflow: hidden;
      border: 1px solid rgb(240 246 252 / 24%);
      border-radius: 10px;
      background: rgb(13 17 23 / 68%);
      color: #f0f6fc;
      box-shadow: 0 8px 24px rgb(0 0 0 / 28%);
      backdrop-filter: blur(4px);
      pointer-events: none;
    }
    .live-stats-head {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      padding: 7px 9px;
      border-bottom: 1px solid rgb(240 246 252 / 16%);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .04em;
    }
    .live-stats-overlay table {
      width: 100%;
      border-collapse: collapse;
      font-size: 11px;
      font-variant-numeric: tabular-nums;
    }
    .live-stats-overlay th, .live-stats-overlay td {
      padding: 4px 7px;
      text-align: center;
    }
    .live-stats-overlay tbody th {
      color: #c9d1d9;
      font-weight: 500;
    }
    .live-team-red { color: #ff7b72; }
    .live-team-black { color: #c9d1d9; }
    .fullscreen-events {
      position: absolute;
      z-index: 4;
      bottom: 14px;
      left: 50%;
      display: none;
      width: min(920px, calc(100% - 28px));
      max-height: min(82vh, 760px);
      overflow: hidden;
      border: 1px solid rgb(240 246 252 / 24%);
      border-radius: 10px;
      background: rgb(13 17 23 / 76%);
      color: #f0f6fc;
      box-shadow: 0 8px 24px rgb(0 0 0 / 28%);
      backdrop-filter: blur(4px);
      transform: translateX(-50%);
    }
    .video-shell:fullscreen .fullscreen-events {
      display: flex;
      flex-direction: column;
    }
    .video-shell:fullscreen.events-hidden .fullscreen-events {
      display: none;
    }
    .fullscreen-only { display: none; }
    .video-shell:fullscreen .fullscreen-only {
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .fullscreen-events-head {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 112px minmax(0, 1fr);
      gap: 8px;
      padding: 8px 10px;
      border-bottom: 1px solid rgb(240 246 252 / 16%);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .04em;
    }
    .fullscreen-events-head span:nth-child(2) { text-align: center; }
    .fullscreen-events-head span:last-child { text-align: right; }
    .comparison-summary {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 7px 10px;
      border-bottom: 1px solid rgb(240 246 252 / 16%);
      color: #c9d1d9;
      font-size: 11px;
    }
    .comparison-summary span::before {
      display: inline-block;
      width: 8px;
      height: 8px;
      margin-right: 5px;
      border-radius: 50%;
      content: "";
    }
    .comparison-summary .matched::before { background: #3fb950; }
    .comparison-summary .reviewed::before { background: #58a6ff; }
    .comparison-summary .stoppage::before { background: #d29922; }
    .comparison-summary .off::before { background: #f85149; }
    .comparison-guide {
      padding: 7px 10px;
      border-bottom: 1px solid rgb(240 246 252 / 16%);
      color: #c9d1d9;
      font-size: 11px;
      line-height: 1.4;
    }
    .comparison-guide summary {
      cursor: pointer;
      color: #c9d1d9;
      font-weight: var(--font-weight-semibold, 600);
    }
    .comparison-guide-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 88px minmax(0, 1fr);
      gap: 8px;
      margin-top: 7px;
    }
    .comparison-guide-column {
      display: grid;
      gap: 4px;
      align-content: start;
      min-width: 0;
    }
    .comparison-guide-column.general {
      padding-inline: 7px;
      border-inline: 1px solid rgb(240 246 252 / 12%);
      text-align: center;
    }
    .comparison-guide-column:last-child { text-align: right; }
    .comparison-guide-line { display: block; }
    .comparison-guide strong {
      color: #f0f6fc;
      font-weight: var(--font-weight-semibold, 600);
    }
    .fullscreen-event-items {
      display: grid;
      grid-auto-rows: max-content;
      align-content: start;
      min-height: 0;
      overflow-y: auto;
      padding: 6px;
    }
    .fullscreen-event-chat {
      display: none;
      min-height: 0;
      border-top: 1px solid rgb(240 246 252 / 18%);
      background: rgb(13 17 23 / 82%);
    }
    .video-shell:fullscreen .fullscreen-event-chat {
      display: grid;
      grid-template-rows: auto minmax(70px, 150px) auto;
    }
    .fullscreen-chat-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      padding: 7px 10px;
    }
    .fullscreen-event-chat .messages {
      max-height: 150px;
      padding: 7px 10px;
      font-size: 11px;
    }
    .fullscreen-event-chat .message { padding: 6px 8px; }
    .fullscreen-chat-composer {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto auto auto;
      gap: 7px;
      padding: 8px 10px 10px;
    }
    .fullscreen-chat-composer textarea {
      min-height: 42px;
      max-height: 90px;
      resize: vertical;
    }
    .fullscreen-chat-status {
      grid-column: 1 / -1;
      min-height: 16px;
      margin: 0;
    }
    .fullscreen-workflow-note {
      grid-column: 1 / -1;
      margin: 0;
      color: var(--text-color-muted, #8b949e);
      font-size: 11px;
      color: #c9d1d9;
      font-size: 11px;
    }
    .comparison-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 88px minmax(0, 1fr);
      gap: 8px;
      align-items: stretch;
      min-height: 54px;
      border-bottom: 1px solid rgb(240 246 252 / 10%);
    }
    .comparison-row.has-review-actions { min-height: 54px; }
    .comparison-row:last-child { border-bottom: 0; }
    .comparison-row.matched { background: transparent; }
    .comparison-row.reviewed { background: rgb(31 111 235 / 16%); }
    .comparison-row.stoppage { background: rgb(210 153 34 / 16%); }
    .comparison-row.off { background: rgb(248 81 73 / 15%); }
    .comparison-row.decision-accepted {
      background: rgb(35 134 54 / 18%);
      box-shadow: inset 3px 0 0 #3fb950;
    }
    .comparison-row.decision-rejected {
      background: rgb(248 81 73 / 11%);
      box-shadow: inset 3px 0 0 #f85149;
      opacity: .8;
    }
    .comparison-time {
      display: grid;
      place-items: center;
      position: relative;
      color: #79c0ff;
      font-family: var(--font-mono, Consolas, monospace);
      font-size: 11px;
      font-variant-numeric: tabular-nums;
    }
    .comparison-time::before {
      position: absolute;
      inset-block: 0;
      left: 50%;
      width: 1px;
      background: rgb(121 192 255 / 32%);
      content: "";
    }
    .comparison-time span {
      position: relative;
      padding: 2px 4px;
      background: #0d1117;
    }
    .comparison-event {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 7px;
      align-items: center;
      width: 100%;
      box-sizing: border-box;
      min-height: 34px;
      margin: 2px 0;
      padding: 4px 6px;
      border-color: transparent;
      background: transparent;
      color: #c9d1d9;
      text-align: left;
    }
    .comparison-review-cell {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 5px;
      align-items: center;
      min-width: 0;
      padding: 2px 4px;
    }
    .comparison-review-cell .comparison-event { min-width: 0; }
    .comparison-review-cell > .comparison-accepted,
    .comparison-review-cell > .comparison-rejected,
    .comparison-review-cell > .comparison-reviewed {
      justify-self: start;
    }
    .comparison-review-cell.verifying {
      border-radius: 7px;
      background: rgb(210 153 34 / 24%);
      box-shadow: inset 0 0 0 1px #d29922;
    }
    .comparison-action {
      min-height: 30px;
      width: 100%;
      box-sizing: border-box;
      padding: 4px 7px;
      border-color: rgb(240 246 252 / 20%);
      background: rgb(13 17 23 / 78%);
      color: #c9d1d9;
      font-size: 10px;
      line-height: 1.2;
      white-space: normal;
    }
    .comparison-actions {
      display: grid;
      grid-template-columns: repeat(2, 38px);
      align-self: center;
      justify-self: end;
      width: auto;
      box-sizing: border-box;
      min-width: 0;
      gap: 4px;
      padding: 2px;
      border: 1px solid rgb(240 246 252 / 12%);
      border-radius: 7px;
      background: rgb(13 17 23 / 46%);
    }
    .comparison-action.icon-action {
      display: grid;
      place-items: center;
      width: 36px;
      min-height: 36px;
      padding: 0;
    }
    .comparison-action-icon {
      width: 16px;
      height: 16px;
      fill: none;
      stroke: currentColor;
      stroke-linecap: round;
      stroke-linejoin: round;
      stroke-width: 2;
    }
    .comparison-action.accept-action {
      border-color: #3fb950;
      color: #aff5b4;
    }
    .comparison-action.reject {
      border-color: #f85149;
      color: #ffb3ad;
    }
    .comparison-rejected {
      padding: 2px 6px;
      border: 1px solid rgb(248 81 73 / 36%);
      border-radius: 999px;
      background: rgb(248 81 73 / 10%);
      color: #ffb3ad;
      font-size: 9px;
      font-weight: var(--font-weight-semibold, 600);
      line-height: 1.25;
      overflow-wrap: anywhere;
    }
    .comparison-reviewed {
      padding: 2px 6px;
      border: 1px solid rgb(88 166 255 / 34%);
      border-radius: 999px;
      background: rgb(31 111 235 / 12%);
      color: #79c0ff;
      font-size: 9px;
      font-weight: var(--font-weight-semibold, 600);
      line-height: 1.25;
      overflow-wrap: anywhere;
    }
    .comparison-engine-cell {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto auto;
      gap: 5px;
      align-items: center;
      min-width: 0;
      padding: 2px 4px;
    }
    .comparison-engine-cell .comparison-event { min-width: 0; }
    .comparison-engine-cell > .comparison-rejected,
    .comparison-engine-cell > .comparison-reviewed {
      justify-self: end;
      text-align: right;
    }
    .comparison-accepted {
      padding: 2px 6px;
      border: 1px solid rgb(63 185 80 / 38%);
      border-radius: 999px;
      background: rgb(35 134 54 / 14%);
      color: #aff5b4;
      font-size: 9px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }
    .comparison-verifying {
      padding: 2px 6px;
      color: #f2cc60;
      font-size: 9px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }
    .comparison-event.engine { text-align: right; }
    .comparison-event.engine .comparison-number { order: 2; }
    .comparison-event:hover,
    .comparison-event:focus-visible {
      border-color: #58a6ff;
      background: rgb(31 111 235 / 24%);
    }
    .comparison-event.current {
      border-color: #8b949e;
      background: rgb(110 118 129 / 14%);
      color: #f0f6fc;
    }
    .comparison-row.stoppage .comparison-event,
    .comparison-row.stoppage .comparison-time {
      color: #e3b341;
    }
    .comparison-row.off .comparison-event,
    .comparison-row.off .comparison-time {
      color: #ff7b72;
    }
    .comparison-event.review.reached {
      border-color: #58a6ff;
      background: transparent;
      color: #dbeafe;
      box-shadow: inset 3px 0 0 rgb(88 166 255 / 72%);
    }
    .comparison-event.engine.reached {
      border-color: #3fb950;
      background: transparent;
      color: #aff5b4;
      box-shadow: inset -3px 0 0 rgb(63 185 80 / 72%);
    }
    .comparison-event.current,
    .comparison-event.current.reached {
      border-color: #8b949e;
      background: rgb(110 118 129 / 18%);
      color: #f0f6fc;
      box-shadow: none;
    }
    .comparison-event.review.playback-ping {
      animation: copilot-event-ping 1.6s ease-out;
    }
    .comparison-event.engine.playback-ping {
      animation: event-ping 1.6s ease-out;
    }
    .comparison-number {
      color: #79c0ff;
      font-family: var(--font-mono, Consolas, monospace);
      font-size: 11px;
    }
    .comparison-label {
      display: grid;
      gap: 2px;
      min-width: 0;
      overflow-wrap: break-word;
      text-wrap: pretty;
    }
    .comparison-frame {
      display: block;
      color: var(--text-color-muted, #8b949e);
      font-family: var(--font-mono, Consolas, monospace);
      font-size: 10px;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }
    .comparison-empty { min-height: 42px; }
    .compact-engine-rail {
      position: absolute;
      z-index: 5;
      top: 136px;
      right: 7px;
      bottom: 14px;
      width: 18px;
      border-right: 1px solid rgb(121 192 255 / 36%);
      pointer-events: none;
    }
    .video-shell:fullscreen .compact-engine-rail { display: none; }
    .compact-engine-spot {
      position: absolute;
      right: -6px;
      width: 12px;
      height: 12px;
      min-height: 0;
      padding: 0;
      border: 2px solid #0d1117;
      border-radius: 50%;
      background: #58a6ff;
      box-shadow: 0 0 0 2px rgb(88 166 255 / 28%);
      pointer-events: auto;
      transform: translateY(-50%);
    }
    .compact-engine-spot.reached { background: #3fb950; }
    .compact-engine-spot.matched { border-color: #3fb950; }
    .compact-engine-spot.stoppage { border-color: #d29922; }
    .compact-engine-spot.off {
      border-color: #f85149;
      box-shadow: 0 0 0 3px rgb(248 81 73 / 40%);
    }
    .compact-engine-spot.current {
      box-shadow: 0 0 0 4px rgb(63 185 80 / 48%);
    }
    @keyframes event-ping {
      0% { box-shadow: 0 0 0 0 rgb(63 185 80 / 65%); }
      55% { box-shadow: 0 0 0 16px rgb(63 185 80 / 0%); }
      100% { box-shadow: 0 0 0 0 rgb(63 185 80 / 0%); }
    }
    @keyframes copilot-event-ping {
      0% { box-shadow: 0 0 0 0 rgb(88 166 255 / 75%); }
      55% { box-shadow: 0 0 0 16px rgb(88 166 255 / 0%); }
      100% { box-shadow: 0 0 0 0 rgb(88 166 255 / 0%); }
    }
    @media (max-width: 900px) {
      .review { gap: 16px; }
      .review-workspace { grid-template-columns: 1fr; }
      .event-rail {
        position: static;
        max-height: none;
        overflow: visible;
      }
      .segment-builder-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .missing-event-fields {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .missing-event-note { grid-column: 1 / -1; }
      .replay-layout { grid-template-columns: 1fr; }
    }
    @media (max-width: 600px) {
      .transport { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .transport label { grid-column: 1 / -1; grid-row: 1; }
      .basis-grid, .decisions { grid-template-columns: 1fr; }
      .missing-event-fields { grid-template-columns: 1fr; }
      .missing-event-note { grid-column: auto; }
      .live-stats-overlay { min-width: 160px; }
      .live-stats-overlay th, .live-stats-overlay td { padding: 3px 5px; }
    }
    @media (prefers-reduced-motion: reduce) {
      .activity.working .activity-dot { animation: none; }
      .event-trigger.active { animation: none; }
      .review-progress-dot { animation: none; }
      video { transition: none; }
    }
    html[data-app-theme="innovation"] {
      --background-color-default: #100d12;
      --background-color-muted: #2a1c2c;
      --background-color-subtle: #19131b;
      --border-color-default: #4b354d;
      --text-color-default: #fbf8fb;
      --text-color-muted: #c5bac6;
      --color-focus-outline: #cf6fbe;
      --true-color-green: #68e0c1;
      --true-color-blue: #ba4ca6;
      --true-color-blue-muted: #6c1d5f;
    }
    html[data-app-theme="innovation"] body {
      background:
        radial-gradient(circle at 84% 2%, rgb(108 29 95 / 32%), transparent 34rem),
        linear-gradient(145deg, #100d12, #0c090e 74%);
    }
    html[data-app-theme="innovation"] header {
      border-bottom-color: rgb(186 76 166 / 42%);
      background: rgb(16 13 18 / 92%);
    }
    html[data-app-theme="innovation"] .scope {
      border-color: #ba4ca6;
      color: #f0b7e6;
      background: rgb(108 29 95 / 18%);
    }
    html[data-app-theme="innovation"] .innovation-brand {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    html[data-app-theme="innovation"] .innovation-brand::before {
      width: 18px;
      height: 3px;
      content: "";
      background: linear-gradient(90deg, #ba4ca6 0 46%, transparent 46% 54%, #68e0c1 54%);
    }
    html[data-app-theme="innovation"] button:hover,
    html[data-app-theme="innovation"] .comparison-event:hover,
    html[data-app-theme="innovation"] .comparison-event:focus-visible {
      border-color: #cf6fbe;
      background: rgb(108 29 95 / 34%);
    }
    html[data-app-theme="innovation"] .comparison-event.current,
    html[data-app-theme="innovation"] .comparison-row.matched .comparison-event {
      border-color: #ba4ca6;
      background: rgb(108 29 95 / 38%);
    }
    html[data-app-theme="innovation"] .comparison-number,
    html[data-app-theme="innovation"] .current-event-label,
    html[data-app-theme="innovation"] .event-source {
      color: #df8fd2;
    }
    html[data-app-theme="innovation"] .video-shell {
      border-color: rgb(186 76 166 / 58%);
      box-shadow: 0 0 0 1px rgb(186 76 166 / 18%),
        0 18px 50px rgb(0 0 0 / 34%);
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1 id="page-title">Live Football Event Review</h1>
      <div class="muted" id="page-subtitle">
        Prepared segment → reference review → engine check
      </div>
      <div class="innovation-brand">
        <span>Raw-video ball coordinates · Current engine</span>
        <span class="component-version" id="tracker-version">
          Ball tracker: loading
        </span>
        <span class="component-version" id="ball-coordinate-coverage">
          Ball coordinates: loading
        </span>
        <span class="component-version" id="rules-version">
          Rules engine: loading
        </span>
      </div>
    </div>
    <div class="header-actions">
      <label class="review-mode-field" for="review-audience">
        Review mode
        <select id="review-audience">
          <option value="reviewer">Normal review</option>
          <option value="developer">Developer</option>
          <option value="trajectory-audit">Ball trajectory audit</option>
        </select>
      </label>
      <a class="home-link" href="${homeUrl}">${homeLabel}</a>
      <span class="scope">20–60 second Alfheim segments · Live pipeline</span>
    </div>
  </header>
  <p class="activity ready" id="activity" aria-live="polite">
    <span class="activity-dot" aria-hidden="true"></span>
    <span><strong id="activity-label">Ready for your review</strong>
      <span class="muted" id="activity-detail"></span></span>
    <button id="proceed-after-coordinate-gate" type="button" hidden>
      Proceed to event review
    </button>
    <button id="continue-coordinate-review" type="button" hidden>
      Continue reviewing
    </button>
  </p>
  <main class="layout">
    <section class="review" aria-label="Selected football event review">
      <details class="segment-builder" id="segment-builder-panel" open>
        <summary>
          <h2 id="segment-builder-title">Prepare & Run a Stream Segment</h2>
          <span class="muted">Open only when changing segments</span>
        </summary>
        <div class="segment-builder-body">
          <div class="segment-builder-grid">
            <label for="segment-start-minute">Start minute
              <input id="segment-start-minute" name="segment-start-minute"
                type="number" min="0" step="1" value="15"
                inputmode="numeric" autocomplete="off">
            </label>
            <label for="segment-start-second">Start second
              <input id="segment-start-second" name="segment-start-second"
                type="number" min="0" max="59" step="1" value="0"
                inputmode="numeric" autocomplete="off">
            </label>
            <label for="segment-duration">Review duration
              <select id="segment-duration" name="segment-duration">
                <option value="20">20 seconds</option>
                <option value="30">30 seconds</option>
                <option value="60" selected>60 seconds</option>
              </select>
            </label>
            <button id="prepare-segment" type="button">Prepare Segment</button>
            <button id="process-segment" type="button">Start AI</button>
          </div>
          <progress class="segment-progress" id="segment-progress"
            max="1" value="0" hidden></progress>
          <p class="muted segment-run-status" id="segment-run-status"
            aria-live="polite">Select an existing segment or prepare a new minute.</p>
        </div>
      </details>
      <details class="segment-builder" id="camera-import-panel">
        <summary>
          <h2>Add a Camera Sample</h2>
          <span class="muted">Own footage · isolated calibration</span>
        </summary>
        <div class="segment-builder-body">
          <div class="camera-import-grid">
            <label for="camera-club">Club
              <input id="camera-club" type="text" maxlength="100"
                autocomplete="organization" placeholder="Club name">
            </label>
            <label for="camera-venue">Venue
              <input id="camera-venue" type="text" maxlength="100"
                autocomplete="off" placeholder="Main stadium">
            </label>
            <label for="camera-position">Camera position
              <input id="camera-position" type="text" maxlength="100"
                autocomplete="off" placeholder="Main stand panoramic">
            </label>
            <label for="camera-name">Camera name
              <input id="camera-name" type="text" maxlength="80"
                autocomplete="off" placeholder="Home main camera">
            </label>
            <label for="camera-serial">Serial number (optional)
              <input id="camera-serial" type="text" maxlength="120"
                autocomplete="off" placeholder="Manufacturer serial">
            </label>
            <label for="camera-sample">Raw 30–60 second sample
              <input id="camera-sample" type="file"
                accept="video/mp4,video/quicktime,video/webm">
            </label>
            <button id="add-camera" type="button">Add Camera</button>
          </div>
          <p class="muted" id="camera-import-status" aria-live="polite">
            The sample is stored under its own camera ID. It is never mixed
            with Alfheim or SoccerTrack calibration, tracking, or review data.
          </p>
        </div>
      </details>
      <details class="segment-builder camera-geometry" id="geometry-panel">
        <summary>
          <h2>Camera Calibration & Overlays</h2>
          <span class="muted" id="geometry-availability">
            Saved pitch edges and goal frames
          </span>
        </summary>
        <div class="segment-builder-body">
          <div class="calibration-visibility">
            <label>
              <input id="show-pitch" type="checkbox" checked>
              Calibrated pitch boundary
            </label>
            <label>
              <input id="show-goals" type="checkbox" checked>
              Calibrated goal frames
            </label>
          </div>
          <div class="calibration-tools">
            <label for="geometry-feature">Feature to calibrate
              <select id="geometry-feature">
                <option value="near_touchline">Near long side</option>
                <option value="far_touchline">Far long side</option>
                <option value="left_goal_line">Left narrow side</option>
                <option value="right_goal_line">Right narrow side</option>
                <option value="left_goal_mouth">Left goal posts</option>
                <option value="right_goal_mouth">Right goal posts</option>
              </select>
            </label>
            <button id="edit-geometry" type="button">Redraw</button>
            <button id="undo-geometry" type="button">Undo point</button>
            <button id="finish-geometry" type="button">Finish</button>
            <button id="save-geometry" type="button">Save calibration for AI</button>
            <button id="restore-geometry" type="button">Restore saved</button>
            <button id="export-geometry" type="button">Download</button>
          </div>
          <p class="muted" id="geometry-status" aria-live="polite">
            Loading the saved camera calibration…
          </p>
          <p class="muted calibration-rule">
            <strong>Line rule:</strong> trace the outer edge of each painted
            white line—the edge furthest from the playing area. For a goal,
            click all four visible goal-frame corners clockwise.
          </p>
        </div>
      </details>
      <div class="segment-picker">
        <label for="source-select">Dataset / camera
          <select id="source-select" autocomplete="off"></select>
        </label>
        <label for="segment-select">Prepared segment
          <select id="segment-select" autocomplete="off"></select>
        </label>
        <span class="segment-status" id="segment-status">Loading</span>
        <p class="muted" id="source-attribution"></p>
      </div>
      <details class="shared-review-card">
        <summary>Shared approvals &amp; validation gates</summary>
        <div class="table-wrap">
          <table class="shared-review-table"
            aria-label="Shared review status for all prepared segments">
            <thead>
              <tr>
                <th>Segment</th>
                <th>Decisions</th>
                <th>Regression</th>
                <th>Publication</th>
                <th>Last update</th>
              </tr>
            </thead>
            <tbody id="shared-review-status"></tbody>
          </table>
        </div>
      </details>
      <div class="review-workspace">
        <div class="media-column">
          <details class="ball-frame-review" id="ball-frame-review">
            <summary>
              <strong>Ball coordinate frames</strong>
              <span class="muted" id="ball-frame-summary">Loading</span>
            </summary>
            <label for="ball-frame-filter">Show
              <select id="ball-frame-filter" autocomplete="off">
                <option value="estimated">Estimated only</option>
                <option value="integrity">Integrity-demoted only</option>
                <option value="flagged">Flagged for review</option>
                <option value="diagnostic">Focused diagnostic batch</option>
                <option value="all">All frames</option>
                <option value="direct">Direct only</option>
              </select>
            </label>
            <div class="ball-coordinate-review-actions">
              <button id="open-ball-coordinate-review" type="button">
                Review flagged frames with Copilot
              </button>
              <button id="download-trajectory-audit" type="button" hidden>
                Download audit JSON
              </button>
              <strong id="ball-coordinate-review-mode">
                Coordinate recovery mode
              </strong>
              <span class="muted" id="ball-coordinate-review-status"></span>
            </div>
            <div class="ball-frame-table-wrap">
              <table class="ball-frame-table">
                <thead>
                  <tr>
                    <th>Frame</th>
                    <th>Time</th>
                    <th>X</th>
                    <th>Y</th>
                    <th>Status</th>
                    <th>Evidence</th>
                    <th>Review</th>
                  </tr>
                </thead>
                <tbody id="ball-frame-items"></tbody>
              </table>
            </div>
          </details>
          <div class="video-shell" id="video-shell">
        <div class="video-media" id="video-media">
          <video id="video" controls preload="metadata"
            aria-label="Selected football stream segment footage"></video>
          <div class="video-empty" id="video-empty" hidden>
            No merged review segment is available for this camera.
          </div>
          <svg class="ball-overlay" id="ball-overlay" hidden
            preserveAspectRatio="xMidYMid meet" aria-hidden="true">
            <path class="ball-trajectory" id="ball-trajectory"></path>
            <circle class="ball-marker" id="ball-marker" r="30"></circle>
            <path class="ball-crosshair" id="ball-crosshair"></path>
          </svg>
          <canvas class="geometry-overlay" id="geometry-overlay"
            aria-label="Calibrated pitch and goal outlines"></canvas>
          <div class="event-trigger copilot" id="copilot-event-trigger" hidden
            role="status" aria-live="polite">
            <span class="event-trigger-dot" aria-hidden="true"></span>
            <strong id="copilot-event-trigger-label">Copilot event</strong>
          </div>
          <div class="event-trigger engine" id="engine-event-trigger" hidden
            role="status" aria-live="polite">
            <span class="event-trigger-dot" aria-hidden="true"></span>
            <strong id="engine-event-trigger-label">Engine event</strong>
          </div>
          <div class="review-progress-overlay" id="review-progress-overlay"
            role="status" aria-live="polite" hidden>
            <span class="review-progress-dot" aria-hidden="true"></span>
            <strong class="review-progress-text" id="review-progress-text">
              Copilot is working…
            </strong>
          </div>
          <aside class="live-stats-overlay" aria-label="Live segment statistics">
            <div class="live-stats-head">
              <strong>Live stats</strong>
              <span id="fullscreen-ball-coverage">Ball coordinates: loading</span>
              <span id="live-stats-time">00:00</span>
            </div>
            <table>
              <thead>
                <tr>
                  <th class="live-team-red">Red/white</th>
                  <th>Event</th>
                  <th class="live-team-black">Black</th>
                </tr>
              </thead>
              <tbody>
                <tr><td id="live-red-passes">0</td><th>Passes</th>
                  <td id="live-black-passes">0</td></tr>
                <tr><td id="live-red-turnovers">0</td><th>Turnovers</th>
                  <td id="live-black-turnovers">0</td></tr>
                <tr><td id="live-red-shots">0</td><th>Shots</th>
                  <td id="live-black-shots">0</td></tr>
                <tr><td id="live-red-on-target">0</td><th>On target</th>
                  <td id="live-black-on-target">0</td></tr>
              </tbody>
            </table>
          </aside>
          <aside class="fullscreen-events" id="fullscreen-events"
            aria-label="Segment events">
            <div class="fullscreen-events-head">
              <span>Review proposal</span>
              <span>Seconds</span>
              <span>Rules engine output</span>
            </div>
            <div class="comparison-summary" id="comparison-summary"
              aria-live="polite"></div>
            <details class="comparison-guide" aria-label="Comparison guidance">
              <summary>How to read this comparison</summary>
              <div class="comparison-guide-grid">
                <div class="comparison-guide-column">
                  <span class="comparison-guide-line">
                    <strong>Green C↔E</strong>: verify and accept C#.
                  </span>
                  <span class="comparison-guide-line">
                    <strong>Red C-only</strong>: verify C# to trigger
                    general-rule synchronization.
                  </span>
                </div>
                <div class="comparison-guide-column general">
                  <span class="comparison-guide-line">
                    <strong>General</strong>
                  </span>
                  <span class="comparison-guide-line">
                    <strong>Yellow</strong>: foul/stoppage context.
                  </span>
                </div>
                <div class="comparison-guide-column">
                  <span class="comparison-guide-line">
                    <strong>Green C↔E</strong>: engine agrees with C#.
                  </span>
                  <span class="comparison-guide-line">
                    <strong>Red E-only</strong>: ask the clip conversation first.
                  </span>
                </div>
              </div>
            </details>
            <div class="fullscreen-event-items" id="fullscreen-event-items"></div>
            <section class="fullscreen-event-chat" data-ai-gated
              aria-labelledby="fullscreen-chat-title">
              <div class="fullscreen-chat-head">
                <div>
                  <strong id="fullscreen-chat-title">Selected event conversation</strong>
                  <p class="fullscreen-workflow-note"
                    id="fullscreen-workflow-note"></p>
                </div>
                <span class="chat-status" id="fullscreen-chat-activity"
                  data-state="ready">Ready</span>
              </div>
              <ol class="messages" id="fullscreen-messages"
                aria-live="polite"></ol>
              <form class="fullscreen-chat-composer"
                id="fullscreen-chat-composer">
                <textarea id="fullscreen-message" maxlength="4000"
                  autocomplete="off"
                  placeholder="Ask Copilot about this event…"></textarea>
                <button id="fullscreen-send-message" type="submit">
                  Ask Copilot
                </button>
                <button class="copilot-handover"
                  id="fullscreen-primary-action" type="button">
                  Verify Selected Event (Autopilot)
                </button>
                <button id="fullscreen-adjust" type="button">
                  Request Adjustment
                </button>
                <button id="fullscreen-cancel-adjustment" type="button" hidden>
                  Stop Adjustment Review
                </button>
                <p class="fullscreen-chat-status"
                  id="fullscreen-chat-status" aria-live="polite"></p>
              </form>
              <details class="developer-panel" data-developer-panel hidden>
                <summary>Developer workflow · local commands</summary>
                <p data-developer-summary></p>
                <h3>Suggested code area</h3>
                <code data-developer-code-area></code>
                <p data-developer-change></p>
                <div class="developer-command">
                  <strong>Focused tests</strong>
                  <pre data-developer-command="focused"></pre>
                </div>
                <div class="developer-command">
                  <strong>Cached rules-engine rerun</strong>
                  <pre data-developer-command="rebuild"></pre>
                </div>
                <div class="developer-command">
                  <strong>Protected live regressions</strong>
                  <pre data-developer-command="protected"></pre>
                </div>
                <div class="developer-actions">
                  <button type="button" data-copy-developer="focused">
                    Copy focused tests
                  </button>
                  <button type="button" data-copy-developer="rebuild">
                    Copy rules-engine rerun
                  </button>
                  <button type="button" data-copy-developer="protected">
                    Copy protected tests
                  </button>
                  <button type="button" data-developer-refresh>
                    Refresh engine output
                  </button>
                  <button class="copilot-handover" type="button"
                    data-developer-copilot>
                    Do it, Copilot
                  </button>
                </div>
                <p class="developer-status" data-developer-status
                  aria-live="polite"></p>
              </details>
            </section>
          </aside>
          <nav class="compact-engine-rail" id="compact-engine-rail"
            aria-label="Rules engine event positions"></nav>
        </div>
        <div class="view-modes" role="group" aria-label="Video view">
          <button type="button" data-view-mode="normal"
            aria-pressed="true">Normal</button>
          <button type="button" data-view-mode="ball"
            aria-pressed="false">Detected ball</button>
          <button type="button" data-view-mode="ai"
            aria-pressed="false">AI tracking</button>
          <span class="muted view-note" id="view-note">
            Original video without overlays
          </span>
        </div>
        <div class="transport">
          <button id="previous-frame" type="button">← Frame</button>
          <button id="next-frame" type="button">Frame →</button>
          <label>Review Position
            <input id="timeline" name="timeline" type="range"
              min="0" max="60" step="0.04" value="0" autocomplete="off">
          </label>
          <output class="time" id="time" aria-live="polite">0.00s</output>
          <label class="playback-speed fullscreen-only" for="playback-speed">
            Speed
            <select id="playback-speed" aria-label="Playback speed">
              <option value="0.25">0.25×</option>
              <option value="0.5">0.5×</option>
              <option value="0.75">0.75×</option>
              <option value="1" selected>1×</option>
              <option value="1.5">1.5×</option>
              <option value="2">2×</option>
            </select>
          </label>
          <button class="fullscreen-only" id="toggle-event-panel" type="button"
            aria-controls="fullscreen-events" aria-expanded="true">
            Hide event panel
          </button>
          <button id="show-ball-frames" type="button"
            aria-controls="ball-coordinate-review-modal">
            Ball frames
          </button>
          <button id="zoom-action" type="button">Zoom to Action</button>
          <button id="enlarge" type="button">Enlarge Review</button>
        </div>
          </div>

          <dialog class="ball-frame-modal" id="ball-frame-modal">
            <div class="ball-frame-modal-head">
              <div class="ball-frame-modal-title" id="ball-frame-modal-title"
                aria-live="polite">
                <span class="review-target-badge"
                  id="ball-frame-review-target">Review frame</span>
                <span class="raw-frame-context"
                  id="ball-frame-raw-context">Viewing raw frame</span>
              </div>
              <button id="close-ball-frame-modal" type="button">Close</button>
            </div>
            <div class="ball-frame-modal-status" role="status"
              aria-live="polite">
              <strong id="ball-frame-modal-mode">Coordinate review active</strong>
              <span id="ball-frame-decision-status">
                No decision recorded for this review frame.
              </span>
            </div>
            <div class="ball-frame-modal-media">
              <div class="raw-frame-nav previous">
                <button id="previous-ball-frame" type="button"
                  aria-label="Previous raw frame, minus one"
                  title="Previous raw frame (−1)">
                  ← −1
                </button>
              </div>
              <video id="ball-frame-modal-video" muted playsinline
                preload="auto" aria-label="Enlarged selected frame"></video>
              <svg class="ball-frame-modal-overlay"
                id="ball-frame-modal-overlay"
                preserveAspectRatio="xMidYMid meet" aria-hidden="true">
                <circle class="ball-frame-modal-marker"
                  id="ball-frame-modal-marker" r="7"></circle>
                <path class="ball-frame-modal-crosshair"
                  id="ball-frame-modal-crosshair"></path>
                <g id="ball-frame-yolo-markers"></g>
                <circle class="ball-frame-user-marker"
                  id="ball-frame-user-marker" r="14" hidden></circle>
              </svg>
              <div class="raw-frame-nav next">
                <button id="next-ball-frame" type="button"
                  aria-label="Next raw frame, plus one"
                  title="Next raw frame (+1)">
                  +1 →
                </button>
              </div>
            </div>
            <div class="ball-frame-modal-details"
              id="ball-frame-modal-details"></div>
            <div class="ball-frame-overlay-controls"
              id="ball-frame-overlay-controls" hidden>
              <label class="engine">
                <input id="show-engine-ball-marker" type="checkbox" checked>
                Engine ring (red)
              </label>
              <label class="yolo">
                <input id="show-yolo-ball-markers" type="checkbox" checked>
                YOLO candidates (blue)
              </label>
            </div>
            <div class="ball-frame-modal-actions">
              <div class="ball-review-navigation"
                id="ball-review-navigation">
                <button id="previous-ball-review-frame" type="button">
                  ← Previous review
                </button>
                <button id="next-ball-review-frame" type="button">
                  Next review →
                </button>
              </div>
              <button id="play-ball-frame-video" type="button" hidden>
                Play
              </button>
              <button id="target-ball-frame" type="button">
                Go to target coordinate
              </button>
              <button class="coordinate-icon-action agree"
                id="agree-ball-coordinate" type="button"
                aria-label="Agree with current coordinate"
                title="Agree with current coordinate">
                ✓
              </button>
              <button class="coordinate-icon-action undefined"
                id="undefined-ball-coordinate" type="button"
                aria-label="Ball undefined or not visible"
                title="Ball undefined or not visible">
                ●
              </button>
              <button id="needs-more-checking" type="button" hidden>
                Needs more checking
              </button>
              <button id="mark-ball-location" type="button">
                Specify my own coordinate
              </button>
              <button id="approve-ball-location" type="button" disabled>
                Confirm my coordinate &amp; next target
              </button>
              <button class="coordinate-icon-action"
                id="undo-ball-coordinate-decision" type="button" disabled
                aria-label="Undo coordinate decision"
                title="Undo coordinate decision">
                ↶
              </button>
              <button id="zoom-ball-frame" type="button">
                Zoom to target
              </button>
              <button id="reset-ball-frame-zoom" type="button" hidden>
                Reset zoom
              </button>
            </div>
          </dialog>

          <dialog class="ball-frame-modal" id="ball-coordinate-review-modal">
            <div class="ball-frame-modal-head">
              <strong>Ball coordinate frames &amp; Copilot review</strong>
              <button id="close-ball-coordinate-review" type="button">
                Close
              </button>
            </div>
            <nav class="event-nav" id="coordinate-review-tabs"
              aria-label="Ball-coordinate review rounds"></nav>
            <ol class="coordinate-review-messages"
              id="coordinate-review-timeline" aria-live="polite"></ol>
            <div class="ball-frame-modal-details">
              This conversation reviews only the flagged coordinate frames.
              Flags remain evaluation-only and never become inference inputs.
            </div>
            <div class="ball-coordinate-modal-frames"
              id="ball-coordinate-modal-frames"></div>
            <ol class="coordinate-review-messages"
              id="ball-coordinate-review-messages" aria-live="polite"></ol>
            <label for="ball-coordinate-review-message">
              Review request
              <textarea id="ball-coordinate-review-message" maxlength="1000"
                autocomplete="off"
                placeholder="Review the flagged frames and explain which coordinates have sufficient raw-video support."></textarea>
            </label>
            <p class="muted" id="ball-coordinate-review-send-status"
              aria-live="polite"></p>
            <div class="ball-frame-modal-actions">
              <button class="copilot-handover"
                id="send-ball-coordinate-autopilot" type="button">
                Review &amp; improve approved batch once (Autopilot)
              </button>
              <button id="finalize-ball-coordinate-review" type="button"
                disabled>
                Finalize and put in review
              </button>
            </div>
          </dialog>

          <section class="missing-event conversation" id="clip-conversation-panel"
            data-ai-gated
            aria-labelledby="clip-conversation-title">
            <div class="clip-conversation-head">
              <div>
                <h2 id="clip-conversation-title">Ask Copilot about this clip</h2>
                <p class="muted" id="clip-conversation-note">
                  General clip messages stay separate from every event conversation.
                </p>
              </div>
              <div class="clip-conversation-head-actions">
                <button id="show-general-clip-conversation" type="button" hidden>
                  Back to General Clip
                </button>
                <span class="chat-status" id="clip-chat-status" data-state="ready">
                  Ready
                </span>
              </div>
            </div>
            <ol class="messages" id="clip-messages" aria-live="polite">
              <li class="message system">No general clip messages yet.</li>
            </ol>
            <form class="missing-event-fields" id="clip-composer">
              <label class="missing-event-note" for="clip-message">
                <span id="clip-message-label">
                  Ask about any event, the current frame, or the overall clip
                </span>
                <textarea id="clip-message" name="clip-message" maxlength="1000"
                  autocomplete="off"
                  placeholder="Example: Did the engine miss an event here?…"></textarea>
              </label>
              <label class="clip-scope-field" id="clip-scope-field"
                for="clip-message-scope">
                Evidence scope
                <select id="clip-message-scope" name="clip-message-scope">
                  <option value="entire_clip" selected>Entire clip</option>
                  <option value="current_time">Current time ±2s</option>
                </select>
              </label>
              <div class="clip-question-actions">
                <button id="toggle-manual-review" type="button">
                  Add Manual Review
                </button>
                <button id="send-clip-plan" type="button">
                  Ask Copilot about
                  <span class="clip-message-target">entire clip</span> (Plan mode)
                </button>
                <button class="copilot-handover" id="send-clip-autopilot"
                  type="button">
                  Ask Copilot about
                  <span class="clip-message-target">entire clip</span> (Autopilot)
                </button>
              </div>
              <section class="manual-review-fields" id="manual-review-fields"
                aria-labelledby="manual-review-heading" hidden>
                <h3 class="manual-review-heading" id="manual-review-heading">
                  Add Manual Review Event
                </h3>
                <label class="manual-review-note" for="manual-review-note">
                  Evidence note (required)
                  <textarea id="manual-review-note" name="manual-review-note"
                    maxlength="1000" autocomplete="off"
                    placeholder="Describe exactly what happened and which players touched the ball…"></textarea>
                </label>
                <label for="manual-review-second">Second
                  <select id="manual-review-second"></select>
                </label>
                <label for="manual-review-frame">Milliseconds / frame
                  <select id="manual-review-frame"></select>
                </label>
                <label for="manual-review-team">Team
                  <select id="manual-review-team">
                    <option value="red">Red/white</option>
                    <option value="black">Black</option>
                  </select>
                </label>
                <label for="manual-review-type">Event
                  <select id="manual-review-type">
                    <option value="completed_pass">Completed pass</option>
                    <option value="turnover">Turnover</option>
                  </select>
                </label>
                <p class="muted manual-review-time" id="manual-review-time">
                  Choose the event second and millisecond frame.
                </p>
                <button class="copilot-handover" id="create-manual-review"
                  type="button" disabled>
                  Choose Time to Create Manual M#
                </button>
              </section>
              <p class="muted missing-event-status" id="missing-event-status"
                aria-live="polite"></p>
              <section class="missing-event-plan" id="missing-event-plan" hidden>
                <strong id="missing-plan-title">Plan result</strong>
                <p id="missing-plan-detail"></p>
                <button class="copilot-handover" id="confirm-missing-event"
                  type="button" hidden>
                  Add as Review Event (Autopilot)
                </button>
              </section>
            </form>
          </section>
        </div>

        <aside class="event-rail" data-ai-gated
          aria-label="Current event review">
          <nav class="event-nav" id="event-nav" aria-label="Reference event navigation">
        <button id="previous-event" type="button">Previous Event</button>
        <div class="event-position">
          <span class="current-event-label">Current Event</span>
          <strong id="event-number">Event 1 of 1</strong>
          <span class="muted" id="event-summary">Loading…</span>
        </div>
        <button id="next-event" type="button">Next Event</button>
        <button class="accept-all-events" id="accept-all-events" type="button">
          Verify &amp; Accept All Events (Autopilot)
        </button>
        <button class="publish-reference" id="publish-reference" type="button"
          hidden>
          Publish Validated Reference (Autopilot)
        </button>
        <p class="muted publication-status" id="publication-status"
          aria-live="polite"></p>
          </nav>

          <details class="workflow-hints" open>
            <summary>How to verify and accept</summary>
            <ul>
              <li><strong>Green C↔E:</strong> the proposal and engine align.
                Use Verify &amp; Accept C# when the video evidence is correct.</li>
              <li><strong>Red C# without E#:</strong> verify C# directly.
                If supported, Copilot accepts it and synchronizes a general
                engine rule.</li>
              <li><strong>Red E# without C#:</strong> ask about it in
                Ask Copilot about this clip. A supported event becomes a C#
                proposal before it can be accepted.</li>
              <li><strong>Yellow:</strong> foul/stoppage match-state context;
                it does not require a pass/turnover engine counterpart.</li>
              <li><strong>Safeguard:</strong> no timestamp-specific fixes.
                A mismatch stays red until cached output and protected
                regressions confirm the general rule.</li>
            </ul>
          </details>

          <details class="developer-panel" data-developer-panel hidden>
            <summary>Developer workflow · local commands</summary>
            <p data-developer-summary></p>
            <h3>Suggested code area</h3>
            <code data-developer-code-area></code>
            <p data-developer-change></p>
            <div class="developer-command">
              <strong>Focused tests</strong>
              <pre data-developer-command="focused"></pre>
            </div>
            <div class="developer-command">
              <strong>Cached rules-engine rerun</strong>
              <pre data-developer-command="rebuild"></pre>
            </div>
            <div class="developer-command">
              <strong>Protected live regressions</strong>
              <pre data-developer-command="protected"></pre>
            </div>
            <div class="developer-actions">
              <button type="button" data-copy-developer="focused">
                Copy focused tests
              </button>
              <button type="button" data-copy-developer="rebuild">
                Copy rules-engine rerun
              </button>
              <button type="button" data-copy-developer="protected">
                Copy protected tests
              </button>
              <button type="button" data-developer-refresh>
                Refresh engine output
              </button>
              <button class="copilot-handover" type="button"
                data-developer-copilot>
                Do it, Copilot
              </button>
            </div>
            <p class="developer-status" data-developer-status
              aria-live="polite"></p>
          </details>

          <section class="empty-review" id="empty-review" hidden>
            <h2 id="empty-review-title">No reviewed events yet</h2>
            <p id="empty-review-detail"></p>
          </section>

          <article class="proposal" id="proposal" aria-labelledby="proposal-title">
        <div class="proposal-title">
          <div>
            <h2 id="proposal-title">Loading proposal…</h2>
            <div class="muted" id="proposal-kind"></div>
            <span class="event-source" id="proposal-source">Loading source</span>
            <span class="event-source-note">
              Proposal origin only; engine agreement is checked after acceptance.
            </span>
          </div>
          <span class="event-time" id="proposal-time"></span>
        </div>
        <div class="basis-grid">
          <section class="basis">
            <h3 id="evidence-heading">Video Evidence</h3>
            <p id="proposal-evidence"></p>
          </section>
          <section class="basis">
            <h3>Rule Basis</h3>
            <p id="proposal-rule"></p>
          </section>
        </div>
        <div class="decisions" aria-label="Review decision">
          <button class="accept" id="accept" type="button">Accept Event</button>
          <button class="adjust" id="adjust" type="button">Request Adjustment</button>
          <button class="reject" id="cancel-adjustment" type="button" hidden>
            Stop Adjustment Review
          </button>
          <button class="reject" id="reject" type="button">Reject Event</button>
        </div>
        <ol class="review-flow" id="review-flow">
          <li><strong>Correct:</strong> accept and reveal the engine check.</li>
          <li><strong>Want a handover:</strong> let Copilot verify this event,
            accept only when it agrees, then check the rules engine. It changes
            a general rule only when the engine is missing or contradicting the
            accepted event.</li>
          <li><strong>Wrong detail:</strong> describe it in the message box,
            then request an adjustment. Copilot will re-check and publish a
            revised proposal here using one targeted review; AI detection is
            not rerun.</li>
          <li><strong>No event occurred:</strong> reject the proposal.</li>
        </ol>
        <p class="decision-status" id="decision-status" aria-live="polite"></p>
        <section class="engine-result" id="engine-result" hidden>
          <h3 id="engine-heading">Engine Check</h3>
          <p id="engine-detail"></p>
          <span class="fingerprint" id="engine-fingerprint"></span>
          <p id="regression-status"></p>
        </section>
        <section class="conversation" id="conversation-panel" data-ai-gated
          aria-labelledby="conversation-title">
          <div class="conversation-head">
            <div class="conversation-title-block">
              <h2 id="conversation-title">Live Copilot for Event 1</h2>
              <p class="muted" id="conversation-scope-note">
                This conversation contains only messages for the selected event.
              </p>
              <span class="chat-status" id="chat-status" data-state="ready">
                Ready
              </span>
            </div>
          </div>
          <ol class="messages" id="messages" aria-live="polite">
            <li class="message system">No messages yet for this event.</li>
          </ol>
          <form class="composer" id="composer">
            <label for="message">Message about this event</label>
            <textarea id="message" name="message" maxlength="4000"
              placeholder="Explain what you see or ask why this event was proposed…"
              autocomplete="off"></textarea>
            <button type="submit" id="send-message">
              Ask Copilot (Plan mode)
            </button>
            <button class="copilot-handover" id="copilot-accept" type="button">
              Verify, Accept &amp; Sync Engine (Autopilot)
            </button>
            <button class="copilot-handover" id="accepted-engine-recheck"
              type="button" hidden>
              Re-check Accepted C# &amp; Engine (Autopilot)
            </button>
            <button id="require-same-frame-review" type="button" hidden>
              Require Same-Frame C↔E Timing
            </button>
            <p class="muted composer-mode">
              Plan mode discusses only. Action buttons explicitly authorize
              Autopilot changes for this event.
            </p>
            <p class="muted composer-status" id="composer-status"
              aria-live="polite"></p>
          </form>
        </section>
          </article>

        </aside>
      </div>

      <details class="world-rules">
        <summary>What “world football rules” means here</summary>
        <p><strong>Universal match-state layer:</strong> use accepted Laws of
          the Game for ball in/out of play, fouls, advantage, restarts, and
          goals.</p>
        <p><strong>Project analytics layer:</strong> completed pass, turnover,
          possession, and shot outcome are explicit operational definitions.
          They are validated here because the Laws do not define those
          statistics.</p>
      </details>

      <section class="match-replay" data-ai-gated
        aria-labelledby="match-replay-title">
        <div class="match-replay-head">
          <div>
            <h2 id="match-replay-title">Match Replay Preview</h2>
            <span class="muted">Consecutive AI-ready minutes only</span>
          </div>
          <span class="replay-readiness" id="replay-readiness">0/10 ready</span>
        </div>
        <label class="replay-picker" for="replay-run">
          Available consecutive run
          <select id="replay-run"></select>
        </label>
        <div class="replay-layout">
          <div class="replay-player">
            <video id="replay-video" controls preload="metadata"
              aria-label="Presentation match replay"></video>
            <div class="replay-controls">
              <button id="replay-play" type="button">Play sequence</button>
              <button id="replay-restart" type="button">Restart</button>
              <span class="muted" id="replay-position">No run selected</span>
            </div>
          </div>
          <aside class="match-board" aria-label="Match statistics preview">
            <div class="match-clock" id="match-clock">00:00 / 10:00</div>
            <div class="scoreline">
              <strong>Red/white</strong>
              <span class="score">
                <span id="red-goals">0</span>–<span id="black-goals">0</span>
              </span>
              <strong>Black</strong>
            </div>
            <table class="stats-table">
              <thead><tr><th>Red/white</th><th>Statistic</th><th>Black</th></tr></thead>
              <tbody>
                <tr><td id="red-passes">0</td><th>Passes</th><td id="black-passes">0</td></tr>
                <tr><td id="red-turnovers">0</td><th>Turnovers</th><td id="black-turnovers">0</td></tr>
                <tr><td id="red-shots">0</td><th>Shots</th><td id="black-shots">0</td></tr>
                <tr><td id="red-on-target">0</td><th>On target</th><td id="black-on-target">0</td></tr>
              </tbody>
            </table>
          </aside>
        </div>
        <p class="muted replay-note" id="replay-note">
          Statistics come only from event files already written to disk.
        </p>
      </section>
    </section>
  </main>
  <script>
    const stateUrl = "/api/state";
    const REVIEW_FPS = 25;
    let state = null;
    let startInputsInitialized = false;
    let selectedIndex = 0;
    let selectedEngineIndex = null;
    const requestedReviewAudience =
      new URLSearchParams(location.search).get("mode");
    const trajectoryAuditMode =
      requestedReviewAudience === "trajectory-audit";
    if (trajectoryAuditMode) {
      document.body.classList.add("trajectory-audit-mode");
      document.getElementById("page-title").textContent =
        "Ball Trajectory Audit";
      document.getElementById("page-subtitle").textContent =
        "All sampled frames · engine, cached YOLO, and evaluation-only review";
      document.getElementById("ball-frame-review").open = true;
      document.getElementById("ball-frame-filter").value = "all";
      document.getElementById("play-ball-frame-video").hidden = false;
      const previousSample = document.getElementById("previous-ball-frame");
      previousSample.textContent = "← Previous sample (−5)";
      previousSample.setAttribute(
        "aria-label",
        "Previous sampled frame, minus five"
      );
      previousSample.title = "Previous sampled frame (−5)";
      const nextSample = document.getElementById("next-ball-frame");
      nextSample.textContent = "Next sample (+5) →";
      nextSample.setAttribute("aria-label", "Next sampled frame, plus five");
      nextSample.title = "Next sampled frame (+5)";
    }
    let reviewAudience = requestedReviewAudience === "developer"
      || (
        requestedReviewAudience !== "reviewer"
        && localStorage.getItem("football-review-audience") === "developer"
      )
      ? "developer"
      : "reviewer";
    let actionZoom = false;
    let statusTimer = null;
    let segmentPreparationPending = false;
    let runStartPending = false;
    let renderedSegmentKey = null;
    let viewMode = "normal";
    let ballTrack = null;
    let ballTrackSegmentKey = null;
    let selectedBallStateIndex = 0;
    let selectedBallTargetFrame = 0;
    let selectedRawBallFrame = 0;
    let ballFrameInteractionMode = "zoom";
    let showEngineBallMarker = true;
    let showYoloBallMarkers = true;
    let flaggedBallFrames = new Set();
    let ballCoordinateObservations = {};
    let lastBallCoordinateDecision = null;
    let selectedCoordinateBatchId = trajectoryAuditMode ? "audit" : null;
    let lastCoordinateBatchStatus = null;
    let rawBallFrameSeekPending = false;
    let rawBallFrameSeekRequest = 0;
    let pendingReviewSeconds = null;
    let pendingMissingReport = null;
    let segmentBuilderInitialized = false;
    let previousPlaybackSeconds = 0;
    const eventTriggerTimers = {copilot: null, engine: null};
    let playbackFrameRequest = null;
    let replayRunId = null;
    let replaySegmentIndex = 0;
    let repositoryGeometry = null;
    let geometry = {
      image_width: 4450,
      image_height: 2000,
      features: {},
    };
    let editingFeature = null;
    const video = document.getElementById("video");
    const timeline = document.getElementById("timeline");
    const videoShell = document.getElementById("video-shell");
    const videoMedia = document.getElementById("video-media");
    const videoEmpty = document.getElementById("video-empty");
    const segmentBuilderPanel =
      document.getElementById("segment-builder-panel");
    const ballOverlay = document.getElementById("ball-overlay");
    const ballMarker = document.getElementById("ball-marker");
    const ballCrosshair = document.getElementById("ball-crosshair");
    const ballTrajectory = document.getElementById("ball-trajectory");
    const sourceSelect = document.getElementById("source-select");
    const segmentSelect = document.getElementById("segment-select");
    const startMinute = document.getElementById("segment-start-minute");
    const startSecond = document.getElementById("segment-start-second");
    const segmentDuration = document.getElementById("segment-duration");
    const prepareButton = document.getElementById("prepare-segment");
    const processButton = document.getElementById("process-segment");
    const cameraName = document.getElementById("camera-name");
    const cameraClub = document.getElementById("camera-club");
    const cameraVenue = document.getElementById("camera-venue");
    const cameraPosition = document.getElementById("camera-position");
    const cameraSerial = document.getElementById("camera-serial");
    const cameraSample = document.getElementById("camera-sample");
    const addCameraButton = document.getElementById("add-camera");
    const cameraImportStatus =
      document.getElementById("camera-import-status");
    const segmentProgress = document.getElementById("segment-progress");
    const segmentRunStatus = document.getElementById("segment-run-status");
    const geometryPanel = document.getElementById("geometry-panel");
    const geometryAvailability =
      document.getElementById("geometry-availability");
    const geometryCanvas = document.getElementById("geometry-overlay");
    const geometryContext = geometryCanvas.getContext("2d");
    const geometryStatus = document.getElementById("geometry-status");
    const replayRunSelect = document.getElementById("replay-run");
    const replayVideo = document.getElementById("replay-video");

    function selectedSegmentKey() {
      return new URLSearchParams(location.search).get("segment") ||
        state?.segment?.key ||
        "segment-0300-020";
    }

    function developerGuidance() {
      const selectedEngine = selectedEngineIndex === null
        ? null
        : state.engineEvents?.[selectedEngineIndex];
      const draft = selectedEngine ? null : currentDraft();
      const event = selectedEngine || draft;
      const type = event?.type || "unknown";
      const details = String(
        selectedEngine?.details || draft?.evidence || ""
      );
      const slash = String.fromCharCode(92);
      const path = (...parts) => parts.join(slash);
      const segmentPath = path(
        "benchmarks",
        "alfheim",
        "generated",
        selectedSegmentKey()
      );
      const environment = '$env:PYTHONPATH="$PWD' + slash + 'src"';
      let codeArea = path("src", "football_poc", "possession.py");
      let focusedTests = [
        path("tests", "test_possession.py"),
        path("tests", "test_live_review_regressions.py")
      ];
      let change = (
        "Inspect the general possession/contact state transition. Require "
        + "observable controlled contact rather than proximity alone, and "
        + "do not key behavior to this segment, timestamp, frame, or track."
      );
      if (
        type === "foul"
        || type === "free_kick"
        || draft?.behavior?.kind === "match_state"
      ) {
        codeArea = path("src", "football_poc", "match_state.py");
        focusedTests = [
          path("tests", "test_match_state.py"),
          path("tests", "test_live_review_regressions.py")
        ];
        change = (
          "Inspect the general law-grounded match-state transition and its "
          + "evidence gate. Do not infer a referee decision that the video "
          + "does not support."
        );
      } else if (
        /deferred possession|intermediate same-team receiver/i.test(details)
      ) {
        codeArea = path("src", "football_poc", "possession.py")
          + " · deferred possession recovery and _nearby_ball_team_track()";
        change = (
          "The deferred recovery path currently promotes nearby same-team "
          + "geometry to a completed reception. Add a general controlled-touch "
          + "gate using contact geometry and post-contact ball behavior; "
          + "proximity alone must not complete a pass."
        );
      } else if (/ball track|trajectory|coordinate/i.test(details)) {
        codeArea = path("src", "football_poc", "ball_tracking.py");
        focusedTests = [
          path("tests", "test_ball_tracking.py"),
          path("tests", "test_live_review_regressions.py")
        ];
        change = (
          "Inspect the general raw-video ball-evidence path. Preserve direct "
          + "versus estimated provenance and never use review labels as input."
        );
      }
      const focused = environment + "\\npython -m pytest -q "
        + focusedTests.join(" ");
      const rebuild = environment + "\\npython "
        + path("scripts", "process-alfheim-segment.py") + " "
        + segmentPath + " --artifact-namespace live --events-only";
      const protectedTests = [
        path("tests", "test_ball_tracking.py"),
        path("tests", "test_match_state.py"),
        path("tests", "test_possession.py"),
        path("tests", "test_live_review_regressions.py")
      ];
      const protectedCommand = environment + "\\npython -m pytest -q "
        + protectedTests.join(" ");
      const acceptedNeedsEngineRecheck =
        draft?.decision?.status === "accepted"
        && draft?.comparison?.status !== "already_agrees";
      return {
        summary: selectedEngine
          ? "Selected E" + (selectedEngineIndex + 1)
            + " remains immutable engine output. Manual code and CLI work "
            + "cannot accept, reject, or confirm it."
          : draft
            ? "Selected C" + (selectedIndex + 1)
              + " keeps its decision in the normal event controls. Developer "
              + "mode only exposes implementation and rerun assistance."
            : "Select a C# or E# to see targeted developer guidance.",
        codeArea,
        change,
        commands: {
          focused,
          rebuild,
          protected: protectedCommand
        },
        canCopilotImplement:
          Boolean(acceptedNeedsEngineRecheck) && !referenceLocked(),
        copilotReason: acceptedNeedsEngineRecheck
          ? "Starts one Copilot coding handover for the already accepted C#."
          : selectedEngine
            ? "Unavailable: E# output cannot authorize an engine change. "
              + "Create and accept a supported C# requirement first."
            : draft?.decision?.status !== "accepted"
              ? "Unavailable: accept the supported C# through the event "
                + "review controls first."
              : "Unavailable: the accepted C# already agrees with the current "
                + "engine and output hashes."
      };
    }

    function renderDeveloperMode() {
      const developer = reviewAudience === "developer";
      document.getElementById("review-audience").value =
        trajectoryAuditMode ? "trajectory-audit" : reviewAudience;
      document.querySelectorAll("[data-developer-panel]").forEach(panel => {
        panel.hidden = !developer;
      });
      if (!developer || !state) return;
      const guidance = developerGuidance();
      document.querySelectorAll("[data-developer-summary]").forEach(node => {
        node.textContent = guidance.summary;
      });
      document.querySelectorAll("[data-developer-code-area]").forEach(node => {
        node.textContent = guidance.codeArea;
      });
      document.querySelectorAll("[data-developer-change]").forEach(node => {
        node.textContent = guidance.change;
      });
      Object.entries(guidance.commands).forEach(([name, command]) => {
        document.querySelectorAll(
          '[data-developer-command="' + name + '"]'
        ).forEach(node => {
          node.textContent = command;
        });
      });
      document.querySelectorAll("[data-developer-copilot]").forEach(button => {
        button.disabled =
          !guidance.canCopilotImplement
          || state.activity?.state === "working";
        button.title = guidance.copilotReason;
      });
      document.querySelectorAll("[data-developer-status]").forEach(node => {
        node.textContent = guidance.copilotReason
          + " Copying commands and refreshing output do not invoke review AI.";
      });
    }

    async function copyDeveloperCommand(name, statusNode) {
      const command = developerGuidance().commands[name];
      try {
        await navigator.clipboard.writeText(command);
        statusNode.textContent =
          "Command copied. Running it locally does not invoke review AI.";
      } catch (error) {
        statusNode.textContent =
          "Clipboard unavailable. Select and copy the command shown above.";
      }
    }

    async function refreshDeveloperOutput(statusNode) {
      statusNode.textContent =
        "Refreshing rules-engine output from disk without invoking review AI…";
      try {
        await loadState();
        statusNode.textContent =
          "Engine output refreshed from disk. No review decision was changed.";
      } catch (error) {
        statusNode.textContent = "Refresh failed: " + error.message;
      }
    }

    function cloneGeometry(value) {
      return JSON.parse(JSON.stringify(value));
    }

    function mediaLayout() {
      const widthAvailable = geometryCanvas.clientWidth;
      const heightAvailable = geometryCanvas.clientHeight;
      const mediaAspect = (video.videoWidth || geometry.image_width) /
        (video.videoHeight || geometry.image_height);
      const stageAspect = widthAvailable / Math.max(1, heightAvailable);
      const width = stageAspect > mediaAspect
        ? heightAvailable * mediaAspect
        : widthAvailable;
      const height = stageAspect > mediaAspect
        ? heightAvailable
        : widthAvailable / mediaAspect;
      return {
        x: (widthAvailable - width) / 2,
        y: (heightAvailable - height) / 2,
        width,
        height,
        widthAvailable,
        heightAvailable,
      };
    }

    function drawGeometry() {
      const layout = mediaLayout();
      if (!layout.widthAvailable || !layout.heightAvailable) return;
      const ratio = window.devicePixelRatio || 1;
      geometryCanvas.width = Math.max(
        1,
        Math.round(layout.widthAvailable * ratio),
      );
      geometryCanvas.height = Math.max(
        1,
        Math.round(layout.heightAvailable * ratio),
      );
      geometryContext.setTransform(ratio, 0, 0, ratio, 0, 0);
      geometryContext.clearRect(
        0,
        0,
        layout.widthAvailable,
        layout.heightAvailable,
      );
      const project = (point) => [
        layout.x + point[0] * layout.width / geometry.image_width,
        layout.y + point[1] * layout.height / geometry.image_height,
      ];
      const innovation =
        document.documentElement.dataset.appTheme === "innovation";
      const touchlineColor = innovation ? "#a63f98" : "#ffd33d";
      const goalLineColor = innovation ? "#a63f98" : "#ff9f1c";
      const goalFrameColor = innovation ? "#e4a5da" : "#00e5ff";
      const drawLine = (
        points,
        color,
        width,
        dashed = false,
        closed = false,
      ) => {
        if (!Array.isArray(points) || points.length < 2) return;
        geometryContext.strokeStyle = color;
        geometryContext.lineWidth = width;
        geometryContext.setLineDash(dashed ? [8, 5] : []);
        geometryContext.beginPath();
        points.forEach((point, index) => {
          const [x, y] = project(point);
          if (index === 0) geometryContext.moveTo(x, y);
          else geometryContext.lineTo(x, y);
        });
        if (closed) geometryContext.closePath();
        geometryContext.stroke();
        geometryContext.setLineDash([]);
        points.forEach((point) => {
          const [x, y] = project(point);
          geometryContext.fillStyle = color;
          geometryContext.beginPath();
          geometryContext.arc(x, y, editingFeature ? 2.5 : 1.5, 0, Math.PI * 2);
          geometryContext.fill();
        });
      };
      if (document.getElementById("show-pitch").checked) {
        drawLine(geometry.features.near_touchline, touchlineColor, 2, true);
        drawLine(geometry.features.far_touchline, touchlineColor, 2, true);
        drawLine(geometry.features.left_goal_line, goalLineColor, 2, true);
        drawLine(geometry.features.right_goal_line, goalLineColor, 2, true);
      }
      if (document.getElementById("show-goals").checked) {
        drawLine(
          geometry.features.left_goal_mouth,
          goalFrameColor,
          2.5,
          false,
          true,
        );
        drawLine(
          geometry.features.right_goal_mouth,
          goalFrameColor,
          2.5,
          false,
          true,
        );
      }
    }

    async function cancelAdjustment() {
      const response = await fetch("/api/cancel-adjustment", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          segment: selectedSegmentKey(),
          index: selectedIndex,
          reason: "Stopped by the user from the review panel.",
        }),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || "Could not stop adjustment review");
      }
      state = result;
      render();
    }

    async function submitEngineConversationMessage() {
      return sendEngineConversationMessage(
        "fullscreen-message",
        "fullscreen-chat-status",
        "fullscreen-send-message"
      );
    }

    async function sendEngineConversationMessage(
      textareaId,
      statusId,
      buttonId
    ) {
      const textarea = document.getElementById(textareaId);
      const status = document.getElementById(statusId);
      const send = document.getElementById(buttonId);
      const engine = state.engineEvents?.[selectedEngineIndex];
      const text = textarea.value.trim();
      if (!engine || !text) return;
      send.disabled = true;
      status.textContent =
        "Sending this E" + (selectedEngineIndex + 1)
        + " event question…";
      try {
        const response = await fetch("/api/engine-message", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            segment: selectedSegmentKey(),
            index: selectedEngineIndex,
            text,
          }),
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not send E# question");
        }
        textarea.value = "";
        status.textContent =
          "Sent. Copilot will reply in this E# event conversation.";
        await loadState();
      } catch (error) {
        status.textContent = error.message;
      } finally {
        send.disabled = state.activity?.state === "working";
      }
    }

    async function persistGeometry() {
      if (
        state.segment.datasetId !== "soccertrack-v2"
        && !state.segment.datasetId.startsWith("custom-")
      ) return;
      const response = await fetch("/api/calibration", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          segment: state.segment.key,
          calibration: geometry
        })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Calibration could not be saved");
      }
      geometry = payload;
      await loadState();
    }

    function saveGeometry() {
      const key = state.segment.calibrationId + "-geometry-v1";
      localStorage.setItem(key, JSON.stringify(geometry));
      drawGeometry();
      return persistGeometry().catch(error => {
        geometryStatus.textContent =
          "Calibration saved in this browser, but processing is still locked: " +
          error.message;
        throw error;
      });
    }

    async function loadGeometry() {
      if (!state.segment.videoUrl) {
        geometryPanel.open = false;
        geometryStatus.textContent =
          "Prepare a video segment for this camera before calibrating it.";
        return;
      }
      try {
        const segment = selectedSegmentKey();
        const response = await fetch(
          "/api/calibration?segment=" + encodeURIComponent(segment),
          {cache: "no-store"}
        );
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || "Calibration is unavailable");
        }
        repositoryGeometry = payload;
        const storageKey = state.segment.calibrationId + "-geometry-v1";
        const saved = localStorage.getItem(storageKey);
        geometry = saved ? JSON.parse(saved) : cloneGeometry(repositoryGeometry);
        geometry.features ||= {};
        if (
          saved
          && (
            state.segment.datasetId === "soccertrack-v2"
            || state.segment.datasetId.startsWith("custom-")
          )
        ) {
          await persistGeometry();
        }
        geometryStatus.textContent = saved
          ? "Loaded the locally saved calibration for this camera."
          : payload.calibration_status === "not_calibrated"
            ? "No SoccerTrack calibration saved yet. Draw each pitch edge and both goals."
            : "Loaded the repository calibration for this camera.";
        drawGeometry();
      } catch (error) {
        geometryStatus.textContent =
          "Camera calibration unavailable: " + error.message;
      }
    }

    function ballCoordinatesNeedReview(segment = state?.segment) {
      return Boolean(
        segment?.key === state?.segment?.key
        && !["verified", "finalized"].includes(
          state?.coordinateReview?.status
        )
        && segment?.state === "failed"
        && segment?.ballTrackAvailable
        && /ball provenance review required/i.test(
          segment?.statusMessage || ""
        )
      );
    }

    function statusLabel(status, segment = null) {
      if (
        segment?.key === state?.segment?.key
        && state?.coordinateReview?.status === "verified"
      ) {
        return "Ball coordinate gate passed";
      }
      if (status === "failed" && ballCoordinatesNeedReview(segment)) {
        return "Ball coordinates need review";
      }
      return {
        passed: "Passed",
        published_stale: "Published · engine changed",
        in_review: "In review",
        ai_ready: "AI ready",
        prepared: "Prepared",
        processing: "AI processing",
        detections_ready: "Detections ready",
        building: "Building events",
        failed: "AI failed"
      }[status] || status.replaceAll("_", " ");
    }

    function trackerIteration(segment) {
      const provenance = segment?.runProvenance || {};
      const explicit = provenance.tracker_iteration;
      if (Number.isInteger(Number(explicit))) {
        return "iteration " + Number(explicit);
      }
      const match = String(provenance.workflow || "").match(
        /iteration[_ -]?(\\d+)/i
      );
      return match ? "iteration " + match[1] : "iteration unavailable";
    }

    function ballCoordinateCoverage(provenance) {
      const direct = Number(provenance?.direct_frame_count);
      const total = Number(provenance?.sampled_frame_count);
      const fraction = Number(provenance?.direct_provenance);
      if (
        !Number.isFinite(direct)
        || !Number.isFinite(total)
        || total <= 0
        || !Number.isFinite(fraction)
      ) {
        return "Ball coordinates: unavailable";
      }
      const percentage = Math.round(fraction * 1000) / 10;
      return "Ball coordinates: " + percentage.toLocaleString(undefined, {
        maximumFractionDigits: 1
      }) + "% · " + direct + "/" + total + " direct";
    }

    function friendlyRunFailure(message) {
      const detail = String(message || "");
      if (
        detail.includes("player_tracking_cli")
        && detail.includes("--ball-state-estimates")
      ) {
        return "The previous run stopped during player tracking because of " +
          "an obsolete command option. That issue is fixed; click Retry " +
          "Segment from Start.";
      }
      if (detail.includes("returned non-zero exit status")) {
        return "A local processing stage failed. Retry the segment or inspect " +
          "analysis.log for technical details.";
      }
      return detail || "See analysis.log for technical details.";
    }

    function shortVersion(value) {
      return String(value || "unavailable").slice(0, 12);
    }

    function referenceLocked() {
      return Boolean(
        state.publication?.published
        || state.segment?.validationStatus === "passed"
      );
    }

    function applyPassedSegmentLock() {
      if (!referenceLocked() || trajectoryAuditMode) return;
      const allowedViewerControls = [
        "#review-audience",
        "#source-select",
        "#segment-select",
        "#segment-start-minute",
        "#segment-start-second",
        "#segment-duration",
        "#prepare-segment",
        "#process-segment",
        "#camera-club",
        "#camera-venue",
        "#camera-position",
        "#camera-name",
        "#camera-serial",
        "#camera-sample",
        "#add-camera",
        "#show-pitch",
        "#show-goals",
        "#geometry-feature",
        "#edit-geometry",
        "#undo-geometry",
        "#finish-geometry",
        "#save-geometry",
        "#restore-geometry",
        "#export-geometry",
        "#previous-event",
        "#next-event",
        "#previous-frame",
        "#next-frame",
        "#timeline",
        "#playback-speed",
        "#toggle-event-panel",
        "#show-ball-frames",
        "#zoom-action",
        "#enlarge",
        "#close-ball-frame-modal",
        "#previous-ball-review-frame",
        "#previous-ball-frame",
        "#target-ball-frame",
        "#zoom-ball-frame",
        "#reset-ball-frame-zoom",
        "#next-ball-frame",
        "#next-ball-review-frame",
        "#close-ball-coordinate-review",
        "#replay-run",
        "#replay-play",
        "#replay-restart",
        "[data-view-mode]",
        ".comparison-event",
        ".compact-engine-spot",
        ".ball-frame-open",
        ".ball-frame-flag",
        "#ball-frame-filter",
      ].join(",");
      document.querySelectorAll("button, input, textarea, select").forEach(
        control => {
          if (control.matches(allowedViewerControls)) return;
          control.disabled = true;
          control.title = "This segment has passed and is locked.";
        }
      );
    }

    function syncStartInputs(segment) {
      const seconds = Number(segment.startSeconds);
      startMinute.value = String(Math.floor(seconds / 60));
      startSecond.value = String(Math.floor(seconds % 60));
      segmentDuration.value = String(segment.durationSeconds);
    }

    function scheduleStatusRefresh() {
      clearTimeout(statusTimer);
      const running = segmentRunActive();
      if (!running) return;
      statusTimer = setTimeout(() => {
        loadState().catch(error => {
          segmentRunStatus.textContent =
            "AI status unavailable: " + error.message;
        });
      }, 2000);
    }

    function segmentRunActive() {
      return segmentPreparationPending
        || runStartPending
        || ["processing", "detections_ready", "building"]
          .includes(state.segment.state);
    }

    function applySegmentProcessingLock() {
      const running = segmentRunActive() && !trajectoryAuditMode;
      const reviewSection = segmentBuilderPanel.closest(".review");
      const layout = document.querySelector(".layout");
      const downstream = [
        ...Array.from(reviewSection.children).filter(
          child => child !== segmentBuilderPanel
        ),
        ...Array.from(layout.children).filter(
          child => child !== reviewSection
        )
      ];
      downstream.forEach(section => {
        section.inert = running;
        section.classList.toggle("segment-processing-locked", running);
        section.setAttribute("aria-disabled", String(running));
      });
    }

    function segmentInputsMatchSelection() {
      const requestedStart =
        Number(startMinute.value) * 60 + Number(startSecond.value);
      return Number.isFinite(requestedStart)
        && requestedStart === Number(state.segment.startSeconds)
        && Number(segmentDuration.value) ===
          Number(state.segment.durationSeconds);
    }

    function renderRunControls() {
      const segment = state.segment;
      const running = segmentRunActive();
      const selectedVideoPrepared = segmentInputsMatchSelection();
      if (!segmentBuilderInitialized) {
        segmentBuilderPanel.open =
          segment.state !== "ready" && segment.validationStatus !== "passed";
        segmentBuilderInitialized = true;
      }
      prepareButton.hidden = selectedVideoPrepared;
      processButton.hidden = !selectedVideoPrepared;
      prepareButton.disabled = running || !segment.preparationSupported;
      processButton.disabled =
        running || !segment.processingSupported || referenceLocked();
      processButton.textContent = referenceLocked()
        ? "Passed Segment Locked"
        : segment.state === "ready"
          ? "Rerun Segment from Start"
          : segment.state === "failed" && segment.recoveryAvailable
            ? "Resume from Saved Detections"
          : segment.state === "failed"
            ? "Retry Segment from Start"
            : "Start AI";
      segmentProgress.hidden = !running;
      if (running && segment.expectedFrames > 0) {
        segmentProgress.max = segment.expectedFrames;
        segmentProgress.value = segment.processedFrames;
      } else if (running) {
        segmentProgress.removeAttribute("value");
      }
      if (segment.validationStatus === "passed") {
        segmentRunStatus.textContent =
          "Validated reference and AI events are ready for review.";
      } else if (segment.state === "ready") {
        const report = segment.performance;
        const coverage = ballCoordinateCoverage(state.ballProvenance);
        const timing = report
          ? " Cold run: " + Number(report.wall_time_seconds).toFixed(1) +
            "s on " + (report.host?.processor || "the current CPU") + "."
          : "";
        const capacity = report?.gpu_guidance
          ? " GPU guidance: " + report.gpu_guidance.planning_tier + ", " +
            report.gpu_guidance.minimum_vram_gb + " GB+ VRAM; requires " +
            Number(
              report.gpu_guidance.required_measured_end_to_end_speedup
            ).toFixed(2) + "x measured end-to-end speedup. Benchmark required."
          : "";
        segmentRunStatus.textContent = "Run complete. " + coverage + ". " + (
          state.drafts.length
            ? state.drafts.length + " AI event candidate(s) ready for review."
            : (state.engineEvents || []).length
              ? "Engine completed with " + state.engineEvents.length
                + " event candidate(s). Independent Copilot proposals have "
                + "not been created yet."
              : "Engine completed and produced no event candidates. "
                + "Independent Copilot proposals have not been created yet."
        ) + timing + capacity;
      } else if (segment.state === "processing") {
        const provenance = segment.runProvenance;
        const elapsed = Number(provenance?.elapsed_seconds || 0);
        segmentRunStatus.textContent = (
          segment.expectedFrames
            ? "Step 1 of 6 — Detecting raw-video frames: " +
              segment.processedFrames + "/" +
              segment.expectedFrames + " sampled frames"
            : "Step 1 of 6 — Detecting raw-video frames locally"
        ) + (elapsed ? " · " + elapsed.toFixed(1) + "s elapsed" : "") +
          ". No prior detections, ball/player tracks, events, review labels, " +
          "or provider annotations are used. Next: build ball coordinates.";
      } else if (segment.state === "detections_ready") {
        segmentRunStatus.textContent =
          "Step 1 of 6 complete — detections are ready. " +
          "Next: build ball coordinates.";
      } else if (segment.state === "building") {
        const timing = segment.stageTiming;
        const stageElapsed = timing?.startedAtUtc
          ? Math.max(
              0,
              (Date.now() - Date.parse(timing.startedAtUtc)) / 1000
            )
          : 0;
        const estimate = Number(timing?.estimatedSeconds || 0);
        const remaining = Math.max(0, estimate - stageElapsed);
        const timingText = estimate
          ? stageElapsed < estimate
            ? " Stage elapsed: " + formatReplayTime(stageElapsed) +
              " · estimated remaining: about " +
              formatReplayTime(remaining) +
              " (benchmark-based, not a deadline)."
            : " Stage elapsed: " + formatReplayTime(stageElapsed) +
              " · the benchmark estimate has been exceeded, but the local " +
              "process is still active."
          : stageElapsed
            ? " Stage elapsed: " + formatReplayTime(stageElapsed) + "."
            : "";
        const stage = {
          ball_track: [
            "Step 2 of 6 — Building ball coordinates",
            "Next: build player tracks and team assignments."
          ],
          tracking: [
            "Step 3 of 6 — Building player tracks and team assignments",
            "Next: validate at least 90% direct ball coordinates."
          ],
          provenance_gate: [
            "Step 4 of 6 — Validating direct ball coordinates (minimum 90%)",
            "Next: infer football events if validation passes."
          ],
          events: [
            "Step 5 of 6 — Inferring football events",
            "Next: publish the local event output."
          ],
          publishing: [
            "Step 6 of 6 — Publishing local event output",
            "Next: unlock the completed segment for review."
          ]
        }[segment.stage] || [
          "Building tracks and event candidates",
          "The next stage will appear here."
        ];
        segmentRunStatus.textContent = stage[0] + ". " +
          (segment.statusMessage || "Local processing is still running.");
        segmentRunStatus.textContent += timingText + " " + stage[1];
      } else if (segment.state === "failed") {
        segmentRunStatus.textContent = ballCoordinatesNeedReview(segment)
          ? "Ball coordinates need review: tracking completed with " +
            ballCoordinateCoverage(state.ballProvenance)
              .replace("Ball coordinates: ", "") +
            ". Recover every additional frame supported by the raw video. " +
            "90% is the minimum gate, not the target."
          : "AI failed: " + friendlyRunFailure(segment.statusMessage);
      } else if (!segment.processingSupported) {
        segmentRunStatus.textContent =
          "Calibrate this camera first. AI remains disabled until its own " +
          "saved calibration is ready.";
      } else {
        segmentRunStatus.textContent =
          "Preparation complete. No AI has run. Next: click Start AI.";
      }
      applySegmentProcessingLock();
      scheduleStatusRefresh();
    }

    function renderAiGate() {
      const ready = (
        state.segment.validated
        || state.segment.validationStatus === "in_review"
        || state.coordinateReview?.status === "finalized"
      )
        && !segmentPreparationPending
        && !runStartPending;
      document.querySelectorAll("[data-ai-gated]").forEach(section => {
        section.inert = !ready;
        section.classList.toggle("ai-locked", !ready);
        section.setAttribute("aria-disabled", String(!ready));
      });
    }

    function renderCalibrationAvailability() {
      const available = Boolean(state.segment.videoUrl);
      geometryPanel.inert = !available;
      geometryPanel.classList.toggle("ai-locked", !available);
      geometryPanel.setAttribute("aria-disabled", String(!available));
      geometryPanel.title = available
        ? ""
        : "Prepare a video segment for this camera before calibrating it.";
      geometryAvailability.textContent = available
        ? "Saved pitch edges and goal frames"
        : "Prepare a video segment first";
      if (!available) geometryPanel.open = false;
    }

    function renderSegments() {
      const selected = state.segment;
      const selectionChanged = renderedSegmentKey !== selected.key;
      const sources = Array.from(new Map(
        state.segments.map(segment => [
          segment.datasetId,
          segment.datasetName
        ])
      ));
      sourceSelect.replaceChildren(...sources.map(([id, name]) => {
        const option = document.createElement("option");
        option.value = id;
        option.textContent = name;
        return option;
      }));
      sourceSelect.value = selected.datasetId;
      const visibleSegments = state.segments.filter(
        segment => segment.datasetId === selected.datasetId
      );
      const existing = new Map(
        Array.from(segmentSelect.options).map(option => [option.value, option])
      );
      const options = visibleSegments.map(segment => {
        const option = existing.get(segment.key) ||
          document.createElement("option");
        const labels = [
          segment.timeLabel,
          statusLabel(segment.validationStatus, segment),
          segment.protected ? "Protected" : ""
        ].filter(Boolean);
        option.value = segment.key;
        option.textContent = labels.join(" · ");
        return option;
      });
      segmentSelect.replaceChildren(...options);
      segmentSelect.value = selected.key;
      if (selectionChanged || !startInputsInitialized) {
        syncStartInputs(selected);
        startInputsInitialized = true;
      }
      renderedSegmentKey = selected.key;
      const badge = document.getElementById("segment-status");
      badge.className = "segment-status " + (
        state.coordinateReview?.status === "verified"
          ? "coordinate-verified"
          : ballCoordinatesNeedReview(selected)
          ? "coordinates-review"
          : selected.validationStatus
      );
      badge.textContent = statusLabel(selected.validationStatus, selected);
      document.getElementById("tracker-version").textContent =
        "Ball tracker: " + trackerIteration(selected) + " · " +
        shortVersion(state.componentVersions?.tracker);
      const ballCoverage = ballCoordinateCoverage(state.ballProvenance);
      document.getElementById("ball-coordinate-coverage").textContent =
        ballCoverage;
      document.getElementById("fullscreen-ball-coverage").textContent =
        ballCoverage;
      renderBallFrames();
      renderBallCoordinateReviewMessages();
      document.getElementById("rules-version").textContent =
        "Rules engine: " +
        shortVersion(state.componentVersions?.rulesEngine);
      document.getElementById("source-attribution").textContent =
        selected.attribution || "";
      const summaries = new Map(
        (state.sharedReviewStatus || []).map(summary => [
          summary.segment,
          summary
        ])
      );
      document.getElementById("shared-review-status").replaceChildren(
        ...state.segments.map(segment => {
          const summary = summaries.get(segment.key) || {};
          const reviewed = Number(summary.reviewed || 0);
          const proposalCount = Number(summary.proposalCount || 0);
          const values = [
            segment.datasetName + " · " + segment.timeLabel,
            proposalCount
              ? reviewed + "/" + proposalCount + " reviewed · "
                + Number(summary.accepted || 0) + " accepted · "
                + Number(summary.rejected || 0) + " rejected"
              : reviewed ? reviewed + " reviewed" : "Not started",
            String(summary.regression || "not_run").replaceAll("_", " "),
            summary.published
              ? "Published"
              : summary.blockers?.length
                ? summary.blockers.length + " gate blocker(s)"
                : "Ready",
            summary.updatedAt
              ? new Date(summary.updatedAt).toLocaleString()
              : "—"
          ];
          const row = document.createElement("tr");
          for (const value of values) {
            const cell = document.createElement("td");
            cell.textContent = value;
            row.append(cell);
          }
          row.classList.toggle("selected", segment.key === selected.key);
          return row;
        })
      );
      if (viewMode === "ai" && !selected.trackingUrl) viewMode = "normal";
      const selectedVideoUrl = viewMode === "ai"
        ? selected.trackingUrl
        : selected.videoUrl;
      if (selectedVideoUrl && video.src !== selectedVideoUrl) {
        replaceVideoSource(selectedVideoUrl);
      } else if (!selectedVideoUrl) {
        clearVideoSource();
      }
      video.setAttribute(
        "aria-label",
        selected.datasetName + " " + selected.timeLabel + " " +
        (viewMode === "ai" ? "AI tracking" : "footage")
      );
      timeline.max = String(selected.durationSeconds);
      renderCalibrationAvailability();
      renderViewMode();
      renderClipConversationControls();
      renderRunControls();
      renderAiGate();
    }

    function renderClipConversationControls() {
      const reviewBusy = state.activity?.state === "working";
      const selectedEngine = selectedEngineIndex === null
        ? null
        : state.engineEvents?.[selectedEngineIndex];
      const planButton = document.getElementById("send-clip-plan");
      const autopilotButton = document.getElementById("send-clip-autopilot");
      const showGeneral = document.getElementById(
        "show-general-clip-conversation"
      );
      const manualToggle = document.getElementById("toggle-manual-review");
      const manualFields = document.getElementById("manual-review-fields");
      const scope = document.getElementById("clip-message-scope").value;
      const seconds = Math.min(60, Math.max(0, video.currentTime || 0));
      const clipTarget = scope === "current_time"
        ? seconds.toFixed(2) + "s ±2s"
        : "entire clip";
      const flaggedTarget = flaggedBallFrames.size
        ? flaggedBallFrames.size + " flagged ball frame"
          + (flaggedBallFrames.size === 1 ? "" : "s")
        : clipTarget;
      planButton.disabled = reviewBusy;
      autopilotButton.disabled = reviewBusy || referenceLocked();
      planButton.textContent = selectedEngine
        ? "Ask Copilot about E" + (selectedEngineIndex + 1) + " (Plan mode)"
        : "Ask Copilot about " + flaggedTarget + " (Plan mode)";
      autopilotButton.textContent = selectedEngine
        ? selectedEngine.review?.status === "confirmed"
          && selectedEngine.review.fresh
          ? "Re-verify E" + (selectedEngineIndex + 1) + " (Autopilot)"
          : selectedEngine.review?.status === "not_confirmed"
            && selectedEngine.review.fresh
            ? "Re-verify unsupported E" + (selectedEngineIndex + 1)
              + " (Autopilot)"
          : selectedEngine.review?.status === "confirmed"
            ? "Verify stale E" + (selectedEngineIndex + 1) + " (Autopilot)"
            : selectedEngine.review?.status === "not_confirmed"
              ? "Re-verify stale unsupported E" + (selectedEngineIndex + 1)
                + " (Autopilot)"
            : "Verify E" + (selectedEngineIndex + 1) + " (Autopilot)"
        : "Ask Copilot about " + flaggedTarget + " (Autopilot)";
      document.getElementById("clip-scope-field").hidden =
        Boolean(selectedEngine);
      showGeneral.hidden = !selectedEngine;
      manualToggle.hidden = Boolean(selectedEngine);
      manualToggle.disabled = reviewBusy || referenceLocked();
      if (selectedEngine) manualFields.hidden = true;
      document.getElementById("clip-conversation-note").textContent =
        selectedEngine
          ? "E" + (selectedEngineIndex + 1)
            + " is rules-engine output. Ask a question in Plan mode, then "
            + "verify or re-verify it independently in Autopilot. "
            + "This does not edit the E# or automatically create a C#."
          : "General clip messages stay separate from every event conversation.";
      const candidate = state.pendingMissingCandidate;
      const plan = document.getElementById("missing-event-plan");
      const confirm = document.getElementById("confirm-missing-event");
      plan.hidden =
        Boolean(selectedEngine) || !candidate || candidate.supported === null;
      if (!plan.hidden) {
        plan.className = "missing-event-plan " +
          (candidate.supported ? "supported" : "unsupported");
        document.getElementById("missing-plan-title").textContent =
          candidate.supported
            ? "Copilot Plan supports this candidate"
            : "Copilot Plan does not support this candidate";
        document.getElementById("missing-plan-detail").textContent =
          candidate.supported
            ? candidate.evidence + " Proposed rule: " + candidate.rule
            : candidate.reason;
        confirm.hidden = !candidate.supported;
        confirm.disabled =
          reviewBusy
          || referenceLocked()
          || Boolean(candidate.autopilotAuthorizedAt);
      }
      if (referenceLocked() && candidate?.supported) {
        document.getElementById("missing-event-status").textContent =
          "This passed reference is locked; reopen it before adding a proposal.";
      }
    }

    function replaceVideoSource(source) {
      const position = pendingReviewSeconds ?? video.currentTime ?? 0;
      const wasPlaying = !video.paused;
      video.hidden = true;
      videoEmpty.hidden = false;
      videoEmpty.textContent = "Loading the selected camera segment…";
      video.src = source;
      video.addEventListener("loadedmetadata", () => {
        video.hidden = false;
        videoEmpty.hidden = true;
        const target = pendingReviewSeconds ?? position;
        video.currentTime = Math.min(target, video.duration || target);
        pendingReviewSeconds = null;
        if (wasPlaying) void video.play();
        updateBallMarker();
      }, {once: true});
    }

    function clearVideoSource() {
      video.pause();
      video.removeAttribute("src");
      video.load();
      video.hidden = true;
      videoEmpty.hidden = false;
      videoEmpty.textContent =
        "No merged review segment is available for this camera.";
    }

    function inspectVideoFile(file) {
      return new Promise((resolve, reject) => {
        const probe = document.createElement("video");
        const objectUrl = URL.createObjectURL(file);
        probe.preload = "metadata";
        probe.addEventListener("loadedmetadata", () => {
          const metadata = {
            duration: probe.duration,
            width: probe.videoWidth,
            height: probe.videoHeight
          };
          URL.revokeObjectURL(objectUrl);
          resolve(metadata);
        }, {once: true});
        probe.addEventListener("error", () => {
          URL.revokeObjectURL(objectUrl);
          reject(new Error("The selected video could not be read"));
        }, {once: true});
        probe.src = objectUrl;
      });
    }

    function nearestBallPoint(seconds) {
      const points = ballTrack?.points || [];
      if (!points.length) return null;
      const closest = points.reduce((best, point) =>
        Math.abs(point[1] - seconds) < Math.abs(best[1] - seconds)
          ? point : best
      );
      return Math.abs(closest[1] - seconds) <= 0.08 ? closest : null;
    }

    function ballStateLabel(point) {
      return point.direct ? "Direct" : "Estimated";
    }

    function ballFrameFlagStorageKey() {
      return "football-ball-frame-flags-v2-" + state.segment.key + "-"
        + (selectedCoordinateBatchId || "unassigned");
    }

    function ballCoordinateObservationStorageKey() {
      return "football-ball-coordinate-observations-v2-" + state.segment.key
        + "-" + (selectedCoordinateBatchId || "unassigned");
    }

    function loadBallFrameFlags() {
      if (trajectoryAuditMode) {
        selectedCoordinateBatchId = "audit";
        flaggedBallFrames = new Set(
          (ballTrack?.states || []).map(point => point.frame)
        );
        const localAuditObservations = JSON.parse(
          localStorage.getItem(ballCoordinateObservationStorageKey()) || "{}"
        );
        ballCoordinateObservations = {
          ...localAuditObservations,
          ...(state.trajectoryAudit?.observations || {})
        };
        localStorage.setItem(
          ballCoordinateObservationStorageKey(),
          JSON.stringify(ballCoordinateObservations)
        );
        return;
      }
      const batches = state.coordinateReview?.batches || [];
      const selectedBatch = batches.find(
        batch => batch.id === selectedCoordinateBatchId
      ) || batches.find(
        batch => batch.id === state.coordinateReview?.activeBatchId
      ) || batches.at(-1);
      selectedCoordinateBatchId = selectedBatch?.id || null;
      const saved = JSON.parse(
        localStorage.getItem(ballFrameFlagStorageKey())
        || (
          selectedBatch?.number === 1
            ? localStorage.getItem(
                "football-ball-frame-flags-v1-" + state.segment.key
              )
            : null
        )
        || "[]"
      );
      const diagnosticFrames = selectedBatch?.frames
        || (
          state.ballRecoveryDiagnostic?.batch_review_completed
            ? state.ballRecoveryDiagnostic.original_review_frames || []
            : []
        );
      const persistedFrames = state.coordinateReview?.flaggedFrames || [];
      const initialFrames = diagnosticFrames.length
        ? diagnosticFrames
        : persistedFrames;
      flaggedBallFrames = new Set(
        (
          selectedBatch?.status === "ready" && initialFrames.length
            ? initialFrames
            : saved.length ? saved : initialFrames
        ).filter(
          frame => Number.isInteger(frame)
        )
      );
      ballCoordinateObservations = JSON.parse(
        localStorage.getItem(ballCoordinateObservationStorageKey())
        || (
          selectedBatch?.number === 1
            ? localStorage.getItem(
                "football-ball-coordinate-observations-v1-"
                + state.segment.key
              )
            : null
        )
        || "{}"
      );
      ballCoordinateObservations = {
        ...(selectedBatch?.observations || {}),
        ...ballCoordinateObservations
      };
    }

    function selectedCoordinateBatch() {
      if (selectedCoordinateBatchId === "all" || trajectoryAuditMode) {
        return null;
      }
      const batches = state.coordinateReview?.batches || [];
      return batches.find(batch => batch.id === selectedCoordinateBatchId)
        || batches.find(
          batch => batch.id === state.coordinateReview?.activeBatchId
        )
        || batches.at(-1)
        || null;
    }

    function coordinateBatchLocked(batch = selectedCoordinateBatch()) {
      return [
        "working",
        "review_completed",
        "code_fix_completed",
        "tests_completed"
      ].includes(batch?.status);
    }

    function coordinateBatchStatusLabel(status) {
      return {
        ready: "Ready",
        working: "Working",
        review_completed: "Review complete",
        code_fix_completed: "Code fix complete",
        tests_completed: "Tests complete",
        rerun_started: "Rerun in progress",
        done: "Done",
        failed: "Failed"
      }[status] || "Pending";
    }

    function formatCoordinateBatchTime(value) {
      if (!value) return "Pending";
      return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "medium"
      }).format(new Date(value));
    }

    async function saveBallFrameFlags() {
      localStorage.setItem(
        ballFrameFlagStorageKey(),
        JSON.stringify([...flaggedBallFrames].sort((a, b) => a - b))
      );
      localStorage.setItem(
        ballCoordinateObservationStorageKey(),
        JSON.stringify(ballCoordinateObservations)
      );
      if (trajectoryAuditMode) {
        const response = await fetch("/api/trajectory-audit-draft", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            segment: selectedSegmentKey(),
            observations: Object.values(ballCoordinateObservations)
          })
        });
        if (!response.ok) {
          const result = await response.json();
          throw new Error(
            result.error || "Could not save trajectory audit decisions"
          );
        }
        state.trajectoryAudit = {
          observations: {...ballCoordinateObservations},
          updatedAt: new Date().toISOString()
        };
        return;
      }
      const batch = selectedCoordinateBatch();
      if (!batch || batch.status !== "ready") return;
      const response = await fetch("/api/coordinate-batch-draft", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          segment: selectedSegmentKey(),
          batchId: batch.id,
          frames: [...flaggedBallFrames].sort((left, right) => left - right),
          observations: Object.values(ballCoordinateObservations)
        })
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(result.error || "Could not save coordinate decisions");
      }
    }

    function downloadTrajectoryAudit() {
      const integrityRejected = new Set(
        ballTrack?.integrityRejectedFrames || []
      );
      const payload = {
        schemaVersion: 1,
        purpose: "evaluation_only_ball_trajectory_audit",
        segment: state.segment.key,
        generatedAt: new Date().toISOString(),
        runtimeOutputReadOnly: true,
        frames: (ballTrack?.states || []).map(point => ({
          ...point,
          auditStatus: integrityRejected.has(point.frame)
            ? "integrity_demoted"
            : point.direct ? "direct" : "needs_review",
          yoloCandidates:
            ballTrack?.yoloCandidates?.[String(point.frame)] || [],
          review: ballCoordinateObservations[String(point.frame)] || null
        }))
      };
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob(
        [JSON.stringify(payload, null, 2) + "\\n"],
        {type: "application/json"}
      ));
      link.download = state.segment.key + "-trajectory-audit.json";
      link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 0);
    }

    function visibleBallStates() {
      const points = ballTrack?.states || [];
      if (!trajectoryAuditMode && selectedCoordinateBatchId === "all") {
        return points.filter(point => point.direct);
      }
      const filter = document.getElementById("ball-frame-filter").value;
      if (filter === "integrity") {
        const rejected = new Set(ballTrack?.integrityRejectedFrames || []);
        return points.filter(point => rejected.has(point.frame));
      }
      const diagnostic = state.ballRecoveryDiagnostic;
      const diagnosticFrames = new Set([
        ...(diagnostic?.original_review_frames || []),
        ...(diagnostic?.new_regression_frames || [])
      ]);
      return filter === "estimated"
        ? points.filter(point => !point.direct)
        : filter === "flagged"
          ? points.filter(point => flaggedBallFrames.has(point.frame))
        : filter === "diagnostic"
          ? points.filter(point => diagnosticFrames.has(point.frame))
        : filter === "direct"
          ? points.filter(point => point.direct)
          : points;
    }

    function ballDiagnosticStatus(frame) {
      const point = (ballTrack?.states || []).find(
        candidate => candidate.frame === frame
      );
      if (point?.state === "engine_pending") {
        return {
          label: "Engine coordinate pending",
          className: "estimated"
        };
      }
      if ((ballTrack?.integrityRejectedFrames || []).includes(frame)) {
        return {
          label: "Integrity-demoted · needs review",
          className: "estimated"
        };
      }
      const batch = selectedCoordinateBatch();
      const batchResult = batch?.frameResults?.[String(frame)]?.status;
      if (batchResult) {
        return {
          label: {
            fixed: "Fixed · direct in persisted rerun",
            unresolved: "Reviewed · still unresolved by tracker",
            regressed: "Regressed in persisted rerun",
            unchanged_direct: "Direct · unchanged"
          }[batchResult] || batchResult.replaceAll("_", " "),
          className: ["fixed", "unchanged_direct"].includes(batchResult)
            ? "direct"
            : "estimated"
        };
      }
      const diagnostic = state.ballRecoveryDiagnostic;
      if (diagnostic?.status !== "focused_unpersisted") return null;
      if (
        (diagnostic.recovered_original_review_frames || []).includes(frame)
      ) {
        return {
          label: "Recovered in focused diagnostic",
          className: "direct"
        };
      }
      if ((diagnostic.new_regression_frames || []).includes(frame)) {
        return {
          label: "New regression found after completed batch review",
          className: "estimated"
        };
      }
      if ((diagnostic.remaining_review_frames || []).includes(frame)) {
        return {
          label: "Reviewed · still unresolved by tracker",
          className: "estimated"
        };
      }
      return null;
    }

    function currentBallTargetPoint() {
      const points = visibleBallStates();
      return points[selectedBallStateIndex] || null;
    }

    function ballPointAtRawFrame(frame) {
      const points = [...(ballTrack?.states || [])].sort(
        (left, right) => left.frame - right.frame
      );
      const exact = points.find(point => point.frame === frame);
      if (exact) return exact;
      const previous = [...points].reverse().find(point => point.frame < frame);
      const following = points.find(point => point.frame > frame);
      if (!previous || !following || following.frame === previous.frame) {
        return null;
      }
      const alpha = (frame - previous.frame) /
        (following.frame - previous.frame);
      return {
        frame,
        x: previous.x + (following.x - previous.x) * alpha,
        y: previous.y + (following.y - previous.y) * alpha,
        direct: false,
        state: "raw_frame_path_interpolation",
        evidence: "between sampled engine coordinates",
        uncertaintyRadius: Math.max(
          Number(previous.uncertaintyRadius || 0),
          Number(following.uncertaintyRadius || 0)
        )
      };
    }

    function renderBallPlaybackOverlay(frame) {
      if (!ballTrack) return;
      const displayedPoint = ballPointAtRawFrame(frame);
      const hasCoordinate =
        Number.isFinite(displayedPoint?.x)
        && Number.isFinite(displayedPoint?.y);
      const marker = document.getElementById("ball-frame-modal-marker");
      const crosshair = document.getElementById(
        "ball-frame-modal-crosshair"
      );
      marker.classList.toggle("trajectory-audit", trajectoryAuditMode);
      marker.setAttribute("r", trajectoryAuditMode ? "11" : "7");
      marker.hidden =
        !hasCoordinate || (trajectoryAuditMode && !showEngineBallMarker);
      marker.style.display = marker.hidden ? "none" : "";
      crosshair.hidden = !hasCoordinate || trajectoryAuditMode;
      crosshair.style.display = crosshair.hidden ? "none" : "";
      if (hasCoordinate) {
        marker.setAttribute("cx", String(displayedPoint.x));
        marker.setAttribute("cy", String(displayedPoint.y));
        crosshair.setAttribute(
          "d",
          "M " + (displayedPoint.x - 20) + " " + displayedPoint.y
            + " H " + (displayedPoint.x + 20)
            + " M " + displayedPoint.x + " " + (displayedPoint.y - 20)
            + " V " + (displayedPoint.y + 20)
        );
      }
      const yoloMarkers = document.getElementById(
        "ball-frame-yolo-markers"
      );
      yoloMarkers.replaceChildren();
      for (const candidate of (
        trajectoryAuditMode && !showYoloBallMarkers
          ? []
          : ballTrack.yoloCandidates?.[String(frame)] || []
      )) {
        if (
          trajectoryAuditMode
          && showEngineBallMarker
          && hasCoordinate
          && Math.hypot(
            candidate.x - displayedPoint.x,
            candidate.y - displayedPoint.y
          ) <= 4
        ) continue;
        const circle = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "circle"
        );
        circle.setAttribute("cx", String(candidate.x));
        circle.setAttribute("cy", String(candidate.y));
        circle.setAttribute("r", "11");
        circle.setAttribute("fill", "none");
        circle.setAttribute("stroke", "#58a6ff");
        circle.setAttribute("stroke-width", "5");
        yoloMarkers.append(circle);
      }
      const fps = Number(ballTrack.fps || 25);
      const frameCount = Number(
        ballTrack.frameCount || Math.round(state.segment.durationSeconds * fps)
      );
      document.getElementById("ball-frame-raw-context").textContent =
        "Playing raw frame " + frame + " of " + (frameCount - 1)
        + " · " + (frame / fps).toFixed(3) + "s";
    }

    function showRawBallFrame(frame, preserveZoom = false) {
      const point = currentBallTargetPoint();
      if (!point) return;
      const fps = Number(ballTrack.fps || 25);
      const frameCount = Number(
        ballTrack.frameCount || Math.round(state.segment.durationSeconds * fps)
      );
      selectedRawBallFrame = Math.max(
        0,
        Math.min(frameCount - 1, Math.round(frame))
      );
      const displayedPoint = ballPointAtRawFrame(selectedRawBallFrame);
      const hasDisplayedCoordinate =
        Number.isFinite(displayedPoint?.x)
        && Number.isFinite(displayedPoint?.y);
      const modal = document.getElementById("ball-frame-modal");
      const modalVideo = document.getElementById("ball-frame-modal-video");
      const overlay = document.getElementById("ball-frame-modal-overlay");
      const marker = document.getElementById("ball-frame-modal-marker");
      const crosshair = document.getElementById(
        "ball-frame-modal-crosshair"
      );
      const userMarker = document.getElementById("ball-frame-user-marker");
      const yoloMarkers = document.getElementById(
        "ball-frame-yolo-markers"
      );
      const media = modalVideo.closest(".ball-frame-modal-media");
      if (!preserveZoom) {
        media.classList.remove("zoomed");
        document.getElementById("reset-ball-frame-zoom").hidden = true;
      }
      const seekRequest = ++rawBallFrameSeekRequest;
      const seek = () => {
        const targetTime = selectedRawBallFrame / fps;
        let seekTimeout = null;
        const finishSeek = () => {
          if (seekRequest !== rawBallFrameSeekRequest) return;
          if (seekTimeout !== null) clearTimeout(seekTimeout);
          rawBallFrameSeekPending = false;
          media.classList.remove("seeking");
          media.removeAttribute("aria-busy");
          media.removeAttribute("data-seek-status");
          document.getElementById("ball-frame-raw-context").textContent =
            "Viewing raw frame " + selectedRawBallFrame + " of " +
            (frameCount - 1) + " · " +
            targetTime.toFixed(3) + "s" +
            (selectedRawBallFrame === selectedBallTargetFrame
              ? " · target"
              : " · context");
          document.getElementById("previous-ball-frame").disabled =
            selectedRawBallFrame === 0;
          document.getElementById("next-ball-frame").disabled =
            selectedRawBallFrame === frameCount - 1;
        };
        if (
          modalVideo.readyState >= 2
          && Math.abs(modalVideo.currentTime - targetTime) < 1 / (fps * 2)
        ) {
          finishSeek();
          return;
        }
        rawBallFrameSeekPending = true;
        media.classList.add("seeking");
        media.setAttribute("aria-busy", "true");
        media.dataset.seekStatus =
          "Loading exact raw frame " + selectedRawBallFrame + "…";
        document.getElementById("previous-ball-frame").disabled = true;
        document.getElementById("next-ball-frame").disabled = true;
        modalVideo.addEventListener("seeked", () => {
          requestAnimationFrame(finishSeek);
        }, {once: true});
        seekTimeout = setTimeout(finishSeek, 3000);
        modalVideo.pause();
        modalVideo.currentTime = targetTime;
      };
      if (modalVideo.src !== state.segment.videoUrl) {
        modalVideo.src = state.segment.videoUrl;
        modalVideo.addEventListener("loadedmetadata", seek, {once: true});
      } else if (modalVideo.readyState >= 1) {
        seek();
      }
      overlay.setAttribute(
        "viewBox",
        "0 0 " + ballTrack.width + " " + ballTrack.height
      );
      marker.setAttribute("cx", String(displayedPoint?.x || 0));
      marker.setAttribute("cy", String(displayedPoint?.y || 0));
      marker.classList.toggle("trajectory-audit", trajectoryAuditMode);
      marker.setAttribute("r", trajectoryAuditMode ? "11" : "7");
      marker.hidden =
        !hasDisplayedCoordinate
        || (trajectoryAuditMode && !showEngineBallMarker);
      marker.style.display = marker.hidden ? "none" : "";
      crosshair.setAttribute(
        "d",
        "M " + ((displayedPoint?.x || 0) - 20) + " "
          + (displayedPoint?.y || 0)
          + " H " + ((displayedPoint?.x || 0) + 20)
          + " M " + (displayedPoint?.x || 0) + " "
          + ((displayedPoint?.y || 0) - 20)
          + " V " + ((displayedPoint?.y || 0) + 20)
      );
      crosshair.hidden = marker.hidden || trajectoryAuditMode;
      crosshair.style.display = crosshair.hidden ? "none" : "";
      yoloMarkers.replaceChildren();
      for (const candidate of (
        trajectoryAuditMode && !showYoloBallMarkers
          ? []
          : ballTrack?.yoloCandidates?.[String(selectedRawBallFrame)] || []
      )) {
        if (
          trajectoryAuditMode
          && showEngineBallMarker
          && hasDisplayedCoordinate
          && Math.hypot(
            candidate.x - displayedPoint.x,
            candidate.y - displayedPoint.y
          ) <= 4
        ) continue;
        const circle = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "circle"
        );
        circle.setAttribute("cx", String(candidate.x));
        circle.setAttribute("cy", String(candidate.y));
        circle.setAttribute("r", "11");
        circle.setAttribute("fill", "none");
        circle.setAttribute("stroke", "#58a6ff");
        circle.setAttribute("stroke-width", "5");
        yoloMarkers.append(circle);
      }
      const observation = ballCoordinateObservations[
        String(selectedBallTargetFrame)
      ];
      const allFramesMode =
        !trajectoryAuditMode && selectedCoordinateBatchId === "all";
      userMarker.hidden =
        allFramesMode
        || selectedRawBallFrame !== selectedBallTargetFrame
        || observation?.decision !== "specified";
      userMarker.style.display = userMarker.hidden ? "none" : "";
      if (observation?.decision === "specified") {
        userMarker.setAttribute("cx", String(observation.x));
        userMarker.setAttribute("cy", String(observation.y));
      }
      document.getElementById("ball-frame-review-target").textContent =
        "Review frame " + selectedBallTargetFrame;
      document.getElementById("ball-frame-raw-context").textContent =
        "Viewing raw frame " + selectedRawBallFrame + " of " +
        (frameCount - 1) + " · " +
        (selectedRawBallFrame / fps).toFixed(3) + "s" +
        (selectedRawBallFrame === selectedBallTargetFrame
          ? " · target"
          : " · context");
      const decisionStatus = document.getElementById(
        "ball-frame-decision-status"
      );
      document.getElementById("ball-frame-modal-mode").textContent =
        trajectoryAuditMode
          ? "Trajectory audit · red ring: engine · blue rings: cached YOLO"
          : allFramesMode ? "All frames · read-only" : "Coordinate review active";
      document.getElementById("ball-frame-overlay-controls").hidden =
        !trajectoryAuditMode;
      const decisionLabel =
        observation?.decision === "agree"
          ? "agreed with the current coordinate"
          : observation?.decision === "needs_more_checking"
            ? "marked as needing more checking"
          : observation?.decision === "undefined"
            ? "ball marked undefined / not visible"
            : observation?.decision === "specified"
              ? "custom coordinate confirmed"
              : "";
      if (allFramesMode) {
        const latestStatus = ballDiagnosticStatus(point.frame)?.label;
        decisionStatus.textContent =
          (point.direct ? "Direct coordinate" : "Estimated coordinate")
          + (latestStatus ? " · " + latestStatus : "") + ".";
      } else if (decisionLabel) {
        decisionStatus.textContent =
          "Decision already recorded for review frame " +
          selectedBallTargetFrame + ": " + decisionLabel + ".";
      } else if (lastBallCoordinateDecision?.removed) {
        decisionStatus.textContent =
          "Decision removed from review frame " +
          lastBallCoordinateDecision.frame +
          ". Review frame " + selectedBallTargetFrame +
          " is awaiting a decision.";
      } else if (lastBallCoordinateDecision) {
        decisionStatus.textContent =
          "Decision saved for review frame " +
          lastBallCoordinateDecision.frame + ": " +
          lastBallCoordinateDecision.description +
          ". Now reviewing frame " + selectedBallTargetFrame +
          ", which is awaiting a decision.";
      } else {
        decisionStatus.textContent =
          "Review frame " + selectedBallTargetFrame +
          " is in coordinate review and awaiting a decision.";
      }
      const viewingTarget =
        selectedRawBallFrame === selectedBallTargetFrame;
      const coordinateDescription = hasDisplayedCoordinate
        ? (
          viewingTarget
            ? "Engine coordinate at target "
            : "Engine path at context frame " + selectedRawBallFrame + " "
        )
          + "(" + displayedPoint.x.toFixed(1) + ", "
          + displayedPoint.y.toFixed(1) + ") · "
          + (
            viewingTarget
              ? ballStateLabel(point) + " · " + point.state + " · "
                + point.evidence
              : displayedPoint.state + " · " + displayedPoint.evidence
                + " · target frame " + selectedBallTargetFrame
          )
        : "No engine path coordinate at context frame "
          + selectedRawBallFrame + " · target frame "
          + selectedBallTargetFrame;
      document.getElementById("ball-frame-modal-details").textContent =
        coordinateDescription
        + (
          !viewingTarget
            ? ""
            : observation?.decision === "agree"
              ? " · your decision: agree with current coordinate"
            : observation?.decision === "needs_more_checking"
              ? " · your decision: needs more checking"
            : observation?.decision === "undefined"
                ? " · your decision: ball undefined / not visible"
                : observation?.decision === "specified"
                  ? " · your proposed location (" +
                    observation.x.toFixed(1) + ", " +
                    observation.y.toFixed(1) + ")" +
                    (observation.approved
                      ? " confirmed for review"
                      : " not yet confirmed")
                  : ""
        )
        + (
          !displayedPoint || displayedPoint.uncertaintyRadius === null
            ? ""
            : " · uncertainty ±"
              + displayedPoint.uncertaintyRadius.toFixed(1) + "px"
        );
      document.getElementById("previous-ball-frame").disabled =
        rawBallFrameSeekPending || selectedRawBallFrame === 0;
      document.getElementById("next-ball-frame").disabled =
        rawBallFrameSeekPending || selectedRawBallFrame === frameCount - 1;
      const reviewFrames = trajectoryAuditMode
        ? visibleBallStates()
        : (ballTrack.states || []).filter(candidate => !candidate.direct);
      const reviewIndex = reviewFrames.findIndex(
        candidate => candidate.frame === selectedBallTargetFrame
      );
      document.getElementById("previous-ball-review-frame").disabled =
        reviewIndex <= 0;
      document.getElementById("next-ball-review-frame").disabled =
        reviewIndex < 0 || reviewIndex === reviewFrames.length - 1;
      document.getElementById("ball-review-navigation").hidden = allFramesMode;
      [
        "target-ball-frame",
        "mark-ball-location",
        "agree-ball-coordinate",
        "undefined-ball-coordinate",
        "needs-more-checking",
        "approve-ball-location",
        "undo-ball-coordinate-decision"
      ].forEach(id => {
        document.getElementById(id).hidden = allFramesMode;
      });
      document.getElementById("target-ball-frame").disabled =
        selectedRawBallFrame === selectedBallTargetFrame;
      document.getElementById("mark-ball-location").disabled =
        selectedRawBallFrame !== selectedBallTargetFrame
        || (!trajectoryAuditMode
          && state.coordinateReview?.status === "finalized")
        || selectedCoordinateBatch()?.status === "done";
      document.getElementById("agree-ball-coordinate").disabled =
        selectedRawBallFrame !== selectedBallTargetFrame
        || !Number.isFinite(point.x)
        || !Number.isFinite(point.y)
        || (!trajectoryAuditMode
          && state.coordinateReview?.status === "finalized")
        || selectedCoordinateBatch()?.status === "done";
      document.getElementById("undefined-ball-coordinate").disabled =
        selectedRawBallFrame !== selectedBallTargetFrame
        || (!trajectoryAuditMode
          && state.coordinateReview?.status === "finalized")
        || selectedCoordinateBatch()?.status === "done";
      document.getElementById("needs-more-checking").disabled =
        selectedRawBallFrame !== selectedBallTargetFrame;
      document.getElementById("approve-ball-location").disabled =
        selectedRawBallFrame !== selectedBallTargetFrame
        || observation?.decision !== "specified"
        || observation.approved
        || (!trajectoryAuditMode
          && state.coordinateReview?.status === "finalized")
        || selectedCoordinateBatch()?.status === "done";
      document.getElementById("undo-ball-coordinate-decision").disabled =
        !observation
        || (!trajectoryAuditMode
          && state.coordinateReview?.status === "finalized")
        || selectedCoordinateBatch()?.status === "done";
      if (!modal.open) modal.showModal();
    }

    function showBallFrame(index) {
      const points = visibleBallStates();
      if (!points.length) return;
      selectedBallStateIndex = Math.max(0, Math.min(points.length - 1, index));
      selectedBallTargetFrame = points[selectedBallStateIndex].frame;
      ballFrameInteractionMode = "zoom";
      showRawBallFrame(selectedBallTargetFrame);
    }

    function showAdjacentBallReviewFrame(offset) {
      const reviewFrames = trajectoryAuditMode
        ? visibleBallStates()
        : flaggedBallFrames.size
        ? (ballTrack?.states || []).filter(
            point => flaggedBallFrames.has(point.frame)
          )
        : (ballTrack?.states || []).filter(point => !point.direct);
      const currentIndex = reviewFrames.findIndex(
        point => point.frame === selectedBallTargetFrame
      );
      if (currentIndex < 0) return;
      const nextIndex = Math.max(
        0,
        Math.min(reviewFrames.length - 1, currentIndex + offset)
      );
      renderBallFrames();
      selectedBallStateIndex = nextIndex;
      selectedBallTargetFrame = reviewFrames[nextIndex].frame;
      ballFrameInteractionMode = "zoom";
      showRawBallFrame(selectedBallTargetFrame);
    }

    async function recordBallCoordinateDecision(observation, description) {
      const reviewedFrame = selectedBallTargetFrame;
      ballCoordinateObservations[String(reviewedFrame)] = {
        frame: reviewedFrame,
        ...observation,
        approved: true
      };
      flaggedBallFrames.add(reviewedFrame);
      lastBallCoordinateDecision = {
        frame: reviewedFrame,
        description
      };
      await saveBallFrameFlags();
      renderBallFrames();
      showRawBallFrame(reviewedFrame, true);
      document.getElementById("ball-coordinate-review-status").textContent =
        "Frame " + reviewedFrame + ": " + description +
        ". Saved locally for the single Copilot batch. Use Next review when " +
        "you are ready to move on.";
    }

    function renderBallFrames() {
      const points = ballTrack?.states || [];
      const direct = points.filter(point => point.direct).length;
      const estimated = points.length - direct;
      const diagnostic = state.ballRecoveryDiagnostic;
      const diagnosticRecovered =
        diagnostic?.recovered_original_review_frames?.length || 0;
      const diagnosticRegressions =
        diagnostic?.new_regression_frames?.length || 0;
      const diagnosticRemaining =
        diagnostic?.remaining_review_frames?.length || 0;
      const finalized = state.coordinateReview?.status === "finalized";
      const batch = selectedCoordinateBatch();
      const batchReadOnly =
        selectedCoordinateBatchId === "all" || batch?.status === "done";
      const activeBatchId = state.coordinateReview?.activeBatchId || null;
      const latestReviewSelected = Boolean(
        batch
        && batch.id === activeBatchId
        && batch.status === "ready"
      );
      const reviewButton = document.getElementById(
        "open-ball-coordinate-review"
      );
      reviewButton.hidden =
        !trajectoryAuditMode && (finalized || batchReadOnly);
      reviewButton.disabled = !flaggedBallFrames.size;
      reviewButton.textContent = trajectoryAuditMode
        ? "Open trajectory audit (" + flaggedBallFrames.size + " frames)"
        : batch
        ? batch.status === "done"
          ? "View completed round " + batch.number
          : "Open round " + batch.number + " (" + batch.frames.length
            + " frames)"
        : diagnostic?.batch_review_completed
        ? "View completed batch ("
          + diagnostic.original_review_frames.length + " reviewed)"
        : diagnostic
          ? "Open diagnostic review (" + diagnosticRemaining + " remaining)"
        : "Open batch review (" + flaggedBallFrames.size + " flagged)";
      document.getElementById("ball-coordinate-review-mode").textContent =
        trajectoryAuditMode
          ? "Independent trajectory audit"
          : finalized
            ? "Query mode · review finalized"
            : "Coordinate recovery mode";
      document.getElementById("ball-coordinate-review-status").textContent =
        trajectoryAuditMode
          ? "Audit decisions are evaluation-only and do not alter runtime output."
          : finalized
          ? "Read-only: inspect coordinates; recovery submissions are closed."
          : selectedCoordinateBatchId === "all"
            ? "All frames is read-only and shows persisted direct coordinates only."
          : batch?.status === "done"
            ? "Round " + batch.number + " completed "
              + formatCoordinateBatchTime(batch.rerunCompletedAt) + " · "
              + (batch.fixedFrames?.length || 0) + " fixed · "
              + (batch.unresolvedFrames?.length || 0) + " unresolved · "
              + (batch.regressionFrames?.length || 0) + " regressed · "
              + batch.before.directFrameCount + "/"
              + batch.before.sampledFrameCount + " before · "
              + batch.after.directFrameCount + "/"
              + batch.after.sampledFrameCount + " after. Read-only."
          : batch?.status === "rerun_started"
            ? "Round " + batch.number + " review and correction are complete. "
              + "The local tracker/YOLO rerun started "
              + formatCoordinateBatchTime(batch.rerunStartedAt) + "."
          : coordinateBatchLocked(batch)
            ? "Round " + batch.number + " · "
              + coordinateBatchStatusLabel(batch.status)
              + ". This modal remains open until the corrected rerun starts."
          : batch?.status === "ready"
            ? "Round " + batch.number + " is ready. Sending it starts one "
              + "Copilot review cycle; the corrected local rerun follows "
              + "automatically after tests pass."
          : diagnostic?.batch_review_completed
            ? "Batch review complete · " + diagnosticRecovered
              + " recovered in the focused diagnostic · "
              + diagnosticRegressions + " new regressions · "
              + diagnosticRemaining + " remain unresolved by the tracker. "
              + "No repeat user review is required. Diagnostic results become "
              + "authoritative only after a complete run persists them."
          : diagnostic
            ? diagnosticRemaining + " frames require review."
          : flaggedBallFrames.size
            ? flaggedBallFrames.size + " frame"
              + (flaggedBallFrames.size === 1 ? "" : "s")
              + " ready for one batch review."
            : "Flag one or more estimated frames to start a batch review.";
      const filter = document.getElementById("ball-frame-filter");
      filter.options[0].textContent =
        "Estimated only (" + estimated + ")";
      filter.options[1].textContent =
        "Integrity-demoted only ("
        + (ballTrack?.integrityRejectedFrames?.length || 0) + ")";
      filter.options[2].textContent =
        latestReviewSelected
          ? "Latest Round " + batch.number + " review ("
            + flaggedBallFrames.size + ")"
          : "Selected round frames (" + flaggedBallFrames.size + ")";
      document.getElementById("download-trajectory-audit").hidden =
        !trajectoryAuditMode;
      document.getElementById("needs-more-checking").hidden =
        !trajectoryAuditMode;
      filter.options[2].classList.toggle(
        "latest-review",
        latestReviewSelected
      );
      filter.classList.toggle(
        "latest-review",
        latestReviewSelected && filter.value === "flagged"
      );
      filter.options[3].textContent = diagnostic
        ? "Focused diagnostic ("
          + (
            new Set([
              ...(diagnostic.original_review_frames || []),
              ...(diagnostic.new_regression_frames || [])
            ])
          ).size
          + ")"
        : "Focused diagnostic (none)";
      filter.options[3].disabled = !diagnostic;
      filter.options[4].textContent = "All frames (" + points.length + ")";
      filter.options[5].textContent = "Direct only (" + direct + ")";
      const visible = visibleBallStates();
      document.getElementById("ball-frame-summary").textContent = points.length
        ? (ballTrack?.pendingEngineOutput
          ? points.length + " sampled raw frames · engine coordinates pending"
          : direct + "/" + points.length + " persisted direct · " + estimated +
          " persisted estimated" + (
            diagnostic
              ? " · diagnostic " + diagnostic.diagnostic_direct_frame_count
                + "/" + diagnostic.sampled_frame_count
                + " · " + diagnosticRecovered + " recovered"
                + " − " + diagnosticRegressions + " regressions"
              : ""
          )) + " · " + flaggedBallFrames.size +
          " flagged · showing " + visible.length +
          " · click a frame to enlarge"
        : "No coordinate states";
      document.getElementById("ball-frame-items").replaceChildren(
        ...visible.map((point, index) => {
          const row = document.createElement("tr");
          const frame = document.createElement("td");
          const openFrame = document.createElement("button");
          openFrame.type = "button";
          openFrame.className = "ball-frame-open";
          openFrame.textContent = String(point.frame);
          openFrame.addEventListener("click", () => showBallFrame(index));
          frame.append(openFrame);
          const values = [
            point.seconds.toFixed(2) + "s",
            Number.isFinite(point.x) ? point.x.toFixed(1) : "Pending",
            Number.isFinite(point.y) ? point.y.toFixed(1) : "Pending",
          ].map(value => {
            const cell = document.createElement("td");
            cell.textContent = value;
            return cell;
          });
          const status = document.createElement("td");
          const diagnosticStatus = ballDiagnosticStatus(point.frame);
          status.className = "ball-frame-status " + (
            diagnosticStatus?.className
            || (point.direct ? "direct" : "estimated")
          );
          status.textContent =
            diagnosticStatus?.label || ballStateLabel(point);
          const evidence = document.createElement("td");
          evidence.textContent = point.evidence;
          const review = document.createElement("td");
          const observation =
            ballCoordinateObservations[String(point.frame)];
          const reviewableFrame = Boolean(
            latestReviewSelected
            && batch.frames.includes(point.frame)
          );
          if (trajectoryAuditMode) {
            const result = document.createElement("span");
            result.className = "coordinate-review-result ";
            if (observation?.approved) {
              result.className += observation.decision === "needs_more_checking"
                ? "checking"
                : "confirmed";
              result.textContent = {
                agree: "✓ Confirmed · engine coordinate",
                specified: "✓ Confirmed · custom "
                  + observation.x.toFixed(1) + ", "
                  + observation.y.toFixed(1),
                undefined: "✓ Confirmed · ball not visible",
                needs_more_checking: "⚠ Needs more checking"
              }[observation.decision] || "✓ Decision saved";
            } else if (observation?.decision === "specified") {
              result.className += "pending";
              result.textContent = "Custom coordinate awaiting confirmation";
            } else {
              result.className += "pending";
              result.textContent = "Not reviewed";
            }
            review.append(result);
            row.classList.toggle(
              "coordinate-reviewed",
              Boolean(observation?.approved)
            );
          } else if (finalized || batchReadOnly || !reviewableFrame) {
            review.textContent = "Read-only";
          } else {
            const flag = document.createElement("button");
            const flagged = flaggedBallFrames.has(point.frame);
            flag.type = "button";
            flag.className = "ball-frame-flag";
            flag.setAttribute("aria-pressed", String(flagged));
            flag.textContent = flagged
              ? ballCoordinateObservations[String(point.frame)]?.approved
                ? "Decision saved"
                : "Awaiting review"
              : diagnosticStatus?.label || "Flag for review";
            flag.addEventListener("click", () => {
              if (flaggedBallFrames.has(point.frame)) {
                flaggedBallFrames.delete(point.frame);
              } else {
                flaggedBallFrames.add(point.frame);
              }
              void saveBallFrameFlags().catch(error => {
                document.getElementById(
                  "ball-coordinate-review-status"
                ).textContent = error.message;
              });
              renderBallFrames();
            });
            review.append(flag);
          }
          row.append(frame, ...values, status, evidence, review);
          return row;
        })
      );
    }

    function renderBallCoordinateReviewMessages() {
      const batches = state.coordinateReview?.batches || [];
      const batch = selectedCoordinateBatch();
      const tabs = document.getElementById("coordinate-review-tabs");
      const allFrames = document.createElement("button");
      allFrames.type = "button";
      allFrames.className =
        selectedCoordinateBatchId === "all" ? "current" : "";
      allFrames.textContent = "All frames";
      allFrames.addEventListener("click", () => {
        selectedCoordinateBatchId = "all";
        flaggedBallFrames = new Set();
        ballCoordinateObservations = {};
        document.getElementById("ball-frame-filter").value = "direct";
        renderBallFrames();
        renderBallCoordinateReviewMessages();
      });
      tabs.replaceChildren(allFrames, ...batches.map(candidate => {
        const button = document.createElement("button");
        button.type = "button";
        button.classList.toggle("current", candidate.id === batch?.id);
        button.classList.toggle(
          "latest-review",
          candidate.id === state.coordinateReview?.activeBatchId
            && candidate.status === "ready"
        );
        button.textContent = "Round " + candidate.number + " · "
          + coordinateBatchStatusLabel(candidate.status);
        button.addEventListener("click", () => {
          selectedCoordinateBatchId = candidate.id;
          flaggedBallFrames = new Set(candidate.frames || []);
          ballCoordinateObservations = {...(candidate.observations || {})};
          document.getElementById("ball-frame-filter").value = "flagged";
          void saveBallFrameFlags().catch(error => {
            document.getElementById(
              "ball-coordinate-review-status"
            ).textContent = error.message;
          });
          renderBallFrames();
          renderBallCoordinateReviewMessages();
        });
        return button;
      }));
      const timeline = document.getElementById("coordinate-review-timeline");
      const timelineEntries = batch ? [
        ["Batch submitted", batch.submittedAt],
        ["Copilot review completed", batch.reviewCompletedAt],
        ["Code fix completed", batch.codeFixCompletedAt],
        ["Tests completed", batch.testsCompletedAt],
        ["Rerun started", batch.rerunStartedAt],
        ["Rerun completed", batch.rerunCompletedAt]
      ] : [];
      timeline.replaceChildren(...timelineEntries.map(([label, value]) => {
        const item = document.createElement("li");
        item.className = "message " + (value ? "system" : "assistant");
        item.textContent = label + ": " + formatCoordinateBatchTime(value);
        return item;
      }));
      const messages = selectedCoordinateBatchId === "all"
        ? []
        : (state.conversation || []).filter(
          message => message.coordinateReview
          && (
            !batch
            || message.coordinateBatchId === batch.id
            || (
              batch.number === 1
              && !message.coordinateBatchId
            )
          )
        );
      const list = document.getElementById("ball-coordinate-review-messages");
      list.replaceChildren(...(
        messages.length
          ? messages.map(message => {
              const item = document.createElement("li");
              item.className = "message " + message.role;
              item.textContent =
                (message.role === "assistant" ? "Copilot: " : "You: ")
                + message.content;
              return item;
            })
          : [Object.assign(document.createElement("li"), {
              className: "message system",
              textContent: "No ball-coordinate review messages yet."
            })]
      ));
      const finalize = document.getElementById(
        "finalize-ball-coordinate-review"
      );
      finalize.disabled = state.coordinateReview?.status !== "verified";
      finalize.hidden = state.coordinateReview?.status === "finalized";
      const approvedCount = [...flaggedBallFrames].filter(
        frame => ballCoordinateObservations[String(frame)]?.approved
      ).length;
      const sendBatch = document.getElementById(
        "send-ball-coordinate-autopilot"
      );
      sendBatch.textContent = batch?.status === "done"
        ? "Batch done"
        : coordinateBatchLocked(batch)
          ? coordinateBatchStatusLabel(batch.status)
        : "Send batch once to Copilot (" + flaggedBallFrames.size +
          " flagged, " + approvedCount + " marked)";
      sendBatch.disabled = Boolean(
        !batch
        || batch.status !== "ready"
      );
      const close = document.getElementById("close-ball-coordinate-review");
      close.disabled = coordinateBatchLocked(batch);
      close.title = close.disabled
        ? "This review remains open until Copilot finishes and the rerun starts."
        : "";
      document.getElementById(
        "ball-coordinate-review-message"
      ).disabled = Boolean(batch && batch.status !== "ready");
      const modal = document.getElementById("ball-coordinate-review-modal");
      if (
        modal.open
        && lastCoordinateBatchStatus
        && lastCoordinateBatchStatus !== "rerun_started"
        && batch?.status === "rerun_started"
      ) {
        modal.close();
      }
      lastCoordinateBatchStatus = batch?.status || null;
      const modalFrames = document.getElementById(
        "ball-coordinate-modal-frames"
      );
      const reviewFrames = selectedCoordinateBatchId === "all"
        ? (ballTrack?.states || []).filter(point => point.direct)
        : flaggedBallFrames.size
        ? (ballTrack?.states || []).filter(
            point => flaggedBallFrames.has(point.frame)
          )
        : (ballTrack?.states || []).filter(point => !point.direct);
      modalFrames.replaceChildren(...reviewFrames.map(point => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "ball-frame-open";
        button.textContent = "Frame " + point.frame + " · "
          + point.seconds.toFixed(2) + "s · "
          + (
            batch?.frameResults?.[String(point.frame)]?.status
              ?.replaceAll("_", " ")
            || ballDiagnosticStatus(point.frame)?.label
            || ballStateLabel(point)
          );
        button.addEventListener("click", () => {
          let visibleIndex = visibleBallStates().findIndex(
            candidate => candidate.frame === point.frame
          );
          if (visibleIndex < 0) {
            document.getElementById("ball-frame-filter").value = "all";
            renderBallFrames();
            visibleIndex = visibleBallStates().findIndex(
              candidate => candidate.frame === point.frame
            );
          }
          showBallFrame(visibleIndex);
        });
        return button;
      }));
    }

    async function sendBallCoordinateReview(mode) {
      const status = document.getElementById(
        "ball-coordinate-review-send-status"
      );
      const input = document.getElementById("ball-coordinate-review-message");
      const flaggedFrames = [...flaggedBallFrames].sort((a, b) => a - b);
      if (!flaggedFrames.length) {
        status.textContent = "Flag at least one estimated frame first.";
        return;
      }
      const text = input.value.trim() ||
        "Review this flagged batch of estimated ball coordinates using only "
        + "the raw-video evidence. Identify genuine visual recoveries and "
        + "leave ambiguous or occluded frames as estimates.";
      const buttons = [
        document.getElementById("send-ball-coordinate-autopilot")
      ];
      buttons.forEach(button => { button.disabled = true; });
      status.textContent = "Sending one flagged-frame batch to Copilot…";
      try {
        const response = await fetch("/api/clip-message", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            segment: selectedSegmentKey(),
            seconds: 0,
            text,
            selectedIndex: null,
            mode,
            scope: "entire_clip",
            flaggedFrames,
            coordinateObservations: flaggedFrames
              .map(frame => ballCoordinateObservations[String(frame)])
              .filter(observation => observation?.approved)
          })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not send coordinate review");
        }
        input.value = "";
        status.textContent =
          "Batch sent. Copilot will reply only in this coordinate-review modal.";
        await loadState();
      } catch (error) {
        status.textContent = error.message;
      } finally {
        buttons.forEach(button => {
          button.disabled = selectedCoordinateBatch()?.status !== "ready";
        });
      }
    }

    async function finalizeBallCoordinateReview() {
      const status = document.getElementById(
        "ball-coordinate-review-send-status"
      );
      const button = document.getElementById(
        "finalize-ball-coordinate-review"
      );
      button.disabled = true;
      status.textContent =
        "Checking local AI completion, 90% minimum, and fresh Copilot verification…";
      try {
        const response = await fetch(
          "/api/finalize-ball-coordinate-review",
          {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({segment: selectedSegmentKey()})
          }
        );
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not finalize coordinate review");
        }
        await loadState();
        document.getElementById("ball-coordinate-review-modal").close();
      } catch (error) {
        status.textContent = error.message;
      } finally {
        button.disabled = state.coordinateReview?.status !== "verified";
      }
    }

    function updateBallMarker() {
      if (viewMode !== "ball" || !ballTrack) {
        ballOverlay.setAttribute("hidden", "");
        return;
      }
      const point = nearestBallPoint(video.currentTime || 0);
      if (!point) {
        ballOverlay.setAttribute("hidden", "");
        return;
      }
      const [, pointSeconds, x, y, trackId] = point;
      const trajectory = ballTrack.points
        .filter(candidate =>
          candidate[4] === trackId
          && candidate[1] >= pointSeconds - 1.5
          && candidate[1] <= pointSeconds + 0.2
        )
        .sort((left, right) => left[1] - right[1]);
      ballOverlay.removeAttribute("hidden");
      ballTrajectory.setAttribute(
        "d",
        trajectory.map((candidate, index) =>
          (index ? "L " : "M ") + candidate[2] + " " + candidate[3]
        ).join(" ")
      );
      ballMarker.setAttribute("cx", String(x));
      ballMarker.setAttribute("cy", String(y));
      ballCrosshair.setAttribute(
        "d",
        "M " + (x - 44) + " " + y + " H " + (x + 44) +
        " M " + x + " " + (y - 44) + " V " + (y + 44)
      );
    }

    function renderViewMode() {
      const selected = state.segment;
      document.querySelectorAll("[data-view-mode]").forEach(button => {
        const mode = button.dataset.viewMode;
        button.setAttribute("aria-pressed", String(mode === viewMode));
        button.disabled =
          (mode === "ball" && !selected.ballTrackAvailable)
          || (mode === "ai" && !selected.trackingUrl);
      });
      ballOverlay.setAttribute(
        "viewBox",
        "0 0 " + (ballTrack?.width || 4450) +
        " " + (ballTrack?.height || 2000)
      );
      document.getElementById("view-note").textContent = {
        normal: "Original video without overlays",
        ball: "Raw-video-derived detected ball position at this frame",
        ai: "Cached AI player, team, and ball tracking"
      }[viewMode];
      updateBallMarker();
    }

    function setViewMode(mode) {
      if (!["normal", "ball", "ai"].includes(mode)) return;
      if (mode === "ball" && !state.segment.ballTrackAvailable) return;
      if (mode === "ai" && !state.segment.trackingUrl) return;
      viewMode = mode;
      const source = mode === "ai"
        ? state.segment.trackingUrl
        : state.segment.videoUrl;
      if (source && video.src !== source) replaceVideoSource(source);
      video.setAttribute(
        "aria-label",
        state.segment.datasetName + " " + state.segment.timeLabel + " " +
        (mode === "ai" ? "AI tracking" : "footage")
      );
      renderViewMode();
    }

    function currentReplayRun() {
      return (state?.replayRuns || []).find(run => run.id === replayRunId)
        || null;
    }

    function formatReplayTime(seconds) {
      const rounded = Math.max(0, Math.floor(seconds));
      return String(Math.floor(rounded / 60)).padStart(2, "0") + ":" +
        String(rounded % 60).padStart(2, "0");
    }

    function replayElapsedSeconds(run) {
      return run.segments.slice(0, replaySegmentIndex)
        .reduce((total, segment) => total + segment.durationSeconds, 0) +
        Math.max(0, replayVideo.currentTime || 0);
    }

    function emptyStatistics() {
      return {
        red: {passes: 0, turnovers: 0, shots: 0, onTarget: 0, goals: 0},
        black: {passes: 0, turnovers: 0, shots: 0, onTarget: 0, goals: 0}
      };
    }

    function includeEventInStatistics(totals, event) {
      const team = totals[event.team];
      if (!team || event.decision?.status === "rejected") return;
      if (event.type === "completed_pass") team.passes += 1;
      if (event.type === "turnover") team.turnovers += 1;
      if (["shot_candidate", "shot_on_target_candidate", "shot_on_target"]
        .includes(event.type)) team.shots += 1;
      if (["shot_on_target_candidate", "shot_on_target"]
        .includes(event.type)) team.onTarget += 1;
      if (["goal", "goal_candidate"].includes(event.type)) team.goals += 1;
    }

    function updateLiveStatistics(seconds) {
      if (!state) return;
      const totals = emptyStatistics();
      state.drafts.forEach(event => {
        if (event.seconds <= seconds + 0.001) {
          includeEventInStatistics(totals, event);
        }
      });
      ["red", "black"].forEach(team => {
        document.getElementById("live-" + team + "-passes").textContent =
          String(totals[team].passes);
        document.getElementById("live-" + team + "-turnovers").textContent =
          String(totals[team].turnovers);
        document.getElementById("live-" + team + "-shots").textContent =
          String(totals[team].shots);
        document.getElementById("live-" + team + "-on-target").textContent =
          String(totals[team].onTarget);
      });
      document.getElementById("live-stats-time").textContent =
        formatReplayTime(seconds);
      updateFullscreenEventProgress(seconds);
    }

    function updateFullscreenEventProgress(seconds) {
      document.querySelectorAll("[data-event-seconds]").forEach(item => {
        const eventSeconds = Number(item.dataset.eventSeconds);
        item.classList.toggle(
          "reached",
          Number.isFinite(eventSeconds) && eventSeconds <= seconds + 0.001
        );
      });
    }

    function initializeBallFrameControls() {
      const modalVideo = document.getElementById("ball-frame-modal-video");
      const playbackButton = document.getElementById(
        "play-ball-frame-video"
      );
      document.getElementById("close-ball-frame-modal").addEventListener(
        "click",
        () => {
          modalVideo.pause();
          document.getElementById("ball-frame-modal").close();
        }
      );
      const ballFrameMedia = document.querySelector(
        "#ball-frame-modal .ball-frame-modal-media"
      );
      const resetBallFrameZoom = () => {
        ballFrameMedia.classList.remove("zoomed");
        ballFrameMedia.classList.remove("panning");
        document.getElementById("reset-ball-frame-zoom").hidden = true;
      };
      playbackButton.addEventListener("click", () => {
        if (modalVideo.paused) {
          if (modalVideo.ended) {
            modalVideo.currentTime =
              selectedBallTargetFrame / Number(ballTrack?.fps || 25);
          }
          void modalVideo.play();
        } else {
          modalVideo.pause();
        }
      });
      modalVideo.addEventListener("play", () => {
        playbackButton.textContent = "Pause";
      });
      modalVideo.addEventListener("pause", () => {
        playbackButton.textContent = "Play";
      });
      modalVideo.addEventListener("timeupdate", () => {
        if (modalVideo.paused || !ballTrack) return;
        const fps = Number(ballTrack.fps || 25);
        selectedRawBallFrame = Math.max(
          0,
          Math.min(
            Number(ballTrack.frameCount || 1) - 1,
            Math.round(modalVideo.currentTime * fps)
          )
        );
        renderBallPlaybackOverlay(selectedRawBallFrame);
      });
      let panStart = null;
      let ballFrameDidDrag = false;
      ballFrameMedia.addEventListener("pointerdown", event => {
        if (
          !ballFrameMedia.classList.contains("zoomed")
          || event.target.closest("button")
        ) return;
        const styles = getComputedStyle(ballFrameMedia);
        panStart = {
          pointerX: event.clientX,
          pointerY: event.clientY,
          originX: parseFloat(styles.getPropertyValue("--zoom-x")),
          originY: parseFloat(styles.getPropertyValue("--zoom-y"))
        };
        ballFrameDidDrag = false;
        ballFrameMedia.setPointerCapture(event.pointerId);
      });
      ballFrameMedia.addEventListener("pointermove", event => {
        if (!panStart) return;
        const bounds = ballFrameMedia.getBoundingClientRect();
        const deltaX = event.clientX - panStart.pointerX;
        const deltaY = event.clientY - panStart.pointerY;
        if (Math.hypot(deltaX, deltaY) < 4) return;
        ballFrameDidDrag = true;
        ballFrameMedia.classList.add("panning");
        const zoomScale = 2.5;
        const originX = panStart.originX +
          deltaX / (1 - zoomScale) / bounds.width * 100;
        const originY = panStart.originY +
          deltaY / (1 - zoomScale) / bounds.height * 100;
        ballFrameMedia.style.setProperty(
          "--zoom-x",
          Math.max(0, Math.min(100, originX)) + "%"
        );
        ballFrameMedia.style.setProperty(
          "--zoom-y",
          Math.max(0, Math.min(100, originY)) + "%"
        );
      });
      const finishBallFramePan = event => {
        if (!panStart) return;
        if (ballFrameMedia.hasPointerCapture(event.pointerId)) {
          ballFrameMedia.releasePointerCapture(event.pointerId);
        }
        panStart = null;
        ballFrameMedia.classList.remove("panning");
      };
      ballFrameMedia.addEventListener("pointerup", finishBallFramePan);
      ballFrameMedia.addEventListener("pointercancel", finishBallFramePan);
      ballFrameMedia.addEventListener("click", event => {
        if (event.target.closest("button")) return;
        if (ballFrameDidDrag) {
          ballFrameDidDrag = false;
          return;
        }
        if (ballFrameInteractionMode === "mark") {
          const bounds = ballFrameMedia.getBoundingClientRect();
          const zoomScale = ballFrameMedia.classList.contains("zoomed")
            ? 2.5
            : 1;
          const styles = getComputedStyle(ballFrameMedia);
          const originX = bounds.width * (
            parseFloat(styles.getPropertyValue("--zoom-x")) / 100
          );
          const originY = bounds.height * (
            parseFloat(styles.getPropertyValue("--zoom-y")) / 100
          );
          const pointerX = event.clientX - bounds.left;
          const pointerY = event.clientY - bounds.top;
          const unzoomedX = originX + (pointerX - originX) / zoomScale;
          const unzoomedY = originY + (pointerY - originY) / zoomScale;
          const scale = Math.min(
            bounds.width / ballTrack.width,
            bounds.height / ballTrack.height
          );
          const renderedWidth = ballTrack.width * scale;
          const renderedHeight = ballTrack.height * scale;
          const offsetX = (bounds.width - renderedWidth) / 2;
          const offsetY = (bounds.height - renderedHeight) / 2;
          const x = (unzoomedX - offsetX) / scale;
          const y = (unzoomedY - offsetY) / scale;
          if (
            x < 0 || x > ballTrack.width
            || y < 0 || y > ballTrack.height
          ) return;
          ballCoordinateObservations[String(selectedBallTargetFrame)] = {
            frame: selectedBallTargetFrame,
            decision: "specified",
            x,
            y,
            approved: false
          };
          ballFrameInteractionMode = "zoom";
          ballFrameMedia.classList.remove("marking");
          document.getElementById("mark-ball-location").textContent =
            "Specify my own coordinate";
          showRawBallFrame(selectedRawBallFrame, true);
          renderBallFrames();
          document.getElementById(
            "ball-coordinate-review-status"
          ).textContent =
            "Custom coordinate placed for frame "
            + selectedBallTargetFrame
            + ". Confirm it before moving to another frame.";
          return;
        }
        if (ballFrameMedia.classList.contains("zoomed")) {
          resetBallFrameZoom();
          return;
        }
        const bounds = ballFrameMedia.getBoundingClientRect();
        ballFrameMedia.style.setProperty(
          "--zoom-x",
          ((event.clientX - bounds.left) / bounds.width * 100) + "%"
        );
        ballFrameMedia.style.setProperty(
          "--zoom-y",
          ((event.clientY - bounds.top) / bounds.height * 100) + "%"
        );
        ballFrameMedia.classList.add("zoomed");
        document.getElementById("reset-ball-frame-zoom").hidden = false;
      });
      document.getElementById("reset-ball-frame-zoom").addEventListener(
        "click",
        event => {
          event.stopPropagation();
          resetBallFrameZoom();
        }
      );
      document.getElementById("previous-ball-frame").addEventListener(
        "click",
        () => {
          if (!rawBallFrameSeekPending) {
            if (trajectoryAuditMode) {
              showAdjacentBallReviewFrame(-1);
            } else {
              showRawBallFrame(selectedRawBallFrame - 1, true);
            }
          }
        }
      );
      document.getElementById("next-ball-frame").addEventListener(
        "click",
        () => {
          if (!rawBallFrameSeekPending) {
            if (trajectoryAuditMode) {
              showAdjacentBallReviewFrame(1);
            } else {
              showRawBallFrame(selectedRawBallFrame + 1, true);
            }
          }
        }
      );
      document.getElementById("previous-ball-review-frame").addEventListener(
        "click",
        () => showAdjacentBallReviewFrame(-1)
      );
      document.getElementById("next-ball-review-frame").addEventListener(
        "click",
        () => showAdjacentBallReviewFrame(1)
      );
      document.getElementById("target-ball-frame").addEventListener(
        "click",
        () => showRawBallFrame(selectedBallTargetFrame)
      );
      document.getElementById("zoom-ball-frame").addEventListener(
        "click",
        () => {
          if (selectedRawBallFrame !== selectedBallTargetFrame) {
            showRawBallFrame(selectedBallTargetFrame);
          }
          const point = currentBallTargetPoint();
          if (!point) return;
          ballFrameMedia.style.setProperty(
            "--zoom-x",
            (point.x / ballTrack.width * 100) + "%"
          );
          ballFrameMedia.style.setProperty(
            "--zoom-y",
            (point.y / ballTrack.height * 100) + "%"
          );
          ballFrameMedia.classList.add("zoomed");
          document.getElementById("reset-ball-frame-zoom").hidden = false;
        }
      );
      document.getElementById("mark-ball-location").addEventListener(
        "click",
        () => {
          ballFrameInteractionMode = "mark";
          ballFrameMedia.classList.add("marking");
          document.getElementById("mark-ball-location").textContent =
            "Click the image to place the ball";
        }
      );
      document.getElementById("agree-ball-coordinate").addEventListener(
        "click",
        () => {
          const point = (ballTrack?.states || []).find(
            candidate => candidate.frame === selectedBallTargetFrame
          );
          if (!point) return;
          void recordBallCoordinateDecision(
            {decision: "agree", x: point.x, y: point.y},
            "agreed with the current coordinate"
          ).catch(error => {
            document.getElementById(
              "ball-coordinate-review-status"
            ).textContent = error.message;
          });
        }
      );
      document.getElementById("undefined-ball-coordinate").addEventListener(
        "click",
        () => void recordBallCoordinateDecision(
          {decision: "undefined"},
          "marked ball undefined / not visible"
        ).catch(error => {
          document.getElementById(
            "ball-coordinate-review-status"
          ).textContent = error.message;
        })
      );
      document.getElementById("needs-more-checking").addEventListener(
        "click",
        () => void recordBallCoordinateDecision(
          {decision: "needs_more_checking"},
          "marked as needing more checking"
        ).catch(error => {
          document.getElementById(
            "ball-coordinate-review-status"
          ).textContent = error.message;
        })
      );
      document.getElementById("download-trajectory-audit").addEventListener(
        "click",
        downloadTrajectoryAudit
      );
      document.getElementById("show-engine-ball-marker").addEventListener(
        "change",
        event => {
          showEngineBallMarker = event.target.checked;
          renderBallPlaybackOverlay(selectedRawBallFrame);
        }
      );
      document.getElementById("show-yolo-ball-markers").addEventListener(
        "change",
        event => {
          showYoloBallMarkers = event.target.checked;
          renderBallPlaybackOverlay(selectedRawBallFrame);
        }
      );
      document.getElementById("approve-ball-location").addEventListener(
        "click",
        () => {
          const observation = ballCoordinateObservations[
            String(selectedBallTargetFrame)
          ];
          if (observation?.decision !== "specified") return;
          void recordBallCoordinateDecision(
            {decision: "specified", x: observation.x, y: observation.y},
            "confirmed your specified coordinate"
          ).catch(error => {
            document.getElementById(
              "ball-coordinate-review-status"
            ).textContent = error.message;
          });
        }
      );
      document.getElementById(
        "undo-ball-coordinate-decision"
      ).addEventListener(
        "click",
        () => {
          const frame = selectedBallTargetFrame;
          delete ballCoordinateObservations[String(frame)];
          lastBallCoordinateDecision = {frame, removed: true};
          void saveBallFrameFlags().catch(error => {
            document.getElementById(
              "ball-coordinate-review-status"
            ).textContent = error.message;
          });
          renderBallFrames();
          showRawBallFrame(frame);
          document.getElementById("ball-coordinate-review-status").textContent =
            "Frame " + frame + " decision removed. Choose again.";
        }
      );
      document.getElementById("ball-frame-filter").addEventListener(
        "change",
        () => {
          selectedBallStateIndex = 0;
          renderBallFrames();
        }
      );
      document.getElementById("open-ball-coordinate-review").addEventListener(
        "click",
        () => {
          renderBallCoordinateReviewMessages();
          document.getElementById("ball-coordinate-review-modal").showModal();
        }
      );
      document.getElementById("close-ball-coordinate-review").addEventListener(
        "click",
        () => {
          if (!coordinateBatchLocked()) {
            document.getElementById("ball-coordinate-review-modal").close();
          }
        }
      );
      document.getElementById(
        "ball-coordinate-review-modal"
      ).addEventListener("cancel", event => {
        if (coordinateBatchLocked()) event.preventDefault();
      });
      document.getElementById(
        "send-ball-coordinate-autopilot"
      ).addEventListener(
        "click",
        () => void sendBallCoordinateReview("autopilot")
      );
      document.getElementById(
        "finalize-ball-coordinate-review"
      ).addEventListener(
        "click",
        () => void finalizeBallCoordinateReview()
      );
      document.getElementById(
        "proceed-after-coordinate-gate"
      ).addEventListener(
        "click",
        () => void finalizeBallCoordinateReview()
      );
      document.getElementById(
        "continue-coordinate-review"
      ).addEventListener(
        "click",
        () => {
          renderBallCoordinateReviewMessages();
          document.getElementById("ball-coordinate-review-modal").showModal();
        }
      );
      document.getElementById("show-ball-frames").addEventListener(
        "click",
        () => {
          renderBallCoordinateReviewMessages();
          document.getElementById("ball-coordinate-review-modal").showModal();
        }
      );
    }

    function clearEventTriggers() {
      ["copilot", "engine"].forEach(source => {
        const trigger = document.getElementById(source + "-event-trigger");
        clearTimeout(eventTriggerTimers[source]);
        eventTriggerTimers[source] = null;
        trigger.hidden = true;
        trigger.classList.remove("active");
      });
      document.querySelectorAll(".comparison-event.playback-ping").forEach(
        item => item.classList.remove("playback-ping")
      );
    }

    function matchingReviewIndex(engineEvent, excluded = new Set()) {
      return (state?.drafts || [])
        .map((draft, index) => ({draft, index}))
        .filter(({draft, index}) =>
          !excluded.has(index)
          && draft.team === engineEvent.team
          && draft.type === engineEvent.type
          && reviewTimesMatch(draft, engineEvent.seconds)
        )
        .sort((left, right) => {
          const priority =
            Number(!requiresSameFrameReview(left.draft))
            - Number(!requiresSameFrameReview(right.draft));
          return priority || (
            Math.abs(left.draft.seconds - engineEvent.seconds)
            - Math.abs(right.draft.seconds - engineEvent.seconds)
          );
        })[0]?.index ?? -1;
    }

    function matchingEngineIndex(reviewEvent) {
      return (state?.engineEvents || [])
        .map((engine, index) => ({engine, index}))
        .filter(({engine}) =>
          engine.team === reviewEvent?.team
          && engine.type === reviewEvent?.type
          && reviewTimesMatch(reviewEvent, engine.seconds)
        )
        .sort((left, right) =>
          Math.abs(left.engine.seconds - reviewEvent.seconds)
          - Math.abs(right.engine.seconds - reviewEvent.seconds)
        )[0]?.index ?? -1;
    }

    function comparisonStatus(review, engine) {
      if (
        !review
        && engine?.review?.status === "confirmed"
        && engine.review.fresh
      ) return "reviewed";
      if (
        review?.type === "foul_encountered"
        || engine?.type === "foul_encountered"
      ) return "stoppage";
      return review && engine ? "matched" : "off";
    }

    function comparisonRows() {
      const engineEvents = state?.engineEvents || [];
      const usedEngine = new Set();
      const assignedEngine = new Map();
      const reviewCandidates = (state?.drafts || [])
        .map((draft, reviewIndex) => ({draft, reviewIndex}))
        .sort((left, right) => {
          const priority =
            Number(!requiresSameFrameReview(left.draft))
            - Number(!requiresSameFrameReview(right.draft));
          return priority || left.reviewIndex - right.reviewIndex;
        });
      reviewCandidates.forEach(({draft, reviewIndex}) => {
        const match = engineEvents
          .map((engine, engineIndex) => ({engine, engineIndex}))
          .filter(({engine, engineIndex}) =>
            !usedEngine.has(engineIndex)
            && engine.team === draft.team
            && engine.type === draft.type
            && reviewTimesMatch(draft, engine.seconds)
          )
          .sort((left, right) =>
            Math.abs(left.engine.seconds - draft.seconds)
            - Math.abs(right.engine.seconds - draft.seconds)
          )[0];
        if (match) {
          usedEngine.add(match.engineIndex);
          assignedEngine.set(reviewIndex, match);
        }
      });
      const rows = (state?.drafts || []).map((draft, reviewIndex) => {
        const match = assignedEngine.get(reviewIndex);
        return {
          review: draft,
          reviewIndex,
          engine: match?.engine || null,
          engineIndex: match?.engineIndex ?? -1,
          status: comparisonStatus(draft, match?.engine || null)
        };
      });
      engineEvents.forEach((engine, engineIndex) => {
        if (!usedEngine.has(engineIndex)) {
          rows.push({
            review: null,
            reviewIndex: -1,
            engine,
            engineIndex,
            status: comparisonStatus(null, engine)
          });
        }
      });
      return rows.sort((left, right) =>
        Number(left.review?.seconds ?? left.engine?.seconds ?? 0)
        - Number(right.review?.seconds ?? right.engine?.seconds ?? 0)
      );
    }

    function canonicalComparisonLabel(event) {
      if (event.type === "foul_encountered") return "Foul / stoppage";
      return teamLabel(event.team) + " " + typeLabel(event.type).toLowerCase();
    }

    function isManualReviewEvent(event) {
      return ["manual_review", "user_reported"].includes(event?.source);
    }

    function requiresSameFrameReview(event) {
      return isManualReviewEvent(event) || event?.sameFrameEngineReview;
    }

    function reviewReference(event, index) {
      return (isManualReviewEvent(event) ? "M" : "C") + (index + 1);
    }

    function reviewTimesMatch(reviewEvent, engineSeconds) {
      return requiresSameFrameReview(reviewEvent)
        ? Math.round(reviewEvent.seconds * 25) === Math.round(engineSeconds * 25)
        : Math.abs(reviewEvent.seconds - engineSeconds) <= 1;
    }

    function comparisonButton(event, side, eventNumber, reviewIndex) {
      if (!event) {
        const empty = document.createElement("span");
        empty.className = "comparison-empty";
        return empty;
      }
      const button = document.createElement("button");
      button.type = "button";
      button.className =
        "comparison-event " + side
        + (reviewIndex === selectedIndex ? " current" : "");
      button.dataset.eventSeconds = String(event.seconds);
      button.dataset.eventSource = side;
      button.dataset.eventIndex = String(eventNumber - 1);
      const description = side === "review"
        ? event.evidence
        : event.details;
      const ballEvidence = side === "engine" && event.ballEvidence
        ? "Ball evidence: " + event.ballEvidence.status
          + (
            event.ballEvidence.estimated_frames?.length
              ? " (estimated frames "
                + event.ballEvidence.estimated_frames.join(", ") + ")"
              : ""
          )
        : "";
      const canonicalLabel = canonicalComparisonLabel(event);
      button.title = [
        canonicalLabel,
        event.title && event.title !== canonicalLabel
          ? "Original description: " + event.title
          : "",
        description || "",
        ballEvidence
      ].filter(Boolean).join("\\n");
      button.setAttribute(
        "aria-label",
        "Seek to " + (
          side === "review"
            ? (isManualReviewEvent(event) ? "manual reference " : "Copilot proposal ")
            : "engine event "
        ) + eventNumber + " at " + event.seconds.toFixed(3)
          + " seconds: " + canonicalLabel
      );
      const number = document.createElement("span");
      number.className = "comparison-number";
      number.textContent = side === "review"
        ? (isManualReviewEvent(event) ? "M" : "C") + eventNumber
        : "E" + eventNumber;
      const label = document.createElement("span");
      label.className = "comparison-label";
      label.textContent = canonicalLabel;
      const frame = document.createElement("span");
      frame.className = "comparison-frame";
      frame.textContent =
        event.seconds.toFixed(3) + "s · frame "
        + Math.round(event.seconds * 25);
      label.append(frame);
      button.append(number, label);
      button.addEventListener("click", () => {
        if (reviewIndex >= 0) {
          selectEvent(reviewIndex);
        } else {
          selectedEngineIndex = eventNumber - 1;
          seekVideo(event.seconds);
          render();
        }
      });
      return button;
    }

    function comparisonActionIcon(kind) {
      const namespace = "http://www.w3.org/2000/svg";
      const icon = document.createElementNS(namespace, "svg");
      icon.classList.add("comparison-action-icon");
      icon.setAttribute("viewBox", "0 0 16 16");
      icon.setAttribute("aria-hidden", "true");
      icon.setAttribute("focusable", "false");
      const path = document.createElementNS(namespace, "path");
      path.setAttribute(
        "d",
        kind === "accept"
          ? "M3 8.5 6.5 12 13 4.5"
          : kind === "reject"
            ? "M4 4l8 8M12 4l-8 8"
            : "M7 2.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9m3.3 8.8L14 15"
      );
      icon.append(path);
      return icon;
    }

    function comparisonReviewCell(row) {
      if (!row.review) {
        const empty = document.createElement("span");
        empty.className = "comparison-empty";
        return empty;
      }
      const cell = document.createElement("div");
      cell.className = "comparison-review-cell";
      const verifying = state.activity?.state === "working"
        && state.activeConversation?.eventIndex === row.reviewIndex;
      if (verifying) cell.classList.add("verifying");
      cell.append(
        comparisonButton(
          row.review,
          "review",
          row.reviewIndex + 1,
          row.reviewIndex
        )
      );
      if (verifying) {
        const progress = document.createElement("span");
        progress.className = "comparison-verifying";
        progress.textContent =
          "Verifying " + reviewReference(row.review, row.reviewIndex) + "…";
        cell.append(progress);
      } else if (row.review.decision?.status === "accepted") {
        const accepted = document.createElement("span");
        accepted.className = "comparison-accepted";
        accepted.textContent = "✓ Accepted";
        accepted.title = "Accepted reference";
        cell.append(accepted);
      } else if (row.review.decision?.status === "rejected") {
        const rejected = document.createElement("span");
        rejected.className = "comparison-rejected";
        rejected.textContent = "✕ Rejected";
        rejected.title = "Rejected and excluded from the reference";
        cell.append(rejected);
      } else if (!referenceLocked()) {
        const actions = document.createElement("div");
        actions.className = "comparison-actions";
        const accept = document.createElement("button");
        accept.type = "button";
        accept.className = "comparison-action icon-action accept-action";
        const acceptLabel =
          "Verify and accept Copilot proposal C" + (row.reviewIndex + 1);
        accept.setAttribute("aria-label", acceptLabel);
        accept.title = acceptLabel;
        accept.append(comparisonActionIcon("accept"));
        accept.disabled = state.activity?.state === "working";
        accept.addEventListener("click", async event => {
          event.stopPropagation();
          selectEvent(row.reviewIndex, {seek: false, pause: false});
          await requestCopilotAcceptance(row.reviewIndex);
        });
        const reject = document.createElement("button");
        reject.type = "button";
        reject.className = "comparison-action icon-action reject";
        const rejectLabel = "Reject Copilot proposal C" + (row.reviewIndex + 1);
        reject.setAttribute("aria-label", rejectLabel);
        reject.title = rejectLabel;
        reject.append(comparisonActionIcon("reject"));
        reject.disabled = state.activity?.state === "working";
        reject.addEventListener("click", async event => {
          event.stopPropagation();
          selectEvent(row.reviewIndex, {seek: false, pause: false});
          await decide("rejected", row.reviewIndex);
        });
        actions.append(accept, reject);
        cell.append(actions);
      }
      return cell;
    }

    function comparisonEngineCell(row) {
      if (!row.engine) {
        const empty = document.createElement("span");
        empty.className = "comparison-empty";
        return empty;
      }
      const cell = document.createElement("div");
      cell.className = "comparison-engine-cell";
      const independentEngineReview =
        !row.review || row.review.decision?.status === "rejected";
      cell.append(
        comparisonButton(
          row.engine,
          "engine",
          row.engineIndex + 1,
          independentEngineReview ? -1 : row.reviewIndex
        )
      );
      if (
        independentEngineReview
        && row.engine.review?.status === "confirmed"
        && row.engine.review.fresh
      ) {
        const reviewed = document.createElement("span");
        reviewed.className = "comparison-reviewed";
        reviewed.textContent = "✓ E" + (row.engineIndex + 1) + " confirmed";
        reviewed.title = "Confirmed by independent review";
        cell.append(reviewed);
      } else if (
        independentEngineReview
        && row.engine.review?.status === "not_confirmed"
        && row.engine.review.fresh
      ) {
        const unsupported = document.createElement("span");
        unsupported.className = "comparison-rejected";
        unsupported.textContent =
          "✕ E" + (row.engineIndex + 1) + " not confirmed";
        unsupported.title = "The exact engine event is unsupported";
        cell.append(unsupported);
      }
      if (independentEngineReview && !referenceLocked()) {
        const confirm = document.createElement("button");
        confirm.type = "button";
        confirm.className = "comparison-action icon-action";
        const confirmLabel =
          row.engine.review?.status === "confirmed"
          && row.engine.review.fresh
          ? "Re-verify engine event E" + (row.engineIndex + 1)
            + " with Copilot Autopilot"
          : row.engine.review?.status === "not_confirmed"
            && row.engine.review.fresh
            ? "Re-verify unsupported engine event E"
              + (row.engineIndex + 1) + " with Copilot Autopilot"
          : row.engine.review?.status === "confirmed"
            ? "Verify stale engine event E" + (row.engineIndex + 1)
              + " with Copilot Autopilot"
            : row.engine.review?.status === "not_confirmed"
              ? "Re-verify stale unsupported engine event E"
                + (row.engineIndex + 1) + " with Copilot Autopilot"
            : "Verify engine event E" + (row.engineIndex + 1)
              + " with Copilot Autopilot";
        confirm.setAttribute("aria-label", confirmLabel);
        confirm.title = confirmLabel;
        confirm.append(comparisonActionIcon("verify"));
        confirm.disabled = state.activity?.state === "working";
        confirm.addEventListener("click", async event => {
          event.stopPropagation();
          selectedEngineIndex = row.engineIndex;
          render();
          await requestEngineEventVerification(
            row.engineIndex,
            "fullscreen-chat-status",
            "fullscreen-message"
          );
        });
        cell.append(confirm);
      }
      if (row.review) {
        const agreement = document.createElement("span");
        agreement.className = row.review.decision?.status === "rejected"
          ? "comparison-rejected"
          : "comparison-reviewed";
        agreement.textContent = row.review.decision?.status === "rejected"
          ? "C↔E conflict"
          : "C↔E agreement";
        agreement.title = row.review.decision?.status === "rejected"
          ? "The nearby C# was rejected and does not validate this E#"
          : "Agreement only; independent review is still required";
        cell.append(agreement);
      }
      return cell;
    }

    function renderFullscreenEvents() {
      const target = document.getElementById("fullscreen-event-items");
      const rows = comparisonRows();
      const totals = rows.reduce(
        (counts, row) => {
          counts[row.status] += 1;
          return counts;
        },
        {matched: 0, reviewed: 0, stoppage: 0, off: 0}
      );
      const summary = document.getElementById("comparison-summary");
      summary.replaceChildren(
        ...[
          ["matched", totals.matched + " synchronized"],
          ["reviewed", totals.reviewed + " confirmed reviewed"],
          ["stoppage", totals.stoppage + " foul/stoppage"],
          ["off", totals.off + " difference" + (totals.off === 1 ? "" : "s")]
        ].map(([status, text]) => {
          const label = document.createElement("span");
          label.className = status;
          label.textContent = text;
          return label;
        })
      );
      target.replaceChildren(...rows.map(row => {
        const item = document.createElement("div");
        item.className = "comparison-row " + row.status;
        if (row.review?.decision?.status) {
          item.classList.add(
            "decision-" + row.review.decision.status
          );
        }
        if (
          row.review
          && !row.review.decision?.status
          && !referenceLocked()
        ) {
          item.classList.add("has-review-actions");
        }
        const seconds = document.createElement("div");
        seconds.className = "comparison-time";
        const timeLabel = document.createElement("span");
        const reviewSeconds = row.review?.seconds;
        const engineSeconds = row.engine?.seconds;
        timeLabel.textContent =
          reviewSeconds !== undefined && engineSeconds !== undefined
            && Math.abs(reviewSeconds - engineSeconds) > 0.049
            ? reviewSeconds.toFixed(1) + " / " + engineSeconds.toFixed(1) + "s"
            : Number(reviewSeconds ?? engineSeconds).toFixed(1) + "s";
        seconds.append(timeLabel);
        item.append(
          comparisonReviewCell(row),
          seconds,
          comparisonEngineCell(row)
        );
        return item;
      }));
      const compactRail = document.getElementById("compact-engine-rail");
      compactRail.replaceChildren(...(state?.engineEvents || []).map(
        (engine, engineIndex) => {
          const reviewIndex = matchingReviewIndex(engine);
          const status = comparisonStatus(
            reviewIndex >= 0 ? state.drafts[reviewIndex] : null,
            engine
          );
          const spot = document.createElement("button");
          spot.type = "button";
          spot.className =
            "compact-engine-spot " + status
            + (reviewIndex === selectedIndex ? " current" : "");
          spot.style.top =
            (Math.max(0, Math.min(60, engine.seconds)) / 60 * 100) + "%";
          spot.dataset.eventSeconds = String(engine.seconds);
          spot.title =
            "E" + (engineIndex + 1)
            + (reviewIndex >= 0 ? " ↔ C" + (reviewIndex + 1) : " · unmatched")
            + " · " + engine.seconds.toFixed(3) + "s · " + engine.title
            + " · click to seek";
          spot.setAttribute("aria-label", spot.title);
          spot.addEventListener("click", () => {
            if (reviewIndex >= 0) selectEvent(reviewIndex);
            else {
              selectedEngineIndex = engineIndex;
              seekVideo(engine.seconds);
              render();
            }
          });
          return spot;
        }
      ));
      updateFullscreenEventProgress(video.currentTime || 0);
    }

    function updateReplayStatistics() {
      const run = currentReplayRun();
      if (!run) return;
      const elapsed = replayElapsedSeconds(run);
      const totals = emptyStatistics();
      let offset = 0;
      run.segments.forEach(segment => {
        segment.events.forEach(event => {
          if (offset + event.seconds > elapsed + 0.001) return;
          includeEventInStatistics(totals, event);
        });
        offset += segment.durationSeconds;
      });
      ["red", "black"].forEach(team => {
        document.getElementById(team + "-goals").textContent =
          String(totals[team].goals);
        document.getElementById(team + "-passes").textContent =
          String(totals[team].passes);
        document.getElementById(team + "-turnovers").textContent =
          String(totals[team].turnovers);
        document.getElementById(team + "-shots").textContent =
          String(totals[team].shots);
        document.getElementById(team + "-on-target").textContent =
          String(totals[team].onTarget);
      });
      const totalDuration = run.segments.reduce(
        (total, segment) => total + segment.durationSeconds,
        0
      );
      document.getElementById("match-clock").textContent =
        formatReplayTime(elapsed) + " / " + formatReplayTime(totalDuration);
    }

    function loadReplaySegment(index, autoplay = false) {
      const run = currentReplayRun();
      if (!run || !run.segments[index]) return;
      replaySegmentIndex = index;
      const segment = run.segments[index];
      document.getElementById("replay-position").textContent =
        "Minute " + (index + 1) + " of " + run.segments.length +
        " · " + segment.timeLabel;
      if (replayVideo.dataset.segment !== segment.key) {
        replayVideo.dataset.segment = segment.key;
        replayVideo.src = segment.videoUrl;
      } else {
        replayVideo.currentTime = 0;
      }
      updateReplayStatistics();
      if (autoplay) {
        replayVideo.addEventListener(
          "loadedmetadata",
          () => void replayVideo.play(),
          {once: true}
        );
      }
    }

    function renderReplayCatalog() {
      const runs = state.replayRuns || [];
      if (!runs.length) {
        replayRunSelect.replaceChildren();
        replayRunSelect.disabled = true;
        document.getElementById("replay-play").disabled = true;
        document.getElementById("replay-restart").disabled = true;
        document.getElementById("replay-note").textContent =
          "No consecutive AI-ready one-minute segments are available yet.";
        return;
      }
      replayRunSelect.disabled = false;
      document.getElementById("replay-play").disabled = false;
      document.getElementById("replay-restart").disabled = false;
      const continuousRuns = runs.filter(run => run.continuityVerified);
      if (!continuousRuns.length) {
        replayRunSelect.replaceChildren();
        replayRunSelect.disabled = true;
        document.getElementById("replay-play").disabled = true;
        document.getElementById("replay-restart").disabled = true;
        document.getElementById("replay-note").textContent =
          "No strictly consecutive replay run is available.";
        return;
      }
      if (!continuousRuns.some(run => run.id === replayRunId)) {
        replayRunId = continuousRuns[0].id;
        replaySegmentIndex = 0;
      }
      replayRunSelect.replaceChildren(...continuousRuns.map(run => {
        const option = document.createElement("option");
        option.value = run.id;
        option.textContent = run.timeLabel + " · " + run.readyMinutes +
          "/10 minutes ready";
        return option;
      }));
      replayRunSelect.value = replayRunId;
      const run = currentReplayRun();
      const readiness = document.getElementById("replay-readiness");
      readiness.className =
        "replay-readiness" + (run.complete ? " complete" : "");
      readiness.textContent = run.readyMinutes + "/10 ready";
      document.getElementById("replay-note").textContent = run.complete
        ? "Ten consecutive AI-ready minutes are available in exact chronological order."
        : run.readyMinutes + " consecutive minute(s) are available in exact order; separate clips are never mixed.";
      const segment = run.segments[replaySegmentIndex] || run.segments[0];
      if (replayVideo.dataset.segment !== segment.key) {
        replaySegmentIndex = Math.max(0, run.segments.indexOf(segment));
        loadReplaySegment(replaySegmentIndex);
      } else {
        updateReplayStatistics();
      }
    }

    function teamLabel(team) {
      return team === "red" ? "Red/white" :
        team === "black" ? "Black" : "Match state";
    }

    function typeLabel(type) {
      return {
        completed_pass: "Completed pass",
        turnover: "Turnover",
        foul_encountered: "Foul encountered"
      }[type] || type.replaceAll("_", " ");
    }

    function playbackEventLabel(draft) {
      return eventSourceLabel(draft).short + " · " +
        teamLabel(draft.team) + " " + ({
        completed_pass: "pass completed",
        turnover: "turnover",
        foul_encountered: "foul encountered",
        shot_candidate: "shot",
        shot_on_target: "shot on target"
      }[draft.type] || draft.type.replaceAll("_", " "));
    }

    function eventSourceLabel(draft) {
      if (draft.source === "engine_output") {
        return {label: "AI engine detected", short: "AI engine", className: "engine"};
      }
      if (isManualReviewEvent(draft)) {
        return {label: "Manual review reference", short: "Manual M#", className: "user"};
      }
      if (draft.source === "validated_reference") {
        return {label: "Validated reference", short: "Reference", className: "reference"};
      }
      if (draft.source === "adjusted_proposal") {
        return {
          label: "Copilot-reviewed correction",
          short: "Copilot reviewed",
          className: "copilot"
        };
      }
      return {
        label: "Copilot-prepared review",
        short: "Review proposal",
        className: "copilot"
      };
    }

    function shortHash(value) {
      return value ? value.slice(0, 12) : "unknown";
    }

    function currentDraft() {
      return state?.drafts?.[selectedIndex] || null;
    }

    function applyActionZoom() {
      const draft = currentDraft();
      const focus = draft?.actionFocus;
      const button = document.getElementById("zoom-action");
      button.disabled = !focus;
      if (!focus) actionZoom = false;
      videoShell.classList.toggle("action-zoom", actionZoom);
      videoMedia.style.transformOrigin = focus
        ? focus.xPercent.toFixed(2) + "% " + focus.yPercent.toFixed(2) + "%"
        : "50% 50%";
      button.textContent = actionZoom
        ? "Reset Zoom"
        : "Zoom to C" + (selectedIndex + 1) + " Action";
      button.setAttribute("aria-pressed", String(actionZoom));
    }

    function renderConversationMessages(targetId, messages, emptyText) {
      const target = document.getElementById(targetId);
      if (!messages.length) {
        const empty = document.createElement("li");
        empty.className = "message system";
        empty.textContent = emptyText;
        target.replaceChildren(empty);
        return;
      }
      target.replaceChildren(...messages.map(message => {
        const item = document.createElement("li");
        item.className = "message " + message.role;
        const author = document.createElement("strong");
        author.textContent = {
          user: "You",
          assistant: "Copilot",
          system: "System"
        }[message.role] || message.role;
        const content = document.createElement("span");
        content.textContent = message.content;
        item.append(author, content);
        return item;
      }));
      target.scrollTop = target.scrollHeight;
    }

    function renderMessages() {
      const eventMessages = (state.conversation || []).filter(
        message => message.eventIndex === selectedIndex
      );
      renderConversationMessages(
        "messages",
        eventMessages,
        "No messages yet for Event " + (selectedIndex + 1) + "."
      );
      const fullscreenMessages = selectedEngineIndex === null
        ? eventMessages
        : (state.conversation || []).filter(
            message => message.engineIndex === selectedEngineIndex
          );
      renderConversationMessages(
        "fullscreen-messages",
        fullscreenMessages,
        selectedEngineIndex === null
          ? "No messages yet for Event " + (selectedIndex + 1) + "."
          : "No messages yet for E" + (selectedEngineIndex + 1) + "."
      );
    }

    function renderClipMessages() {
      const messages = selectedEngineIndex === null
        ? (state.conversation || []).filter(
            message =>
              message.eventIndex === null
              && !Number.isInteger(message.engineIndex)
          )
        : (state.conversation || []).filter(
            message => message.engineIndex === selectedEngineIndex
          );
      renderConversationMessages(
        "clip-messages",
        messages,
        selectedEngineIndex === null
          ? "No general clip messages yet."
          : "No messages yet for E" + (selectedEngineIndex + 1) + "."
      );
    }

    function renderActivity() {
      const current = state.activity || {
        state: "ready",
        label: "Ready for your review",
        detail: ""
      };
      const target = document.getElementById("activity");
      target.className = "activity " + current.state + (
        ballCoordinatesNeedReview() ? " coordinates-review" : ""
      );
      document.getElementById("activity-label").textContent = current.label;
      document.getElementById("activity-detail").textContent =
        current.detail ? " · " + current.detail : "";
      const coordinateGateVerified =
        state.coordinateReview?.status === "verified";
      document.getElementById(
        "proceed-after-coordinate-gate"
      ).hidden = !coordinateGateVerified;
      const continueCoordinateReview = document.getElementById(
        "continue-coordinate-review"
      );
      continueCoordinateReview.hidden = !coordinateGateVerified;
      continueCoordinateReview.textContent = "Continue reviewing "
        + (state.coordinateReview?.flaggedFrames?.length || 0)
        + " frames";
      const chatStatus = document.getElementById("chat-status");
      const clipChatStatus = document.getElementById("clip-chat-status");
      const eventActive = current.state === "working"
        && state.activeConversation?.eventIndex === selectedIndex;
      const clipActive = current.state === "working"
        && (
          selectedEngineIndex === null
            ? state.activeConversation?.eventIndex === null
              && !Number.isInteger(state.activeConversation?.engineIndex)
            : state.activeConversation?.engineIndex === selectedEngineIndex
        );
      chatStatus.dataset.state = eventActive ? "working" : "ready";
      chatStatus.textContent = eventActive
        ? current.label + "…"
        : currentDraft()?.decision?.status === "accepted"
          ? "Accepted · adjustment only"
          : currentDraft()?.decision?.status === "rejected"
            ? "Rejected · adjustment only"
          : "Ready";
      clipChatStatus.dataset.state = clipActive ? "working" : "ready";
      clipChatStatus.textContent = clipActive ? current.label + "…" : "Ready";
      const progressOverlay =
        document.getElementById("review-progress-overlay");
      progressOverlay.hidden = current.state !== "working";
      document.getElementById("review-progress-text").textContent =
        eventActive
          ? "Copilot is verifying "
            + reviewReference(state.drafts[selectedIndex], selectedIndex) + "…"
          : current.label + "…";
    }

    function renderReviewFlow({matched, decision, comparison}) {
      const steps = decision?.status === "accepted"
        ? [
            ["Accepted C#", "The saved reference decision is complete."],
            [
              "Next check",
              comparison?.status === "already_agrees"
                ? "The current engine source and cached-output hashes agree. No recalculation is needed."
                : comparison?.status === "stale"
                  ? "Use Re-check Accepted C# & Engine. Rerun only cached event building because the saved hashes are stale."
                  : "Use Re-check Accepted C# & Engine to synchronize the general rule and protected regressions."
            ],
            [
              "Correction",
              "Describe the changed evidence, then use Request C# Adjustment."
            ]
          ]
        : decision?.status === "rejected"
          ? [
              ["Rejected C#", "This proposal is excluded from the reference."],
              [
                "Engine event",
                matched
                  ? "The nearby E# is not validated by this rejection and must be independently verified."
                  : "No matched E# is attached to this rejected proposal."
              ],
              [
                "Correction",
                "Describe why the rejection should change, then use Request C# Adjustment."
              ]
            ]
          : matched
            ? [
                [
                  "C↔E agreement",
                  "Team, event type, and time tolerance align; this is not proof of correctness."
                ],
                ["Question", "Ask Copilot about C# in Plan mode."],
                [
                  "Correct",
                  "Verify and accept C#. The saved engine hashes then determine whether recalculation is needed."
                ],
                ["Wrong detail", "Request a C# adjustment."],
                [
                  "No C# event",
                  "Reject C#. The nearby E# must then be independently verified."
                ]
              ]
            : [
                ["C# only", "No current E# matches this independent proposal."],
                ["Question", "Ask Copilot about C# in Plan mode."],
                [
                  "Correct",
                  "Verify and accept C#. Copilot then synchronizes a general rule and runs protected regressions."
                ],
                ["Wrong detail", "Request a C# adjustment."],
                ["No event", "Reject the C# proposal."]
              ];
      const flow = document.getElementById("review-flow");
      flow.replaceChildren(...steps.map(([label, detail]) => {
        const item = document.createElement("li");
        const strong = document.createElement("strong");
        strong.textContent = label + ":";
        item.append(strong, " " + detail);
        return item;
      }));
    }

    function render() {
      const draft = currentDraft();
      renderSegments();
      renderReplayCatalog();
      renderFullscreenEvents();
      const hasDraft = Boolean(draft);
      const selectedReference = hasDraft
        ? reviewReference(draft, selectedIndex)
        : null;
      const selectedReferenceKind = hasDraft && isManualReviewEvent(draft)
        ? "M#"
        : "C#";
      const lockedReference = referenceLocked();
      const reviewBusy = state.activity?.state === "working";
      const remainingCount = state.drafts.filter(
        candidate => !candidate.decision
      ).length;
      const mainReviewActive = Boolean(
        state.segment.validated
        || state.segment.validationStatus === "in_review"
        || state.coordinateReview?.status === "finalized"
      );
      const canPublish =
        mainReviewActive
        && hasDraft
        && !lockedReference
        && Boolean(state.publication?.reviewComplete);
      document.getElementById("event-nav").hidden = !hasDraft && !canPublish;
      document.getElementById("previous-event").hidden = !hasDraft;
      document.getElementById("next-event").hidden = !hasDraft;
      document.querySelector(".event-position").hidden = !hasDraft;
      const acceptAll = document.getElementById("accept-all-events");
      acceptAll.hidden = !hasDraft || lockedReference || remainingCount === 0;
      acceptAll.disabled = reviewBusy || remainingCount === 0;
      acceptAll.textContent = remainingCount
        ? "Verify & Accept All " + remainingCount + " Remaining Events (Autopilot)"
        : "All Events Accepted";
      document.getElementById("proposal").hidden = !hasDraft;
      document.getElementById("empty-review").hidden = hasDraft;
      document.getElementById("composer").hidden = !hasDraft;
      const publishReference = document.getElementById("publish-reference");
      publishReference.hidden = !canPublish;
      publishReference.disabled = reviewBusy;
      publishReference.title = state.publication?.regressionFresh
        ? "Run the final exact-match gate and publish this reference"
        : "Run protected regressions, then publish only if every gate passes";
      const fullscreenDecision = draft?.decision?.status;
      const selectedEngine = selectedEngineIndex === null
        ? null
        : state.engineEvents?.[selectedEngineIndex];
      document.getElementById("proposal").hidden =
        !hasDraft || Boolean(selectedEngine);
      document.getElementById("empty-review").hidden =
        hasDraft || Boolean(selectedEngine);
      document.getElementById("composer").hidden =
        !hasDraft || Boolean(selectedEngine);
      const matchedEngineIndex = hasDraft ? matchingEngineIndex(draft) : -1;
      const matchedEngine = matchedEngineIndex >= 0
        ? state.engineEvents[matchedEngineIndex]
        : null;
      const selectedEngineReviewIndex = selectedEngine
        ? matchingReviewIndex(selectedEngine)
        : -1;
      const selectedEngineLinkedRejected =
        selectedEngineReviewIndex >= 0
        && state.drafts[selectedEngineReviewIndex]?.decision?.status === "rejected";
      const acceptedNeedsEngineRecheck =
        fullscreenDecision === "accepted"
        && draft?.comparison?.status !== "already_agrees";
      renderDeveloperMode();
      document.getElementById("fullscreen-chat-title").textContent =
        selectedEngine
          ? "Copilot conversation for E" + (selectedEngineIndex + 1)
          : hasDraft
            ? "Copilot conversation for " + selectedReference
            : "No selected event conversation";
      document.getElementById("fullscreen-send-message").disabled =
        selectedEngine
          ? reviewBusy
          : !hasDraft || Boolean(fullscreenDecision) || reviewBusy;
      document.getElementById("fullscreen-send-message").textContent =
        selectedEngine
          ? "Ask Copilot about E" + (selectedEngineIndex + 1) + " (Plan)"
          : hasDraft
            ? "Ask Copilot about " + selectedReference + " (Plan)"
            : "Ask Copilot";
      const fullscreenPrimary =
        document.getElementById("fullscreen-primary-action");
      fullscreenPrimary.hidden =
        referenceLocked()
        || (
          selectedEngine
            ? false
            : !hasDraft
              || (Boolean(fullscreenDecision) && !acceptedNeedsEngineRecheck)
        );
      fullscreenPrimary.disabled = reviewBusy;
      fullscreenPrimary.textContent = selectedEngine
        ? selectedEngine.review?.status === "confirmed"
          && selectedEngine.review.fresh
          ? "Re-verify E" + (selectedEngineIndex + 1) + " (Autopilot)"
          : selectedEngine.review?.status === "not_confirmed"
            && selectedEngine.review.fresh
            ? "Re-verify unsupported E" + (selectedEngineIndex + 1)
              + " (Autopilot)"
          : selectedEngine.review?.status === "confirmed"
            ? "Verify stale E" + (selectedEngineIndex + 1) + " (Autopilot)"
            : selectedEngine.review?.status === "not_confirmed"
              ? "Re-verify stale unsupported E" + (selectedEngineIndex + 1)
                + " (Autopilot)"
            : "Verify E" + (selectedEngineIndex + 1) + " (Autopilot)"
        : acceptedNeedsEngineRecheck
          ? "Re-check Accepted " + selectedReference + " & Engine"
          : matchedEngine
            ? "Verify " + selectedReference + ", Accept & Confirm ↔E"
            : "Verify " + selectedReference + ", Accept & Sync Engine";
      const fullscreenAdjust = document.getElementById("fullscreen-adjust");
      fullscreenAdjust.hidden = Boolean(selectedEngine) || !hasDraft;
      fullscreenAdjust.disabled = !hasDraft || reviewBusy;
      fullscreenAdjust.textContent =
        hasDraft ? "Request " + selectedReference + " Adjustment" : "";
      document.getElementById("fullscreen-cancel-adjustment").hidden =
        Boolean(selectedEngine) || fullscreenDecision !== "adjust";
      document.getElementById("fullscreen-message").placeholder =
        selectedEngine
          ? "Ask Copilot about E" + (selectedEngineIndex + 1) + "…"
          : fullscreenDecision
          ? "Describe the correction, then request an adjustment…"
          : "Ask Copilot about " + selectedReference + "…";
      document.getElementById("fullscreen-chat-activity").dataset.state =
        state.activity?.state || "ready";
      document.getElementById("fullscreen-chat-activity").textContent =
        reviewBusy
          ? "Copilot working"
          : selectedEngine
            ? selectedEngine.review?.status === "confirmed"
              && selectedEngine.review.fresh
              ? "Confirmed reviewed"
              : selectedEngine.review?.status === "not_confirmed"
                && selectedEngine.review.fresh
                ? "Not confirmed · unsupported"
              : selectedEngine.review?.status === "confirmed"
                ? "Review stale"
                : selectedEngine.review?.status === "not_confirmed"
                  ? "Unsupported review stale"
                : "Not independently verified"
            : fullscreenDecision || "Ready";
      document.getElementById("fullscreen-workflow-note").textContent =
        selectedEngine
          ? selectedEngineLinkedRejected
            ? "The nearby C# was rejected, so it does not validate this E#. Ask in Plan mode, then independently verify or re-verify E# in Autopilot."
            : selectedEngine.review?.status === "confirmed"
              && selectedEngine.review.fresh
              ? "This E# has a fresh confirmation receipt. Ask about new evidence in Plan mode, then use Re-verify E# to challenge that receipt."
              : selectedEngine.review?.status === "not_confirmed"
                && selectedEngine.review.fresh
                ? "This exact E# was independently reviewed and not confirmed. It remains visible as engine output; a corrected C# requires separate Add as Review Event confirmation."
              : selectedEngine.review?.status === "confirmed"
                ? "This E# confirmation is stale for the current engine or output. Verify it again before relying on it."
                : selectedEngine.review?.status === "not_confirmed"
                  ? "This E# was not confirmed, but that receipt is stale for the current engine or output. Re-verify it before relying on the result."
                : "This E# has no independent confirmation. Ask in Plan mode, then verify it in Autopilot."
          : fullscreenDecision === "accepted"
            ? draft.comparison?.status === "already_agrees"
              ? selectedReferenceKind + " is already accepted and the current engine/output hashes agree. No recalculation is needed; use Request " + selectedReference + " Adjustment only if the football judgment changes."
              : selectedReferenceKind + " is already accepted, but its engine check is not current or does not agree. Use Re-check Accepted " + selectedReference + " & Engine; hashes determine whether to recalculate cached events or synchronize a general rule."
          : matchedEngine
            ? selectedReferenceKind + " and E# align by team, type, and the applicable time rule. Verify " + selectedReference + " against video before accepting the reference."
            : hasDraft
              ? "This " + selectedReferenceKind + " has no matching E#. Verify and accept " + selectedReference + " only if the video supports it; synchronization follows from the saved engine hashes."
              : "";
      document.getElementById("clip-conversation-title").textContent =
        selectedEngine
          ? "Copilot conversation for E" + (selectedEngineIndex + 1)
          : "Ask Copilot about this clip";
      if (!draft) {
        const emptyTitle = document.getElementById("empty-review-title");
        const emptyDetail = document.getElementById("empty-review-detail");
        if (["processing", "detections_ready", "building"]
          .includes(state.segment.state)) {
          emptyTitle.textContent = "AI is still running";
          emptyDetail.textContent =
            "Event candidates remain hidden until the run completes.";
        } else if (state.segment.state === "ready") {
          emptyTitle.textContent = "AI run complete";
          emptyDetail.textContent =
            "The rules engine did not produce event candidates for this minute.";
        } else {
          emptyTitle.textContent = "No AI events yet";
          emptyDetail.textContent =
            "The video is prepared. Click Start AI when you want event " +
            "processing to begin; preparation alone never starts it.";
        }
        renderActivity();
        renderMessages();
        renderClipMessages();
        updateLiveStatistics(video.currentTime || 0);
        applyPassedSegmentLock();
        return;
      }
      const engineCandidate = draft.source === "engine_output";
      const adjustedProposal = draft.source === "adjusted_proposal";
      const userReported = isManualReviewEvent(draft);
      document.getElementById("event-number").textContent =
        selectedReference + " · Event " + (selectedIndex + 1)
        + " of " + state.drafts.length;
      document.getElementById("event-summary").textContent =
        draft.seconds.toFixed(3) + "s · " + teamLabel(draft.team)
        + " · " + typeLabel(draft.type);
      document.getElementById("proposal-title").textContent = draft.title;
      document.getElementById("proposal-kind").textContent =
        teamLabel(draft.team) + " · " + typeLabel(draft.type);
      const sourceLabel = eventSourceLabel(draft);
      const sourceBadge = document.getElementById("proposal-source");
      sourceBadge.textContent = sourceLabel.label;
      sourceBadge.className = "event-source " + sourceLabel.className;
      document.getElementById("proposal-time").textContent =
        draft.seconds.toFixed(3) + "s · frame " + Math.round(draft.seconds * 25);
      document.getElementById("proposal-evidence").textContent = draft.evidence;
      document.getElementById("evidence-heading").textContent =
        lockedReference
          ? "Reference Basis"
          : engineCandidate
            ? "Engine Evidence"
            : adjustedProposal
              ? "Re-reviewed Evidence"
              : userReported ? "Verification Evidence" : "Video Evidence";
      document.getElementById("proposal-rule").textContent = draft.rule;
      document.getElementById("conversation-title").textContent =
        "Live Copilot for " + selectedReference;
      document.getElementById("conversation-scope-note").textContent =
        matchedEngine
          ? selectedReference + " ↔ E" + (matchedEngineIndex + 1)
            + (
              userReported
                ? " requires same-frame agreement after manual verification."
                : " is an agreement candidate only. This C# still requires video verification."
            )
          : selectedReference + " has no matching engine event.";
      document.getElementById("previous-event").disabled = selectedIndex === 0;
      document.getElementById("next-event").disabled =
        selectedIndex === state.drafts.length - 1;
      applyActionZoom();
      document.querySelector(".decisions").hidden = lockedReference;

      const decision = draft.decision;
      const accepted = decision?.status === "accepted";
      const rejected = decision?.status === "rejected";
      const adjusting = decision?.status === "adjust";
      const finalized = accepted || rejected;
      document.getElementById("proposal").classList.toggle("accepted", accepted);
      document.getElementById("proposal").classList.toggle("rejected", rejected);
      document.getElementById("accept").hidden = finalized;
      document.getElementById("copilot-accept").hidden = finalized;
      document.getElementById("reject").hidden = finalized;
      document.getElementById("cancel-adjustment").hidden = !adjusting;
      document.getElementById("accept").disabled = reviewBusy;
      document.getElementById("adjust").disabled = reviewBusy;
      document.getElementById("reject").disabled = reviewBusy;
      document.getElementById("copilot-accept").disabled =
        finalized || reviewBusy;
      const acceptedEngineRecheck =
        document.getElementById("accepted-engine-recheck");
      acceptedEngineRecheck.hidden =
        !acceptedNeedsEngineRecheck || lockedReference;
      acceptedEngineRecheck.disabled = reviewBusy;
      acceptedEngineRecheck.textContent =
        "Re-check Accepted " + selectedReference + " & Engine (Autopilot)";
      const sameFrameReview =
        document.getElementById("require-same-frame-review");
      sameFrameReview.hidden =
        !hasDraft || isManualReviewEvent(draft) || lockedReference;
      sameFrameReview.disabled =
        reviewBusy || Boolean(draft.sameFrameEngineReview);
      sameFrameReview.textContent = draft.sameFrameEngineReview
        ? "Same-Frame C↔E Timing Required"
        : "Require Same-Frame C↔E Timing";
      document.getElementById("accept").textContent = matchedEngine
        ? "Accept " + selectedReference + " & Check Matched E#"
        : "Accept " + selectedReference + " & Check Engine";
      document.getElementById("adjust").textContent =
        "Request " + selectedReference + " Adjustment";
      document.getElementById("reject").textContent =
        "Reject " + selectedReference + " Proposal";
      document.getElementById("send-message").textContent =
        "Ask Copilot about " + selectedReference + " (Plan mode)";
      document.getElementById("copilot-accept").textContent = matchedEngine
        ? "Verify " + selectedReference + ", Accept & Confirm ↔E (Autopilot)"
        : "Verify " + selectedReference + ", Accept & Sync Engine (Autopilot)";
      renderReviewFlow({
        matched: Boolean(matchedEngine),
        decision,
        comparison: draft.comparison,
      });
      const messageInput = document.getElementById("message");
      const sendMessage = document.getElementById("send-message");
      messageInput.placeholder = finalized
        ? "Describe the correction, then choose Request Adjustment…"
        : "Explain what you see or ask why this event was proposed…";
      sendMessage.disabled = finalized || reviewBusy;
      document.querySelector(".composer-mode").textContent = accepted
        ? "Accepted event locked. Enter a correction above and use Request Adjustment to reopen it."
        : rejected
          ? "Rejected event locked. Only Request Adjustment can reopen it."
          : "Plan mode discusses only. Action buttons explicitly authorize Autopilot changes for this event.";
      document.getElementById("decision-status").textContent = decision
        ? lockedReference
          ? "Published reference · this segment has already passed exact engine validation."
          : {
            accepted: "Accepted reference · engine comparison revealed below.",
            adjust: "Adjustment requested · describe the correction to Copilot.",
            rejected: "Rejected · this proposal will not become an engine requirement."
          }[decision.status]
        : "Engine result hidden until you accept this independent proposal.";
      if (!decision && engineCandidate) {
        document.getElementById("decision-status").textContent =
          "Review this AI candidate against the video, then accept, adjust, or reject it.";
      } else if (!decision && adjustedProposal) {
        document.getElementById("decision-status").textContent =
          "Revised proposal ready · check it again, then accept, adjust, or reject.";
      }

      const engine = document.getElementById("engine-result");
      if (decision?.status === "accepted" && draft.comparison) {
        engine.hidden = false;
        engine.className = "engine-result " + draft.comparison.status;
        document.getElementById("engine-heading").textContent =
          draft.comparison.label;
        document.getElementById("engine-detail").textContent =
          draft.comparison.detail;
        const verification = decision.engineVerification;
        document.getElementById("engine-fingerprint").textContent = verification
          ? (
              (verification.fresh ? "Current engine verified: " : "Stale engine check: ")
              + shortHash(verification.currentEngineContentHash)
              + " · output " + shortHash(verification.currentOutputHash)
            )
          : (
              "Frozen before engine: "
              + shortHash(state.engineBefore.fingerprint.contentHash)
              + " · output " + shortHash(state.engineBefore.outputHash)
            );
        const regression = document.getElementById("regression-status");
        if (draft.comparison.status === "stale") {
          regression.textContent =
            "Rerun required: rebuild cached events only, then run protected regressions.";
        } else if (draft.comparison.status === "already_agrees") {
          regression.textContent =
            state.regression?.passed && state.regression?.fresh
            ? "Regression verified: " + state.regression.summary
            : "No inference change required. Add or retain regression protection.";
        } else if (!state.engineAfter) {
          regression.textContent =
            "Accepted · pending general rule implementation and full regression run.";
        } else if (!state.regression) {
          regression.textContent =
            "Engine rerun captured · protected regression result still pending.";
        } else {
          regression.textContent =
            state.regression.passed && state.regression.fresh
            ? "Implemented · regression verified: " + state.regression.summary
            : state.regression.passed
              ? "Regression result is stale for the current engine/output."
              : "Blocked by regression: " + state.regression.summary;
        }
      } else {
        engine.hidden = true;
      }
      renderActivity();
      renderMessages();
      renderClipMessages();
      applyPassedSegmentLock();
    }

    let stateRefreshPending = false;
    let stateRefreshQueued = false;

    async function loadState() {
      if (stateRefreshPending) {
        stateRefreshQueued = true;
        return;
      }
      stateRefreshPending = true;
      try {
        do {
          stateRefreshQueued = false;
          const previousSegmentKey = state?.segment?.key || null;
          const previousSegmentReady = state?.segment?.state === "ready";
          const url = stateUrl + "?segment=" +
            encodeURIComponent(selectedSegmentKey());
          const response = await fetch(url, { cache: "no-store" });
          if (!response.ok) throw new Error("State HTTP " + response.status);
          const previousActiveBatchId =
            state?.coordinateReview?.activeBatchId || null;
          state = await response.json();
          if (
            runStartPending
            && !["processing", "detections_ready", "building"]
              .includes(state.segment.state)
            && state.activity?.state !== "working"
          ) {
            runStartPending = false;
          }
          if (
            previousSegmentKey !== state.segment.key
            || previousActiveBatchId
              !== (state.coordinateReview?.activeBatchId || null)
          ) {
              if (
                previousActiveBatchId
                !== (state.coordinateReview?.activeBatchId || null)
              ) {
                selectedCoordinateBatchId =
                  state.coordinateReview?.activeBatchId || null;
              }
              loadBallFrameFlags();
          }
          const resetForReadySegment =
            previousSegmentKey !== state.segment.key
            || (!previousSegmentReady && state.segment.state === "ready");
          const ballStatesAvailable = trajectoryAuditMode
            || (state.segment.ballTrackAvailable && !segmentRunActive());
          if (!ballStatesAvailable) {
            ballTrack = null;
            ballTrackSegmentKey = null;
          } else if (
            ballTrackSegmentKey !== state.segment.key
            || (
              trajectoryAuditMode
              && ballTrack?.pendingEngineOutput
              && state.segment.ballTrackAvailable
            )
          ) {
            const ballResponse = await fetch(
              "/api/ball-track?segment=" +
              encodeURIComponent(state.segment.key)
              + (trajectoryAuditMode ? "&audit=1" : ""),
              {cache: "no-store"}
            );
            ballTrack = ballResponse.ok ? await ballResponse.json() : null;
            ballTrackSegmentKey = state.segment.key;
            document.getElementById("ball-frame-filter").value =
              trajectoryAuditMode
                ? "all"
                : state.ballRecoveryDiagnostic?.status === "focused_unpersisted"
                ? "diagnostic"
                : state.segment.state === "failed" ? "estimated" : "all";
            if (trajectoryAuditMode) loadBallFrameFlags();
          }
          selectedIndex = Math.max(
            0,
            Math.min(selectedIndex, state.drafts.length - 1)
          );
          if (resetForReadySegment) selectedIndex = 0;
          if (
            pendingMissingReport
            && state.drafts.length > pendingMissingReport.count
          ) {
            const addedIndex = state.drafts.findIndex((draft, index) =>
              index >= pendingMissingReport.count
              && draft.source === "user_reported"
              && Math.abs(draft.seconds - pendingMissingReport.seconds) <= 0.5
            );
            if (addedIndex >= 0) {
              selectedIndex = addedIndex;
              video.pause();
              video.currentTime = state.drafts[addedIndex].seconds;
              pendingMissingReport = null;
              document.getElementById("missing-event-status").textContent =
                "Verified proposal added below. Review it, then accept or reject it.";
            }
          }
          render();
          if (resetForReadySegment) {
            resetReviewPlayback();
            if (state.drafts.length) {
              selectEvent(0, {seek: false, pause: false});
            }
          }
        } while (stateRefreshQueued);
      } finally {
        stateRefreshPending = false;
      }
    }

    async function sendClipMessage(mode = "plan") {
      const noteInput = document.getElementById("clip-message");
      const status = document.getElementById("missing-event-status");
      if (selectedEngineIndex !== null && mode === "autopilot") {
        await requestEngineEventVerification(
          selectedEngineIndex,
          "missing-event-status",
          "clip-message"
        );
        return;
      }
      const text = noteInput.value.trim();
      if (!text) {
        status.textContent = "Enter a question or observation about this clip.";
        noteInput.focus();
        return;
      }
      if (selectedEngineIndex !== null) {
        await sendEngineConversationMessage(
          "clip-message",
          "missing-event-status",
          mode === "plan" ? "send-clip-plan" : "send-clip-autopilot"
        );
        return;
      }
      const buttons = [
        document.getElementById("send-clip-plan"),
        document.getElementById("send-clip-autopilot")
      ];
      const seconds = Math.min(
        state.segment.durationSeconds,
        Math.max(0, video.currentTime || 0)
      );
      const scope = document.getElementById("clip-message-scope").value;
      buttons.forEach(button => { button.disabled = true; });
      status.textContent =
        "Sending this clip question to Copilot in " +
        (mode === "autopilot" ? "Autopilot inspection mode" : "Plan mode") +
        "…";
      try {
        const response = await fetch("/api/clip-message", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            segment: selectedSegmentKey(),
            seconds,
            text,
            selectedIndex: state.drafts.length ? selectedIndex : null,
            mode,
            scope,
            flaggedFrames: [...flaggedBallFrames].sort((a, b) => a - b)
          })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not send clip question");
        }
        noteInput.value = "";
        status.textContent =
          mode === "autopilot"
            ? "Sent in Autopilot inspection mode. Adding an event still requires separate confirmation."
            : "Sent in Plan mode. Copilot will reply only in the clip conversation.";
        await loadState();
      } catch (error) {
        status.textContent = error.message;
      } finally {
        buttons.forEach(button => { button.disabled = false; });
      }
    }

    function updateClipMessageTargets() {
      renderClipConversationControls();
    }

    function selectedManualReviewFrame() {
      const secondValue =
        document.getElementById("manual-review-second").value;
      const frameValue =
        document.getElementById("manual-review-frame").value;
      if (secondValue === "" || frameValue === "") return null;
      const second = Number(secondValue);
      const frameWithinSecond = Number(frameValue);
      const maximumFrame = Math.round(
        Number(state?.segment?.durationSeconds || 0) * REVIEW_FPS
      );
      return Math.min(
        maximumFrame,
        Math.max(0, second * REVIEW_FPS + frameWithinSecond)
      );
    }

    function updateManualReviewTime() {
      const frameSelect = document.getElementById("manual-review-frame");
      const selectedSecond = Number(
        document.getElementById("manual-review-second").value
      );
      const maximumFrame = Math.round(
        Number(state?.segment?.durationSeconds || 0) * REVIEW_FPS
      );
      Array.from(frameSelect.options).forEach(option => {
        if (option.value === "") return;
        option.disabled =
          !Number.isFinite(selectedSecond)
          || selectedSecond * REVIEW_FPS + Number(option.value) > maximumFrame;
      });
      if (frameSelect.selectedOptions[0]?.disabled) {
        frameSelect.value = "";
      }
      const frame = selectedManualReviewFrame();
      const button = document.getElementById("create-manual-review");
      if (frame === null) {
        document.getElementById("manual-review-time").textContent =
          "Choose the event second and millisecond frame.";
        button.textContent = "Choose Time to Create Manual M#";
        button.disabled = true;
        return;
      }
      const seconds = frame / REVIEW_FPS;
      const label =
        seconds.toFixed(3) + "s · frame " + frame;
      document.getElementById("manual-review-time").textContent =
        "Selected time: " + label;
      button.textContent =
        "Create Manual M# at " + label;
      button.disabled =
        state.activity?.state === "working" || referenceLocked();
    }

    function initializeManualReviewTime() {
      const secondSelect = document.getElementById("manual-review-second");
      const frameSelect = document.getElementById("manual-review-frame");
      const maximumFrame = Math.round(
        Number(state.segment.durationSeconds) * REVIEW_FPS
      );
      secondSelect.replaceChildren();
      const secondPlaceholder = document.createElement("option");
      secondPlaceholder.value = "";
      secondPlaceholder.textContent = "Choose second";
      secondPlaceholder.selected = true;
      secondSelect.append(secondPlaceholder);
      for (
        let second = 0;
        second <= Math.floor(maximumFrame / REVIEW_FPS);
        second += 1
      ) {
        const option = document.createElement("option");
        option.value = String(second);
        option.textContent = second + "s";
        secondSelect.append(option);
      }
      frameSelect.replaceChildren();
      const framePlaceholder = document.createElement("option");
      framePlaceholder.value = "";
      framePlaceholder.textContent = "Choose milliseconds / frame";
      framePlaceholder.selected = true;
      frameSelect.append(framePlaceholder);
      for (let frame = 0; frame < REVIEW_FPS; frame += 1) {
        const option = document.createElement("option");
        option.value = String(frame);
        option.textContent =
          String(frame * 40).padStart(3, "0") + " ms · frame +" + frame;
        frameSelect.append(option);
      }
      updateManualReviewTime();
    }

    function toggleManualReviewForm() {
      const fields = document.getElementById("manual-review-fields");
      fields.hidden = !fields.hidden;
      document.getElementById("toggle-manual-review").textContent =
        fields.hidden ? "Add Manual Review" : "Close Manual Review";
      if (!fields.hidden) {
        initializeManualReviewTime();
        document.getElementById("manual-review-note").focus();
      }
    }

    async function createManualReviewEvent() {
      const noteInput = document.getElementById("manual-review-note");
      const note = noteInput.value.trim();
      const status = document.getElementById("missing-event-status");
      if (!note) {
        status.textContent = "Add an evidence note for this manual review.";
        noteInput.focus();
        return;
      }
      const button = document.getElementById("create-manual-review");
      const selectedFrame = selectedManualReviewFrame();
      if (selectedFrame === null) {
        status.textContent =
          "Choose both the event second and millisecond frame.";
        document.getElementById("manual-review-second").focus();
        return;
      }
      const seconds = selectedFrame / REVIEW_FPS;
      button.disabled = true;
      status.textContent = "Creating an unaccepted manual M#…";
      try {
        const response = await fetch("/api/manual-review-event", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            segment: selectedSegmentKey(),
            seconds,
            team: document.getElementById("manual-review-team").value,
            eventType: document.getElementById("manual-review-type").value,
            note
          })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not create manual M#");
        }
        noteInput.value = "";
        document.getElementById("manual-review-fields").hidden = true;
        document.getElementById("toggle-manual-review").textContent =
          "Add Manual Review";
        await loadState();
        selectEvent(result.index);
        status.textContent =
          "Manual M" + (result.index + 1)
          + " created. Verify it before accepting or rejecting it.";
      } catch (error) {
        status.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    }

    async function confirmMissingEvent() {
      const candidate = state.pendingMissingCandidate;
      if (!candidate?.supported) return;
      const button = document.getElementById("confirm-missing-event");
      const status = document.getElementById("missing-event-status");
      button.disabled = true;
      pendingMissingReport = {
        seconds: candidate.seconds,
        count: state.drafts.length
      };
      status.textContent =
        "Autopilot is adding the planned candidate for event review. It is not accepted yet.";
      try {
        const response = await fetch("/api/confirm-missing-event", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({segment: selectedSegmentKey()})
        });
        const result = await response.json();
        if (!response.ok) {
          pendingMissingReport = null;
          throw new Error(result.error || "Could not add planned event");
        }
        await loadState();
      } catch (error) {
        status.textContent = error.message;
        button.disabled = false;
      }
    }

    async function decide(status, targetIndex = selectedIndex) {
      const note = status === "adjust"
        ? document.getElementById("message").value.trim()
        : "";
      const response = await fetch("/api/decision", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          segment: selectedSegmentKey(),
          index: targetIndex,
          status,
          note
        })
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Decision failed");
      }
      state = await response.json();
      render();
    }

    async function requestEngineEventVerification(
      engineIndex,
      statusId = "missing-event-status",
      textareaId = null
    ) {
      const status = document.getElementById(statusId);
      const engine = state.engineEvents?.[engineIndex];
      const textarea = textareaId
        ? document.getElementById(textareaId)
        : null;
      const reviewFocus = textarea?.value.trim() || "";
      if (!engine) return;
      status.textContent = engine.review?.fresh
        ? "Copilot is re-verifying E" + (engineIndex + 1)
          + " against the raw video and current hashes…"
        : "Copilot is independently verifying E" + (engineIndex + 1)
          + " against the raw video…";
      try {
        const response = await fetch("/api/copilot-verify-engine", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            segment: selectedSegmentKey(),
            index: engineIndex,
            note: reviewFocus,
          })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(
            result.error || "Could not start engine-event verification"
          );
        }
        if (textarea) textarea.value = "";
        await loadState();
      } catch (error) {
        status.textContent = error.message;
      }
    }

    async function sendReviewMessage(text, mode = "plan") {
      const response = await fetch("/api/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          segment: selectedSegmentKey(),
          index: selectedIndex,
          text,
          mode
        })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Message failed");
      await loadState();
    }

    async function requestCopilotAcceptance(targetIndex = selectedIndex) {
      const draft = state.drafts[targetIndex];
      if (!draft || draft.decision) return;
      const button = document.getElementById("copilot-accept");
      const status = document.getElementById("decision-status");
      const reference = reviewReference(draft, targetIndex);
      button.disabled = true;
      status.textContent =
        "Copilot is verifying " + reference
        + ", then checking whether the rules engine needs a general fix.";
      try {
        const response = await fetch("/api/copilot-accept", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            segment: selectedSegmentKey(),
            index: targetIndex
          })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Copilot verification failed");
        }

        async function requireSameFrameReview(targetIndex = selectedIndex) {
          const draft = state.drafts[targetIndex];
          if (!draft || isManualReviewEvent(draft)) return;
          const button = document.getElementById("require-same-frame-review");
          const status = document.getElementById("decision-status");
          button.disabled = true;
          status.textContent =
            "Saving the same-frame timing requirement for C"
            + (targetIndex + 1) + "…";
          try {
            const response = await fetch("/api/require-same-frame-review", {
              method: "POST",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify({
                segment: selectedSegmentKey(),
                index: targetIndex,
              }),
            });
            const result = await response.json();
            if (!response.ok) {
              throw new Error(
                result.error || "Could not require same-frame timing review"
              );
            }
            await loadState();
          } catch (error) {
            status.textContent = error.message;
            button.disabled = false;
          }
        }
        await loadState();
      } catch (error) {
        status.textContent = error.message;
        button.disabled = false;
      }
    }

    async function requestAcceptedEngineRecheck(targetIndex = selectedIndex) {
      const draft = state.drafts[targetIndex];
      if (draft?.decision?.status !== "accepted") return;
      const status = document.getElementById("decision-status");
      status.textContent =
        "Checking the accepted " + reviewReference(draft, targetIndex)
        + " against the current engine source and cached-output hashes…";
      try {
        const response = await fetch("/api/copilot-recheck-accepted", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            segment: selectedSegmentKey(),
            index: targetIndex,
          }),
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(
            result.error || "Could not start the accepted-event engine re-check"
          );
        }
        await loadState();
      } catch (error) {
        status.textContent = error.message;
        document.getElementById("fullscreen-chat-status").textContent =
          error.message;
      }
    }

    async function requestCopilotAcceptanceAll() {
      const button = document.getElementById("accept-all-events");
      const status = document.getElementById("missing-event-status");
      button.disabled = true;
      status.textContent =
        "Copilot is verifying every unaccepted proposal as one batch. "
        + "Unsupported events will remain unaccepted.";
      try {
        const response = await fetch("/api/copilot-accept-all", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({segment: selectedSegmentKey()})
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Batch verification failed");
        }
        document.getElementById("clip-conversation-panel").scrollIntoView({
          behavior: "smooth",
          block: "nearest"
        });
        await loadState();
      } catch (error) {
        status.textContent = error.message;
        button.disabled = false;
      }
    }

    async function requestReferencePublication() {
      const button = document.getElementById("publish-reference");
      const status = document.getElementById("publication-status");
      button.disabled = true;
      status.textContent =
        "Running protected regressions and the final exact-match gate…";
      try {
        const response = await fetch("/api/publish-reference", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({segment: selectedSegmentKey()})
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Final publication failed");
        }
        await loadState();
        document.getElementById("publication-status").textContent =
          "Final publication handover started. Copilot is running the "
          + "validation gate…";
      } catch (error) {
        status.textContent = error.message;
        button.disabled = false;
      }
    }

    async function requestAdjustment({
      textareaId = "message",
      statusId = "composer-status",
      buttonId = "adjust",
    } = {}) {
      const textarea = document.getElementById(textareaId);
      const note = textarea.value.trim();
      const composerStatus = document.getElementById(statusId);
      if (!note) {
        composerStatus.textContent =
          "Describe what is inaccurate in the message box first.";
        textarea.focus();
        return;
      }
      const button = document.getElementById(buttonId);
      button.disabled = true;
      composerStatus.textContent =
        "Sending this event to Copilot for re-review…";
      try {
        await decide("adjust");
        await sendReviewMessage(
          "Please re-check this proposal against the video. " +
          "The correction I see is: " + note,
          "autopilot"
        );
        document.getElementById("message").value = "";
        document.getElementById("fullscreen-message").value = "";
        composerStatus.textContent =
          "Re-review requested. Stay on this event; a revised proposal will refresh here.";
      } catch (error) {
        composerStatus.textContent =
          "Could not request re-review: " + error.message;
      } finally {
        button.disabled = state.activity?.state === "working";
      }
    }

    function seekVideo(seconds) {
      video.pause();
      pendingReviewSeconds = seconds;
      if (video.readyState >= 1) {
        video.currentTime = pendingReviewSeconds;
        previousPlaybackSeconds = pendingReviewSeconds;
        pendingReviewSeconds = null;
        updateBallMarker();
        updateLiveStatistics(video.currentTime);
      }
    }

    function resetReviewPlayback() {
      video.pause();
      pendingReviewSeconds = 0;
      previousPlaybackSeconds = 0;
      timeline.value = "0";
      document.getElementById("time").textContent = "0.00s";
      clearEventTriggers();
      if (video.readyState >= 1) {
        video.currentTime = 0;
        pendingReviewSeconds = null;
      }
      updateBallMarker();
      updateLiveStatistics(0);
      updateFullscreenEventProgress(0);
    }

    function scrollSelectedComparisonIntoView() {
      const selected = document.querySelector(
        '#fullscreen-event-items '
        + '[data-event-source="review"][data-event-index="'
        + selectedIndex + '"]'
      );
      selected?.closest(".comparison-row")?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }

    function selectEvent(index, options = {}) {
      if (!state.drafts.length) return;
      selectedEngineIndex = null;
      const seek = options.seek !== false;
      const pause = options.pause !== false;
      selectedIndex = Math.max(0, Math.min(state.drafts.length - 1, index));
      if (pause) video.pause();
      if (seek) {
        seekVideo(currentDraft().seconds);
      }
      document.getElementById("message").value = "";
      document.getElementById("composer-status").textContent = "";
      document.getElementById("fullscreen-message").value = "";
      document.getElementById("fullscreen-chat-status").textContent = "";
      render();
      if (document.fullscreenElement === videoShell) {
        requestAnimationFrame(scrollSelectedComparisonIntoView);
      }
    }

    function showGeneralClipConversation() {
      selectedEngineIndex = null;
      document.getElementById("clip-message").value = "";
      document.getElementById("missing-event-status").textContent = "";
      render();
      document.getElementById("clip-conversation-panel").scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      document.getElementById("clip-message").focus();
    }

    function showEventTrigger(source, index) {
      const event = source === "copilot"
        ? state.drafts[index]
        : state.engineEvents[index];
      if (!event) return;
      const trigger = document.getElementById(source + "-event-trigger");
      const prefix = source === "copilot" ? "C" : "E";
      const label = source === "copilot"
        ? playbackEventLabel(event)
        : canonicalComparisonLabel(event);
      document.getElementById(source + "-event-trigger-label").textContent =
        prefix + (index + 1) + " · " + label;
      trigger.hidden = false;
      trigger.classList.remove("active");
      void trigger.offsetWidth;
      trigger.classList.add("active");
      const button = document.querySelector(
        '[data-event-source="' + (
          source === "copilot" ? "review" : "engine"
        ) + '"][data-event-index="' + index + '"]'
      );
      if (button) {
        button.classList.remove("playback-ping");
        void button.offsetWidth;
        button.classList.add("playback-ping");
      }
      clearTimeout(eventTriggerTimers[source]);
      eventTriggerTimers[source] = setTimeout(() => {
        trigger.hidden = true;
        trigger.classList.remove("active");
        button?.classList.remove("playback-ping");
      }, 1600);
    }

    function followPlaybackEvents() {
      const seconds = Math.min(60, Math.max(0, video.currentTime || 0));
      updateLiveStatistics(seconds);
      updateFullscreenEventProgress(seconds);
      if (seconds < previousPlaybackSeconds - 0.08) {
        clearEventTriggers();
        previousPlaybackSeconds = seconds;
      }
      const crossedCopilot = state?.drafts
        ?.map((draft, index) => ({draft, index}))
        .filter(({draft}) =>
          draft.seconds > previousPlaybackSeconds
          && draft.seconds <= seconds + 0.02
        );
      for (const event of crossedCopilot || []) {
        selectEvent(event.index, {seek: false, pause: false});
        showEventTrigger("copilot", event.index);
      }
      const crossedEngine = state?.engineEvents
        ?.map((engine, index) => ({engine, index}))
        .filter(({engine}) =>
          engine.seconds > previousPlaybackSeconds
          && engine.seconds <= seconds + 0.02
        );
      for (const event of crossedEngine || []) {
        showEventTrigger("engine", event.index);
      }
      previousPlaybackSeconds = seconds;
      if (!video.paused && !video.ended) {
        playbackFrameRequest = requestAnimationFrame(followPlaybackEvents);
      }
    }

    document.getElementById("previous-event").addEventListener(
      "click", () => selectEvent(selectedIndex - 1)
    );
    segmentSelect.addEventListener("change", async () => {
      selectedIndex = 0;
      actionZoom = false;
      viewMode = "normal";
      ballTrack = null;
      ballTrackSegmentKey = null;
      segmentBuilderInitialized = false;
      const segment = segmentSelect.value;
      const query = new URLSearchParams(location.search);
      query.set("segment", segment);
      history.replaceState(null, "", location.pathname + "?" + query);
      state = null;
      video.pause();
      await loadState();
      await loadGeometry();
    });
    sourceSelect.addEventListener("change", async () => {
      const segment = state.segments.find(
        candidate => candidate.datasetId === sourceSelect.value
      );
      if (!segment) return;
      segmentSelect.value = segment.key;
      segmentSelect.dispatchEvent(new Event("change"));
    });
    addCameraButton.addEventListener("click", async () => {
      const name = cameraName.value.trim();
      const club = cameraClub.value.trim();
      const venue = cameraVenue.value.trim();
      const position = cameraPosition.value.trim();
      const serial = cameraSerial.value.trim();
      const file = cameraSample.files?.[0];
      if (!club || !venue || !position || !name || !file) {
        cameraImportStatus.textContent =
          "Enter club, venue, camera position, camera name, and choose a raw sample.";
        return;
      }
      addCameraButton.disabled = true;
      cameraImportStatus.textContent =
        "Checking and importing this camera sample…";
      try {
        const metadata = await inspectVideoFile(file);
        if (![30, 60].some(
          duration => Math.abs(metadata.duration - duration) <= 0.25
        )) {
          throw new Error("Camera sample must be exactly 30 or 60 seconds");
        }
        const query = new URLSearchParams({
          name,
          club,
          venue,
          position,
          serial,
          file: file.name,
          width: String(metadata.width),
          height: String(metadata.height),
          duration: String(metadata.duration)
        });
        const response = await fetch("/api/custom-camera?" + query, {
          method: "POST",
          headers: {"Content-Type": file.type || "application/octet-stream"},
          body: file
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Camera sample could not be added");
        }
        history.replaceState(
          null,
          "",
          "?segment=" + encodeURIComponent(result.segment)
        );
        state = null;
        selectedIndex = 0;
        actionZoom = false;
        viewMode = "normal";
        ballTrack = null;
        ballTrackSegmentKey = null;
        segmentBuilderInitialized = false;
        await loadState();
        await loadGeometry();
        cameraImportStatus.textContent =
          "Camera sample added. Draw and save its calibration before running AI.";
      } catch (error) {
        cameraImportStatus.textContent =
          "Could not add camera: " + error.message;
      } finally {
        addCameraButton.disabled = false;
      }
    });
    prepareButton.addEventListener("click", async () => {
      const minute = Number(startMinute.value);
      const second = Number(startSecond.value);
      const duration = Number(segmentDuration.value);
      if (
        !Number.isInteger(minute) || minute < 0 ||
        !Number.isInteger(second) || second < 0 || second > 59
      ) {
        segmentRunStatus.textContent =
          "Enter a non-negative minute and a second from 0 to 59.";
        return;
      }
      if (![20, 30, 60].includes(duration)) {
        segmentRunStatus.textContent =
          "Choose a 20-, 30-, or 60-second review duration.";
        return;
      }
      segmentPreparationPending = true;
      renderRunControls();
      renderAiGate();
      segmentRunStatus.textContent =
        "Preparing the " + duration + "-second playable video window locally. " +
        "AI and Copilot conversations are disabled. " +
        "Next: start the full raw-video AI run.";
      try {
        const response = await fetch("/api/prepare", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            start_seconds: minute * 60 + second,
            duration_seconds: duration,
            source_id: state.segment.datasetId,
            source_segment: state.segment.key
          })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not prepare segment");
        }
        state = result;
        selectedIndex = 0;
        actionZoom = false;
        viewMode = "normal";
        ballTrack = null;
        ballTrackSegmentKey = null;
        segmentBuilderInitialized = false;
        history.replaceState(
          null,
          "",
          "?segment=" + encodeURIComponent(state.segment.key)
        );
        render();
        resetReviewPlayback();
        if (state.drafts.length) {
          selectEvent(0, {seek: false, pause: false});
        }
      } catch (error) {
        segmentRunStatus.textContent =
          "Could not prepare segment: " + error.message;
      } finally {
        segmentPreparationPending = false;
        renderRunControls();
        renderAiGate();
      }
    });
    [startMinute, startSecond, segmentDuration].forEach(control => {
      control.addEventListener("input", renderRunControls);
      control.addEventListener("change", renderRunControls);
    });
    processButton.addEventListener("click", async () => {
      const segment = selectedSegmentKey();
      runStartPending = true;
      ballTrack = null;
      ballTrackSegmentKey = null;
      renderBallFrames();
      renderRunControls();
      renderAiGate();
      segmentRunStatus.textContent =
        state.segment.recoveryAvailable
          ? "Resuming after interrupted processing. Completed raw-video " +
            "detections are preserved; ball coordinates and every later " +
            "artifact will be rebuilt. This is not a cold-path benchmark " +
            "and does not invoke Copilot."
          : "Starting a local rerun from the raw video. Existing detections, " +
            "ball coordinates, tracks, events, review labels, and provider " +
            "annotations will not be used. This does not invoke Copilot.";
      try {
        const response = await fetch("/api/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            segment,
            resumeAfterDetection: state.segment.recoveryAvailable
          })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not start AI");
        }
        runStartPending = false;
        await loadState();
        renderRunControls();
        renderAiGate();
      } catch (error) {
        runStartPending = false;
        segmentRunStatus.textContent =
          "Could not start AI: " + error.message;
        renderRunControls();
        renderAiGate();
      }
    });
    document.getElementById("next-event").addEventListener(
      "click", () => selectEvent(selectedIndex + 1)
    );
    document.getElementById("accept").addEventListener(
      "click", () => decide("accepted")
    );
    document.getElementById("copilot-accept").addEventListener(
      "click", () => requestCopilotAcceptance(selectedIndex)
    );
    document.getElementById("require-same-frame-review").addEventListener(
      "click", () => requireSameFrameReview(selectedIndex)
    );
    document.getElementById("accept-all-events").addEventListener(
      "click", requestCopilotAcceptanceAll
    );
    document.getElementById("publish-reference").addEventListener(
      "click", requestReferencePublication
    );
    document.getElementById("adjust").addEventListener(
      "click", requestAdjustment
    );
    document.getElementById("cancel-adjustment").addEventListener(
      "click",
      () => cancelAdjustment().catch(error => {
        document.getElementById("composer-status").textContent = error.message;
      })
    );
    document.getElementById("fullscreen-adjust").addEventListener(
      "click",
      () => requestAdjustment({
        textareaId: "fullscreen-message",
        statusId: "fullscreen-chat-status",
        buttonId: "fullscreen-adjust",
      })
    );
    document.getElementById("fullscreen-primary-action").addEventListener(
      "click",
      async () => {
        if (selectedEngineIndex !== null) {
          await requestEngineEventVerification(
            selectedEngineIndex,
            "fullscreen-chat-status",
            "fullscreen-message"
          );
          return;
        }
        if (currentDraft()?.decision?.status === "accepted") {
          await requestAcceptedEngineRecheck(selectedIndex);
          return;
        }
        await requestCopilotAcceptance(selectedIndex);
      }
    );
    document.getElementById("accepted-engine-recheck").addEventListener(
      "click",
      () => requestAcceptedEngineRecheck(selectedIndex)
    );
    document.getElementById("review-audience").addEventListener(
      "change",
      event => {
        const selectedMode = event.currentTarget.value;
        reviewAudience = selectedMode === "developer"
          ? "developer"
          : "reviewer";
        localStorage.setItem("football-review-audience", reviewAudience);
        if (selectedMode === "trajectory-audit" || trajectoryAuditMode) {
          const query = new URLSearchParams(location.search);
          if (selectedMode === "trajectory-audit") {
            query.set("mode", "trajectory-audit");
          } else {
            query.delete("mode");
          }
          location.assign(location.pathname + "?" + query);
          return;
        }
        renderDeveloperMode();
      }
    );
    document.querySelectorAll("[data-copy-developer]").forEach(button => {
      button.addEventListener("click", () => {
        const panel = button.closest("[data-developer-panel]");
        void copyDeveloperCommand(
          button.dataset.copyDeveloper,
          panel.querySelector("[data-developer-status]")
        );
      });
    });
    document.querySelectorAll("[data-developer-refresh]").forEach(button => {
      button.addEventListener("click", () => {
        const panel = button.closest("[data-developer-panel]");
        void refreshDeveloperOutput(
          panel.querySelector("[data-developer-status]")
        );
      });
    });
    document.querySelectorAll("[data-developer-copilot]").forEach(button => {
      button.addEventListener("click", () => {
        if (!developerGuidance().canCopilotImplement) return;
        void requestAcceptedEngineRecheck(selectedIndex);
      });
    });
    document.getElementById("reject").addEventListener(
      "click", () => decide("rejected")
    );

    document.getElementById("previous-frame").addEventListener("click", () => {
      video.pause();
      video.currentTime = Math.max(0, video.currentTime - 1 / 25);
    });
    document.getElementById("next-frame").addEventListener("click", () => {
      video.pause();
      video.currentTime = Math.min(
        Number.isFinite(video.duration) ? video.duration : 60,
        video.currentTime + 1 / 25
      );
    });
    document.getElementById("toggle-event-panel").addEventListener(
      "click",
      () => {
        const hidden = videoShell.classList.toggle("events-hidden");
        const button = document.getElementById("toggle-event-panel");
        button.textContent = hidden ? "Show event panel" : "Hide event panel";
        button.setAttribute("aria-expanded", String(!hidden));
      }
    );
    document.getElementById("playback-speed").addEventListener(
      "change",
      event => {
        video.playbackRate = Number(event.currentTarget.value);
      }
    );
    timeline.addEventListener("input", () => {
      video.pause();
      video.currentTime = Number(timeline.value);
    });
    video.addEventListener("timeupdate", () => {
      const seconds = Math.min(60, Math.max(0, video.currentTime || 0));
      timeline.value = String(seconds);
      document.getElementById("time").textContent = seconds.toFixed(2) + "s";
      updateClipMessageTargets();
      updateBallMarker();
      updateLiveStatistics(seconds);
      updateFullscreenEventProgress(seconds);
    });
    video.addEventListener("play", () => {
      cancelAnimationFrame(playbackFrameRequest);
      previousPlaybackSeconds = video.currentTime;
      playbackFrameRequest = requestAnimationFrame(followPlaybackEvents);
    });
    video.addEventListener("pause", () => {
      cancelAnimationFrame(playbackFrameRequest);
      playbackFrameRequest = null;
      previousPlaybackSeconds = video.currentTime;
    });
    video.addEventListener("ended", () => {
      cancelAnimationFrame(playbackFrameRequest);
      playbackFrameRequest = null;
    });
    video.addEventListener("seeked", () => {
      const seconds = Math.min(60, Math.max(0, video.currentTime || 0));
      previousPlaybackSeconds = seconds;
      clearEventTriggers();
      updateBallMarker();
      updateLiveStatistics(seconds);
      updateFullscreenEventProgress(seconds);
    });
    video.addEventListener("loadedmetadata", drawGeometry);
    ["show-pitch", "show-goals"].forEach((id) => {
      document.getElementById(id).addEventListener("change", drawGeometry);
    });
    document.getElementById("edit-geometry").addEventListener("click", () => {
      editingFeature = document.getElementById("geometry-feature").value;
      geometry.features[editingFeature] = [];
      geometryCanvas.classList.add("editing");
      geometryStatus.textContent =
        "Click points for " + editingFeature.replaceAll("_", " ") +
        ". Trace the outer edge of painted pitch lines. For a goal, click " +
        "all four visible goal-frame corners clockwise.";
      drawGeometry();
    });
    document.getElementById("undo-geometry").addEventListener("click", () => {
      if (!editingFeature) return;
      geometry.features[editingFeature].pop();
      drawGeometry();
    });
    document.getElementById("finish-geometry").addEventListener("click", () => {
      if (!editingFeature) return;
      const minimumPoints = editingFeature.endsWith("goal_mouth") ? 4 : 2;
      if (geometry.features[editingFeature].length < minimumPoints) {
        geometryStatus.textContent =
          "Add at least " + minimumPoints + " points before finishing.";
        return;
      }
      const completed = editingFeature;
      editingFeature = null;
      geometryCanvas.classList.remove("editing");
      saveGeometry();
      geometryStatus.textContent =
        completed.replaceAll("_", " ") +
        " saved locally for this camera.";
    });
    document.getElementById("restore-geometry").addEventListener(
      "click",
      () => {
        if (!repositoryGeometry) return;
        geometry = cloneGeometry(repositoryGeometry);
        editingFeature = null;
        geometryCanvas.classList.remove("editing");
        localStorage.removeItem(
          state.segment.calibrationId + "-geometry-v1"
        );
        geometryStatus.textContent =
          "Restored the repository camera calibration.";
        drawGeometry();
      },
    );
    document.getElementById("save-geometry").addEventListener(
      "click",
      async () => {
        geometryStatus.textContent = "Saving this camera calibration…";
        try {
          await saveGeometry();
          geometryStatus.textContent =
            "Calibration saved. Start AI is now available.";
        } catch (error) {
          geometryStatus.textContent =
            "Calibration is incomplete: " + error.message;
        }
      },
    );
    geometryCanvas.addEventListener("click", (event) => {
      if (!editingFeature) return;
      const layout = mediaLayout();
      const rect = geometryCanvas.getBoundingClientRect();
      const displayX =
        (event.clientX - rect.left) * geometryCanvas.clientWidth / rect.width;
      const displayY =
        (event.clientY - rect.top) * geometryCanvas.clientHeight / rect.height;
      const x = displayX - layout.x;
      const y = displayY - layout.y;
      if (x < 0 || y < 0 || x > layout.width || y > layout.height) return;
      geometry.features[editingFeature].push([
        Math.round(x * geometry.image_width / layout.width),
        Math.round(y * geometry.image_height / layout.height),
      ]);
      drawGeometry();
    });
    document.getElementById("export-geometry").addEventListener(
      "click",
      () => {
        const link = document.createElement("a");
        link.href = URL.createObjectURL(new Blob(
          [JSON.stringify(geometry, null, 2)],
          {type: "application/json"},
        ));
        link.download =
          (geometry.camera_id || "camera") + "-pitch-calibration.json";
        link.click();
        URL.revokeObjectURL(link.href);
      },
    );
    document.querySelectorAll("[data-view-mode]").forEach(button => {
      button.addEventListener("click", () => {
        setViewMode(button.dataset.viewMode);
      });
    });
    initializeBallFrameControls();
    document.getElementById("clip-composer").addEventListener(
      "submit",
      event => event.preventDefault()
    );
    document.getElementById("send-clip-plan").addEventListener(
      "click",
      () => void sendClipMessage("plan")
    );
    document.getElementById("send-clip-autopilot").addEventListener(
      "click",
      () => void sendClipMessage("autopilot")
    );
    document.getElementById("clip-message-scope").addEventListener(
      "change",
      updateClipMessageTargets
    );
    document.getElementById("toggle-manual-review").addEventListener(
      "click",
      toggleManualReviewForm
    );
    document.getElementById("manual-review-second").addEventListener(
      "change",
      updateManualReviewTime
    );
    document.getElementById("manual-review-frame").addEventListener(
      "change",
      updateManualReviewTime
    );
    document.getElementById("create-manual-review").addEventListener(
      "click",
      createManualReviewEvent
    );
    document.getElementById("show-general-clip-conversation").addEventListener(
      "click",
      showGeneralClipConversation
    );
    document.getElementById("confirm-missing-event").addEventListener(
      "click",
      confirmMissingEvent
    );
    document.getElementById("enlarge").addEventListener("click", async () => {
      if (document.fullscreenElement === videoShell) {
        await document.exitFullscreen();
      } else {
        await videoShell.requestFullscreen();
      }
    });
    document.getElementById("zoom-action").addEventListener("click", () => {
      actionZoom = !actionZoom;
      applyActionZoom();
    });
    document.addEventListener("fullscreenchange", () => {
      document.getElementById("enlarge").textContent =
        document.fullscreenElement === videoShell
          ? "Exit Full Screen"
          : "Enlarge Review";
      document.getElementById("toggle-event-panel").setAttribute(
        "aria-expanded",
        String(!videoShell.classList.contains("events-hidden"))
      );
      drawGeometry();
      if (document.fullscreenElement === videoShell) {
        requestAnimationFrame(scrollSelectedComparisonIntoView);
      } else if (selectedEngineIndex !== null) {
        document.getElementById("clip-conversation-panel").scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }
    });
    window.addEventListener("resize", drawGeometry);

    replayRunSelect.addEventListener("change", () => {
      replayVideo.pause();
      replayRunId = replayRunSelect.value;
      loadReplaySegment(0);
      renderReplayCatalog();
    });
    document.getElementById("replay-play").addEventListener("click", () => {
      const run = currentReplayRun();
      if (!run) return;
      if (
        replaySegmentIndex === run.segments.length - 1
        && replayVideo.duration
        && replayVideo.currentTime >= replayVideo.duration - 0.05
      ) {
        loadReplaySegment(0, true);
        return;
      }
      if (replayVideo.paused) {
        void replayVideo.play();
      } else {
        replayVideo.pause();
      }
    });
    document.getElementById("replay-restart").addEventListener("click", () => {
      replayVideo.pause();
      loadReplaySegment(0);
    });
    replayVideo.addEventListener("timeupdate", updateReplayStatistics);
    replayVideo.addEventListener("play", () => {
      document.getElementById("replay-play").textContent = "Pause sequence";
    });
    replayVideo.addEventListener("pause", () => {
      document.getElementById("replay-play").textContent = "Play sequence";
    });
    replayVideo.addEventListener("ended", () => {
      const run = currentReplayRun();
      if (!run || replaySegmentIndex >= run.segments.length - 1) {
        updateReplayStatistics();
        return;
      }
      loadReplaySegment(replaySegmentIndex + 1, true);
    });

    async function submitEventMessage(textareaId, statusId, buttonId) {
      const textarea = document.getElementById(textareaId);
      const text = textarea.value.trim();
      if (!text) return;
      const send = document.getElementById(buttonId);
      const composerStatus = document.getElementById(statusId);
      if (currentDraft()?.decision?.status === "accepted") {
        composerStatus.textContent =
          "This event is accepted. Use Request Adjustment to submit the correction.";
        return;
      }
      send.disabled = true;
      composerStatus.textContent = "Sending to this Copilot session…";
      try {
        await sendReviewMessage(text);
        textarea.value = "";
        composerStatus.textContent = "Sent. Copilot will reply in this conversation.";
      } catch (error) {
        composerStatus.textContent = error.message;
      } finally {
        send.disabled =
          Boolean(currentDraft()?.decision)
          || state.activity?.state === "working";
      }
    }

    document.getElementById("composer").addEventListener("submit", async event => {
      event.preventDefault();
      await submitEventMessage("message", "composer-status", "send-message");
    });
    document.getElementById("fullscreen-chat-composer").addEventListener(
      "submit",
      async event => {
        event.preventDefault();
        if (selectedEngineIndex !== null) {
          await submitEngineConversationMessage();
        } else {
          await submitEventMessage(
            "fullscreen-message",
            "fullscreen-chat-status",
            "fullscreen-send-message"
          );
        }
      }
    );
    const events = new EventSource("/events");
    events.addEventListener("state", loadState);
    events.addEventListener("conversation", loadState);
    events.addEventListener("activity", loadState);
    window.setInterval(() => {
      if (document.visibilityState === "visible") {
        loadState().catch(() => {});
      }
    }, 2000);
    window.addEventListener("focus", () => {
      loadState().catch(() => {});
    });
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        loadState().catch(() => {});
      }
    });
    loadState().then(async () => {
      await loadGeometry();
    }).catch(error => {
      document.getElementById("decision-status").textContent = error.message;
    });
  </script>
</body>
</html>`;
}
