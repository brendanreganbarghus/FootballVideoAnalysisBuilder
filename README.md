# Football video analysis POC

This command-line POC evaluates one fixed, wide-area football video. It uses a
YOLO model with ByteTrack to:

- detect and track people and sports balls;
- label tracked people as stationary, walking, or running from image-space
  motion;
- propose ball-control and pass-or-shot candidates;
- produce an annotated MP4, object CSV, event JSON, and summary JSON.

The action labels are deliberately candidates. A single uncalibrated video
cannot reliably distinguish passes from shots, identify teams, or determine
shots on target and corners.

## Setup

Python 3.10-3.13 is supported by this project. Create a virtual environment and
install the package:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[test]"
```

Run it against a recording:

```powershell
.\.venv\Scripts\football-poc match.mp4 --output output
```

The default model is `yolo11n.pt`; Ultralytics downloads its weights on first
use. For a small football in a wide view, a football-specific model supplied
with `--model` will normally be necessary. Use `--device 0` for the first CUDA
GPU or `--device cpu` for CPU inference. The CPU-friendly defaults process
every second frame at 640 pixels and print progress with an estimated remaining
time.

Useful options:

```powershell
.\.venv\Scripts\football-poc match.mp4 `
  --model path\to\football-model.pt `
  --confidence 0.2 `
  --image-size 1280 `
  --device 0
```

For a quick CPU check before processing the whole recording:

```powershell
python -m football_poc.cli match.mp4 --output output --device cpu --max-frames 50
```

For higher accuracy after the quick check, use `--stride 1 --image-size 1280`.
This can be many times slower without an NVIDIA GPU.

## Outputs

- `annotated.mp4`: boxes, track IDs, and current motion labels.
- `objects.csv`: frame-by-frame detections and image-space positions.
- `events.json`: candidate ball controls and ball departures.
- `summary.json`: input details, counts, and limitations.

## Important limitations

- Generic COCO weights detect `person` and `sports ball`, but the ball may be
  only a few pixels in wide footage and frequently missed.
- Motion labels describe image-space movement, not calibrated real-world speed.
- `pass_or_shot_candidate` means the tracked ball departed a nearby player at
  speed. Team classification, pitch calibration, goal geometry, and temporal
  football rules are required to turn it into a confirmed event.
- Two-camera fusion is intentionally outside this first, single-video spike.

Ultralytics code and models have licensing conditions including AGPL-3.0 and
commercial options. Review the current Ultralytics licence before distributing
or commercializing this POC. A later commercial benchmark should include
permissively licensed alternatives such as RF-DETR.

## Grassroots pilot profile

The local-first pilot stack, licensing boundary, ONNX export, ByteTrack path,
K-Means team references, metric pitch calibration, per-minute JSON output, and
acceptance gates are defined in
[`docs\GRASSROOTS_PILOT.md`](docs/GRASSROOTS_PILOT.md).

The project deliberately keeps the validated event algorithm unchanged while
adding pilot infrastructure around it. In particular, ONNX is an optimized
deployment format but does not change the Ultralytics licence, and ByteTrack
IDs are best-effort identities rather than permanent player records.

## SoccerTrack v2 benchmark

SoccerTrack's documented Hugging Face repository is not live as of
2026-08-18. Use its official Google Drive mirror instead:

https://drive.google.com/drive/folders/1N2Qx2qkFgRtpbHitl2Vh6sLVYGgqkWwn

Install the optional downloader and fetch match `117093` annotations:

```powershell
python -m pip install -e ".[dataset]"
.\scripts\download-soccertrack-117093.ps1
```

Download the first-half panoramic video when sufficient disk space is
available:

```powershell
.\scripts\download-soccertrack-117093.ps1 -Content first
```

Use `-Content second` or `-Content both` for the other half. The mirror
currently provides panoramic videos, BAS action annotations, GSR files, and
raw calibration material, but no documented `mot\` folder. The project script
downloads only BAS and selected videos. SoccerTrack v2 data is CC BY 4.0 and
must be attributed.

The released `117093` BAS file contains 2,252 actions. Its actual top-level
field is `actions` and labels are uppercase (for example, `PASS`), despite the
repository documentation showing `annotations` and title-case labels. The
adapter accepts both forms and normalizes labels.

Inspect the downloaded annotations:

```powershell
python -m football_poc.soccertrack_cli inspect
```

Select the most pass-rich 60-second first-half window containing a shot and
write a ground-truth manifest:

```powershell
python -m football_poc.soccertrack_cli select-window `
  --half 1 `
  --duration 60 `
  --output benchmarks\soccertrack-117093-window.json
```

The manifest identifies the source video, exact frame range, normalized event
labels, clip-relative timestamps, and expected action counts. It lets future
detector/event benchmarks read the original 4K source directly without
re-encoding and degrading the small ball.

Cache tiled detections for that exact window:

```powershell
python -m football_poc.benchmark_cli `
  benchmarks\soccertrack-117093-window.json `
  --output benchmarks\soccertrack-117093-yolo `
  --device cpu
```

The runner splits each 4096-pixel panoramic frame into four overlapping
horizontal tiles, merges duplicate detections, and appends each completed frame
to `detections.jsonl`. An interrupted run can be resumed with the same command.
Use `--max-frames 2` for a cheap smoke test. `detection-summary.json` reports
ball-frame coverage and preserves the SoccerTrack ground-truth action counts.
It does not claim pass or shot accuracy until tracking and temporal event
inference consume the cached detections.

Track ball candidates from the completed cache without rerunning YOLO:

```powershell
python -m football_poc.ball_tracking_cli
```

This suppresses detections that remain in the same image cell for much of the
clip, applies the SoccerTrack panoramic pitch boundary, and joins plausible
motion across short detection gaps. `ball-tracking-summary.json` reports
tracked-frame coverage and whether a track is present near each labeled event.
That event-time support is only a detector diagnostic, not pass/shot accuracy.

### Football-trained detector comparison

Download the football-trained benchmark checkpoint:

```powershell
.\scripts\download-football-ball-model.ps1
```

The script pins and verifies SHA-256
`844E9AD1EBAFBD0C07F066E45AA87D9B87595DD9092DFEE9CAC3B10A6A5FA730`.
The checkpoint detects `ball`, `goalkeeper`, `player`, and `referee`; the
adapter normalizes its `ball` output to `sports ball`. Its Hugging Face model
card does not declare a model license or training-data provenance, so it is
restricted to internal POC benchmarking until those rights are clarified.

Run the cached comparison:

```powershell
python -m football_poc.benchmark_cli `
  benchmarks\soccertrack-117093-window.json `
  --output benchmarks\soccertrack-117093-football-model `
  --model models\football-players-ball-yolov8.pt `
  --confidence 0.01 `
  --image-size 960 `
  --stride 2 `
  --device cpu
```

On match `117093`, half 1, frames `31676-33176`, the generic `yolo11n.pt`
baseline produced accepted temporal tracks in 16.1% of sampled frames and had
ball-track evidence near 9/17 passes, 0/2 high passes, and 0/1 shot. The
football-trained checkpoint improved accepted track coverage to 31.9%, with
evidence near 17/17 passes, 1/2 high passes, and 1/1 shot. These figures measure
whether a plausible ball track exists within 0.32 seconds of a labeled event;
they are not pass/shot precision or recall. Player possession and event
classification are the next benchmark stage.

Fuse cached player detections with the accepted football-model ball tracks:

```powershell
python -m football_poc.player_tracking_cli
```

This filters detections to the panoramic pitch, links player identities,
classifies each frame's torso crop into blue, white, goalkeeper, official, or
unknown, and writes `benchmarks\soccertrack-117093-fused`. Per-frame team
labels prevent an identity switch between opponents from contaminating later
possession decisions. The
`tracking-verification.mp4` output overlays team labels, player track IDs, and
accepted ball points for visual review before possession events are counted.

After reviewing that video, infer possession transfers and benchmark pass
candidates without rerunning either model:

```powershell
python -m football_poc.possession_cli
```

This writes the control observations and stable segments to `possession.json`,
candidate transfers to `predicted-events.json`, and timestamp-matched precision
and recall to `event-evaluation.json`. Pass inference combines an observed
ball-release/flight state with confirmed sender and receiver control, then uses
the older stable-segment transfer as a deduplicated fallback. High passes are
evaluated as passes until calibrated trajectory height is available. Shot
candidates use manually calibrated normalized goal centers, ball speed and
direction, plus a receiver-control veto so ordinary passes toward goal are not
counted as shots.

Conservative interpolation within accepted ball tracks fills 114 short missing
detections and raises tracked-frame coverage from 31.9% to 45.9%. On the first
window, the flight-aware state machine predicts 16 passes, of which 12 match 19
labels within one second: 75.0% precision and 63.2% recall. Shot speed and pass
release speed continue to use observed points only, so interpolation cannot
invent an event trajectory. These are useful POC results, not production
accuracy claims.

The same window contains one labeled shot. The calibrated baseline predicts one
shot at 30.12 seconds, matching the 30.0-second annotation. This single example
validates the wiring and geometry, but is far too small to claim a reliable
shot precision or recall rate; additional shot-rich windows are required.

Run the complete resumable pipeline for another manifest:

```powershell
.\scripts\run-soccertrack-window.ps1 `
  -Manifest benchmarks\soccertrack-117093-window-2.json `
  -Name soccertrack-117093-window-2
```

The runner uses the four-class football checkpoint for both player and ball
detections, then executes ball tracking, player/team tracking, possession, and
event evaluation. Completed detection frames are cached, so an interrupted run
continues rather than starting again.

Aggregate multiple completed windows:

```powershell
python -m football_poc.aggregate_cli `
  benchmarks\soccertrack-117093-fused\event-evaluation.json `
  benchmarks\soccertrack-117093-window-2-fused\event-evaluation.json `
  benchmarks\soccertrack-117093-window-3-fused\event-evaluation.json
```

Across the three preselected windows, the current fixed-threshold baseline
matches 22 of 31 predicted passes against 46 labels: 71.0% precision and 47.8%
recall. It matches 1 of 4 predicted shots against 3 labels: 25.0% precision and
33.3% recall. The weaker independent-window shot result supersedes the
single-window result as the honest generalization baseline.

Replay the first completed window as overlapping live-style chunks:

```powershell
python -m football_poc.chunk_simulator_cli `
  --chunk-seconds 20 `
  --overlap-seconds 2 `
  --processing-seconds 20
```

The simulator publishes provisional event totals after each chunk, persists
accepted-event/finalization state, suppresses overlap duplicates, and compares
the final stream result with the batch event file. `--processing-seconds`
controls synthetic worker latency so queue backlog can be tested independently
from event correctness. A checkpoint is written after every chunk; use
`--max-chunks 2` to simulate interruption and rerun the same command to resume.

Build the team demonstration after benchmarks and chunk validation:

```powershell
python -m football_poc.demo_cli
python -m http.server 8000
```

Open `http://localhost:8000/demo/`. The generated page includes the annotated
video, six-stage architecture, aggregate metrics, event timeline, incremental
chunk statistics synchronized to video playback, limitations, and presenter
flow. The live counters replay precomputed chunk results; they do not claim the
current CPU performs model inference in real time.

## Technical knowledge pack

- Read [`docs\DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md) for the architecture,
  package responsibilities, code map, tuning points, and dependency-aware rerun
  commands.
- Present or edit
  [`docs\Football-Analytics-Knowledge-Session.pptx`](docs/Football-Analytics-Knowledge-Session.pptx).
- Use
  [`docs\Football-Analytics-Knowledge-Session.pdf`](docs/Football-Analytics-Knowledge-Session.pdf)
  for a read-only copy.
- Use the shorter, non-technical
  [`docs\Football-Analytics-Product-Pitch.pptx`](docs/Football-Analytics-Product-Pitch.pptx)
  or its
  [`PDF copy`](docs/Football-Analytics-Product-Pitch.pdf)
  for club owners, partners and product discussions.

Rebuild the editable PowerPoint after changing its content:

```powershell
python .\scripts\build-knowledge-deck.py
python .\scripts\build-product-pitch.py
```

## Alfheim labelled ball benchmark

Camera Setting 2 from the
[Simula Alfheim dataset](https://datasets.simula.no/alfheim/) provides native
panoramic H.264 segments with a labelled ball coordinate for every frame.
After downloading its `pano` folder, prepare the selected one-minute benchmark:

```powershell
python .\scripts\prepare-alfheim-window.py
```

See [`benchmarks\alfheim\README.md`](benchmarks/alfheim/README.md) for outputs,
POC commands, and the dataset's non-commercial research restrictions.
