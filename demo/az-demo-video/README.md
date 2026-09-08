# Football AI Platform — Demo Video

Reproducible source for a general-purpose, ~4-minute narrated pitch-deck
video for the Football AI Platform. It is deliberately club-agnostic: no
spoken, captioned, or on-screen references to any single club remain. The
finished MP4 and its raw WAV/build artifacts are intentionally **not**
committed (large, machine-generated, and gitignored) — this folder contains
everything needed to regenerate them locally.

## Deliverables (generated locally, not committed)

Two narration **pace presets** are produced from the same `scenes.json`
source text (see `scripts/synthesize_narration_edge.py`):

| File | Pace | Description |
|---|---|---|
| `Football_AI_Platform_Demo.mp4` | fast | Canonical deliverable. 1920x1080, 30fps, h264/aac, ~4:00–4:22, burned-in captions. |
| `Football_AI_Platform_Demo_4min.mp4` | fast | Same render as above, explicit pace-named copy. |
| `Football_AI_Platform_Demo_4m48s.mp4` | relaxed | Slightly more deliberately paced alternate cut, ~4:40–4:48, for side-by-side review. |
| `Football_AI_Platform_Demo.srt` | fast | Caption track for the fast cut (committed — small text file). |
| `Football_AI_Platform_Demo_relaxed.srt` | relaxed | Caption track for the relaxed cut (committed). |
| `Football_AI_Platform_Narration.txt` | — | Exact narration text per scene, both presets share this text (committed). |

## What's committed here

```
demo/az-demo-video/
  Football_AI_Platform_Narration.txt      # exact narration text (source of truth)
  Football_AI_Platform_Demo.srt           # caption track, fast pace
  Football_AI_Platform_Demo_relaxed.srt   # caption track, relaxed pace
  STORYBOARD.md                           # scene -> visual -> timing map
  assets/shots/                           # real screenshots used as calibrated or presentation B-roll
  scripts/
    scenes.json                           # narration source text per scene (id, title, text)
    synthesize_narration_edge.py          # PRIMARY: edge-tts neural voice -> WAV per scene, per pace
    synthesize_narration.ps1              # FALLBACK: WinRT (Windows.Media.SpeechSynthesis) "Mark" voice
    generate_srt.py                       # builds the .srt from scenes.json + rendered WAV durations
    build_demo_video.py                   # assembles the final MP4 (selective HD motion + real clips + audio + captions)
demo/landing/                             # standalone HTML mockups used to capture some of the shots
    index.html, copilot-concept.html, future-vision.html, query-by-probability.html
```

`demo/az-demo-video/build/` (audio WAVs per pace, per-scene intermediate
clips, the final MP4s themselves) is machine-generated scratch space and is
gitignored.

## Reproducing the video

Requires: Python 3.11+ with `imageio_ffmpeg` and `Pillow` (already declared
as optional deps in `pyproject.toml`), and **either**:

- **Primary (recommended): `pip install edge-tts`** — a natural Microsoft
  neural voice (default: `en-GB-RyanNeural`, a calm professional UK male
  consultant voice), synthesized sentence-by-sentence with calibrated pauses
  and subtle per-sentence rate/pitch variation so it reads like a person with
  real grammar and pacing, not a flat non-stop machine voice. **Requires
  internet access** to Microsoft's Edge TTS endpoint at synthesis time; the
  rendered WAV output itself stays entirely local afterwards. The narration
  content is non-confidential, so this is an acceptable trade-off — do not
  use this for confidential text.
- **Fallback: the local WinRT "Microsoft Mark" voice** (no internet
  required) via `synthesize_narration.ps1`, if edge-tts or internet access to
  Microsoft's TTS endpoint is unavailable. Windows PowerShell 5.1
  (`powershell.exe`, **not** `pwsh.exe`) is required for that path — the
  WinRT speech API's type-literal projection syntax only resolves under 5.1.

Do not use paid ElevenLabs or unauthorized cloned voices for this narration.

1. **Narrate.** From the repo root, pick a pace preset (`fast` ~4:00,
   `relaxed` ~4:48) — see `PACE_PRESETS` in the script for the exact
   pause/rate constants of each:
   ```powershell
   python demo\az-demo-video\scripts\synthesize_narration_edge.py --voice en-GB-RyanNeural --pace fast
   python demo\az-demo-video\scripts\synthesize_narration_edge.py --voice en-GB-RyanNeural --pace relaxed
   ```
   Writes one WAV per scene to `demo/az-demo-video/build/audio/<pace>/sceneNN.wav`.
   To re-synthesize a single corrected scene only, add `--only-ids 5`.

   Fallback (no internet, WinRT "Mark" voice, single pace only):
   ```powershell
   & "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass `
     -File demo\az-demo-video\scripts\synthesize_narration.ps1
   ```

2. **Captions.**
   ```powershell
   python demo\az-demo-video\scripts\generate_srt.py --pace fast
   python demo\az-demo-video\scripts\generate_srt.py --pace relaxed
   ```
   Reads the rendered WAV durations for that pace and `scenes.json` text,
   writes `Football_AI_Platform_Demo.srt` (fast) or
   `Football_AI_Platform_Demo_relaxed.srt` (relaxed).

3. **Assemble the video.**
   ```powershell
   python demo\az-demo-video\scripts\build_demo_video.py --pace fast
   python demo\az-demo-video\scripts\build_demo_video.py --pace relaxed
   ```
   Renders each of the 10 scenes (static calibrated screenshots and restrained
   motion on presentation graphics from `assets/shots/`, plus short real
   match-footage clips), concatenates video
   and audio as separate safe passes (PCM WAV audio concat + H.264 video-only
   concat, to avoid AAC bitstream corruption from concatenating
   independently-encoded AAC segments), muxes once, encodes AAC once, and
   burns in the SRT captions. Produces
   `demo/az-demo-video/Football_AI_Platform_Demo_<pace-suffix>.mp4`, and for
   the `fast` pace additionally writes the canonical
   `Football_AI_Platform_Demo.mp4` copy.

   Calibrated pitch and goal screenshots intentionally remain fixed. Other
   presentation graphics use only a 3–4% slow zoom, rendered from a
   Lanczos-scaled 4K working frame to keep the 1080p output clean.

### External, machine-local inputs (not shipped in the repo)

`build_demo_video.py` references two locally-generated benchmark clips from
the Alfheim `segment-0300-020` benchmark (see
`docs/RULES_ENGINE_ARCHITECTURE.md` and `benchmarks/alfheim/`):

- `alfheim-window-playable.mp4` — the raw playable match window.
- `analytics-data/tracking-verification.mp4` — the AI tracking overlay clip.

These are large generated artifacts, gitignored by design, and not committed.
Point the `FOOTBALL_DEMO_SEGMENT_ROOT` environment variable at a directory
containing both (e.g. a sibling worktree's `benchmarks/alfheim/generated/
segment-0300-020` output) if this worktree doesn't have them locally, or
regenerate them with the benchmark pipeline.

### Screenshots in `assets/shots/`

Captured with headless Microsoft Edge (`msedge.exe --headless`) against the
live local app server and the current Football Event Review canvas (an
extension iframe) — the all-in-one segment/detect/independently-review/
validate/regression-protect/publish workflow — plus the standalone mockups
in `demo/landing/`. Notable ones used in the final cut:

- `review-canvas-base.png` — the current Football Event Review Canvas
  (segment builder / preparation area). Used for the Scene 1 reveal and the
  Scene 3 segment-builder shot, **replacing** the old, obsolete manual-click
  "Validation Lab" screen (`validation-lab.png`, no longer referenced).
- `review-canvas-timeline-accept.png` — the clean maximized ("Enlarge Review")
  Copilot-proposal vs rules-engine comparison timeline used in the videos.
- `review-canvas-timeline-calibrated.png` — the same review state with the
  saved pitch and goal calibration projected for static website explanations.
- `review-canvas-zoomed-action.png` — the clean focused action view used in
  the videos.
- `tests-105-passed.png` — the 105 protected regression tests passing before
  publication.
- `match-replay-playing-crop.png` — the "Match Replay Preview" panel captured
  mid-playback (real video advancing, real non-zero per-team stats), on a
  separate consecutive-minute window (27:45 onward) from the reviewed segment.
- `stats-dashboard.png`, `landing.png` — the statistics/maturity roadmap view
  (club-agnostic; no "AZ Alkmaar" text).
- `future-vision.png` — roadmap/continuous-processing concept plus a
  stylized (non-trademarked) Xebia Netherlands wordmark badge.
- `query-by-probability.png` — dedicated architecture graphic for the
  **Query By Probability** future concept (main camera + confidence-drop
  trigger + targeted goal-end/touchline query cameras + evidence fusion).

`validation-lab.png`, `review-studio.png`, `demo-pipeline.png`,
`review-canvas-enlarged.png`, and `review-canvas-event10.png` remain in the
folder but are **not referenced** by the current build script.

## Accuracy notes

See the "Notes" section at the end of
`Football_AI_Platform_Narration.txt` for the specific factual claims this
video makes and the evidence behind them. For the 15:00–16:00 reviewed
segment: C10 (a proposed black completed pass) was rejected as a false
proposal, and the separate unmatched E10 (a red/white turnover) was
independently confirmed — this is the authoritative durable review state.
The spoken narration and captions avoid naming "C10"/"E10" directly and
require no rebuild on this account.

**Query By Probability** (Scene 9) and the **continuous, daily-refresh
processing** concept (Scene 8) are both narrated and captioned explicitly as
future architecture, not current behaviour, and are not framed as a
patentability claim anywhere in the video, README, or storyboard. See the
durable guardrails in `.github/copilot-instructions.md` ("Query By
Probability" section) and `docs/RULES_ENGINE_ARCHITECTURE.md` (section 11)
for the authoritative constraints on both concepts.

**Xebia Netherlands** (Scene 10) is mentioned as optional scalable AI and
engineering capacity for a next phase, with no prices or contract terms. The
on-screen wordmark is a stylized "X" monogram created for this video, not a
reproduction of Xebia's official trademarked logo artwork.
