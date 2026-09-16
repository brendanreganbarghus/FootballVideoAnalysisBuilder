# Manual Football Pipeline Commands

This guide separates the live raw-video pipeline into independently runnable
stages. Run the commands from the repository root in PowerShell.

## Namespace and output safety

The commands in this guide have two different destinations:

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
