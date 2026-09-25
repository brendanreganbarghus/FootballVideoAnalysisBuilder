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
   are not rendered in the active Innovation review UI. They never control M#
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
    event output for every published segment in that workflow, compare each
    result with its publication hash, and run focused and protected tests.
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

### Fast independent Innovation review

An authorized Innovation review should complete as one bounded manual
adjudication pass, not as a frame-export or engineering investigation. Watch
the prepared 30–60-second Canvas video and use the quick-capture actions
to record completed passes, turnovers, and (optionally) shots on target at the
playhead. Review the ordered
list and team/type counts, make corrections, map useful E# comparisons, then
approve the complete minute as golden. The Innovation scope is completed passes
and turnovers, plus shots on target when the opt-in SOT analysis is enabled
(see below); shots and fouls otherwise remain disabled. Use frozen BAC and prepared player context only to
clarify an uncertain moment. Do not replace continuous viewing with
frame-by-frame export, exhaustive coordinate analysis, an automatic Copilot
pre-review, or a new inference run.

### Innovation shots on target (opt-in, evidence-gated)

`innovation_day_snapshot\shots_on_target.py` implements the SOT analytics
contract above (definition `innovation-sot-v1`, a project statistic, not an
IFAB statistic). It is off by default. The Canvas **Enable shots on target**
setting writes `innovation\shots-on-target-setting.json` only after a
readiness check of the runtime evidence file `innovation\shot-evidence.json`
(`source_kind: innovation_runtime_shot_evidence`) succeeds. That file must
supply calibrated goal geometry (goal line, posts, crossbar, uncertainty),
team attacking directions, observed 3-D ball samples, deliberate-release
intent records, contact roles (goalkeeper, last-line defender, outfield,
woodwork), and separately supported valid-goal facts. Frozen BAC image
coordinates alone cannot establish height, so the runtime adapter
`innovation_day_snapshot\shot_evidence_adapter.py`
(`innovation-shot-evidence-v1`) builds the file from frozen runtime inputs
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
reasons, and fingerprints. Disabled or unavailable totals are null, never
zero; the Canvas shows `—`, and `*` for partial counts. Disabled runs leave
`predicted-events.json` and output hashes unchanged, and published
pass/turnover-only segments keep their scope unless reprocessing is
explicitly authorized. Publication is blocked unless SOT status is
`complete` whenever SOT is in scope, or when golden M# includes SOT that the
engine output does not analyse.

The **Process AI** action runs only the cached BAC-assisted Innovation rules
engine. It does not automatically launch the optional independent C# protocol.
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

The Innovation Canvas enforces that separation as a visible three-stage gate:
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

### 7.1 Separate Innovation and live review lines

Alfheim review has two deliberately isolated workflows. They may read the same
raw-only prepared video manifest, camera calibration, and immutable
`copilot-review.json` produced from that video before either engine is exposed.
This keeps the evidence-scoped `C#` proposals identical while each Canvas
matches them independently. The workflows never share runtime manifests,
detections, tracks, `E#` events, decisions, fingerprints, regression receipts,
manual references, or publication locks.

- **Innovation Day** uses explicitly labelled BAC provider coordinates with
  the separately versioned engine under
  `src/football_poc/innovation_day_snapshot`. Its artifacts live under each
  segment's `innovation/` directory. BAC is resolved only by
  `process-alfheim-innovation-segment.py`; it never enters the shared prepared
  manifest. Its possible out-of-bounds intervals are derived by comparing BAC
  positions with the shared Alfheim pitch calibration; they are evidence
  candidates, not camera calibration data or assumed referee decisions. This
  is a diagnostic/demo workflow and cannot produce raw-video performance
  claims. Player detection is also frozen to the trusted Innovation profile:
  the approved YOLO11n checkpoint (verified by SHA-256), confidence `0.12`,
  image size `960`, stride `5`, tile width `1484`, full-height horizontal
  tiles, overlap `0.1`, and NMS IoU `0.5`. The runner rejects a model override
  with any other filename or checkpoint hash. Detection executes through the
  Innovation-only `football_poc.innovation_day_detector` module, preserving
  the showcase pipeline's sequential frame inference. It does not import or
  execute the mutable live `benchmark_cli` detector path.
  After evidence preparation, the Canvas stores a complete segment-scoped copy
  of the frozen BAC coordinates in shared review state. Reviewer changes are
  versioned against that immutable base and do not modify the BAC artifact.
  Once a correction batch is approved, its materialized coordinate layer
  becomes the current Innovation input for that segment. Existing YOLO player
  detections are always reused. Player tracking is rebuilt when it has already
  run because it consumes ball coordinates; if the Innovation event engine has
  also already run, possession and event outputs are rebuilt afterward. An
  engine that has not yet run remains an explicit separate action after player
  tracking is refreshed.
  Exact-prefix comparisons may declare namespace-specific `innovation_video`
  and `live_video` sources while retaining a separate `playable_video`. Both
  inference sources must cover the declared frame range; this avoids
  re-encoding drift without sharing runtime artifacts.
  Player-team stabilization and terminal possession reconciliation are causal
  at a segment boundary: a shorter segment must preserve all player evidence
  and completed events supported before its final frame. A terminal,
  confidently controlled turnover may resolve an earlier contested contact,
  and repeated strong control at the boundary may confirm a direction-change
  reception, but neither rule may inspect frames outside the declared segment.
- **Live** uses raw-video detector output, iteration-25 ball tracking, and the
  current engine. Its artifacts live under each segment's `live/` directory.
  BAC, manual references, and provider event annotations are rejected as
  inference inputs. When trustworthy ball coordinates resume after a long
  tracking gap, a reception may be recovered only from a real local closest
  approach, consistent team control before the gap, and a following same-team
  release. This degraded-evidence rule never creates a coordinate or fills a
  missing frame. A reviewed segment enters `live-regressions.json` only after
  the live publication gate passes.

The validated live detector profile samples every fifth source frame. A
stride-1 diagnostic must be reported separately and must not replace the
validated profile merely because it yields more points: denser detections also
require possession and event inference to remain sampling-rate invariant.

#### Ball Time Machine

**Ball Time Machine** is the user-facing name for **Temporal Ball Coordinate
Recovery**. When the detector cannot establish a ball coordinate for a sampled
frame, the tracker examines the preceding and following raw-video frames,
moving backward and forward through the local temporal window to determine
whether the missing coordinate can be recovered from a consistent trajectory.
It uses only raw-video detections and tracking evidence; dataset event labels,
manual review labels, and provider coordinates are forbidden inputs.

A coordinate produced by this process remains a bidirectional or forward
trajectory estimate with its uncertainty and source-frame provenance intact.
It is not a direct detector observation, does not count toward the minimum 90%
direct-coordinate requirement, and must not be presented as a ball that was
visibly detected in the missing frame.

Recovery is finalized in a deterministic order. The tracker first establishes
trusted sampled anchors, then resolves gaps from the nearest trusted anchor on
each side, and finally applies a whole-trajectory integrity pass before state
publication. A lone recovered point is discarded when stable support exists
on both sides and that point creates an unsupported out-and-back excursion.
Discarded points are not reused as recovery anchors. Long vertical gaps may
use a bounded acceleration-aware curve when an adjacent trusted velocity
supports it; otherwise they remain linear estimates with their uncertainty.
Neither form of interpolation becomes direct event evidence. A single missing
sample between stationary direct YOLO or focused-redetection anchors may become
evidence-backed recovery only when independent templates from both endpoints
match the same raw-video pixels with strict score and spatial-agreement gates.
The recovered point then passes the whole-trajectory integrity check again.

The 90% provenance threshold is a blocking development and localhost
validation gate. Production live processing records the same provenance
result and degraded-evidence status but does not pause the match pipeline for
human review. Production continuation never promotes estimated coordinates:
event inference must preserve and enforce each coordinate's evidence class.

#### Planned ball-coordinate auto-verification contract

This contract is required after the current YOLO and ball-coordinate
investigation is complete; it is not implemented by the current 90% provenance
gate. Direct coverage measures how many coordinates were produced, not whether
they are correct. Production must ultimately require each coordinate to earn
an evidence-based `auto_verified`, `ambiguous`, or `unresolved` result without
routine frame-by-frame human approval.

An `auto_verified` coordinate must pass the complete, versioned gate stack:

1. exact-frame visual evidence from broad detection, focused redetection, or
   validated raw motion;
2. pitch and player context, including feet support and upper-body/static-object
   rejection;
3. temporal support from nearby past and future raw-video evidence;
4. a sufficient winning margin over every credible competing candidate;
5. bidirectional confirmation when the evidence class requires it;
6. final trajectory-integrity checks with no silent removal or replacement.

The runtime must persist a per-frame trace before any evaluation reference is
loaded. Each gate entry records a stable gate ID and version, pass/fail result,
measured score, threshold, evidence source, candidate coordinate, competing
candidate or margin where applicable, and a reason. The trace also records the
detector weight hash, detector/runtime versions, tracker source hash,
configuration hash, input-cache hash, final evidence class, and final
verification result. For example:

```text
Broad YOLO candidate       PASS
Pitch/player context       PASS
Temporal support           PASS
Competing-path margin      FAIL (0.03 < 0.08)
Bidirectional confirmation FAIL
Final result               AMBIGUOUS — not auto-verified
```

A fresh `auto_verified` receipt remains valid without another human review only
while all recorded hashes and gate versions match. Any mismatch makes the
receipt stale. An ambiguous or unresolved frame is never converted into a
success-shaped coordinate merely to improve coverage.

Ball-coordinate development is fail-forward:

- an independently confirmed `PASS` becoming `FAIL`, `AMBIGUOUS`, missing, or
  materially moved is a blocking regression;
- `FAIL` or `AMBIGUOUS` becoming `PASS` is a potential gain and is accepted
  only after evaluation confirms it;
- a new rule must not silently remove, move, weaken, or change the evidence
  path of a previously confirmed passing coordinate;
- a previously auto-verified result later proven false must be corrected, not
  preserved for a green regression; its old receipt is invalidated and the
  intentional correction is recorded;
- insufficient or contradictory evidence fails forward to `AMBIGUOUS` or
  `UNRESOLVED`, never backward to an assumed coordinate.

Runtime traces and reviewed expectations are physically and logically
separate. Detection, tracking, gate execution, scoring, and trace publication
finish and freeze before the protected evaluation reference is loaded. The
reference may classify a failure as a missing general rule, insufficient
visual evidence, or a correct rejection, but it must never select a candidate,
set a threshold, or otherwise influence inference.

The live rules engine may consume the complete generated ball-state timeline
for continuity, but it must preserve the evidence class of every sample:

- direct detector and evidence-backed recovery states may provide proximity,
  speed, and direction evidence;
- bidirectional and forward trajectory estimates may provide continuity and
  proximity evidence only;
- estimated states must never be reclassified as detector observations;
- every emitted event records whether its interval used direct, mixed, or
  estimated ball evidence, including the estimated source-frame numbers and
  maximum uncertainty radius;
- the possession artifact records all input frames grouped by state so a
  reviewer can distinguish complete processing coverage from direct-evidence
  coverage.

Human review may validate whether an estimate is visually acceptable, but that
decision remains evaluation-only. It cannot selectively promote that frame or
change its runtime evidence class.

Coordinate-review decisions have explicit visual meanings. Agreeing says the
proposed coordinate is visually supported. Confirming a custom coordinate says
the reviewer can see the ball at that supplied location. `Ball undefined / not
visible` says the current camera cannot visually locate the ball, including
player occlusion. `YOLO candidate N is correct` says the reviewer can see the
ball at that numbered raw detection but the selector or tracker did not choose
it. `Needs more checking` records unresolved ambiguity. A custom or selected
YOLO coordinate must never be reinterpreted as an uncertain or invisible-ball
decision. It is a diagnostic lead only, never a reference coordinate, ground
truth, or expected engine target. A selected YOLO candidate directs
investigation toward general candidate-selection logic but must not be
force-selected. None of these review observations may become inference input
or be used to calculate success against the supplied coordinate.

Each submitted ball-coordinate batch is one durable review round. While
Copilot reviews evidence, implements a general correction, and runs focused
tests, the batch modal remains open and reports timestamped progress. Passing
tests automatically start one whole-segment recovery run from the saved raw
detections; no second user authorization is required for that rerun. The modal
remains open through the rerun and then changes from progress notifications to
the persisted result. The round records each reviewed frame as fixed,
unresolved, or regressed, captures before/after provenance and completion time,
preserves the user's decision in the durable review-state artifact, and becomes
read-only. A closed-round frame may show only its prior decision, rerun result,
raw-frame navigation, review-frame navigation, and zoom controls; it cannot
accept a new decision.
If direct coverage remains below the configured gate, unresolved and regressed
frames form a required new review round. Once direct coverage reaches the
configured gate, the Canvas shows the measured result and asks the user either
to continue to event inference or explicitly create another round from the
remaining unresolved and regressed frames. Only the user may submit that round
or finalize the segment after the gate is met.

Both engines may evolve, but only independently. Every Innovation acceptance,
whether recorded by the user or Copilot, checks the Innovation regression
receipt against the exact engine and cached-output hashes. A fresh matching
receipt is reused without rerunning the engine or tests. A missing receipt runs
the Innovation suite once; a changed signature is stale and requires cached
event rebuilding for every published Innovation segment, exact comparison with
each publication hash, and the protected suite. Any mismatch blocks acceptance.
The accepted review requirement remains pending while the agent reports each
affected segment and its event differences, then adjusts the general rule and
repeats the full gate. It must not silently discard the new requirement or
weaken an old reference. A successful all-segment receipt is keyed by the exact
engine content hash and published-segment set, so later review-only decisions
reuse it without rerunning every segment. A new engine hash or newly published
segment invalidates that receipt. Live acceptance and publication use the live
suite and live registry; neither regression runner discovers the other
workflow's cases.

The workflow identity is carried and checked at every review boundary:

| Workflow | Canvas ID | State `workflowId` | Artifact namespace |
| --- | --- | --- | --- |
| Innovation Day BAC diagnostic | `football-event-review` | `innovation_day_bac` | `innovation/` and `event-review-state-innovation/` |
| Raw-video iteration-25 live | `football-event-review-live` | `live_iteration_25` | `live/` and `event-review-state-live/` |

Each persisted review-state document stores both its `workflowId` and
`canvasId`. Loading or saving a document owned by the other workflow is a hard
error. Every Canvas-to-Copilot prompt repeats both identifiers and explicitly
forbids the other workflow's actions, state, and engine output. These checks,
rather than the visual theme or selected segment alone, determine which
pipeline the Canvas refers to.

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

Run the Innovation engine contracts:

```powershell
$env:PYTHONPATH="$PWD\src"
python -m pytest -q `
  tests\test_innovation_day_snapshot.py `
  tests\test_innovation_match_state_regression.py `
  tests\test_innovation_possession_regression.py `
  tests\test_innovation_review_regressions.py
```

Run the live ball-coordinate and engine contracts:

```powershell
$env:PYTHONPATH="$PWD\src"
python -m pytest -q `
  tests\test_ball_tracking.py `
  tests\test_match_state.py `
  tests\test_possession.py `
  tests\test_live_review_regressions.py
```

Refresh cached event logic only in the intended workflow:

```powershell
$env:PYTHONPATH="$PWD\src"
python scripts\process-alfheim-innovation-segment.py `
  benchmarks\alfheim\generated\segment-0180-020 `
  --events-only

python scripts\process-alfheim-segment.py `
  benchmarks\alfheim\generated\segment-0180-020 `
  --artifact-namespace live `
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

The live review Canvas may expose an opt-in Developer mode to reduce repeated
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
