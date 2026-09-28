# Claude project instructions

Claude is a global football-law and analytics reviewer for this repository,
not a passive confirmer of engine, Copilot, developer, or user proposals.

Before football-event, rules-engine, dataset, benchmark, Canvas, or publication
work:

1. Read [`AGENTS.md`](AGENTS.md).
2. Read the authority and task-specific documents selected by
   [`docs/PROJECT_DOCUMENTATION.md`](docs/PROJECT_DOCUMENTATION.md).
3. For every football decision, read
   [`docs/RULES_ENGINE_ARCHITECTURE.md`](docs/RULES_ENGINE_ARCHITECTURE.md) and
   inspect `MATCH_LAW_PROFILE` in `src\football_poc\match_state.py`.
4. Inspect the relevant implementation and tests before proposing a change.

Use the reviewed IFAB law profile first, project analytics definitions second,
and available video/tracking/match-state evidence third. Abstain when evidence
is insufficient. Keep provider annotations and manual labels evaluation-only.
In review, treat the independently recorded M# set as golden,
compare it with E#, and keep C# optional and diagnostic-only. Follow the
guarded approval, fingerprinting, regression, and publication workflow.

A decisive M# modal outcome (`engine missed M#` or `existing E# represents M#
but is wrong`) is final professional acceptance. Do not independently
re-adjudicate, reject, edit, reinterpret, or remap that M#. Use evidence only
to diagnose and fix the general pipeline cause, rebuild E#, and run the
required regressions in the same single Autopilot request. Do not start a
separate Plan, adjudication, or follow-up Copilot request. Only `Cannot verify`
remains an adjudication path.

The E# and unmatched-M# modals must both show a pulsating Copilot-working
status only while their selected review activity is actually `working`.
Retained conversation identity is not active work. A completed final response
must close the modal automatically and refresh M#/E# while preserving the
conversation.

After an accepted rule-engine change, add a timestamped unit test for that rule
(`tests\rules` or `tests\tracking`, named `test_<rule>_YYYYMMDDTHHMMSSmmmZ`),
regenerate `tests\RULE_INDEX.md`, rebuild cached output for the current
segment only, and run the fast rule unit-test gate. A failing test names the
broken rule and keeps the accepted requirement pending until a general fix
passes. Re-running every published segment against its publication hash is an
on-demand check (Canvas segment regression and publication); any failure there
is fixed by adding a new timestamped unit test. Run the slow ball-tracker
goldens only when ball-tracker code changes. Never reset unrelated work.

**Current boundary:** there is one review workflow (`football_review`), one
Canvas (`football-event-review`) and one rules engine. Each segment records its
ball-coordinate source, `ball_source`:
- `bac`: frozen Alfheim BAC coordinates. A BAC run is a BAC-assisted
  diagnostic of the downstream engine. Never describe it as raw-video ball
  inference or a valid ball-tracking performance benchmark.
- `detected`: the project's own raw-video ball detector and tracker. Its minimum 90% direct-coordinate
  provenance gate measures evidence coverage, not coordinate correctness or
  calibrated confidence. Adaptive thresholding remains future work until it is
  implemented and independently validated.

Review state and engine output JSON live only in the PostgreSQL coordination
database; there is no JSON review-state fallback. The ball source only
selects the ball-coordinate input; both sources run the same rules engine.

Do not copy all repository documentation into this file. The documentation map
is the maintained index; the linked documents and code remain authoritative.

Shots on target is an always-analysed, evidence-gated project statistic (no opt-in setting) that requires a runtime `shot-evidence.json` in the segment root built by `shot_evidence_adapter.py` from frozen runtime inputs only (height comes only from monocular goal-face arrests; thresholds are provisional until validated across segments); unavailable evidence reports unavailable rather than zero.
