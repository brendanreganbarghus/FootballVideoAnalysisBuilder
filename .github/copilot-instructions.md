# Football event review instructions

Read `AGENTS.md` and `docs/PROJECT_DOCUMENTATION.md` before football inference,
review workflow, dataset, benchmark, or publication work. This file supplies
Copilot-specific persistent instructions; the rules architecture and code/tests
remain authoritative.

Live ball tracking and `football-event-review-live` are currently frozen and
fully separate from Innovation Day. Do not inspect, run, edit, or reuse Live
tracker code, Live state, or `live/` artifacts unless Brendan explicitly
resumes that work. Innovation uses only frozen BAC coordinates, the frozen
Innovation engine, `innovation/` artifacts, `event-review-state-innovation`,
and Canvas type `football-event-review`. It is a BAC-assisted diagnostic/demo
of the downstream football engine, not raw-video ball inference or a valid
ball-tracking performance benchmark.

For football-event analysis and rules-engine work, act as a senior football-law
and analytics adjudicator. Identify relevant events, challenge unsupported
proposals, and explain missing evidence. Do not assume that a proposal is
correct merely because it was produced by the engine, Copilot, or a user.

Use this authority order:

1. Apply the current official IFAB Laws of the Game through the reviewed law
   profile documented in `docs/RULES_ENGINE_ARCHITECTURE.md` and implemented by
   `MATCH_LAW_PROFILE` in `src/football_poc/match_state.py`.
2. Apply the project's explicit analytics definitions for completed passes,
   turnovers, possession, shots, and shots on target. These statistics are
   project contracts, not IFAB Laws.
3. Decide whether the available video, tracking, and match-state evidence
   satisfies those rules. Never fabricate a referee decision, player identity,
   touch, or control state when the evidence is insufficient.

## Hard rule: raw-video-only event inference and performance testing

For SoccerTrack and every other labelled dataset, passes, drives, shots, free
kicks, possession changes, turnovers, and all other football events must be
detected from the raw video evidence by the platform's detector, tracker,
match-state engine, and analytics state machines.

- Never read dataset event annotations, ground-truth event files, manual review
  labels, or published provider events during detection, tracking, team
  classification, possession inference, match-state inference, event
  generation, confidence scoring, threshold selection, or rule execution.
- Never copy, translate, seed, align, recover, or manufacture an engine event
  from a dataset label. Do not use labelled timestamps to narrow the inference
  search or resolve an uncertain result.
- Keep runtime inputs physically and logically separate from evaluation
  references. A runtime segment manifest may identify only the raw media,
  frame/time range, camera calibration, and non-label processing
  configuration. Event annotations belong in a separate evaluation artifact.
- Load evaluation references only after predictions are complete and frozen.
  They may calculate evaluation metrics and support independent review, but
  they must never affect predictions or a rerun of those predictions.
- Measure and report raw-video processing speed using a cold path from the raw
  video through detection, tracking, inference, and event publication. Do not
  include annotation-derived artifacts or substitute a precomputed
  detection/track cache and describe the result as raw-video processing speed.
  Cache-rebuild timing may be measured separately and must be labelled as such.
- Treat each configured 30- or 60-second segment as a production-like streaming
  deadline. Fresh raw-video processing is the default; cache reuse must be an
  explicit opt-in diagnostic or interrupted-run recovery mode. Report wall
  time, processed video duration, real-time factor, achieved frames per second,
  and the acceleration factor required to publish before the next segment is
  due.
- Treat any violation as data leakage and an invalid benchmark. Stop, disclose
  the violation, discard the affected predictions and timing result, correct
  the pipeline separation, and rerun from raw video.

## Ball-coordinate batch review outcomes

Treat each saved user outcome as an evaluation claim that defines what the
reviewer says they can see:

- `agree`: the user says the current proposed coordinate is visually supported;
- `specified`: the user says the ball is visible at their supplied coordinate;
- `yolo_candidate`: the user says the numbered raw YOLO candidate is visibly
  correct, but the selector or tracker did not choose it;
- `undefined`: the user says the current camera cannot visually locate the ball,
  including player occlusion;
- `needs_more_checking`: the user says the frame remains visually ambiguous.

Use these outcomes only as reviewer observations and diagnostic leads:
independently inspect the targeted raw-video frame/window and group general
detector or tracker failure patterns. A supplied coordinate is never a
reference coordinate, ground truth, expected engine target, or permission to
make the engine match it. A `yolo_candidate` outcome is a diagnostic reason to
investigate general candidate-selection logic, not permission to force-select
that detection. Do not reinterpret a supplied coordinate as uncertainty, and
do not treat a frame as generically rejected. Challenge an unsupported user
outcome explicitly rather than silently changing its meaning. Never copy these
outcomes or coordinates into a prediction, use them to select a candidate or
threshold, narrow inference, calculate success against the supplied coordinate,
or create a frame-, timestamp-, segment-, or track-specific rule.

During a Canvas review, independently adjudicate the selected event against the
global rules architecture and its event-specific evidence. Keep inspection
limited to the selected segment and use a small frame window when possible.
A `copilot_review` or `adjusted_proposal` source means Copilot reviewed the
proposal; it does not mean the proposal is accepted or implemented.

Use a fast cached-first path for targeted M#/E# reviews:

- Start with the prepared Canvas video, current cached possession/match-state
  evidence, and current E# output. Never rerun detection or ball tracking.
- A decisive M# modal outcome (`engine missed M#` or `existing E# represents
  M# but is wrong`) is final professional acceptance. Do not independently
  re-adjudicate, reject, edit, reinterpret, or remap that M#. Inspect evidence
  only to diagnose the general pipeline cause, then fix it, rebuild E#, and run
  the required regressions in the same single Autopilot request. Do not start a
  separate Plan, adjudication, or follow-up Copilot request. Only `Cannot
  verify` requests adjudication.
- If that accepted requirement exposes a general player-tracking defect, fix
  it and rebuild player tracks only from the existing cached detector output;
  do not rerun the detector or ball tracker.
- The E# and unmatched-M# modals must both show a pulsating
  `Copilot is working…` status only while their selected review activity is
  actually `working`. Retained conversation identity is not active work. A
  completed final response must close the modal automatically and refresh
  M#/E# while preserving the conversation.
- Do not generate new OpenCV/FFmpeg crops, contact sheets, or broad evidence
  dumps when the prepared video and cached evidence already cover the selected
  window. Inspect one minimal visual window and only the directly relevant
  cached rows.
- First check whether a same-team, same-type E# already represents the play
  within the one-second review tolerance. If it does, report that the engine
  already agrees and stop; matching ambiguity is not an inference miss. Treat
  M#/E# numbers only as display ordinals: never match number-to-number. Match
  by canonical event type, team, completion time/frame evidence, and the
  one-to-one uniqueness rule; inserting an event renumbers later E# rows.
- Expand the investigation only when the targeted video conflicts with the
  cache or no supported E# exists. Run cached event rebuilding and regressions
  only after a general engine change is actually required.

For a full-clip independent C# review, do not infer completeness from E# output
or prior conversation memory. Review only the current prepared segment through
either continuous playback or a complete, timestamped local frame sequence
whose coverage is independently validated, and build a chronological possession
ledger before writing any C#. A coverage manifest proves sequence integrity
only; it is not football evidence. Resolve every
supported controlled-player change as a same-team pass, opponent turnover, or
explicit abstention. Then make a second continuity pass: recheck every outgoing
passer not linked to the prior controlled player and every event-free gap longer
than three seconds while play is visibly live. Require current-segment evidence
for stoppages and restarts; never reuse another segment's event pattern. Submit
C# only through the current versioned review protocol and its coverage checks.
Each C# must include a concrete release time/frame, completion time/frame,
sender or prior-owner evidence, receiver controlled-touch evidence, and
current-segment match-state evidence. Freeze that independent C# list before
suggesting C↔E links by team, canonical event type, and completion time.
Protocol version 5 must use two separate passes. First persist a chronological
visual touch-candidate ledger containing supported, rejected, and unresolved
contacts before deciding final events. Then derive the possession ledger and
C# proposals from those frozen candidates. Each event transition must reference
its supported release or possession-loss candidate and controlled-touch
candidate. Persist contiguous coverage windows of no more than three seconds
for the full clip, with every touch candidate and C# completion represented
exactly once. Any possession-ledger interval longer than three seconds requires
full-resolution checkpoints no more than 1.5 seconds apart and the IDs of the
touch candidates considered. Boolean completion claims without these concrete
records are invalid. Full-resolution continuous playback is the required
primary visual channel; individual full-resolution frames may supplement it,
but tiled contact sheets cannot prove uninterrupted travel or the absence of an
intermediate controlled touch.

For C# adjudication, the turnover event belongs to the team that **loses**
controlled possession, not the opponent that gains it. BAC position,
nearest-player distance, tracker identity, and cached team classification are
diagnostic context only: none independently proves a controlled touch, player
change, or team. Prefer visible kit identity and physical-player continuity;
never create an event from a team-label flicker, track handoff, brief challenge,
deflection, or alternating proximity without a supported deliberate touch and
subsequent control. A complete local sequence may combine each full-pitch frame
with a synchronized frozen-BAC ball-centred zoom to inspect release, travel,
nearby players, and reception; BAC remains diagnostic context and cannot create
an event. Do not substitute sampled contact sheets, omitted frames, or
cache-derived event evidence for either approved visual channel. During later
comparison, preserve chronological one-to-one order and consider the C#
release-to-completion interval rather than requiring exact timestamp equality
or matching display ordinals.

Keep manual references, Copilot diagnostics, and rules-engine events
independent:

1. The prepared segment may cache tracking, possession, match state, and
   rules-engine `E#` events.
2. In Innovation review, the professional reviewer records the ordered `M#`
   golden set independently from the video. `E#` may be compared only after M#
   exists and must never create or rewrite M#.
3. Automatic `M#`/`E#` links are suggestions. The reviewer may explicitly map,
   replace, or remove a one-to-one link without changing either timestamp.
4. Keep `C#` optional and diagnostic-only. If requested, create it
   independently from video evidence; it cannot control M#, mappings, approval,
   publication, or inference.
5. A green `M↔E` link is agreement, not proof that either side is correct.

Treat unmatched and rejected rows explicitly:

- Rejecting a `C#` proposal records only that the Copilot proposal is not a
  valid reference. It must not automatically confirm a nearby `E#` event.
- Verify an unmatched `E#` independently through **Verify E# (Autopilot)** or
  an explicitly authorized Autopilot conversation in the general Canvas chat.
- Do not mark `E#` as reviewed merely because the engine produced it. Inspect
  the targeted video and cached evidence first.
- When the exact team, canonical event type, and completion time are supported,
  record **Confirmed reviewed** with the evidence reason, review time, current
  engine source hash, and current cached-output hash.
- Treat an engine-event confirmation as stale when either recorded hash no
  longer matches. A confirmed `E#` validates that specific output under the
  reviewed engine version; protected regressions provide broader rule safety.

Use the general Canvas conversation according to its selected evidence scope:

- **Entire clip** is the default and permits review of only the prepared
  30–60-second segment, regardless of the current playhead position.
- **Current time ±2s** limits evidence inspection to the local playhead window.
- Plan mode may explain and recommend only. Autopilot mode may record a
  supported review result, but creating a missing `C#` still requires the
  separate **Add as Review Event** confirmation.

Acceptance must follow the guarded review workflow in
`docs/RULES_ENGINE_ARCHITECTURE.md`:

- require explicit user authorization for the selected proposal;
- fingerprint both the current rules-engine source and current cached engine
  output at acceptance;
- claim that the engine already agrees without a rerun only when both hashes
  match the stored snapshot used for the comparison;
- treat either hash mismatch as stale, then rerun only cached event building
  and the focused and protected regressions;
- make no engine change when the fresh, exact engine version already agrees;
- otherwise implement a general evidence-based rule, never a timestamp,
  frame, segment, track-ID, or manual-label exception;
- rerun cached event building and the focused and protected regressions;
- rebuild every published segment in the selected workflow from its own cached
  detector/tracker inputs and require an exact match with each output hash
  recorded at publication;
- if any published segment or protected test fails, do not record engine
  synchronization or publish;
  keep the accepted review requirement pending, report every affected segment
  and its added, missing, retimed, or reclassified E# events, revise the general
  rule without weakening the new requirement, and repeat the complete gate;
- record synchronization only after the accepted behavior appears in engine
  output and all required tests pass.

Publish a completed segment only through the Canvas final publication gate:

- require every `C#` proposal to have an accepted or rejected decision;
- exclude rejected proposals and match-state annotations from the analytics
  reference;
- include an unmatched `E#` only after its independent confirmation receipt
  matches the current engine source and cached-output hashes;
- rerun and record the protected regressions against those same hashes;
- write the manual reference only when its dynamic event count and one-to-one
  event matches exactly equal current engine output;
- mark the segment **Passed** and lock it only after the local validation API
  confirms the published reference.

The fingerprint proves version identity, not football correctness. Correctness
comes from independent `C#`/`E#` construction, targeted evidence review, and
regression protection.

Keep manual review labels evaluation-only. They must never become inference
inputs, thresholds, or hidden special cases.

## Query By Probability (future architecture — not implemented)

**Query By Probability** is Brendan's forward-looking architectural concept
for multi-camera coverage. It is documented here as a durable design note, not
as shipped or partially-shipped behavior:

- One strong primary camera (the "Main Camera") continuously covers the main
  stream for the whole segment or match. It is the default and only source of
  evidence in normal operation.
- The system only reaches for other cameras when the Main Camera's own
  ball/player detection confidence drops below a decision threshold for
  particular frames or a short window. At that point it queries the *relevant*
  secondary/query cameras only — e.g. a goal-end camera or a touchline camera
  whose field of view actually covers the ambiguous moment — never every
  secondary stream, and never for the full match.
- The targeted evidence from those query cameras is fused with the Main
  Camera's evidence to strengthen the probability/decision for that specific
  low-confidence moment, then the system reverts to relying on the Main Camera
  stream.
- This is explicitly a future concept for larger-stadium, multi-camera
  deployments. It must never be described or implied as current pipeline
  behavior, and it is not a patentability claim — do not mention patents when
  discussing it.

### Continuous, incremental review cadence (future architecture — not implemented)

A related future-facing idea, also not implemented today: the same
30–60-second controlled-segment discipline is designed to eventually run
continuously and configurably (e.g. rolling 30-second or 60-second chunks)
through the existing law-grounded match-state engine and its analytics event
state machines (`src/football_poc/match_state.py`), appending newly validated
statistics to the screen as more of a match is processed, rather than
requiring a human to hand-pick each window. In the same future vision, the
rules engine itself would be refreshed on a regular (e.g. daily) cadence as
more segments are independently reviewed — but every refresh must still follow
the guarded review workflow above: general, evidence-based rule changes only,
never a timestamp/segment/label-specific exception, and always re-verified
against the full protected regression suite before publication. Manual review
labels remain evaluation-only under this future cadence exactly as they are
today — they never become inference inputs, and a "daily" cadence is a
scheduling idea, not a license to skip regression protection.

When the Live freeze or another current workstream boundary changes, update
this file, `AGENTS.md`, and `CLAUDE.md` together.
