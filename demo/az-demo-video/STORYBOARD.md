# Storyboard — AZ Football AI Platform Demo

Total runtime: **240.8s (4:00.8)**, 1920x1080 @ 30fps, h264/aac, burned-in
captions (`AZ_Football_AI_Platform_Demo.srt`), narration by Microsoft Mark
(WinRT SAPI voice).

Timings below are approximate global start times in the final render (title
card + 8 narrated scenes + closing card). Regenerating with different
narration text will shift these slightly — see `scripts/generate_srt.py`,
which derives exact caption timing from the rendered WAV durations at build
time.

| # | Segment | Approx. start | Duration | Visual(s) | Source |
|---|---|---|---|---|---|
| — | Title card | 0:00 | 4.0s | "AZ ALKMAAR · Football Intelligence Platform" title card | Generated (PIL) |
| 1 | Opening | 0:04 | 19.3s | Real Alfheim match footage (opening wide shot) | `alfheim-window-playable.mp4` |
| 2 | Segmentation principle | 0:23 | 20.4s | Landing page hero (Ken Burns) | `assets/shots/landing.png` |
| 3 | Segment builder | 0:44 | 28.5s | Validation Lab / Alfheim Match Lab screen (Ken Burns) → real ~4s match clip (segment window @ 20s in) | `assets/shots/validation-lab.png` + `alfheim-window-playable.mp4` |
| 4 | AI event detection | 1:12 | 29.8s | AI tracking overlay clip (~18s) → zoomed review-canvas action shot | `tracking-verification.mp4` + `assets/shots/review-canvas-zoomed-action.png` |
| 5 | Global Football Rules Reviewer & passed gate | 1:42 | 43.1s | Maximized accept/validate C#↔E# comparison timeline (60%) → 105-tests-passed screen (40%) | `assets/shots/review-canvas-timeline-accept.png` + `assets/shots/tests-105-passed.png` |
| 6 | Statistics & maturity dashboard | 2:25 | 27.6s | Stats dashboard (42%) → real mid-playback Match Replay Preview w/ live stats (30%) → maturity roadmap grid (28%) | `assets/shots/stats-dashboard.png` + `assets/shots/match-replay-playing-crop.png` + `assets/shots/landing.png` |
| 7 | Copilot over validated data | 2:52 | 19.2s | Copilot concept mockup (Ken Burns) | `assets/shots/copilot-concept.png` |
| 8 | Future vision & Xebia | 3:12 | 43.0s | Future-vision roadmap mockup, three pans (top/mid/bottom thirds) | `assets/shots/future-vision.png` |
| — | Closing card | 3:55 | 6.0s | "Xebia Netherlands · Scalable AI & engineering capacity" closing card | Generated (PIL) |

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
  multi-camera "second opinion" concept, private/on-premises deployment) is
  narrated as a future/prototype concept, not a shipped feature.

## Regenerating this storyboard's timings

Timings will shift if narration text changes. After re-running
`synthesize_narration.ps1` and `generate_srt.py`, re-run
`build_demo_video.py` — its console output prints each scene's actual
rendered duration, which can be used to update the table above.
