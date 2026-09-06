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
