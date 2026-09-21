# Football analytics technical guide

This guide explains the current proof of concept (POC), the intended two-camera
home-ground system, where each algorithm lives, and how to change and rerun the
pipeline.

The canonical football-law, match-state, analytics-definition, portability,
and rule-change contracts live in
[`RULES_ENGINE_ARCHITECTURE.md`](RULES_ENGINE_ARCHITECTURE.md). Treat that
document as the architectural base for event-engine changes.

The project is currently a single-camera, offline benchmark with a live-style
replay. The two-camera RTSP ingestion, frame synchronization, GPU optimization,
operator review UI, and stadium-screen output are the next architecture stage;
they are not yet implemented.

The active Innovation Day workflow uses frozen BAC ball coordinates, cached
player evidence, the frozen Innovation engine, and
`event-review-state-innovation`. Live ball tracking and the Live review
workflow are frozen and separate; do not run or reuse them for Innovation
work.

## 1. Target home-ground architecture

```text
  Stable weatherproof tripod                 Stable weatherproof tripod
  Camera A: left half                        Camera B: right half
  4K, 25 fps, fixed exposure                 4K, 25 fps, fixed exposure
            |                                           |
            +---------- Cat6 / PoE Ethernet ------------+
                                |
                          Gigabit PoE switch
                                |
                   Local NVIDIA GPU workstation
                   - RTSP ingest and recording
                   - timestamp synchronization
                   - tiled player/ball detection
                   - cross-camera track fusion
                   - event inference and statistics
                                |
                    Local WebSocket / HTTP service
                       |                    |
               Operator review UI    Stadium display UI
                                      (browser / HDMI)
```

Use Cat6 Ethernet with Power over Ethernet (PoE), not long HDMI runs. Cat6 can
carry synchronized IP streams over 100 m, powers the cameras, and lets the GPU
PC ingest both feeds independently. The system should run on the club's local
network and continue operating without internet access.

Recommended initial display latency is 10-20 seconds. Public statistics should
be labeled "Provisional AI Statistics", with operator confirmation for goals,
shots on target, and disputed events.

## 2. Current processing pipeline

```text
SoccerTrack manifest / recorded video
              |
              v
Horizontal 4K tiles -> YOLO inference -> overlap NMS -> detections.jsonl
              |
              +------------------------+
              |                        |
              v                        v
       temporal ball tracks      player identity tracks
       + short interpolation     + per-frame team color
              |                        |
              +-----------+------------+
                          v
             possession observations and segments
                          |
             ball release / flight / reception state
                          |
                 pass, turnover, shot candidates
                          |
          benchmark metrics + chunk replay + HTML demo
```

Inference results are cached. Event logic can therefore be changed and tested
without rerunning slow YOLO inference.

## 3. Package responsibilities

| Package | Responsibility |
| --- | --- |
| Python | Pipeline orchestration, domain logic, CLIs, JSON/CSV outputs and tests |
| Ultralytics | YOLO model loading and player/ball object detection |
| PyTorch | Tensor execution on CPU or NVIDIA CUDA GPU underneath Ultralytics |
| OpenCV | Video decoding, frame access, resizing, drawing and video encoding |
| NumPy | Arrays and numerical operations used by OpenCV/Ultralytics and tests |
| LAP | Linear assignment support used by tracking dependencies |
| pytest | Automated behavior and regression tests |
| python-pptx | Reproducible generation of the knowledge-session PowerPoint |
| Browser JavaScript | Video-synchronized counters in the generated demo |

Most expensive pixel and neural-network operations execute in compiled C++ or
CUDA libraries. Python coordinates those operations. The current speed problem
is CPU-only tiled 4K inference, not Python syntax.

## 4. Project map

```text
FootballVideoAnalysisBuilder\
|-- src\football_poc\       Python package and algorithms
|-- tests\                  Unit and pipeline-behavior tests
|-- scripts\                Downloads, complete pipeline and deck generation
|-- benchmarks\             Manifests, caches, tracks, events and evaluations
|-- data\                   Large source datasets (ignored)
|-- models\                 Model weights (ignored)
|-- demo\                   Generated HTML and browser-compatible video
|-- docs\                   Knowledge deck and this guide
|-- pyproject.toml          Dependencies, package metadata and CLI entry points
`-- README.md               Main setup, benchmark and operational reference
```

### Innovation Day: reproducible developer workspace

Use three storage tiers. Do not put raw footage, model weights, detection
caches, track files, rendered videos, or archives in Git.

| Tier | Contents | Lifecycle |
| --- | --- | --- |
| Git repository | Code, tests, documentation, schemas, small configuration, and manifests containing logical source IDs rather than developer-specific absolute paths | Review and merge normally |
| Shared OneDrive artifact store | Authorized full recordings, immutable prepared 30/60-second segments, per-camera calibration, approved model packages and model cards, passed reference baselines, review receipts, engine/output fingerprints, and the SHA-256 inventory | Team-owned, checksummed, immutable after promotion |
| Local workspace | Fresh detections, ball/player tracks, initialization evidence, possession, provisional events, logs, thumbnails, and performance reports under `benchmarks\...\generated` or `benchmarks\custom-cameras` | Disposable and reproducible; never used as another developer's hidden input |

The governed OneDrive layout is:

```text
Innovationday Artifacts\
|-- 00-governance\checksums.sha256
|-- 00-governance\Verify-Artifacts.ps1
|-- 10-master-data\
|   |-- <club>\<venue>\<camera-id>\
|       |-- camera.json
|       |-- calibrations\<calibration-id>\pitch-calibration.json
|       `-- recordings\<recording-id>\
|           |-- recording.json
|           `-- source.<container>
|   `-- custom-cameras\custom-<camera-uuid>\
|       |-- camera.json
|       |-- sample.mp4
|       `-- pitch-calibration.json
|-- 15-prepared-segments\<camera-id>\<recording-id>\<segment-id>\
|   |-- segment.json
|   `-- segment.mp4
|-- 20-approved-models\<scope>\<model>\
|-- 30-shared-baselines\
|   |-- event-review-state-innovation\
|   |-- event-review-state-live\
|   `-- <baseline-version>\...
`-- 40-team-runs\<dataset>\<segment>\<run-id>\
    |-- run.json
    |-- checksums.sha256
    `-- selected reproducibility artifacts
`-- 40-results\coordination-backups\
    `-- football-coordination-<UTC timestamp>.zip
```

### Shared coordination control plane

OneDrive/Xebia Shared Drive is the artifact plane; PostgreSQL is the
coordination and history plane. PostgreSQL stores no video, frame image,
detection cache, coordinate stream, track cache, or result bundle. It stores a
provider-neutral logical artifact key, SHA-256, size, media type, immutable
version, and relationships to workflow-scoped segments and runs.

The first shared authority may be Brendan's local Docker PostgreSQL instance.
The endpoint is selected through deployment configuration and the secret
connection URL remains outside Git. The same code later points to Xebia
PostgreSQL. Innovation and Live use separate workflow identities, leases,
review histories, engine/tracker fingerprints, jobs, regressions, receipts, and
publications even when they reference the same prepared media.

The configured database must already exist. Backend startup obtains a
PostgreSQL advisory migration lock, applies checked forward-only migrations,
and verifies migration checksums, constraints, indexes, workflow seeds, and
historical reconciliation before enabling shared mutations. A configured but
unavailable or inconsistent database makes shared state read-only; it never
creates an offline mutation queue or silently falls back to mutable JSON.

An editing lease is exclusive per workflow and segment. Browsing does not take
a lease. **Start working** or the first shared mutation acquires one, followed
by a 30-second heartbeat and five-minute expiry fallback. The UI warns after 18
minutes without keyboard, pointer, touch, or review activity and releases the
editing lease at 20 minutes. Analysis and regression jobs use separate worker
leases and continue after an editing lease is released.

The Innovation review must also be opened from an active Copilot project
session for the same repository worktree. A standalone, copied, or stale local
URL remains available for viewing but is read-only and cannot acquire a lease
or invoke any mutation endpoint. The Canvas explains the missing connection
and provides **Refresh connection**; if the instance is stale, reopen the
Innovation review from its Copilot project session and retry.

After PostgreSQL is enabled, it is authoritative for mutable review state.
Checksummed OneDrive review JSON is imported idempotently and retained as
immutable source/export receipts. Before moving from local Docker to Xebia
PostgreSQL, pause writes, take a PostgreSQL-native consistent backup, restore
it, run migrations/reconciliation, compare deterministic row counts/digests
and all workflow history, then switch the configured authority. The retired
local database remains read-only and clients reject it as a writable authority.

The two review-state directories are intentionally incompatible. Innovation
state uses workflow ID `innovation_day_bac`, frozen BAC coordinates, and the
frozen Innovation engine. Live state uses workflow ID `live_iteration_25` for
the separate active ball-tracking R&D workstream. Do not rename, merge, or use
either directory as a fallback for the other.

`football-event-review` is the active Innovation review screen. The
`football-event-review-live` provider is used only by explicitly requested Live
work; do not open or use it for Innovation work. The shared implementation
remains in `.github\extensions\football-event-review\shared`, but each workflow
keeps its own adapter, state, artifacts, fingerprints, and publication gates.

The selected adapter controls the segment catalog, artifact namespace, state
directory, engine files, processing API, permitted actions, regression suite,
publication gate, prompts, and theme as one unit. Never select workflow
behavior from the theme or move state or artifacts between adapters.
Innovation hides `segment-0540-020` from its review catalog because it is an
exact regression prefix of the passed `segment-0540-060` run, not an
independent published Innovation reference. Its artifacts remain available to
the protected regression suite. Live catalog behavior is unchanged.

Each published Innovation row exposes **Run regression**. This action rebuilds
only cached event and match-state output with the current frozen Innovation
engine, then compares its combined output hash with the hash recorded when that
segment was published. The blocking modal reports the elapsed time and remains
open with an explicit pass, mismatch, or execution-failure result. It does not
run detection, use evaluation labels as inference input, or affect Live.

The source hierarchy is:

```text
Club -> Venue -> Camera -> Recording -> Prepared Segment -> AI Run
```

A camera has an immutable generated UUID, club, venue, position/role, and an
optional manufacturer serial number. The serial is metadata rather than the
primary key because hardware metadata can be absent and a camera can be moved
or replaced. A moved camera creates a new installation/calibration version.
Alfheim and SoccerTrack each currently register one test camera. Their
`TESTDATA-*` serials are assigned test identifiers, not manufacturer claims.

One camera may own multiple authorized raw recordings. A developer selects the
camera and recording, then a start position and exactly 30 or 60 seconds.
FFmpeg creates a child clip; the AI endpoint accepts only that child clip and
must reject the full 5-, 10-, 45-, or 90-minute recording. Store originals in
`10-master-data` and reusable child clips plus provenance manifests in the
append-only `15-prepared-segments` catalog. A segment manifest records the
camera, recording, calibration and hashes, source start, duration, creator,
creation time, and segment hash. This makes the same exact clip selectable by
other developers without using provider event labels.

The Review Canvas stores a newly uploaded custom-camera 30/60-second sample and
its calibration in `10-master-data\custom-cameras` until full-recording upload
is implemented. Every camera receives a unique source/calibration namespace.
Its detections, tracks, events, logs, and timing report run locally under
`benchmarks\custom-cameras`; they are not written into the synchronized source
folder. Alfheim, SoccerTrack, and custom-camera files must never be used as
fallbacks for one another.

### Windows developer onboarding

Use this sequence on a new Xebia Windows laptop. Do not copy another
developer's virtual environment, machine identity, database password, or local
generated caches.

1. Install Git, Python 3.11, and Docker Desktop if they are not already
   available:

   ```powershell
   winget install --exact --id Git.Git
   winget install --exact --id Python.Python.3.11
   winget install --exact --id Docker.DockerDesktop

   git --version
   py -3.11 --version
   docker version
   ```

   Restart the terminal after installation. Docker is required only for the
   developer who hosts local PostgreSQL; clients connecting to that host or to
   Xebia PostgreSQL do not need a local database container.

2. Retrieve the repository and select the agreed team branch:

   ```powershell
   git clone https://github.com/brendanreganbarghus/FootballVideoAnalysisBuilder.git
   Set-Location .\FootballVideoAnalysisBuilder
   git fetch --all --prune
   git switch <shared-branch>
   git status --short --branch
   ```

   Replace `<shared-branch>` with the branch named in the handoff. Do not start
   work from an old local copy or infer the branch from a OneDrive folder.

3. Create an isolated Python environment and install the project, tests,
   dataset helpers, and PostgreSQL coordination support:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\python -m pip install --upgrade pip
   .\.venv\Scripts\python -m pip install -e ".[test,dataset,coordination]"
   .\.venv\Scripts\python -c "import football_poc, cv2, psycopg; print('Python environment ready')"
   ```

   Calling `.\.venv\Scripts\python` directly avoids PowerShell execution-policy
   problems. Activating the environment is optional:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

4. Sync the approved **Innovationday Artifacts** folder through OneDrive and
   configure its logical root outside Git:

   ```powershell
   $artifactRoot = "C:\Users\<name>\OneDrive - Xebia\Innovationday Artifacts"
   [Environment]::SetEnvironmentVariable(
     "FOOTBALL_ARTIFACT_ROOT",
     $artifactRoot,
     "User"
   )
   $env:FOOTBALL_ARTIFACT_ROOT = $artifactRoot
   $env:FOOTBALL_ALFHEIM_PANO = Join-Path `
     $artifactRoot "10-master-data\alfheim\pano"

   & "$artifactRoot\00-governance\Verify-Artifacts.ps1"
   .\.venv\Scripts\python .\scripts\verify-innovation-workspace.py --require-alfheim
   ```

5. Configure PostgreSQL without putting credentials in the repository. Copy
   the non-secret profile to the per-user application directory, then obtain
   `FOOTBALL_DATABASE_URL` from the current coordination administrator through
   the approved Xebia secret-sharing channel:

   ```powershell
   $configHome = Join-Path $env:LOCALAPPDATA "FootballVideoPOC"
   New-Item -ItemType Directory -Path $configHome -Force | Out-Null
   Copy-Item .\config\coordination.example.json `
     (Join-Path $configHome "coordination.json")

   [Environment]::SetEnvironmentVariable(
     "FOOTBALL_COORDINATION_CONFIG",
     (Join-Path $configHome "coordination.json"),
     "User"
   )
   [Environment]::SetEnvironmentVariable(
     "FOOTBALL_DATABASE_URL",
     "<secret PostgreSQL URL supplied outside Git>",
     "User"
   )
   ```

   Open a new terminal after setting user-level variables, or copy them into
   the current process before continuing:

   ```powershell
   $env:FOOTBALL_COORDINATION_CONFIG = `
     [Environment]::GetEnvironmentVariable(
       "FOOTBALL_COORDINATION_CONFIG", "User"
     )
   $env:FOOTBALL_DATABASE_URL = `
     [Environment]::GetEnvironmentVariable("FOOTBALL_DATABASE_URL", "User")
   $env:FOOTBALL_ARTIFACT_ROOT = `
     [Environment]::GetEnvironmentVariable("FOOTBALL_ARTIFACT_ROOT", "User")
   ```

   The configured database must already exist. Runtime credentials must have
   access only to that database and must not have `SUPERUSER`, `CREATEDB`, or
   `CREATEROLE`. Never paste the URL into Git, browser storage, screenshots, or
   support logs.

6. Bootstrap and verify the coordination authority:

   ```powershell
   .\.venv\Scripts\python -m football_poc.coordination.cli --json
   ```

   The expected result is `"mode": "available"` and `"writable": true`.
   Server startup repeats this migration, index, authority, and checksummed
   history-reconciliation gate. A configured but unavailable or inconsistent
   database starts read-only; it does not silently write JSON.

   Only the administrator performing the initial migration should run the
   explicit import. Always dry-run first:

   ```powershell
   .\.venv\Scripts\python -m football_poc.coordination.history_import `
     --source-root $env:FOOTBALL_ARTIFACT_ROOT `
     --provider xebia-shared `
     --dry-run

   .\.venv\Scripts\python -m football_poc.coordination.history_import `
     --source-root $env:FOOTBALL_ARTIFACT_ROOT `
     --provider xebia-shared `
     --apply
   ```

7. Run the workstation readiness checks and start the loopback backend:

   ```powershell
   .\.venv\Scripts\python -m pytest `
     tests\test_coordination.py `
     tests\test_coordination_import.py `
     tests\test_local_server.py `
     tests\test_event_review_canvas_extension.py -q

   .\.venv\Scripts\python .\scripts\serve-local.py `
     --bind 127.0.0.1 `
     --port 8080
   ```

   In another terminal, confirm the backend reports the intended authority:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8080/api/coordination/health
   Invoke-RestMethod http://127.0.0.1:8080/api/coordination/identity
   ```

   The machine is ready when the artifact verification passes, focused tests
   pass, coordination is `available`, the expected authority ID is shown, and
   the Review Canvas can browse a segment without taking a lease. Confirm the
   Copilot project-session warning is absent, then select **Start working**
   before editing and **Stop working** before leaving it.

#### Monday office laptop acceptance

Use a colleague's laptop as a clean-machine test rather than copying Brendan's
working directory. Record the laptop name, Git revision, Python version,
coordination authority ID, and result of each check.

1. Clone the repository and complete the Windows onboarding steps above.
2. Verify the OneDrive checksum inventory before opening any segment.
3. Confirm the coordination health endpoint is `available` and identifies the
   expected shared authority, not a retired or accidental local database.
4. Open the same Innovation segment on both laptops. Confirm both can browse it
   without a lease, the first **Start working** succeeds, and the second laptop
   becomes read-only with the correct developer, machine, stage, and heartbeat.
5. Release the first lease with **Stop working**, acquire it from the second
   laptop, make one harmless review-state change, and confirm both screens show
   the new version.
6. Start a protected regression, release the editing lease, and confirm the
   background job continues to its terminal result.
7. Disconnect one test client and verify its abandoned editing lease expires
   after five minutes. Do not wait for expiry on a segment with unsaved work.
8. Restart the backend and confirm migrations and historical reconciliation
   are idempotent and the imported review history is unchanged.

The laptop passes only when all eight checks succeed. Record failures instead
of bypassing PostgreSQL, copying mutable JSON, or changing a rule to fit one
segment.

The detector is resolved in this order: explicit
`FOOTBALL_DETECTOR_MODEL`, the checksummed shared approved model, then a local
generic `yolo11n.pt`. The football-specific checkpoint is never selected
implicitly because its training-data and licence provenance are unresolved.
The exact model path and SHA-256 are written into each cold-run performance
receipt.

Use this promotion rule:

1. Run the 30–60 second segment locally from raw video with cache reuse off.
2. Record and approve the ordered manual M# set independently, then compare it
   with frozen E# output. Time-based links are suggestions; explicit reviewer
   unique same-team, same-type matches within one second update
   automatically when the reviewer edits an M#; neither timestamp is changed,
   and differing or ambiguous events remain unmatched without arrow-based
   manual mapping. Use **Review missing E#** on an unmatched M# to record
   whether the engine missed a correct event, the M# needs editing, the M# is
   unsupported and must remain visibly rejected but excluded from the golden
   set, an erroneous entry must be removed, or the video requires independent
   adjudication. Cancelling or closing the guide makes no change.
3. Keep C# optional and diagnostic-only. Run protected regressions only after
   an inference/rules-engine change.
   Pre-manual-first Innovation references are retired historical artifacts and
   are excluded from active review and protected regressions. Begin the
   replacement regression line with the independently reviewed 04:00–05:00
   M# segment.
4. Publish only when the golden M# revision, engine source hash, output hash,
   reference count, automatic one-second matches, and final validation gate are
   current.
5. Publish any run that teammates need to inspect into the append-only shared
   run catalog. A passed reference is additionally promoted into
   `30-shared-baselines`.
6. Do not promote transient detections, tracks, logs, thumbnails, or failed and
   provisional outputs unless a debugging package is deliberately requested.

Publish a run without its large intermediate cache:

```powershell
python .\scripts\publish-segment-run.py `
  .\benchmarks\custom-cameras\custom-home-main `
  --dataset custom-home-main `
  --status provisional
```

Add `--include-cache` only when another developer needs the exact detections
and tracks for debugging. "Checked in" means published to this checksummed
OneDrive run catalog, not committed to Git. Each run uses an immutable UUID
folder, so developers can see one another's work without overwriting it.

Full-match upload with automatic segmentation and a shared "currently in use"
lease is a later workflow. Until that lock exists, shared master data and
passed baselines are append-only: do not overwrite an existing camera ID or
baseline folder.

### Parallel event-rule development

Use one branch, one worktree/session, and one pull request per event family.
Suggested Innovation Day ownership:

| Workstream | Owns | Must not own |
| --- | --- | --- |
| Shot attempts and outcomes | Shot candidate, on-target, off-target, saved/blocked evidence, and links to goals | Goal/restart law transitions |
| Goals and goal restarts | Goal confirmation and kick-off restart state | Generic shot-direction thresholds |
| Corners and goal kicks | Whole-ball goal-line crossing and restart-family classification | Possession/pass thresholds |
| Four-zone analytics | Calibrated zone membership and zone aggregates | Event truth or team classification |
| Platform integration | Shared event schema, registry, Canvas rendering, run publication, and merge sequencing | Event rules without the owning workstream |

A shot, shot outcome, and goal are related but separate facts. One attempt gets
a stable `attempt_id`. It may have exactly one terminal outcome such as
`on_target` or `off_target`; a confirmed goal is a separate event linked to
that attempt and also implies on-target. A saved on-target shot is not a goal.
Do not infer off-target merely because no goal occurred.

To reduce merge conflicts, event-family code should move toward separate
modules such as `events\shots.py`, `events\goals.py`,
`events\set_pieces.py`, and `analytics\zones.py`. A small central registry owns
canonical names and ordering. Only the integration owner changes the registry
or shared evidence contracts during the event. Developers should reuse a
merged shared evidence helper rather than copy a similar rule into another
module.

Merge rule work serially:

1. Branch from the same protected baseline and declare the owned event family.
2. Add focused tests plus at least one negative or abstention case.
3. Before review, update from the latest integration branch and resolve
   semantic overlap with already accepted rules.
4. Run the focused suite and every protected passed-segment regression.
5. Merge only if the new event appears without changing protected unrelated
   events. A failing or stale regression receipt blocks the merge.
6. Publish the new cold run and fingerprints to `40-team-runs`.
7. The next event-family branch updates to that merged commit and repeats the
   complete regression gate.

This cannot eliminate textual conflicts in shared contracts, but it prevents
two rule versions from being accepted independently and then combined without
rechecking behavior.

## 5. Algorithm and module map

### `src\football_poc\benchmark.py`

Object detection cache for exact benchmark windows.

- `BenchmarkManifest`: loads and validates the video/frame window.
- `horizontal_tiles`: divides a 4K panorama into overlapping horizontal tiles.
- `run_detection_cache`: runs YOLO and appends resumable JSONL records.
- `class_aware_nms`: removes duplicate tile-overlap detections.

Tune from `benchmark_cli.py`:

- `--confidence`: detector confidence threshold.
- `--image-size`: YOLO inference resolution per tile.
- `--stride`: process every Nth source frame.
- `--tile-width` and `--overlap`: panorama tiling.
- `--nms-iou`: duplicate suppression threshold.
- `--device 0`: first CUDA GPU; `--device cpu`: CPU.

Changing detector/model/tile settings requires a new detection cache.

### `src\football_poc\ball_tracking.py`

Turns isolated ball detections into plausible temporal tracks.

- `track_cached_balls`: complete cached-ball pipeline.
- `_inside_soccertrack_pitch`: rejects points outside the calibrated pitch.
- `_static_cells`: identifies persistent false balls such as field markings.
- `_associate_tracks`: joins detections using time and speed constraints.
- `interpolate_track_gaps`: conservatively fills short gaps inside accepted
  tracks while preserving observed/interpolated provenance.

Tune from `ball_tracking_cli.py`:

- `--static-cell-size`, `--static-occupancy`
- `--max-gap`, `--max-speed`
- `--minimum-track-points`
- `--event-tolerance`

Shot and pass-release velocity use observed points only. Interpolation cannot
invent a shot or kick trajectory.

### `src\football_poc\player_tracking.py`

Tracks people and assigns a team label per frame.

- `track_cached_players`: complete cached-player pipeline.
- `_associate_players`: links detections into identities.
- `_jersey_features`: extracts torso color evidence.
- `classify_color_scores` and `_classify_tracks`: assign blue, white,
  goalkeeper, official, or unknown labels.
- `_render_verification_video`: creates the annotated benchmark video.

Tune from `player_tracking_cli.py`:

- `--confidence`
- `--max-gap`, `--max-speed`
- `--minimum-track-points`

Per-frame team labels are intentional. A mistaken identity merge should not
permanently change a track from one team to another.

### `src\football_poc\possession.py`

Contains the main football event logic.

- `_control_observations`: finds the player nearest the ball at foot level.
- `_smooth_teams`: reduces brief team-color noise.
- `build_possession_segments`: groups stable ownership observations.
- `infer_flight_transfer_events`: state machine for observed ball release,
  flight, first receiver and pass/turnover classification.
- `infer_transfer_events`: older stable-control transfer fallback.
- `merge_transfer_events`: deduplicates the state machine and fallback.
- `infer_shot_events`: uses observed speed, direction toward calibrated goal
  centers, receiver veto, and prior confirmed possession.
- `evaluate_events`: timestamp-matches predictions to SoccerTrack labels.

The defaults on `infer_cached_possession` are the main tuning surface:

- `control_radius_heights`
- `smoothing_seconds`
- `segment_gap_seconds`
- `identity_switch_radius_heights`
- `minimum_segment_observations`
- `maximum_transfer_seconds`
- `minimum_transfer_heights`
- `minimum_pass_speed_pixels_per_second`
- `maximum_pass_step_seconds`
- `pass_flight_debounce_seconds`
- `pass_sender_lookback_seconds`
- `pass_receiver_window_seconds`
- `transfer_deduplication_seconds`
- `maximum_flyby_speed_pixels_per_second`
- `initial_possession_team`
- `minimum_flyby_direction_cosine`
- `minimum_shot_speed_pixels_per_second`
- `minimum_shot_goal_cosine`

Change one threshold at a time and evaluate all three windows. Do not tune only
against the visible demo minute.

### `src\football_poc\match_state.py`

Contains the platform-neutral, law-grounded state model that gates event
inference.

- `MATCH_LAW_PROFILE`: reviewed official IFAB source profile.
- `MatchPlayState`: live, uncertain, stopped, restart-pending, and period-end
  states.
- `RestartType`: all Law 8 restart families.
- `build_match_state_timeline`: deterministic law/evidence transitions.
- `detect_stationary_ball_restarts`: observable restart evidence without a
  mandatory official detector.

Keep official match-state rules separate from analytics definitions in
`possession.py`. See
[`RULES_ENGINE_ARCHITECTURE.md`](RULES_ENGINE_ARCHITECTURE.md) before changing
either contract.

For the Alfheim diagnostic, high-speed straight ball motion near a player is
treated as a fly-by rather than control. Calibrated sustained pitch exits can
produce boundary turnovers, and inferred restart receptions use a distinct
`restart_pass_candidate` type so they do not silently change measured pass
precision. Each live chunk should inherit the prior chunk's possession team;
`initial_possession_team` supplies that state for an isolated clip. Pass
releases during an out-of-play interval are rejected, and duplicate receptions
from the flight and stable-segment inference paths are counted once.

### `src\football_poc\chunk_simulator.py`

Validates stream-state behavior using precomputed events.

- `make_replay_chunks`: creates overlapping chunks.
- `simulate_event_chunks`: checkpoints state, deduplicates overlap events,
  publishes provisional counts, and models queue latency.
- `_event_key`: event identity across overlapping chunks.

This module does not run model inference. It proves delivery and state behavior
that the future RTSP ingestion service must preserve.

### `src\football_poc\demo.py`

Builds the team-facing HTML demonstration.

- `build_demo`: architecture, metrics, timelines and team counters.
- `prepare_demo_video`: converts OpenCV FMP4 output to browser-compatible VP8.
- Embedded JavaScript synchronizes detected events to video time.

### Supporting modules

- `soccertrack.py`: released/documented annotation schema adapter and window
  selection.
- `aggregate.py`: three-window micro precision/recall aggregation.
- `actions.py`: original simple single-video action engine. It is useful prior
  art; the benchmark event logic now lives in `possession.py`.
- `team_colors.py`: OpenCV K-Means dominant jersey colour and reference mapping.
- `pitch_geometry.py`: image-space boundary checks plus metric homography.
- `pilot_metrics.py`: compact one-minute possession, event, heatmap, distance,
  and speed JSON for a local scoreboard service.
- `*_cli.py`: argument parsing and command-line entry points for each stage.

The pilot-specific operational and licensing requirements live in
[`GRASSROOTS_PILOT.md`](GRASSROOTS_PILOT.md). The benchmark player association
is custom; only the single-video `cli.py` path currently invokes ByteTrack.

## 6. Set up the development environment

From PowerShell in the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e ".[test,docs,dataset]"
```

`-e` means editable install. Changes under `src\football_poc\` are used on the
next Python invocation; there is no separate compile or refresh command.

If using the system Python instead of the virtual environment:

```powershell
python -m pip install -e ".[test,docs,dataset]"
```

## 7. Fast edit-test-run loop

After changing Python:

```powershell
python -m compileall -q src tests
python -m pytest -q
python -m pip check
```

Run one focused test while editing:

```powershell
python -m pytest -q tests\test_match_state.py
python -m pytest -q tests\test_possession.py
python -m pytest -q tests\test_ball_tracking.py
```

Run a specific test:

```powershell
python -m pytest -q tests\test_possession.py::test_ball_flight_confirms_sender_and_receiver
```

## 8. Dependency-aware rerun matrix

| What changed | Rerun |
| --- | --- |
| Demo HTML/CSS/JavaScript only | `python -m football_poc.demo_cli` |
| Chunk length/deduplication only | chunk simulator, then demo |
| Pass, turnover or shot logic | possession, chunk simulator, aggregate, demo |
| Team classification/player association | player tracking, possession, chunk simulator, aggregate, demo |
| Ball association/interpolation | ball tracking, player verification video, possession, chunk simulator, aggregate, demo |
| YOLO model/confidence/image size/tiles | detection cache in a new output directory, then every downstream stage |
| SoccerTrack parsing/window selection | manifest selection, then every benchmark stage |

### Event-logic-only refresh

This is the most common and fastest workflow:

```powershell
python -m football_poc.possession_cli
python -m football_poc.chunk_simulator_cli
python -m football_poc.aggregate_cli `
  benchmarks\soccertrack-117093-fused\event-evaluation.json `
  benchmarks\soccertrack-117093-window-2-fused\event-evaluation.json `
  benchmarks\soccertrack-117093-window-3-fused\event-evaluation.json
python -m football_poc.demo_cli
python -m pytest -q
```

When changing shared event logic, regenerate windows 2 and 3 before aggregation:

```powershell
python -m football_poc.possession_cli `
  benchmarks\soccertrack-117093-window-2.json `
  --player-tracks benchmarks\soccertrack-117093-window-2-fused\player-tracks.json `
  --ball-tracks benchmarks\soccertrack-117093-window-2-model\ball-tracks.json `
  --output benchmarks\soccertrack-117093-window-2-fused

python -m football_poc.possession_cli `
  benchmarks\soccertrack-117093-window-3.json `
  --player-tracks benchmarks\soccertrack-117093-window-3-fused\player-tracks.json `
  --ball-tracks benchmarks\soccertrack-117093-window-3-model\ball-tracks.json `
  --output benchmarks\soccertrack-117093-window-3-fused
```

### Full cached benchmark window

```powershell
.\scripts\run-soccertrack-window.ps1 `
  -Manifest benchmarks\soccertrack-117093-window-2.json `
  -Name soccertrack-117093-window-2
```

The script currently requests CPU inference. Change `--device` in the script to
`0` after installing a CUDA-compatible PyTorch environment on the GPU PC.

### Quick detector smoke test

```powershell
python -m football_poc.benchmark_cli `
  benchmarks\soccertrack-117093-window.json `
  --output benchmarks\smoke-test `
  --model models\football-players-ball-yolov8.pt `
  --device cpu `
  --max-frames 2
```

Use a new output directory when detector settings change. A resumable cache
refuses incompatible metadata to prevent accidental mixing.

## 9. Build and serve the demo

```powershell
python -m football_poc.demo_cli
python -m http.server 8000
```

Open `http://localhost:8000/demo/`.

The server must be started from the project root so the page can load its video
asset. Stop it with `Ctrl+C`.

## 10. Build the knowledge deck

```powershell
python .\scripts\build-knowledge-deck.py
```

Output:

```text
docs\Football-Analytics-Knowledge-Session.pptx
```

## 11. Current measured results

- Ball tracked-frame coverage after interpolation: 45.9%.
- First benchmark minute: 12 correct pass matches from 16 predictions against
  19 labels (75.0% precision, 63.2% recall).
- Three-window passes: 22 correct from 31 predictions against 46 labels
  (71.0% precision, 47.8% recall).
- Three-window shots: 1 correct from 4 predictions against 3 labels
  (25.0% precision, 33.3% recall).
- Current CPU tiled inference: about 0.4 panoramic frames per second.
- Target at source stride 2: 12.5 panoramic frames per second.

These figures are an honest POC baseline, not production accuracy.

## 12. Next implementation modules

The live system should add modules rather than place everything in one file:

```text
src\football_poc\streaming\
|-- rtsp_reader.py          Reconnectable camera ingest and timestamping
|-- synchronizer.py         Pair Camera A/B frames within a time tolerance
|-- recorder.py             Preserve original streams for review/retraining
|-- inference_worker.py     GPU batch/tile scheduling
|-- camera_fusion.py        Common pitch coordinates and duplicate tracks
|-- event_state.py          Persistent state across stream chunks
|-- publisher.py            WebSocket/JSON provisional statistics
`-- health.py               FPS, latency, dropped frames and camera status
```

Before coding this layer, obtain a one-minute original camera sample and measure:

- ball diameter in pixels at near, middle and far pitch locations;
- motion blur under daylight and floodlights;
- exact RTSP resolution, FPS, codec and bitrate;
- timestamp drift between the two cameras;
- GPU throughput at the required detection resolution.

## 13. Safe tuning practice

1. Preserve the current benchmark outputs before experiments.
2. Change one logical behavior or a small related parameter set.
3. Run focused unit tests.
4. Regenerate all three event evaluations from cached tracks.
5. Compare aggregate precision, recall and prediction counts.
6. Visually review the annotated video and event timestamps.
7. Keep a change only if it improves generalization or clearly fixes a defined
   failure without hiding new false positives.

Do not count an interpolated ball trajectory as observed evidence. Do not
present provisional candidates as confirmed official match statistics without
review.
