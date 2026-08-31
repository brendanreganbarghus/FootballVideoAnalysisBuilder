# Alfheim research benchmark

The Simula Alfheim dataset is used only for non-commercial POC research. Its
terms prohibit commercial use, player re-identification, and player or club
performance profiling. Do not redistribute generated clips.

The Camera Setting 2 download contains native 4450x2000, 25 FPS H.264 segments
and one ball coordinate per frame. Build the selected one-minute window without
resizing or re-encoding:

```powershell
python .\scripts\prepare-alfheim-window.py
```

The default selection is segments 555-574. It contains 1,500 labelled frames
with substantial ball movement. Outputs are written to:

- `benchmarks\alfheim\window-555\alfheim-window.mp4`
- `benchmarks\alfheim\window-555\alfheim-window-playable.mp4`
- `benchmarks\alfheim\window-555\ball-ground-truth.csv`
- `benchmarks\alfheim\window-555\manifest.json`
- `benchmarks\alfheim\window-555\segments.txt`

Run a short POC smoke test:

```powershell
python -m football_poc.cli `
  .\benchmarks\alfheim\window-555\alfheim-window.mp4 `
  --output .\output\alfheim-window-555 `
  --model .\models\football-player-ball.pt `
  --image-size 1280 `
  --stride 2 `
  --max-frames 100
```

Detection results must be scored against `ball-ground-truth.csv`; visual
inspection alone is not sufficient. This night panorama remains a difficult
wide-view benchmark and is not representative of the planned two half-pitch
camera installation.

The native MP4 retains the source's 4450x2000 H.264 High 4:2:2 stream for
analysis. Many browsers and Windows players cannot decode that format. The
`playable` copy is 3840-wide H.264 4:2:0 for browser review.

Open the labelled benchmark viewer:

```powershell
python .\scripts\serve-local.py --port 8080 --bind 127.0.0.1
```

This range-aware server is required for reliable video seeking and the manual
review page's `-2 seconds` and `+2 seconds` controls.

Then visit:
`http://localhost:8080/benchmarks/alfheim/window-555/`

Run tiled inference and score detected ball centres against the labels:

```powershell
python -m football_poc.benchmark_cli `
  .\benchmarks\alfheim\window-555\manifest.json `
  --output .\benchmarks\alfheim\window-555\detections `
  --model .\models\football-players-ball-yolov8.pt `
  --image-size 1280 `
  --tile-width 1280 `
  --stride 2

python .\scripts\evaluate-alfheim-ball.py `
  .\benchmarks\alfheim\window-555\detections\detections.jsonl `
  .\benchmarks\alfheim\window-555\ball-ground-truth.csv
```

Separate recognition quality from panorama search quality by testing crops
centred on the known ball coordinates:

```powershell
python .\scripts\probe-alfheim-ball.py
```

If this oracle-crop test succeeds while tiled detection fails, improve
tiling/search. If both fail, retrain the ball model for this camera domain.

## Unified Match Lab

The primary test screen is:

```text
http://localhost:8080/benchmarks/alfheim/window-555/manual-review/
```

The Match Lab combines clean and AI-tracked video, optional supplied ball
labels, named pitch edges, goal-frame calibration, live AI counters, assisted
manual review, and timestamp tables. The older labelled-ball and analytics
pages remain available for diagnostics but are not required for normal review.

The local source contains 767 three-second segments (38:21). Enter any start
time and duration up to five minutes in Match Lab to prepare only that
browser-compatible slice. Prepared slices are cached under
`benchmarks\alfheim\generated`; selecting footage does not run model inference.
New slices intentionally show AI as unprocessed until their analytics pipeline
has been run.

Press `1` or `2` for a red/white or black completed pass, and `3` or `4` for a
turnover by the team losing possession. Use `5`/`6` for shots and `7`/`8` for
shots on target.
Entries are timestamped, stored locally in the browser, and can be exported as
JSON for comparison with `predicted-events.json`. Separate manual and calibrated
AI counters replay live to the same video playhead. Manual clicks never change
AI confidence, thresholds, inferred events, or the saved baseline.
Separate timestamp tables show the manual receiver-touch clicks and AI release
and completion times. A same-team first touch after a throw-in, goal kick, or
other restart follows the same completed-pass rule.

Generate provisional pitch-boundary crossing intervals:

```powershell
python .\scripts\analyze-alfheim-boundary.py
```

Match Lab draws the four named field edges separately: near/far touchlines and
left/right goal lines. These traces remain provisional. Each goal mouth is a
four-corner camera-specific polygon; calibrate it by pausing a clear frame,
choosing the goal feature, clicking the visible goal-frame corners clockwise,
and downloading the resulting calibration. A future opposite-side camera must
have its own calibration file. Geometry remains a review aid until validated.

Compare an exported manual count against AI receiver-touch times and render
ball-centred review crops:

```powershell
python .\scripts\compare-alfheim-events.py
python .\scripts\render-alfheim-event-crops.py
```

The calibrated pass configuration uses a 1.8-player-height control radius,
one second of team smoothing, a 0.5-player-height minimum transfer, and a
45-pixel/second minimum release speed. Motion-aware contact filtering rejects
high-speed straight fly-bys, while a sharp ball-direction change remains a
possible touch. A six-second sender memory supports long clearances where the
player detector temporarily loses foot proximity.

Against the 14-event manual review, the current output strictly matches 7
events within one second and identifies 4 more likely timing matches within
three seconds. The live totals match the manual totals: red has 3 passes
(including one separately marked restart candidate) and 2 turnovers; black has
6 passes and 3 turnovers. The first black turnover uses inherited chunk state
because the clip starts after the corner kick has already been taken.

Sustained calibrated pitch exits produce a turnover for the most recent owner,
unless a nearby receiver-confirmed turnover already exists. Pass releases while
the ball is outside are rejected, and the two transfer inference paths are
deduplicated by receiver-touch time. A same-team reception after a detected
restart is shown as a separate low-confidence `restart_pass_candidate`; it is
visible in live counts but excluded from measured normal-pass precision because
the off-pitch restart taker is not detected.
