# AZ Alkmaar Football AI Platform — Demo Video

Reproducible source for the ~4-minute narrated demo video prepared for AZ
Alkmaar. The finished MP4 and its raw WAV/build artifacts are intentionally
**not** committed (large, machine-generated, and gitignored) — this folder
contains everything needed to regenerate them locally.

## Deliverables (generated locally, not committed)

| File | Description |
|---|---|
| `AZ_Football_AI_Platform_Demo.mp4` | Final video: 1920x1080, 30fps, h264/aac, ~4:00, burned-in captions. |
| `AZ_Football_AI_Platform_Demo.srt` | Caption track (committed — small text file). |
| `AZ_Football_AI_Platform_Narration.txt` | Exact narration text per scene (committed). |

## What's committed here

```
demo/az-demo-video/
  AZ_Football_AI_Platform_Narration.txt   # exact narration text (source of truth)
  AZ_Football_AI_Platform_Demo.srt        # caption track matching the narration timing
  STORYBOARD.md                           # scene -> visual -> timing map
  assets/shots/                           # real screenshots used as B-roll / Ken Burns stills
  scripts/
    scenes.json                           # TTS source text per scene (id, title, text)
    synthesize_narration.ps1              # WinRT (Windows.Media.SpeechSynthesis) TTS -> WAV per scene
    generate_srt.py                       # builds the .srt from scenes.json + rendered WAV durations
    build_demo_video.py                   # assembles the final MP4 (Ken Burns stills + real clips + audio + captions)
demo/landing/                             # standalone HTML mockups used to capture some of the shots
    index.html, copilot-concept.html, future-vision.html
```

`demo/az-demo-video/build/` (audio WAVs, per-scene intermediate clips, the
final MP4 itself) is machine-generated scratch space and is gitignored.

## Reproducing the video

Requires: Python 3.11+ with `imageio_ffmpeg` and `Pillow` (already declared as
optional deps in `pyproject.toml`), Windows with the "Microsoft Mark" SAPI/
WinRT voice available, and Windows PowerShell 5.1 (`powershell.exe`, **not**
`pwsh.exe` — the WinRT speech API's type-literal projection syntax only
resolves under 5.1).

1. **Narrate.** From the repo root:
   ```powershell
   & "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass `
     -File demo\az-demo-video\scripts\synthesize_narration.ps1
   ```
   Writes one WAV per scene to `demo/az-demo-video/build/audio/sceneNN.wav`.
   To re-synthesize a single corrected scene only, add `-OnlyIds 5`.

2. **Captions.**
   ```powershell
   python demo\az-demo-video\scripts\generate_srt.py
   ```
   Reads the rendered WAV durations and `scenes.json` text, writes
   `AZ_Football_AI_Platform_Demo.srt`.

3. **Assemble the video.**
   ```powershell
   python demo\az-demo-video\scripts\build_demo_video.py
   ```
   Renders each scene (Ken Burns pans over the real screenshots in
   `assets/shots/`, plus short real match-footage clips), concatenates video
   and audio as separate safe passes (PCM WAV audio concat + H.264 video-only
   concat, to avoid AAC bitstream corruption from concatenating
   independently-encoded AAC segments), muxes once, encodes AAC once, and
   burns in the SRT captions. Produces
   `demo/az-demo-video/AZ_Football_AI_Platform_Demo.mp4`.

### External, machine-local inputs (not shipped in the repo)

`build_demo_video.py` references two locally-generated benchmark clips from
the Alfheim `segment-0300-020` benchmark (see
`docs/RULES_ENGINE_ARCHITECTURE.md` and `benchmarks/alfheim/`):

- `alfheim-window-playable.mp4` — the raw playable match window.
- `analytics-data/tracking-verification.mp4` — the AI tracking overlay clip.

These are large generated artifacts, gitignored by design, and not committed.
Point the `RAW_MATCH_MP4` / `TRACKING_MP4` constants at the top of
`build_demo_video.py` at your own local copies (regenerate them with the
benchmark pipeline, or use the same worktree's `benchmarks/alfheim/generated/`
output) before running.

### Screenshots in `assets/shots/`

Captured with headless Microsoft Edge (`msedge.exe --headless`) against the
live local app server and the Football Event Review canvas (an extension
iframe), plus the standalone mockups in `demo/landing/`. Notable ones used in
the final cut:

- `validation-lab.png` — the Alfheim Match Lab / Validation Lab screen.
- `review-canvas-timeline-accept.png` — the maximized ("Enlarge Review")
  Copilot-proposal vs rules-engine comparison timeline for the reviewed
  15:00–16:00 segment, showing real Accept/Reject decision badges and the
  "Engine already agrees" panel.
- `tests-105-passed.png` — the 105 protected regression tests passing before
  publication.
- `match-replay-playing-crop.png` — the "Match Replay Preview" panel captured
  mid-playback (real video advancing, real non-zero per-team stats), on a
  separate consecutive-minute window (27:45 onward) from the reviewed segment.
- `stats-dashboard.png`, `landing.png` — the statistics/maturity roadmap view.

## Accuracy notes

See the "Notes" section at the end of
`AZ_Football_AI_Platform_Narration.txt` for the specific factual claims this
video makes and the evidence behind them. For the 15:00–16:00 reviewed
segment: C10 (a proposed black completed pass) was rejected as a false
proposal, and the separate unmatched E10 (a red/white turnover) was
independently confirmed — this is the authoritative durable review state.
The spoken narration and captions avoid naming "C10"/"E10" directly and
require no rebuild on this account.
