# Coding agent instructions

This file is the shared entry point for any coding agent working in this
repository. Read [`docs/PROJECT_DOCUMENTATION.md`](docs/PROJECT_DOCUMENTATION.md)
before changing football inference, review workflows, datasets, benchmarks, or
publication behavior.

## Current workstream boundary

- Live ball tracking and `football-event-review-live` are frozen and separate
  from Innovation Day. Do not inspect, run, edit, or reuse Live tracker code,
  Live review state, or `live\` artifacts unless Brendan explicitly resumes
  that work.
- Innovation Day uses frozen BAC coordinates, the frozen Innovation engine,
  `innovation\` artifacts, `event-review-state-innovation`, and Canvas type
  `football-event-review`. It is a BAC-assisted diagnostic/demo of the
  downstream football engine, not raw-video ball inference or a valid
  ball-tracking performance benchmark.
- Never move artifacts, state, decisions, thresholds, or fixes between the
  Innovation and Live workflows.

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
thresholds, or performance results. In Innovation review, build the M# golden
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

## Working rules

- Treat the architecture document and implementation/tests as authoritative;
  use the documentation map to find operational and presentation material.
- Make general evidence-based changes only. Never add frame-, timestamp-,
  segment-, track-, player-, team-, or label-specific exceptions.
- Keep fresh raw-video benchmarks distinct from cache rebuilds and report
  provenance and timing honestly.
- After an accepted rule-engine change, rebuild cached output for every
  published segment in that workflow and require exact publication-hash
  matches plus all protected tests. A failure keeps the accepted requirement
  pending, identifies each affected segment and event difference, and blocks
  synchronization/publication until a general fix passes the complete gate.
- Read the current worktree and test state; do not assume conversation history
  is available.
- Preserve unrelated working-tree changes and use the smallest relevant
  validation before broader protected regressions.

When the Live freeze or another current workstream boundary changes, update
this file, `CLAUDE.md`, and `.github\copilot-instructions.md` together.
