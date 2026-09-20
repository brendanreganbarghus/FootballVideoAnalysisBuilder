[CmdletBinding()]
param(
    [string]$RepositoryRoot
)

$ErrorActionPreference = "Stop"
if (-not $RepositoryRoot) {
    $RepositoryRoot = Split-Path `
        -Parent `
        (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$startupScript = Join-Path `
    $RepositoryRoot `
    "scripts\start-innovation-review.ps1"

if (-not (Test-Path -LiteralPath $startupScript)) {
    throw "Startup script not found: $startupScript"
}

$configHome = Join-Path $env:LOCALAPPDATA "FootballVideoPOC"
New-Item -ItemType Directory -Path $configHome -Force | Out-Null
$launcher = Join-Path $configHome "start-innovation-review.ps1"
$escapedStartupScript = $startupScript.Replace("'", "''")
$escapedRepositoryRoot = $RepositoryRoot.Replace("'", "''")
$launcherContent = @"
& '$escapedStartupScript' -RepositoryRoot '$escapedRepositoryRoot'
if (`$LASTEXITCODE -ne 0) { exit `$LASTEXITCODE }
"@
[System.IO.File]::WriteAllText(
    $launcher,
    $launcherContent,
    [System.Text.UTF8Encoding]::new($false)
)

$startupDirectory = Join-Path `
    $env:APPDATA `
    "Microsoft\Windows\Start Menu\Programs\Startup"
New-Item -ItemType Directory -Path $startupDirectory -Force | Out-Null
$startupCommand = Join-Path `
    $startupDirectory `
    "FootballVideoAnalysisBuilder-InnovationReview.cmd"
$commandContent = (
    '@start "" powershell.exe -NoProfile -ExecutionPolicy Bypass ' +
    '-WindowStyle Hidden -File "' + $launcher + '"' +
    [Environment]::NewLine
)
[System.IO.File]::WriteAllText(
    $startupCommand,
    $commandContent,
    [System.Text.ASCIIEncoding]::new()
)

Write-Output "Installed per-user startup command: $startupCommand"
