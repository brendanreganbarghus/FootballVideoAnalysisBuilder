export function renderHtml() {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0d1117">
  <title>Football Event Review</title>
  <style>
    :root { color-scheme: dark; }
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
    h1, h2, h3 { margin: 0; text-wrap: balance; }
    h1 { font-size: var(--text-title-medium, 20px); }
    h2 { font-size: var(--text-title-small, 16px); }
    h3 { font-size: var(--text-body-medium, 14px); }
    p { text-wrap: pretty; }
    .muted { color: var(--text-color-muted, #8b949e); }
    .scope {
      padding: 5px 9px;
      border: 1px solid var(--true-color-green, #3fb950);
      border-radius: 999px;
      color: var(--true-color-green, #7ee787);
      font-size: 12px;
      font-weight: var(--font-weight-semibold, 600);
      white-space: nowrap;
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
      background: var(--true-color-yellow, #d29922);
      animation: pulse 1.2s ease-in-out infinite;
    }
    .activity.error .activity-dot {
      background: var(--true-color-red, #ff7b72);
    }
    .activity strong { margin-right: 4px; }
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
    .segment-picker {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
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
    }
    .segment-status.in_review {
      border-color: var(--true-color-blue, #1f6feb);
      color: var(--true-color-blue, #79c0ff);
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
      grid-template-columns: auto minmax(120px, 1fr) auto auto;
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
    .missing-event {
      padding: 12px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 12px;
      background: var(--background-color-subtle, #161b22);
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
    .missing-event-fields {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto;
      gap: 8px;
      align-items: end;
      margin-top: 12px;
    }
    .clip-question-actions {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .clip-question-actions button { min-width: 190px; }
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
      left: 14px;
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
    .event-trigger[hidden] { display: none; }
    .event-trigger.active { animation: event-ping 1.6s ease-out; }
    .event-trigger-dot {
      width: 10px;
      height: 10px;
      flex: 0 0 auto;
      border-radius: 50%;
      background: #3fb950;
      box-shadow: 0 0 0 5px rgb(63 185 80 / 22%);
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
      max-height: min(62vh, 560px);
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
      display: grid;
      grid-template-columns: minmax(0, 1fr) 112px minmax(0, 1fr);
      gap: 8px;
      padding: 7px 10px;
      border-bottom: 1px solid rgb(240 246 252 / 16%);
      color: #c9d1d9;
      font-size: 11px;
      line-height: 1.4;
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
      overflow-y: auto;
      padding: 6px;
    }
    .comparison-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 112px minmax(0, 1fr);
      gap: 8px;
      align-items: stretch;
      min-height: 42px;
      border-bottom: 1px solid rgb(240 246 252 / 10%);
    }
    .comparison-row.has-review-actions { min-height: 48px; }
    .comparison-row:last-child { border-bottom: 0; }
    .comparison-row.matched { background: rgb(35 134 54 / 10%); }
    .comparison-row.reviewed { background: rgb(31 111 235 / 16%); }
    .comparison-row.stoppage { background: rgb(210 153 34 / 16%); }
    .comparison-row.off { background: rgb(248 81 73 / 15%); }
    .comparison-row.decision-rejected {
      background: rgb(110 118 129 / 18%);
      opacity: .78;
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
      min-height: 36px;
      margin: 3px 0;
      padding: 6px 8px;
      border-color: transparent;
      background: transparent;
      color: #c9d1d9;
      text-align: left;
    }
    .comparison-review-cell {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 6px;
      align-items: center;
      min-width: 0;
    }
    .comparison-review-cell .comparison-event { min-width: 0; }
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
      grid-template-columns: repeat(2, 34px);
      align-self: center;
      min-width: 0;
      gap: 6px;
      padding: 4px;
      border: 1px solid rgb(240 246 252 / 12%);
      border-radius: 7px;
      background: rgb(13 17 23 / 46%);
    }
    .comparison-action.icon-action {
      display: grid;
      width: 34px;
      min-height: 34px;
      padding: 0;
      place-items: center;
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
      padding: 4px 7px;
      color: #ffb3ad;
      font-size: 10px;
      font-weight: var(--font-weight-semibold, 600);
      white-space: nowrap;
    }
    .comparison-reviewed {
      padding: 4px 7px;
      color: #79c0ff;
      font-size: 10px;
      font-weight: var(--font-weight-semibold, 600);
      white-space: nowrap;
    }
    .comparison-engine-cell {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 6px;
      align-items: center;
      min-width: 0;
    }
    .comparison-engine-cell .comparison-event { min-width: 0; }
    .comparison-accepted {
      padding: 4px 7px;
      color: #aff5b4;
      font-size: 10px;
      white-space: nowrap;
    }
    .comparison-verifying {
      padding: 4px 7px;
      color: #f2cc60;
      font-size: 10px;
      white-space: nowrap;
    }
    .comparison-event.engine { text-align: right; }
    .comparison-event.engine .comparison-number { order: 2; }
    .comparison-event:hover,
    .comparison-event:focus-visible {
      border-color: #58a6ff;
      background: rgb(31 111 235 / 24%);
    }
    .comparison-event.current {
      border-color: #3fb950;
      background: rgb(35 134 54 / 28%);
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
    .comparison-event.reached:not(.current) { color: #aff5b4; }
    .comparison-number {
      color: #79c0ff;
      font-family: var(--font-mono, Consolas, monospace);
      font-size: 11px;
    }
    .comparison-label {
      overflow: hidden;
      text-overflow: ellipsis;
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
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Football Event Review</h1>
      <div class="muted">Prepared segment → reference review → engine check</div>
    </div>
    <span class="scope">30–60 second segments</span>
  </header>
  <p class="activity ready" id="activity" aria-live="polite">
    <span class="activity-dot" aria-hidden="true"></span>
    <span><strong id="activity-label">Ready for your review</strong>
      <span class="muted" id="activity-detail"></span></span>
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
              <input id="segment-duration" name="segment-duration"
                type="number" min="30" max="60" step="1" value="60"
                inputmode="numeric" autocomplete="off">
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
      <div class="segment-picker">
        <label for="segment-select">Prepared segment
          <select id="segment-select" autocomplete="off"></select>
        </label>
        <span class="segment-status" id="segment-status">Loading</span>
      </div>
      <div class="review-workspace">
        <div class="media-column">
          <div class="video-shell" id="video-shell">
        <div class="video-media" id="video-media">
          <video id="video" controls preload="metadata"
            aria-label="Selected Alfheim stream segment footage"></video>
          <svg class="ball-overlay" id="ball-overlay" hidden
            preserveAspectRatio="xMidYMid meet" aria-hidden="true">
            <circle class="ball-marker" id="ball-marker" r="30"></circle>
            <path class="ball-crosshair" id="ball-crosshair"></path>
          </svg>
          <div class="event-trigger" id="event-trigger" hidden
            role="status" aria-live="polite">
            <span class="event-trigger-dot" aria-hidden="true"></span>
            <strong id="event-trigger-label">Event detected</strong>
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
          <aside class="fullscreen-events" aria-label="Segment events">
            <div class="fullscreen-events-head">
              <span>Copilot proposal</span>
              <span>Seconds</span>
              <span>Rules engine output</span>
            </div>
            <div class="comparison-summary" id="comparison-summary"
              aria-live="polite"></div>
            <div class="comparison-guide" aria-label="Comparison guidance">
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
            <div class="fullscreen-event-items" id="fullscreen-event-items"></div>
          </aside>
          <nav class="compact-engine-rail" id="compact-engine-rail"
            aria-label="Rules engine event positions"></nav>
        </div>
        <div class="view-modes" role="group" aria-label="Video view">
          <button type="button" data-view-mode="normal"
            aria-pressed="true">Normal</button>
          <button type="button" data-view-mode="ball"
            aria-pressed="false">Labelled ball</button>
          <button type="button" data-view-mode="ai"
            aria-pressed="false">AI tracking</button>
          <span class="muted view-note" id="view-note">
            Original video without overlays
          </span>
        </div>
        <div class="transport">
          <button id="previous-frame" type="button">← Frame</button>
          <label>Review Position
            <input id="timeline" name="timeline" type="range"
              min="0" max="60" step="0.04" value="0" autocomplete="off">
          </label>
          <output class="time" id="time" aria-live="polite">0.00s</output>
          <button id="zoom-action" type="button">Zoom to Action</button>
          <button id="enlarge" type="button">Enlarge Review</button>
        </div>
          </div>

          <section class="missing-event conversation" id="clip-conversation-panel"
            aria-labelledby="clip-conversation-title">
            <div class="clip-conversation-head">
              <div>
                <h2 id="clip-conversation-title">Ask Copilot about this clip</h2>
                <p class="muted">
                  General clip messages stay separate from every event conversation.
                </p>
              </div>
              <span class="chat-status" id="clip-chat-status" data-state="ready">
                Ready
              </span>
            </div>
            <ol class="messages" id="clip-messages" aria-live="polite">
              <li class="message system">No general clip messages yet.</li>
            </ol>
            <form class="missing-event-fields" id="clip-composer">
              <label class="missing-event-note" for="clip-message">
                Ask about any event, the current frame, or the overall clip
                <textarea id="clip-message" name="clip-message" maxlength="1000"
                  autocomplete="off"
                  placeholder="Example: Did the engine miss an event here?"></textarea>
              </label>
              <label class="clip-scope-field" for="clip-message-scope">
                Evidence scope
                <select id="clip-message-scope" name="clip-message-scope">
                  <option value="entire_clip" selected>Entire clip</option>
                  <option value="current_time">Current time ±2s</option>
                </select>
              </label>
              <div class="clip-question-actions">
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

        <aside class="event-rail" aria-label="Current event review">
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
          <button class="reject" id="reject" type="button">Reject Event</button>
        </div>
        <ol class="review-flow">
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
        <section class="conversation" id="conversation-panel"
          aria-labelledby="conversation-title">
          <div class="conversation-head">
            <div class="conversation-title-block">
              <h2 id="conversation-title">Copilot for Event 1</h2>
              <p class="muted">
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

      <section class="match-replay" aria-labelledby="match-replay-title">
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
    let state = null;
    let selectedIndex = 0;
    let actionZoom = false;
    let statusTimer = null;
    let renderedSegmentKey = null;
    let viewMode = "normal";
    let ballTrack = null;
    let ballTrackSegmentKey = null;
    let pendingReviewSeconds = null;
    let pendingMissingReport = null;
    let segmentBuilderInitialized = false;
    let previousPlaybackSeconds = 0;
    let eventTriggerTimer = null;
    let playbackFrameRequest = null;
    let replayRunId = null;
    let replaySegmentIndex = 0;
    const video = document.getElementById("video");
    const timeline = document.getElementById("timeline");
    const videoShell = document.getElementById("video-shell");
    const videoMedia = document.getElementById("video-media");
    const segmentBuilderPanel =
      document.getElementById("segment-builder-panel");
    const ballOverlay = document.getElementById("ball-overlay");
    const ballMarker = document.getElementById("ball-marker");
    const ballCrosshair = document.getElementById("ball-crosshair");
    const segmentSelect = document.getElementById("segment-select");
    const startMinute = document.getElementById("segment-start-minute");
    const startSecond = document.getElementById("segment-start-second");
    const segmentDuration = document.getElementById("segment-duration");
    const prepareButton = document.getElementById("prepare-segment");
    const processButton = document.getElementById("process-segment");
    const segmentProgress = document.getElementById("segment-progress");
    const segmentRunStatus = document.getElementById("segment-run-status");
    const replayRunSelect = document.getElementById("replay-run");
    const replayVideo = document.getElementById("replay-video");

    function selectedSegmentKey() {
      return state?.segment?.key ||
        new URLSearchParams(location.search).get("segment") ||
        "segment-0300-020";
    }

    function statusLabel(status) {
      return {
        passed: "Passed",
        in_review: "In review",
        ai_ready: "AI ready",
        prepared: "Prepared",
        processing: "AI processing",
        detections_ready: "Detections ready",
        building: "Building events",
        failed: "AI failed"
      }[status] || status.replaceAll("_", " ");
    }

    function syncStartInputs(segment) {
      const seconds = Number(segment.startSeconds);
      startMinute.value = String(Math.floor(seconds / 60));
      startSecond.value = String(Math.floor(seconds % 60));
      segmentDuration.value = String(segment.durationSeconds);
    }

    function scheduleStatusRefresh() {
      clearTimeout(statusTimer);
      const running = ["processing", "detections_ready", "building"]
        .includes(state.segment.state);
      if (!running) return;
      statusTimer = setTimeout(() => {
        loadState().catch(error => {
          segmentRunStatus.textContent =
            "AI status unavailable: " + error.message;
        });
      }, 2000);
    }

    function renderRunControls() {
      const segment = state.segment;
      const running = ["processing", "detections_ready", "building"]
        .includes(segment.state);
      const generated = segment.key.startsWith("segment-");
      if (!segmentBuilderInitialized) {
        segmentBuilderPanel.open =
          segment.state !== "ready" && segment.validationStatus !== "passed";
        segmentBuilderInitialized = true;
      }
      prepareButton.disabled = running;
      processButton.disabled = running || !generated;
      processButton.textContent = segment.state === "ready"
        ? "Rerun AI logic"
        : segment.state === "failed" ? "Retry AI" : "Start AI";
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
        segmentRunStatus.textContent = state.drafts.length
          ? state.drafts.length + " AI event candidate(s) ready for review."
          : "AI completed and produced no event candidates.";
      } else if (segment.state === "processing") {
        segmentRunStatus.textContent = segment.expectedFrames
          ? "AI processing locally: " + segment.processedFrames + "/" +
            segment.expectedFrames + " sampled frames. Events stay hidden."
          : "AI processing locally. Events stay hidden until completion.";
      } else if (segment.state === "detections_ready") {
        segmentRunStatus.textContent =
          "Detections are complete; tracks and events still need building.";
      } else if (segment.state === "building") {
        segmentRunStatus.textContent =
          segment.statusMessage || "Building tracks and event candidates.";
      } else if (segment.state === "failed") {
        segmentRunStatus.textContent =
          "AI failed: " + (segment.statusMessage || "See analysis.log.");
      } else if (!generated) {
        segmentRunStatus.textContent =
          "This baseline is review-only; select or prepare a generated segment.";
      } else {
        segmentRunStatus.textContent =
          "Segment prepared. AI has not started; click Start AI when ready.";
      }
      scheduleStatusRefresh();
    }

    function renderSegments() {
      const selected = state.segment;
      const selectionChanged = renderedSegmentKey !== selected.key;
      const existing = new Map(
        Array.from(segmentSelect.options).map(option => [option.value, option])
      );
      const options = state.segments.map(segment => {
        const option = existing.get(segment.key) ||
          document.createElement("option");
        const labels = [
          segment.timeLabel,
          statusLabel(segment.validationStatus),
          segment.protected ? "Protected" : ""
        ].filter(Boolean);
        option.value = segment.key;
        option.textContent = labels.join(" · ");
        return option;
      });
      segmentSelect.replaceChildren(...options);
      segmentSelect.value = selected.key;
      if (selectionChanged) syncStartInputs(selected);
      renderedSegmentKey = selected.key;
      const badge = document.getElementById("segment-status");
      badge.className = "segment-status " + selected.validationStatus;
      badge.textContent = statusLabel(selected.validationStatus);
      if (viewMode === "ai" && !selected.trackingUrl) viewMode = "normal";
      const selectedVideoUrl = viewMode === "ai"
        ? selected.trackingUrl
        : selected.videoUrl;
      if (selectedVideoUrl && video.src !== selectedVideoUrl) {
        replaceVideoSource(selectedVideoUrl);
      }
      video.setAttribute(
        "aria-label",
        "Alfheim " + selected.timeLabel + " " +
        (viewMode === "ai" ? "AI tracking" : "footage")
      );
      timeline.max = String(selected.durationSeconds);
      renderViewMode();
      renderClipConversationControls();
      renderRunControls();
    }

    function renderClipConversationControls() {
      const reviewBusy = state.activity?.state === "working";
      document.getElementById("send-clip-plan").disabled = reviewBusy;
      document.getElementById("send-clip-autopilot").disabled = reviewBusy;
      const candidate = state.pendingMissingCandidate;
      const plan = document.getElementById("missing-event-plan");
      const confirm = document.getElementById("confirm-missing-event");
      plan.hidden = !candidate || candidate.supported === null;
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
          || state.segment.validationStatus === "passed"
          || Boolean(candidate.autopilotAuthorizedAt);
      }
      if (state.segment.validationStatus === "passed" && candidate?.supported) {
        document.getElementById("missing-event-status").textContent =
          "This passed reference is locked; reopen it before adding a proposal.";
      }
    }

    function replaceVideoSource(source) {
      const position = pendingReviewSeconds ?? video.currentTime ?? 0;
      const wasPlaying = !video.paused;
      video.src = source;
      video.addEventListener("loadedmetadata", () => {
        const target = pendingReviewSeconds ?? position;
        video.currentTime = Math.min(target, video.duration || target);
        pendingReviewSeconds = null;
        if (wasPlaying) void video.play();
        updateBallMarker();
      }, {once: true});
    }

    function nearestBallPoint(seconds) {
      const points = ballTrack?.points || [];
      if (!points.length) return null;
      const expected = Math.max(
        0,
        Math.min(points.length - 1, Math.round(seconds * 25))
      );
      let closest = points[expected];
      if (!closest) {
        closest = points.reduce((best, point) =>
          Math.abs(point[1] - seconds) < Math.abs(best[1] - seconds)
            ? point : best
        );
      }
      return Math.abs(closest[1] - seconds) <= 0.08 ? closest : null;
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
      const [, , x, y] = point;
      ballOverlay.removeAttribute("hidden");
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
          (mode === "ball" && !selected.labelsAvailable)
          || (mode === "ai" && !selected.trackingUrl);
      });
      ballOverlay.setAttribute(
        "viewBox",
        "0 0 " + (ballTrack?.width || 4450) +
        " " + (ballTrack?.height || 2000)
      );
      document.getElementById("view-note").textContent = {
        normal: "Original video without overlays",
        ball: "Supplied labelled ball position at this frame",
        ai: "Cached AI player, team, and ball tracking"
      }[viewMode];
      updateBallMarker();
    }

    function setViewMode(mode) {
      if (!["normal", "ball", "ai"].includes(mode)) return;
      if (mode === "ball" && !state.segment.labelsAvailable) return;
      if (mode === "ai" && !state.segment.trackingUrl) return;
      viewMode = mode;
      const source = mode === "ai"
        ? state.segment.trackingUrl
        : state.segment.videoUrl;
      if (source && video.src !== source) replaceVideoSource(source);
      video.setAttribute(
        "aria-label",
        "Alfheim " + state.segment.timeLabel + " " +
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

    function matchingReviewIndex(engineEvent, excluded = new Set()) {
      return (state?.drafts || [])
        .map((draft, index) => ({draft, index}))
        .filter(({draft, index}) =>
          !excluded.has(index)
          && draft.team === engineEvent.team
          && draft.type === engineEvent.type
          && Math.abs(draft.seconds - engineEvent.seconds) <= 1
        )
        .sort((left, right) =>
          Math.abs(left.draft.seconds - engineEvent.seconds)
          - Math.abs(right.draft.seconds - engineEvent.seconds)
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
      const rows = (state?.drafts || []).map((draft, reviewIndex) => {
        const match = engineEvents
          .map((engine, engineIndex) => ({engine, engineIndex}))
          .filter(({engine, engineIndex}) =>
            !usedEngine.has(engineIndex)
            && engine.team === draft.team
            && engine.type === draft.type
            && Math.abs(engine.seconds - draft.seconds) <= 1
          )
          .sort((left, right) =>
            Math.abs(left.engine.seconds - draft.seconds)
            - Math.abs(right.engine.seconds - draft.seconds)
          )[0];
        if (match) usedEngine.add(match.engineIndex);
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
      const description = side === "review"
        ? event.evidence
        : event.details;
      const canonicalLabel = canonicalComparisonLabel(event);
      button.title = [
        canonicalLabel,
        event.title && event.title !== canonicalLabel
          ? "Original description: " + event.title
          : "",
        description || ""
      ].filter(Boolean).join("\\n");
      button.setAttribute(
        "aria-label",
        "Seek to " + (side === "review" ? "Copilot proposal " : "engine event ")
          + eventNumber + " at " + event.seconds.toFixed(3)
          + " seconds: " + canonicalLabel
      );
      const number = document.createElement("span");
      number.className = "comparison-number";
      number.textContent = side === "review"
        ? "C" + eventNumber
        : "E" + eventNumber;
      const label = document.createElement("span");
      label.className = "comparison-label";
      label.textContent = canonicalLabel;
      button.append(number, label);
      button.addEventListener("click", () => {
        if (reviewIndex >= 0) {
          selectEvent(reviewIndex);
        } else {
          seekVideo(event.seconds);
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
        kind === "accept" ? "M3 8.5 6.5 12 13 4.5" : "M4 4l8 8M12 4l-8 8"
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
        progress.textContent = "Verifying C" + (row.reviewIndex + 1) + "…";
        cell.append(progress);
      } else if (row.review.decision?.status === "accepted") {
        const accepted = document.createElement("span");
        accepted.className = "comparison-accepted";
        accepted.textContent = "✓ Accepted";
        cell.append(accepted);
      } else if (row.review.decision?.status === "rejected") {
        const rejected = document.createElement("span");
        rejected.className = "comparison-rejected";
        rejected.textContent = "✕ Rejected";
        cell.append(rejected);
      } else if (state.segment.validationStatus !== "passed") {
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
      cell.append(
        comparisonButton(
          row.engine,
          "engine",
          row.engineIndex + 1,
          row.reviewIndex
        )
      );
      if (!row.review && row.engine.review?.fresh) {
        const reviewed = document.createElement("span");
        reviewed.className = "comparison-reviewed";
        reviewed.textContent = "✓ Confirmed reviewed";
        cell.append(reviewed);
      } else if (
        !row.review
        && state.segment.validationStatus !== "passed"
      ) {
        const confirm = document.createElement("button");
        confirm.type = "button";
        confirm.className = "comparison-action";
        confirm.textContent = "Verify E" + (row.engineIndex + 1) + " (Autopilot)";
        confirm.disabled = state.activity?.state === "working";
        confirm.addEventListener("click", async event => {
          event.stopPropagation();
          await requestEngineEventVerification(row.engineIndex);
        });
        cell.append(confirm);
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
        if (row.review?.decision?.status === "rejected") {
          item.classList.add("decision-rejected");
        }
        if (
          row.review
          && !row.review.decision?.status
          && state.segment.validationStatus !== "passed"
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
            else seekVideo(engine.seconds);
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
      if (draft.source === "user_reported") {
        return {label: "User-reported candidate", short: "User report", className: "user"};
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
      renderConversationMessages(
        "messages",
        (state.conversation || []).filter(
          message => message.eventIndex === selectedIndex
        ),
        "No messages yet for Event " + (selectedIndex + 1) + "."
      );
    }

    function renderClipMessages() {
      renderConversationMessages(
        "clip-messages",
        (state.conversation || []).filter(
          message => message.eventIndex === null
        ),
        "No general clip messages yet."
      );
    }

    function renderActivity() {
      const current = state.activity || {
        state: "ready",
        label: "Ready for your review",
        detail: ""
      };
      const target = document.getElementById("activity");
      target.className = "activity " + current.state;
      document.getElementById("activity-label").textContent = current.label;
      document.getElementById("activity-detail").textContent =
        current.detail ? " · " + current.detail : "";
      const chatStatus = document.getElementById("chat-status");
      const clipChatStatus = document.getElementById("clip-chat-status");
      const eventActive = current.state === "working"
        && state.activeConversation?.eventIndex === selectedIndex;
      const clipActive = current.state === "working"
        && state.activeConversation?.eventIndex === null;
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
          ? "Copilot is verifying C" + (selectedIndex + 1) + "…"
          : current.label + "…";
    }

    function render() {
      const draft = currentDraft();
      renderSegments();
      renderReplayCatalog();
      renderFullscreenEvents();
      const hasDraft = Boolean(draft);
      document.getElementById("event-nav").hidden = !hasDraft;
      document.getElementById("proposal").hidden = !hasDraft;
      document.getElementById("empty-review").hidden = hasDraft;
      document.getElementById("composer").hidden = !hasDraft;
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
        return;
      }
      const lockedReference =
        state.segment.validationStatus === "passed";
      const engineCandidate = draft.source === "engine_output";
      const adjustedProposal = draft.source === "adjusted_proposal";
      const userReported = draft.source === "user_reported";
      document.getElementById("event-number").textContent =
        "Event " + (selectedIndex + 1) + " of " + state.drafts.length;
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
        "Copilot for Event " + (selectedIndex + 1);
      document.getElementById("previous-event").disabled = selectedIndex === 0;
      document.getElementById("next-event").disabled =
        selectedIndex === state.drafts.length - 1;
      applyActionZoom();
      document.querySelector(".decisions").hidden = lockedReference;

      const decision = draft.decision;
      const accepted = decision?.status === "accepted";
      const rejected = decision?.status === "rejected";
      const finalized = accepted || rejected;
      const reviewBusy = state.activity?.state === "working";
      const remainingCount = state.drafts.filter(
        candidate => !candidate.decision
      ).length;
      const acceptAll = document.getElementById("accept-all-events");
      acceptAll.hidden = lockedReference;
      acceptAll.disabled = reviewBusy || remainingCount === 0;
      acceptAll.textContent = remainingCount
        ? "Verify & Accept All " + remainingCount + " Remaining Events (Autopilot)"
        : "All Events Accepted";
      document.getElementById("proposal").classList.toggle("accepted", accepted);
      document.getElementById("proposal").classList.toggle("rejected", rejected);
      document.getElementById("accept").hidden = finalized;
      document.getElementById("copilot-accept").hidden = finalized;
      document.getElementById("reject").hidden = finalized;
      document.getElementById("accept").disabled = reviewBusy;
      document.getElementById("adjust").disabled = reviewBusy;
      document.getElementById("reject").disabled = reviewBusy;
      document.getElementById("copilot-accept").disabled =
        finalized || reviewBusy;
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
    }

    async function loadState() {
      const url = stateUrl + "?segment=" +
        encodeURIComponent(selectedSegmentKey());
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) throw new Error("State HTTP " + response.status);
      state = await response.json();
      if (ballTrackSegmentKey !== state.segment.key) {
        const ballResponse = await fetch(
          "/api/ball-track?segment=" +
          encodeURIComponent(state.segment.key),
          {cache: "no-store"}
        );
        ballTrack = ballResponse.ok ? await ballResponse.json() : null;
        ballTrackSegmentKey = state.segment.key;
      }
      selectedIndex = Math.max(
        0,
        Math.min(selectedIndex, state.drafts.length - 1)
      );
      if (pendingMissingReport && state.drafts.length > pendingMissingReport.count) {
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
    }

    async function sendClipMessage(mode = "plan") {
      const noteInput = document.getElementById("clip-message");
      const status = document.getElementById("missing-event-status");
      const text = noteInput.value.trim();
      if (!text) {
        status.textContent = "Enter a question or observation about this clip.";
        noteInput.focus();
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
            scope
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
      const scope = document.getElementById("clip-message-scope").value;
      const seconds = Math.min(60, Math.max(0, video.currentTime || 0));
      const label = scope === "current_time"
        ? seconds.toFixed(2) + "s ±2s"
        : "entire clip";
      document.querySelectorAll(".clip-message-target").forEach(element => {
        element.textContent = label;
      });
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

    async function requestEngineEventVerification(engineIndex) {
      const response = await fetch("/api/copilot-verify-engine", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          segment: selectedSegmentKey(),
          index: engineIndex
        })
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || "Could not start engine-event verification");
      }
      await loadState();
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
      button.disabled = true;
      status.textContent =
        "Copilot is verifying C" + (targetIndex + 1)
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
        await loadState();
      } catch (error) {
        status.textContent = error.message;
        button.disabled = false;
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

    async function requestAdjustment() {
      const textarea = document.getElementById("message");
      const note = textarea.value.trim();
      const composerStatus = document.getElementById("composer-status");
      if (!note) {
        composerStatus.textContent =
          "Describe what is inaccurate in the message box first.";
        textarea.focus();
        return;
      }
      const button = document.getElementById("adjust");
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
        textarea.value = "";
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

    function selectEvent(index, options = {}) {
      if (!state.drafts.length) return;
      const seek = options.seek !== false;
      const pause = options.pause !== false;
      selectedIndex = Math.max(0, Math.min(state.drafts.length - 1, index));
      if (pause) video.pause();
      if (seek) {
        seekVideo(currentDraft().seconds);
      }
      document.getElementById("message").value = "";
      document.getElementById("composer-status").textContent = "";
      render();
    }

    function showEventTrigger(index) {
      const draft = state.drafts[index];
      if (!draft) return;
      const trigger = document.getElementById("event-trigger");
      document.getElementById("event-trigger-label").textContent =
        playbackEventLabel(draft);
      trigger.hidden = false;
      trigger.classList.remove("active");
      void trigger.offsetWidth;
      trigger.classList.add("active");
      clearTimeout(eventTriggerTimer);
      eventTriggerTimer = setTimeout(() => {
        trigger.hidden = true;
        trigger.classList.remove("active");
      }, 1600);
    }

    function followPlaybackEvents() {
      const seconds = Math.min(60, Math.max(0, video.currentTime || 0));
      updateLiveStatistics(seconds);
      if (seconds < previousPlaybackSeconds - 0.08) {
        previousPlaybackSeconds = seconds;
      }
      const crossed = state?.drafts
        ?.map((draft, index) => ({draft, index}))
        .filter(({draft}) =>
          draft.seconds > previousPlaybackSeconds
          && draft.seconds <= seconds + 0.02
        );
      for (const event of crossed || []) {
        selectEvent(event.index, {seek: false, pause: false});
        showEventTrigger(event.index);
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
      history.replaceState(null, "", "?segment=" + encodeURIComponent(segment));
      state = null;
      video.pause();
      await loadState();
      if (state.drafts.length) selectEvent(0);
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
      if (!Number.isInteger(duration) || duration < 30 || duration > 60) {
        segmentRunStatus.textContent =
          "Choose a review duration from 30 to 60 seconds.";
        return;
      }
      prepareButton.disabled = true;
      processButton.disabled = true;
      segmentProgress.hidden = false;
      segmentProgress.removeAttribute("value");
      segmentRunStatus.textContent =
        "Preparing only this " + duration +
        "-second video window. AI is not running.";
      try {
        const response = await fetch("/api/prepare", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            start_seconds: minute * 60 + second,
            duration_seconds: duration
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
        if (state.drafts.length) selectEvent(0);
      } catch (error) {
        segmentRunStatus.textContent =
          "Could not prepare segment: " + error.message;
      } finally {
        prepareButton.disabled = false;
      }
    });
    processButton.addEventListener("click", async () => {
      const segment = selectedSegmentKey();
      processButton.disabled = true;
      segmentProgress.hidden = false;
      segmentProgress.removeAttribute("value");
      segmentRunStatus.textContent =
        state.segment.state === "ready"
          ? "Rerunning event logic from cached analysis…"
          : "Starting local AI. Events stay hidden until it finishes.";
      try {
        const response = await fetch("/api/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ segment })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not start AI");
        }
        await loadState();
      } catch (error) {
        segmentRunStatus.textContent =
          "Could not start AI: " + error.message;
        processButton.disabled = false;
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
    document.getElementById("accept-all-events").addEventListener(
      "click", requestCopilotAcceptanceAll
    );
    document.getElementById("adjust").addEventListener(
      "click", requestAdjustment
    );
    document.getElementById("reject").addEventListener(
      "click", () => decide("rejected")
    );

    document.getElementById("previous-frame").addEventListener("click", () => {
      video.pause();
      video.currentTime = Math.max(0, video.currentTime - 1 / 25);
    });
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
    video.addEventListener("seeked", updateBallMarker);
    document.querySelectorAll("[data-view-mode]").forEach(button => {
      button.addEventListener("click", () => {
        setViewMode(button.dataset.viewMode);
      });
    });
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
    });

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

    document.getElementById("composer").addEventListener("submit", async event => {
      event.preventDefault();
      const textarea = document.getElementById("message");
      const text = textarea.value.trim();
      if (!text) return;
      const send = document.getElementById("send-message");
      const composerStatus = document.getElementById("composer-status");
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
          currentDraft()?.decision?.status === "accepted"
          || state.activity?.state === "working";
      }
    });
    const events = new EventSource("/events");
    events.addEventListener("state", loadState);
    events.addEventListener("conversation", loadState);
    events.addEventListener("activity", loadState);
    loadState().then(() => {
      if (state.drafts.length) selectEvent(0);
    }).catch(error => {
      document.getElementById("decision-status").textContent = error.message;
    });
  </script>
</body>
</html>`;
}
