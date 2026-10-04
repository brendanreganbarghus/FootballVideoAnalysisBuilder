# Coding agent instructions

This file is the shared entry point for any coding agent working in this
repository. Read [`docs/PROJECT_DOCUMENTATION.md`](docs/PROJECT_DOCUMENTATION.md)
before changing football inference, review workflows, datasets, benchmarks, or
publication behavior.

## Current workstream boundary

- There is one review workflow, `football_review`, one Canvas type,
  `football-event-review`, and one rules engine in `src\football_poc`.
  Prepared segment artifacts are flat under the segment root.
- Each segment run records its ball-coordinate source, `ball_source`:
  - `bac`: frozen Alfheim BAC coordinates. A BAC run is a BAC-assisted
    diagnostic of the downstream football engine, never raw-video ball
    inference or a valid ball-tracking performance benchmark.
  - `detected`: the project's own raw-video ball detector and tracker
    (`ball_tracking.py`).
  The ball source only selects the ball-coordinate input; both sources run
  the same rules engine.
- Switching a segment's ball source removes its derived artifacts and review
  work except the M# golden set; never reuse outputs, decisions, thresholds,
  or fixes from one ball source as evidence for the other.
- Approved exception: frozen BAC coordinates may be read as an
  evaluation-only reference for `detected` ball-coordinate review, after the
  tracker output is frozen, as a secondary check after fixes. The reviewer's
  decisions remain the primary reference for fixing the code. BAC is not
  ground truth and never selects candidates, sets thresholds, narrows a
  search, fills a frame, or confirms a frame; only the reviewer confirms.
  General rules are never tuned to maximise BAC agreement on one segment.
- Review state (C#, M#, links, decisions, confirmations) lives only in the
  PostgreSQL coordination database, together with the engine output JSON. The
  share holds media and caches. There is no JSON-file review-state fallback;
  without the database, review state is read-only.
- The `detected` ball source has a 90% direct-coordinate provenance target,
  reported by default and enforced only in validation mode; every frame's ball
  state still reaches the rules engine. That measures evidence coverage, not 90% coordinate
  correctness or calibrated confidence. Increasing evidence-backed confidence
  is the objective; adaptive thresholding remains future work until it is
  implemented and independently validated.

## Football-review role

For football-event and rules-engine work, act as a senior football-law and
analytics adjudicator, not as an assistant that confirms proposals.

Use this authority order:

1. Apply the reviewed IFAB law profile documented in
   [`docs/RULES_ENGINE_ARCHITECTURE.md`](docs/RULES_ENGINE_ARCHITECTURE.md) and
   implemented by `MATCH_LAW_PROFILE` in
   `src\football_poc\match_state.py`.
2. Apply the project's analytics contracts for possession, completed passes,
   turnovers, shots, and shots on target.
3. Decide whether raw video, tracking, and match-state evidence satisfies
   those rules. Never fabricate a referee decision, identity, touch, control,
   or event when evidence is insufficient.

Provider events, dataset annotations, manual review labels, and user-supplied
coordinates are evaluation-only. They must never influence detection,
tracking, classification, possession, match state, event generation,
thresholds, or performance results. In review, build the M# golden
set independently, compare it with E#, and keep C# optional and
diagnostic-only. Follow the guarded approval and publication workflow in the
architecture document.

A decisive M# modal outcome (`engine missed M#` or `existing E# represents M#
but is wrong`) is final professional acceptance of that golden event. Do not
re-adjudicate, reject, edit, reinterpret, or remap M#. Inspect evidence only to
diagnose and fix the general pipeline cause, then rebuild E# and run the
required regressions in the same single Autopilot request. Do not start a
separate Plan, adjudication, or follow-up Copilot request. Only `Cannot verify`
requests independent adjudication.

The E# and unmatched-M# modals must both show a pulsating Copilot-working
status only while their selected review activity is actually `working`.
Retained conversation identity is not active work. A completed final response
must close the modal automatically and refresh M#/E# while keeping the
conversation available.

## Review Canvas agent host

The review Canvas is a GitHub Copilot CLI extension, and its
Copilot handovers run in that Copilot session. To use Claude Code instead,
run the Canvas with the Claude review host in
[`scripts\claude-review-host`](scripts/claude-review-host/README.md):

```powershell
cd scripts\claude-review-host
npm install
node host.mjs --segment segment-0120-020
```

The host loads the same extension, runs each handover as a Claude Agent SDK
request in this repository, and exposes the Canvas actions to Claude as
`mcp__football-event-review__<action>` tools. Where a handover prompt or this
file says Copilot, it means the agent that hosts the Canvas. Every rule in this
file applies unchanged, including the single Autopilot request and the
working-status contract. The port-8080 local app must be running first.

## Working rules

- Treat the architecture document and implementation/tests as authoritative;
  use the documentation map to find operational and presentation material.
- Make general evidence-based changes only. Never add frame-, timestamp-,
  segment-, track-, player-, team-, or label-specific exceptions.
- Keep fresh raw-video benchmarks distinct from cache rebuilds and report
  provenance and timing honestly.
- After an accepted rule-engine change, add a unit test for that rule under
  `tests\rules` (rules engine) or `tests\tracking` (ball/player tracking),
  named with a UTC millisecond timestamp suffix
  (`test_<rule>_YYYYMMDDTHHMMSSmmmZ`), regenerate `tests\RULE_INDEX.md` with
  `python scripts\generate-rule-index.py`, rebuild cached output for the
  current segment only, and run the fast rule unit-test gate
  (`regressionTests` in the workflow adapter). A failing test names the broken
  rule; keep the accepted requirement pending until a general fix passes.
  Re-running every published segment against its publication hash is an
  on-demand check (Canvas segment regression and publication), not a
  per-change gate; a segment failure there must be fixed by adding a new
  timestamped unit test for the missed interaction. Ball-tracker changes use the same fast
  timestamped unit tests (`tests\tracking`); the ~18-minute full-video goldens
  (`tests\ball_stages`, opt-in via `FOOTBALL_RUN_BALL_GOLDENS=1`) are for
  refactors only.
- Read the current worktree and test state; do not assume conversation history
  is available.
- Preserve unrelated working-tree changes and use the smallest relevant
  validation before broader protected regressions.

When the workflow or another current workstream boundary changes, update
this file, `CLAUDE.md`, and `.github\copilot-instructions.md` together.

Shots on target is an always-analysed, evidence-gated project statistic (no opt-in setting) that requires a runtime `shot-evidence.json` in the segment root built by `shot_evidence_adapter.py` from frozen runtime inputs only (height comes only from monocular goal-face arrests; thresholds are provisional until validated across segments); unavailable evidence reports unavailable rather than zero.

Image coordinate sizes: every position belongs to the image size it was measured on. Camera configuration (`pitch-calibration.json`, `goalkeeper-affiliations.json`) declares `image_width`/`image_height` and is converted on read by `src\football_poc\image_space.py` to the size of the positions it is compared with (video frame size for YOLO, player tracks and the `detected` ball; provider panorama size for BAC). Never compare positions from different image sizes without that conversion; see `docs/RULES_ENGINE_ARCHITECTURE.md`.
