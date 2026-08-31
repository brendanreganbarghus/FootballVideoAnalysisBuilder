# Grassroots club pilot profile

This profile keeps the football analytics POC local-first, inexpensive, and
camera-neutral. It is a target architecture and acceptance checklist, not a
claim that every stage is production-ready.

## Approved stack

| Stage | Pilot choice | Current status |
| --- | --- | --- |
| Video I/O | OpenCV for recorded files, frame decoding, drawing, and output | Implemented |
| Detection | YOLO11 exported to ONNX, benchmarked on the pilot laptop | Export command implemented; ONNX laptop benchmark pending |
| Tracking | ByteTrack through `model.track(..., tracker="bytetrack.yaml")` | Implemented in the single-video runner |
| Team grouping | Upper-torso crop, OpenCV K-Means dominant colour, pre-match team/referee references | Implemented as an optional cached-track classifier |
| Pitch mapping | Four or more image/pitch point pairs and OpenCV homography | Implemented |
| Possession | Sustained ball-to-player control observations, aggregated per minute | Implemented; provisional |
| Events | Existing receiver-control pass/turnover state machine | Implemented; benchmark accuracy remains limited |
| Movement | Homography-projected player distance, maximum speed, and heatmap bins | Implemented |
| Publishing | Compact local JSON; browser/HDMI display consumes only statistics | Implemented |
| Live ingest | RTSP/HLS/RTMP capture, reconnect, buffering, and chunk handoff | Not yet implemented |

The current high-resolution tiled benchmark uses a custom association algorithm
after cached detections. It is valuable for repeatable evaluation, but it is
not the ByteTrack pilot path. Do not describe that benchmark tracker as
ByteTrack.

## Licensing boundary

Open source does not automatically mean unrestricted commercial use:

- OpenCV is Apache-2.0.
- ByteTrack's repository is MIT licensed.
- Ultralytics software and YOLO models are offered under AGPL-3.0 and an
  enterprise licence. Exporting a checkpoint to ONNX does **not** remove the
  model/code licence obligations.
- Every downloaded checkpoint and dataset needs an explicit model licence,
  training-data provenance, attribution requirements, and permission for the
  planned commercial use. A Roboflow listing alone is not proof of those
  rights.

Before a paid pilot, either comply with AGPL-3.0 for the complete distributed
solution, obtain an Ultralytics enterprise licence, or benchmark a
commercially compatible detector and checkpoint. Keep model and dataset rights
in the pilot sign-off.

## Prepare the detector

Export an owned or properly licensed checkpoint:

```powershell
python .\scripts\export-yolo11-onnx.py .\models\football.pt `
  --image-size 1280 --simplify
```

Then pass the resulting `.onnx` file to the runner or detection cache through
`--model`. ONNX is a deployment format, not an accuracy improvement. Measure
effective frames per second, ball recall, temperature, and end-to-end latency
on the exact laptop before match day.

The existing single-video runner invokes ByteTrack:

```powershell
python -m football_poc.cli .\pilot-input.mp4 `
  --model .\models\football.onnx `
  --tracker bytetrack.yaml `
  --stride 1 `
  --output .\output\pilot
```

ByteTrack IDs survive ordinary frame-to-frame motion but can change after
occlusion, camera cuts, stream interruption, or a chunk restart. Statistics
must tolerate ID handoffs; they must not treat an ID as a permanent player
registry.

## Calibrate team colours

At warm-up, capture representative upper-torso colours for both teams and the
official. Store BGR reference colours using
[`config\team-colors.example.json`](..\config\team-colors.example.json).

For cached detections, enable K-Means classification:

```powershell
python -m football_poc.player_tracking_cli .\manifest.json `
  --player-cache .\cache\detections.jsonl `
  --ball-tracks .\cache\ball-tracks.json `
  --team-colors .\config\pilot-team-colors.json `
  --output .\output\tracked
```

K-Means extracts a dominant torso colour. The nearest pre-match reference maps
it to Team A, Team B, or official. Goalkeepers require explicit affiliation
because both teams may use the same goalkeeper colour. Lighting changes,
shadows, bibs, and background pixels still require temporal smoothing and
operator review.

## Calibrate the pitch

Copy [`config\pitch-calibration.example.json`](..\config\pitch-calibration.example.json)
and replace its points. Use at least four accurately identifiable pitch-line
intersections spread over the visible field. The destination points are metres
on the real pitch.

A single homography is valid for a fixed perspective camera and the ground
plane. It does not accurately model a heavily stitched panorama, moving
camera, or airborne ball. Those cases need piecewise/camera calibration.

## Publish one-minute statistics

After the existing player, ball, and possession stages:

```powershell
python -m football_poc.pilot_metrics_cli `
  --player-tracks .\output\tracked\player-tracks.json `
  --possession .\output\tracked\possession.json `
  --events .\output\tracked\predicted-events.json `
  --calibration .\config\pilot-pitch.json `
  --output .\output\scoreboard\latest.json
```

The compact JSON includes, per 60-second block:

- controlled-observation possession percentages;
- pass candidates and turnovers lost;
- distance and maximum speed per track;
- small team heatmap grids.

Only this lightweight JSON needs to leave the local laptop. Raw video can stay
at the club unless consent and retention policy explicitly allow upload.

## Camera-neutral, not camera-independent

Acceptable sources include a Veo feed, fixed 4K IP camera, security camera, or
phone only when they provide an accessible, stable stream or recording. The
minimum pilot check is:

- elevated fixed long-side view covering the whole pitch;
- no digital follow-cam crop for full-team tracking;
- 25 fps preferred, fixed exposure and focus where possible;
- enough bitrate that the ball remains visible rather than becoming a
  compression block;
- wired Ethernet where available; local recording during network loss;
- legal access to the stream and permission to process it.

Brand does not guarantee suitability. Test one representative minute and
record resolution, fps, ball diameter in pixels, blur, occlusion, packet loss,
and detector recall before accepting a camera.

## Pilot acceptance gates

1. Process a 60-second block in no more than 60 seconds on the target laptop.
2. Publish provisional JSON within 20 seconds after the block closes.
3. Continue locally when internet access is unavailable.
4. Recover from an interrupted chunk without duplicate public events.
5. Compare passes and turnovers against independent manual labels.
6. Show possession, event totals, and data freshness on the scoreboard.
7. Keep an operator correction path for disputed events.
8. Complete model/data licensing, privacy, minors, retention, and deletion
   review before using identifiable club footage.

Do not market player distance, speed, pass, or turnover figures as reliable
until held-out pilot matches meet agreed error thresholds.
