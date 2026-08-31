$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$destination = Join-Path $projectRoot "models\football-players-ball-yolov8.pt"
$expectedHash = "844E9AD1EBAFBD0C07F066E45AA87D9B87595DD9092DFEE9CAC3B10A6A5FA730"
$url = "https://huggingface.co/uisikdag/yolo-v8-football-players-detection/resolve/main/best.pt"

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) |
    Out-Null
if (-not (Test-Path -LiteralPath $destination)) {
    Write-Host "Downloading benchmark-only football detector..."
    curl.exe -L --fail --silent --show-error $url -o $destination
    if ($LASTEXITCODE -ne 0) {
        throw "Download failed: $url"
    }
}

$actualHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
if ($actualHash -ne $expectedHash) {
    throw "Model checksum mismatch. Expected $expectedHash, got $actualHash"
}

Write-Host "Verified model: $destination"
Write-Warning (
    "The model card does not declare a license or training-data provenance. " +
    "Use this checkpoint for internal benchmarking only."
)
