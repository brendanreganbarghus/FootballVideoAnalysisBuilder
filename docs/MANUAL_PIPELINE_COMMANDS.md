# Manual Football Pipeline Commands

Run commands from the repository root in PowerShell. The repository now has one
review workflow, `football_review`, one Canvas type, `football-event-review`,
and one rules engine in `src\football_poc`. Each segment records its selected
ball-coordinate source as `ball_source`:

| Source | Meaning | Benchmark claim boundary |
| --- | --- | --- |
| `bac` | Frozen Alfheim BAC coordinates feeding the downstream football engine | BAC-assisted diagnostic only; never raw-video ball inference or a valid ball-tracking benchmark |
| `live` | Raw-video detector and `ball_tracking.py` output | The fixed minimum 90% direct-coordinate provenance gate measures evidence coverage, not coordinate correctness or calibrated confidence |

Prepared-segment artifacts are flat under the segment root, not under
`innovation\` or `live\` subfolders. Runtime outputs include
`analysis-status.json`, `analysis.log`, `runtime-manifest.json`,
`analytics-cache\`, `analytics-data\`, `reviewer-coordinate-layer.json`,
`boundary-events.json`, and `shot-evidence.json`. `analysis-status.json` and
`analytics-data\run-provenance.json` carry `ball_source`.

## Run or rebuild a prepared Alfheim segment

Choose the ball source explicitly for a full run:

```powershell
$env:PYTHONPATH = "$PWD\src"
$segment = "benchmarks\alfheim\generated\segment-0540-060"

python scripts\process-alfheim-segment.py $segment --ball-source bac
python scripts\process-alfheim-segment.py $segment --ball-source live
```

Rebuild cached event output only after the segment already records its
`ball_source`:

```powershell
python scripts\process-alfheim-segment.py $segment --events-only
```

Use Live interrupted-run recovery only for Live runs:

```powershell
python scripts\process-alfheim-segment.py $segment --ball-source live --resume-after-detection
```

The processor rebuilds `shot-evidence.json` automatically for event builds
because shots on target is always analysed. To inspect that evidence manually:

```powershell
python -m football_poc.shot_evidence_adapter --segment-root $segment
```

BAC runs write ball tracks with intentionally frozen persisted identifiers such
as `source_kind = evaluation_only_provider_coordinates` and
`pipeline_mode = innovation_day_bac_assisted`. Do not rename those values in
artifacts or documentation; they are part of the historical output contract.

## Switching ball source in the Canvas

Use the Canvas **Run ball coordinates** button to create the first run for a
segment. Use **Change ball source** only when you intend to discard the derived
work for that segment. The switch endpoint is:

```text
POST /api/alfheim/switch-ball-source
{ "cache_key": "segment-0540-060", "ball_source": "bac", "confirm": true }
```

Switching is blocked while a job runs or another developer holds the lease. On
success it removes derived artifacts and review work (E# output, ball/player
and possession caches, C# proposals and decisions, E# confirmations, M↔E links,
and Passed status) while keeping the prepared video, `manifest.json`,
`segment.json`, and the M# golden set. The previous database
`segment_outputs` revisions remain append-only history.

## Publish an active prepared segment

Only segments intentionally exposed in the review dropdown belong in the shared
prepared catalogue. Publish a ready segment with its recorded `ball_source`:

```powershell
python .\scripts\publish-prepared-segment.py `
  .\benchmarks\alfheim\generated\segment-0120-020 `
  --workflow football_review `
  --camera-id f7a5f35d-9c61-5e9c-b6f3-795742c2c8f1 `
  --recording-id alfheim-pano-camera-setting-2
```

The command writes one canonical `segment.mp4`, normalizes the manifest, and
verifies files against `checksums.sha256`. The final Canvas publication gate
invokes the same publisher automatically. Do not publish inactive scratch
windows merely because they exist locally.

## Runtime and evaluation separation

Runtime manifests may contain raw media, frame/time ranges, camera calibration,
and non-label processing configuration only. Dataset event annotations,
provider events, manual review decisions, and reference coordinates must not
influence detection, tracking, confidence, thresholds, or rules-engine output.
Load evaluation references only after predictions are complete and frozen.

Fresh raw-video processing is the default performance path. Cache reuse is an
explicit diagnostic or interrupted-run recovery path and must be reported as
such, with wall time, processed video duration, real-time factor, achieved FPS,
and the acceleration factor required to publish before the next segment is due.

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
  -File scripts\install-review-startup.ps1
```

The installer adds a command to the current user's Windows Startup folder. At
sign-in it runs `scripts\start-review.ps1`, starts Docker Desktop when
necessary, applies the `unless-stopped` restart policy to the dedicated
`postgresql-container`, starts that container, launches the loopback review
server independently of the Copilot session, and waits until
`/api/coordination/health` reports `available`. It reads PostgreSQL credentials
only from existing per-user environment variables and requires no administrator
permission.

Run the bootstrap manually after a restart if the Canvas is needed before the
Startup command finishes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File scripts\start-review.ps1
```

### 1. Start the local server

```powershell
$env:PYTHONPATH = "$PWD\src"

python scripts\serve-local.py `
  --bind 127.0.0.1 `
  --port 8080 `
  --directory "$PWD"
```

Check a segment status:

```powershell
Invoke-RestMethod `
  "http://127.0.0.1:8080/api/alfheim/status?cache_key=segment-0540-060"
```

If port 8080 is already serving the project, do not start a second copy.

### 2. Reload the project extension after code changes

In the GitHub Copilot app, reload extensions. The project extension is:

```text
project:football-event-review
```

Reloading restarts the extension provider. Any URL returned by an older
provider process may stop working, so reopen the Canvas instead of saving and
reusing an old temporary port.

### 3. Open Football Event Review

Ask Copilot in the project session:

```text
Open Football Event Review for segment-0540-060.
```

Copilot opens canvas type:

```text
football-event-review
```

with input like:

```json
{
  "segment": "segment-0540-060",
  "theme": "grassroots",
  "audit": false
}
```

The temporary address resembles:

```text
http://127.0.0.1:<temporary-port>/?segment=segment-0540-060&theme=grassroots
```

The same Canvas supports ball-coordinate audit mode for Live runs:

```json
{
  "segment": "segment-0540-060",
  "theme": "grassroots",
  "audit": true
}
```

## Troubleshooting

- If the API health check fails, start or restart `scripts\serve-local.py`.
- If the Canvas says its provider is unavailable, reload extensions and reopen
  the Canvas.
- If coordination is unavailable, the Canvas is read-only; it does not write a
  JSON fallback.
- If an old `127.0.0.1:<temporary-port>` URL is blank, do not edit the port by
  hand. Reopen the Canvas so the extension returns its current URL.
- If the segment appears to be processing when no process is running, inspect
  `benchmarks\alfheim\generated\<segment>\analysis-status.json`.
- Keep the `serve-local.py` terminal separate from YOLO, tracker, and rules
  terminals so stopping a processing command does not stop the review API.
