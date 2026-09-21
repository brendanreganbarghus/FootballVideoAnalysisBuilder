export const INNOVATION_MARK_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" aria-hidden="true">
  <defs>
    <linearGradient id="review-brand-gradient" x1="64" y1="40" x2="448" y2="472" gradientUnits="userSpaceOnUse">
      <stop stop-color="#ba4ca6"/>
      <stop offset="1" stop-color="#59164f"/>
    </linearGradient>
  </defs>
  <rect x="36" y="36" width="440" height="440" rx="112" fill="url(#review-brand-gradient)"/>
  <rect x="92" y="92" width="328" height="328" rx="48" fill="#120d14" fill-opacity=".72" stroke="#e4a5da" stroke-width="10"/>
  <path d="M256 96v320M96 256h320" stroke="#e4a5da" stroke-width="8" opacity=".62"/>
  <circle cx="256" cy="256" r="74" fill="none" stroke="#e4a5da" stroke-width="8" opacity=".62"/>
  <path d="M104 326h72l30-68 50 112 44-144 36 100h72" fill="none" stroke="#68e0c1" stroke-width="22" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="256" cy="256" r="38" fill="#f8f5f8" stroke="#160f18" stroke-width="8"/>
  <path d="m256 235 18 13-7 21h-22l-7-21 18-13Zm-35 9 18 4m34 0 18-4m-61 43 15-18m22 0 15 18" fill="#6c1d5f" stroke="#6c1d5f" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;

const INNOVATION_XEBIA_SVG = `<svg viewBox="0 0 612 202.4" aria-hidden="true">
  <g fill="#6c1d5f">
    <path d="M296.5,92.8H239.4A28.91,28.91,0,0,1,267,71.4c15.4,0,25.6,7.6,29.5,21.4m-57.4,19.6h83.8v-5.3c0-13.8-3.2-24.9-9.7-34.3-11.1-14.7-27.6-23.7-45.4-23.7-14.3,0-28.1,6.2-38.7,17.3-9.7,10.3-14.7,23.2-14.7,37.8A57,57,0,0,0,230,142.6c10.8,10.8,23.7,16.1,39.3,16.1,23.2,0,41.6-12.9,50.4-35.7H293.4c-5,8.5-14.3,12.9-24.9,12.9-17.1.6-28.2-8.8-29.4-23.5"/>
    <path d="M360.7,105.2c0-17.9,12.9-31.3,29.9-31.3S421,88.2,421,104.7c0,17.3-12.9,30.8-31.7,30.8-15.1.1-28.6-13.3-28.6-30.3m-.9-44.6V18.7h-24V157h24v-8.5a50.45,50.45,0,0,0,32.5,11.1,53.38,53.38,0,0,0,34.3-12,56,56,0,0,0,19.6-42.8c0-15.2-6.2-30.4-17.9-40.7-9.7-9.4-22.3-13.8-36.1-13.8-12.7-.3-23,2.7-32.4,10.3"/>
    <path d="M462.9,52.7h23.2V157H462.9Zm0-34h23.2V41.9H462.9Z"/>
    <path d="M526.8,103.4a29.6,29.6,0,0,1,29.9-29.9c15.2,0,29.4,13.4,29.4,31.3,0,16.1-13.8,29.9-29,29.9-16.5,0-30.3-12.9-30.3-31.3m62,53.6H612V52.7H588.8V65.2C581.7,54.9,570.9,50,555.7,50c-15.6,0-28.1,5-38.7,16.1-9.7,10.3-14.7,23.7-14.7,38.4,0,31.3,23.2,54.8,53.9,54.8,16.1,0,26.7-4.4,32.5-15.2l.1,12.9Z"/>
    <polygon points="0.9 202.4 64.5 202.4 133.3 133.8 201.9 202.4 266.3 202.4 165.5 101.6 267.2 0 202.8 0 133.3 69.6 64.2 0 0 0 101.1 101.6 0.9 202.4"/>
  </g>
</svg>`;

export function renderHtml({ adapter } = {}) {
  if (!adapter?.key) {
    throw new Error("A football review workflow adapter is required.");
  }
  const appTheme = adapter.theme;
  const themeColor = adapter.themeColor;
  const homeUrl = adapter.homeUrl;
  const homeLabel = adapter.homeLabel;
  const palette = adapter.palette;
  const innovationFavicon = adapter.key === "innovation"
    ? '<link rel="icon" type="image/svg+xml" sizes="any" href="/favicon.svg?v=pitch-pulse-1">'
    : "";
  return `<!doctype html>
<html lang="en" data-app-theme="${appTheme}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="${themeColor}">
  ${innovationFavicon}
  <title>${adapter.displayName}</title>
  <style>
    :root { color-scheme: dark; }
    html[data-app-theme="${appTheme}"] {
      --background-color-default: ${palette.backgroundDefault};
      --background-color-subtle: ${palette.backgroundSubtle};
      --background-color-muted: ${palette.backgroundMuted};
      --border-color-default: ${palette.borderDefault};
      --border-color-muted: ${palette.borderMuted};
      --panel-background: ${palette.panelBackground};
      --panel-border: ${palette.panelBorder};
      --nested-panel-background: ${palette.nestedPanelBackground};
      --nested-panel-border: ${palette.nestedPanelBorder};
      --text-color-default: ${palette.textDefault};
      --text-color-muted: ${palette.textMuted};
      --true-color-green: ${palette.green};
      --true-color-blue: ${palette.blue};
      ${adapter.key === "innovation"
        ? `--true-color-blue-muted: ${palette.blueMuted};
      --innovation-purple: #a63f98;
      --innovation-lilac: #e4a5da;`
        : ""}
      --color-focus-outline: ${palette.focus};
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
    html[data-app-theme="${appTheme}"] body {
      background: ${palette.bodyBackground};
    }
    .segment-loading-overlay {
      position: fixed;
      z-index: 10000;
      inset: 0;
      display: grid;
      place-items: center;
      padding: 24px;
      background: rgb(5 8 13 / 82%);
      backdrop-filter: blur(5px);
    }
    .segment-loading-card {
      display: grid;
      justify-items: center;
      gap: 12px;
      min-width: min(340px, 90vw);
      padding: 24px;
      border: 1px solid var(--true-color-blue, #78bfff);
      border-radius: 14px;
      background: var(--panel-background, #0b141f);
      box-shadow: 0 18px 60px rgb(0 0 0 / 55%);
      text-align: center;
    }
    .segment-loading-spinner {
      width: 42px;
      height: 42px;
      border: 4px solid rgb(120 191 255 / 24%);
      border-top-color: var(--true-color-blue, #78bfff);
      border-radius: 50%;
      animation: segment-loading-spin 800ms linear infinite;
    }
    .segment-loading-elapsed {
      padding: 3px 9px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 999px;
      font-family: var(--font-mono, Consolas, monospace);
      font-size: 12px;
    }
    #segment-loading-detail {
      white-space: pre-line;
      text-align: left;
    }
    #segment-loading-close,
    #segment-loading-cancel {
      margin-top: 4px;
    }
    .coordinate-round-result.processing::before {
      width: 16px;
      height: 16px;
      flex: 0 0 auto;
      border: 2px solid rgb(120 191 255 / 24%);
      border-top-color: var(--true-color-blue, #78bfff);
      border-radius: 50%;
      content: "";
      animation: segment-loading-spin 800ms linear infinite;
    }
    @keyframes segment-loading-spin {
      to { transform: rotate(360deg); }
    }
    html[data-app-theme="${appTheme}"] .innovation-brand {
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
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      padding: 14px 18px;
      border-bottom: 1px solid var(--border-color-default, #30363d);
    }
    .review-heading {
      display: flex;
      align-items: center;
      gap: 14px;
      min-width: 0;
    }
    .review-brand-lockup {
      display: flex;
      flex: none;
      align-items: center;
      gap: 8px;
      padding-right: 14px;
      border-right: 1px solid rgb(255 255 255 / 16%);
    }
    .review-brand-lockup > svg {
      display: block;
      width: 42px;
      height: 42px;
    }
    .review-brand-xebia {
      display: grid;
      width: 88px;
      height: 38px;
      padding: 7px 9px;
      place-items: center;
      border-radius: 7px;
      background: #fff;
    }
    .review-brand-xebia svg {
      display: block;
      width: 100%;
      height: auto;
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
    .engine-user-claim legend {
      padding: 0 5px;
      color: #f0f6fc;
    }
    .engine-user-claim label {
      display: inline-flex;
      gap: 5px;
      align-items: center;
      cursor: pointer;
    }
    .engine-verification-modal {
      width: min(720px, calc(100vw - 48px));
      max-width: none;
      max-height: calc(100dvh - 48px);
      padding: 0;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 12px;
      background: var(--background-color-subtle, #161b22);
      color: var(--text-color-default, #f0f6fc);
      overflow: auto;
      overscroll-behavior: contain;
    }
    .engine-verification-modal::backdrop {
      background: rgb(0 0 0 / 72%);
    }
    .engine-verification-modal form {
      display: grid;
      gap: 14px;
      margin: 0;
      padding: 20px;
    }
    .engine-verification-modal[data-review-state="working"]
      .engine-verification-cost-note {
      border-left-color: #d29922;
      background: rgb(210 153 34 / 12%);
      color: #f2cc60;
    }
    .engine-verification-modal[data-review-state="working"]
      .engine-verification-cost-note::before {
      display: inline-block;
      width: 10px;
      height: 10px;
      margin-right: 7px;
      border: 2px solid currentColor;
      border-right-color: transparent;
      border-radius: 50%;
      content: "";
      animation: spin .8s linear infinite;
      vertical-align: -1px;
    }
    .engine-verification-modal[data-review-state="working"]
      #ask-copilot-manual-engine-review {
      border-color: #d29922;
      background: rgb(210 153 34 / 12%);
      color: #f2cc60;
    }
    .engine-verification-modal header {
      display: grid;
      gap: 5px;
      padding: 0;
      border: 0;
    }
    .engine-verification-modal fieldset {
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      border: 0;
    }
    .engine-verification-modal legend {
      margin-bottom: 8px;
      padding: 0;
      color: var(--text-color-default, #f0f6fc);
      font-weight: var(--font-weight-semibold, 600);
    }
    .engine-verification-choice {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 3px 10px;
      align-items: start;
      padding: 11px 12px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 9px;
      cursor: pointer;
    }
    .engine-verification-choice:has(input:checked) {
      border-color: var(--true-color-blue, #58a6ff);
      background: rgb(31 111 235 / 16%);
    }
    .engine-verification-choice input {
      grid-row: 1 / 3;
      margin-top: 3px;
    }
    .engine-verification-choice strong {
      color: var(--text-color-default, #f0f6fc);
    }
    .engine-verification-choice span {
      color: var(--text-color-muted, #8b949e);
      line-height: 1.45;
    }
    .engine-verification-cost-note {
      margin: 0;
      padding: 10px 12px;
      border-left: 3px solid var(--true-color-blue, #58a6ff);
      background: rgb(31 111 235 / 10%);
      color: var(--text-color-muted, #8b949e);
    }
    .engine-verification-modal[data-review-state="working"]
      :is(#engine-verification-guidance, #manual-engine-review-guidance) {
      border-left-color: #f2cc60;
      background: rgb(187 128 9 / 18%);
      color: #f2cc60;
      font-weight: 800;
      box-shadow: 0 0 12px rgb(242 204 96 / 22%);
      animation: engine-verification-working-pulse 1.2s ease-in-out infinite;
    }
    @keyframes engine-verification-working-pulse {
      50% {
        color: #fff4ad;
        border-left-color: #fff4ad;
        box-shadow: 0 0 18px rgb(242 204 96 / 48%);
      }
    }
    .engine-verification-time {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 6px 10px;
      align-items: end;
    }
    .engine-verification-time label {
      display: grid;
      gap: 5px;
      color: var(--text-color-muted, #8b949e);
      font-weight: var(--font-weight-semibold, 600);
    }
    .engine-verification-time small {
      grid-column: 1 / -1;
      color: var(--text-color-muted, #8b949e);
    }
    .similar-review-group {
      display: grid;
      gap: 8px;
      margin: 12px 0;
    }
    .similar-review-group[hidden] {
      display: none;
    }
    .similar-review-list {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 6px;
    }
    .similar-review-item {
      display: flex;
      gap: 8px;
      align-items: flex-start;
      padding: 8px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 6px;
      background: color-mix(
        in srgb,
        var(--background-color-default, #0d1117) 90%,
        var(--true-color-blue, #58a6ff)
      );
    }
    .similar-review-item span {
      display: grid;
      gap: 2px;
    }
    .similar-review-item small {
      color: var(--text-color-muted, #8b949e);
    }
    .engine-verification-actions {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
    }
    .manual-ledger-audit-summary {
      margin: 0;
      padding: 10px 12px;
      border-left: 3px solid var(--true-color-blue, #58a6ff);
      background: rgb(31 111 235 / 10%);
    }
    .manual-ledger-audit-list {
      display: grid;
      gap: 10px;
    }
    .manual-ledger-audit-finding {
      display: grid;
      gap: 8px;
      padding: 12px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 9px;
      background: var(--background-color-default, #0d1117);
    }
    .manual-ledger-audit-finding.acknowledged {
      border-color: var(--true-color-green, #2ea043);
      opacity: .78;
    }
    .manual-ledger-audit-finding header {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 8px;
      padding: 0;
      border: 0;
    }
    .manual-ledger-audit-finding p {
      margin: 0;
      color: var(--text-color-muted, #8b949e);
    }
    .manual-ledger-audit-meta {
      font-family: var(--font-mono, Consolas, monospace);
      font-size: 12px;
    }
    .manual-ledger-audit-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .manual-ledger-audit-confirmed {
      color: var(--true-color-green, #7ee787);
      font-weight: 700;
    }
    #confirm-engine-without-copilot {
      border-color: var(--true-color-green, #2ea043);
      background: rgb(46 160 67 / 18%);
      color: var(--true-color-green, #7ee787);
    }
    #ask-copilot-engine-review {
      border-color: var(--true-color-blue, #58a6ff);
      background: rgb(31 111 235 / 18%);
      color: var(--true-color-blue, #79c0ff);
    }
    .copilot-decision-options {
      display: grid;
      gap: 10px;
    }
    .copilot-decision-option {
      display: grid;
      gap: 4px;
      width: 100%;
      min-height: 0;
      padding: 12px;
      text-align: left;
    }
    .copilot-decision-option span {
      color: var(--text-color-muted, #8b949e);
      line-height: 1.45;
    }
    #accept-copilot-decision {
      border-color: var(--true-color-green, #2ea043);
      background: rgb(46 160 67 / 18%);
    }
    #reject-copilot-decision {
      border-color: var(--true-color-red, #da3633);
      background: rgb(218 54 51 / 12%);
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
      display: flex;
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
    .segment-status.regression-failed {
      min-width: 180px;
      border-color: var(--true-color-red, #da3633);
      color: var(--true-color-red, #ff7b72);
      background: rgb(218 54 51 / 16%);
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
    .regression-batch-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-top: 12px;
    }
    .coordination-status {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      grid-column: 1 / -1;
      padding: 8px 10px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 8px;
      background: var(--background-color-subtle, #161b22);
    }
    .coordination-status.read-only {
      border-color: var(--true-color-yellow, #d29922);
    }
    .coordination-status.locked {
      border-color: var(--true-color-red, #da3633);
    }
    .coordination-status .coordination-detail {
      flex: 1 1 280px;
    }
    .copilot-session-status {
      border-color: var(--true-color-yellow, #d29922);
    }
    .copilot-session-status .coordination-detail {
      flex: 1 1 360px;
    }
    .regression-batch-actions .muted {
      margin-left: auto;
    }
    .regression-select {
      width: 18px;
      height: 18px;
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
    .shared-review-table tr.regression-diff {
      background: rgb(210 153 34 / 14%);
    }
    .shared-review-table tr.regression-diff td:first-child {
      box-shadow: inset 4px 0 0 var(--true-color-yellow, #d29922);
    }
    .regression-queue {
      margin-top: 12px;
      padding: 10px;
      border: 1px solid var(--true-color-red, #da3633);
      border-radius: 8px;
      background: var(--true-color-red-muted, rgb(218 54 51 / 12%));
    }
    .regression-queue ul {
      margin: 8px 0 0;
      padding-left: 20px;
    }
    .engine-output-notice {
      margin: 0 0 10px;
      padding: 8px 10px;
      border: 1px solid var(--true-color-yellow, #d29922);
      border-radius: 8px;
      background: rgb(210 153 34 / 14%);
      color: var(--true-color-yellow, #f2cc60);
      font-weight: var(--font-weight-semibold, 600);
    }
    .comparison-event.regression-added {
      border-color: var(--true-color-yellow, #d29922);
      box-shadow: inset 4px 0 0 var(--true-color-yellow, #d29922);
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
    }
    .video-zoom-layer {
      position: relative;
      width: 100%;
      transform: scale(1);
      transform-origin: 50% 50%;
      transition: transform 160ms ease-out;
    }
    .video-media.zoomed .video-zoom-layer {
      cursor: grab;
      touch-action: none;
    }
    .video-media.panning .video-zoom-layer {
      cursor: grabbing;
      transition: none;
    }
    .video-shell:fullscreen {
      display: grid;
      width: 100vw;
      height: 100vh;
      grid-template-rows: minmax(0, 1fr) auto auto;
      overflow: hidden;
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
    .ball-coordinate-label rect {
      fill: rgb(13 17 23 / 88%);
      stroke: var(--true-color-red, #ff3b30);
      stroke-width: 3;
      vector-effect: non-scaling-stroke;
    }
    .ball-coordinate-label text {
      fill: #fff;
      font-family: var(--font-mono, Consolas, monospace);
      font-size: 44px;
      font-weight: 700;
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
    .video-shell.action-zoom .video-zoom-layer { transform: scale(2.35); }
    .video-shell:fullscreen .video-media,
    .video-shell:fullscreen .video-zoom-layer,
    .video-shell:fullscreen video {
      min-height: 0;
      height: 100%;
      aspect-ratio: auto;
    }
    .video-shell:fullscreen .view-modes {
      min-width: 0;
      flex-wrap: nowrap;
      overflow-x: auto;
      overscroll-behavior: contain;
    }
    .video-shell:fullscreen > .transport {
      min-width: 0;
      max-height: min(30dvh, 220px);
      overflow-y: auto;
      overscroll-behavior: contain;
      scrollbar-gutter: stable;
      padding-bottom: max(10px, env(safe-area-inset-bottom));
    }
    .video-shell:fullscreen
      > .transport
      > .innovation-manual-controls {
      display: none;
    }
    .transport {
      position: relative;
      z-index: 2;
      display: grid;
      grid-template-columns:
        auto auto auto minmax(240px, 1fr) auto auto auto auto;
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
    .timeline-control {
      min-width: 0;
    }
    .timeline-control input {
      width: 100%;
      min-width: 120px;
    }
    .video-zoom-controls {
      display: inline-flex;
      gap: 4px;
      align-items: center;
    }
    .video-zoom-controls button {
      min-width: 34px;
      min-height: 34px;
      padding: 4px 9px;
      font-size: 18px;
      line-height: 1;
    }
    .video-zoom-controls output {
      min-width: 36px;
      color: var(--text-color-muted, #8b949e);
      font-size: 12px;
      text-align: center;
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
      width: 100%;
      max-height: 300px;
      overflow: auto;
      overscroll-behavior: contain;
      scrollbar-gutter: stable;
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
    @media (max-width: 700px) {
      .ball-frame-table {
        table-layout: fixed;
      }
      .ball-frame-table th,
      .ball-frame-table td {
        padding-inline: 4px;
      }
      .ball-frame-table th:nth-child(1) { width: 58px; }
      .ball-frame-table th:nth-child(2) { width: 52px; }
      .ball-frame-table th:nth-child(3),
      .ball-frame-table th:nth-child(4) { width: 58px; }
      .ball-frame-table th:nth-child(n + 6),
      .ball-frame-table td:nth-child(n + 6) {
        display: none;
      }
      .ball-frame-table .ball-frame-status {
        overflow-wrap: anywhere;
        white-space: normal;
      }
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
    .coordinate-review-result.undefined {
      border-color: var(--true-color-red, #da3633);
      color: var(--true-color-red, #ff7b72);
      background: rgb(218 54 51 / 12%);
    }
    .coordinate-review-result.pending {
      color: var(--text-color-muted, #8b949e);
    }
    .coordinate-gate-info-button {
      margin-left: 6px;
      min-height: 28px;
      padding: 3px 8px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 999px;
      color: var(--true-color-blue, #58a6ff);
      background: rgb(88 166 255 / 10%);
      font-size: 11px;
      font-weight: var(--font-weight-semibold, 600);
      white-space: nowrap;
    }
    .coordinate-gate-popover {
      position: fixed;
      inset: auto;
      max-width: min(520px, calc(100vw - 32px));
      margin: 0;
      padding: 12px;
      border: 1px solid var(--true-color-blue, #58a6ff);
      border-radius: 10px;
      background: var(--background-color-subtle, #161b22);
      color: var(--text-color-default, #c9d1d9);
      box-shadow: 0 16px 48px rgb(0 0 0 / 48%);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font: 12px/1.5 var(--font-mono, Consolas, monospace);
      overscroll-behavior: contain;
    }
    .coordinate-gate-popover::backdrop {
      background: rgb(0 0 0 / 24%);
    }
    .shared-review-table .regression-action {
      min-height: 30px;
      margin-top: 6px;
      padding: 4px 10px;
      border-color: var(--true-color-blue, #58a6ff);
      background: rgb(31 111 235 / 22%);
      color: var(--true-color-blue, #79c0ff);
      font-weight: var(--font-weight-semibold, 600);
      white-space: nowrap;
    }
    .shared-review-table .regression-action:hover {
      border-color: var(--true-color-blue, #79c0ff);
      background: rgb(31 111 235 / 34%);
    }
    .shared-review-table .segment-replay-action {
      min-height: 30px;
      margin-top: 6px;
      padding: 4px 10px;
      border-color: var(--true-color-green, #3fb950);
      background: rgb(46 160 67 / 18%);
      color: var(--true-color-green, #7ee787);
      font-weight: var(--font-weight-semibold, 600);
      white-space: nowrap;
    }
    .shared-review-table .segment-replay-action:hover {
      border-color: var(--true-color-green, #7ee787);
      background: rgb(46 160 67 / 30%);
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
    }
    .ball-coordinate-modal-frames .coordinate-review-result {
      min-height: 28px;
      box-sizing: border-box;
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
      flex-wrap: wrap;
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
    .ball-frame-modal-status .decision-detail {
      flex: 1 1 320px;
      color: var(--text-color-muted, #8b949e);
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
    .coordinate-undefined-action {
      color: #ff7b72;
      font-size: inherit;
      font-weight: var(--font-weight-semibold, 600);
    }
    .coordinate-decision-guide {
      margin: 10px 0;
      padding: 10px 12px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 8px;
      background: var(--background-color-muted, #161b22);
    }
    .coordinate-decision-guide strong {
      display: block;
      margin-bottom: 6px;
    }
    .coordinate-decision-guide ul {
      margin: 0;
      padding-left: 20px;
    }
    .coordinate-decision-guide li + li { margin-top: 4px; }
    .yolo-candidate-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 8px 0;
    }
    .yolo-candidate-actions button {
      border-color: #58a6ff;
      color: #79c0ff;
    }
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
    .ball-frame-modal-marker.engine-coordinate {
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
    .ball-frame-pointer {
      position: absolute;
      z-index: 4;
      inset: 0;
      pointer-events: none;
    }
    .ball-frame-pointer[hidden] { display: none; }
    .ball-frame-pointer::before,
    .ball-frame-pointer::after {
      content: "";
      position: absolute;
      background: rgb(255 255 255 / 82%);
      box-shadow: 0 0 1px #000;
    }
    .ball-frame-pointer::before {
      left: 0;
      right: 0;
      top: var(--pointer-y);
      height: 1px;
    }
    .ball-frame-pointer::after {
      top: 0;
      bottom: 0;
      left: var(--pointer-x);
      width: 1px;
    }
    .ball-frame-pointer-label {
      position: absolute;
      left: min(calc(var(--pointer-x) + 10px), calc(100% - 145px));
      top: max(calc(var(--pointer-y) - 30px), 8px);
      padding: 3px 6px;
      border-radius: 4px;
      background: rgb(13 17 23 / 88%);
      color: #f0f6fc;
      font-family: var(--font-mono, Consolas, monospace);
      font-size: 12px;
      white-space: nowrap;
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
    .innovation-manual-controls {
      display: flex;
      flex: 0 0 auto;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      padding: 8px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 10px;
      background: var(--background-color-subtle, #161b22);
    }
    .innovation-manual-controls button { min-height: 44px; }
    .manual-capture-label {
      flex-basis: 100%;
      color: var(--text-color-muted, #8b949e);
      font-size: 11px;
      font-weight: var(--font-weight-semibold, 600);
    }
    .manual-editor input,
    .manual-editor select {
      min-height: 40px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 8px;
      padding: 7px;
      background: var(--background-color-default, #0d1117);
      color: inherit;
    }
    .manual-editor {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(100px, .62fr);
      gap: 6px;
      align-items: center;
    }
    .manual-editor > input,
    .manual-editor > select,
    .manual-editor > button {
      width: 100%;
      box-sizing: border-box;
    }
    .manual-editor-summary {
      grid-column: 1 / -1;
      display: flex;
      flex-wrap: wrap;
      gap: 6px 10px;
      align-items: center;
    }
    .manual-editor-details {
      flex: 0 0 auto;
    }
    .manual-editor-details[open] {
      flex-basis: 100%;
    }
    .manual-editor-details > summary {
      min-height: 32px;
      display: inline-flex;
      align-items: center;
      padding: 3px 9px;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 7px;
      background: var(--background-color-subtle, #161b22);
      color: inherit;
      cursor: pointer;
      font-weight: 700;
      list-style-position: inside;
    }
    .manual-editor-details[open] > summary {
      margin-bottom: 6px;
    }
    .mapping-warning { color: #f2cc60; font-weight: 700; }
    .automatic-match { color: #3fb950; font-weight: 700; }
    .copilot-reference {
      position: absolute;
      z-index: 5;
      bottom: 14px;
      left: 14px;
      display: none;
      width: min(410px, calc(48vw - 14px));
      min-width: min(300px, calc(100vw - 28px));
      max-width: calc(100% - 28px);
      max-height: min(58vh, 560px);
      overflow: hidden;
      flex-direction: column;
      border: 1px solid rgb(248 81 73 / 72%);
      border-radius: 10px;
      background: rgb(49 13 18 / 88%);
      color: #fff0f0;
      box-shadow: 0 8px 24px rgb(0 0 0 / 34%);
      backdrop-filter: blur(5px);
    }
    .copilot-reference[hidden] {
      display: none !important;
    }
    .copilot-reference-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      padding: 8px 10px;
      border-bottom: 1px solid rgb(248 81 73 / 38%);
      background: rgb(110 24 31 / 48%);
    }
    .copilot-reference-head button {
      min-height: 30px;
      padding: 3px 8px;
    }
    .copilot-reference-items {
      display: grid;
      gap: 5px;
      min-height: 0;
      overflow-y: auto;
      padding: 7px;
    }
    .copilot-reference-event {
      position: relative;
      width: 100%;
      min-height: 38px;
      overflow: hidden;
      padding: 15px 8px 6px;
      border: 1px solid rgb(248 81 73 / 24%);
      border-radius: 7px;
      background: rgb(74 18 24 / 42%);
      color: #ffd8d5;
      font-weight: var(--font-weight-semibold, 600);
      line-height: 1.2;
      text-align: left;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .copilot-reference-label {
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .copilot-closest-manual-tag {
      position: absolute;
      top: 0;
      right: 0;
      max-width: calc(100% - 10px);
      overflow: hidden;
      padding: 2px 5px 2px 8px;
      border-radius: 0 6px 0 7px;
      background: var(--true-color-red, #cf222e);
      color: #fff;
      font-size: 9px;
      font-weight: 700;
      line-height: 1.2;
      letter-spacing: .02em;
      text-overflow: ellipsis;
      text-transform: uppercase;
      white-space: nowrap;
    }
    .copilot-reference-event:hover,
    .copilot-reference-event:focus-visible {
      border-color: #ff7b72;
      background: rgb(153 40 48 / 42%);
    }
    .copilot-reference-event.reached {
      border-color: #ff7b72;
      box-shadow: inset 3px 0 0 #ff7b72;
    }
    .copilot-reference-event.current {
      border-color: #fff;
      background: rgb(218 54 51 / 76%);
      color: #fff;
      box-shadow:
        0 0 0 2px rgb(255 255 255 / 82%),
        0 0 24px 8px rgb(255 123 114 / 68%);
    }
    .copilot-reference-event.playback-ping {
      animation: reference-event-ping 1.6s ease-out;
    }
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
      document.getElementById("seek-engine-check-time").addEventListener(
        "click",
        seekEngineVerificationTime
      );
      document.getElementById("engine-check-seconds").addEventListener(
        "keydown",
        event => {
          if (event.key !== "Enter") return;
          event.preventDefault();
          seekEngineVerificationTime();
        }
      );
      document.getElementById("refresh-copilot-session").addEventListener(
        "click",
        async () => {
          const detail = document.getElementById("copilot-session-detail");
          detail.textContent = "Checking the Copilot project session connection…";
          try {
            await loadState();
          } catch (error) {
            detail.textContent =
              "Connection check failed: " + String(error.message || error);
          }
        }
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
      border: 1px solid rgb(228 165 218 / 52%);
      border-radius: 10px;
      background:
        radial-gradient(circle at 85% 8%, rgb(228 165 218 / 18%), transparent 34%),
        linear-gradient(145deg, #170919, #42103a 58%, #6c1d5f);
      color: #fff;
      box-shadow:
        inset 0 1px 0 rgb(255 255 255 / 12%),
        0 12px 28px rgb(0 0 0 / 34%);
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
    .segment-replay-modal {
      width: calc(100vw - 20px);
      max-width: none;
      height: calc(100dvh - 20px);
      max-height: none;
      padding: 0;
      border: 1px solid var(--border-color-default, #30363d);
      border-radius: 16px;
      background: #070b0d;
      color: #f0f6fc;
      overflow: hidden;
      box-shadow: 0 24px 80px rgb(0 0 0 / 70%);
    }
    .segment-replay-modal::backdrop {
      background: rgb(0 0 0 / 82%);
      backdrop-filter: blur(5px);
    }
    .segment-replay-modal-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      padding: 13px 16px;
      border-bottom: 1px solid rgb(255 255 255 / 14%);
      background: linear-gradient(90deg, #071b12, #102c20);
    }
    .segment-replay-modal-head h2 {
      margin: 0;
      font-size: 18px;
    }
    .segment-replay-modal-head p { margin: 2px 0 0; }
    .segment-replay-media {
      position: relative;
      display: flex;
      min-width: 0;
      height: calc(100dvh - 87px);
      align-items: center;
      justify-content: center;
      background: #000;
    }
    .segment-replay-media video {
      display: block;
      width: 100%;
      height: 100%;
      aspect-ratio: auto;
      object-fit: contain;
      object-position: center bottom;
      background: #000;
    }
    .stadium-scoreboard {
      position: absolute;
      left: 50%;
      top: 32px;
      width: min(760px, calc(100% - 40px));
      overflow: hidden;
      border: 1px solid rgb(228 165 218 / 68%);
      border-radius: 16px;
      background:
        radial-gradient(circle at 86% 0, rgb(228 165 218 / 22%), transparent 34%),
        linear-gradient(125deg, rgb(20 7 24 / 96%), rgb(76 16 66 / 95%) 58%,
          rgb(108 29 95 / 96%));
      box-shadow:
        inset 0 1px 0 rgb(255 255 255 / 16%),
        0 16px 48px rgb(0 0 0 / 64%),
        0 0 28px rgb(166 63 152 / 22%);
      backdrop-filter: blur(12px);
      transform: translateX(-50%);
      pointer-events: none;
    }
    .stadium-scoreboard::after {
      position: absolute;
      inset: 0;
      border: 1px solid rgb(255 255 255 / 8%);
      border-radius: inherit;
      content: "";
      pointer-events: none;
    }
    .stadium-scoreboard-head {
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      gap: 14px;
      align-items: center;
      padding: 9px 12px;
      border-bottom: 1px solid rgb(228 165 218 / 28%);
      background: rgb(11 4 14 / 48%);
    }
    .stadium-scoreboard-head strong {
      text-align: center;
      text-transform: uppercase;
      letter-spacing: .12em;
      text-wrap: balance;
    }
    .stadium-scoreboard-clock {
      font-family: var(--font-mono, Consolas, monospace);
      font-size: 16px;
      font-weight: 800;
      font-variant-numeric: tabular-nums;
    }
    .stadium-scoreboard-live {
      display: inline-flex;
      gap: 7px;
      align-items: center;
      color: #f6d8f1;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .1em;
      text-transform: uppercase;
    }
    .stadium-scoreboard-live::before {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #f778ba;
      box-shadow: 0 0 10px rgb(247 120 186 / 78%);
      content: "";
    }
    .stadium-scoreboard-brand {
      display: inline-flex;
      gap: 7px;
      align-items: center;
      justify-self: end;
      color: #f6d8f1;
      font-size: 10px;
      letter-spacing: .04em;
      text-transform: uppercase;
    }
    .stadium-scoreboard-logo {
      display: inline-flex;
      padding: 4px 7px;
      border-radius: 6px;
      background: #fff;
      box-shadow: inset 0 0 0 1px rgb(108 29 95 / 16%);
    }
    .stadium-scoreboard-brand img {
      display: block;
      width: 68px;
      height: 23px;
    }
    .stadium-scoreboard-teams {
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      gap: 16px;
      align-items: center;
      padding: 12px 16px 9px;
      text-align: center;
      font-size: 15px;
      font-weight: 800;
    }
    .stadium-scoreboard-team {
      display: inline-flex;
      gap: 8px;
      align-items: center;
      justify-content: center;
      min-width: 0;
    }
    .stadium-scoreboard-team:last-child {
      flex-direction: row-reverse;
    }
    .stadium-scoreboard-kit {
      width: 14px;
      height: 14px;
      border: 2px solid rgb(255 255 255 / 80%);
      border-radius: 50%;
      box-shadow: 0 0 0 2px rgb(0 0 0 / 28%);
    }
    .stadium-scoreboard-kit.red {
      background: linear-gradient(135deg, #f7f7f7 0 48%, #d73a49 48%);
    }
    .stadium-scoreboard-kit.black { background: #16161a; }
    .stadium-scoreboard-teams span {
      color: rgb(255 255 255 / 62%);
      font-size: 11px;
      text-transform: uppercase;
    }
    .segment-replay-stats {
      width: 100%;
      border-spacing: 0 4px;
      border-collapse: collapse;
      font-variant-numeric: tabular-nums;
    }
    .segment-replay-stats thead {
      color: #e4a5da;
      font-size: 10px;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .segment-replay-stats th,
    .segment-replay-stats td {
      padding: 7px 6px;
      border-top: 1px solid rgb(228 165 218 / 18%);
      text-align: center;
    }
    .segment-replay-stats tbody tr {
      background: linear-gradient(
        90deg,
        rgb(166 63 152 / 18%),
        rgb(255 255 255 / 3%) 42% 58%,
        rgb(108 29 95 / 24%)
      );
    }
    .segment-replay-stats tbody th {
      color: #f6d8f1;
      font-size: 12px;
      font-weight: 650;
      letter-spacing: .035em;
      text-transform: uppercase;
    }
    .segment-replay-stats td {
      width: 54px;
      color: #fff;
      font-size: 20px;
      font-weight: 900;
      text-shadow: 0 2px 10px rgb(0 0 0 / 60%);
    }
    .segment-replay-provenance {
      margin: 0;
      padding: 5px 12px 9px;
      color: #d7acd0;
      font-size: 11px;
      text-align: center;
    }
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
      right: 14px;
      display: none;
      width: min(860px, calc(86vw - 14px));
      height: min(58vh, 560px);
      min-width: min(360px, calc(100vw - 28px));
      min-height: 220px;
      max-width: calc(100% - 28px);
      max-height: calc(100dvh - 28px);
      overflow: hidden;
      resize: both;
      border: 1px solid rgb(240 246 252 / 24%);
      border-radius: 10px;
      background: rgb(13 17 23 / 76%);
      color: #f0f6fc;
      box-shadow: 0 8px 24px rgb(0 0 0 / 28%);
      backdrop-filter: blur(4px);
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
      flex: 0 0 auto;
      grid-template-columns:
        minmax(0, 1fr) 88px minmax(0, 1fr) auto auto auto;
      gap: 8px;
      padding: 8px 10px;
      border-bottom: 1px solid rgb(240 246 252 / 16%);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .04em;
    }
    .fullscreen-events-head span:nth-child(2) { text-align: center; }
    .fullscreen-events-head span:nth-child(3) { text-align: right; }
    .copilot-reference-toggle {
      display: inline-flex;
      gap: 5px;
      align-items: center;
      white-space: nowrap;
      text-transform: none;
      letter-spacing: normal;
    }
    .fullscreen-events-drag {
      min-height: 28px;
      padding: 3px 8px;
      cursor: grab;
      touch-action: none;
      text-transform: none;
      letter-spacing: normal;
      white-space: nowrap;
    }
    .fullscreen-events-drag:active { cursor: grabbing; }
    #validate-engine-reference {
      border-color: #d4a72c;
      background: #9a6700;
      color: #fff;
      font-weight: 700;
    }
    #validate-engine-reference:hover:not(:disabled) {
      border-color: #f2cc60;
      background: #b58407;
      color: #fff;
    }
    #approve-manual-minute[data-reference-state="unfrozen"],
    #golden-workflow-status[data-reference-state="unfrozen"] {
      border-color: #f0883e;
      background: rgb(240 136 62 / 18%);
      color: #ffa657;
    }
    #approve-manual-minute[data-reference-state="frozen"],
    #golden-workflow-status[data-reference-state="frozen"] {
      border-color: #58a6ff;
      background: rgb(31 111 235 / 22%);
      color: #79c0ff;
    }
    #approve-manual-minute[data-reference-state="published"],
    #golden-workflow-status[data-reference-state="published"] {
      border-color: var(--true-color-green, #2ea043);
      background: rgb(46 160 67 / 18%);
      color: var(--true-color-green, #7ee787);
    }
    #approve-manual-minute:disabled[data-reference-state] {
      opacity: 1;
    }
    #golden-workflow-status[data-reference-state] {
      display: inline-flex;
      min-height: 40px;
      align-items: center;
      padding: 8px 12px;
      border: 1px solid;
      border-radius: 8px;
      font-weight: 700;
    }
    .comparison-summary {
      display: flex;
      flex: 0 0 auto;
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
      flex: 0 0 auto;
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
      flex: 1 1 auto;
      grid-auto-rows: max-content;
      align-content: start;
      min-height: 0;
      overflow-y: auto;
      padding: 6px;
    }
    .innovation-manual-panel {
      display: block;
      flex: 0 0 auto;
      min-height: 0;
      overflow: hidden;
      border-top: 1px solid rgb(240 246 252 / 18%);
      background: rgb(13 17 23 / 82%);
    }
    .innovation-manual-panel:not([open]) {
      min-height: 34px;
    }
    .innovation-manual-panel > summary {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      padding: 7px 10px;
      list-style: none;
      cursor: pointer;
    }
    .innovation-manual-panel > summary::-webkit-details-marker {
      display: none;
    }
    .innovation-manual-panel > summary::after {
      color: #c9d1d9;
      content: "Show";
      font-size: 11px;
      font-weight: var(--font-weight-semibold, 600);
    }
    .innovation-manual-panel[open] > summary::after {
      content: "Hide";
    }
    .innovation-manual-panel .innovation-manual-controls {
      border: 0;
      border-radius: 0;
    }
    .fullscreen-event-chat {
      display: none;
      flex: 0 0 auto;
      min-height: 0;
      overflow: hidden;
      border-top: 1px solid rgb(240 246 252 / 18%);
      background: rgb(13 17 23 / 82%);
    }
    .video-shell:fullscreen .fullscreen-event-chat {
      display: block;
    }
    .video-shell:fullscreen .fullscreen-event-chat:not([open]) {
      min-height: 34px;
    }
    .video-shell:fullscreen .fullscreen-events:has(
      .fullscreen-event-chat[open]
    ) {
      min-height: min(560px, calc(100dvh - 28px));
    }
    .video-shell:fullscreen .fullscreen-event-chat[open] {
      display: grid;
      grid-template-rows: auto auto minmax(48px, 1fr) auto;
      flex: 0 0 min(220px, 48%);
      min-height: min(160px, 48%);
      max-height: min(250px, 48%);
    }
    .fullscreen-event-chat[hidden] {
      display: none !important;
    }
    .fullscreen-event-chat > summary {
      list-style: none;
      cursor: pointer;
    }
    .fullscreen-event-chat > summary::-webkit-details-marker {
      display: none;
    }
    .fullscreen-event-chat > summary::after {
      color: #c9d1d9;
      content: "Show";
      font-size: 11px;
      font-weight: var(--font-weight-semibold, 600);
    }
    .fullscreen-event-chat[open] > summary::after {
      content: "Hide";
    }
    .fullscreen-chat-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      padding: 7px 10px;
    }
    .fullscreen-event-chat .messages {
      min-height: 0;
      max-height: none;
      overflow-y: auto;
      overscroll-behavior: contain;
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
    .engine-user-claim {
      display: inline-flex;
      grid-column: 1 / -1;
      gap: 10px;
      align-items: center;
      width: fit-content;
      padding: 5px 8px;
      border: 1px solid var(--true-color-blue, #58a6ff);
      border-radius: 999px;
      background: rgb(31 111 235 / 18%);
      color: #f0f6fc;
      font-size: 12px;
      font-weight: var(--font-weight-semibold, 600);
    }
    .comparison-reviewer-verdict {
      display: block;
      margin-top: 3px;
      color: #a5d6ff;
      font-size: 10px;
      font-weight: var(--font-weight-semibold, 600);
      letter-spacing: .02em;
      text-transform: uppercase;
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
    .comparison-row.engine-selected {
      outline: 2px solid #58a6ff;
      outline-offset: -2px;
      background: rgb(31 111 235 / 22%);
    }
    .comparison-row.stoppage { background: rgb(210 153 34 / 16%); }
    .comparison-row.off { background: rgb(248 81 73 / 15%); }
    .comparison-row.manual-rejected {
      background: rgb(110 118 129 / 14%);
      box-shadow: inset 3px 0 0 #8c959f;
      opacity: .82;
    }
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
      align-content: start;
      justify-items: center;
      position: relative;
      padding-top: 8px;
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
      grid-template-areas:
        "event action"
        "status status";
      gap: 5px;
      align-content: start;
      align-items: center;
      min-width: 0;
      padding: 2px 4px;
    }
    .comparison-review-cell .comparison-event {
      grid-area: event;
      min-width: 0;
    }
    .comparison-review-cell > .comparison-actions {
      grid-area: action;
    }
    .comparison-review-cell > .comparison-accepted,
    .comparison-review-cell > .comparison-rejected,
    .comparison-review-cell > .comparison-reviewed {
      grid-area: status;
      justify-self: start;
    }
    .comparison-review-cell.verifying,
    .comparison-engine-cell.verifying {
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
      grid-template-columns: minmax(0, 1fr) auto;
      grid-template-areas:
        "event action"
        "status status";
      gap: 5px;
      align-content: start;
      align-items: center;
      min-width: 0;
      padding: 2px 4px;
    }
    .comparison-engine-cell .comparison-event {
      grid-area: event;
      min-width: 0;
    }
    .comparison-engine-cell > .comparison-action {
      grid-area: action;
    }
    .comparison-engine-cell > .comparison-rejected,
    .comparison-engine-cell > .comparison-reviewed {
      grid-area: status;
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
      white-space: nowrap;
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
    .comparison-new {
      display: inline-flex;
      width: fit-content;
      margin-top: 2px;
      padding: 1px 5px;
      border: 1px solid #d29922;
      border-radius: 999px;
      background: rgb(210 153 34 / 16%);
      color: #f2cc60;
      font-size: 9px;
      font-weight: var(--font-weight-semibold, 600);
      line-height: 1.25;
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
      0% {
        border-color: #d2ffd7;
        background: rgb(35 134 54 / 92%);
        color: #fff;
        box-shadow:
          0 0 0 3px rgb(255 255 255 / 88%),
          0 0 30px 12px rgb(63 255 93 / 90%);
        transform: scale(1.05);
      }
      55% {
        border-color: #7ee787;
        background: rgb(35 134 54 / 58%);
        box-shadow:
          0 0 0 18px rgb(63 255 93 / 0%),
          0 0 22px 6px rgb(63 255 93 / 34%);
      }
      100% {
        box-shadow: 0 0 0 0 rgb(63 255 93 / 0%);
        transform: scale(1);
      }
    }
    @keyframes copilot-event-ping {
      0% {
        border-color: #d9efff;
        background: rgb(31 111 235 / 92%);
        color: #fff;
        box-shadow:
          0 0 0 3px rgb(255 255 255 / 88%),
          0 0 30px 12px rgb(88 166 255 / 94%);
        transform: scale(1.05);
      }
      55% {
        border-color: #79c0ff;
        background: rgb(31 111 235 / 58%);
        box-shadow:
          0 0 0 18px rgb(88 166 255 / 0%),
          0 0 22px 6px rgb(88 166 255 / 38%);
      }
      100% {
        box-shadow: 0 0 0 0 rgb(88 166 255 / 0%);
        transform: scale(1);
      }
    }
    @keyframes reference-event-ping {
      0% {
        border-color: #ffd7d2;
        background: rgb(218 54 51 / 92%);
        color: #fff;
        box-shadow:
          0 0 0 3px rgb(255 255 255 / 88%),
          0 0 30px 12px rgb(255 123 114 / 90%);
        transform: scale(1.05);
      }
      55% {
        border-color: #ffa198;
        background: rgb(218 54 51 / 58%);
        box-shadow:
          0 0 0 18px rgb(255 123 114 / 0%),
          0 0 22px 6px rgb(255 123 114 / 34%);
      }
      100% {
        box-shadow: 0 0 0 0 rgb(255 123 114 / 0%);
        transform: scale(1);
      }
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
      .stadium-scoreboard {
        top: 18px;
        width: calc(100% - 24px);
      }
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
      .engine-verification-modal[data-review-state="working"]
        #engine-verification-guidance { animation: none; }
      .event-trigger.active { animation: none; }
      .comparison-event.playback-ping,
      .copilot-reference-event.playback-ping { animation: none; }
      .review-progress-dot { animation: none; }
      .segment-loading-spinner { animation: none; }
      .coordinate-round-result.processing::before { animation: none; }
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
    html[data-app-theme="innovation"] button {
      --innovation-hover-border: #cf6fbe;
      --innovation-hover-background: rgb(108 29 95 / 44%);
      --innovation-hover-glow: rgb(186 76 166 / 24%);
    }
    html[data-app-theme="innovation"]
      :is(#approve-manual-minute[data-reference-state="unfrozen"],
        #reopen-manual-minute, #validate-engine-reference, .adjust) {
      --innovation-hover-border: #ffa657;
      --innovation-hover-background: rgb(240 136 62 / 32%);
      --innovation-hover-glow: rgb(240 136 62 / 28%);
    }
    html[data-app-theme="innovation"]
      :is(#confirm-engine-without-copilot, #accept-copilot-decision,
        #publish-passed-segment, .accept, .segment-replay-action) {
      --innovation-hover-border: #7ee787;
      --innovation-hover-background: rgb(46 160 67 / 30%);
      --innovation-hover-glow: rgb(46 160 67 / 28%);
    }
    html[data-app-theme="innovation"]
      :is(#reject-copilot-decision, .reject, .coordinate-undefined-action) {
      --innovation-hover-border: #ff7b72;
      --innovation-hover-background: rgb(218 54 51 / 28%);
      --innovation-hover-glow: rgb(218 54 51 / 26%);
    }
    html[data-app-theme="innovation"]
      :is(#ask-copilot-engine-review, .regression-action, .publish-reference) {
      --innovation-hover-border: #79c0ff;
      --innovation-hover-background: rgb(31 111 235 / 34%);
      --innovation-hover-glow: rgb(31 111 235 / 28%);
    }
    html[data-app-theme="innovation"] button:not(:disabled):hover,
    html[data-app-theme="innovation"] .comparison-event:hover,
    html[data-app-theme="innovation"] .comparison-event:focus-visible {
      border-color: var(--innovation-hover-border, #cf6fbe) !important;
      background: var(
        --innovation-hover-background,
        rgb(108 29 95 / 44%)
      ) !important;
      color: #fff !important;
      box-shadow:
        0 0 0 1px var(--innovation-hover-glow, rgb(186 76 166 / 24%)),
        0 0 16px var(--innovation-hover-glow, rgb(186 76 166 / 24%));
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
  <div class="segment-loading-overlay" id="segment-loading-overlay"
    role="status" aria-live="assertive" aria-busy="true" hidden>
    <div class="segment-loading-card">
      <span class="segment-loading-spinner" aria-hidden="true"></span>
      <strong id="segment-loading-title">Loading segment…</strong>
      <span class="muted" id="segment-loading-detail">
        Loading video, coordinates, and review state.
      </span>
      <span class="segment-loading-elapsed" id="segment-loading-elapsed">
        Elapsed: 0s
      </span>
      <button id="segment-loading-close" type="button" hidden>Close</button>
      <button id="segment-loading-cancel" type="button" hidden>
        Cancel Copilot Review
      </button>
    </div>
  </div>
  <dialog id="coordination-idle-warning">
    <form method="dialog">
      <h2>Still working on this segment?</h2>
      <p>
        The editing lease will be released after 20 minutes of inactivity.
        Background analysis and regression jobs will continue.
      </p>
      <div class="actions">
        <button id="keep-segment-lease" type="button">Keep working</button>
        <button value="release">Release now</button>
      </div>
    </form>
  </dialog>
  <dialog class="engine-verification-modal" id="engine-verification-modal"
    aria-labelledby="engine-verification-title">
    <form method="dialog">
      <header>
        <h2 id="engine-verification-title">Review rules-engine event</h2>
        <p class="muted" id="engine-verification-event"></p>
      </header>
      <p>
        This guide applies only to the selected E# already produced by the
        rules engine. Watch the targeted video evidence, then choose the
        statement that best matches what you can support. Opening or closing
        this window does not start Copilot, spend AI credits, or change the
        event.
      </p>
      <div class="engine-verification-time" id="engine-verification-time" hidden>
        <label for="engine-check-seconds">
          Optional corrected E# completion time (seconds)
          <input id="engine-check-seconds" type="text" inputmode="decimal"
            autocomplete="off" placeholder="For example, 2.900">
        </label>
        <button id="seek-engine-check-time" type="button">
          Preview time in video
        </button>
        <small id="engine-check-time-status" aria-live="polite">
          Use this only when the E# completion time is wrong. Previewing does
          not change M# or E#; the time is sent to Copilot with the correction
          request.
        </small>
      </div>
      <fieldset>
        <legend>Your evidence decision</legend>
        <label class="engine-verification-choice">
          <input name="engine-verification-decision" type="radio"
            value="correct">
          <strong>Correct — exact event is supported</strong>
          <span>
            The team, canonical event type, and completion time are all
            visibly correct. Approve the existing E# from your professional
            review. No Copilot review, engine check, engine change, or
            regression run is needed.
          </span>
        </label>
        <label class="engine-verification-choice">
          <input name="engine-verification-decision" type="radio"
            value="details_wrong">
          <strong>Same play, but this E# timing or details are wrong</strong>
          <span>
            The play occurred, but this E# has the wrong completion time, team,
            or event type. Keep M# unchanged and send this E# discrepancy for
            a general rules-engine fix and cached rerun.
          </span>
        </label>
        <label class="engine-verification-choice">
          <input name="engine-verification-decision" type="radio"
            value="incorrect">
          <strong>No such event occurred — reject this E#</strong>
          <span>
            The exact E# is unsupported by the video. Reject it and send only
            this discrepancy for a general rules-engine fix and cached rerun.
          </span>
        </label>
        <label class="engine-verification-choice">
          <input name="engine-verification-decision" type="radio"
            value="cannot_verify">
          <strong>Cannot verify from this camera</strong>
          <span>
            Occlusion, framing, or insufficient evidence prevents a reliable
            decision. Ask Copilot to inspect the targeted prepared context;
            uncertainty must remain unconfirmed rather than become a guess.
          </span>
        </label>
      </fieldset>
      <fieldset class="similar-review-group"
        id="engine-similar-review-group" hidden>
        <legend>Check similar E# discrepancies together</legend>
        <div class="similar-review-list" id="engine-similar-review-list"></div>
        <small>
          Only unmatched, reviewable E# events with this same canonical event
          type are available. One evidence decision and one Copilot request
          applies to every checked E#.
        </small>
      </fieldset>
      <p class="engine-verification-cost-note"
        id="engine-verification-guidance" aria-live="polite">
        Choose an evidence decision to see the available next action.
      </p>
      <div class="engine-verification-actions">
        <button id="cancel-engine-verification" type="button">
          Close
        </button>
        <button id="confirm-engine-without-copilot" type="button" disabled>
          Approve exact E# without Copilot
        </button>
        <button id="ask-copilot-engine-review" type="button">
          Ask Copilot to review
        </button>
      </div>
    </form>
  </dialog>
  <dialog class="engine-verification-modal" id="manual-engine-review-modal"
    aria-labelledby="manual-engine-review-title">
    <form method="dialog">
      <header>
        <h2 id="manual-engine-review-title">Review unmatched manual event</h2>
        <p class="muted" id="manual-engine-review-event"></p>
      </header>
      <p>
        First decide whether a current E# represents this play. Then choose
        what your video review says. Nothing changes until you use the action
        at the bottom.
      </p>
      <fieldset>
        <legend>Your evidence decision</legend>
        <label class="engine-verification-choice">
          <input name="manual-engine-review-decision" type="radio"
            value="engine_match_wrong">
          <strong>Existing E# is this play, but E# timing or details are wrong</strong>
          <span>
            M# is accepted as correct. Copilot must correct the general engine
            cause, rebuild E# output, and make this play match M# without
            changing the golden reference.
          </span>
        </label>
        <label class="engine-verification-choice">
          <input name="manual-engine-review-decision" type="radio"
            value="correct">
          <strong>No E# represents this play — the engine missed M#</strong>
          <span>
            M# is accepted as correct. Copilot must diagnose the general engine
            cause, rebuild cached E# output, and run protected regressions
            without changing the golden reference.
          </span>
        </label>
        <label class="engine-verification-choice"
          data-manual-draft-action>
          <input name="manual-engine-review-decision" type="radio"
            value="details_wrong">
          <strong>M# itself is wrong — edit M#</strong>
          <span>Close this guide and expand the M# time/team/type editor.</span>
        </label>
        <label class="engine-verification-choice"
          data-manual-draft-action>
          <input name="manual-engine-review-decision" type="radio"
            value="reject">
          <strong>Reject M# — not supported by the video</strong>
          <span>
            Keep a visible audit record, but exclude this M# from matching and
            the golden set.
          </span>
        </label>
        <label class="engine-verification-choice"
          data-manual-draft-action>
          <input name="manual-engine-review-decision" type="radio"
            value="remove">
          <strong>Remove M# — added in error</strong>
          <span>
            Remove the manual entry because it should not have been recorded.
          </span>
        </label>
        <label class="engine-verification-choice">
          <input name="manual-engine-review-decision" type="radio"
            value="cannot_verify">
          <strong>Cannot verify from this camera</strong>
          <span>
            Ask Copilot to inspect the targeted evidence without assuming that
            either M# or the engine is correct.
          </span>
        </label>
      </fieldset>
      <fieldset class="similar-review-group"
        id="manual-similar-review-group" hidden>
        <legend>Check similar unmatched M# events together</legend>
        <div class="similar-review-list" id="manual-similar-review-list"></div>
        <small>
          Only unmatched M# events with this same canonical event type are
          available. One professional verdict and one Copilot request applies
          to every checked M#.
        </small>
      </fieldset>
      <p class="engine-verification-cost-note"
        id="manual-engine-review-frozen-note" hidden>
        Golden M# is frozen. Reopen the manual reference before editing,
        rejecting, or removing an M#.
      </p>
      <p class="engine-verification-cost-note"
        id="manual-engine-review-guidance" aria-live="polite">
        Choose an evidence decision to see the available next action.
      </p>
      <div class="engine-verification-actions">
        <button id="close-manual-engine-review" type="button">
          Close Modal
        </button>
        <button id="cancel-manual-copilot-review" type="button" hidden>
          Cancel Copilot Review
        </button>
        <button id="ask-copilot-manual-engine-review" type="button">
          Choose a decision
        </button>
      </div>
    </form>
  </dialog>
  <dialog class="engine-verification-modal" id="copilot-decision-modal"
    aria-labelledby="copilot-decision-title">
    <form method="dialog">
      <header>
        <h2 id="copilot-decision-title">Decide Copilot proposal</h2>
        <p class="muted" id="copilot-decision-event"></p>
      </header>
      <p>
        This guide applies only to the selected C# proposal. Choose what should
        happen to the proposal; a nearby E# is never accepted or rejected
        merely because it matches this C#.
      </p>
      <div class="copilot-decision-options">
        <button class="copilot-decision-option" id="accept-copilot-decision"
          type="button">
          <strong>Accept C# proposal</strong>
          <span id="accept-copilot-decision-detail"></span>
        </button>
        <button class="copilot-decision-option" id="reject-copilot-decision"
          type="button">
          <strong>Reject C# proposal</strong>
          <span id="reject-copilot-decision-detail"></span>
        </button>
      </div>
      <p class="engine-verification-cost-note">
        If the event exists but a detail is wrong, close this guide and use
        <strong>Request Adjustment</strong> on the selected C# instead.
      </p>
      <div class="engine-verification-actions">
        <button id="cancel-copilot-decision" type="button">
          Cancel / Close
        </button>
      </div>
    </form>
  </dialog>
  ${adapter.key === "innovation" ? `
  <dialog class="engine-verification-modal manual-ledger-audit-modal"
    id="manual-ledger-audit-modal"
    aria-labelledby="manual-ledger-audit-title">
    <form method="dialog">
      <header>
        <h2 id="manual-ledger-audit-title">M# Ledger Audit</h2>
        <p class="muted">
          Separate deterministic checks for the current manual ledger
        </p>
      </header>
      <p>
        This local code checks M# only. It does not call Copilot, inspect E#,
        change an event, or overrule your continuous-video review.
      </p>
      <p class="manual-ledger-audit-summary"
        id="manual-ledger-audit-summary" aria-live="polite"></p>
      <div class="manual-ledger-audit-list"
        id="manual-ledger-audit-list"></div>
      <p class="muted">
        The current manual schema supports completed passes and turnovers.
        Restart and shot/SOT checks will remain unavailable until those event
        types are part of manual review.
      </p>
      <p class="muted" id="manual-ledger-audit-status"
        aria-live="polite"></p>
      <div class="engine-verification-actions">
        <button id="close-manual-ledger-audit" type="button">Close</button>
      </div>
    </form>
  </dialog>
  ` : ""}
  <header>
    <div class="review-heading">
      ${adapter.key === "innovation" ? `
      <div class="review-brand-lockup"
        aria-label="Grassroots Football Intelligence and Xebia">
        ${INNOVATION_MARK_SVG}
        <span class="review-brand-xebia">${INNOVATION_XEBIA_SVG}</span>
      </div>` : ""}
      <div>
        <h1 id="page-title">${adapter.displayName}</h1>
        <div class="muted" id="page-subtitle">
          Prepared segment → reference review → engine check
        </div>
        <div class="innovation-brand">
          ${adapter.brandLead ? `<strong>${adapter.brandLead}</strong>` : ""}
          <span>${adapter.brandDetail}</span>
          <span class="component-version" id="tracker-version">
            ${adapter.trackerLoadingLabel}
          </span>
          <span class="component-version" id="ball-coordinate-coverage">
            Ball coordinates: loading
          </span>
          <span class="component-version" id="rules-version">
            Rules engine: loading
          </span>
        </div>
      </div>
    </div>
    <div class="header-actions">
      <label class="review-mode-field" for="workflow-adapter">
        Workflow
        <select id="workflow-adapter">
          <option value="innovation"${
            adapter.key === "innovation" ? " selected" : ""
          }>Innovation Day — Frozen BAC</option>
          <option value="live"${
            adapter.key === "live" ? " selected" : ""
          }>Live — Raw-video pipeline</option>
        </select>
      </label>
      <label class="review-mode-field" for="review-audience">
        Review mode
        <select id="review-audience">
          <option value="reviewer">Normal review</option>
          <option value="developer">Developer</option>
        </select>
      </label>
      <a class="home-link" href="${homeUrl}">${homeLabel}</a>
      <span class="scope">${adapter.scopeLabel}</span>
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
    <button id="cancel-copilot-review" type="button" hidden>
      Cancel Copilot Review
    </button>
  </p>
  <dialog class="segment-replay-modal" id="segment-replay-modal"
    aria-labelledby="segment-replay-title">
    <header class="segment-replay-modal-head">
      <div>
        <h2 id="segment-replay-title">Cached engine replay</h2>
        <p class="muted" id="segment-replay-subtitle"></p>
      </div>
      <button id="close-segment-replay" type="button">Close</button>
    </header>
    <section class="segment-replay-media" aria-label="Stadium segment replay">
      <video id="segment-replay-video" controls preload="metadata"></video>
      <aside class="stadium-scoreboard"
        aria-label="Football statistics from cached engine output">
        <div class="stadium-scoreboard-head">
          <span class="stadium-scoreboard-live">Replay statistics</span>
          <strong>Innovation Day Match Centre</strong>
          <div class="stadium-scoreboard-brand">
            <span>Powered by</span>
            <span class="stadium-scoreboard-logo">
              <img src="${homeUrl.replace(/\/$/, "")}/assets/xebia-logo.svg"
                width="68" height="23" alt="Xebia">
            </span>
          </div>
        </div>
        <div class="stadium-scoreboard-teams">
          <strong class="stadium-scoreboard-team live-team-red">
            <span class="stadium-scoreboard-kit red" aria-hidden="true"></span>
            Red/white
          </strong>
          <span class="stadium-scoreboard-clock"
            id="segment-replay-clock">00:00 / 00:00</span>
          <strong class="stadium-scoreboard-team live-team-black">
            <span class="stadium-scoreboard-kit black" aria-hidden="true"></span>
            Black
          </strong>
        </div>
        <table class="segment-replay-stats">
          <thead>
            <tr>
              <th class="live-team-red">Red/white</th>
              <th>Statistic</th>
              <th class="live-team-black">Black</th>
            </tr>
          </thead>
          <tbody>
            <tr><td id="segment-replay-red-passes">0</td><th>Completed passes</th>
              <td id="segment-replay-black-passes">0</td></tr>
            <tr><td id="segment-replay-red-turnovers">0</td><th>Turnovers</th>
              <td id="segment-replay-black-turnovers">0</td></tr>
            <tr><td id="segment-replay-red-shots">0</td><th>Shots</th>
              <td id="segment-replay-black-shots">0</td></tr>
            <tr><td id="segment-replay-red-on-target">0</td><th>On target</th>
              <td id="segment-replay-black-on-target">0</td></tr>
          </tbody>
        </table>
        <p class="segment-replay-provenance">
          Read-only stadium replay · cached rules-engine statistics only
        </p>
      </aside>
    </section>
  </dialog>
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
            <button id="prepare-innovation-evidence" type="button" hidden>
              Prepare BAC + player context
            </button>
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
        <div class="coordination-status copilot-session-status"
          id="copilot-session-status" role="status" aria-live="polite" hidden>
          <strong>Copilot project session required</strong>
          <span class="coordination-detail muted"
            id="copilot-session-detail"></span>
          <button id="refresh-copilot-session" type="button">
            Refresh connection
          </button>
        </div>
        <div class="coordination-status" id="coordination-status" hidden>
          <strong id="coordination-title">Shared coordination</strong>
          <span class="coordination-detail muted"
            id="coordination-detail"></span>
          <button id="start-segment-work" type="button">Start working</button>
          <button id="stop-segment-work" type="button" hidden>
            Stop working
          </button>
        </div>
      </div>
      <details class="shared-review-card" id="shared-review-panel">
        <summary>Shared approvals &amp; validation gates</summary>
        <div class="regression-batch-actions"
          id="regression-batch-actions" hidden>
          <button id="select-passed-regressions" type="button">
            Select all passed
          </button>
          <button id="run-selected-regressions" type="button" disabled>
            Run selected (0)
          </button>
          <button id="view-regression-runs" type="button">
            View regression runs
          </button>
          <span class="muted" id="regression-batch-status"></span>
        </div>
        <div class="table-wrap">
          <table class="shared-review-table"
            aria-label="Shared review status for all prepared segments">
            <thead>
              <tr>
                <th scope="col">Select</th>
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
        <section class="regression-queue" id="regression-review-queue" hidden>
          <strong>Regression review required</strong>
          <p id="regression-review-summary"></p>
          <ul id="regression-review-failures"></ul>
        </section>
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
                Open coordinate review
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
                    <th scope="col">Frame</th>
                    <th scope="col">Time</th>
                    <th scope="col">X</th>
                    <th scope="col">Y</th>
                    <th scope="col">Status</th>
                    <th scope="col">Evidence</th>
                    <th scope="col">Review status</th>
                    <th scope="col">Your decision</th>
                  </tr>
                </thead>
                <tbody id="ball-frame-items"></tbody>
              </table>
            </div>
          </details>
          <div class="video-shell" id="video-shell">
        <div class="video-media" id="video-media">
          <div class="video-zoom-layer" id="video-zoom-layer">
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
            <g class="ball-coordinate-label" id="ball-coordinate-label" hidden>
              <rect width="690" height="72" rx="10"></rect>
              <text x="18" y="50" id="ball-coordinate-label-text"></text>
            </g>
          </svg>
          <canvas class="geometry-overlay" id="geometry-overlay"
            aria-label="Calibrated pitch and goal outlines"></canvas>
          </div>
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
          <aside class="live-stats-overlay" aria-label="${adapter.statisticsLabel}">
            <div class="live-stats-head">
              <strong>${adapter.statisticsTitle}</strong>
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
              <span>${adapter.key === "innovation" ? "Manual M#" : "Review proposal"}</span>
              <span>Seconds</span>
              <span>${adapter.key === "innovation" ? "Rules engine E#" : "Rules engine output"}</span>
              <button class="fullscreen-events-drag"
                id="move-event-panel" type="button"
                aria-label="Drag the Events panel; use arrow keys to move it"
                title="Drag to move · Arrow keys move the panel">
                Move
              </button>
            </div>
            <div class="comparison-summary" id="comparison-summary"
              aria-live="polite"></div>
            <details class="comparison-guide" aria-label="Comparison guidance">
              <summary>How to read this comparison</summary>
              <div class="comparison-guide-grid">
                <div class="comparison-guide-column">
                  <span class="comparison-guide-line">
                    <strong>Manual M#</strong>: edit time, team, or event type
                    directly; changes save automatically.
                  </span>
                  <span class="comparison-guide-line">
                    <strong>Unmatched M#</strong>: no engine event has the same
                    team and event type within one second.
                  </span>
                </div>
                <div class="comparison-guide-column general">
                  <span class="comparison-guide-line">
                    <strong>General</strong>
                  </span>
                  <span class="comparison-guide-line">
                    Unique M#/E# matches within one second appear immediately.
                    No arrow or manual mapping is required.
                  </span>
                </div>
                <div class="comparison-guide-column">
                  <span class="comparison-guide-line">
                    <strong>Rules engine E#</strong>: matching rows show engine
                    agreement.
                  </span>
                  <span class="comparison-guide-line">
                    <strong>Unmatched E#</strong>: verify the discrepancy and
                    fix only a general engine rule when needed.
                  </span>
                </div>
              </div>
            </details>
            <div class="fullscreen-event-items" id="fullscreen-event-items"></div>
            ${adapter.key === "innovation" ? `
            <details class="innovation-manual-panel"
              id="innovation-manual-panel" open
              aria-labelledby="innovation-manual-panel-title">
              <summary>
                <strong id="innovation-manual-panel-title">
                  Manual event and publication controls
                </strong>
              </summary>
              <div class="innovation-manual-controls">
                <span class="manual-capture-label">
                  Add M# at the current video time:
                </span>
                <button type="button" data-manual-team="black"
                  data-manual-type="completed_pass">Black completed pass</button>
                <button type="button" data-manual-team="black"
                  data-manual-type="turnover">Black turnover</button>
                <button type="button" data-manual-team="red"
                  data-manual-type="completed_pass">White/red completed pass</button>
                <button type="button" data-manual-team="red"
                  data-manual-type="turnover">White/red turnover</button>
                <label>
                  <input id="show-bac-coordinate" type="checkbox">
                  Show BAC ball coordinate
                </label>
                <button id="open-manual-ledger-audit" type="button">
                  Audit M# ledger
                </button>
                <button id="approve-manual-minute" type="button">
                  Freeze manual M# reference as golden
                </button>
                <button id="validate-engine-reference" type="button" hidden>
                  Validate engine against golden reference
                </button>
                <button id="publish-passed-segment" type="button" hidden>
                  Publish Passed segment
                </button>
                <button id="reopen-manual-minute" type="button" hidden>
                  Reopen approved minute for editing (cannot be undone)
                </button>
                <output id="golden-workflow-status" aria-live="polite"></output>
              </div>
            </details>
            ` : ""}
            <details class="fullscreen-event-chat" id="fullscreen-event-chat"
              data-ai-gated
              aria-labelledby="fullscreen-chat-title">
              <summary class="fullscreen-chat-head">
                <strong id="fullscreen-chat-title">
                  Selected event conversation
                </strong>
                <span class="chat-status" id="fullscreen-chat-activity"
                  data-state="ready">Ready</span>
              </summary>
              <p class="fullscreen-workflow-note"
                id="fullscreen-workflow-note"></p>
              <ol class="messages" id="fullscreen-messages"
                aria-live="polite"></ol>
              <form class="fullscreen-chat-composer"
                id="fullscreen-chat-composer">
                <fieldset class="engine-user-claim"
                  id="engine-user-claim" hidden>
                  <legend>My professional opinion</legend>
                  <label>
                    <input name="engine-user-verdict" type="radio"
                      value="correct">
                    Correct
                  </label>
                  <label>
                    <input name="engine-user-verdict" type="radio"
                      value="incorrect">
                    Incorrect
                  </label>
                  <label>
                    <input name="engine-user-verdict" type="radio"
                      value="unsure">
                    Unsure
                  </label>
                </fieldset>
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
            </details>
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
          <button id="toggle-playback" type="button">Play</button>
          <button id="previous-frame" type="button">← Frame</button>
          <button id="next-frame" type="button">Frame →</button>
          <label class="timeline-control">Review Position
            <input id="timeline" name="timeline" type="range"
              min="0" max="60" step="0.04" value="0" autocomplete="off">
          </label>
          <output class="time" id="time" aria-live="polite">0.00s</output>
          <output class="muted" id="playback-status"
            aria-live="polite"></output>
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
          ${adapter.key === "innovation" ? `
          <div class="innovation-manual-controls"
            aria-label="Quick capture manual football events">
            <button type="button" data-manual-team="black"
              data-manual-type="completed_pass">Black completed pass</button>
            <button type="button" data-manual-team="black"
              data-manual-type="turnover">Black turnover</button>
            <button type="button" data-manual-team="red"
              data-manual-type="completed_pass">White/red completed pass</button>
            <button type="button" data-manual-team="red"
              data-manual-type="turnover">White/red turnover</button>
            <output id="manual-capture-status" aria-live="polite"></output>
          </div>
          ` : ""}
          <div class="video-zoom-controls"
            aria-label="Manual video zoom">
            <button id="zoom-out" type="button"
              aria-label="Zoom video out" title="Zoom video out">−</button>
            <output id="video-zoom-level" aria-live="polite">1×</output>
            <button id="zoom-in" type="button"
              aria-label="Zoom video in" title="Zoom video in">+</button>
          </div>
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
              <span class="coordinate-review-result pending"
                id="ball-frame-current-decision">
                Current decision: Awaiting decision
              </span>
              <span class="coordinate-review-result pending"
                id="ball-frame-resolution-status" hidden></span>
              <span class="decision-detail" id="ball-frame-decision-status">
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
                <circle class="ball-frame-modal-marker engine-coordinate"
                  id="ball-frame-modal-marker" r="7"></circle>
                <path class="ball-frame-modal-crosshair"
                  id="ball-frame-modal-crosshair"></path>
                <g id="ball-frame-yolo-markers"></g>
                <circle class="ball-frame-user-marker"
                  id="ball-frame-user-marker" r="14" hidden></circle>
              </svg>
              <div class="ball-frame-pointer" id="ball-frame-pointer" hidden>
                <span class="ball-frame-pointer-label"
                  id="ball-frame-pointer-label"></span>
              </div>
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
            <div class="coordinate-decision-guide"
              id="coordinate-decision-guide"${
                adapter.coordinateCorrectionEnabled ? "" : " hidden"
              }>
              <strong>Choose an evidence outcome</strong>
              <ul>
                <li><b>Agree with coordinate</b> — the proposed coordinate is supported.</li>
                <li><b>YOLO candidate is correct</b> — the ball is visible in a blue ring, but the selector did not choose it.</li>
                <li><b>Specify my own coordinate</b> — the ball is visible elsewhere.</li>
                <li><b>Ball undefined / not visible</b> — the single camera cannot show the ball, including player occlusion.</li>
                <li><b>Needs more checking</b> — the image is ambiguous but potentially reviewable.</li>
              </ul>
            </div>
            <div class="yolo-candidate-actions"
              id="yolo-candidate-actions" hidden></div>
            <div class="ball-frame-modal-actions">
              <div class="ball-review-navigation"
                id="ball-review-navigation"${
                  adapter.coordinateCorrectionEnabled ? "" : " hidden"
                }>
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
                title="Agree with current coordinate"${
                  adapter.coordinateCorrectionEnabled ? "" : " hidden"
                }>
                ✓
              </button>
              <button class="coordinate-undefined-action"
                id="undefined-ball-coordinate" type="button"
                aria-label="Ball undefined or not visible"
                title="Use when the ball is hidden, occluded, or not visible"${
                  adapter.coordinateCorrectionEnabled ? "" : " hidden"
                }>
                Ball undefined / not visible
              </button>
              <button id="needs-more-checking" type="button" hidden>
                Needs more checking
              </button>
              <button id="mark-ball-location" type="button"${
                adapter.coordinateCorrectionEnabled ? "" : " hidden"
              }>
                Specify my own coordinate
              </button>
              <button id="approve-ball-location" type="button" disabled${
                adapter.coordinateCorrectionEnabled ? "" : " hidden"
              }>
                Confirm my coordinate &amp; next target
              </button>
              <button class="coordinate-icon-action"
                id="undo-ball-coordinate-decision" type="button" disabled
                aria-label="Undo coordinate decision"
                title="Undo coordinate decision"${
                  adapter.coordinateCorrectionEnabled ? "" : " hidden"
                }>
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
              <strong>Ball coordinate review</strong>
              <button id="close-ball-coordinate-review" type="button">
                Close
              </button>
            </div>
            <nav class="event-nav" id="coordinate-review-tabs"
              aria-label="Ball-coordinate review rounds"></nav>
            <ol class="coordinate-review-messages"
              id="coordinate-review-timeline" aria-live="polite"></ol>
            <p class="ball-frame-modal-status" id="coordinate-round-result"
              role="status" aria-live="polite" hidden></p>
            <div class="ball-frame-modal-details">
              ${adapter.reviewerCorrectedDemoLayer
                ? "Frozen BAC remains unchanged. Applying this batch creates "
                  + "a shared, versioned reviewer-coordinate layer used by "
                  + "the Innovation rules engine for this segment."
                : "Review decisions remain evaluation-only and never become "
                  + "inference inputs."}
            </div>
            <div class="ball-coordinate-modal-frames"
              id="ball-coordinate-modal-frames"></div>
            <p class="muted" id="ball-coordinate-review-send-status"
              aria-live="polite"></p>
            <div class="ball-frame-modal-actions">
              <button id="apply-reviewer-coordinate-layer" type="button"${
                adapter.reviewerCorrectedDemoLayer ? "" : " hidden"
              } disabled>
                Apply approved coordinate updates
              </button>
              <button class="copilot-handover"${
                adapter.coordinateReviewEnabled ? "" : " hidden"
              }
                id="send-ball-coordinate-autopilot" type="button">
                Review &amp; improve approved batch once (Autopilot)
              </button>
              <button id="finalize-ball-coordinate-review" type="button"${
                adapter.coordinateReviewEnabled ? "" : " hidden"
              }
                disabled>
                Start rules-engine run
              </button>
              <button id="improve-coordinate-coverage" type="button" hidden>
                Improve coverage with unresolved frames
              </button>
            </div>
          </dialog>
        </div>

        <aside class="event-rail" data-ai-gated
          aria-label="Current event review">
          <p class="engine-output-notice" id="engine-output-notice"
            role="status" hidden>
            Showing the current engine candidate for regression review.
            Published files remain unchanged.
          </p>
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
              <li><strong>Red E# without C#:</strong> use its E# decision guide.
                A professional reviewer can approve an exact supported E#
                directly, or explicitly ask Copilot to adjudicate it.</li>
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
          <li><strong>Correct:</strong> accept the proposal. A matching E#
            requires no engine change.</li>
          <li><strong>Want a handover:</strong> let Copilot verify this event,
            then accept only when it agrees. It changes a general rule only
            when the engine is missing or contradicting the accepted event.</li>
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
              <h2 id="conversation-title">${adapter.conversationPrefix}Event 1</h2>
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
    const reviewWorkflow = ${JSON.stringify({
      key: adapter.key,
      conversationPrefix: adapter.conversationPrefix,
      processorScript: adapter.processorScript,
      processorArguments: adapter.processorArguments,
      preparationMessage: adapter.preparationMessage,
      processingMessage: adapter.processingMessage,
      recoveryMessage: adapter.recoveryMessage,
      detectionMessage: adapter.detectionMessage,
      coordinateReviewEnabled: adapter.coordinateReviewEnabled,
      coordinateCorrectionEnabled: adapter.coordinateCorrectionEnabled,
      reviewerCorrectedDemoLayer: adapter.reviewerCorrectedDemoLayer,
      evidencePreparationEnabled: adapter.evidencePreparationEnabled,
    })};
    const stateUrl = "/api/state";
    const hostInstanceId =
      new URLSearchParams(window.location.search).get("hostInstanceId") || "";
    const workflowAdapterSelect =
      document.getElementById("workflow-adapter");
    const workflowSegmentStorageKey = workflowKey =>
      "football-review-last-segment-" + workflowKey;
    const REVIEW_FPS = 25;
    let state = null;
    const selectedRegressionSegments = new Set();
    const manualTimeDrafts = new Map();
    let fullscreenEventsRenderSignature = null;
    let forceFullscreenEventsRender = false;
    let activeRegressionBatch = new Set();
    let regressionDashboardOpen = false;
    let regressionDashboardCloseTimer = null;
    let coordinationHeartbeatTimer = null;
    let coordinationIdleTimer = null;
    let coordinationTimerLeaseKey = null;
    let coordinationLastActivityAt = Date.now();
    let startInputsInitialized = false;
    let selectedIndex = 0;
    let selectedCopilotReferenceIndex = null;
    let manualEngineReviewIndex = null;
    let manualEngineReviewPending = null;
    let selectedEngineIndex = null;
    let showBacCoordinate = false;
    let verificationModalEngineIndex = null;
    let engineVerificationPending = null;
    let decisionModalReviewIndex = null;
    let reviewAudience =
      localStorage.getItem("football-review-audience") === "developer"
      ? "developer"
      : "reviewer";
    let actionZoom = false;
    let manualZoom = 1;
    let videoPanX = 0;
    let videoPanY = 0;
    let statusTimer = null;
    let segmentPreparationPending = false;
    let runStartPending = false;
    let validateGoldenAfterEngineRun = false;
    let analysisModalMode = null;
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
    let selectedCoordinateBatchId = null;
    let lastCoordinateBatchStatus = null;
    let lastCoordinateBatchId = null;
    let ballFrameSaveQueue = Promise.resolve();
    let rawBallFrameSeekPending = false;
    let rawBallFrameSeekRequest = 0;
    let pendingReviewSeconds = null;
    let pendingMissingReport = null;
    let segmentBuilderInitialized = false;
    let previousPlaybackSeconds = 0;
    const eventTriggerTimers = {manual: null, copilot: null, engine: null};
    let playbackFrameRequest = null;
    let replayRunId = null;
    let replaySegmentIndex = 0;
    let segmentReplayKey = null;
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
    const videoZoomLayer = document.getElementById("video-zoom-layer");
    const videoEmpty = document.getElementById("video-empty");
    const segmentBuilderPanel =
      document.getElementById("segment-builder-panel");
    const ballOverlay = document.getElementById("ball-overlay");
    const ballMarker = document.getElementById("ball-marker");
    const ballCrosshair = document.getElementById("ball-crosshair");
    const ballTrajectory = document.getElementById("ball-trajectory");
    const ballCoordinateLabel =
      document.getElementById("ball-coordinate-label");
    const ballCoordinateLabelText =
      document.getElementById("ball-coordinate-label-text");
    const sourceSelect = document.getElementById("source-select");
    const segmentSelect = document.getElementById("segment-select");
    const startMinute = document.getElementById("segment-start-minute");
    const startSecond = document.getElementById("segment-start-second");
    const segmentDuration = document.getElementById("segment-duration");
    const prepareButton = document.getElementById("prepare-segment");
    const processButton = document.getElementById("process-segment");
    const prepareEvidenceButton =
      document.getElementById("prepare-innovation-evidence");
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
    const segmentReplayModal =
      document.getElementById("segment-replay-modal");
    const segmentReplayVideo =
      document.getElementById("segment-replay-video");

    function selectedSegmentKey() {
      return new URLSearchParams(location.search).get("segment") ||
        state?.segment?.key ||
        "segment-0300-020";
    }

    function engineVerificationCheckTime() {
      const input = document.getElementById("engine-check-seconds");
      const raw = input.value.trim();
      if (!raw) return null;
      const seconds = Number(raw);
      if (
        !Number.isFinite(seconds)
        || seconds < 0
        || seconds > Number(state.segment.durationSeconds)
      ) {
        throw new Error(
          "Enter seconds from 0 to "
          + Number(state.segment.durationSeconds).toFixed(3)
          + ", for example 2.900."
        );
      }
      return Math.round(seconds * 1000) / 1000;
    }

    function seekEngineVerificationTime() {
      const status = document.getElementById("engine-check-time-status");
      try {
        const seconds = engineVerificationCheckTime();
        if (seconds === null) {
          throw new Error("Enter the completion time you want to inspect.");
        }
        seekVideo(seconds);
        status.textContent = "Viewing " + seconds.toFixed(3)
          + "s. M# and E# remain unchanged.";
      } catch (error) {
        status.textContent = error.message;
        document.getElementById("engine-check-seconds").focus();
      }
    }

    let segmentLoadingStartedAt = null;
    let segmentLoadingTimer = null;
    let regressionQueueTimer = null;

    function updateSegmentLoadingElapsed() {
      if (segmentLoadingStartedAt === null) return;
      const elapsed = Math.max(
        0,
        Math.floor((Date.now() - segmentLoadingStartedAt) / 1000)
      );
      document.getElementById("segment-loading-elapsed").textContent =
        "Elapsed: " + elapsed + "s";
    }

    function setSegmentLoading(
      loading,
      label = "",
      detail = "",
      elapsedSeconds = null
    ) {
      const overlay = document.getElementById("segment-loading-overlay");
      const closeButton = document.getElementById("segment-loading-close");
      const cancelButton = document.getElementById("segment-loading-cancel");
      overlay.hidden = !loading;
      document.body.setAttribute("aria-busy", String(loading));
      segmentSelect.disabled = loading;
      sourceSelect.disabled = loading;
      if (loading) {
        document.querySelector(".segment-loading-spinner").hidden = false;
        closeButton.hidden = true;
        cancelButton.hidden = !state?.activeConversation;
        if (segmentLoadingStartedAt === null) {
          segmentLoadingStartedAt = Date.now() -
            Math.max(0, Number(elapsedSeconds || 0)) * 1000;
        }
        if (segmentLoadingTimer === null) {
          segmentLoadingTimer = setInterval(
            updateSegmentLoadingElapsed,
            1000
          );
        }
        updateSegmentLoadingElapsed();
        document.getElementById("segment-loading-title").textContent =
          label ? label + "…" : "Loading segment…";
        document.getElementById("segment-loading-detail").textContent =
          detail || "Loading video, coordinates, and review state.";
      } else {
        cancelButton.hidden = true;
        clearInterval(segmentLoadingTimer);
        segmentLoadingTimer = null;
        segmentLoadingStartedAt = null;
      }
    }

    function finishSegmentLoading(label, detail) {
      const overlay = document.getElementById("segment-loading-overlay");
      overlay.hidden = false;
      document.body.setAttribute("aria-busy", "false");
      clearInterval(segmentLoadingTimer);
      segmentLoadingTimer = null;
      segmentLoadingStartedAt = null;
      document.querySelector(".segment-loading-spinner").hidden = true;
      document.getElementById("segment-loading-title").textContent = label;
      document.getElementById("segment-loading-detail").textContent = detail;
      document.getElementById("segment-loading-close").hidden = false;
      document.getElementById("segment-loading-cancel").hidden = true;
    }

    function completeSegmentLoading(label, detail) {
      finishSegmentLoading(label, detail);
      analysisModalMode = null;
      setSegmentLoading(false);
    }

    function innovationAnalysisMode(segment) {
      if (
        ["bac_coordinates", "player_detection", "player_tracking"]
          .includes(segment.stage)
        || segment.state === "evidence_ready"
      ) {
        return "evidence";
      }
      if (segment.stage === "events" || segment.state === "ready") {
        return "rules";
      }
      return analysisModalMode;
    }

    function innovationAnalysisDetail(segment, mode) {
      const timeLabel = segment.timeLabel || segment.key;
      if (mode === "rules") {
        const eventsStatus = segment.state === "ready"
          ? "Complete"
          : segment.state === "failed"
            ? "Failed"
            : "In progress";
        return [
          "Target: " + timeLabel,
          "Playable segment: Complete",
          "Frozen BAC coordinates: Complete",
          "YOLO player context: Complete",
          "Innovation rules engine: " + eventsStatus,
          segment.statusMessage || "Building football events."
        ].join("\\n");
      }
      const stageOrder = [
        "bac_coordinates",
        "player_detection",
        "player_tracking",
        "evidence_ready"
      ];
      const activeIndex = stageOrder.indexOf(segment.stage);
      const stageStatus = index => {
        if (segment.state === "failed" && index === activeIndex) return "Failed";
        if (segment.state === "evidence_ready" || index < activeIndex) {
          return "Complete";
        }
        return index === activeIndex ? "In progress" : "Waiting";
      };
      const detectionProgress = (
        segment.stage === "player_detection" && segment.expectedFrames
      )
        ? " — " + Number(segment.processedFrames || 0) + "/" +
          Number(segment.expectedFrames) + " sampled frames"
        : "";
      return [
        "Target: " + timeLabel,
        "Playable segment: Complete",
        "Frozen BAC coordinates: " + stageStatus(0),
        "YOLO player context: " + stageStatus(1) + detectionProgress,
        "Player tracking: " + stageStatus(2),
        segment.statusMessage || "Preparing Innovation evidence."
      ].join("\\n");
    }

    function syncInnovationAnalysisModal(segment) {
      if (reviewWorkflow.key !== "innovation") return;
      if (
        segment.stage === "events"
        || (segment.state === "ready" && analysisModalMode === "evidence")
      ) {
        analysisModalMode = "rules";
      }
      const active = ["processing", "detections_ready", "building"]
        .includes(segment.state);
      if (active) {
        analysisModalMode = innovationAnalysisMode(segment);
        setSegmentLoading(
          true,
          analysisModalMode === "rules"
            ? "Processing Innovation rules engine"
            : "Preparing BAC + player context",
          innovationAnalysisDetail(segment, analysisModalMode),
          segment.runProvenance?.elapsed_seconds
        );
        return;
      }
      if (analysisModalMode === "evidence" && segment.state === "evidence_ready") {
        completeSegmentLoading(
          "BAC + player context complete",
          innovationAnalysisDetail(segment, "evidence")
        );
      } else if (analysisModalMode === "rules" && segment.state === "ready") {
        completeSegmentLoading(
          "Innovation AI processing complete",
          innovationAnalysisDetail(segment, "rules")
        );
      } else if (analysisModalMode && segment.state === "failed") {
        finishSegmentLoading(
          "Innovation processing failed",
          innovationAnalysisDetail(segment, analysisModalMode)
        );
      }
    }

    async function cancelCopilotReview() {
      const buttons = [
        document.getElementById("segment-loading-cancel"),
        document.getElementById("cancel-copilot-review"),
        document.getElementById("cancel-engine-verification"),
        document.getElementById("cancel-manual-copilot-review")
      ];
      buttons.forEach(button => { button.disabled = true; });
      try {
        const response = await fetch("/api/cancel-review", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({segment: selectedSegmentKey()})
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not cancel Copilot review");
        }
        analysisModalMode = null;
        setSegmentLoading(false);
        await loadState();
        return true;
      } catch (error) {
        finishSegmentLoading("Could not cancel Copilot review", error.message);
        return false;
      } finally {
        buttons.forEach(button => { button.disabled = false; });
      }
    }

    document.getElementById("segment-loading-close").addEventListener(
      "click",
      () => {
        analysisModalMode = null;
        regressionDashboardOpen = false;
        clearTimeout(regressionDashboardCloseTimer);
        regressionDashboardCloseTimer = null;
        setSegmentLoading(false);
      }
    );
    document.getElementById("segment-loading-cancel").addEventListener(
      "click",
      cancelCopilotReview
    );
    document.getElementById("cancel-copilot-review").addEventListener(
      "click",
      cancelCopilotReview
    );
    document.querySelectorAll(
      "[name=engine-verification-decision]"
    ).forEach(input => {
      input.addEventListener("change", updateEngineVerificationActions);
    });
    document.getElementById("cancel-engine-verification").addEventListener(
      "click",
      cancelOrCloseEngineVerification
    );
    document.getElementById("confirm-engine-without-copilot").addEventListener(
      "click",
      confirmEngineWithoutCopilot
    );
    document.getElementById("ask-copilot-engine-review").addEventListener(
      "click",
      askCopilotFromEngineVerification
    );
    document.getElementById("engine-verification-modal").addEventListener(
      "cancel",
      event => {
        if (
          engineVerificationPending
          || state.activeDiscrepancyBatch?.kind === "engine"
          || state.activity?.state === "working"
        ) {
          event.preventDefault();
        }
      }
    );
    document.getElementById("engine-verification-modal").addEventListener(
      "close",
      () => {
        verificationModalEngineIndex = null;
      }
    );
    document.getElementById("accept-copilot-decision").addEventListener(
      "click",
      acceptCopilotDecision
    );
    document.getElementById("reject-copilot-decision").addEventListener(
      "click",
      rejectCopilotDecision
    );
    document.getElementById("cancel-copilot-decision").addEventListener(
      "click",
      closeCopilotDecisionModal
    );
    document.getElementById("copilot-decision-modal").addEventListener(
      "close",
      () => {
        decisionModalReviewIndex = null;
      }
    );
    document.getElementById("start-segment-work").addEventListener(
      "click",
      async () => {
        const detail = document.getElementById("coordination-detail");
        try {
          detail.textContent = "Acquiring editing lease…";
          await coordinationLeaseAction("acquire");
        } catch (error) {
          detail.textContent = error.message;
        }
      }
    );
    document.getElementById("stop-segment-work").addEventListener(
      "click",
      releaseCoordinationLease
    );
    document.getElementById("keep-segment-lease").addEventListener(
      "click",
      async () => {
        recordCoordinationActivity();
        await coordinationLeaseAction("heartbeat");
      }
    );
    document.getElementById("coordination-idle-warning").addEventListener(
      "close",
      event => {
        if (event.target.returnValue === "release") {
          releaseCoordinationLease();
        }
      }
    );
    ["pointerdown", "keydown", "touchstart"].forEach(eventName => {
      window.addEventListener(
        eventName,
        recordCoordinationActivity,
        {passive: true}
      );
    });
    window.addEventListener("pagehide", () => {
      if (!coordinationLeaseHeld()) return;
      navigator.sendBeacon(
        "/api/coordination/release",
        JSON.stringify({segment: state.segment.key})
      );
    });
    document.getElementById("select-passed-regressions").addEventListener(
      "click",
      () => {
        const published = state.segments.filter(segment => {
          const summary = state.sharedReviewStatus.find(
            candidate => candidate.segment === segment.key
          );
          return segment.validated && summary?.published;
        });
        const allSelected = published.every(segment =>
          selectedRegressionSegments.has(segment.key)
        );
        published.forEach(segment => {
          if (allSelected) selectedRegressionSegments.delete(segment.key);
          else selectedRegressionSegments.add(segment.key);
        });
        render();
      }
    );
    document.getElementById("run-selected-regressions").addEventListener(
      "click",
      () => {
        const selectedSegments = state.segments.filter(segment =>
          selectedRegressionSegments.has(segment.key)
          && state.regressionJobs?.[segment.key]?.status !== "running"
        );
        if (selectedSegments.length) {
          runPublishedSegmentRegressions(selectedSegments);
        }
      }
    );
    document.getElementById("view-regression-runs").addEventListener(
      "click",
      () => {
        const jobKeys = Object.keys(state.regressionJobs || {});
        if (!jobKeys.length) {
          document.getElementById("regression-batch-status").textContent =
            "No regression runs are available yet";
          return;
        }
        openRegressionDashboard(jobKeys);
      }
    );

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
        + path("scripts", reviewWorkflow.processorScript) + " "
        + segmentPath + " " + reviewWorkflow.processorArguments.join(" ");
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
      document.getElementById("review-audience").value = reviewAudience;
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
      if (
        reviewWorkflow.key === "innovation"
        && ["processing", "detections_ready", "building"].includes(status)
      ) {
        return {
          bac_coordinates: "Preparing BAC coordinates",
          player_detection: "Detecting player context",
          player_tracking: "Building player tracks",
          events: "Building events"
        }[segment?.stage] || "Innovation processing";
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

    function regressionStatusLabel(status) {
      return {
        passed: "Passed",
        failed: "Current engine differs",
        stale: "Needs rerun",
        not_run: "Not run",
        unavailable: "Unavailable"
      }[status] || String(status || "not_run").replaceAll("_", " ");
    }

    function regressionJobLabel(job, fallback) {
      if (!job || job.status === "not_started") return fallback;
      if (
        job.status === "passed"
        && job.changeKind === "metadata_only"
      ) {
        return "Passed";
      }
      if (
        job.status === "mismatch"
        && job.changeKind === "metadata_only"
      ) {
        return "Metadata-only mismatch";
      }
      return {
        running: "Regression running",
        passed: "Regression passed",
        mismatch: "Regression mismatch",
        failed: "Regression failed"
      }[job.status] || fallback;
    }

    function renderRegressionDashboard() {
      if (!regressionDashboardOpen) return;
      const jobs = state.regressionJobs || {};
      const segmentsByKey = new Map(
        state.segments.map(segment => [segment.key, segment])
      );
      const batchJobs = [...activeRegressionBatch].map(segmentKey => ({
        segment: segmentsByKey.get(segmentKey),
        job: jobs[segmentKey]
      }));
      const running = batchJobs.some(
        ({job}) => !job || job.status === "running"
      );
      const detail = batchJobs.map(({segment, job}) => {
        const label = segment?.timeLabel || job?.segment || "Segment";
        if (!job) return label + " — Queued";
        const activeStep = (job.steps || []).find(
          step => step.status === "running"
        );
        const status = regressionJobLabel(job, job.status);
        return label + " — " + status
          + (activeStep ? ": " + activeStep.label : "")
          + (
            !activeStep && job.message
              ? "\\n  " + job.message
              : ""
          );
      }).join("\\n");
      document.getElementById("segment-loading-title").textContent =
        running
          ? "Running " + batchJobs.length + " segment regression"
            + (batchJobs.length === 1 ? "" : "s") + "…"
          : "Regression batch complete";
      document.getElementById("segment-loading-detail").textContent =
        detail || "Preparing regression jobs.";
      document.querySelector(".segment-loading-spinner").hidden = !running;
      if (running) {
        clearTimeout(regressionDashboardCloseTimer);
        regressionDashboardCloseTimer = null;
        return;
      }
      clearInterval(segmentLoadingTimer);
      segmentLoadingTimer = null;
      segmentLoadingStartedAt = null;
      if (regressionDashboardCloseTimer === null) {
        regressionDashboardCloseTimer = setTimeout(() => {
          regressionDashboardOpen = false;
          regressionDashboardCloseTimer = null;
          activeRegressionBatch.clear();
          setSegmentLoading(false);
        }, 1500);
      }
    }

    function openRegressionDashboard(segmentKeys) {
      activeRegressionBatch = new Set(segmentKeys);
      regressionDashboardOpen = true;
      clearTimeout(regressionDashboardCloseTimer);
      regressionDashboardCloseTimer = null;
      setSegmentLoading(
        true,
        "Starting regression batch",
        "Queuing selected published segments."
      );
      renderRegressionDashboard();
    }

    function syncRegressionQueuePolling() {
      const running = Object.values(state.regressionJobs || {}).some(
        job => job.status === "running"
      );
      if (running && regressionQueueTimer === null) {
        regressionQueueTimer = setInterval(() => loadState(false), 1000);
      } else if (!running && regressionQueueTimer !== null) {
        clearInterval(regressionQueueTimer);
        regressionQueueTimer = null;
      }
      renderRegressionDashboard();
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

    function coordinationLeaseHeld() {
      return Boolean(state?.coordination?.lease?.heldByCurrent);
    }

    function copilotSessionConnected() {
      return Boolean(state?.copilotSession?.connected);
    }

    function coordinationMutationAllowed() {
      if (!copilotSessionConnected()) return false;
      const coordination = state?.coordination;
      return !coordination
        || coordination.mode === "disabled"
        || (
          coordination.mode === "available"
          && (
            !coordination.lease?.active
            || coordinationLeaseHeld()
          )
        );
    }

    function renderCopilotSessionStatus() {
      const connection = state?.copilotSession || {
        connected: false,
        message: "Copilot project session status is unavailable."
      };
      const panel = document.getElementById("copilot-session-status");
      panel.hidden = connection.connected;
      document.getElementById("copilot-session-detail").textContent =
        connection.message
        || "Open this review from the Copilot project session for this repository.";
    }

    function renderCoordinationStatus() {
      const coordination = state.coordination || {mode: "disabled"};
      const panel = document.getElementById("coordination-status");
      const title = document.getElementById("coordination-title");
      const detail = document.getElementById("coordination-detail");
      const start = document.getElementById("start-segment-work");
      const stop = document.getElementById("stop-segment-work");
      panel.hidden = coordination.mode === "disabled";
      if (panel.hidden) return;
      panel.classList.toggle(
        "read-only",
        coordination.mode !== "available" || !coordinationLeaseHeld()
      );
      panel.classList.toggle(
        "locked",
        Boolean(coordination.lease?.active && !coordinationLeaseHeld())
      );
      title.textContent = coordination.mode === "unavailable"
        ? "Shared coordination unavailable"
        : coordinationLeaseHeld()
          ? "You are working on this segment"
          : coordination.lease?.active
            ? "Segment locked"
            : "Shared coordination";
      detail.textContent = coordination.mode === "unavailable"
        ? coordination.message
          || "PostgreSQL is unavailable. Shared changes are read-only."
        : coordinationLeaseHeld()
          ? (
              (coordination.identity?.displayName || "Current developer")
              + " · "
              + (coordination.identity?.machineLabel || "this machine")
              + " · heartbeat active"
            )
          : coordination.lease?.active
            ? (
                "In use by "
                + (coordination.lease.holderName || "another developer")
                + " · "
                + (coordination.lease.machineLabel || "another machine")
                + (
                  coordination.lease.stage
                    ? " · " + coordination.lease.stage
                    : ""
                )
              )
            : "Available · start working before changing shared review state.";
      start.hidden = coordinationLeaseHeld();
      start.disabled = (
        !copilotSessionConnected()
        ||
        coordination.mode !== "available"
        || Boolean(coordination.lease?.active)
      );
      stop.hidden = !coordinationLeaseHeld();
    }

    function applyCoordinationLock() {
      if (coordinationMutationAllowed()) return;
      const viewerControls = [
        "#review-audience",
        "#source-select",
        "#segment-select",
        "#previous-event",
        "#next-event",
        "#previous-frame",
        "#next-frame",
        "#timeline",
        "#playback-speed",
        "#toggle-event-panel",
        "#move-event-panel",
        "#show-ball-frames",
        "#zoom-action",
        "#zoom-out",
        "#zoom-in",
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
        "#segment-loading-close",
        "#segment-loading-cancel",
        "[data-view-mode]",
        ".comparison-event",
        ".compact-engine-spot",
        "#show-bac-coordinate",
        "#cancel-engine-verification",
        "#close-manual-engine-review",
        "#cancel-manual-copilot-review",
        "[name=engine-verification-decision]",
        "#engine-check-seconds",
        "#seek-engine-check-time",
        "#validate-engine-reference",
        ".ball-frame-open",
        "#ball-frame-filter",
        "#workflow-adapter",
        "#refresh-copilot-session",
        "#start-segment-work",
        "#view-regression-runs"
      ].join(",");
      document.querySelectorAll("button, input, textarea, select").forEach(
        control => {
          if (control.matches(viewerControls)) return;
          control.disabled = true;
          control.title = !copilotSessionConnected()
            ? "Connect this review to its Copilot project session before making changes."
            : state.coordination?.mode === "unavailable"
              ? "Shared coordination is unavailable; changes are read-only."
              : "Start working on this segment before making changes.";
        }
      );
    }

    async function coordinationLeaseAction(
      action,
      {userActivity = true} = {}
    ) {
      const response = await fetch("/api/coordination/" + action, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({segment: state.segment.key})
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Coordination request failed");
      }
      if (userActivity) coordinationLastActivityAt = Date.now();
      await loadState();
      return payload;
    }

    async function releaseCoordinationLease() {
      if (!coordinationLeaseHeld()) return;
      try {
        await coordinationLeaseAction("release", {userActivity: false});
      } catch (error) {
        document.getElementById("coordination-detail").textContent =
          "Could not release editing lease: " + error.message;
      }
    }

    function recordCoordinationActivity() {
      coordinationLastActivityAt = Date.now();
      const dialog = document.getElementById("coordination-idle-warning");
      if (dialog.open) dialog.close();
    }

    function syncCoordinationTimers() {
      const leaseKey = coordinationLeaseHeld()
        ? reviewWorkflow.key + ":" + state.segment.key
        : null;
      if (leaseKey === coordinationTimerLeaseKey) return;
      clearInterval(coordinationHeartbeatTimer);
      clearInterval(coordinationIdleTimer);
      coordinationHeartbeatTimer = null;
      coordinationIdleTimer = null;
      coordinationTimerLeaseKey = leaseKey;
      if (!leaseKey) return;
      coordinationHeartbeatTimer = setInterval(() => {
        coordinationLeaseAction(
          "heartbeat",
          {userActivity: false}
        ).catch(() => {
          loadState(false).catch(() => {});
        });
      }, 30000);
      coordinationIdleTimer = setInterval(() => {
        const idleSeconds = (
          Date.now() - coordinationLastActivityAt
        ) / 1000;
        const dialog = document.getElementById(
          "coordination-idle-warning"
        );
        if (idleSeconds >= 1200) {
          dialog.close();
          releaseCoordinationLease();
        } else if (idleSeconds >= 1080 && !dialog.open) {
          dialog.showModal();
        }
      }, 5000);
    }

    function regressionCandidateReviewActive() {
      return state.engineDisplayMode === "regression_candidate";
    }

    function applyPassedSegmentLock() {
      if (!referenceLocked()) return;
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
        "#move-event-panel",
        "#show-ball-frames",
        "#zoom-action",
        "#zoom-out",
        "#zoom-in",
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
        "#segment-loading-close",
        "#segment-loading-cancel",
        "[data-view-mode]",
        ".comparison-event",
        ".compact-engine-spot",
        "#show-bac-coordinate",
        "#cancel-engine-verification",
        "#close-manual-engine-review",
        "#cancel-manual-copilot-review",
        "[name=engine-verification-decision]",
        "#engine-check-seconds",
        "#seek-engine-check-time",
        "#confirm-engine-without-copilot",
        "#ask-copilot-engine-review",
        ".ball-frame-open",
        ".ball-frame-flag",
        ".shared-review-table button",
        ".segment-replay-modal button",
        "#ball-frame-filter",
        "#workflow-adapter",
        ...(regressionCandidateReviewActive()
          ? [
              ".comparison-action",
              "#send-clip-plan",
              "#send-clip-autopilot",
              "#fullscreen-send-message",
              "#fullscreen-primary-action",
              "#fullscreen-message",
              "[name=engine-user-verdict]"
            ]
          : []),
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
      const running = segmentRunActive();
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
      prepareEvidenceButton.hidden =
        !reviewWorkflow.evidencePreparationEnabled || !selectedVideoPrepared;
      prepareButton.disabled = running || !segment.preparationSupported;
      prepareEvidenceButton.disabled =
        running
        || !segment.evidencePreparationSupported
        || referenceLocked();
      prepareEvidenceButton.textContent = segment.evidenceReady
        ? "Rebuild BAC + player context"
        : "Prepare BAC + player context";
      processButton.disabled =
        running || !segment.processingSupported || referenceLocked();
      processButton.textContent = referenceLocked()
        ? "Passed Segment Locked"
        : reviewWorkflow.evidencePreparationEnabled
          ? segment.state === "ready"
            ? "Rerun AI"
            : "Process AI"
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
      } else if (segment.state === "evidence_ready") {
        segmentRunStatus.textContent =
          "Frozen BAC coordinates and YOLO player context are ready. "
          + "No events exist yet; process the AI rules engine when ready.";
      } else if (segment.state === "processing") {
        if (reviewWorkflow.key === "innovation") {
          segmentRunStatus.textContent =
            segment.statusMessage || "Starting Innovation processing.";
        } else {
          const provenance = segment.runProvenance;
          const elapsed = Number(provenance?.elapsed_seconds || 0);
          segmentRunStatus.textContent = (
            segment.expectedFrames
              ? "Step 1 of 6 — Detecting raw-video frames: " +
                segment.processedFrames + "/" +
                segment.expectedFrames + " sampled frames"
              : "Step 1 of 6 — Detecting raw-video frames locally"
          ) + (elapsed ? " · " + elapsed.toFixed(1) + "s elapsed" : "") +
            ". " + reviewWorkflow.detectionMessage;
        }
      } else if (segment.state === "detections_ready") {
        segmentRunStatus.textContent =
          "Step 1 of 6 complete — detections are ready. " +
          "Next: build ball coordinates.";
      } else if (segment.state === "building") {
        if (reviewWorkflow.key === "innovation") {
          segmentRunStatus.textContent = (
            segment.stage === "player_detection" && segment.expectedFrames
              ? "Preparing YOLO player context: " +
                Number(segment.processedFrames || 0) + "/" +
                Number(segment.expectedFrames) + " sampled frames. "
              : ""
          ) + (
            segment.statusMessage || "Innovation processing is still running."
          );
          applySegmentProcessingLock();
          syncInnovationAnalysisModal(segment);
          scheduleStatusRefresh();
          return;
        }
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
        segmentRunStatus.textContent = (
          reviewWorkflow.key === "innovation"
          && segment.evidencePreparationSupported
        )
          ? "Video preparation complete. No football events exist. "
            + "Next: prepare frozen BAC coordinates and YOLO player context."
          : "Calibrate this camera first. AI remains disabled until its own "
            + "saved calibration is ready.";
      } else {
        segmentRunStatus.textContent = reviewWorkflow.key === "innovation"
          ? "Evidence preparation complete. No football events exist. "
            + "Run the Innovation rules engine when ready."
          : "Preparation complete. No AI has run. Next: click Start AI.";
      }
      applySegmentProcessingLock();
      syncInnovationAnalysisModal(segment);
      scheduleStatusRefresh();
    }

    function renderAiGate() {
      const ready = (
        state.segment.validated
        || state.segment.validationStatus === "in_review"
        || (
          reviewWorkflow.key === "innovation"
          && state.segment.state === "evidence_ready"
        )
        || (
          reviewWorkflow.coordinateReviewEnabled
            ? state.coordinateReview?.status === "finalized"
            : state.segment.state === "ready"
        )
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
      const summaries = new Map(
        (state.sharedReviewStatus || []).map(summary => [
          summary.segment,
          summary
        ])
      );
      const selectedSummary = summaries.get(selected.key) || {};
      const selectionChanged = renderedSegmentKey !== selected.key;
      if (selectionChanged && referenceLocked()) {
        document.getElementById("shared-review-panel").open = true;
      }
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
        const segmentSummary = summaries.get(segment.key) || {};
        const labels = [
          segment.timeLabel,
          segmentSummary.regression === "failed"
            ? "Passed · Current rules differ"
            : statusLabel(segment.validationStatus, segment),
          segment.coordinationLease?.active
            ? segment.coordinationLease.heldByCurrent
              ? "Locked by you"
              : "Locked by "
                + (segment.coordinationLease.holderName || "another developer")
            : "",
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
        selectedSummary.regression === "failed"
          ? "regression-failed"
          : state.coordinateReview?.status === "verified"
          ? "coordinate-verified"
          : ballCoordinatesNeedReview(selected)
          ? "coordinates-review"
          : selected.validationStatus
      );
      badge.textContent = selectedSummary.regression === "failed"
        ? "Passed · Current rules differ"
        : statusLabel(selected.validationStatus, selected);
      document.getElementById("tracker-version").textContent =
        selected.coordinateMode === "frozen_bac"
          ? "BAC coordinates: frozen"
          : "Ball tracker: " + trackerIteration(selected) + " · " +
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
      const regressionBatchActions =
        document.getElementById("regression-batch-actions");
      regressionBatchActions.hidden = reviewWorkflow.key !== "innovation";
      const selectableRegressionSegments = state.segments.filter(segment => {
        const summary = summaries.get(segment.key) || {};
        return segment.validated && summary.published;
      });
      const selectableKeys = new Set(
        selectableRegressionSegments.map(segment => segment.key)
      );
      [...selectedRegressionSegments].forEach(segmentKey => {
        if (!selectableKeys.has(segmentKey)) {
          selectedRegressionSegments.delete(segmentKey);
        }
      });
      const runSelectedButton =
        document.getElementById("run-selected-regressions");
      runSelectedButton.textContent =
        "Run selected (" + selectedRegressionSegments.size + ")";
      runSelectedButton.disabled = selectedRegressionSegments.size === 0;
      const runningRegressionCount = Object.values(
        state.regressionJobs || {}
      ).filter(job => job.status === "running").length;
      document.getElementById("regression-batch-status").textContent =
        runningRegressionCount
          ? runningRegressionCount + " regression"
            + (runningRegressionCount === 1 ? "" : "s")
            + " running in parallel"
          : "No regressions running";
      document.getElementById("shared-review-status").replaceChildren(
        ...state.segments.map(segment => {
          const summary = summaries.get(segment.key) || {};
          const regressionJob = state.regressionJobs?.[segment.key] || null;
          const regressionRunning = regressionJob?.status === "running";
          const reviewed = Number(summary.reviewed || 0);
          const proposalCount = Number(summary.proposalCount || 0);
          const matched = Number(summary.matched || 0);
          const values = [
            segment.datasetName + " · " + segment.timeLabel,
            reviewWorkflow.key === "innovation" && proposalCount
              ? matched + "/" + proposalCount + " M# matched · "
                + Number(summary.accepted || 0) + " accepted · "
                + Number(summary.rejected || 0) + " rejected"
              : proposalCount
              ? reviewed + "/" + proposalCount + " reviewed · "
                + Number(summary.accepted || 0) + " accepted · "
                + Number(summary.rejected || 0) + " rejected"
              : reviewed ? reviewed + " reviewed" : "Not started",
            regressionJobLabel(
              regressionJob,
              summary.regressionChangeKind === "metadata_only"
                ? "Passed"
                : regressionStatusLabel(summary.regression)
            ),
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
          const selectCell = document.createElement("td");
          if (
            reviewWorkflow.key === "innovation"
            && segment.validated
            && summary.published
          ) {
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.className = "regression-select";
            checkbox.checked = selectedRegressionSegments.has(segment.key);
            checkbox.disabled = regressionRunning;
            checkbox.setAttribute(
              "aria-label",
              "Select regression for " + segment.timeLabel
            );
            checkbox.addEventListener("change", () => {
              if (checkbox.checked) {
                selectedRegressionSegments.add(segment.key);
              } else {
                selectedRegressionSegments.delete(segment.key);
              }
              render();
            });
            selectCell.append(checkbox);
          }
          row.append(selectCell);
          values.forEach((value, columnIndex) => {
            const cell = document.createElement("td");
            const text = document.createElement("span");
            text.textContent = value;
            cell.append(text);
            if (
              columnIndex === 0
              && segment.validated
              && summary.published
            ) {
              const replay = (state.replaySegments || []).find(
                candidate => candidate.key === segment.key
              );
              if (replay) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "segment-replay-action";
                button.textContent = "Replay";
                button.setAttribute(
                  "aria-label",
                  "Replay " + segment.timeLabel + " from cached engine output"
                );
                button.addEventListener("click", () => {
                  openSegmentReplay(segment.key);
                });
                cell.append(button);
              }
            }
            if (
              columnIndex === 2
              && reviewWorkflow.key === "innovation"
              && segment.validated
              && summary.published
            ) {
              const button = document.createElement("button");
              button.type = "button";
              button.className = "regression-action";
              button.textContent = regressionRunning
                ? "Running…"
                : "Run regression";
              button.disabled = regressionRunning;
              button.setAttribute(
                "aria-label",
                regressionRunning
                  ? "Regression running for " + segment.timeLabel
                  : "Run regression for " + segment.timeLabel
              );
              if (regressionJob?.message) {
                button.title = regressionJob.message;
              }
              button.addEventListener("click", () => {
                runPublishedSegmentRegression(segment);
              });
              cell.append(button);
            }
            row.append(cell);
          });
          row.classList.toggle("selected", segment.key === selected.key);
          row.classList.toggle(
            "regression-diff",
            summary.regression === "failed"
          );
          return row;
        })
      );
      const regressionQueue =
        document.getElementById("regression-review-queue");
      const workflowRegression = state.workflowRegression;
      const currentlyFailedSegments = new Set(
        (state.sharedReviewStatus || [])
          .filter(result => result.regression === "failed")
          .map(result => result.segment)
      );
      const workflowFailures = (
        workflowRegression?.segmentResults || []
      ).filter(result =>
        !result.passed && currentlyFailedSegments.has(result.segment)
      );
      const failedBySegment = new Map(
        workflowFailures.map(result => [result.segment, result])
      );
      (state.sharedReviewStatus || [])
        .filter(result => result.regression === "failed")
        .forEach(result => {
          if (failedBySegment.has(result.segment)) {
            const existing = failedBySegment.get(result.segment);
            existing.summary = result.regressionSummary || existing.summary;
            existing.changeKind =
              result.regressionChangeKind || existing.changeKind || null;
            return;
          }
          const segment = (state.segments || []).find(
            candidate => candidate.key === result.segment
          );
          failedBySegment.set(result.segment, {
            segment: result.segment,
            timeLabel: segment?.timeLabel || result.segment,
            summary: result.regressionSummary
              || "Current engine output differs from the published output.",
            changeKind: result.regressionChangeKind || null,
          });
        });
      const failedRegressions = [...failedBySegment.values()];
      const workflowHasNonSegmentFailure = Boolean(
        workflowRegression
        && !workflowRegression.passed
        && !(workflowRegression.segmentResults || []).some(
          result => !result.passed
        )
      );
      const metadataOnlyFailures = (
        failedRegressions.length > 0
        && failedRegressions.every(
          result => result.changeKind === "metadata_only"
        )
      );
      regressionQueue.hidden = !(
        reviewWorkflow.key === "innovation"
        && (workflowHasNonSegmentFailure || failedRegressions.length)
      );
      if (!regressionQueue.hidden) {
        document.getElementById("regression-review-summary").textContent =
          metadataOnlyFailures
            ? "No events or match-state behavior changed. The exact published "
              + "artifacts remain blocked because the current output adds "
              + "schema v2 football-law provenance metadata."
            : "The candidate engine is blocked. Review these segments and "
              + "refine the general rule; the published references remain "
              + "unchanged.";
        document.getElementById("regression-review-failures").replaceChildren(
          ...failedRegressions.map(result => {
            const item = document.createElement("li");
            item.textContent = (
              (result.timeLabel || result.segment)
              + ": "
              + result.summary
            );
            return item;
          })
        );
      }
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
      renderRunControls();
      renderAiGate();
      syncRegressionQueuePolling();
    }

    async function runPublishedSegmentRegression(segment) {
      return runPublishedSegmentRegressions([segment]);
    }

    async function runPublishedSegmentRegressions(segments) {
      const segmentKeys = segments.map(segment => segment.key);
      openRegressionDashboard(segmentKeys);
      try {
        const results = await Promise.all(segments.map(async segment => {
          const response = await fetch("/api/innovation/regression", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({segment: segment.key})
          });
          const result = await response.json();
          if (!response.ok) {
            throw new Error(
              segment.timeLabel + ": "
                + (result.error || "Regression rerun failed")
            );
          }
          return result;
        }));
        await loadState();
        syncRegressionQueuePolling();
        return results;
      } catch (error) {
        document.getElementById("composer-status").textContent =
          "Regression could not start: " + error.message;
        await loadState();
        renderRegressionDashboard();
        return [];
      }
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
      autopilotButton.disabled = reviewBusy || (
        referenceLocked() && !regressionCandidateReviewActive()
      );
      const userClaim = document.getElementById("engine-user-claim");
      userClaim.hidden = !selectedEngine;
      if (selectedEngine) {
        const savedVerdict = selectedEngine.review?.userVerdict
          || (selectedEngine.review?.userClaimedCorrect ? "correct" : "");
        document.querySelectorAll("[name=engine-user-verdict]").forEach(
          input => {
            input.checked = input.value === savedVerdict;
          }
        );
      }
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
      if (state?.segment?.coordinateMode === "frozen_bac") {
        return "Frozen BAC";
      }
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

    function reviewerCoordinateChangeStatus(frame, observation) {
      if (!observation?.approved) return "base";
      const applied =
        state.reviewerCoordinateLayer?.corrections?.[String(frame)];
      if (!applied || applied.outcome !== observation.decision) {
        return "pending";
      }
      if (observation.decision === "undefined") return "applied";
      return (
        Number(applied.x) === Number(observation.x)
        && Number(applied.y) === Number(observation.y)
      ) ? "applied" : "pending";
    }

    function loadBallFrameFlags() {
      if (state?.segment?.coordinateMode === "frozen_bac") {
        selectedCoordinateBatchId = "all";
        ballCoordinateObservations = {
          ...(state.trajectoryAudit?.observations || {})
        };
        flaggedBallFrames = new Set(
          Object.keys(ballCoordinateObservations)
            .map(Number)
            .filter(Number.isInteger)
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
      if (selectedCoordinateBatchId === "all") {
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
        "tests_completed",
        "rerun_started"
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

    function saveBallFrameFlags() {
      const save = ballFrameSaveQueue.catch(() => {}).then(async () => {
        localStorage.setItem(
          ballFrameFlagStorageKey(),
          JSON.stringify([...flaggedBallFrames].sort((a, b) => a - b))
        );
        localStorage.setItem(
          ballCoordinateObservationStorageKey(),
          JSON.stringify(ballCoordinateObservations)
        );
        if (state?.segment?.coordinateMode === "frozen_bac") {
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
              result.error || "Could not save reviewer coordinate correction"
            );
          }
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
          throw new Error(
            result.error || "Could not save coordinate decisions"
          );
        }
      });
      ballFrameSaveQueue = save;
      return save;
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
      if (selectedCoordinateBatchId === "all") {
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
      marker.hidden = !hasCoordinate || !showEngineBallMarker;
      marker.style.display = marker.hidden ? "none" : "";
      crosshair.hidden = true;
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
        showYoloBallMarkers
          ? ballTrack.yoloCandidates?.[String(frame)] || []
          : []
      )) {
        if (
          showEngineBallMarker
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
      marker.hidden = !hasDisplayedCoordinate || !showEngineBallMarker;
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
      crosshair.hidden = true;
      crosshair.style.display = crosshair.hidden ? "none" : "";
      yoloMarkers.replaceChildren();
      const displayedYoloCandidates = (
        showYoloBallMarkers
          ? ballTrack?.yoloCandidates?.[String(selectedRawBallFrame)] || []
          : []
      );
      for (const [candidateIndex, candidate] of (
        displayedYoloCandidates.entries()
      )) {
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
        const label = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "text"
        );
        label.setAttribute("x", String(candidate.x + 18));
        label.setAttribute("y", String(candidate.y - 18));
        label.setAttribute("fill", "#79c0ff");
        label.setAttribute("font-size", "32");
        label.setAttribute("font-weight", "700");
        label.textContent = String(candidateIndex + 1);
        yoloMarkers.append(circle, label);
      }
      const observation = ballCoordinateObservations[
        String(selectedBallTargetFrame)
      ];
      const selectedBatch = selectedCoordinateBatch();
      const activeRoundView =
        selectedCoordinateBatchId !== "all"
        && document.getElementById("ball-frame-filter").value === "flagged"
        && selectedBatch?.status === "ready";
      const reviewerCorrectionView = Boolean(
        reviewWorkflow.reviewerCorrectedDemoLayer
        && state?.segment?.coordinateMode === "frozen_bac"
      );
      const inspectionOnly = !activeRoundView && !reviewerCorrectionView;
      const yoloCandidateActions = document.getElementById(
        "yolo-candidate-actions"
      );
      const selectableYoloCandidates =
        selectedRawBallFrame === selectedBallTargetFrame
          ? displayedYoloCandidates.map((candidate, candidateIndex) => ({
              candidate,
              candidateIndex
            }))
          : [];
      yoloCandidateActions.hidden =
        inspectionOnly || !selectableYoloCandidates.length;
      yoloCandidateActions.replaceChildren(
        ...selectableYoloCandidates.map(({candidate, candidateIndex}) => {
          const button = document.createElement("button");
          button.type = "button";
          button.textContent =
            "YOLO candidate " + (candidateIndex + 1) + " is correct";
          button.title = "Blue candidate " + (candidateIndex + 1)
            + " at (" + candidate.x.toFixed(1) + ", "
            + candidate.y.toFixed(1) + ") · confidence "
            + (Number(candidate.confidence || 0) * 100).toFixed(1) + "%";
          button.addEventListener("click", () => {
            void recordBallCoordinateDecision(
              {
                decision: "yolo_candidate",
                x: candidate.x,
                y: candidate.y,
                candidateIndex,
                confidence: Number(candidate.confidence || 0)
              },
              "confirmed YOLO candidate " + (candidateIndex + 1)
            ).catch(error => {
              document.getElementById(
                "ball-coordinate-review-status"
              ).textContent = error.message;
            });
          });
          return button;
        })
      );
      userMarker.hidden =
        selectedRawBallFrame !== selectedBallTargetFrame
        || !["specified", "yolo_candidate"].includes(observation?.decision);
      userMarker.style.display = userMarker.hidden ? "none" : "";
      if (["specified", "yolo_candidate"].includes(observation?.decision)) {
        userMarker.setAttribute("cx", String(observation.x));
        userMarker.setAttribute("cy", String(observation.y));
      }
      document.getElementById("ball-frame-review-target").textContent =
        (
          state?.segment?.coordinateMode === "frozen_bac"
            ? "Inspect frame "
            : "Review frame "
        ) + selectedBallTargetFrame;
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
      const currentDecision = document.getElementById(
        "ball-frame-current-decision"
      );
      const resolutionStatus = document.getElementById(
        "ball-frame-resolution-status"
      );
      document.getElementById("ball-frame-modal-mode").textContent =
        inspectionOnly
          ? "Inspection only · red ring: engine · blue rings: YOLO"
          : "Coordinate review · red ring: engine · blue rings: YOLO";
      document.getElementById("ball-frame-overlay-controls").hidden = false;
      const frozenBac =
        state?.segment?.coordinateMode === "frozen_bac";
      const reviewerChangeStatus = reviewerCoordinateChangeStatus(
        selectedBallTargetFrame,
        observation
      );
      const decisionLabel =
        observation?.decision === "agree"
          ? "agreed with the current coordinate"
          : observation?.decision === "needs_more_checking"
            ? "marked as needing more checking"
          : observation?.decision === "undefined"
            ? "ball marked undefined / not visible"
            : observation?.decision === "yolo_candidate"
              ? "confirmed a visible YOLO candidate"
            : observation?.decision === "specified"
              ? "custom coordinate confirmed"
              : frozenBac
                ? "BAC imported coordinate confirmed"
                : "";
      const currentDecisionLabel =
        reviewerChangeStatus === "pending"
          ? "User changed · pending batch apply"
          : reviewerChangeStatus === "applied"
            ? "✓ User change applied"
        : observation?.decision === "agree"
          ? "✓ Agreed with coordinate"
          : observation?.decision === "needs_more_checking"
            ? "Needs more checking"
            : observation?.decision === "undefined"
              ? "Ball undefined / not visible"
              : observation?.decision === "yolo_candidate"
                ? "✓ YOLO candidate confirmed"
              : observation?.decision === "specified" && observation.approved
                ? "✓ Custom coordinate confirmed"
                : observation?.decision === "specified"
                  ? "Custom coordinate awaiting confirmation"
                  : frozenBac
                    ? "✓ BAC imported · confirmed"
                    : "Not reviewed yet";
      currentDecision.textContent =
        (selectedBatch?.status === "done"
          ? "Your previous decision: "
          : "Current decision: ") + currentDecisionLabel;
      currentDecision.className =
        "coordinate-review-result "
        + (
          reviewerChangeStatus === "applied"
          || frozenBac && reviewerChangeStatus === "base"
          || observation?.decision === "agree"
          || observation?.decision === "yolo_candidate"
          || (
            observation?.decision === "specified"
            && observation.approved
          )
            ? "confirmed"
            : observation?.decision === "undefined"
              ? "undefined"
            : ["needs_more_checking", "specified"].includes(
                observation?.decision
              )
              ? "checking"
              : "pending"
        );
      const frameResult =
        selectedBatch?.frameResults?.[String(selectedBallTargetFrame)]?.status;
      const carryForward =
        selectedBatch?.carryForward?.[String(selectedBallTargetFrame)];
      const resolution = {
        fixed: ["Resolved by rerun", "confirmed"],
        unresolved: ["Still unresolved", "checking"],
        regressed: ["Regression after rerun", "undefined"],
        unchanged_direct: ["Still direct", "confirmed"]
      }[frameResult];
      resolutionStatus.hidden = !resolution && !carryForward;
      resolutionStatus.textContent = carryForward
        ? "Returned from Round " + carryForward.sourceRound + ": "
          + carryForward.reason
        : resolution
          ? "Result: " + resolution[0]
          : "";
      resolutionStatus.className =
        "coordinate-review-result "
        + (carryForward ? "checking" : resolution?.[1] || "pending");
      if (reviewerCorrectionView) {
        decisionStatus.textContent =
          "Frozen BAC remains unchanged. Your confirmed coordinate is saved "
          + "in the separate reviewer-corrected Innovation demo layer.";
      } else if (inspectionOnly) {
        decisionStatus.textContent =
          selectedBatch?.status === "done"
            ? "Closed Round " + selectedBatch.number
              + ". Decisions cannot be changed."
            : "Inspection view. Open Latest Round "
              + (selectedBatch?.number || "") + " to record decisions.";
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
                : observation?.decision === "yolo_candidate"
                  ? " · your decision: YOLO candidate "
                    + (Number(observation.candidateIndex) + 1)
                    + " visibly correct at (" + observation.x.toFixed(1)
                    + ", " + observation.y.toFixed(1) + ")"
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
      const reviewFrames = flaggedBallFrames.size
        ? (ballTrack.states || []).filter(
            candidate => flaggedBallFrames.has(candidate.frame)
          )
        : (ballTrack.states || []).filter(candidate => !candidate.direct);
      const reviewIndex = reviewFrames.findIndex(
        candidate => candidate.frame === selectedBallTargetFrame
      );
      document.getElementById("previous-ball-review-frame").disabled =
        reviewIndex <= 0;
      document.getElementById("next-ball-review-frame").disabled =
        reviewIndex < 0 || reviewIndex === reviewFrames.length - 1;
      document.getElementById("ball-review-navigation").hidden =
        selectedCoordinateBatchId === "all";
      document.getElementById("previous-ball-review-frame").textContent =
        inspectionOnly ? "← Previous reviewed frame" : "← Previous review";
      document.getElementById("next-ball-review-frame").textContent =
        inspectionOnly ? "Next reviewed frame →" : "Next review →";
      [
        "coordinate-decision-guide",
        "yolo-candidate-actions",
        "target-ball-frame",
        "mark-ball-location",
        "agree-ball-coordinate",
        "undefined-ball-coordinate",
        "needs-more-checking",
        "approve-ball-location",
        "undo-ball-coordinate-decision"
      ].forEach(id => {
        document.getElementById(id).hidden = inspectionOnly;
      });
      document.getElementById("target-ball-frame").disabled =
        selectedRawBallFrame === selectedBallTargetFrame;
      document.getElementById("mark-ball-location").disabled =
        selectedRawBallFrame !== selectedBallTargetFrame
        || (
          state.coordinateReview?.status === "finalized"
          && !reviewerCorrectionView
        )
        || selectedCoordinateBatch()?.status === "done";
      document.getElementById("agree-ball-coordinate").disabled =
        selectedRawBallFrame !== selectedBallTargetFrame
        || !Number.isFinite(point.x)
        || !Number.isFinite(point.y)
        || (
          state.coordinateReview?.status === "finalized"
          && !reviewerCorrectionView
        )
        || selectedCoordinateBatch()?.status === "done";
      document.getElementById("undefined-ball-coordinate").disabled =
        selectedRawBallFrame !== selectedBallTargetFrame
        || (
          state.coordinateReview?.status === "finalized"
          && !reviewerCorrectionView
        )
        || selectedCoordinateBatch()?.status === "done";
      document.getElementById("needs-more-checking").disabled =
        selectedRawBallFrame !== selectedBallTargetFrame
        || (
          state.coordinateReview?.status === "finalized"
          && !reviewerCorrectionView
        )
        || selectedCoordinateBatch()?.status === "done";
      document.getElementById("approve-ball-location").disabled =
        selectedRawBallFrame !== selectedBallTargetFrame
        || observation?.decision !== "specified"
        || observation.approved
        || (
          state.coordinateReview?.status === "finalized"
          && !reviewerCorrectionView
        )
        || selectedCoordinateBatch()?.status === "done";
      document.getElementById("undo-ball-coordinate-decision").disabled =
        !observation
        || (
          state.coordinateReview?.status === "finalized"
          && !reviewerCorrectionView
        )
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
      const reviewFrames = flaggedBallFrames.size
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
      const media = document.querySelector(
        "#ball-frame-modal .ball-frame-modal-media"
      );
      const preserveZoom = media.classList.contains("zoomed");
      renderBallFrames();
      selectedBallStateIndex = nextIndex;
      selectedBallTargetFrame = reviewFrames[nextIndex].frame;
      ballFrameInteractionMode = "zoom";
      if (preserveZoom) {
        const nextPoint = reviewFrames[nextIndex];
        media.style.setProperty(
          "--zoom-x",
          (nextPoint.x / ballTrack.width * 100) + "%"
        );
        media.style.setProperty(
          "--zoom-y",
          (nextPoint.y / ballTrack.height * 100) + "%"
        );
      }
      showRawBallFrame(selectedBallTargetFrame, preserveZoom);
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
        state?.segment?.coordinateMode === "frozen_bac"
          ? "Frame " + reviewedFrame + ": " + description
            + ". Saved in the separate reviewer-corrected Innovation demo "
            + "layer; frozen BAC is unchanged."
          : "Frame " + reviewedFrame + ": " + description
            + ". Saved locally for the single Copilot batch. Use Next review "
            + "when you are ready to move on.";
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
      const reviewerCorrectionView = Boolean(
        reviewWorkflow.reviewerCorrectedDemoLayer
        && state?.segment?.coordinateMode === "frozen_bac"
      );
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
        !reviewerCorrectionView && (finalized || batchReadOnly);
      reviewButton.disabled =
        !reviewerCorrectionView && !flaggedBallFrames.size;
      reviewButton.textContent = reviewerCorrectionView
        ? "Open reviewer coordinate layer ("
          + flaggedBallFrames.size + " corrected)"
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
        reviewerCorrectionView
          ? "Reviewer-corrected Innovation demo layer"
        : finalized
          ? "Query mode · review finalized"
          : "Coordinate recovery mode";
      document.getElementById("ball-coordinate-review-status").textContent =
        reviewerCorrectionView
          ? "Frozen BAC stays unchanged. Click any frame to agree, mark "
            + "undefined, choose a YOLO candidate, or save your own coordinate "
            + "in the separate reviewer-corrected demo layer."
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
      const activeRoundView =
        filter.value === "flagged" && latestReviewSelected;
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
          " · click a frame number to review"
        : "No coordinate states";
      document.getElementById("ball-frame-items").replaceChildren(
        ...visible.map((point, index) => {
          const observation =
            ballCoordinateObservations[String(point.frame)];
          const reviewerCoordinate = Boolean(
            reviewWorkflow.reviewerCorrectedDemoLayer
            && observation?.decision === "specified"
            && observation?.approved
            && Number.isFinite(observation.x)
            && Number.isFinite(observation.y)
          );
          const displayedX = reviewerCoordinate ? observation.x : point.x;
          const displayedY = reviewerCoordinate ? observation.y : point.y;
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
            Number.isFinite(displayedX) ? displayedX.toFixed(1) : "Pending",
            Number.isFinite(displayedY) ? displayedY.toFixed(1) : "Pending",
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
          const evidenceLabel = document.createElement("span");
          evidenceLabel.textContent = point.evidence;
          const gateInfoButton = document.createElement("button");
          gateInfoButton.type = "button";
          gateInfoButton.className = "coordinate-gate-info-button";
          gateInfoButton.textContent = "Details";
          gateInfoButton.setAttribute(
            "aria-label",
            "Show coordinate gate details for frame " + point.frame
          );
          gateInfoButton.title = "Show coordinate evidence";
          const broadCandidateCount = (
            ballTrack?.yoloCandidates?.[String(point.frame)] || []
          ).length;
          const carryForward =
            batch?.carryForward?.[String(point.frame)] || null;
          const disputed = (batch?.disputedFrames || []).includes(point.frame)
            || carryForward?.status === "disputed_direct";
          const gateDetail = document.createElement("div");
          const gateDetailId = "coordinate-gate-" + point.frame;
          gateDetail.id = gateDetailId;
          gateDetail.className = "coordinate-gate-popover";
          gateDetail.setAttribute("popover", "auto");
          gateInfoButton.setAttribute("popovertarget", gateDetailId);
          gateDetail.textContent = [
            "Broad YOLO candidate: "
              + (broadCandidateCount
                ? broadCandidateCount + " saved candidate(s)"
                : "NONE SAVED"),
            broadCandidateCount
              ? "Open this frame to view the saved YOLO candidates as blue rings."
              : "No saved YOLO candidates are available for this frame.",
            "Engine source: " + point.evidence,
            point.evidence === "focused_multiscale_detector"
              ? "Focused YOLO crops: generated after the broad run; these "
                + "are not represented by the saved blue rings."
              : null,
            "Current review result: " + (
              disputed
                ? "DISPUTED — do not treat as correct"
                : point.direct ? "DIRECT" : "UNRESOLVED"
            ),
            carryForward?.reason
              ? "Previous-round reason: " + carryForward.reason
              : null,
            "",
            "Required gate order:",
            "1. YOLO candidate",
            "2. Pitch/player context",
            "3. Temporal support",
            "4. Competing-path margin",
            "5. Bidirectional confirmation",
            "6. Final result"
          ].filter(value => value !== null).join("\\n");
          evidence.append(evidenceLabel, gateInfoButton, gateDetail);
          const review = document.createElement("td");
          const decision = document.createElement("td");
          const savedDecisionPresentation = observation?.decision
            ? {
                agree: ["Agreed with coordinate", "confirmed"],
                undefined: ["Ball undefined / not visible", "undefined"],
                yolo_candidate: ["YOLO candidate confirmed", "confirmed"],
                specified: [
                  observation.approved
                    ? "Custom coordinate confirmed"
                    : "Custom coordinate awaiting confirmation",
                  observation.approved ? "confirmed" : "checking"
                ],
                needs_more_checking: ["Needs more checking", "checking"]
              }[observation.decision]
            : null;
          const decisionPresentation =
            reviewerCorrectionView
            && reviewerCoordinateChangeStatus(point.frame, observation)
              === "pending"
              ? ["User changed · pending batch apply", "checking"]
            : reviewerCorrectionView
            && reviewerCoordinateChangeStatus(point.frame, observation)
              === "applied"
              ? [
                  "User changed · applied revision "
                    + Number(state.reviewerCoordinateLayer?.revision || 0),
                  "confirmed"
                ]
            : savedDecisionPresentation || (
                  state?.segment?.coordinateMode === "frozen_bac"
                    ? ["BAC imported · confirmed", "confirmed"]
                    : ["Not reviewed yet", "pending"]
                );
          const decisionStatus = document.createElement("span");
          decisionStatus.className =
            "coordinate-review-result " + decisionPresentation[1];
          decisionStatus.textContent = decisionPresentation[0];
          if (
            ["specified", "yolo_candidate"].includes(observation?.decision)
            && Number.isFinite(observation.x)
            && Number.isFinite(observation.y)
          ) {
            decisionStatus.title = "Visible ball at ("
              + observation.x.toFixed(1) + ", "
              + observation.y.toFixed(1) + ")";
          }
          decision.append(decisionStatus);
          const reviewableFrame = Boolean(
            activeRoundView
            && batch.frames.includes(point.frame)
          );
          if (reviewerCorrectionView) {
            review.textContent =
              reviewerCoordinateChangeStatus(point.frame, observation)
                === "pending"
                ? "Flagged for next coordinate update"
                : reviewerCoordinateChangeStatus(point.frame, observation)
                    === "applied"
                  ? "Applied to current coordinate revision"
                  : "No user change";
          } else if (finalized) {
            review.textContent = "Review finalized";
          } else if (selectedCoordinateBatchId === "all") {
            review.textContent = "Inspect only";
          } else if (batch?.status === "done") {
            const rerunResult = {
              fixed: "resolved",
              unresolved: "still unresolved",
              regressed: "regressed",
              unchanged_direct: "still direct"
            }[batch.frameResults?.[String(point.frame)]?.status]
              || "result unavailable";
            review.textContent = rerunResult;
          } else if (!activeRoundView) {
            review.textContent =
              batch?.status === "ready" && batch.frames.includes(point.frame)
                ? "Review in Round " + batch.number
                : "Inspect only";
          } else if (!reviewableFrame) {
            review.textContent = batch
              ? "Not in Round " + batch.number
              : "Not in active round";
          } else {
            const reviewStatus = document.createElement("span");
            const carryForward =
              batch?.carryForward?.[String(point.frame)];
            reviewStatus.className = "coordinate-review-result "
              + (observation?.approved ? "confirmed" : "pending");
            reviewStatus.textContent = observation?.approved
              ? "Decision saved"
              : carryForward
                ? "Returned from Round " + carryForward.sourceRound
                : "Pending decision";
            if (carryForward) {
              reviewStatus.title = carryForward.reason;
              review.append(reviewStatus);
            } else {
              review.append(reviewStatus);
            }
          }
          row.append(frame, ...values, status, evidence, review, decision);
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
          loadBallFrameFlags();
          document.getElementById("ball-frame-filter").value = "flagged";
          renderBallFrames();
          renderBallCoordinateReviewMessages();
        });
        return button;
      }));
      const timeline = document.getElementById("coordinate-review-timeline");
      const completedNotifications = batch ? [
        {
          label: "Batch submitted",
          value: batch.submittedAt,
          detail: (batch.frames?.length || 0)
            + " reviewed frame decisions frozen for bounded analysis."
        },
        {
          label: "Evidence review completed",
          value: batch.reviewCompletedAt,
          detail: batch.reviewSummary
        },
        {
          label: "General code fix completed",
          value: batch.codeFixCompletedAt,
          detail: batch.codeFixSummary
        },
        {
          label: "Focused and protected tests passed",
          value: batch.testsCompletedAt,
          detail: batch.testsSummary
        },
        {
          label: "Whole-segment coordinate rerun started",
          value: batch.rerunStartedAt,
          detail: "Rebuilding from runtime detections without using review labels."
        },
        {
          label: "Coordinate rerun completed",
          value: batch.rerunCompletedAt,
          detail: batch.status === "done"
            ? (batch.fixedFrames?.length || 0) + " provenance additions, "
              + (batch.unresolvedFrames?.length || 0) + " unresolved, "
              + (batch.regressionFrames?.length || 0) + " regressed."
            : null
        },
        {
          label: "Independent output review rejected",
          value: batch.reviewRejectedAt,
          detail: batch.reviewRejectedAt
            ? (
                (batch.fixedFrames?.length || 0)
                - (batch.disputedFrames?.length || 0)
              ) + " visually supported fixes, "
              + (batch.disputedFrames?.length || 0)
              + " disputed direct results, "
              + (batch.unresolvedFrames?.length || 0)
              + " unresolved. Validation remains blocked."
            : null
        }
      ].filter(notification => notification.value) : [];
      const currentNotification = batch && !["done", "failed", "ready"].includes(
        batch.status
      ) ? {
        active: true,
        label: {
          working: "Copilot is reviewing the frozen evidence",
          review_completed: "Copilot is implementing a general code fix",
          code_fix_completed: "Copilot is running focused and protected tests",
          tests_completed: "Starting the whole-segment coordinate rerun",
          rerun_started: "Rebuilding ball coordinates"
        }[batch.status] || "Preparing coordinate review",
        detail: batch.status === "rerun_started"
          ? [
              state.segment?.statusMessage,
              state.segment?.expectedFrames
                ? state.segment.processedFrames + "/"
                  + state.segment.expectedFrames + " sampled frames"
                : null
            ].filter(Boolean).join(" · ")
            || "The current raw-video processing stage is running."
          : {
              working: "Checking only the submitted frames against raw-video evidence.",
              review_completed: "Applying a reusable rule; no frame-specific exception is allowed.",
              code_fix_completed: "The rerun starts only if all required tests pass.",
              tests_completed: "Preparing fresh coordinate output from runtime evidence."
            }[batch.status]
      } : batch?.status === "ready" ? {
        active: false,
        status: "Ready",
        label: "Round " + batch.number + " ready for your decisions",
        detail: (batch.frames?.length || 0)
          + " unresolved or disputed frames are awaiting review. "
          + "Use the frame table below the modal; each row includes the "
          + "previous-round reason."
      } : null;
      const timelineNotifications = currentNotification
        ? [...completedNotifications, currentNotification]
        : completedNotifications;
      timeline.replaceChildren(...timelineNotifications.map(notification => {
        const item = document.createElement("li");
        item.className = "message "
          + (notification.active ? "assistant" : "system");
        const heading = document.createElement("strong");
        heading.textContent = notification.label + (
          notification.value
            ? " · " + formatCoordinateBatchTime(notification.value)
            : " · " + (notification.status || "In progress")
        );
        const detail = document.createElement("span");
        detail.textContent = notification.detail || "Completed.";
        item.append(heading, detail);
        return item;
      }));
      const latestCompletedBatch = [...batches].reverse().find(
        candidate => candidate.status === "done"
      );
      const roundResult = document.getElementById("coordinate-round-result");
      const afterDirect = Number(batch?.after?.directFrameCount || 0);
      const afterSampled = Number(batch?.after?.sampledFrameCount || 0);
      const afterCoverage = afterSampled
        ? afterDirect / afterSampled
        : Number(batch?.after?.directProvenance || 0);
      const unresolvedCount = batch?.unresolvedFrames?.length || 0;
      const regressionCount = batch?.regressionFrames?.length || 0;
      const disputedCount = batch?.disputedFrames?.length || 0;
      const supportedFixedCount = Math.max(
        0,
        (batch?.fixedFrames?.length || 0) - disputedCount
      );
      const gateDirectCount = Number(
        latestCompletedBatch?.after?.directFrameCount || 0
      );
      const gateSampledCount = Number(
        latestCompletedBatch?.after?.sampledFrameCount || 0
      );
      const coordinateMinimumReached = Boolean(
        gateSampledCount
        && gateDirectCount >= Math.ceil(gateSampledCount * 0.90)
      );
      const batchProcessing = coordinateBatchLocked(batch)
        || batch?.status === "rerun_started";
      roundResult.hidden = !batchProcessing && batch?.status !== "done";
      roundResult.className = "ball-frame-modal-status"
        + (batchProcessing ? " coordinate-round-result processing" : "");
      roundResult.textContent = batchProcessing
        ? "Processing Round " + batch.number
          + ": reviewing evidence, applying a general code fix, running "
          + "tests, then rebuilding ball coordinates for the whole segment."
        : batch?.status === "done"
          ? batch.reviewRejectedAt
            ? "Round " + batch.number + " decision · Review rejected · "
              + supportedFixedCount + " visually supported fixes · "
              + disputedCount + " disputed direct results · "
              + unresolvedCount + " unresolved · "
              + (unresolvedCount + disputedCount + regressionCount)
              + " moved to Round " + (Number(batch.number) + 1) + ". "
              + afterDirect + "/" + afterSampled + " direct provenance ("
              + (afterCoverage * 100).toFixed(1)
              + "%) was not validated as coordinate-correct."
            : "Round " + batch.number + " result · "
              + supportedFixedCount + " resolved · "
              + unresolvedCount + " unresolved · "
              + regressionCount + " regressed · "
              + afterDirect + "/" + afterSampled + " direct ("
              + (afterCoverage * 100).toFixed(1) + "%). "
              + (
                afterCoverage >= 0.90
                  ? state.coordinateReview?.status === "verified"
                    ? "The 90% minimum is reached. Choose Continue to event "
                      + "review or improve the remaining frames."
                    : "The 90% minimum is reached. Verifying the current code "
                      + "and persisted output before presenting your choice."
                  : "The 90% minimum is not reached; the next unresolved round is required."
              )
          : "";
      const finalize = document.getElementById(
        "finalize-ball-coordinate-review"
      );
      finalize.disabled = !coordinateMinimumReached || segmentRunActive();
      finalize.hidden = state.coordinateReview?.status === "finalized";
      finalize.textContent = "Start rules-engine run";
      const applyReviewerLayer = document.getElementById(
        "apply-reviewer-coordinate-layer"
      );
      const approvedCoordinateChanges = Object.values(
        ballCoordinateObservations
      ).filter(observation =>
        observation?.approved
        && ["specified", "yolo_candidate", "undefined"].includes(
          observation.decision
        )
      ).length;
      applyReviewerLayer.disabled =
        !approvedCoordinateChanges || segmentRunActive();
      applyReviewerLayer.textContent =
        "Apply " + approvedCoordinateChanges + " approved coordinate update"
        + (approvedCoordinateChanges === 1 ? "" : "s");
      const improveCoverage = document.getElementById(
        "improve-coordinate-coverage"
      );
      const canImproveCoverage = Boolean(
        state.coordinateReview?.status === "verified"
        && batch?.id === latestCompletedBatch?.id
        && unresolvedCount + regressionCount > 0
      );
      improveCoverage.hidden = !canImproveCoverage;
      improveCoverage.disabled = !canImproveCoverage;
      if (canImproveCoverage) {
        improveCoverage.textContent =
          "Improve coverage: review "
          + new Set([
            ...(batch.unresolvedFrames || []),
            ...(batch.regressionFrames || [])
          ]).size + " leftover frames";
      }
      const approvedCount = [...flaggedBallFrames].filter(
        frame => ballCoordinateObservations[String(frame)]?.approved
      ).length;
      const sendBatch = document.getElementById(
        "send-ball-coordinate-autopilot"
      );
      const reviewComplete = Boolean(
        flaggedBallFrames.size
        && approvedCount === flaggedBallFrames.size
      );
      sendBatch.textContent = batch?.status === "done"
        ? "Batch done"
        : coordinateBatchLocked(batch)
          ? coordinateBatchStatusLabel(batch.status)
        : reviewComplete
          ? "Send reviewed batch once to Copilot ("
            + approvedCount + "/" + flaggedBallFrames.size + " marked)"
          : "Complete all decisions before sending ("
            + approvedCount + "/" + flaggedBallFrames.size + " marked)";
      sendBatch.disabled = Boolean(
        !batch
        || batch.status !== "ready"
        || !reviewComplete
      );
      const close = document.getElementById("close-ball-coordinate-review");
      close.disabled = coordinateBatchLocked(batch);
      close.title = close.disabled
        ? "This progress modal remains open until Copilot and the rerun finish."
        : "";
      const modal = document.getElementById("ball-coordinate-review-modal");
      if (
        modal.open
        && lastCoordinateBatchStatus === "rerun_started"
        && batch?.status === "ready"
        && batch.id !== lastCoordinateBatchId
      ) {
        modal.close();
        document.getElementById("ball-frame-filter").value = "flagged";
        const frameReview = document.getElementById("ball-frame-review");
        frameReview.open = true;
        requestAnimationFrame(() => {
          frameReview.scrollIntoView({behavior: "smooth", block: "start"});
        });
      }
      lastCoordinateBatchStatus = batch?.status || null;
      lastCoordinateBatchId = batch?.id || null;
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
        const observation =
          ballCoordinateObservations[String(point.frame)] || null;
        const reviewerChangeStatus = reviewerCoordinateChangeStatus(
          point.frame,
          observation
        );
        const result =
          batch?.frameResults?.[String(point.frame)]?.status || null;
        const carryForward =
          batch?.carryForward?.[String(point.frame)] || null;
        const disputed = (batch?.disputedFrames || []).includes(point.frame)
          || carryForward?.status === "disputed_direct";
        const presentation =
          reviewWorkflow.reviewerCorrectedDemoLayer
          && reviewerChangeStatus === "pending"
            ? ["User changed · pending batch apply", "checking"]
          : reviewWorkflow.reviewerCorrectedDemoLayer
          && reviewerChangeStatus === "applied"
            ? [
                "User changed · applied revision "
                  + Number(state.reviewerCoordinateLayer?.revision || 0),
                "confirmed"
              ]
          : disputed
          ? ["Disputed", "undefined"]
          : ["fixed", "unchanged_direct"].includes(result)
            ? ["Fixed", "confirmed"]
            : result === "regressed"
              ? ["Regressed", "undefined"]
              : result === "unresolved" || carryForward
                ? ["Unresolved", "checking"]
                : state?.segment?.coordinateMode === "frozen_bac"
                  ? ["BAC imported · confirmed", "confirmed"]
                  : point.direct
                    ? ["Direct coordinate · Not reviewed yet", "pending"]
                    : ["Estimated coordinate · Not reviewed yet", "pending"];
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "coordinate-review-result " + presentation[1];
        chip.textContent = "Frame " + point.frame + " · "
          + point.seconds.toFixed(2) + "s · "
          + presentation[0];
        chip.title = carryForward?.reason || "";
        chip.addEventListener("click", () => {
          const pointIndex = (ballTrack?.states || []).findIndex(
            candidate => candidate.frame === point.frame
          );
          if (pointIndex >= 0) showBallFrame(pointIndex);
        });
        return chip;
      }));
    }

    async function sendBallCoordinateReview(mode) {
      const status = document.getElementById(
        "ball-coordinate-review-send-status"
      );
      const flaggedFrames = [...flaggedBallFrames].sort((a, b) => a - b);
      if (!flaggedFrames.length) {
        status.textContent = "Flag at least one estimated frame first.";
        return;
      }
      const text =
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
        status.textContent =
          "Bounded coordinate review started. Progress is shown above.";
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
        "Starting the rules engine from the current coordinates…";
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
        button.disabled = state.coordinateReview?.status === "finalized"
          || segmentRunActive();
      }
    }

    async function applyReviewerCoordinateLayer() {
      const status = document.getElementById(
        "ball-coordinate-review-send-status"
      );
      const button = document.getElementById(
        "apply-reviewer-coordinate-layer"
      );
      button.disabled = true;
      status.textContent =
        "Saving the shared coordinate revision and rebuilding dependent "
        + "player tracking and events…";
      try {
        const response = await fetch(
          "/api/innovation/approve-coordinate-layer",
          {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({segment: selectedSegmentKey()})
          }
        );
        const result = await response.json();
        if (!response.ok) {
          throw new Error(
            result.error || "Could not apply reviewer coordinate updates"
          );
        }
        status.textContent =
          "Coordinate revision " + result.revision + " saved. Existing YOLO "
          + "detections are being reused while player tracking rebuilds."
          + (result.eventsRerun
            ? " The previously run Innovation engine will then rerun."
            : " The Innovation engine has not run yet and will remain waiting.");
        await loadState();
      } catch (error) {
        status.textContent = error.message;
        renderBallCoordinateReviewMessages();
      }
    }

    async function continueCoordinateReview() {
      const status = document.getElementById(
        "ball-coordinate-review-send-status"
      );
      const modal = document.getElementById("ball-coordinate-review-modal");
      if (!modal.open) modal.showModal();
      const buttons = [
        document.getElementById("continue-coordinate-review"),
        document.getElementById("improve-coordinate-coverage")
      ];
      buttons.forEach(button => {
        button.disabled = true;
      });
      status.textContent =
        "Creating a new review round from unresolved frames…";
      try {
        const response = await fetch("/api/continue-coordinate-review", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({segment: selectedSegmentKey()})
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(
            result.error || "Could not create the next coordinate round"
          );
        }
        await loadState();
        selectedCoordinateBatchId = result.batchId;
        loadBallFrameFlags();
        document.getElementById("ball-frame-filter").value = "flagged";
        renderBallFrames();
        renderBallCoordinateReviewMessages();
        document.getElementById("ball-coordinate-review-modal").showModal();
        status.textContent =
          "Round created with " + result.frameCount
          + " unresolved frames ready for review.";
      } catch (error) {
        status.textContent = error.message;
      } finally {
        buttons.forEach(button => {
          button.disabled = state.coordinateReview?.status !== "verified";
        });
      }
    }

    function updateBallMarker() {
      if ((viewMode !== "ball" && !showBacCoordinate) || !ballTrack) {
        ballOverlay.setAttribute("hidden", "");
        return;
      }
      const point = nearestBallPoint(video.currentTime || 0);
      if (!point) {
        ballOverlay.setAttribute("hidden", "");
        return;
      }
      const [, pointSeconds, frozenX, frozenY, trackId] = point;
      const frame = Number(point[0]);
      const reviewerCoordinate = ballCoordinateObservations[String(frame)];
      const useReviewerCoordinate = Boolean(
        reviewWorkflow.reviewerCorrectedDemoLayer
        && reviewerCoordinate?.decision === "specified"
        && reviewerCoordinate?.approved
        && Number.isFinite(reviewerCoordinate.x)
        && Number.isFinite(reviewerCoordinate.y)
      );
      const x = useReviewerCoordinate ? reviewerCoordinate.x : frozenX;
      const y = useReviewerCoordinate ? reviewerCoordinate.y : frozenY;
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
        viewMode === "ball"
          ? trajectory.map((candidate, index) =>
              (index ? "L " : "M ") + candidate[2] + " " + candidate[3]
            ).join(" ")
          : ""
      );
      ballMarker.setAttribute("cx", String(x));
      ballMarker.setAttribute("cy", String(y));
      ballCrosshair.setAttribute(
        "d",
        "M " + (x - 44) + " " + y + " H " + (x + 44) +
        " M " + x + " " + (y - 44) + " V " + (y + 44)
      );
      ballCoordinateLabel.toggleAttribute("hidden", !showBacCoordinate);
      if (showBacCoordinate) {
        const labelX = Math.min(
          Math.max(0, x + 48),
          Math.max(0, Number(ballTrack.width) - 700)
        );
        const labelY = Math.min(
          Math.max(0, y - 92),
          Math.max(0, Number(ballTrack.height) - 76)
        );
        ballCoordinateLabel.setAttribute(
          "transform",
          "translate(" + labelX + " " + labelY + ")"
        );
        ballCoordinateLabelText.textContent =
          (useReviewerCoordinate ? "Reviewer correction" : "BAC")
          + " · frame " + frame + " · x " + Math.round(x)
          + " · y " + Math.round(y);
      }
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

    function cachedReplaySegment(segmentKey = segmentReplayKey) {
      return (state?.replaySegments || []).find(
        segment => segment.key === segmentKey
      ) || null;
    }

    function updateSegmentReplay() {
      const segment = cachedReplaySegment();
      if (!segment) return;
      const seconds = Math.max(0, segmentReplayVideo.currentTime || 0);
      const totals = emptyStatistics();
      segment.events.forEach(event => {
        if (event.seconds > seconds + 0.001) return;
        includeEventInStatistics(totals, event);
      });
      ["red", "black"].forEach(team => {
        document.getElementById(
          "segment-replay-" + team + "-passes"
        ).textContent = String(totals[team].passes);
        document.getElementById(
          "segment-replay-" + team + "-turnovers"
        ).textContent = String(totals[team].turnovers);
        document.getElementById(
          "segment-replay-" + team + "-shots"
        ).textContent = String(totals[team].shots);
        document.getElementById(
          "segment-replay-" + team + "-on-target"
        ).textContent = String(totals[team].onTarget);
      });
      document.getElementById("segment-replay-clock").textContent =
        formatReplayTime(seconds) + " / "
        + formatReplayTime(segment.durationSeconds);
    }

    function openSegmentReplay(segmentKey) {
      const segment = cachedReplaySegment(segmentKey);
      if (!segment) return;
      segmentReplayKey = segment.key;
      document.getElementById("segment-replay-title").textContent =
        "Cached engine replay · " + segment.timeLabel;
      document.getElementById("segment-replay-subtitle").textContent =
        "Published segment · stadium playback";
      segmentReplayVideo.src = segment.videoUrl;
      segmentReplayVideo.currentTime = 0;
      updateSegmentReplay();
      segmentReplayModal.showModal();
      segmentReplayVideo.addEventListener(
        "loadedmetadata",
        () => void segmentReplayVideo.play(),
        {once: true}
      );
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
      const pointerCrosshair = document.getElementById("ball-frame-pointer");
      const pointerLabel = document.getElementById(
        "ball-frame-pointer-label"
      );
      const originalBallCoordinateAtPointer = event => {
        const bounds = ballFrameMedia.getBoundingClientRect();
        const sourceWidth = Number(ballTrack?.width || 4450);
        const sourceHeight = Number(ballTrack?.height || 2000);
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
          bounds.width / sourceWidth,
          bounds.height / sourceHeight
        );
        const renderedWidth = sourceWidth * scale;
        const renderedHeight = sourceHeight * scale;
        const offsetX = (bounds.width - renderedWidth) / 2;
        const offsetY = (bounds.height - renderedHeight) / 2;
        const x = (unzoomedX - offsetX) / scale;
        const y = (unzoomedY - offsetY) / scale;
        if (x < 0 || x > sourceWidth || y < 0 || y > sourceHeight) {
          return null;
        }
        return {x, y};
      };
      const updatePointerCoordinate = event => {
        if (!ballTrack || event.target.closest("button")) {
          pointerCrosshair.hidden = true;
          return;
        }
        const mediaBounds = ballFrameMedia.getBoundingClientRect();
        const coordinate = originalBallCoordinateAtPointer(event);
        if (!coordinate) {
          pointerCrosshair.hidden = true;
          return;
        }
        pointerCrosshair.hidden = false;
        pointerCrosshair.style.setProperty(
          "--pointer-x",
          (event.clientX - mediaBounds.left) + "px"
        );
        pointerCrosshair.style.setProperty(
          "--pointer-y",
          (event.clientY - mediaBounds.top) + "px"
        );
        pointerLabel.textContent =
          "x " + Math.round(coordinate.x)
          + " · y " + Math.round(coordinate.y);
      };
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
        updatePointerCoordinate(event);
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
      ballFrameMedia.addEventListener("pointerleave", () => {
        if (!panStart) pointerCrosshair.hidden = true;
      });
      ballFrameMedia.addEventListener("click", event => {
        if (event.target.closest("button")) return;
        if (ballFrameDidDrag) {
          ballFrameDidDrag = false;
          return;
        }
        if (ballFrameInteractionMode === "mark") {
          const coordinate = originalBallCoordinateAtPointer(event);
          if (!coordinate) return;
          ballCoordinateObservations[String(selectedBallTargetFrame)] = {
            frame: selectedBallTargetFrame,
            decision: "specified",
            x: coordinate.x,
            y: coordinate.y,
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
            showRawBallFrame(selectedRawBallFrame - 1, true);
          }
        }
      );
      document.getElementById("next-ball-frame").addEventListener(
        "click",
        () => {
          if (!rawBallFrameSeekPending) {
            showRawBallFrame(selectedRawBallFrame + 1, true);
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
        "apply-reviewer-coordinate-layer"
      ).addEventListener(
        "click",
        () => void applyReviewerCoordinateLayer()
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
        () => void continueCoordinateReview()
      );
      document.getElementById(
        "improve-coordinate-coverage"
      ).addEventListener(
        "click",
        () => void continueCoordinateReview()
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
      clearTimeout(eventTriggerTimers.manual);
      eventTriggerTimers.manual = null;
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

    function innovationComparisonRows() {
      const manualEvents = state?.manualEvents || [];
      const rejectedManualEvents = state?.rejectedManualEvents || [];
      const engineEvents = state?.engineEvents || [];
      const suggestions = state?.manualReference?.suggestions || {};
      const usedEngine = new Set();
      const rows = manualEvents.map((manual, reviewIndex) => {
        const suggestion = suggestions[manual.key];
        const engineKey = suggestion?.engineKey;
        const engineIndex = engineEvents.findIndex(
          (event, index) => (event.key || "E" + (index + 1)) === engineKey
        );
        if (engineIndex >= 0) usedEngine.add(engineIndex);
        return {
          review: manual,
          reviewIndex,
          engine: engineIndex >= 0 ? engineEvents[engineIndex] : null,
          engineIndex,
          mappingKind: suggestion ? "automatic" : null,
          mappingWarning: false,
          status: engineIndex >= 0 ? "matched" : "off"
        };
      });
      rejectedManualEvents.forEach(manual => {
        rows.push({
          review: manual,
          reviewIndex: -1,
          engine: null,
          engineIndex: -1,
          mappingKind: null,
          mappingWarning: false,
          status: "manual-rejected"
        });
      });
      engineEvents.forEach((engine, engineIndex) => {
        if (!usedEngine.has(engineIndex)) {
          rows.push({
            review: null,
            reviewIndex: -1,
            engine,
            engineIndex,
            mappingKind: null,
            mappingWarning: false,
            status: comparisonStatus(null, engine)
          });
        }
      });
      return rows.sort((left, right) =>
        Number(left.review?.seconds ?? left.engine?.seconds ?? 0)
        - Number(right.review?.seconds ?? right.engine?.seconds ?? 0)
      );
    }

    function comparisonRows() {
      if (reviewWorkflow.key === "innovation") {
        return innovationComparisonRows();
      }
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
      return isManualReviewEvent(event) && event.key
        ? event.key
        : (isManualReviewEvent(event) ? "M" : "C") + (index + 1);
    }

    function manualDisplayKey(event, index) {
      return event?.displayKey || (
        Number.isInteger(index) ? "M" + (index + 1) : event?.key || "M"
      );
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
            ? (
                isManualReviewEvent(event)
                  ? "manual reference " + reviewReference(event, reviewIndex)
                    + " "
                  : "Copilot proposal "
              )
            : "engine event "
        ) + (side === "review" && isManualReviewEvent(event) ? "" : eventNumber)
          + " at " + event.seconds.toFixed(3)
          + " seconds: " + canonicalLabel
      );
      const number = document.createElement("span");
      number.className = "comparison-number";
      number.textContent = side === "review"
        ? (
            isManualReviewEvent(event)
              ? manualDisplayKey(event, eventNumber - 1)
              : (isManualReviewEvent(event) ? "M" : "C") + eventNumber
          )
        : "E" + eventNumber;
      button.classList.toggle(
        "regression-added",
        side === "engine" && event.regressionChange === "added"
      );
      const label = document.createElement("span");
      label.className = "comparison-label";
      label.textContent = canonicalLabel;
      const frame = document.createElement("span");
      frame.className = "comparison-frame";
      const sourceFrame = isManualReviewEvent(event)
        ? Number(event.sourceFrame)
        : Math.round(event.seconds * 25);
      frame.textContent =
        event.seconds.toFixed(3) + "s · frame "
        + sourceFrame;
      label.append(frame);
      if (side === "engine" && event.regressionChange === "added") {
        const newBadge = document.createElement("span");
        newBadge.className = "comparison-new";
        newBadge.textContent = "NEW";
        label.append(newBadge);
      }
      const userVerdict = event.review?.userVerdict
        || (event.review?.userClaimedCorrect ? "correct" : null);
      if (side === "engine" && userVerdict) {
        const reviewerVerdict = document.createElement("span");
        reviewerVerdict.className = "comparison-reviewer-verdict";
        reviewerVerdict.textContent =
          "Reviewer verdict: "
          + userVerdict.charAt(0).toUpperCase()
          + userVerdict.slice(1);
        label.append(reviewerVerdict);
      }
      button.append(number, label);
      button.addEventListener("click", () => {
        if (side === "review" && event.reviewStatus === "rejected") {
          seekVideo(event.seconds);
          return;
        }
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

    async function mutateManualReference(payload) {
      const response = await fetch("/api/manual-review-event", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({segment: selectedSegmentKey(), ...payload})
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || "Could not update manual reference");
      }
      await loadState();
      return result;
    }

    async function updateManualLedgerAcknowledgement(findingId, acknowledged) {
      const status = document.getElementById("manual-ledger-audit-status");
      status.textContent = acknowledged
        ? "Recording your confirmation…"
        : "Reopening this advisory…";
      try {
        const response = await fetch("/api/manual-ledger-audit", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            segment: selectedSegmentKey(),
            action: acknowledged ? "acknowledge" : "reopen",
            findingId
          })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not update the ledger audit");
        }
        await loadState();
        status.textContent = acknowledged
          ? "Your M# decision remains unchanged and authoritative."
          : "The advisory is open again.";
      } catch (error) {
        status.textContent = error.message;
      }
    }

    function renderManualLedgerAudit() {
      if (reviewWorkflow.key !== "innovation") return;
      const audit = state?.manualReference?.ledgerAudit || {
        findings: [],
        acknowledgedCount: 0
      };
      const findings = audit.findings || [];
      const openFindings = findings.filter(
        finding => !finding.acknowledgement
      );
      const openButton = document.getElementById("open-manual-ledger-audit");
      openButton.textContent = openFindings.length
        ? "Audit M# ledger (" + openFindings.length + ")"
        : "Audit M# ledger";
      const totals = (state.manualEvents || []).reduce((result, event) => {
        const key = event.team + ":" + event.type;
        result[key] = Number(result[key] || 0) + 1;
        return result;
      }, {});
      const ledgerCounts = (state.manualEvents || []).length + " active M# · "
        + "Black: " + Number(totals["black:completed_pass"] || 0)
        + " completed passes, " + Number(totals["black:turnover"] || 0)
        + " turnovers · Red/white: "
        + Number(totals["red:completed_pass"] || 0)
        + " completed passes, " + Number(totals["red:turnover"] || 0)
        + " turnovers. ";
      const summary = document.getElementById("manual-ledger-audit-summary");
      summary.textContent = findings.length === 0
        ? ledgerCounts
          + "No potential inconsistencies were found in the current M# ledger."
        : ledgerCounts + openFindings.length + " open advisory check"
          + (openFindings.length === 1 ? "" : "s") + " · "
          + Number(audit.acknowledgedCount || 0) + " confirmed by reviewer. "
          + "None of these findings blocks approval.";
      const displayKeys = new Map(
        (state.manualEvents || []).map(
          event => [event.key, event.displayKey || event.key]
        )
      );
      const list = document.getElementById("manual-ledger-audit-list");
      list.replaceChildren(...findings.map(finding => {
        const item = document.createElement("article");
        item.className = "manual-ledger-audit-finding"
          + (finding.acknowledgement ? " acknowledged" : "");
        const heading = document.createElement("header");
        const title = document.createElement("strong");
        title.textContent = finding.title;
        const category = document.createElement("span");
        category.className = "muted";
        category.textContent = finding.category;
        heading.append(title, category);
        const detail = document.createElement("p");
        detail.textContent = finding.detail;
        const meta = document.createElement("span");
        meta.className = "manual-ledger-audit-meta";
        const references = (finding.manualKeys || [])
          .map(key => displayKeys.get(key) || key);
        meta.textContent = (references.length ? references.join(" ↔ ") : "Minute")
          + " · " + Number(finding.seconds || 0).toFixed(3) + "s";
        const actions = document.createElement("div");
        actions.className = "manual-ledger-audit-actions";
        const seek = document.createElement("button");
        seek.type = "button";
        seek.textContent = "Seek";
        seek.addEventListener("click", () => {
          document.getElementById("manual-ledger-audit-modal").close();
          seekVideo(Number(finding.seconds || 0));
        });
        const confirm = document.createElement("button");
        confirm.type = "button";
        confirm.textContent = finding.acknowledgement
          ? "Reopen advisory"
          : "Confirm M# is correct";
        confirm.disabled =
          referenceLocked() || state.activity?.state === "working";
        confirm.addEventListener("click", () => {
          void updateManualLedgerAcknowledgement(
            finding.id,
            !finding.acknowledgement
          );
        });
        actions.append(seek, confirm);
        if (finding.acknowledgement) {
          const confirmed = document.createElement("span");
          confirmed.className = "manual-ledger-audit-confirmed";
          confirmed.textContent = "Reviewer confirmed";
          actions.append(confirmed);
        }
        item.append(heading, detail, meta, actions);
        return item;
      }));
    }

    function missingEngineReviewButton(row) {
      const reviewMissing = document.createElement("button");
      reviewMissing.type = "button";
      reviewMissing.className = "comparison-action icon-action";
      const reviewMissingLabel =
        "Review missing E# for "
        + manualDisplayKey(row.review, row.reviewIndex);
      reviewMissing.setAttribute("aria-label", reviewMissingLabel);
      reviewMissing.title = reviewMissingLabel;
      reviewMissing.append(comparisonActionIcon("verify"));
      reviewMissing.disabled = state.activity?.state === "working";
      reviewMissing.addEventListener("click", event => {
        event.stopPropagation();
        selectedIndex = row.reviewIndex;
        video.pause();
        video.currentTime = Number(row.review.seconds);
        openManualEngineReviewModal(row.reviewIndex);
      });
      return reviewMissing;
    }

    function manualControls(row) {
      const controls = document.createElement("div");
      controls.className = "manual-editor-summary";
      if (row.review.reviewStatus === "rejected") {
        const rejected = document.createElement("span");
        rejected.className = "comparison-rejected";
        rejected.textContent = "✕ Rejected M# · excluded from golden set";
        rejected.title =
          "This manual event remains visible for audit but is not matched, "
          + "counted, approved, or published.";
        const restore = document.createElement("button");
        restore.type = "button";
        restore.className = "comparison-action";
        restore.textContent = "Restore removed event";
        restore.addEventListener("click", async event => {
          event.stopPropagation();
          await mutateManualReference({
            action: "restore",
            manualKey: row.review.key
          });
        });
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "comparison-action";
        remove.textContent = "Remove event";
        remove.addEventListener("click", async event => {
          event.stopPropagation();
          await mutateManualReference({
            action: "delete",
            manualKey: row.review.key
          });
        });
        controls.append(rejected, restore, remove);
        return controls;
      }
      const details = document.createElement("details");
      details.className = "manual-editor-details";
      details.dataset.manualEditor = row.review.key;
      const summary = document.createElement("summary");
      const displayKey = manualDisplayKey(row.review, row.reviewIndex);
      summary.textContent = "Edit " + displayKey;
      summary.setAttribute(
        "aria-label",
        "Edit " + displayKey + " time, team, event type, or delete it"
      );
      const editor = document.createElement("div");
      editor.className = "manual-editor";
      const time = document.createElement("input");
      time.type = "text";
      time.inputMode = "decimal";
      time.name = row.review.key + "-seconds";
      time.dataset.manualTime = row.review.key;
      time.autocomplete = "off";
      time.value = manualTimeDrafts.has(row.review.key)
        ? manualTimeDrafts.get(row.review.key)
        : Number(row.review.seconds).toFixed(3);
      time.placeholder = "Seconds, e.g. 18.180…";
      time.title = "Seconds from the start of the clip";
      time.setAttribute("aria-label", displayKey + " timestamp in seconds");
      const team = document.createElement("select");
      team.setAttribute("aria-label", displayKey + " team");
      [["black", "Black"], ["red", "White/red"]].forEach(([value, label]) => {
        team.add(new Option(label, value, false, row.review.team === value));
      });
      const type = document.createElement("select");
      type.setAttribute("aria-label", displayKey + " event type");
      [["completed_pass", "Completed pass"], ["turnover", "Turnover"]]
        .forEach(([value, label]) => {
          type.add(new Option(label, value, false, row.review.type === value));
        });
      const saveImmediately = () => {
        const seconds = Number(time.value);
        if (
          !time.value.trim()
          || !Number.isFinite(seconds)
          || seconds < 0
          || seconds > Number(state.segment.durationSeconds)
        ) {
          const status = document.getElementById("manual-capture-status");
          if (status) {
            status.textContent = "Enter seconds from 0 to "
              + Number(state.segment.durationSeconds).toFixed(3)
              + ", for example 18.180.";
          }
          return Promise.resolve();
        }
        return mutateManualReference({
          action: "edit",
          manualKey: row.review.key,
          timestampMs: Math.round(seconds * 1000),
          team: team.value,
          eventType: type.value
        }).then(result => {
          manualTimeDrafts.delete(row.review.key);
          forceFullscreenEventsRender = true;
          renderFullscreenEvents();
          return result;
        }).catch(error => {
          const status = document.getElementById("manual-capture-status");
          if (status) status.textContent = error.message;
        });
      };
      time.addEventListener("input", () => {
        manualTimeDrafts.set(row.review.key, time.value);
      });
      time.addEventListener("change", saveImmediately);
      time.addEventListener("keydown", event => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        saveImmediately();
      });
      team.addEventListener("change", saveImmediately);
      type.addEventListener("change", saveImmediately);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Delete " + displayKey;
      remove.addEventListener("click", async () => {
        await mutateManualReference({
          action: "delete",
          manualKey: row.review.key
        });
      });
      const mappingLabel = document.createElement("span");
      mappingLabel.className = row.engine
        ? "automatic-match"
        : "mapping-warning";
      mappingLabel.textContent = row.engine
        ? "Automatically matched to "
          + (row.engine.key || "E" + (row.engineIndex + 1))
          + " · "
          + Math.round(Math.abs(
            Number(row.engine.seconds) - Number(row.review.seconds)
          ) * 1000)
          + " ms apart"
        : "No engine match within one second";
      editor.append(time, team, type, remove);
      details.append(summary, editor);
      controls.append(mappingLabel, details);
      if (!row.engine) {
        controls.append(missingEngineReviewButton(row));
      }
      return controls;
    }

    function comparisonReviewCell(row) {
      if (!row.review) {
        const empty = document.createElement("span");
        empty.className = "comparison-empty";
        return empty;
      }
      const cell = document.createElement("div");
      cell.className = "comparison-review-cell";
      const batchTarget = state.activeDiscrepancyBatch?.targets?.find(
        target => (
          target.kind === "manual"
          && target.manualKey === row.review?.key
          && !target.completed
        )
      );
      const verifying = state.activity?.state === "working"
        && (
          state.activeConversation?.eventIndex === row.reviewIndex
          || Boolean(batchTarget)
        );
      if (verifying) cell.classList.add("verifying");
      cell.append(
        comparisonButton(
          row.review,
          "review",
          row.reviewIndex + 1,
          row.reviewIndex
        )
      );
      if (reviewWorkflow.key === "innovation") {
        if (!state.manualReference?.approved) {
          cell.append(manualControls(row));
        } else if (
          !row.engine
          && row.review.reviewStatus !== "rejected"
        ) {
          cell.append(missingEngineReviewButton(row));
        }
        return cell;
      }
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
        if (reviewWorkflow.key === "innovation") {
          const decideButton = document.createElement("button");
          decideButton.type = "button";
          decideButton.className = "comparison-action icon-action";
          const decideLabel =
            "Decide Copilot proposal C" + (row.reviewIndex + 1);
          decideButton.setAttribute("aria-label", decideLabel);
          decideButton.title = decideLabel;
          decideButton.append(comparisonActionIcon("decide"));
          decideButton.disabled = state.activity?.state === "working";
          decideButton.addEventListener("click", event => {
            event.stopPropagation();
            openCopilotDecisionModal(row.reviewIndex);
          });
          actions.append(decideButton);
        } else {
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
          const rejectLabel =
            "Reject Copilot proposal C" + (row.reviewIndex + 1);
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
        }
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
      const engineBatchTarget = state.activeDiscrepancyBatch?.targets?.find(
        target => (
          target.kind === "engine"
          && target.engineReviewKey === [
            row.engine?.type,
            row.engine?.team,
            Number(row.engine?.seconds).toFixed(3)
          ].join("|")
          && !target.completed
        )
      );
      if (state.activity?.state === "working" && engineBatchTarget) {
        cell.classList.add("verifying");
      }
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
        reviewed.textContent =
          row.engine.review.reviewSource === "professional_reviewer"
            ? "✓ Approved"
            : "✓ Confirmed";
        reviewed.title =
          row.engine.review.reviewSource === "professional_reviewer"
            ? "Approved directly by the professional reviewer"
            : "Confirmed by independent review";
        cell.append(reviewed);
      } else if (
        independentEngineReview
        && row.engine.review?.status === "not_confirmed"
        && row.engine.review.fresh
      ) {
        const unsupported = document.createElement("span");
        unsupported.className = "comparison-rejected";
        unsupported.textContent =
          row.engine.review.userVerdict === "incorrect"
            ? "✕ Incorrect — no such event"
            : "✕ Not confirmed";
        unsupported.title =
          row.engine.review.userVerdict === "incorrect"
            ? "The professional reviewer determined that no such event occurred"
            : "The exact engine event is unsupported";
        cell.append(unsupported);
      }
      if (
        independentEngineReview
        && (!referenceLocked() || regressionCandidateReviewActive())
      ) {
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
          if (reviewWorkflow.key === "innovation") {
            openEngineVerificationModal(row.engineIndex);
          } else {
            await requestEngineEventVerification(
              row.engineIndex,
              "fullscreen-chat-status",
              null,
              false
            );
          }
        });
        cell.append(confirm);
      }
      if (row.review) {
        const agreement = document.createElement("span");
        agreement.className = row.review.decision?.status === "rejected"
          ? "comparison-rejected"
          : "comparison-reviewed";
        agreement.textContent = reviewWorkflow.key === "innovation"
          ? "M and E match within one second"
          : row.review.decision?.status === "rejected"
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
      const force = forceFullscreenEventsRender;
      forceFullscreenEventsRender = false;
      const renderSignature = JSON.stringify({
        segment: state?.segment?.key || null,
        manualRevision: state?.manualReference?.revision ?? null,
        approvedRevision: state?.manualReference?.approved?.revision ?? null,
        manualEvents: state?.manualEvents || [],
        rejectedManualEvents: state?.rejectedManualEvents || [],
        engineEvents: state?.engineEvents || [],
        suggestions: state?.manualReference?.suggestions || {},
        copilotEvents: state?.copilotEvents || [],
        activity: state?.activity?.state || null,
        activeConversation: state?.activeConversation || null,
        selectedIndex,
        selectedEngineIndex,
        selectedCopilotReferenceIndex
      });
      if (!force && renderSignature === fullscreenEventsRenderSignature) {
        return;
      }
      if (
        !force
        && target.contains(document.activeElement)
        && document.activeElement.matches("[data-manual-time]")
      ) return;
      const openManualEditors = new Set(
        Array.from(
          target.querySelectorAll(".manual-editor-details[open]")
        ).map(editor => editor.dataset.manualEditor)
      );
      const rows = comparisonRows();
      const totals = rows.reduce(
        (counts, row) => {
          counts[row.status] += 1;
          return counts;
        },
        {
          matched: 0,
          reviewed: 0,
          stoppage: 0,
          off: 0,
          "manual-rejected": 0
        }
      );
      const summary = document.getElementById("comparison-summary");
      const manualCounts = (state?.manualEvents || []).reduce(
        (counts, event) => {
          counts[event.team + ":" + event.type] =
            (counts[event.team + ":" + event.type] || 0) + 1;
          return counts;
        },
        {}
      );
      const automaticMatchCount = Object.keys(
        state?.manualReference?.suggestions || {}
      ).length;
      const summaryItems = reviewWorkflow.key === "innovation"
        ? [
            ["matched", "Black: "
              + (manualCounts["black:completed_pass"] || 0) + " passes, "
              + (manualCounts["black:turnover"] || 0) + " turnovers"],
            ["reviewed", "White/red: "
              + (manualCounts["red:completed_pass"] || 0) + " passes, "
              + (manualCounts["red:turnover"] || 0) + " turnovers"],
            ["stoppage", automaticMatchCount + " automatic matches (±1s)"],
            [
              "off",
              totals.off + " missing/extra"
                + (
                  totals["manual-rejected"]
                    ? " · " + totals["manual-rejected"] + " rejected M#"
                    : ""
                )
            ]
          ]
        : [
          ["matched", totals.matched + " synchronized"],
          ["reviewed", totals.reviewed + " confirmed reviewed"],
          ["stoppage", totals.stoppage + " foul/stoppage"],
          ["off", totals.off + " difference" + (totals.off === 1 ? "" : "s")]
        ];
      summary.replaceChildren(
        ...summaryItems.map(([status, text]) => {
          const label = document.createElement("span");
          label.className = status;
          label.textContent = text;
          return label;
        })
      );
      target.replaceChildren(...rows.map(row => {
        const item = document.createElement("div");
        item.className = "comparison-row " + row.status;
        if (
          row.engine
          && row.engineIndex === selectedEngineIndex
        ) {
          item.classList.add("engine-selected");
        }
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
        timeLabel.textContent = reviewSeconds !== undefined
          && engineSeconds !== undefined
          ? reviewSeconds.toFixed(3) + "s / " + engineSeconds.toFixed(3)
            + "s · Δ" + (engineSeconds - reviewSeconds >= 0 ? "+" : "")
            + (engineSeconds - reviewSeconds).toFixed(3) + "s"
          : Number(reviewSeconds ?? engineSeconds).toFixed(3) + "s · frame "
            + Math.round(Number(reviewSeconds ?? engineSeconds) * 25);
        seconds.append(timeLabel);
        item.append(
          comparisonReviewCell(row),
          seconds,
          comparisonEngineCell(row)
        );
        return item;
      }));
      openManualEditors.forEach(manualKey => {
        const editor = target.querySelector(
          '[data-manual-editor="' + manualKey + '"]'
        );
        if (editor) editor.open = true;
      });
      fullscreenEventsRenderSignature = renderSignature;
      const copilotReferenceItems = document.getElementById(
        "copilot-reference-items"
      );
      if (copilotReferenceItems) {
        const hasCopilotReference = Boolean(state?.copilotEvents?.length);
        if (!hasCopilotReference) {
          setCopilotReferenceVisible(false);
        }
        copilotReferenceItems.replaceChildren(...(
          state?.copilotEvents || []
        ).map(
          (event, eventIndex) => {
            const closestManual = (state?.manualEvents || []).reduce(
              (closest, manual, manualIndex) => {
                const delta = Math.abs(
                  Number(manual.seconds) - Number(event.seconds)
                );
                return closest === null || delta < closest.delta
                  ? {event: manual, index: manualIndex, delta}
                  : closest;
              },
              null
            );
            const item = document.createElement("button");
            item.type = "button";
            item.className = "copilot-reference-event"
              + (
                eventIndex === selectedCopilotReferenceIndex
                  ? " current"
                  : ""
              );
            item.dataset.eventSeconds = String(event.seconds);
            item.dataset.eventSource = "copilot-reference";
            item.dataset.eventIndex = String(eventIndex);
            const label = document.createElement("span");
            label.className = "copilot-reference-label";
            label.textContent = event.key + " · " + event.seconds.toFixed(3)
              + "s · " + canonicalComparisonLabel(event);
            item.append(label);
            if (closestManual) {
              const closestTag = document.createElement("span");
              closestTag.className = "copilot-closest-manual-tag";
              closestTag.textContent = "Closest "
                + (closestManual.event.key || "M" + (closestManual.index + 1));
              item.append(closestTag);
            }
            item.title = event.key + " · frame "
              + Math.round(event.seconds * 25) + " · "
              + canonicalComparisonLabel(event)
              + (
                closestManual
                  ? " · closest to "
                    + (
                      closestManual.event.key
                      || "M" + (closestManual.index + 1)
                    )
                    + " by " + closestManual.delta.toFixed(3) + "s"
                  : ""
              )
              + " · diagnostic only";
            item.addEventListener("click", () => {
              selectedCopilotReferenceIndex = eventIndex;
              seekVideo(event.seconds);
              renderFullscreenEvents();
            });
            return item;
          }
        ));
      }
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
      if (
        draft.source === "copilot_review"
        && Number(draft.reviewProtocolVersion || 1) < 5
      ) {
        return {
          label: "Legacy Copilot review · rerun required",
          short: "Legacy C#",
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

    function currentZoomFocus() {
      const selectedEngine = selectedEngineIndex === null
        ? null
        : state?.engineEvents?.[selectedEngineIndex];
      const points = ballTrack?.states || [];
      if (selectedEngine && points.length && ballTrack?.width && ballTrack?.height) {
        const targetFrame = Math.round(
          selectedEngine.seconds * Number(ballTrack.fps || REVIEW_FPS)
        );
        const point = points.reduce((nearest, candidate) =>
          Math.abs(candidate.frame - targetFrame)
            < Math.abs(nearest.frame - targetFrame)
            ? candidate
            : nearest
        );
        return {
          xPercent: point.x / ballTrack.width * 100,
          yPercent: point.y / ballTrack.height * 100,
        };
      }
      return currentDraft()?.actionFocus || null;
    }

    function currentAppliedZoom() {
      return actionZoom ? Math.max(2.35, manualZoom) : manualZoom;
    }

    function clampVideoPan(appliedZoom, focus) {
      if (appliedZoom <= 1) {
        videoPanX = 0;
        videoPanY = 0;
        return;
      }
      const width = videoMedia.clientWidth;
      const height = videoMedia.clientHeight;
      const originX = width * Number(focus?.xPercent ?? 50) / 100;
      const originY = height * Number(focus?.yPercent ?? 50) / 100;
      videoPanX = Math.min(
        (appliedZoom - 1) * originX,
        Math.max(
          -(appliedZoom - 1) * (width - originX),
          videoPanX
        )
      );
      videoPanY = Math.min(
        (appliedZoom - 1) * originY,
        Math.max(
          -(appliedZoom - 1) * (height - originY),
          videoPanY
        )
      );
    }

    function applyActionZoom() {
      const draft = currentDraft();
      const focus = currentZoomFocus();
      const button = document.getElementById("zoom-action");
      button.disabled = !focus;
      if (!focus) actionZoom = false;
      videoShell.classList.toggle("action-zoom", actionZoom);
      videoZoomLayer.style.transformOrigin = focus
        ? focus.xPercent.toFixed(2) + "% " + focus.yPercent.toFixed(2) + "%"
        : "50% 50%";
      const appliedZoom = currentAppliedZoom();
      clampVideoPan(appliedZoom, focus);
      videoMedia.classList.toggle("zoomed", appliedZoom > 1);
      videoZoomLayer.style.transform =
        "translate3d(" + videoPanX.toFixed(1) + "px, "
        + videoPanY.toFixed(1) + "px, 0) scale("
        + appliedZoom.toFixed(2) + ")";
      document.getElementById("video-zoom-level").textContent =
        manualZoom.toFixed(manualZoom % 1 ? 1 : 0) + "×";
      document.getElementById("zoom-out").disabled = manualZoom <= 1;
      document.getElementById("zoom-in").disabled = manualZoom >= 6;
      button.textContent = actionZoom
        ? "Reset Action Zoom"
        : "Zoom to " + (
          selectedEngineIndex === null
            ? "C" + (selectedIndex + 1)
            : "E" + (selectedEngineIndex + 1)
        ) + " Action";
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
      document.getElementById("cancel-copilot-review").hidden = !(
        state.activeConversation
        || state.automaticCopilotReview?.status === "reviewing"
      );
      const coordinateGateVerified =
        state.coordinateReview?.status === "verified";
      document.getElementById(
        "proceed-after-coordinate-gate"
      ).hidden = !coordinateGateVerified;
      const continueCoordinateReview = document.getElementById(
        "continue-coordinate-review"
      );
      continueCoordinateReview.hidden = !coordinateGateVerified;
      const latestCompletedCoordinateBatch = [
        ...(state.coordinateReview?.batches || [])
      ].reverse().find(batch => batch.status === "done");
      const leftoverCoordinateFrames = new Set([
        ...(latestCompletedCoordinateBatch?.unresolvedFrames || []),
        ...(latestCompletedCoordinateBatch?.regressionFrames || [])
      ]).size;
      continueCoordinateReview.hidden =
        !coordinateGateVerified || !leftoverCoordinateFrames;
      continueCoordinateReview.textContent =
        "Improve coverage: review " + leftoverCoordinateFrames
        + " leftover frames";
      const chatStatus = document.getElementById("chat-status");
      const eventActive = current.state === "working"
        && state.activeConversation?.eventIndex === selectedIndex;
      chatStatus.dataset.state = eventActive ? "working" : "ready";
      chatStatus.textContent = eventActive
        ? current.label + "…"
        : currentDraft()?.decision?.status === "accepted"
          ? "Accepted · adjustment only"
          : currentDraft()?.decision?.status === "rejected"
            ? "Rejected · adjustment only"
          : "Ready";
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
                  "Verify and accept C#. The matching E# means no engine "
                    + "change or regression run is needed."
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
      renderManualLedgerAudit();
      document.getElementById("engine-output-notice").hidden =
        state.engineDisplayMode !== "regression_candidate";
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
      acceptAll.hidden = reviewWorkflow.key === "innovation"
        || !hasDraft || lockedReference || remainingCount === 0;
      acceptAll.disabled = reviewBusy || remainingCount === 0;
      acceptAll.textContent = remainingCount
        ? "Verify & Accept All " + remainingCount + " Remaining Events (Autopilot)"
        : "All Events Accepted";
      document.getElementById("proposal").hidden = !hasDraft;
      document.getElementById("empty-review").hidden = hasDraft;
      document.getElementById("composer").hidden = !hasDraft;
      if (reviewWorkflow.key === "innovation") {
        document.getElementById("proposal").hidden = true;
        document.getElementById("composer").hidden = true;
        const approved = Boolean(state.manualReference?.approved);
        const comparisonRevealed = Boolean(
          state.manualReference?.comparisonRevealed
        );
        const approveMinute = document.getElementById("approve-manual-minute");
        const referenceState = state.publication?.published
          ? "published"
          : approved
            ? "frozen"
            : "unfrozen";
        const captureLocked = reviewBusy || approved || lockedReference;
        document.querySelectorAll("[data-manual-team]").forEach(button => {
          button.disabled = captureLocked;
          button.title = lockedReference
            ? "This Passed segment is published and locked."
            : approved
              ? "Reopen the frozen M# reference before changing it."
              : reviewBusy
                ? "Wait for the active review request to finish."
                : "Capture this M# at the current video time.";
        });
        approveMinute.hidden = false;
        approveMinute.disabled =
          approved
          || Math.round(Number(state.segment.durationSeconds) * 1000) !== 60000;
        approveMinute.dataset.referenceState = referenceState;
        approveMinute.textContent = referenceState === "published"
          ? "Passed segment locked"
          : approved
            ? "M# reference frozen"
            : "Freeze manual M# reference as golden";
        document.getElementById("reopen-manual-minute").hidden =
          !approved || lockedReference;
        const validateEngine = document.getElementById(
          "validate-engine-reference"
        );
        validateEngine.hidden = false;
        validateEngine.disabled =
          !approved || comparisonRevealed || reviewBusy;
        const publishPassed = document.getElementById(
          "publish-passed-segment"
        );
        publishPassed.hidden = false;
        publishPassed.disabled =
          reviewBusy || !Boolean(state.publication?.ready);
        publishPassed.title = state.publication?.ready
          ? "Run the final publication gate and lock this Passed segment"
          : (state.publication?.blockers || []).join(" ");
        const goldenStatus = document.getElementById("golden-workflow-status");
        goldenStatus.dataset.referenceState = referenceState;
        if (!goldenStatus.textContent.trim()) {
          goldenStatus.textContent = state.publication?.published
            ? "Passed segment published and locked. Select an unpublished "
              + "prepared segment to capture a new manual M# reference."
            : comparisonRevealed
              ? "Engine comparison revealed. Resolve every mismatch before publication."
              : approved
                ? "Golden M# is frozen. Validate to reveal E#."
                : "Complete M#, then freeze the golden reference.";
        }
        if (
          validateGoldenAfterEngineRun
          && state.segment.state === "ready"
          && !reviewBusy
        ) {
          validateGoldenAfterEngineRun = false;
          queueMicrotask(() => void requestGoldenValidation());
        }
      }
      const publishReference = document.getElementById("publish-reference");
      publishReference.hidden = !canPublish;
      publishReference.disabled = reviewBusy;
      publishReference.textContent = reviewWorkflow.key === "innovation"
        ? "Publish Passed segment"
        : "Publish Validated Reference (Autopilot)";
      publishReference.title = state.publication?.regressionFresh
        ? "Run the final exact-match gate and publish this reference"
        : "Run protected regressions, then publish only if every gate passes";
      const fullscreenDecision = draft?.decision?.status;
      const selectedEngine = selectedEngineIndex === null
        ? null
        : state.engineEvents?.[selectedEngineIndex];
      document.getElementById("proposal").hidden =
        reviewWorkflow.key === "innovation"
        || !hasDraft || Boolean(selectedEngine);
      document.getElementById("empty-review").hidden =
        hasDraft || Boolean(selectedEngine);
      document.getElementById("composer").hidden =
        reviewWorkflow.key === "innovation"
        || !hasDraft || Boolean(selectedEngine);
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
      const selectedConversation = (state.conversation || []).filter(
        message => selectedEngine
          ? message.engineIndex === selectedEngineIndex
          : message.eventIndex === selectedIndex
      );
      document.getElementById("fullscreen-event-chat").hidden =
        reviewWorkflow.key === "innovation"
        && !selectedEngine
        && selectedConversation.length === 0;
      document.getElementById("fullscreen-send-message").hidden =
        reviewWorkflow.key === "innovation" && !selectedEngine;
      document.getElementById("fullscreen-message").hidden =
        reviewWorkflow.key === "innovation" && !selectedEngine;
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
        (reviewWorkflow.key === "innovation" && !selectedEngine)
        || (referenceLocked() && !regressionCandidateReviewActive())
        || (
          selectedEngine
            ? false
            : !hasDraft
              || (Boolean(fullscreenDecision) && !acceptedNeedsEngineRecheck)
        );
      const savedReviewerVerdict = selectedEngine?.review?.userVerdict
        || (selectedEngine?.review?.userClaimedCorrect ? "correct" : "");
      fullscreenPrimary.disabled =
        reviewBusy || (Boolean(selectedEngine) && !savedReviewerVerdict);
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
      if (selectedEngine && !savedReviewerVerdict) {
        fullscreenPrimary.textContent = "Choose Your Verdict First";
      } else if (selectedEngine && savedReviewerVerdict === "incorrect") {
        fullscreenPrimary.textContent =
          "Confirm Incorrect & Diagnose Engine (Autopilot)";
      } else if (selectedEngine && savedReviewerVerdict === "unsure") {
        fullscreenPrimary.textContent =
          "Ask Copilot to Adjudicate E" + (selectedEngineIndex + 1)
          + " (Autopilot)";
      }
      const fullscreenAdjust = document.getElementById("fullscreen-adjust");
      fullscreenAdjust.hidden = reviewWorkflow.key === "innovation"
        || Boolean(selectedEngine) || !hasDraft;
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
            ? selectedEngine.review?.userVerdict
              ? selectedEngine.review?.status === "confirmed"
                && selectedEngine.review.fresh
                ? "Reviewer verdict: "
                  + selectedEngine.review.userVerdict
                  + " · Copilot confirmed"
                : selectedEngine.review?.status === "not_confirmed"
                  && selectedEngine.review.fresh
                  ? "Reviewer verdict: "
                    + selectedEngine.review.userVerdict
                    + " · Copilot not confirmed"
                  : "Reviewer verdict: "
                    + selectedEngine.review.userVerdict
                    + " · Copilot review stale"
            : selectedEngine.review?.status === "confirmed"
              && selectedEngine.review.fresh
              ? "Confirmed reviewed"
              : selectedEngine.review?.status === "not_confirmed"
                && selectedEngine.review.fresh
                ? selectedEngine.review.userVerdict === "incorrect"
                  ? "Incorrect · no such event occurred"
                  : "Not confirmed · unsupported"
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
                ? selectedEngine.review.userVerdict === "incorrect"
                  ? "The professional reviewer determined that this exact E# did not occur. It remains visible only as rejected engine output until a general engine correction removes it."
                  : "This exact E# was independently reviewed and not confirmed. It remains visible as engine output; a corrected C# requires separate Add as Review Event confirmation."
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
          emptyDetail.textContent = reviewWorkflow.key === "innovation"
            ? state.segment.evidenceReady
              ? "Frozen BAC coordinates and YOLO player context are ready. "
                + "Run the Innovation rules engine when you want event "
                + "processing to begin."
              : "The video is prepared. Prepare frozen BAC coordinates and "
                + "YOLO player context first; preparation alone never creates "
                + "football events."
            : "The video is prepared. Click Start AI when you want event "
              + "processing to begin; preparation alone never starts it.";
        }
        renderActivity();
        renderMessages();
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
        (
          Number.isFinite(Number(draft.releaseSeconds))
            ? "release " + Number(draft.releaseSeconds).toFixed(3) + "s"
              + " · frame " + Math.round(Number(draft.releaseSeconds) * 25)
              + " → completion "
            : ""
        )
        + draft.seconds.toFixed(3) + "s · frame "
        + Math.round(draft.seconds * 25);
      document.getElementById("proposal-evidence").textContent = [
        draft.evidence,
        draft.senderEvidence
          ? "Sender / prior owner: " + draft.senderEvidence
          : null,
        draft.receiverEvidence
          ? "Receiver control: " + draft.receiverEvidence
          : null,
        draft.matchStateEvidence
          ? "Match state: " + draft.matchStateEvidence
          : null
      ].filter(Boolean).join(" ");
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
        reviewWorkflow.conversationPrefix + selectedReference;
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
        ? "Accept " + selectedReference + " · E# Already Matches"
        : "Accept " + selectedReference + " & Check Engine";
      document.getElementById("adjust").textContent =
        "Request " + selectedReference + " Adjustment";
      document.getElementById("reject").textContent =
        "Reject " + selectedReference + " Proposal";
      document.getElementById("send-message").textContent =
        "Ask Copilot about " + selectedReference + " (Plan mode)";
      document.getElementById("copilot-accept").textContent = matchedEngine
        ? "Verify & Accept " + selectedReference
          + " · No Engine Change (Autopilot)"
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
      syncEngineVerificationModal();
      syncManualEngineReviewModal();
      applyPassedSegmentLock();
      renderCopilotSessionStatus();
      renderCoordinationStatus();
      applyCoordinationLock();
      syncCoordinationTimers();
    }

    let stateRefreshPending = false;
    let stateRefreshQueued = false;
    let stateRefreshPromise = null;

    async function showPublishedSegmentOverview() {
      video.pause();
      if (document.fullscreenElement === videoShell) {
        try {
          await document.exitFullscreen();
        } catch (error) {
          document.getElementById("publication-status").textContent =
            "Published, but the browser could not leave full screen: "
            + error.message;
        }
      }
      const sharedReviewPanel =
        document.getElementById("shared-review-panel");
      sharedReviewPanel.open = true;
      requestAnimationFrame(() => {
        sharedReviewPanel.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
        sharedReviewPanel.querySelector("tr.selected")?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
      });
    }

    async function loadState(queueIfPending = true) {
      if (stateRefreshPromise) {
        if (queueIfPending) stateRefreshQueued = true;
        return stateRefreshPromise;
      }
      stateRefreshPending = true;
      stateRefreshPromise = (async () => {
        try {
          do {
          stateRefreshQueued = false;
          const previousSegmentKey = state?.segment?.key || null;
          const previousSegmentReady = state?.segment?.state === "ready";
          const previousReferenceLocked = Boolean(
            state?.publication?.published
            || state?.segment?.validationStatus === "passed"
          );
          const requestedSegmentKey = selectedSegmentKey();
          const url = stateUrl + "?segment=" +
            encodeURIComponent(requestedSegmentKey) +
            "&hostInstanceId=" + encodeURIComponent(hostInstanceId);
          const response = await fetch(url, { cache: "no-store" });
          if (!response.ok) throw new Error("State HTTP " + response.status);
          const previousActiveBatchId =
            state?.coordinateReview?.activeBatchId || null;
          const nextState = await response.json();
          if (selectedSegmentKey() !== requestedSegmentKey) {
            stateRefreshQueued = true;
            continue;
          }
          state = nextState;
          const referenceJustPublished = Boolean(
            previousSegmentKey === state.segment.key
            && !previousReferenceLocked
            && (
              state.publication?.published
              || state.segment.validationStatus === "passed"
            )
          );
          localStorage.setItem(
            workflowSegmentStorageKey(reviewWorkflow.key),
            state.segment.key
          );
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
          const ballStatesAvailable =
            state.segment.ballTrackAvailable && !segmentRunActive();
          if (!ballStatesAvailable) {
            ballTrack = null;
            ballTrackSegmentKey = null;
          } else if (ballTrackSegmentKey !== state.segment.key) {
            const ballResponse = await fetch(
              "/api/ball-track?segment=" +
              encodeURIComponent(state.segment.key),
              {cache: "no-store"}
            );
            ballTrack = ballResponse.ok ? await ballResponse.json() : null;
            ballTrackSegmentKey = state.segment.key;
            const activeCoordinateBatch =
              state.coordinateReview?.batches?.find(
                candidate =>
                  candidate.id === state.coordinateReview?.activeBatchId
              );
            document.getElementById("ball-frame-filter").value =
              activeCoordinateBatch?.status === "ready"
                ? "flagged"
              : state.ballRecoveryDiagnostic?.status === "focused_unpersisted"
                ? "diagnostic"
                : state.segment.state === "failed" ? "estimated" : "all";
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
          if (referenceJustPublished) {
            await showPublishedSegmentOverview();
          }
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
      })();
      try {
        return await stateRefreshPromise;
      } finally {
        stateRefreshPromise = null;
      }
    }

    async function sendClipMessage(mode = "plan") {
      const noteInput = document.getElementById("clip-message");
      const status = document.getElementById("publication-status");
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
      textareaId = null,
      requireReviewerVerdict = true,
      reviewChoice = null
    ) {
      const status = document.getElementById(statusId);
      const engine = state.engineEvents?.[engineIndex];
      const textarea = textareaId
        ? document.getElementById(textareaId)
        : null;
      const reviewFocus = [
        textarea?.value.trim() || "",
        reviewChoice?.note || ""
      ].filter(Boolean).join(" ");
      const userClaim = document.getElementById("engine-user-claim");
      const userVerdict = reviewChoice
        ? reviewChoice.userVerdict
        : requireReviewerVerdict && !userClaim?.hidden
          ? document.querySelector(
              "[name=engine-user-verdict]:checked"
            )?.value || null
          : null;
      if (requireReviewerVerdict && !userVerdict) {
        status.textContent =
          "Choose Correct, Incorrect, or Unsure before continuing.";
        document.querySelector("[name=engine-user-verdict]")?.focus();
        return;
      }
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
            userVerdict,
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

    function selectedEngineVerificationDecision() {
      return document.querySelector(
        "[name=engine-verification-decision]:checked"
      )?.value || null;
    }

    function renderSimilarReviewChoices(groupId, listId, choices) {
      const group = document.getElementById(groupId);
      const list = document.getElementById(listId);
      list.replaceChildren();
      choices.forEach(choice => {
        const label = document.createElement("label");
        label.className = "similar-review-item";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = Boolean(choice.selected);
        input.disabled = Boolean(choice.selected);
        input.dataset.primaryTarget = choice.selected ? "true" : "false";
        input.dataset.batchIndex = String(choice.index);
        input.addEventListener("change", () => {
          updateEngineVerificationActions();
          updateManualEngineReviewActions();
        });
        const content = document.createElement("span");
        const title = document.createElement("strong");
        title.textContent = choice.reference + " · " + choice.team;
        const detail = document.createElement("small");
        detail.textContent = Number(choice.seconds).toFixed(3) + "s";
        content.append(title, detail);
        label.append(input, content);
        list.append(label);
      });
      group.hidden = choices.length < 2;
    }

    function selectedSimilarReviewIndices(listId) {
      return Array.from(
        document.querySelectorAll(
          "#" + listId + " input[data-batch-index]:checked"
        )
      ).map(input => Number(input.dataset.batchIndex));
    }

    function setSimilarReviewChoicesDisabled(listId, disabled) {
      document.querySelectorAll(
        "#" + listId + " input[data-batch-index]"
      ).forEach(input => {
        input.disabled = disabled || input.dataset.primaryTarget === "true";
      });
    }

    function selectedEngineBatchIndices() {
      const selected = selectedSimilarReviewIndices(
        "engine-similar-review-list"
      );
      return selected.length ? selected : [verificationModalEngineIndex];
    }

    function selectedManualBatchIndices() {
      const selected = selectedSimilarReviewIndices(
        "manual-similar-review-list"
      );
      return selected.length ? selected : [manualEngineReviewIndex];
    }

    function updateEngineVerificationActions() {
      const decision = selectedEngineVerificationDecision();
      const batchCount = selectedEngineBatchIndices().filter(
        Number.isInteger
      ).length;
      const timePanel = document.getElementById("engine-verification-time");
      const confirm = document.getElementById(
        "confirm-engine-without-copilot"
      );
      const guidance = document.getElementById(
        "engine-verification-guidance"
      );
      confirm.disabled = !["correct", "details_wrong", "incorrect"].includes(
        decision
      );
      timePanel.hidden = decision !== "details_wrong" || batchCount > 1;
      confirm.textContent = decision === "correct"
        ? batchCount > 1
          ? "Approve " + batchCount + " exact E# events without Copilot"
          : "Approve exact E# without Copilot"
        : decision === "details_wrong"
          ? "Send " + batchCount + " E# correction"
          : decision === "incorrect"
              ? batchCount > 1
                ? "Reject " + batchCount + " E# & fix engine"
                : "Reject E# & fix engine"
            : "Choose a decision";
      document.getElementById("ask-copilot-engine-review").textContent =
        batchCount > 1
          ? "Ask Copilot to review " + batchCount + " similar E# events once"
          : "Ask Copilot to review";
      guidance.textContent = decision === "correct"
        ? "Your professional review can approve this existing E# without "
          + "Copilot, an engine check, or a regression run."
        : decision === "details_wrong"
          ? batchCount > 1
            ? "The same details-wrong verdict applies to every checked E#. "
              + "Corrected times remain event-specific, so no single shared "
              + "replacement time is sent. Copilot will diagnose them in one "
              + "request and run one final cached rebuild and regression gate."
            : "Reject this exact E# and review only this discrepancy. Copilot "
              + "will diagnose a general fix, rerun cached engine output, and "
              + "replace the old E# list after protected tests pass."
          : decision === "incorrect"
            ? "Reject this exact E# and review only this discrepancy. Copilot "
              + "will diagnose a general fix, rerun cached engine output, and "
              + "replace the old E# list after protected tests pass."
            : decision === "cannot_verify"
              ? "Copilot may inspect the targeted prepared context, but it "
                + "must leave the E# unconfirmed if evidence remains insufficient."
              : "Choose an evidence decision, or ask Copilot for an "
                + "independent review without stating a verdict.";
    }

    function openEngineVerificationModal(engineIndex) {
      const engine = state.engineEvents?.[engineIndex];
      if (!engine) return;
      verificationModalEngineIndex = engineIndex;
      document.querySelectorAll(
        "[name=engine-verification-decision]"
      ).forEach(input => {
        input.checked = false;
        input.disabled = false;
      });
      document.getElementById("engine-verification-title").textContent =
        "Review E" + (engineIndex + 1) + " before continuing";
      document.getElementById("engine-verification-event").textContent =
        canonicalComparisonLabel(engine) + " at "
        + Number(engine.seconds).toFixed(3) + "s";
      document.getElementById("engine-check-seconds").value = "";
      document.getElementById("engine-verification-time").hidden = true;
      document.getElementById("engine-check-time-status").textContent =
        "Use this only when the E# completion time is wrong. Previewing does "
        + "not change M# or E#; the time is sent to Copilot with the "
        + "correction request.";
      const reviewableEngineIndices = reviewWorkflow.key === "innovation"
        ? new Set(
            innovationComparisonRows()
              .filter(row => row.engine && !row.review)
              .map(row => row.engineIndex)
          )
        : new Set();
      const similarChoices = reviewWorkflow.key === "innovation"
        ? (state.engineEvents || [])
            .map((candidate, index) => ({candidate, index}))
            .filter(({candidate, index}) =>
              candidate.type === engine.type
              && (
                index === engineIndex
                || (
                  reviewableEngineIndices.has(index)
                  && !(
                    candidate.review?.status === "confirmed"
                    && candidate.review?.fresh
                  )
                )
              )
            )
            .map(({candidate, index}) => ({
              index,
              selected: index === engineIndex,
              reference: "E" + (index + 1),
              team: teamLabel(candidate.team),
              seconds: candidate.seconds,
            }))
        : [];
      renderSimilarReviewChoices(
        "engine-similar-review-group",
        "engine-similar-review-list",
        similarChoices
      );
      updateEngineVerificationActions();
      const modal = document.getElementById("engine-verification-modal");
      modal.dataset.reviewState = "ready";
      document.getElementById("ask-copilot-engine-review").disabled = false;
      document.getElementById("cancel-engine-verification").disabled = false;
      document.getElementById("cancel-engine-verification").textContent =
        "Close";
      if (!modal.open) modal.showModal();
      document.querySelector(
        "[name=engine-verification-decision]"
      )?.focus();
    }

    function dismissCompletedSegmentOverlay() {
      const overlay = document.getElementById("segment-loading-overlay");
      const closeButton = document.getElementById("segment-loading-close");
      if (overlay.hidden || closeButton.hidden) return;
      analysisModalMode = null;
      regressionDashboardOpen = false;
      clearTimeout(regressionDashboardCloseTimer);
      regressionDashboardCloseTimer = null;
      setSegmentLoading(false);
    }

    function closeEngineVerificationModal() {
      const modal = document.getElementById("engine-verification-modal");
      if (modal.open) modal.close();
      verificationModalEngineIndex = null;
      dismissCompletedSegmentOverlay();
    }

    function setEngineVerificationWorking(engineIndex) {
      if (!engineVerificationPending) {
        const engine = state.engineEvents?.[engineIndex];
        engineVerificationPending = {
          engineIndex,
          identity: engine
            ? {
                team: engine.team,
                type: engine.type,
                seconds: Number(engine.seconds),
                releaseSeconds: Number(engine.releaseSeconds),
              }
            : null,
        };
      }
      verificationModalEngineIndex = engineIndex;
      const modal = document.getElementById("engine-verification-modal");
      modal.dataset.reviewState = "working";
      document.querySelectorAll(
        "[name=engine-verification-decision]"
      ).forEach(input => {
        input.disabled = true;
      });
      setSimilarReviewChoicesDisabled(
        "engine-similar-review-list",
        true
      );
      document.getElementById("confirm-engine-without-copilot").disabled =
        true;
      document.getElementById("ask-copilot-engine-review").disabled = true;
      const cancel = document.getElementById("cancel-engine-verification");
      cancel.textContent = "Copilot is working…";
      cancel.disabled = true;
      document.getElementById("engine-verification-guidance").textContent =
        "Copilot is working… Reviewing E" + (engineIndex + 1)
        + ". The rejection is preserved; Cancel review stops only the active "
        + "diagnosis.";
    }

    function resetEngineVerificationControls() {
      const modal = document.getElementById("engine-verification-modal");
      modal.dataset.reviewState = "ready";
      document.querySelectorAll(
        "[name=engine-verification-decision]"
      ).forEach(input => {
        input.disabled = false;
      });
      setSimilarReviewChoicesDisabled(
        "engine-similar-review-list",
        false
      );
      document.getElementById("ask-copilot-engine-review").disabled = false;
      document.getElementById("cancel-engine-verification").textContent =
        "Close";
      updateEngineVerificationActions();
    }

    function syncEngineVerificationModal() {
      const activeEngineReview = state.activeConversation?.engineIndex !== null
        && state.activeConversation?.engineIndex !== undefined
        ? state.activeConversation
        : null;
      const modal = document.getElementById("engine-verification-modal");
      const activeBatch = state.activeDiscrepancyBatch;
      if (
        modal.open
        && activeBatch?.kind === "engine"
        && state.activity?.state === "working"
        && engineVerificationPending?.batchId !== activeBatch.id
      ) {
        const target = activeBatch.targets.find(
          candidate => !candidate.completed
        ) || activeBatch.targets[0];
        engineVerificationPending = {
          engineIndex: Number(target?.originalIndex || 0),
          batchId: activeBatch.id,
          count: activeBatch.targets.length,
          identity: target
            ? {
                team: target.team,
                type: target.type,
                seconds: Number(target.seconds),
                releaseSeconds: Number(target.releaseSeconds),
              }
            : null,
        };
      }
      const sameBatchActive = Boolean(
        engineVerificationPending?.batchId
        && activeBatch?.id === engineVerificationPending.batchId
      );
      if (sameBatchActive && state.activity?.state === "working") {
        setEngineVerificationWorking(engineVerificationPending.engineIndex);
        document.getElementById(
          "engine-verification-guidance"
        ).textContent =
          "Copilot is working… Reviewing "
          + activeBatch.targets.filter(target => !target.completed).length
          + " remaining similar E# events in this one request.";
        return;
      }
      if (
        modal.open
        && modal.dataset.reviewState === "working"
        && state.activity?.state === "ready"
      ) {
        const pending = engineVerificationPending;
        engineVerificationPending = null;
        const refreshedIndex = pending?.identity
          ? state.engineEvents.findIndex(engine =>
              engine.team === pending.identity.team
              && engine.type === pending.identity.type
              && Number(engine.seconds) === pending.identity.seconds
              && Number(engine.releaseSeconds)
                === pending.identity.releaseSeconds
            )
          : -1;
        selectedEngineIndex = refreshedIndex >= 0 ? refreshedIndex : null;
        resetEngineVerificationControls();
        closeEngineVerificationModal();
        renderFullscreenEvents();
        if (selectedEngineIndex !== null) {
          requestAnimationFrame(scrollSelectedComparisonIntoView);
        }
        return;
      }
      if (
        engineVerificationPending?.batchId
        && !sameBatchActive
        && state.activity?.state !== "working"
      ) {
        engineVerificationPending = null;
        resetEngineVerificationControls();
        closeEngineVerificationModal();
        renderFullscreenEvents();
        return;
      }
      if (
        !engineVerificationPending
        && modal.open
        && activeEngineReview
      ) {
        engineVerificationPending = {
          engineIndex: activeEngineReview.engineIndex,
          identity: activeEngineReview.engineIdentity || null,
          reviewKey: activeEngineReview.engineReviewKey || null,
        };
      }
      if (!engineVerificationPending) return;
      const pending = engineVerificationPending;
      const engineIndex = pending.engineIndex;
      const sameReviewActive = Boolean(
        activeEngineReview
        && (
          pending.reviewKey
            ? activeEngineReview.engineReviewKey === pending.reviewKey
            : activeEngineReview.engineIndex === engineIndex
        )
      );
      if (sameReviewActive && state.activity?.state === "working") {
        setEngineVerificationWorking(engineIndex);
        return;
      }
      if (!sameReviewActive && state.activity?.state !== "working") {
        engineVerificationPending = null;
        const refreshedIndex = pending.identity
          ? state.engineEvents.findIndex(engine =>
              engine.team === pending.identity.team
              && engine.type === pending.identity.type
              && Number(engine.seconds) === pending.identity.seconds
              && Number(engine.releaseSeconds)
                === pending.identity.releaseSeconds
            )
          : -1;
        selectedEngineIndex = refreshedIndex >= 0 ? refreshedIndex : null;
        resetEngineVerificationControls();
        closeEngineVerificationModal();
        renderFullscreenEvents();
        if (selectedEngineIndex !== null) {
          requestAnimationFrame(scrollSelectedComparisonIntoView);
        }
        return;
      }
      resetEngineVerificationControls();
      document.getElementById("engine-verification-guidance").textContent =
        state.activity?.state === "error"
          ? state.activity.detail || "The E# review did not complete."
          : "The previous E# review is no longer active. Controls were restored.";
    }

    async function cancelOrCloseEngineVerification() {
      if (!engineVerificationPending) {
        closeEngineVerificationModal();
        return;
      }
      const cancelled = await cancelCopilotReview();
      if (!cancelled) return;
      engineVerificationPending = null;
      resetEngineVerificationControls();
      closeEngineVerificationModal();
    }

    function openManualEngineReviewModal(reviewIndex) {
      const event = state.manualEvents?.[reviewIndex];
      if (!event) return;
      manualEngineReviewIndex = reviewIndex;
      document.querySelectorAll(
        "[name=manual-engine-review-decision]"
      ).forEach(input => {
        input.checked = false;
      });
      document.getElementById("manual-engine-review-title").textContent =
        "Review " + manualDisplayKey(event, reviewIndex)
          + " missing engine event";
      document.getElementById("manual-engine-review-event").textContent =
        canonicalComparisonLabel(event) + " at "
        + Number(event.seconds).toFixed(3) + "s";
      const modal = document.getElementById("manual-engine-review-modal");
      modal.dataset.reviewState = "ready";
      document.querySelectorAll(
        "[name=manual-engine-review-decision]"
      ).forEach(input => {
        input.disabled = false;
      });
      setSimilarReviewChoicesDisabled(
        "manual-similar-review-list",
        false
      );
      const manualReferenceFrozen = Boolean(state.manualReference?.approved);
      document.querySelectorAll("[data-manual-draft-action]").forEach(
        option => {
          option.hidden = manualReferenceFrozen;
        }
      );
      document.getElementById(
        "manual-engine-review-frozen-note"
      ).hidden = !manualReferenceFrozen;
      document.getElementById("close-manual-engine-review").disabled = false;
      const cancel = document.getElementById(
        "cancel-manual-copilot-review"
      );
      cancel.hidden = true;
      cancel.disabled = false;
      const suggestions = state.manualReference?.suggestions || {};
      const similarChoices = reviewWorkflow.key === "innovation"
        ? (state.manualEvents || [])
        .map((candidate, index) => ({candidate, index}))
        .filter(({candidate, index}) =>
          candidate.type === event.type
          && candidate.reviewStatus !== "rejected"
          && (
            index === reviewIndex
            || !suggestions[candidate.key]
          )
        )
            .map(({candidate, index}) => ({
              index,
              selected: index === reviewIndex,
              reference: candidate.key,
              team: teamLabel(candidate.team),
              seconds: candidate.seconds,
            }))
        : [];
      renderSimilarReviewChoices(
        "manual-similar-review-group",
        "manual-similar-review-list",
        similarChoices
      );
      updateManualEngineReviewActions();
      if (!modal.open) modal.showModal();
      document.querySelector(
        "[name=manual-engine-review-decision]"
      )?.focus();
    }

    function closeManualEngineReviewModal() {
      const modal = document.getElementById("manual-engine-review-modal");
      if (modal.open) modal.close();
      manualEngineReviewIndex = null;
      dismissCompletedSegmentOverlay();
    }

    function resetManualEngineReviewControls(message) {
      const modal = document.getElementById("manual-engine-review-modal");
      modal.dataset.reviewState = "ready";
      document.querySelectorAll(
        "[name=manual-engine-review-decision]"
      ).forEach(input => {
        input.disabled = false;
      });
      document.getElementById(
        "cancel-manual-copilot-review"
      ).hidden = true;
      document.getElementById("close-manual-engine-review").disabled = false;
      document.getElementById("manual-engine-review-guidance").textContent =
        message;
      updateManualEngineReviewActions();
    }

    async function cancelManualEngineReview() {
      const cancelled = await cancelCopilotReview();
      if (!cancelled) return;
      manualEngineReviewPending = null;
      document.getElementById(
        "cancel-manual-copilot-review"
      ).hidden = true;
      closeManualEngineReviewModal();
    }

    function syncManualEngineReviewModal() {
      const modal = document.getElementById("manual-engine-review-modal");
      const activeBatch = state.activeDiscrepancyBatch;
      if (
        modal.open
        && activeBatch?.kind === "manual"
        && state.activity?.state === "working"
        && manualEngineReviewPending?.batchId !== activeBatch.id
      ) {
        const target = activeBatch.targets.find(
          candidate => !candidate.completed
        ) || activeBatch.targets[0];
        manualEngineReviewPending = {
          index: Number(target?.originalIndex || 0),
          manualKey: target?.manualKey || null,
          batchId: activeBatch.id,
          count: activeBatch.targets.length,
          identity: target
            ? {
                team: target.team,
                type: target.type,
                seconds: Number(target.seconds),
              }
            : null,
        };
      }
      const sameBatchActive = Boolean(
        manualEngineReviewPending?.batchId
        && activeBatch?.id === manualEngineReviewPending.batchId
      );
      if (sameBatchActive && state.activity?.state === "working") {
        modal.dataset.reviewState = "working";
        setSimilarReviewChoicesDisabled(
          "manual-similar-review-list",
          true
        );
        document.getElementById(
          "manual-engine-review-guidance"
        ).textContent =
          "Copilot is working… Reviewing "
          + activeBatch.targets.filter(target => !target.completed).length
          + " remaining similar M# events in this one request.";
        document.getElementById("close-manual-engine-review").disabled = true;
        document.getElementById(
          "cancel-manual-copilot-review"
        ).hidden = false;
        return;
      }
      if (
        modal.open
        && modal.dataset.reviewState === "working"
        && state.activity?.state === "ready"
      ) {
        const completedKey = manualEngineReviewPending?.manualKey;
        manualEngineReviewPending = null;
        closeManualEngineReviewModal();
        renderFullscreenEvents();
        document.getElementById("fullscreen-chat-status").textContent =
          (completedKey ? completedKey + " review" : "Grouped review")
          + " completed. M#/E# rows refreshed.";
        return;
      }
      if (
        manualEngineReviewPending?.batchId
        && !sameBatchActive
        && state.activity?.state !== "working"
      ) {
        manualEngineReviewPending = null;
        closeManualEngineReviewModal();
        renderFullscreenEvents();
        return;
      }
      const activeManualReview =
        typeof state.activeConversation?.manualReviewKey === "string"
          ? state.activeConversation
          : null;
      if (
        !manualEngineReviewPending
        && modal.open
        && activeManualReview
      ) {
        manualEngineReviewPending = {
          index: activeManualReview.eventIndex,
          manualKey: activeManualReview.manualReviewKey,
          identity: activeManualReview.manualIdentity || null,
        };
      }
      if (!manualEngineReviewPending) {
        if (
          modal.open
          && modal.dataset.reviewState === "working"
          && !activeManualReview
          && state.activity?.state !== "working"
        ) {
          resetManualEngineReviewControls(
            "The previous M# review is no longer active. Controls were restored."
          );
        }
        return;
      }
      const status = document.getElementById(
        "manual-engine-review-guidance"
      );
      const sameReviewActive = Boolean(
        activeManualReview
        && activeManualReview.manualReviewKey
          === manualEngineReviewPending.manualKey
      );
      if (sameReviewActive && state.activity?.state === "working") {
        modal.dataset.reviewState = "working";
        status.textContent =
          "Copilot is working… Reviewing "
          + manualEngineReviewPending.manualKey
          + ". This stays open through diagnosis, cached rebuilding, tests, "
          + "and the final M#/E# refresh.";
        document.getElementById("close-manual-engine-review").disabled = true;
        const cancel = document.getElementById(
          "cancel-manual-copilot-review"
        );
        cancel.hidden = false;
        cancel.disabled = true;
        return;
      }
      if (state.activity?.state === "error") {
        resetManualEngineReviewControls(
          state.activity.detail || "The Copilot review did not complete."
        );
        manualEngineReviewPending = null;
        return;
      }
      if (sameReviewActive) {
        resetManualEngineReviewControls(
          "The M# conversation is retained, but no review is currently active. "
          + "Controls were restored."
        );
        manualEngineReviewPending = null;
        return;
      }
      document.getElementById(
        "cancel-manual-copilot-review"
      ).disabled = true;
      const completedKey = manualEngineReviewPending.manualKey;
      manualEngineReviewPending = null;
      closeManualEngineReviewModal();
      document.getElementById("fullscreen-chat-status").textContent =
        completedKey + " review completed. M#/E# rows refreshed.";
    }

    function selectedManualEngineReviewDecision() {
      return document.querySelector(
        "[name=manual-engine-review-decision]:checked"
      )?.value || null;
    }

    function updateManualEngineReviewActions() {
      const decision = selectedManualEngineReviewDecision();
      const batchCount = selectedManualBatchIndices().filter(
        Number.isInteger
      ).length;
      const button = document.getElementById(
        "ask-copilot-manual-engine-review"
      );
      const guidance = document.getElementById(
        "manual-engine-review-guidance"
      );
      button.disabled = !decision;
      button.textContent = decision === "engine_match_wrong"
        ? "Ask Copilot to correct " + batchCount + " existing E#"
        : decision === "correct"
          ? "Ask Copilot to fix " + batchCount + " missing E#"
        : decision === "details_wrong"
          ? "Open M# editor"
          : decision === "reject"
            ? "Reject M#"
            : decision === "remove"
              ? "Remove M#"
            : decision === "cannot_verify"
              ? "Ask Copilot to adjudicate " + batchCount + " M# once"
              : "Choose a decision";
      guidance.textContent = decision === "engine_match_wrong"
        ? "This accepts M# as the required result. M# stays unchanged while "
          + "Copilot corrects the general cause of the existing E# timing, "
          + "team, or type discrepancy."
        : decision === "correct"
          ? "This accepts M# as the required result. M# stays unchanged while "
            + "Copilot corrects the general cause of the missing E#."
        : decision === "details_wrong"
          ? "Use the compact editor to correct the M# yourself."
          : decision === "reject"
            ? "M# stays visible as rejected for audit, but is excluded from "
              + "matching, golden counts, approval, and publication."
            : decision === "remove"
              ? "This removes an M# entered in error; it does not approve or "
                + "reject any E#."
            : decision === "cannot_verify"
              ? "Copilot will inspect the targeted evidence and must preserve "
                + "uncertainty when the camera is insufficient."
              : "Choose an evidence decision to see the available next action.";
    }

    async function requestManualEngineReview() {
      const index = manualEngineReviewIndex;
      if (!Number.isInteger(index)) return;
      const event = state.manualEvents?.[index];
      const decision = selectedManualEngineReviewDecision();
      if (!event || !decision) return;
      const button = document.getElementById(
        "ask-copilot-manual-engine-review"
      );
      button.disabled = true;
      if (decision === "details_wrong") {
        const manualKey = event.key;
        closeManualEngineReviewModal();
        const editor = document.querySelector(
          '[data-manual-editor="' + manualKey + '"]'
        );
        if (editor) editor.open = true;
        return;
      }
      if (["reject", "remove"].includes(decision)) {
        try {
          await mutateManualReference({
            action: decision === "reject" ? "reject" : "delete",
            manualKey: event.key,
          });
          closeManualEngineReviewModal();
        } catch (error) {
          document.getElementById("fullscreen-chat-status").textContent =
            error.message;
          document.getElementById(
            "manual-engine-review-guidance"
          ).textContent = error.message;
          button.disabled = false;
        }
        return;
      }
      try {
        const batchIndices = selectedManualBatchIndices();
        const modal = document.getElementById("manual-engine-review-modal");
        modal.dataset.reviewState = "working";
        document.querySelectorAll(
          "[name=manual-engine-review-decision]"
        ).forEach(input => {
          input.disabled = true;
        });
        setSimilarReviewChoicesDisabled(
          "manual-similar-review-list",
          true
        );
        document.getElementById(
          "cancel-manual-copilot-review"
        ).hidden = false;
        button.textContent = "Copilot is working…";
        document.getElementById("manual-engine-review-guidance").textContent =
          "Starting the targeted review. Keep this maximized view open; the "
          + "event rows will refresh automatically.";
        const batchReview = batchIndices.length > 1;
        const response = await fetch(
          batchReview
            ? "/api/copilot-review-discrepancy-batch"
            : "/api/copilot-review-manual-engine",
          {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(batchReview
              ? {
                  segment: selectedSegmentKey(),
                  kind: "manual",
                  indices: batchIndices,
                  userVerdict: decision === "engine_match_wrong"
                    ? "engine_match_wrong"
                    : decision === "correct"
                      ? "correct"
                      : "unsure",
                }
              : {
                  segment: selectedSegmentKey(),
                  index,
                  manualKey: event.key,
                  userVerdict: decision === "engine_match_wrong"
                    ? "engine_match_wrong"
                    : decision === "correct"
                      ? "correct"
                      : "unsure",
                }),
          }
        );
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not start M# engine review");
        }
        manualEngineReviewPending = {
          index,
          manualKey: result.manualKey || event.key,
          batchId: result.batchId || null,
          count: result.count || 1,
        };
        await loadState();
      } catch (error) {
        document.getElementById(
          "manual-engine-review-modal"
        ).dataset.reviewState = "ready";
        document.getElementById("fullscreen-chat-status").textContent =
          error.message;
        document.getElementById("manual-engine-review-guidance").textContent =
          error.message;
        document.querySelectorAll(
          "[name=manual-engine-review-decision]"
        ).forEach(input => {
          input.disabled = false;
        });
        document.getElementById(
          "cancel-manual-copilot-review"
        ).hidden = true;
        button.disabled = false;
        updateManualEngineReviewActions();
      }
    }

    async function confirmEngineWithoutCopilot() {
      const engineIndex = verificationModalEngineIndex;
      const batchIndices = selectedEngineBatchIndices();
      const decision = selectedEngineVerificationDecision();
      if (
        !["correct", "details_wrong", "incorrect"].includes(decision)
        || !Number.isInteger(engineIndex)
      ) return;
      const confirm = document.getElementById(
        "confirm-engine-without-copilot"
      );
      confirm.disabled = true;
      try {
        const approving = decision === "correct";
        if (!approving) {
          const checkSeconds = decision === "details_wrong"
            ? engineVerificationCheckTime()
            : null;
          const checkNote = checkSeconds === null
            ? ""
            : " Inspect the reviewer-supplied alternative completion time "
              + checkSeconds.toFixed(3) + "s without changing M#.";
          const guidance = document.getElementById(
            "engine-verification-guidance"
          );
          guidance.textContent =
            "Starting the targeted E" + (engineIndex + 1)
            + " rejection review…";
          const batchReview = batchIndices.length > 1;
          const response = await fetch(
            batchReview
              ? "/api/copilot-review-discrepancy-batch"
              : "/api/copilot-verify-engine",
          {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
              segment: selectedSegmentKey(),
              ...(batchReview
                ? {kind: "engine", indices: batchIndices}
                : {index: engineIndex}),
              userVerdict: "incorrect",
              note: decision === "details_wrong"
                ? "The reviewer rejects each exact E# because the event exists "
                  + "but its team, canonical event type, or completion time "
                  + "is wrong. Diagnose and fix the general engine rule, "
                  + "rerun cached output, and replace the old E# list."
                  + checkNote
                : "The reviewer rejects each exact E# because no such event "
                  + "occurred. Diagnose and fix the general engine rule, "
                  + "rerun cached output, and replace the old E# list."
                  + checkNote
            }),
          });
          const result = await response.json();
          if (!response.ok) {
            throw new Error(
              result.error || "Could not start engine-event rejection review"
            );
          }
          setEngineVerificationWorking(engineIndex);
          const status = document.getElementById("fullscreen-chat-status");
          status.textContent =
            batchReview
              ? batchIndices.length
                + " similar E# rejection reviews started in one Copilot request."
              : "E" + (engineIndex + 1)
                + " rejection review started. Copilot is inspecting only this "
                + "discrepancy.";
          try {
            await loadState();
          } catch (stateError) {
            status.textContent =
              "E" + (engineIndex + 1)
              + " rejection review started, but the immediate Canvas refresh "
              + "was delayed (" + stateError.message
              + "). The automatic refresh will retry.";
          }
          return;
        }
        for (const index of batchIndices) {
          const response = await fetch("/api/reviewer-confirm-engine", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
              segment: selectedSegmentKey(),
              index,
              userVerdict: decision
            })
          });
          const result = await response.json();
          if (!response.ok) {
            throw new Error(result.error || "Could not confirm engine event");
          }
        }
        closeEngineVerificationModal();
        await loadState();
        document.getElementById("fullscreen-chat-status").textContent =
          (batchIndices.length > 1
            ? batchIndices.length + " E# events"
            : "E" + (engineIndex + 1))
          + " approved from your professional review."
          + " No Copilot, engine check, or regression run was needed.";
      } catch (error) {
        document.getElementById("engine-verification-guidance").textContent =
          error.message;
        confirm.disabled = false;
      }
    }

    async function askCopilotFromEngineVerification() {
      const engineIndex = verificationModalEngineIndex;
      const batchIndices = selectedEngineBatchIndices();
      if (!Number.isInteger(engineIndex)) return;
      const decision = selectedEngineVerificationDecision();
      let checkSeconds = null;
      try {
        if (decision === "details_wrong") {
          checkSeconds = engineVerificationCheckTime();
        }
      } catch (error) {
        document.getElementById("engine-check-time-status").textContent =
          error.message;
        document.getElementById("engine-check-seconds").focus();
        return;
      }
      const checkNote = checkSeconds === null
        ? ""
        : " Inspect the reviewer-supplied alternative completion time "
          + checkSeconds.toFixed(3) + "s without changing M#.";
      const reviewChoice = decision === "details_wrong"
        ? {
            userVerdict: "incorrect",
            note: "The reviewer can see the event, but the exact team, "
              + "canonical event type, or completion time is wrong."
              + checkNote
          }
        : decision === "incorrect"
          ? {
              userVerdict: "incorrect",
              note: "The reviewer reports that no such event occurred."
                + checkNote
            }
          : decision === "cannot_verify"
            ? {
                userVerdict: "unsure",
                note: "The reviewer cannot verify the event from this camera "
                  + "because the available visual evidence is insufficient."
                  + checkNote
              }
            : decision === "correct"
              ? {userVerdict: "correct", note: ""}
              : {userVerdict: null, note: ""};
      if (batchIndices.length > 1) {
        const response = await fetch(
          "/api/copilot-review-discrepancy-batch",
          {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
              segment: selectedSegmentKey(),
              kind: "engine",
              indices: batchIndices,
              userVerdict: reviewChoice.userVerdict || "unsure",
              note: reviewChoice.note,
            }),
          }
        );
        const result = await response.json();
        if (!response.ok) {
          document.getElementById(
            "engine-verification-guidance"
          ).textContent =
            result.error || "Could not start grouped E# review";
          return;
        }
        engineVerificationPending = {
          engineIndex,
          batchId: result.batchId,
          count: result.count,
        };
        await loadState();
      } else {
        await requestEngineEventVerification(
          engineIndex,
          "engine-verification-guidance",
          null,
          false,
          reviewChoice
        );
      }
      if (state.activity?.state === "working") {
        setEngineVerificationWorking(engineIndex);
      }
    }

    function openCopilotDecisionModal(reviewIndex) {
      if (reviewWorkflow.key === "innovation") return;
      const draft = state.drafts?.[reviewIndex];
      if (!draft || draft.decision) return;
      decisionModalReviewIndex = reviewIndex;
      selectEvent(reviewIndex, {seek: false, pause: false});
      const reference = reviewReference(draft, reviewIndex);
      const engineIndex = matchingEngineIndex(draft);
      const matched = engineIndex >= 0;
      document.getElementById("copilot-decision-title").textContent =
        "Decide " + reference;
      document.getElementById("copilot-decision-event").textContent =
        canonicalComparisonLabel(draft) + " at "
        + Number(draft.seconds).toFixed(3) + "s";
      document.getElementById("accept-copilot-decision-detail").textContent =
        matched
          ? "Verify the proposal against the video and accept it. E"
            + (engineIndex + 1)
            + " already matches, so no engine change or regression run is needed."
          : "Verify the proposal against the video and accept it only if "
            + "supported. Copilot then synchronizes a general engine rule; "
            + "regressions run only if the engine changes.";
      document.getElementById("reject-copilot-decision-detail").textContent =
        matched
          ? "Exclude only this C# from the reference. E"
            + (engineIndex + 1)
            + " remains unchanged and must be decided separately through its "
            + "E# verification guide."
          : "Exclude this unsupported C# from the reference. With no matching "
            + "E#, no engine work or regression run is needed.";
      const modal = document.getElementById("copilot-decision-modal");
      if (!modal.open) modal.showModal();
      document.getElementById("accept-copilot-decision").focus();
    }

    function closeCopilotDecisionModal() {
      const modal = document.getElementById("copilot-decision-modal");
      if (modal.open) modal.close();
      decisionModalReviewIndex = null;
    }

    async function acceptCopilotDecision() {
      const reviewIndex = decisionModalReviewIndex;
      if (!Number.isInteger(reviewIndex)) return;
      closeCopilotDecisionModal();
      await requestCopilotAcceptance(reviewIndex);
    }

    async function rejectCopilotDecision() {
      const reviewIndex = decisionModalReviewIndex;
      if (!Number.isInteger(reviewIndex)) return;
      closeCopilotDecisionModal();
      await decide("rejected", reviewIndex);
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
      if (reviewWorkflow.key === "innovation") return;
      const draft = state.drafts[targetIndex];
      if (!draft || draft.decision) return;
      const button = document.getElementById("copilot-accept");
      const status = document.getElementById("decision-status");
      const reference = reviewReference(draft, targetIndex);
      const matchedEngine = matchingEngineIndex(draft) >= 0;
      button.disabled = true;
      status.textContent = matchedEngine
        ? "Copilot is verifying " + reference
          + ". The existing E# already matches, so no engine change or "
          + "regression run is expected."
        : "Copilot is verifying " + reference
          + ", then synchronizing a general engine rule if the proposal is "
          + "supported. Regressions run only if the engine changes.";
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
      if (reviewWorkflow.key === "innovation") return;
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

    async function requestGoldenValidation() {
      const button = document.getElementById("validate-engine-reference");
      const status = document.getElementById("golden-workflow-status");
      if (state.segment.state !== "ready") {
        if (!state.segment.evidenceReady) {
          status.textContent =
            "Prepare BAC + player context before validating the engine.";
          return;
        }
        validateGoldenAfterEngineRun = true;
        status.textContent =
          "Running the Innovation engine before golden-reference validation…";
        void startSegmentAnalysis();
        return;
      }
      button.disabled = true;
      status.textContent =
        "Validating current E# output and creating automatic M↔E suggestions…";
      try {
        const response = await fetch("/api/validate-engine-reference", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({segment: selectedSegmentKey()})
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(
            result.error || "Could not validate the engine against golden M#"
          );
        }
        await loadState();
        document.getElementById("golden-workflow-status").textContent =
          "Engine comparison revealed: "
          + result.mappingCount + " automatic M↔E match"
          + (result.mappingCount === 1 ? "" : "es")
          + " across " + result.engineEventCount + " E# event"
          + (result.engineEventCount === 1 ? "." : "s.");
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
      const selected = selectedEngineIndex === null
        ? document.querySelector(
            '#fullscreen-event-items '
            + '[data-event-source="review"][data-event-index="'
            + selectedIndex + '"]'
          )
        : document.querySelector(
            '#fullscreen-event-items '
            + '[data-event-source="engine"][data-event-index="'
            + selectedEngineIndex + '"]'
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
        ? reviewWorkflow.key === "innovation"
          ? state.copilotEvents?.[index]
          : state.drafts[index]
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
          source === "copilot"
            ? reviewWorkflow.key === "innovation"
              ? "copilot-reference"
              : "review"
            : "engine"
        ) + '"][data-event-index="' + index + '"]'
      );
      if (button) {
        if (source === "copilot" && reviewWorkflow.key === "innovation") {
          selectedCopilotReferenceIndex = index;
          document.querySelectorAll(".copilot-reference-event.current")
            .forEach(item => item.classList.remove("current"));
          button.classList.add("current");
          button.scrollIntoView({block: "nearest"});
        }
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

    function pulseManualEvent(index) {
      const button = document.querySelector(
        '[data-event-source="review"][data-event-index="' + index + '"]'
      );
      if (!button) return;
      button.classList.remove("playback-ping");
      void button.offsetWidth;
      button.classList.add("playback-ping");
      button.closest(".comparison-row")?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
      clearTimeout(eventTriggerTimers.manual);
      eventTriggerTimers.manual = setTimeout(() => {
        button.classList.remove("playback-ping");
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
      const crossedManual = reviewWorkflow.key === "innovation"
        ? state?.manualEvents
          ?.map((event, index) => ({event, index}))
          .filter(({event}) =>
            event.seconds > previousPlaybackSeconds
            && event.seconds <= seconds + 0.02
          )
        : [];
      for (const event of crossedManual || []) {
        pulseManualEvent(event.index);
      }
      const copilotTimeline = reviewWorkflow.key === "innovation"
        ? state?.copilotEvents
        : state?.drafts;
      const crossedCopilot = copilotTimeline
        ?.map((draft, index) => ({draft, index}))
        .filter(({draft}) =>
          draft.seconds > previousPlaybackSeconds
          && draft.seconds <= seconds + 0.02
        );
      for (const event of crossedCopilot || []) {
          if (reviewWorkflow.key !== "innovation") {
            selectEvent(event.index, {seek: false, pause: false});
          }
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
      const segment = segmentSelect.value;
      const previousSegment = state?.segment?.key;
      const segmentLabel =
        segmentSelect.selectedOptions[0]?.textContent?.trim() || segment;
      setSegmentLoading(
        true,
        "Loading " + segmentLabel,
        "Loading its video, coordinates, events, and review state."
      );
      selectedIndex = 0;
      actionZoom = false;
      manualZoom = 1;
      viewMode = "normal";
      ballTrack = null;
      ballTrackSegmentKey = null;
      segmentBuilderInitialized = false;
      if (previousSegment && previousSegment !== segment) {
        await releaseCoordinationLease();
      }
      const query = new URLSearchParams(location.search);
      query.set("segment", segment);
      history.replaceState(null, "", location.pathname + "?" + query);
      state = null;
      video.pause();
      try {
        await loadState();
        await loadGeometry();
      } catch (error) {
        document.getElementById("activity-label").textContent =
          "Could not load segment";
        document.getElementById("activity-detail").textContent = error.message;
      } finally {
        setSegmentLoading(false);
        if (state?.segment) syncInnovationAnalysisModal(state.segment);
      }
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
      setSegmentLoading(
        true,
        "Importing camera sample",
        "Validating the media and writing its isolated camera artifacts."
      );
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
        manualZoom = 1;
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
        setSegmentLoading(false);
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
      setSegmentLoading(
        true,
        "Preparing " + duration + "-second review segment",
        "Creating the playable clip and registering its workflow artifacts."
      );
      renderRunControls();
      renderAiGate();
      segmentRunStatus.textContent =
        "Preparing the " + duration + "-second playable video window locally. " +
        reviewWorkflow.preparationMessage;
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
        manualZoom = 1;
        viewMode = "normal";
        ballTrack = null;
        ballTrackSegmentKey = null;
        segmentBuilderInitialized = false;
        const preparedUrl = new URL(window.location.href);
        preparedUrl.searchParams.set("segment", state.segment.key);
        history.replaceState(null, "", preparedUrl);
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
        setSegmentLoading(false);
        renderRunControls();
        renderAiGate();
      }
    });
    [startMinute, startSecond, segmentDuration].forEach(control => {
      control.addEventListener("input", renderRunControls);
      control.addEventListener("change", renderRunControls);
    });
    prepareEvidenceButton.addEventListener("click", async () => {
      const segment = selectedSegmentKey();
      analysisModalMode = "evidence";
      setSegmentLoading(
        true,
        "Preparing BAC + player context",
        "Target: " + (state.segment.timeLabel || segment) + "\\n"
          + "Playable segment: Complete\\n"
          + "Frozen BAC coordinates: Waiting\\n"
          + "YOLO player context: Waiting\\n"
          + "Player tracking: Waiting"
      );
      runStartPending = true;
      renderRunControls();
      renderAiGate();
      segmentRunStatus.textContent =
        "Preparing frozen BAC coordinates and YOLO player context. "
        + "No football events will be generated.";
      try {
        const response = await fetch("/api/innovation/prepare-evidence", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({segment})
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not prepare evidence");
        }
        runStartPending = false;
        await loadState();
        renderRunControls();
        renderAiGate();
      } catch (error) {
        runStartPending = false;
        finishSegmentLoading(
          "Could not prepare BAC + player context",
          error.message
        );
        segmentRunStatus.textContent =
          "Could not prepare Innovation evidence: " + error.message;
        renderRunControls();
        renderAiGate();
      }
    });
    async function startSegmentAnalysis() {
      const segment = selectedSegmentKey();
      if (reviewWorkflow.key === "innovation") {
        analysisModalMode = "rules";
        setSegmentLoading(
          true,
          "Processing Innovation rules engine",
          "Target: " + (state.segment.timeLabel || segment) + "\\n"
            + "Playable segment: Complete\\n"
            + "Frozen BAC coordinates: Complete\\n"
            + "YOLO player context: Complete\\n"
            + "Innovation rules engine: Waiting"
        );
      }
      runStartPending = true;
      ballTrack = null;
      ballTrackSegmentKey = null;
      renderBallFrames();
      renderRunControls();
      renderAiGate();
      segmentRunStatus.textContent =
        state.segment.recoveryAvailable
          ? reviewWorkflow.recoveryMessage
          : reviewWorkflow.processingMessage;
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
        validateGoldenAfterEngineRun = false;
        if (reviewWorkflow.key === "innovation") {
          finishSegmentLoading(
            "Could not start Innovation rules engine",
            error.message
          );
        }
        segmentRunStatus.textContent =
          "Could not start AI: " + error.message;
        renderRunControls();
        renderAiGate();
      }
    }
    processButton.addEventListener("click", startSegmentAnalysis);
    document.getElementById("next-event").addEventListener(
      "click", () => selectEvent(selectedIndex + 1)
    );
    document.querySelectorAll("[data-manual-team]").forEach(button => {
      button.addEventListener("click", async () => {
        video.pause();
        const timestampMs = Math.round(
          Math.min(
            Number(state.segment.durationSeconds) * 1000,
            Math.max(0, Number(video.currentTime || 0) * 1000)
          )
        );
        const status = document.getElementById("manual-capture-status");
        try {
          const result = await mutateManualReference({
            action: "create",
            timestampMs,
            team: button.dataset.manualTeam,
            eventType: button.dataset.manualType
          });
          status.textContent = result.event.key + " saved at "
            + (timestampMs / 1000).toFixed(3) + "s · frame "
            + Math.min(1499, Math.round(timestampMs * 25 / 1000));
        } catch (error) {
          status.textContent = error.message;
        }
      });
    });
    document.getElementById("approve-manual-minute")?.addEventListener(
      "click",
      () => mutateManualReference({action: "approve"})
    );
    document.getElementById("validate-engine-reference")?.addEventListener(
      "click",
      () => void requestGoldenValidation()
    );
    document.getElementById("publish-passed-segment")?.addEventListener(
      "click",
      requestReferencePublication
    );
    document.getElementById("reopen-manual-minute")?.addEventListener(
      "click",
      () => mutateManualReference({action: "reopen"})
    );
    const openManualLedgerAudit = () => {
      renderManualLedgerAudit();
      document.getElementById("manual-ledger-audit-status").textContent =
        referenceLocked()
          ? "This published reference is read-only."
          : "Advisories never block or alter M# approval.";
      document.getElementById("manual-ledger-audit-modal").showModal();
    };
    document.getElementById("open-manual-ledger-audit")?.addEventListener(
      "click",
      openManualLedgerAudit
    );
    document.getElementById("close-manual-ledger-audit")?.addEventListener(
      "click",
      () => document.getElementById("manual-ledger-audit-modal").close()
    );
    function setCopilotReferenceVisible(visible) {
      const panel = document.getElementById("copilot-reference");
      const toggle = document.getElementById("show-copilot-reference");
      if (!panel || !toggle) return;
      panel.hidden = !visible;
      panel.style.display = visible ? "flex" : "none";
      toggle.checked = visible;
    }

    document.getElementById("show-copilot-reference")?.addEventListener(
      "change",
      event => {
        setCopilotReferenceVisible(event.currentTarget.checked);
      }
    );
    document.getElementById("hide-copilot-reference")?.addEventListener(
      "click",
      () => setCopilotReferenceVisible(false)
    );
    document.getElementById("show-bac-coordinate")?.addEventListener(
      "change",
      event => {
        showBacCoordinate = event.currentTarget.checked;
        updateBallMarker();
      }
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
          document.querySelectorAll("[name=engine-user-verdict]").forEach(input => {
            input.addEventListener("change", () => {
              const action = document.getElementById("fullscreen-primary-action");
              action.disabled = state.activity?.state === "working";
              action.textContent = input.value === "incorrect"
                ? "Confirm Incorrect & Diagnose Engine (Autopilot)"
                : input.value === "unsure"
                  ? "Ask Copilot to Adjudicate E"
                    + (selectedEngineIndex + 1) + " (Autopilot)"
                  : "Verify E" + (selectedEngineIndex + 1) + " (Autopilot)";
            });
          });
          return;
        }
        if (currentDraft()?.decision?.status === "accepted") {
          await requestAcceptedEngineRecheck(selectedIndex);
          return;
        }
        await requestCopilotAcceptance(selectedIndex);
      }
    );
    document.getElementById("close-manual-engine-review").addEventListener(
      "click",
      closeManualEngineReviewModal
    );
    document.getElementById("manual-engine-review-modal").addEventListener(
      "cancel",
      event => {
        if (
          manualEngineReviewPending
          || state.activeDiscrepancyBatch?.kind === "manual"
          || state.activity?.state === "working"
        ) {
          event.preventDefault();
        }
      }
    );
    document.getElementById(
      "cancel-manual-copilot-review"
    ).addEventListener("click", cancelManualEngineReview);
    document.getElementById(
      "ask-copilot-manual-engine-review"
    ).addEventListener("click", requestManualEngineReview);
    document.querySelectorAll(
      "[name=manual-engine-review-decision]"
    ).forEach(input => {
      input.addEventListener("change", updateManualEngineReviewActions);
    });
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
    document.getElementById("toggle-playback").addEventListener(
      "click",
      async () => {
        const status = document.getElementById("playback-status");
        status.textContent = "";
        if (!video.paused) {
          video.pause();
          return;
        }
        try {
          await video.play();
        } catch {
          status.textContent = "Playback could not start. Try again.";
        }
      }
    );
    document.getElementById("toggle-event-panel").addEventListener(
      "click",
      () => {
        const hidden = videoShell.classList.toggle("events-hidden");
        const button = document.getElementById("toggle-event-panel");
        button.textContent = hidden ? "Show event panel" : "Hide event panel";
        button.setAttribute("aria-expanded", String(!hidden));
      }
    );
    {
      const panel = document.getElementById("fullscreen-events");
      const handle = document.getElementById("move-event-panel");
      const movePanelTo = (left, top) => {
        const shellRect = videoShell.getBoundingClientRect();
        const inset = 14;
        const maxLeft = Math.max(
          inset,
          shellRect.width - panel.offsetWidth - inset
        );
        const maxTop = Math.max(
          inset,
          shellRect.height - panel.offsetHeight - inset
        );
        panel.style.left =
          Math.min(maxLeft, Math.max(inset, left)) + "px";
        panel.style.top =
          Math.min(maxTop, Math.max(inset, top)) + "px";
        panel.style.right = "auto";
        panel.style.bottom = "auto";
      };
      let panelClampFrame = null;
      const clampPanelToShell = () => {
        cancelAnimationFrame(panelClampFrame);
        panelClampFrame = requestAnimationFrame(() => {
          if (!document.fullscreenElement || !panel.style.left) return;
          const shellRect = videoShell.getBoundingClientRect();
          const panelRect = panel.getBoundingClientRect();
          movePanelTo(
            panelRect.left - shellRect.left,
            panelRect.top - shellRect.top
          );
        });
      };
      new ResizeObserver(clampPanelToShell).observe(panel);
      document.getElementById("fullscreen-event-chat").addEventListener(
        "toggle",
        clampPanelToShell
      );
      document.addEventListener("fullscreenchange", clampPanelToShell);
      handle.addEventListener("pointerdown", event => {
        if (!document.fullscreenElement) return;
        event.preventDefault();
        const shellRect = videoShell.getBoundingClientRect();
        const panelRect = panel.getBoundingClientRect();
        const startLeft = panelRect.left - shellRect.left;
        const startTop = panelRect.top - shellRect.top;
        const startX = event.clientX;
        const startY = event.clientY;
        handle.setPointerCapture(event.pointerId);
        const move = moveEvent => {
          movePanelTo(
            startLeft + moveEvent.clientX - startX,
            startTop + moveEvent.clientY - startY
          );
        };
        const stop = () => {
          handle.removeEventListener("pointermove", move);
          handle.removeEventListener("pointerup", stop);
          handle.removeEventListener("pointercancel", stop);
        };
        handle.addEventListener("pointermove", move);
        handle.addEventListener("pointerup", stop);
        handle.addEventListener("pointercancel", stop);
      });
      handle.addEventListener("keydown", event => {
        if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(
          event.key
        )) return;
        event.preventDefault();
        const shellRect = videoShell.getBoundingClientRect();
        const panelRect = panel.getBoundingClientRect();
        const step = event.shiftKey ? 50 : 20;
        movePanelTo(
          panelRect.left - shellRect.left
            + (event.key === "ArrowRight" ? step
              : event.key === "ArrowLeft" ? -step : 0),
          panelRect.top - shellRect.top
            + (event.key === "ArrowDown" ? step
              : event.key === "ArrowUp" ? -step : 0)
        );
      });
    }
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
      updateBallMarker();
      updateLiveStatistics(seconds);
      updateFullscreenEventProgress(seconds);
    });
    video.addEventListener("play", () => {
      document.getElementById("toggle-playback").textContent = "Pause";
      cancelAnimationFrame(playbackFrameRequest);
      previousPlaybackSeconds = video.currentTime;
      playbackFrameRequest = requestAnimationFrame(followPlaybackEvents);
    });
    video.addEventListener("pause", () => {
      document.getElementById("toggle-playback").textContent = "Play";
      cancelAnimationFrame(playbackFrameRequest);
      playbackFrameRequest = null;
      previousPlaybackSeconds = video.currentTime;
    });
    video.addEventListener("ended", () => {
      document.getElementById("toggle-playback").textContent = "Play";
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
    document.getElementById("enlarge").addEventListener("click", async () => {
      if (document.fullscreenElement === videoShell) {
        await document.exitFullscreen();
      } else {
        await videoShell.requestFullscreen();
      }
    });
    document.getElementById("zoom-action").addEventListener("click", () => {
      actionZoom = !actionZoom;
      videoPanX = 0;
      videoPanY = 0;
      applyActionZoom();
    });
    document.getElementById("zoom-out").addEventListener("click", () => {
      actionZoom = false;
      manualZoom = Math.max(1, manualZoom - 0.5);
      applyActionZoom();
    });
    document.getElementById("zoom-in").addEventListener("click", () => {
      actionZoom = false;
      manualZoom = Math.min(6, manualZoom + 0.5);
      applyActionZoom();
    });
    videoZoomLayer.addEventListener("pointerdown", event => {
      if (
        currentAppliedZoom() <= 1
        || geometryCanvas.classList.contains("editing")
        || (event.pointerType === "mouse" && event.button !== 0)
      ) return;
      const startX = event.clientX;
      const startY = event.clientY;
      const startPanX = videoPanX;
      const startPanY = videoPanY;
      let didDrag = false;
      const move = moveEvent => {
        const deltaX = moveEvent.clientX - startX;
        const deltaY = moveEvent.clientY - startY;
        if (!didDrag && Math.hypot(deltaX, deltaY) < 5) return;
        if (!didDrag) {
          didDrag = true;
          videoMedia.classList.add("panning");
          videoZoomLayer.setPointerCapture(event.pointerId);
        }
        moveEvent.preventDefault();
        videoPanX = startPanX + deltaX;
        videoPanY = startPanY + deltaY;
        applyActionZoom();
      };
      const stop = stopEvent => {
        videoMedia.classList.remove("panning");
        if (videoZoomLayer.hasPointerCapture(stopEvent.pointerId)) {
          videoZoomLayer.releasePointerCapture(stopEvent.pointerId);
        }
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", stop);
        window.removeEventListener("pointercancel", stop);
      };
      window.addEventListener("pointermove", move, {passive: false});
      window.addEventListener("pointerup", stop);
      window.addEventListener("pointercancel", stop);
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
    document.getElementById("close-segment-replay").addEventListener(
      "click",
      () => segmentReplayModal.close()
    );
    segmentReplayModal.addEventListener("close", () => {
      segmentReplayVideo.pause();
      segmentReplayVideo.removeAttribute("src");
      segmentReplayVideo.load();
      segmentReplayKey = null;
    });
    segmentReplayModal.addEventListener("click", event => {
      if (event.target === segmentReplayModal) segmentReplayModal.close();
    });
    segmentReplayVideo.addEventListener("timeupdate", updateSegmentReplay);

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
    workflowAdapterSelect.addEventListener("change", async () => {
      const targetWorkflow = workflowAdapterSelect.value;
      if (targetWorkflow === reviewWorkflow.key) return;
      setSegmentLoading(
        true,
        "Switching review workflow",
        "Loading the selected adapter, segment catalog, and isolated review state."
      );
      try {
        await releaseCoordinationLease();
        const response = await fetch("/api/switch-workflow", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            workflow: targetWorkflow,
            segment: localStorage.getItem(
              workflowSegmentStorageKey(targetWorkflow)
            ),
            hostInstanceId
          })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Could not switch workflow");
        }
        window.location.assign(result.url);
      } catch (error) {
        workflowAdapterSelect.value = reviewWorkflow.key;
        setSegmentLoading(false);
        document.getElementById("activity-label").textContent =
          "Could not switch workflow";
        document.getElementById("activity-detail").textContent = error.message;
      }
    });
    window.setInterval(() => {
      if (document.visibilityState === "visible") {
        loadState(false).catch(() => {});
      }
    }, 2000);
    window.addEventListener("focus", () => {
      loadState(false).catch(() => {});
    });
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        loadState(false).catch(() => {});
      }
    });
    setSegmentLoading(
      true,
      "Loading football review",
      "Loading video, coordinates, events, and review state."
    );
    loadState().then(async () => {
      await loadGeometry();
    }).catch(error => {
      document.getElementById("decision-status").textContent = error.message;
    }).finally(() => {
      setSegmentLoading(false);
      if (state?.segment) syncInnovationAnalysisModal(state.segment);
    });
  </script>
</body>
</html>`;
}
