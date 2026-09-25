# Claude review host

Runs the Innovation Day Football Event Review Canvas with a Claude agent in
place of GitHub Copilot. The host needs no changes to the extension in
`.github\extensions\football-event-review`: `hooks.mjs` resolves
its `@github/copilot-sdk/extension` import to `copilot-shim.mjs`, which

- starts the Canvas through the extension's own `open` handler;
- runs each Copilot handover (`session.send`) as a Claude Agent SDK request in
  the repository, resuming one Claude conversation for the host's lifetime;
- exposes the Canvas actions to Claude as the `football-event-review` MCP
  tools;
- reports shell tool use and failures through the `tool.execution_start` and
  `session.error` events that drive the Canvas working status.

The Copilot project-session guard stays active: the Canvas opened by the host
is the connected session, and copied or stale URLs remain read-only.

## Run

Prerequisites: the port-8080 local app, the Innovation workspace environment
(`FOOTBALL_ARTIFACT_ROOT`, `FOOTBALL_ALFHEIM_PANO`), Node.js 20 or later, and
Claude credentials (a Claude Code login or `ANTHROPIC_API_KEY`).

```powershell
cd scripts\claude-review-host
npm install
$env:PATH = "$(Resolve-Path ..\..\.venv\Scripts);$env:PATH"
node host.mjs --segment segment-0120-020
```

Open `http://127.0.0.1:8080/review-canvas?theme=innovation`. Stop the host
with Ctrl+C.

## Options

| Variable | Default | Purpose |
| --- | --- | --- |
| `CLAUDE_REVIEW_MODEL` | Claude Code default | Model for review requests |
| `CLAUDE_REVIEW_AUTOPILOT_PERMISSION_MODE` | `bypassPermissions` | Permission mode for Autopilot handovers |

Autopilot handovers run without approval prompts, as Copilot Autopilot does,
so Claude can edit the rules engine and run regressions unattended. Plan
handovers run in `dontAsk` mode, which allows only `Read`, `Glob`, `Grep`, and
the Canvas actions. Claude's own `plan` mode is not used, because it also
blocks the Canvas actions that report the answer.

A request that ends without a completed Canvas reporting action raises
`session.error`, so the Canvas never stays in the working state.

Only the Innovation workflow is hosted. The Live Canvas remains a separate
workstream.
