# Storyboard — Football AI Platform Demo

Two narration pace presets are produced from the same `scenes.json` source
text (see `scripts/synthesize_narration_edge.py`). Timings below are for the
**fast** pace (canonical deliverable, `Football_AI_Platform_Demo.mp4`),
total runtime **~261.5s (4:21.5)**, 1920x1080 @ 30fps, h264/aac, burned-in
captions (`Football_AI_Platform_Demo.srt`), narration by Microsoft Edge
neural TTS (`en-GB-RyanNeural`). The **relaxed** pace
(`Football_AI_Platform_Demo_4m48s.mp4`) uses the same visuals and scene
order but ~298s (4:58) total, from slightly longer calibrated pauses and a
slower per-sentence rate — see `PACE_PRESETS` in the script.

Timings below are approximate global start times in the final render (title
card + 10 narrated scenes + closing card). Regenerating with different
narration text or a different pace preset will shift these — see
`scripts/generate_srt.py`, which derives exact caption timing from the
rendered WAV durations at build time.

| # | Segment | Approx. start (fast pace) | Duration (fast pace) | Visual(s) | Source |
|---|---|---|---|---|---|
| — | Title card | 0:00 | 4.0s | "Football Intelligence Platform" title card | Generated (PIL) |
| 1 | Opening | 0:04 | 18.6s | Real Alfheim match footage (opening wide shot) → reveal of the current Football Event Review Canvas | `alfheim-window-playable.mp4` + `assets/shots/review-canvas-base.png` |
| 2 | Segmentation and ongoing evaluation | 0:23 | 23.8s | Landing page hero (Ken Burns) | `assets/shots/landing.png` |
| 3 | Segment builder | 0:46 | 23.1s | Current Football Event Review Canvas segment builder (Ken Burns) → real ~4s match clip (segment window @ 20s in) | `assets/shots/review-canvas-base.png` + `alfheim-window-playable.mp4` |
| 4 | AI event detection | 1:09 | 25.3s | AI tracking overlay clip → zoomed review-canvas action shot | `tracking-verification.mp4` + `assets/shots/review-canvas-zoomed-action.png` |
| 5 | Rules Reviewer and passed gate | 1:35 | 40.8s | Maximized accept/validate C#↔E# comparison timeline (60%) → 105-tests-passed screen (40%) | `assets/shots/review-canvas-timeline-accept.png` + `assets/shots/tests-105-passed.png` |
| 6 | Statistics and maturity | 2:15 | 24.3s | Stats dashboard (42%) → real mid-playback Match Replay Preview w/ live stats (30%) → maturity roadmap grid (28%) | `assets/shots/stats-dashboard.png` + `assets/shots/match-replay-playing-crop.png` + `assets/shots/landing.png` |
| 7 | Copilot over validated data | 2:39 | 16.3s | Copilot concept mockup (Ken Burns) | `assets/shots/copilot-concept.png` |
| 8 | Future vision and continuous processing | 2:56 | 30.7s | Future-vision roadmap/continuous-processing mockup, two pans (top/middle) | `assets/shots/future-vision.png` |
| 9 | Query By Probability | 3:26 | 32.1s | Dedicated Query By Probability architecture graphic | `assets/shots/query-by-probability.png` |
| 10 | Partnership | 3:58 | 16.7s | Future-vision mockup, bottom crop (Xebia Netherlands wordmark card) | `assets/shots/future-vision.png` |
| — | Closing card | 4:15 | 6.0s | "Football Intelligence Platform · Xebia Netherlands" closing card | Generated (PIL) |

## Notable real-footage / real-data moments (not mockups)

- **Scene 1** and the **end of Scene 3**: actual Alfheim match video
  (`alfheim-window-playable.mp4`), not a screenshot or illustration.
- **Start of Scene 4**: the AI tracking-overlay verification clip
  (`tracking-verification.mp4`) — real detections drawn over real footage.
- **Scene 5**: a real, maximized capture of the Football Event Review canvas
  showing the actual Copilot-proposal vs rules-engine comparison timeline for
  the reviewed 15:00–16:00 segment (`segment-0300-020`), with real
  Accept/Reject decision badges and the "Engine already agrees" panel — this
  is the strongest concrete proof moment in the video, matching the
  just-passed guarded publication gate (15 proposals reviewed, 14 accepted
  analytics events matching E1–E14, one excluded proposal, foul/match-state
  annotation excluded, 105 protected tests passed).
- **Middle of Scene 6**: the "Match Replay Preview" panel captured
  mid-playback (video `currentTime` genuinely advancing, `paused=false`) with
  real, non-zero per-team pass/turnover counters sourced from event files
  already written to disk — verified live via Playwright before capture, not
  a static/empty placeholder. Runs on a separate consecutive-minute window
  (27:45 onward) from the reviewed segment shown in Scene 5.

## Explicitly labeled as roadmap / illustrative

- Scene 6's maturity grid clearly separates "implemented, under validation"
  (possession, passes, pass completion %, fouls, interceptions) from
  "in review" (shots, shots on target), "near completion" (corners), and
  "in development" (offsides, attacks/dangerous attacks, defensive actions,
  player/team/formation stats) — see the landing page maturity board this
  grid is captured from.
- Scene 8's future-vision mockup (heat maps, pitch-zone identification,
  and the continuous/state-machine-driven processing concept with a
  daily rules-engine refresh cadence) is narrated as a future/prototype
  concept, not a shipped feature.
- Scene 9's dedicated **Query By Probability** graphic (one continuous
  primary camera; a confidence-drop trigger for particular frames or a short
  window; targeted, conditional queries to specific goal-end/touchline
  cameras only, never every secondary stream for the whole match; evidence
  fusion strengthening the decision) is narrated and captioned explicitly as
  a future architectural concept we are exploring, not current behaviour —
  see `.github/copilot-instructions.md` and
  `docs/RULES_ENGINE_ARCHITECTURE.md` section 11 for the durable guardrails.
- Scene 10's Xebia Netherlands mention is framed as optional scalable AI and
  engineering capacity for a next phase, with no prices or contract terms.

## Regenerating this storyboard's timings

Timings will shift if narration text or the pace preset changes. After
re-running `synthesize_narration_edge.py --pace <pace>` and
`generate_srt.py --pace <pace>`, re-run `build_demo_video.py --pace <pace>`
— its console output prints each scene's actual rendered duration, which can
be used to update the table above.

