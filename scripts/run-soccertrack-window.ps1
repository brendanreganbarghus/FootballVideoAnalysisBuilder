param(
    [Parameter(Mandatory = $true)]
    [string]$Manifest,

    [Parameter(Mandatory = $true)]
    [string]$Name
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $projectRoot $Manifest
$modelPath = Join-Path $projectRoot "models\football-players-ball-yolov8.pt"
$modelOutput = Join-Path $projectRoot "benchmarks\$Name-model"
$fusedOutput = Join-Path $projectRoot "benchmarks\$Name-fused"
$cachePath = Join-Path $modelOutput "detections.jsonl"
$ballTracksPath = Join-Path $modelOutput "ball-tracks.json"
$playerTracksPath = Join-Path $fusedOutput "player-tracks.json"

function Invoke-Python {
    param([string[]]$Arguments)
    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: python $($Arguments -join ' ')"
    }
}

Invoke-Python @(
    "-m", "football_poc.benchmark_cli",
    $manifestPath,
    "--output", $modelOutput,
    "--model", $modelPath,
    "--device", "cpu",
    "--stride", "2",
    "--image-size", "960",
    "--confidence", "0.01"
)
Invoke-Python @(
    "-m", "football_poc.ball_tracking_cli",
    $manifestPath,
    "--cache", $cachePath,
    "--output", $modelOutput
)
Invoke-Python @(
    "-m", "football_poc.player_tracking_cli",
    $manifestPath,
    "--player-cache", $cachePath,
    "--ball-tracks", $ballTracksPath,
    "--output", $fusedOutput,
    "--no-video"
)
Invoke-Python @(
    "-m", "football_poc.possession_cli",
    $manifestPath,
    "--player-tracks", $playerTracksPath,
    "--ball-tracks", $ballTracksPath,
    "--output", $fusedOutput
)

Write-Host "Completed SoccerTrack window pipeline: $Name"
