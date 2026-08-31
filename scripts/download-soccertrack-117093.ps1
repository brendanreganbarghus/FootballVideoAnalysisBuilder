param(
    [ValidateSet("annotations", "first", "second", "both")]
    [string]$Content = "annotations"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$datasetRoot = Join-Path $projectRoot "data\soccertrack-v2"

python -c "import gdown" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'gdown is required. Run: python -m pip install -e ".[dataset]"'
}

$files = @(
    @{
        Kind = "annotations"
        Id = "1IkpBlr7-i8C0CxrGzq0r4CJ44Yiazf4v"
        Path = "bas\117093\117093_12_class_events.json"
    },
    @{
        Kind = "first"
        Id = "1gPoN2h2SxEjWORK6FwKTEsCuKPylar53"
        Path = "videos\117093\117093_panorama_1st_half.mp4"
    },
    @{
        Kind = "second"
        Id = "1dJNSKYtiuynakFDO7Hj7dCp7yjb2iMXy"
        Path = "videos\117093\117093_panorama_2nd_half.mp4"
    }
)

$selected = $files | Where-Object {
    $_.Kind -eq "annotations" -or
    $Content -eq "both" -or
    $_.Kind -eq $Content
}

foreach ($file in $selected) {
    $destination = Join-Path $datasetRoot $file.Path
    if (Test-Path -LiteralPath $destination) {
        Write-Host "Already downloaded: $destination"
        continue
    }

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) |
        Out-Null
    Write-Host "Downloading $($file.Path)..."
    python -m gdown "https://drive.google.com/uc?id=$($file.Id)" -O $destination
    if ($LASTEXITCODE -ne 0) {
        throw "Download failed: $($file.Path)"
    }
}

Write-Host "SoccerTrack files are under $datasetRoot"
