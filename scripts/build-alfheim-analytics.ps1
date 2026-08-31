$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

$window = ".\benchmarks\alfheim\window-555"
$manifest = "$window\manifest.json"
$cache = "$window\analytics-cache"
$results = "$window\analytics-data"
$page = "$window\analytics"

python .\scripts\build-alfheim-ball-track.py

python -m football_poc.benchmark_cli $manifest `
  --output $cache `
  --model .\yolo11n.pt `
  --confidence 0.12 `
  --image-size 960 `
  --stride 5 `
  --tile-width 1484 `
  --overlap 0.1

python -m football_poc.player_tracking_cli $manifest `
  --player-cache "$cache\detections.jsonl" `
  --ball-tracks "$window\ground-truth-ball-tracks.json" `
  --output $results `
  --confidence 0.2 `
  --max-gap 0.5 `
  --max-speed 700 `
  --minimum-track-points 3 `
  --team-profile red-black `
  --goalkeeper-affiliations "$window\goalkeeper-affiliations.json"

python -m football_poc.possession_cli $manifest `
  --player-tracks "$results\player-tracks.json" `
  --ball-tracks "$window\ground-truth-ball-tracks.json" `
  --output $results `
  --no-shots `
  --control-radius-heights 1.8 `
  --smoothing-seconds 1.0 `
  --minimum-transfer-heights 0.5 `
  --minimum-pass-speed 45 `
  --pass-debounce-seconds 1.2 `
  --pass-sender-lookback-seconds 6 `
  --pass-receiver-window-seconds 3 `
  --maximum-flyby-speed 500 `
  --minimum-flyby-direction-cosine 0.95 `
  --boundary-events "$window\boundary-events.json" `
  --initial-possession-team black

python -m football_poc.chunk_simulator_cli $manifest `
  --events "$results\predicted-events.json" `
  --output "$results\chunk-simulation.json"

python .\scripts\compare-alfheim-events.py
python .\scripts\render-alfheim-event-crops.py

python -m football_poc.demo_cli `
  --simulation "$results\chunk-simulation.json" `
  --events "$results\predicted-events.json" `
  --output "$page\index.html" `
  --video-source "$results\tracking-verification.mp4" `
  --video-output "$page\tracking-verification.webm" `
  --clip-title "Alfheim 60-second red-versus-black analysis" `
  --team-a red `
  --team-b black `
  --unlabelled-actions `
  --ground-truth-ball `
  --manual-comparison "$results\manual-comparison.json" `
  --manual-review-image-url "..\analytics-data\manual-event-crops.jpg"

Write-Host "Labelled ball: http://localhost:8080/benchmarks/alfheim/window-555/"
Write-Host "Pass analysis: http://localhost:8080/benchmarks/alfheim/window-555/analytics/"
