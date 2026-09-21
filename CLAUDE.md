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
In Innovation review, treat the independently recorded M# set as golden,
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

After an accepted rule-engine change, rebuild cached output for every published
segment in that workflow and compare it exactly with its publication hash
before completing engine synchronization. Any mismatch keeps the accepted
review requirement pending: report each affected segment and its event
differences, revise the general rule without weakening the new requirement,
and repeat the complete protected regression gate. Never reset unrelated work.

**Current boundary:** Live ball tracking is an active R&D workstream, fully
separate from Innovation Day. Inspect, run, or edit Live code, state, artifacts,
or the Live review Canvas only when the current task explicitly targets Live
work. Its current minimum 90% direct-coordinate provenance gate measures
evidence coverage, not coordinate correctness or calibrated confidence;
adaptive thresholding remains future work until implemented and independently
validated. Innovation Day uses frozen BAC coordinates and only its Innovation
engine, artifact namespace, review state, and Canvas. Treat Innovation Day as a
BAC-assisted diagnostic/demo of the frozen downstream football engine. Never
describe it as raw-video ball inference, a valid ball-tracking performance
benchmark, or current Live pipeline behavior.

Do not copy all repository documentation into this file. The documentation map
is the maintained index; the linked documents and code remain authoritative.
