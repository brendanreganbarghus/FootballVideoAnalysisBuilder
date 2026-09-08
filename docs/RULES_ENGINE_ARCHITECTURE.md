# Football rules engine architecture

This document is the architectural base for the platform-neutral football
rules engine. It defines how official football law, observable video evidence,
analytics definitions, event inference, human adjudication, and regression
protection fit together.

The core principle is:

> Official Laws determine whether and how play can continue. Project analytics
> definitions determine which measurable events are reported while play is
> live.

The engine must never substitute an analytics convention for a Law of the Game,
and it must never claim an official decision that cannot be supported by the
available evidence.

## 1. Authoritative law profile

The match-state policy is grounded in the current official IFAB Laws of the
Game. The code uses stable law concepts while linking to IFAB's `latest` pages
so the source can be reviewed when a new edition is published.

| Law area | Engine principle | Official source | Code |
| --- | --- | --- | --- |
| Law 5 and Law 12 | A referee stoppage makes the ball dead; advantage keeps play live | [Fouls and misconduct](https://www.theifab.com/laws/latest/fouls-and-misconduct/) | `LawReference.REFEREE_AND_ADVANTAGE`; `law_event="offence"` in `build_match_state_timeline` |
| Law 8 | Kick-offs, free kicks, penalty kicks, throw-ins, goal kicks, corner kicks, and dropped balls are restart families | [Start and restart of play](https://www.theifab.com/laws/latest/the-start-and-restart-of-play/) | `RestartType`; `RESTART_LAW_REFERENCES` |
| Law 9 | The whole ball crossing a boundary, or the referee stopping play, makes the ball out of play; rebounds that remain on the field stay live | [Ball in and out of play](https://www.theifab.com/laws/latest/the-ball-in-and-out-of-play/) | `MatchPlayState.OUT_OF_PLAY`; boundary transitions |
| Law 13 | Direct and indirect free kicks restart play after relevant offences | [Free kicks](https://www.theifab.com/laws/latest/free-kicks/) | `FREE_KICK`, `DIRECT_FREE_KICK`, and `INDIRECT_FREE_KICK` |
| Law 15 | A throw-in is a boundary restart | [The throw-in](https://www.theifab.com/laws/latest/the-throw-in/) | `RestartType.THROW_IN` |
| Law 16 | A goal kick is a boundary restart | [The goal kick](https://www.theifab.com/laws/latest/the-goal-kick/) | `RestartType.GOAL_KICK` |
| Law 17 | A corner kick is a boundary restart | [The corner kick](https://www.theifab.com/laws/latest/the-corner-kick/) | `RestartType.CORNER_KICK` |

The active profile is declared as `MATCH_LAW_PROFILE` in
[`src\football_poc\match_state.py`](..\src\football_poc\match_state.py).
Generated match-state output includes the profile identifier, review date,
official source URLs, and the analytics-definition boundary. The initial
profile was reviewed on 2026-09-06.

This is not a frozen copy of IFAB text. Before adopting a new Laws edition,
review the linked sources, update the profile date or identifier, add focused
tests for changed behavior, and run every protected regression.

## 2. Engine layers

```text
Video / sensor / operator observations
                    |
                    v
       Platform-specific evidence adapters
                    |
                    v
      Law-grounded match-state engine
      - live, uncertain, stopped, restart
                    |
                    v
       Analytics event state machines
       - possession, pass, turnover, shot
                    |
                    v
      Independent human adjudication
                    |
                    v
   Regression-protected published statistics
```

### Layer A: normalized evidence

Inputs are observations, not conclusions. Examples include:

- ball position, speed, trajectory, and boundary distance;
- player position, team evidence, movement, disengagement, and reaction;
- controlled touch and possession confidence;
- calibrated pitch lines, goal mouths, and restart locations;
- whistle, referee, or assistant signals when a platform can supply them;
- operator evidence for cases that remain visually ambiguous.

Camera, detector, tracker, UI, and deployment integrations must translate their
data into normalized observations before invoking the rules engine.

### Layer B: law-grounded match state

Implemented in
[`src\football_poc\match_state.py`](..\src\football_poc\match_state.py).
It determines whether ordinary analytics events are legally possible.

| State | Meaning | Event policy |
| --- | --- | --- |
| `IN_PLAY` | Available evidence supports live competitive play | Ordinary pass, turnover, and shot inference may run |
| `POSSIBLE_STOPPAGE` | An offence or stoppage may have occurred, but continuation or a referee stoppage is not yet established | Suppress speculative ordinary events until resolved |
| `OUT_OF_PLAY` | The whole ball crossing a boundary is supported | Suppress ordinary events; retain the boundary-loss transition where appropriate |
| `RESTART_PENDING` | Play is stopped and a legal restart has not yet released the ball into play | Ignore ball retrieval, placement, and repositioning |
| `PERIOD_ENDED` | The current period has ended | Suppress all later events in that period |
| `UNKNOWN` | The clip or tracking evidence does not establish whether play is live | Suppress speculative ordinary events |

The state policy is conservative by design. Missing evidence does not become a
fabricated referee decision.

### Layer C: analytics definitions

Implemented primarily in
[`src\football_poc\possession.py`](..\src\football_poc\possession.py).
These are project definitions, not IFAB Laws:

- **Completed pass:** a player deliberately plays the ball and the first
  controlled following touch is by a teammate. This includes legal restarts.
- **Turnover:** the team in controlled possession loses it when an opponent
  establishes control. A challenge, deflection, foul, or loose ball alone is
  not a turnover.
- **Possession:** evidence of controlled ball ownership aggregated over time;
  proximity alone is insufficient.
- **Shot:** an intentional attempt to score.
- **Shot on target:** a goal or an attempt that would enter without a
  goalkeeper or last-line save.
- **Shot off target:** an attempt that misses the goal and was not saved on
  target.

An event must satisfy both its analytics definition and the match-state gate.

## 3. Law-derived transition contracts

### Ball crossing a boundary

1. Sustained evidence that the whole ball crossed a calibrated boundary moves
   `IN_PLAY → OUT_OF_PLAY`.
2. Ball retrieval or re-entry before the restart moves
   `OUT_OF_PLAY → RESTART_PENDING`.
3. A credible legal restart release moves
   `RESTART_PENDING → IN_PLAY`.
4. Continuous flight, projection artifacts, and confirmed competitive control
   are explicit reasons to reject a false boundary stoppage.

### Possible foul or other offence

1. An observed possible offence with no confirmed outcome moves
   `IN_PLAY → POSSIBLE_STOPPAGE`.
2. Clear competitive continuation resolves it back to `IN_PLAY`, representing
   advantage or no stoppage.
3. Confirmed cessation of competitive play moves it to `RESTART_PENDING`.
4. A credible free-kick release and renewed player reaction return it to
   `IN_PLAY`.
5. The foul does not create a turnover.

If the referee applies advantage, the engine remains `IN_PLAY`. It may preserve
a later disciplinary annotation, but that annotation must not stop event
inference.

### Goal

A confirmed goal moves play to `RESTART_PENDING` with
`RestartType.KICK_OFF`. Ordinary events remain suppressed until the kick-off
legally resumes play.

### Other referee stoppage

When the referee stops play and no Law prescribes another restart, the restart
family is `DROPPED_BALL`. The engine uses `RESTART_PENDING` until the dropped
ball returns to play.

### Period end

The end of a half or extra-time period moves to `PERIOD_ENDED`. No later event
may be inferred inside that period.

## 4. Observable-evidence policy

The Laws may depend on information a video platform does not always expose.
The engine therefore separates a legal concept from its evidence adapter.

| Concept | Preferred evidence | Conservative fallback |
| --- | --- | --- |
| Ball out of play | Calibrated whole-ball boundary crossing | `UNKNOWN` if the ball or line is not observable |
| Referee stoppage | Whistle, referee gesture, assistant signal | Ball stops behaving competitively and multiple nearby players disengage |
| Advantage | Referee signal plus uninterrupted competitive play | Sustained competitive continuation without restart setup |
| Restart pending | Known stoppage plus ball retrieval/placement | Stationary ball and low nearby-player activity |
| Restart release | Correct release motion plus renewed player reaction | Remain pending if movement looks like repositioning |
| Restart family | Boundary location, award direction, setup geometry, official signal | `RestartType.UNKNOWN` |

Official and assistant-referee detection can increase confidence but is not a
mandatory dependency. This keeps the core usable on different platforms while
avoiding false certainty.

## 5. Stateful streaming execution contract

The production engine processes a live match as consecutive configurable
30–60 second micro-batches. A batch is not an independent match:

1. load the last committed checkpoint;
2. ingest only the next time-bounded segment, with a small configured overlap
   where boundary evidence requires it;
3. run evidence normalization, match-state transitions, and analytics event
   inference;
4. reconcile provisional boundary events and suppress duplicate event IDs;
5. append event and statistic deltas to durable output;
6. atomically persist the new checkpoint before acknowledging the batch;
7. start the next segment from that checkpoint.

The checkpoint contract must be versioned and JSON-compatible. At minimum it
must preserve:

- source/match identity, period, absolute source time, and finalized-through
  time;
- law-grounded play state and pending restart context;
- current possession team and any unresolved pass, turnover, shot, foul, or
  boundary candidate;
- stable team/player identity evidence needed across a tracker handoff;
- accepted event identities used for overlap deduplication;
- cumulative statistics plus the per-batch deltas that produced them;
- engine, law-profile, analytics-definition, and checkpoint-schema versions.

Publishing must be idempotent. Replaying a completed segment from the same
input checkpoint must produce the same output checkpoint and must not
double-count an event or statistic. A failed batch leaves the previous
checkpoint authoritative and can be retried.

The end-to-end processing time target is shorter than the configured segment
duration so the worker does not accumulate backlog during a live match.
Latency, queue wait, and finalized-through time are correctness telemetry, not
only performance metrics.

A presentation or replay run must use one continuous chronological segment
chain from the same match and period. Every segment start must equal the prior
segment end, and each segment must consume the prior segment's output
checkpoint. Disjoint prepared clips must remain separate runs; the UI must
never concatenate them to reach a requested demonstration length.

`src\football_poc\chunk_simulator.py` currently proves checkpoint resume,
overlap deduplication, cumulative provisional counts, and queue-latency
behavior using precomputed events. `initial_possession_team` provides limited
possession inheritance for isolated inference. These are foundations, not the
complete production handoff: real inference still needs the full checkpoint
contract above.

## 6. Test 3 reference behavior

For Alfheim Test 3 (`segment-0300-020`, 15:00–16:00):

- `IN_PLAY`: 0.0–19.4s;
- `RESTART_PENDING`: 19.4–25.6s;
- `IN_PLAY`: 25.6–44.44s;
- `OUT_OF_PLAY`: 44.44–45.36s;
- `RESTART_PENDING`: 45.36–45.4s;
- `IN_PLAY`: 45.4–60.0s.

The 21.2–22.6s ball movement is dead-ball repositioning, not a pass. The
25.6s free-kick release resumes play, and the controlled reception at 27.4s is
a completed black pass under the project analytics definition.

This example illustrates the required separation:

- official law determines that ordinary play is stopped pending a restart;
- video evidence determines the most likely state interval;
- the project definition determines whether the restart reception is a pass.

## 7. Human review and engine-change workflow

The **Football Event Review** canvas enforces this sequence:

1. Copilot independently adjudicates one event from video evidence and the
   architecture in this document.
2. The user accepts, adjusts, or rejects the proposed reference.
3. The canvas may place the already-prepared review proposal beside the frozen
   engine result for transparent comparison. Engine output must not rewrite or
   silently bias the proposal.
4. If the engine already agrees, no inference change is made; regression
   protection is retained or added.
5. If the event is missing or conflicting, implement a general evidence-based
   rule. Never use a segment timestamp, track ID, or manual label as an
   inference input.
6. Capture a new engine fingerprint and rerun the focused and protected tests.
7. Mark the event `Implemented · Regression Verified` only when the accepted
   behavior matches and every protected test passes.
8. After every proposal has a final decision, publish through the guarded
   Canvas action. It excludes rejected and match-state-only proposals, includes
   independently confirmed unmatched engine events, reruns protected
   regressions, and requires a dynamic one-to-one reference/output match.
9. Mark the segment `Passed` and lock it only after the published manual
   reference is reloaded and independently reported as validated.

Engine snapshots contain:

- Git revision;
- SHA-256 of the rules-engine source files;
- SHA-256 of the generated Test 3 state and event output;
- capture time;
- protected-regression result.

This proves whether an accepted rule was already present, still pending, or
implemented by a later engine version.

## 8. Fast regression contract

Logic changes reuse cached detections and tracks. They must not rerun the source
recording or model inference.

Run focused state and event contracts:

```powershell
$env:PYTHONPATH="$PWD\src"
python -m pytest -q `
  tests\test_match_state.py `
  tests\test_possession.py `
  tests\test_alfheim_blind_regressions.py
```

Refresh Test 3 event logic from cached artifacts:

```powershell
$env:PYTHONPATH="$PWD\src"
python scripts\process-alfheim-segment.py `
  benchmarks\alfheim\generated\segment-0300-020 `
  --events-only
```

Then run the complete repository suite:

```powershell
$env:PYTHONPATH="$PWD\src"
python -m pytest -q
```

The release gate is:

- accepted event behavior matches;
- no extra event is introduced;
- Test 3 match-state intervals remain correct;
- every protected one-minute reference remains exact;
- the complete test suite passes.

## 9. Portability contract

The core remains platform-neutral by requiring:

- pure typed domain values and deterministic state transitions;
- JSON-compatible normalized observations and outputs;
- no UI, operating-system, video-decoder, detector, or model-provider
  dependency inside `match_state.py`;
- platform adapters outside the domain layer;
- versioned law profiles and analytics definitions;
- deterministic fixtures for every accepted behavior.

Python is the current reference implementation. Other runtimes may reproduce
the same state contract as long as they consume the same normalized evidence,
emit the same state/event schema, and pass the shared regression fixtures.

## 10. Change governance

Every rules-engine change must state which category it belongs to:

1. **Law profile update:** an IFAB Law changed or its engine interpretation was
   corrected.
2. **Evidence adapter update:** the legal concept is unchanged, but detection
   of its observable evidence improved.
3. **Analytics definition update:** the project's pass, turnover, possession,
   or shot contract changed.
4. **Inference implementation fix:** code did not satisfy an existing written
   contract.

Do not silently mix categories. Update this document, the law-profile metadata,
or the analytics definition before changing behavior when the contract itself
changes.

## 11. Future architecture concepts (not implemented)

These are durable design notes for forward-looking ideas. Neither is shipped,
partially shipped, or assumed implemented anywhere in this codebase; both are
described in full, with their guardrails, in `.github/copilot-instructions.md`
("Query By Probability" section) and must be kept consistent with it:

- **Query By Probability** — a single primary ("Main") camera covers the
  normal stream; only when its own detection confidence drops for a
  particular frame or short window does the system query the specific
  secondary camera(s) whose field of view covers that moment (e.g. a
  goal-end or touchline camera), fusing that targeted evidence to strengthen
  the decision, then reverting to the Main Camera. It never processes every
  secondary stream for the whole match, and it is not a patentability claim.
- **Continuous, incremental review cadence** — running the existing
  30–60-second controlled-segment discipline as configurable, rolling chunks
  (e.g. 30s or 60s) through the law-grounded match-state engine and its
  analytics event state machines continuously, appending newly validated
  statistics to the screen as more of a match is processed, alongside a
  regularly (e.g. daily) refreshed rules engine. Any such refresh must still
  go through Section 7's guarded review workflow and Section 8's full
  regression suite — general, evidence-based rule changes only, never a
  timestamp/segment/label-specific exception.
