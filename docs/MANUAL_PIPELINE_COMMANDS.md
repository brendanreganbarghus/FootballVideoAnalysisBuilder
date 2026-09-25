# Manual Football Pipeline Commands

This guide separates the BAC-assisted Innovation Day workflow from the live
raw-video pipeline, then splits the live pipeline into independently runnable
stages. Run the commands from the repository root in PowerShell.

## Choose the workflow first

Innovation and Live may use the same prepared video segment, but they are
separate workflows with separate engines, artifacts, review state, and Canvas
providers:

| Property | Innovation Day | Live |
|---|---|---|
| Purpose | Demonstrate and review the frozen downstream football engine | Develop and review the current raw-video pipeline |
| Ball evidence | Frozen BAC provider coordinates | Raw-video detector and iteration-25 tracker |
| Engine | `src\football_poc\innovation_day_snapshot` | Current `src\football_poc` engine |
| Segment artifacts | `innovation\` | `live\` |
| Review state | `event-review-state-innovation` | `event-review-state-live` |
| Canvas provider | `project:football-event-review` | `project:football-event-review-live` |
| Canvas type | `football-event-review` | `football-event-review-live` |
| State workflow ID | `innovation_day_bac` | `live_iteration_25` |

Never copy artifacts or review state between these columns. A visual theme or
segment name does not select a workflow; the Canvas identity, state workflow
ID, and artifact namespace do.

### Run or rebuild Innovation Day

The Innovation runner writes only to:

```text
benchmarks\alfheim\generated\<segment>\innovation
```

Run the frozen Innovation player pipeline and rules engine:

```powershell
$env:PYTHONPATH = "$PWD\src"
$segment = "benchmarks\alfheim\generated\segment-0540-060"

python scripts\process-alfheim-innovation-segment.py $segment
```

Rebuild only the cached Innovation event output:

```powershell
python scripts\process-alfheim-innovation-segment.py $segment --events-only
```

Check optional shots-on-target evidence readiness (SOT stays off unless the
Canvas setting is enabled and readiness is `ready`; see
`docs\RULES_ENGINE_ARCHITECTURE.md`):

```powershell
python -m football_poc.innovation_day_snapshot.shots_on_target readiness "$segment\innovation\shot-evidence.json"
```

The runner accepts BAC only through its dedicated extraction step and writes
`innovation\analytics-cache\ball-tracks.json` with:

```text
source_kind = evaluation_only_provider_coordinates
pipeline_mode = innovation_day_bac_assisted
```

The Innovation Canvas rejects any other ball-track provenance. It presents
every BAC point as a read-only `frozen_bac` coordinate; it has no coordinate
review rounds and no Live 90% direct-coordinate gate. BAC makes this a
diagnostic/demo workflow, not raw-video ball inference and not a valid
ball-tracking performance benchmark.

After reloading extensions, ask Copilot to open Football Event Review for the
prepared segment. The provider uses an ephemeral loopback port, so reopen the
Canvas instead of saving its URL. Its local endpoints are:

- Segment catalog: `/api/alfheim/segments?workflow=innovation`
- Status: `/api/alfheim/innovation/status`

Existing passed Innovation segments can be reviewed from their frozen
artifacts without rerunning AI. Run the processor only for a new prepared
segment, an intentional frozen-pipeline rebuild, or a guarded event rebuild.

### Publish an active prepared segment

Only segments intentionally exposed in an Innovation or Live dropdown belong
in the shared prepared catalogue. Publish one selected workflow after its
local artifacts are ready:

```powershell
python .\scripts\publish-prepared-segment.py `
  .\benchmarks\alfheim\generated\segment-0120-020 `
  --workflow innovation_day_bac `
  --camera-id f7a5f35d-9c61-5e9c-b6f3-795742c2c8f1 `
  --recording-id alfheim-pano-camera-setting-2
```

For Live, use `--workflow live_iteration_25`. The command copies only the
selected namespace, writes one canonical `segment.mp4`, normalizes the shared
manifest, and verifies every file against `checksums.sha256`. Re-publishing
one workflow preserves the other workflow namespace for the same prepared
segment. The final Canvas publication gate invokes this command automatically.

The local server prefers a local generated segment with the same ID; otherwise
it discovers the verified bundle under
`15-prepared-segments\<camera-id>\<recording-id>\<segment-id>`. PostgreSQL
continues to provide mutable review state and history. Do not publish inactive
scratch windows merely because they exist in the local generated directory.

## Namespace and output safety

The remaining commands in this guide operate on the Live workflow and have two
different destinations:

| Command | Destination | Changes validated `live` artifacts? |
|---|---|---|
| Broad YOLO only | `manual-cpu-run\analytics-cache` | No |
| Ball tracking only | `manual-cpu-run\analytics-cache` | No |
| Rules engine with `--artifact-namespace live --events-only` | `live` | **Yes** |
| Complete pipeline with `--artifact-namespace live` | `live` | **Yes** |

The word `live` describes the current raw-video workflow, but it is also the
name of the persisted artifact directory:

```text
benchmarks\alfheim\generated\<segment>\live
```

A command writes to that directory only when it explicitly receives:

```text
--artifact-namespace live
```

or when an input/output path itself contains `\live\`.

The isolated manual commands use:

```powershell
$run = "$segment\manual-cpu-run"
```

Therefore their output goes to:

```text
benchmarks\alfheim\generated\segment-0540-020\manual-cpu-run
```

and cannot overwrite:

```text
benchmarks\alfheim\generated\segment-0540-020\live
```

Before running a command, print and resolve both paths:

```powershell
$segment = "benchmarks\alfheim\generated\segment-0540-020"
$run = "$segment\manual-cpu-run"

Write-Host "Protected live output:"
Resolve-Path "$segment\live"

Write-Host "Manual experiment output:"
[System.IO.Path]::GetFullPath($run)
```

For manual experimentation, check that `$run` does not resolve inside the
`live` directory:

```powershell
$livePath = [System.IO.Path]::GetFullPath("$segment\live")
$runPath = [System.IO.Path]::GetFullPath($run)

if ($runPath.StartsWith($livePath, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Refusing to run: the manual output is inside the protected live namespace."
}
```

### Commands that intentionally modify `live`

These flags are the visible warning:

```text
--artifact-namespace live
```

The rules-only command modifies the existing `live\analytics-data` outputs:

```powershell
python scripts\process-alfheim-segment.py `
  "benchmarks\alfheim\generated\segment-0540-020" `
  --artifact-namespace live `
  --events-only
```

The complete cold command modifies the whole live runtime output:

```powershell
python scripts\process-alfheim-segment.py `
  "benchmarks\alfheim\generated\segment-0540-020" `
  --artifact-namespace live
```

Do not run either command while preserving the current live result unless the
live directory has first been copied to a safe snapshot.

### Canvas namespace

The Canvas is also explicitly limited to the live workflow:

- Canvas provider: `project:football-event-review-live`
- Canvas type: `football-event-review-live`
- Segment catalog request: `/api/alfheim/segments?workflow=live`
- Status request: `/api/alfheim/live/status`
- Runtime artifact root:
  `benchmarks\alfheim\generated\<segment>\live`
- Review state directory: `event-review-state-live`

It does not load the separate `innovation` namespace. Ball Trajectory Audit is
a view mode within the same live Canvas and reads the same live runtime
artifacts.

## Current workspace

- Worktree:
  `D:\Projects\Xebia\FootballVideoAnalysisBuilder-worktrees\pass-shot-validation`
- Branch: `feature/pass-shot-validation`
- Repository: `brendanreganbarghus/FootballVideoAnalysisBuilder`

Open the worktree directory, not the parent repository checkout, in Rider.

## Current validated state

The preserved 09:00-10:00 focused-recovery result contains:

- 300 sampled frames.
- 264 Direct coordinates.
- 36 unresolved Estimated coordinates.
- Zero regressed Direct frames.
- 88.0% Direct provenance, so the localhost 90% gate correctly leaves the
  segment in **Ball coordinates need review**.

This result reused frozen broad YOLO detections and is therefore a cached
recovery result, not a cold raw-video performance measurement.

The protected 09:00-09:20 baseline contains 94 Direct coordinates from 100
sampled frames. Its player tracks, possession, and predicted events match the
frozen baseline hashes.

The previous complete cold 20-second CPU measurement was:

| Stage | Wall time |
|---|---:|
| YOLO detection | 684.540 seconds |
| Ball tracking | 286.483 seconds |
| Player tracking | 14.512 seconds |
| Rules/event inference | 4.282 seconds |
| Chunk publication | 0.144 seconds |
| **Complete pipeline** | **989.975 seconds** |

That run processed 20 seconds of video with a real-time factor of 49.499 and
an achieved source rate of 0.505 frames per second.

## PowerShell setup

```powershell
$env:PYTHONPATH = "$PWD\src"

$segment = "benchmarks\alfheim\generated\segment-0540-020"
$run = "$segment\manual-cpu-run"
New-Item -ItemType Directory -Force "$run\analytics-cache" | Out-Null
```

The separate `manual-cpu-run` directory prevents these experiments from
overwriting the validated `live` artifacts.

## Stage 1: run only broad YOLO

```powershell
python -m football_poc.benchmark_cli `
  "$segment\live\runtime-manifest.json" `
  --output "$run\analytics-cache" `
  --model "$PWD\yolo26n.pt" `
  --device cpu `
  --confidence 0.10 `
  --image-size 960 `
  --stride 5 `
  --tile-width 960 `
  --tile-height 960 `
  --overlap 0.2 `
  --nms-iou 0.5 `
  --frame-batch-size 2
```

This runs broad YOLO inference for people and sports-ball candidates. It does
not select the final ball trajectory or run football rules.

Outputs:

```text
manual-cpu-run\analytics-cache\detections.jsonl
manual-cpu-run\analytics-cache\detection-summary.json
```

Omit `--reuse-cache` for a true cold raw-video measurement. Supplying
`--reuse-cache` makes the run an explicit interrupted-run recovery and its
timing must not be reported as cold processing.

## Developer ball-validation CLI

Use this wrapper for visible 20-second YOLO model comparisons and ball-tracker
experiments. It reuses the production tiled detector and tracker, refuses to
write inside the protected `live` namespace, and loads the protected baseline
only after a new prediction is complete.

Set the source path once in Rider's PowerShell terminal:

```powershell
$env:PYTHONPATH = "$PWD\src"
```

Run the current `yolo26n` configuration first:

```powershell
python -m football_poc.ball_validation_cli yolo `
  --segment segment-0540-020 `
  --models n `
  --compare
```

Run any comma-separated model selection:

```powershell
python -m football_poc.ball_validation_cli yolo `
  --segment segment-0540-020 `
  --models n,s,m `
  --compare
```

For a quicker detector-concept screen that asks only whether each model sees a
`sports ball`, use a separate run name and `--ball-only`:

```powershell
python -m football_poc.ball_validation_cli yolo `
  --segment segment-0540-020 `
  --run-name ball-only-smoke `
  --models n,s,m `
  --max-frames 10 `
  --ball-only
```

This excludes person results and may reduce result post-processing, but every
tile still passes through YOLO, so it does not remove the main neural-network
cost. A ball-only cache is labelled `detection_scope: ball_only` and is
deliberately rejected by the production ball tracker because player context is
required. Use it only to compare raw detector recall, confidence, and timing.

Run the three models against the 23 independently reviewed raw frames from the
60-second segment:

```powershell
python -m football_poc.ball_validation_cli yolo `
  --segment segment-0540-060 `
  --run-name reviewed-23-ball-models `
  --models n,s,m `
  --frames 505,520,555,650,760,765,770,780,785,790,795,805,815,820,825,915,975,1065,1120,1190,1195,1230,1285 `
  --ball-only
```

`--frames` contains source-frame numbers and cannot be combined with
`--max-frames`. Predictions are produced without reading reviewed coordinates.
After all three model outputs are frozen, their candidates and confidence can
be evaluated against the separate review ledger.

Use `--models all` for `yolo26n/s/m/l/x`. This can take several hours on CPU,
especially for `l` and `x`; each completed model has an independent cache and
report. Missing weights are resolved by Ultralytics and may be downloaded on
first use.

After a model's YOLO cache completes, run ball coordinates only:

```powershell
python -m football_poc.ball_validation_cli track `
  --segment segment-0540-020 `
  --models n `
  --compare
```

Run both stages in sequence:

```powershell
python -m football_poc.ball_validation_cli pipeline `
  --segment segment-0540-020 `
  --models n `
  --compare
```

Reprint comparisons without rerunning either stage:

```powershell
python -m football_poc.ball_validation_cli compare `
  --segment segment-0540-020 `
  --models n `
  --stage all `
  --show-all-frames
```

The default output is:

```text
benchmarks\alfheim\generated\segment-0540-020\
  developer-runs\ball-validation\<model>\
```

Each YOLO run writes:

```text
detections.jsonl
detection-summary.json
yolo-run-report.json
yolo-comparison.json
```

Each ball-tracking run additionally writes:

```text
ball-tracks.json
ball-state-estimates.json
ball-tracking-summary.json
decode-cache-metrics.json
tracking-run-report.json
tracking-comparison.json
```

The terminal uses green for matches, red for missing outputs, cyan for gains,
and yellow for changed coordinates, candidate sets, or provenance. By default
it prints changed frames only; `--show-all-frames` prints every sampled frame.
Use `--no-color` or the `NO_COLOR` environment variable when redirecting
output.

YOLO reports model loading, video decoding, inference, post-processing/write
time, wall time, and real-time factor. Ball tracking reports wall time,
decoded-frame-cache build time, and its ten slowest substages. The run reports
record whether raw video was processed cold or a diagnostic cache was reused.

For a short command check, `--max-frames 5` is available on `yolo`, but that is
an incomplete diagnostic and its comparison will correctly report all
unprocessed baseline frames as missing. Do not describe it as a complete
20-second result.

## Stage 2: run only ball detection and tracking

```powershell
python -m football_poc.ball_tracking_cli `
  "$segment\live\runtime-manifest.json" `
  --cache "$run\analytics-cache\detections.jsonl" `
  --output "$run\analytics-cache"
```

This consumes the broad YOLO result and raw video. It runs ball candidate
selection, temporal recovery, optical flow, focused redetection, and final
trajectory-integrity checks.

Outputs:

```text
manual-cpu-run\analytics-cache\ball-tracks.json
manual-cpu-run\analytics-cache\ball-state-estimates.json
manual-cpu-run\analytics-cache\ball-tracking-summary.json
manual-cpu-run\analytics-cache\decode-cache-metrics.json
```

The temporary lossless decoded-frame cache is removed after a successful
fresh run. Do not add `--reuse-decoded-frame-cache` when measuring a true cold
run. Cache reuse is for diagnostics or interrupted-run recovery only.

## Stage 3: run only the rules engine

```powershell
python scripts\process-alfheim-segment.py `
  "benchmarks\alfheim\generated\segment-0540-020" `
  --artifact-namespace live `
  --events-only
```

This skips broad YOLO, ball tracking, and player tracking. It rebuilds ball
provenance, possession, match state, analytics events, and chunk publication
from the existing live tracking artifacts.

Required inputs:

```text
live\analytics-cache\ball-tracks.json
live\analytics-cache\ball-state-estimates.json
live\analytics-data\player-tracks.json
```

Outputs:

```text
live\analytics-data\ball-provenance.json
live\analytics-data\possession.json
live\analytics-data\predicted-events.json
live\analytics-data\chunk-simulation.json
```

The rules-only command operates on the `live` namespace. Preserve or copy that
namespace before experimenting if its current output must remain unchanged.

## Complete cold 20-second pipeline

```powershell
python scripts\process-alfheim-segment.py `
  "benchmarks\alfheim\generated\segment-0540-020" `
  --artifact-namespace live
```

This deliberately removes prior runtime outputs and processes the raw video
through detection, tracking, provenance, possession, event inference, and
publication. Do not use `--resume-after-detection`, `--focused-recovery`, or
`--events-only` when measuring cold processing.

Do not start a cold 60-second run until the 20-second output comparison has
zero regressions and its measured wall time, real-time factor, achieved FPS,
and projected 60-second duration have been reported.

## Runtime and evaluation separation

Runtime manifests may contain raw media, frame/time ranges, camera
calibration, and non-label processing configuration only. Dataset event
annotations, provider events, manual review decisions, and reference
coordinates must not influence detection, tracking, confidence, thresholds,
or rules-engine output.

Load evaluation references only after predictions are complete and frozen.

## Start the local review server and Canvas

The review workflow has two local parts:

1. `scripts\serve-local.py` serves segment media and the local analysis API on
   port 8080.
2. The project Canvas extension creates a separate temporary loopback URL for
   each opened Canvas panel.

### Windows restart recovery

Install the per-user logon bootstrap once:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File scripts\install-innovation-review-startup.ps1
```

The installer adds a command to the current user's Windows Startup folder. At
sign-in it runs `scripts\start-innovation-review.ps1`, starts Docker Desktop
when necessary, applies the `unless-stopped` restart policy to the dedicated
`postgresql-container`, starts that container, launches the loopback review
server independently of the Copilot session, and waits until
`/api/coordination/health` reports `available`. It reads PostgreSQL credentials
only from the existing per-user environment variables and requires no
administrator permission.

Run the bootstrap manually after a restart if the Canvas is needed before the
Startup command finishes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File scripts\start-innovation-review.ps1
```

### 1. Start the local server

From the repository root in a PowerShell terminal:

```powershell
$env:PYTHONPATH = "$PWD\src"

python scripts\serve-local.py `
  --bind 127.0.0.1 `
  --port 8080 `
  --directory "$PWD"
```

Leave that terminal running while using the Canvas. Binding to `127.0.0.1`
keeps the API available only on the local machine.

Check that the live-segment API is responding:

```powershell
Invoke-RestMethod `
  "http://127.0.0.1:8080/api/alfheim/live/status?cache_key=segment-0540-060"
```

If port 8080 is already serving the project, do not start a second copy.

### 2. Reload the project extension after code changes

In the GitHub Copilot app, use the command palette to reload extensions. The
project extension is:

```text
project:football-event-review-live
```

Reloading restarts the extension provider. Any URL returned by an older
provider process may stop working, so reopen the Canvas instead of saving and
reusing an old temporary port.

### 3. Open normal Live Football Event Review

Ask Copilot in the project session:

```text
Open Live Football Event Review for segment-0540-060.
```

Copilot opens canvas type:

```text
football-event-review-live
```

with this input:

```json
{
  "segment": "segment-0540-060",
  "theme": "grassroots",
  "audit": false
}
```

The returned address resembles:

```text
http://127.0.0.1:<temporary-port>/?segment=segment-0540-060&theme=grassroots
```

The temporary port is allocated when the Canvas opens and may change after an
extension reload.

### 4. Open Ball Trajectory Audit

Ask Copilot:

```text
Open Ball Trajectory Audit for segment-0540-060.
```

That opens the same Canvas type with:

```json
{
  "segment": "segment-0540-060",
  "theme": "grassroots",
  "audit": true
}
```

Its returned address includes:

```text
?segment=segment-0540-060&theme=grassroots&mode=trajectory-audit
```

Trajectory Audit exposes the sampled ball-coordinate frames, stride-5
Previous/Next navigation, raw-frame playback, the green engine crosshair, and
blue cached-YOLO candidate rings. It remains separate from normal event
review.

### Troubleshooting

- If the API health check fails, start or restart `scripts\serve-local.py`.
- If the Canvas says its provider is unavailable, reload extensions and reopen
  the Canvas.
- If an old `127.0.0.1:<temporary-port>` URL is blank, do not edit the port by
  hand. Reopen the Canvas so the extension returns its current URL.
- If the segment appears to be processing when no process is running, inspect:

  ```text
  benchmarks\alfheim\generated\<segment>\live\analysis-status.json
  ```

- Keep the `serve-local.py` terminal separate from YOLO, tracker, and rules
  terminals so stopping a processing command does not stop the review API.
