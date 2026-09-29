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

### Hard input boundary: raw video versus evaluation labels

For labelled video datasets, event inference and performance benchmarking use
the raw video as the source of football evidence. Camera calibration and
non-label processing configuration may describe how to interpret that video;
dataset annotations may not participate in interpretation.

Dataset or provider labels for passes, drives, shots, free kicks, possession,
turnovers, or any other event are forbidden inputs to detection, tracking,
classification, match state, event state machines, confidence, thresholds, or
rule execution. They must be stored separately and loaded only after engine
predictions are complete and frozen, solely for evaluation and independent
review. Label timestamps must not narrow an inference search or resolve an
uncertain prediction.

Raw-video speed results must cover the cold path from video decoding through
detection, tracking, inference, and event publication. A run that substitutes
precomputed detections or tracks is a cache-rebuild benchmark and must be
reported separately; it is not a raw-video processing-speed result. Any
annotation leakage invalidates both the affected predictions and benchmark.

Each 30- or 60-second segment is also a production-like streaming deadline.
Fresh processing is the default. Cache reuse is an explicit diagnostic or
interrupted-run recovery option, never the headline performance path. Runtime
reports must include wall time, source duration, real-time factor, achieved
frame throughput, and the minimum acceleration required to publish before the
next configured segment is due.

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
[`src\football_poc\engine`](..\src\football_poc\engine). The legacy
`src\football_poc\possession.py` path is a thin compatibility shim that
re-exports the engine package API, including private helpers still imported by
existing tests.
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
- **Goal:** a separately confirmed match-state event linked to its originating
  shot attempt. A goal also implies that shot was on target, but a
  shot-on-target event does not imply a goal. Saved attempts remain on target;
  absence of a goal is never sufficient evidence for an off-target
  classification.

#### Contact-to-event state rules

These rules provide a concise explanation of how the analytics engine converts
player-ball contacts into passes and turnovers:

| Observed contact | State transition | Analytics result |
| --- | --- | --- |
| A teammate makes the first controlled legal touch after a deliberate play | Sender control → teammate control | Complete the pass at that touch |
| The receiver deliberately redirects the ball with one touch | Teammate control → new pass in flight | Complete the incoming pass immediately; open a new pass candidate |
| An opponent makes a controlled legal touch | Current-team control → opponent control | Complete the turnover at that touch |
| The opponent then deliberately plays to a teammate, who controls it | Opponent control → opponent-teammate control | Complete the opponent's pass at the teammate's touch |
| The ball merely ricochets, is blocked or deflected, or remains contested | Control is unresolved or remains with the prior team | Record contact evidence only; do not complete a pass or turnover |

“Controlled” does not mean retaining the ball for several seconds. A single
touch with sufficient evidence of deliberate reception or direction is enough,
including a legal touch with the foot, head, chest, thigh, or another permitted
part of the body. Continued tracking may confirm player identity and distinguish
a real controlled touch from a detection flicker, but it must not delay the
event timestamp. A pass and a later turnover are separate events even when they
occur close together.

An event must satisfy both its analytics definition and the match-state gate.

#### Stage modules

The cached event-inference path is split into readable Python stage modules.
Each stage owns a frozen settings dataclass with the current threshold defaults,
and the stage-golden test records JSON-serialisable outputs from the current
published segment artifacts.

| Order | Stage | Module(s) | Inputs | Output |
| --- | --- | --- | --- | --- |
| 1 | Ball-evidence annotation | `engine.ball_evidence` | Cached ball tracks plus optional ball-state estimates selected by `has_ball_state_estimates` | Evidence provenance summary and event-eligible ball samples |
| 2 | Ball control and touch candidates | `engine.ball_control`, `_control_observations` in `engine.ball_evidence` | Player tracks, ball evidence, flyby/contact settings | Control observations keyed by frame, team, player, and control ratio |
| 3 | Possession ledger | `engine.possession_ledger`, `engine.contact_helpers` | Control observations, smoothing, player continuity, jersey evidence | Chronological team/player possession segments |
| 4 | Completed-pass inference | `engine.completed_pass`, `engine.pass_reconciliation`, `engine.flight_receptions`, `engine.advanced_passes`, `engine.pass_cleanup`, `engine.pass_recovery`, `engine.pass_recovery_extra` | Possession segments, ball flight/deceleration evidence, receiver continuity | Completed pass candidates with release and controlled-reception evidence |
| 5 | Turnover inference | `engine.turnover`, `engine.turnover_refinement` | Possession segments, pass candidates, opponent-control evidence | Turnover candidates attributed to the team losing controlled possession |
| 6 | Boundary and restart reconciliation | `engine.boundary_restart` | Boundary candidates, restart release evidence, ownership lookback | Boundary turnovers, restart passes, and rejected boundary diagnostics |
| 7 | Shot inference | `engine.shot` | Possession/player continuity, ball motion, calibrated goal context and runtime shot evidence | Shot and shots-on-target analytics candidates where evidence is available |
| 8 | Live/detected ball-state variants | `engine.live_segments`, `engine.live_turnovers`, `engine.live_refinement`, `engine.live_recovery`, `engine.live_helpers` | Earlier stage inputs plus detected-source ball-state estimates | Detected-source variants that preserve direct-coordinate evidence gating |
| 9 | Match-state glue/export | `engine.match_state_export`, `engine.pipeline` | Analytics candidates, boundary/restart evidence, `MATCH_LAW_PROFILE` timeline | `predicted-events.json`, `match-state-events.json`, and possession-stage export |

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

The Innovation **Football Event Review** canvas is manual-first:

1. The professional reviewer watches the prepared segment and records `M#`
   events at the current playhead. Each click saves a draft immediately.
2. The reviewer corrects team, canonical event type, or approximate
   millisecond time as needed. Event identities, order, and counts are the
   golden claim; timestamps are navigation evidence and need not equal engine
   timestamps exactly.
3. The canvas compares `M#` with frozen rules-engine `E#` output automatically.
   A one-to-one match appears immediately when a unique unused E# has the same
   team and canonical event type within one second. This tolerance reflects
   sampling and human playhead placement; it does not rewrite either
   timestamp. Ambiguous events or events more than one second apart remain
   visibly unmatched; there is no arrow-based manual mapping.
4. The reviewer approves the complete minute when the ordered `M#` set and
   counts are correct. Approval does not require complete mappings, exact
   timing, same-frame agreement, Copilot review, an engine rerun, or
   regressions.
5. Approval freezes an immutable, fingerprinted golden revision. A later
   correction creates a new draft revision.
6. Historical `C#` proposals remain optional, read-only diagnostic state and
   are not rendered in the active review UI. They never control M#
   creation, counts, mappings, approval, publication, or inference.
7. Investigate only selected missing, extra, mistyped, mis-teamed, mistimed, or
   misordered E# discrepancies. An unmatched M# exposes a review guide where
   the reviewer can distinguish an entirely missing E# from a nearby E# that
   represents the same play with incorrect timing, team, or canonical type;
   reopen the M# editor; reject an unsupported M# while retaining its visible
   audit record; remove an M# entered in error; or request independent
   adjudication when the camera is inconclusive. A rejected M# remains visible
   but is excluded from matching, golden counts, approval, and publication.
   Removal is reserved for erroneous data entry. Cancelling or closing the
   guide changes nothing. Choosing confirmed-missing or incorrect-E#-details
   explicitly accepts that frozen M# as the required evaluation result.
   Copilot must not reject, edit, or reinterpret it; raw video and cached
   runtime evidence are then used to diagnose and correct only the general
   pipeline cause. Those choices do not rewrite M# or force a manual link.
   Diagnosis, implementation, cached rebuilding, protected tests, comparison
   refresh, and the final response must complete in the same single Autopilot
   request; do not launch a separate Plan, adjudication, or follow-up request.
   The inconclusive choice remains an independent adjudication request. If the
   engine agrees, no Copilot call, inference change, or regression is required.
8. If a discrepancy requires an engine correction, implement a general
   evidence-based rule. Never use an M# timestamp, segment, track ID, or manual
   label as an inference input.
9. After an engine change, capture a new engine fingerprint, rebuild cached
    event output for the current segment only, add a unit test for the rule
    under `tests\rules` or `tests\tracking` named
    `test_<rule>_YYYYMMDDTHHMMSSmmmZ` (UTC milliseconds), regenerate
    `tests\RULE_INDEX.md` with `python scripts\generate-rule-index.py`, and
    run the fast rule unit-test gate (`regressionTests` in the workflow
    adapter). A failing test names the broken rule. Re-running every published
    segment against its publication hash is an on-demand check (Canvas
    segment regression and publication), not a per-change gate; fix any
    failure there by adding a new timestamped unit test. Ball-tracker changes
    use the same fast unit tests; the full-video stage goldens
    (`tests\ball_stages`, opt-in via `FOOTBALL_RUN_BALL_GOLDENS=1`) are for
    refactors only.
10. Mark the segment passed only when current E# output satisfies the approved
    golden reference and every protected publication gate passes.

The Innovation header may open a separate, optional **M# Ledger Audit**. This
is deterministic local code, not a Copilot or model review. It reads only the
current M# draft and can flag possible duplicates, same-frame timing conflicts,
possession-team discontinuities, turnover-attribution inconsistencies, and
long event-free intervals. Every result is advisory: it cannot change M#,
block approval, reveal or inspect E#, or overrule the professional reviewer's
continuous-video decision. A reviewer may correct M# or confirm that an
advisory is not applicable; confirmations are tied to the current M# revision
and become stale after any manual edit. Restart and shot/SOT checks are not
claimed while those event types are absent from the manual-review schema.

The pre-manual-first Innovation segments are retired from active review and
protected regression coverage. Their artifacts remain historical records but
must not be presented as current M# references or regression baselines. The
04:00–05:00 segment is the first candidate in the replacement regression line;
it becomes baseline one only after its independent M# review and full
publication gate complete.

### Review decision preflights

The compact comparison table has permanent Manual `M#` and Engine `E#`
columns. Editing an M# time, team, or event type saves automatically and
immediately recomputes exact one-to-one M#/E# matches. The working panel has no
manual arrows or mapping controls. Copilot `C#` history appears only through
its read-only toggle. An `E#` guide applies to a selected discrepancy and
explains the evidence outcomes below.

Opening `E#` verification must first show a decision guide; it must not
immediately launch Copilot, spend AI credits, grant temporary authorization,
or alter review state. The guide explains these evidence outcomes:

Both the E# and unmatched-M# decision modals show the same visibly pulsating
`Copilot is working…` status while, and only while, the selected review's
activity state is `working`. Retaining the selected E#/M# conversation after a
response must not keep either modal active. Publishing the final response
changes activity out of `working`, automatically closes the corresponding
modal, refreshes the M#/E# rows, and retains the conversation separately.

When the reviewer chooses that an E# represents the same play but has incorrect
details, they may enter an alternative completion time to seek and inspect that
video moment. The field is hidden for other decisions. This inspection time may
focus the evidence review and Copilot diagnosis, but it does not alter M#,
rewrite E#, create a manual link, or become an inference input. Only a general
engine correction and rerun may replace E#.

Every E# verification resolves the current event by canonical type, team,
release time, and completion time; E# numbers are display ordinals and may
change after any rebuild. Once the M# reference is frozen, verification checks
whether that exact current E# has a unique same-team, same-type M# within the
one-second review tolerance, then inspects the relevant cached runtime evidence.
This comparison is evaluation-only: M#, its timestamp, and the reviewer verdict
must never affect event inference, thresholds, or engine rule execution.

- **Correct — exact event is supported:** the professional reviewer can see
  that the team, canonical event type, and completion time are all correct.
  Their explicit approval creates a hash-bound human review receipt directly.
  Because this exact E# already exists, no further Copilot review, engine
  check, engine change, or regression run is needed.
- **Event exists, but details are wrong:** an event occurred, but its team,
  canonical type, or completion time differs. The exact `E#` is not confirmed;
  an explicitly requested Copilot review may document the mismatch and
  diagnose the general engine cause.
- **Incorrect — no such event occurred:** the exact `E#` is unsupported. An
  explicitly requested Copilot review may record it as not confirmed and
  diagnose the general engine cause.
- **Cannot verify from this camera:** occlusion, framing, or insufficient
  evidence prevents a reliable decision. An explicitly requested Copilot
  review may inspect the targeted prepared context, but unresolved evidence
  must remain unconfirmed rather than become a guessed verdict.

Copilot escalation is a separate explicit action after the reviewer chooses an
outcome; it is never an automatic consequence of opening the guide. The
reviewer may also request independent Copilot adjudication without first
stating a verdict. Cancel or close leaves the event, authorization, receipts,
and conversations unchanged. A direct human confirmation records
`reviewSource=professional_reviewer` with the current engine-source and
cached-output hashes; it must become stale when either hash changes. An
`M↔E` link alone remains insufficient proof of football correctness.

Protected regressions run only after a rules-engine change. They are required
when an approved M# discrepancy causes a general engine change, or when
diagnosis of an incorrect E# produces such a change. Capturing or editing M#,
mapping M# to E#, approving the golden minute, confirming an already-existing
correct E#, asking a Plan-mode question, or cancelling a review does not run
regressions.

### Fast independent review

An authorized review should complete as one bounded manual
adjudication pass, not as a frame-export or engineering investigation. Watch
the prepared 30–60-second Canvas video and use the quick-capture actions
to record completed passes, turnovers, and shots on target at the
playhead. Review the ordered
list and team/type counts, make corrections, map useful E# comparisons, then
approve the complete minute as golden. The current scope is completed passes,
turnovers, and shots on target (always analysed; see below); shots and fouls
otherwise remain disabled. Use the segment's selected ball source and prepared
player context only to clarify an uncertain moment. Do not replace continuous viewing with
frame-by-frame export, exhaustive coordinate analysis, an automatic Copilot
pre-review, or a new inference run.

### Shots on target (always analysed, evidence-gated)

`src\football_poc\shots_on_target.py` implements the SOT analytics
contract above. The persisted definition name remains the frozen identifier
`innovation-sot-v1`; it is a project statistic, not an IFAB statistic. Every
review engine run analyses shots on target; there is no opt-in setting. The
runner rebuilds the runtime evidence file `shot-evidence.json` in the segment
root (`source_kind: innovation_runtime_shot_evidence`, also a frozen persisted
identifier) before every event build and applies the classifier only when that
evidence passes its readiness check.
That file must
supply calibrated goal geometry (goal line, posts, crossbar, uncertainty),
team attacking directions, observed 3-D ball samples, deliberate-release
intent records, contact roles (goalkeeper, last-line defender, outfield,
woodwork), and separately supported valid-goal facts. Frozen BAC image
coordinates alone cannot establish height, so the runtime adapter
`src\football_poc\shot_evidence_adapter.py`
(`innovation-shot-evidence-v1`, a frozen persisted identifier) builds the file
from frozen runtime inputs
only: BAC ball tracks, cached player tracks and goalkeeper roles, the
goalkeeper-affiliation config (attacking directions), engine match state,
and the calibrated goal mouths in `pitch-calibration.json`.
`goal_calibration.py` (`innovation-goal-face-v1`) fits one goal-face
homography per goal from the four image corners and the Law 1 goal size
(7.32 m × 2.44 m). Its uncertainty is the worst-case shift under ±4 px corner
error plus a 0.25 m monocular depth margin (about 0.5 m on Alfheim).
Because one camera cannot measure height in flight, height evidence comes
only from **goal-face arrivals**. An arrival requires a fast approach
(≥ 400 px/s within 1 s) that arrests (speed ≤ 0.35 × approach) inside a
40 px zone around the face. The median arrested position is projected onto
the goal plane. Release is the last player-foot contact 0.4–3 s earlier.
Intent is `scoring_attempt` only for a direct approach toward the kicker's
attacking goal. An opponent within 0.4 s of the arrest is a contact.
A face arrival resolves as:

- on target (`stopped_at_goal_face`, confidence 0.65) when the ball arrests
  inside the face and play stays live for 2 s;
- off target (`wide_or_high`) when it arrests outside the face and a
  stoppage follows;
- unresolved otherwise.

These thresholds are provisional. They were fixed before comparison but have
only one positive example, and they need multi-segment validation. Known
monocular ambiguity remains: a catch in front of the goal can project inside
the face. The adapter output is a BAC-assisted diagnostic, not raw-video
ball inference. Manual labels, M#/C#, or provider events must never
populate it.

Each attempt resolves at most once as on target (valid goal, goalkeeper save,
or last-line save of a goal-bound path), off target (wide/high, woodwork out,
keeper collecting an off-target path), blocked (ordinary block), excluded
(dead-ball release), or unresolved with an explicit reason. A goal after
woodwork or a save counts once; a rebound is a new attempt only after an
intervening contact; repeated observations and track handoffs are merged by
attempt identity (`sot-v1-<team>-<release frame>-<goal>`), not by debounce.
The outcome may fall at its own goal/stoppage transition; an earlier stoppage
leaves the attempt unresolved. One `shot_on_target` row per on-target attempt
is merged into `predicted-events.json` (outcome time is `completion_seconds`),
and `analytics-data\shots-on-target.json` records status
(`unavailable`/`partial`/`complete`), per-team counts, total, unresolved
reasons, and fingerprints. Unavailable totals are null, never zero; the Canvas
shows `—`, and `*` for partial counts. Unavailable or zero-attempt runs leave
`predicted-events.json` unchanged. The Canvas engine-output hash covers
`predicted-events.json` (including any SOT rows) and match state, not the
derived SOT summary, so published pass/turnover segments whose events are
unchanged keep their publication hash; any added SOT row is an E# difference
that fails the published-segment regression. Publication is blocked unless
SOT status is `complete`, or when golden M# includes SOT that the engine
output does not analyse.

The **Process AI** action runs only the cached rules engine for the segment's recorded `ball_source`. It does not automatically launch the optional independent C# protocol.
The M# Ledger Audit remains a separate optional local-code check and is not an
independent visual review.

An explicitly requested independent Copilot `C#` review may instead use a
complete local visual sequence exported directly from the same prepared video.
That sequence must contain every source frame exactly once in chronological
order with frame indices and timestamps, retain the full-pitch frame, and may
add a synchronized frozen-BAC ball-centred zoom. The export manifest establishes
source identity and complete coverage only; it is never football-event evidence.
Copilot must still inspect release, travel, nearby players, reception, visible
kit identity, and match state from the images themselves, complete the
possession ledger and continuity pass, and abstain where visual control is not
supported. Sampled sheets, missing frames, inferred cache events, M#, and E#
cannot substitute for this complete sequence.

Independent C# protocol version 5 must use two distinct passes. The first pass
persists a chronological visual touch-candidate ledger containing supported,
rejected, and unresolved contacts before any final event adjudication. The
second pass derives the possession ledger and proposals from those frozen touch
candidates. Every event-bearing possession transition must reference its
supported release or possession-loss candidate and controlled-touch candidate,
then map one-to-one to a C# proposal.

The protocol must also persist contiguous review windows no longer than three
seconds covering the complete clip. Every touch candidate and proposal
completion must appear in exactly one coverage window. Every possession-ledger
interval longer than three seconds must include full-resolution checkpoints no
more than 1.5 seconds apart and identify the touch candidates considered within
that interval. Boolean claims that a ledger or continuity pass was completed
are not sufficient evidence. Full-resolution continuous playback is mandatory
as the primary visual channel. Individual full-resolution source frames may
supplement playback, but tiled contact sheets cannot establish uninterrupted
travel or the absence of an intermediate controlled touch.

Freeze the complete ordered `M#` set and explicit mappings atomically,
including an approved zero-event set when no event is supported. This fast path
never permits E#, C#, provider labels, or earlier decisions to create or alter
the manual reference.

The Canvas enforces that separation as a visible three-stage gate:
**Freeze manual M# reference as golden**, then **Validate engine against golden
reference**, and finally **Publish Passed segment**. E# output and automatic
M↔E suggestions remain hidden until validation fingerprints the frozen M# set
and current engine output. Publication remains disabled until every golden M#
has one current E# match, every extra E# has a current independent resolution,
and the protected regression and publication gates pass.

Engine snapshots contain:

- Git revision;
- SHA-256 of the rules-engine source files;
- SHA-256 of the generated Test 3 state and event output;
- capture time;
- protected-regression result.

This proves whether an accepted rule was already present, still pending, or
implemented by a later engine version.

### 7.1 Single review workflow and ball-source boundary

Alfheim review now has one workflow, `football_review`, one Canvas,
`football-event-review`, and one rules engine in `src\football_poc`. Runtime
artifacts are flat under the prepared segment root. Each processed segment
records its `ball_source` in `segment.json`, `analysis-status.json`,
`analytics-data\run-provenance.json`, PostgreSQL segment metadata, and the
append-only `segment_outputs` history.

- **BAC (`ball_source: bac`)** uses frozen Alfheim BAC coordinates. BAC is a
  BAC-assisted diagnostic of the downstream football engine, never raw-video
  ball inference and never a valid ball-tracking performance benchmark. Its
  ball-track artifacts intentionally retain frozen identifiers such as
  `evaluation_only_provider_coordinates`, `innovation_day_bac_assisted`,
  `reviewer_corrected_innovation_coordinates`,
  `detector_implementation: innovation_showcase_sequential_v1`, reason codes
  such as `innovation_ball_source_mismatch`, and suite name `innovation`.
  These names are historical output contracts, not separate workflows.
- **Detected (`ball_source: detected`)** uses raw-video detector output and
  `ball_tracking.py`. BAC, manual references, and provider event annotations
  are rejected as inference inputs. Its 90% direct-coordinate provenance
  target measures evidence coverage, not coordinate correctness or calibrated
  confidence. By default (`--runtime-mode review`) the run stops after ball
  tracking and the Canvas shows each frame's ball state; the reviewer can ask
  Copilot questions and then choose **Continue to rules engine**, which runs
  `--events-only` whatever the coverage. `--runtime-mode production` reports
  the coverage and continues straight to the rules engine;
  `--runtime-mode validation` still blocks below 90%. Every sampled frame's
  ball state reaches the rules engine, which uses only direct-evidence frames
  to prove touches, speed, and direction. Increasing
  evidence-backed confidence is the objective; adaptive thresholding remains
  future work until implemented and independently validated.

The Canvas **Run ball coordinates** action chooses the source for a segment.
**Change ball source** requires confirmation, is blocked while a job runs or
another developer holds the lease, and deletes the segment's derived artifacts
and review work except the M# golden set. The previous `segment_outputs`
revisions remain as append-only database history.

Review state lives only in PostgreSQL under workflow `football_review`. The
retired `30-shared-baselines\event-review-state-*` JSON files are not read or
written as mutable state, and there is no JSON fallback. When coordination is
unavailable, review state is read-only. Media and binary caches stay in the
OneDrive artifact share.

`src\football_poc\possession.py` now has one possession rules path: the
selected ball source changes only the coordinate input, while BAC and detected
coordinates run through the same smoothing, segment-building, possession, and
event rules. During consolidation, adopting the removed Live-only variants as
the single implementation did not preserve the protected published set: the
four BAC publications still match exactly on the single path, but the detected
0540-020 publication remains a pending review mismatch until a general
evidence-based rule change or re-review resolves the difference.

### Detected ball confirmation cascade

The detected-ball tracker is split under `src\football_poc\ball` while
`src\football_poc\ball_tracking.py` remains an import-compatible shim. Cached
rebuilds use the shared frame and detection cache layer in `ball\frames.py` and
`ball\io_filters.py`; this cache-rebuild path must remain labelled separately
from a fresh raw-video detection, tracking, inference, and publication run.

Detected coordinates are now published through an append-only frame ledger rather
than a free-form sequence of stages that can later remove earlier points. The
ledger has one entry per sampled frame. Each entry starts `unresolved`; the first
module that satisfies its evidence gate may mark it `confirmed` with x/y,
confidence, confirming module, evidence, and detected-source attribution. A
confirmed frame is a lock: later modules may read it as context, but they cannot
edit, unconfirm, or remove it. Failed attempts append rejection reasons to the
unresolved entry. The time machine runs last and gives every remaining frame an
estimate, so each sampled frame reaches the rules engine with a coordinate, an
uncertainty radius, and a ball state.

`track_cached_balls` applies the confirmation cascade in this fixed order (the
module labels are stable identifiers, so `02_time_machine` runs last), and the
ball-stage golden harness names files with the same module labels so the first
changed module is visible:

| # | Module | Responsibility |
| --- | --- | --- |
| 1 | `01_confirm_yolo` | Lock real YOLO ball detections only after detector confidence, player/upper-body exclusion, neighbouring motion consistency, and static-object rejection agree. Static detections that remain within a few pixels over a long span without nearby player or motion support are rejected here before they can become track anchors. Unselected detector candidates near a player's feet must also be reachable at the maximum ball speed from the nearest confirmed ball on each side; among reachable alternatives the strongest detection is tried first, so one weak lock-in cannot drag a false chain along. The trajectory's own pick loses that priority when it is isolated (not part of a moving chain) and a stronger non-static detection exists in the same frame; it is then checked like any other candidate after the stronger ones. A static object never counts as neighbouring motion support. Ball colour: a weak (below 0.25) detection near a player's feet can be a boot, so the pixels inside it whose colour (not brightness) differs from the surrounding grass must match the red-green colour range of this video's own strong (at least 0.5) detections (5th–95th percentile, at least ±5 Lab units); otherwise it is rejected (`colour_differs_from_ball`). Without video or at least 5 strong detections the colour check does not apply, and a detection with nothing standing out from the grass is not rejected on colour. Inside a gap with no confirmed ball within 3 sampled steps, a detection still confirms when it belongs to a moving chain (at least 3 linked non-static detections, at most one missed sampled frame between links, peak confidence at least 0.3) that the last and next confirmed ball can reach. After the first pass, a weak (below 0.5) detection that is weaker than both confirmed neighbours within 3 steps and makes a detour larger than a quarter of the maximum ball speed over that bracket is withdrawn (detour_from_consistent_confirmed_neighbours); a second pass may replace it only with a candidate reachable from the confirmed ball. A weaker detection far from two bracketing detections that agree the ball is resting within 3 s is withdrawn. Resting-ball persistence: once two detections within 3 s agree on one resting spot, with no equally strong detection elsewhere between them, each neighbouring frame keeps the ball there (`resting_ball_persistence`, `visually_reacquired`) while the pixels in the ball disc still match the detected ball and still contrast with the surrounding grass. The check tolerates the ball being covered for up to 3 s when it is seen at rest again afterwards: covered frames stay unresolved and cannot be claimed elsewhere by later modules. A weak (confidence below 0.5) detection elsewhere, or a second resting spot inside that span, is withdrawn because there is one ball. |
| 2 | `03_motion_and_optical_flow` | Try raw-motion, Kalman-guided visual reacquisition, and dense optical-flow proposals for unresolved frames; each proposal must pass its module gate and the confirmed-neighbour plausibility gate before locking. That gate also rejects a proposal far from two confirmed neighbours that show the ball resting at one spot within 3 s. |
| 3 | `04_focused_multiscale` | Run the existing focused multiscale re-detection on cached crops only, never a full-video detector rerun, and lock only unresolved frames that pass the cascade gate. |
| 4 | `05_short_stationary` | Apply short stationary template recovery for unresolved frames that are supported by the locked context and pass the cascade gate. |
| 5 | `06_time_machine_region_search` | Use the time machine's reachable region to guide a new search. For each unresolved frame, the region is the area the ball can reach at the maximum ball speed from the nearest confirmed frames before and after (at least 48 px). Regions wider than 480 px are skipped. The region is searched at full resolution in 640 px tiles, so a small ball is not shrunk. A detection counts only when it has confidence of at least 0.5, is 0.5–2× the anchor ball size, is within reach of every anchor, is outside player upper bodies, and passes the confirmed-neighbour gate. The 0.5 floor is set from a video check: weaker detections in the region were mostly coloured boots and pitch markings. Smaller regions are searched first; each confirmation narrows its neighbours' regions for up to three passes (`time_machine_region_detector`, `visually_reacquired`). A frame with no acceptable detection stays unresolved. |
| 6 | `02_time_machine` | Estimate every frame still unresolved after visual recovery. Gaps of at most 1.2 s between confirmed frames are interpolated, and frames within the short one-sided bound hold the nearest confirmed position, with a small uncertainty radius. Longer gaps and segment edges get a best-guess point plus a possible-region radius equal to the distance the ball could travel at the maximum ball speed, capped at half the frame diagonal. A segment without any confirmed frame gets the frame centre with that cap. |
| Final | `final` | Write the locked track, unresolved ledger states, per-frame confirming module/rejection metadata, and a per-module summary in `ball-tracking-summary.json`. |

Every sampled frame has exactly one ball state:

| State | Produced by | Meaning | Rules-engine use |
| --- | --- | --- | --- |
| `observed` | `01_confirm_yolo` | YOLO detected the ball in this frame and the detection passed the confirmation gates. | Direct evidence: touches, speed, direction. |
| `visually_reacquired` | `03`, `04`, `05`, `06` | Another visual method found the ball in this frame; the method is recorded in `evidence`. | Direct evidence; precision can be lower than a YOLO detection. |
| `trajectory_estimated_bidirectional`, `trajectory_estimated_forward`, `trajectory_estimated_backward` | `02_time_machine` | Not seen in this frame; estimated from nearby seen frames within the short bounds. | Continuity and proximity only; never a touch. |
| `trajectory_estimated_possible_region` | `02_time_machine` | Not seen, and the nearest seen frame is too far away. A best-guess point plus the reachable radius. | Only whether the ball could be at a location; never control or a touch. |

Each state records its confirming module, evidence method or mode, anchor
frames, uncertainty radius, and every earlier module's rejection reasons. The
tracker never labels why the ball was not seen (occlusion, out of shot, blur)
without evidence. Direct provenance in `src\football_poc\ball_provenance.py`
counts `observed` and `visually_reacquired` frames; time-machine frames are
never direct and carry `interpolated: true`.

The workflow identity is carried and checked at every review boundary:

| Workflow | Canvas ID | State `workflowId` | Artifact layout |
| --- | --- | --- | --- |
| Football review | `football-event-review` | `football_review` | flat segment root with recorded `ball_source` |

Every Canvas-to-Copilot prompt repeats the single workflow identity and the
segment's ball source. Theme, display name, or segment ID must never select
inference behavior.

## 8. Fast regression contract

Logic changes reuse cached detections and tracks from their own workflow. They
must not rerun the source recording or model inference.

Regression comparison is exact for published output. Preserving every old event
while adding new events is still a failure because an added false positive
changes the locked reference and published statistics. If a justified general
rule adds, removes, retimes, or reclassifies an event in a published segment,
that segment must be independently reviewed and republished before it can
become the new baseline.

An additive match-state provenance upgrade is not a football regression when
all events and match-state behavior remain exact. The regression comparator may
ignore only `schema_version`, the top-level `law_profile`, and per-transition
`law_reference` while comparing behavior. It must still report the metadata
upgrade, and any interval, transition timing, state, restart, boundary,
confidence, event, team, or event-time difference remains blocking.

When the planned ball-coordinate auto-verification contract is implemented,
the live regression artifact must compare both the final coordinate and its
complete per-gate trace. A final-state match with a changed or weakened
evidence path is not sufficient. Independently confirmed passing receipts are
protected by the fail-forward rules in Section 7; runtime traces remain
separate from evaluation expectations.

Run the review engine contracts:

```powershell
$env:PYTHONPATH="$PWD\src"
python -m pytest -q `
  tests\test_shots_on_target.py `
  tests\test_shot_evidence.py `
  tests\test_possession_regression.py `
  tests\test_match_state_regression.py `
  tests\test_review_regressions.py `
  tests\test_ball_tracking.py `
  tests\test_match_state.py `
  tests\test_possession.py
```

Refresh cached event logic only for the segment's recorded ball source:

```powershell
$env:PYTHONPATH="$PWD\src"
python scripts\process-alfheim-segment.py `
  benchmarks\alfheim\generated\segment-0180-020 `
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

### Developer-mode review contract

The review Canvas may expose an opt-in Developer mode to reduce repeated
AI handovers. It is an implementation aid, not a second adjudication path:

- code locations, focused tests, cached event-rebuild commands, protected
  regressions, clipboard actions, and output refreshes are deterministic local
  operations and do not invoke event-review AI;
- a developer may edit code and run the displayed commands manually;
- **Do it, Copilot** is a separate explicit coding handover and is available
  only for an already accepted C# whose current engine output does not agree;
- **Rerun rules engine only** means running the cached `--events-only` stage
  without editing code, detection, tracking, or review state;
- neither successful commands nor refreshed E# output accept, reject, confirm,
  or publish an event;
- C# acceptance/rejection and E# confirmation remain available only through
  the normal or expanded event-review controls;
- review labels and provider annotations remain evaluation-only in both manual
  and Copilot-assisted developer workflows.

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
