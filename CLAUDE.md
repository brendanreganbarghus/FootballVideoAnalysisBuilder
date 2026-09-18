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

After an accepted rule-engine change, rebuild cached output for every published
segment in that workflow and compare it exactly with its publication hash
before completing engine synchronization. Any mismatch keeps the accepted
review requirement pending: report each affected segment and its event
differences, revise the general rule without weakening the new requirement,
and repeat the complete protected regression gate. Never reset unrelated work.

**Current boundary:** Live ball tracking and the Live review Canvas are frozen
and fully separate from Innovation Day. Do not inspect, run, edit, or reuse
Live code, state, or artifacts unless Brendan explicitly resumes Live work.
Innovation Day uses frozen BAC coordinates and only its Innovation engine,
artifact namespace, review state, and Canvas. Treat Innovation Day as a
BAC-assisted diagnostic/demo of the frozen downstream football engine. Never
describe it as raw-video ball inference, a valid ball-tracking performance
benchmark, or current Live pipeline behavior.

Do not copy all repository documentation into this file. The documentation map
is the maintained index; the linked documents and code remain authoritative.
