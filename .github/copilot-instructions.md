# Football event review instructions

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

During a Canvas review, independently adjudicate the selected event against the
global rules architecture and its event-specific evidence. Keep inspection
limited to the selected segment and use a small frame window when possible.
A `copilot_review` or `adjusted_proposal` source means Copilot reviewed the
proposal; it does not mean the proposal is accepted or implemented.

Keep Copilot proposals and rules-engine events independent:

1. The prepared segment may cache tracking, possession, match state, and
   rules-engine `E#` events.
2. Create each Copilot `C#` proposal independently from the video evidence.
   Never treat an `E#` event as the answer or use it to shape the proposal.
3. Only after the proposal is complete, match `C#` and `E#` by canonical event
   type, team, and timestamp tolerance.
4. Verify every proposal against its targeted video evidence before accepting
   it. A green `C↔E` match is agreement, not proof that either side is correct.

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
