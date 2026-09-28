# One-time developer environment setup for FootballVideoAnalysisBuilder.
#
# Sets the user-level environment variables required by the application:
#   FOOTBALL_ARTIFACT_ROOT        shared "Innovationday Artifacts" OneDrive folder
#   FOOTBALL_ALFHEIM_PANO         Alfheim panorama folder under the artifact root
#   FOOTBALL_COORDINATION_CONFIG  per-user copy of config\coordination.example.json
#   FOOTBALL_DATABASE_URL         secret PostgreSQL URL (prompted, never stored in Git)
#
# Usage (from the repository root):
#   .\scripts\setup-dev-env.ps1
#
# The database URL is supplied by the coordination administrator through the
# approved Xebia secret-sharing channel. This script never writes it to disk
# inside the repository.

[CmdletBinding()]
param(
    # Override auto-detection of the shared OneDrive artifact folder.
    [string]$ArtifactRoot,
    # Skip the database URL prompt (leave any existing value unchanged).
    [switch]$SkipDatabaseUrl
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Set-UserEnv {
    param([string]$Name, [string]$Value)
    [Environment]::SetEnvironmentVariable($Name, $Value, "User")
    Set-Item -Path "Env:$Name" -Value $Value
    Write-Host "  $Name = $Value"
}

Write-Host "== Football Video Analysis Builder: developer environment setup ==" `
    -ForegroundColor Cyan

# 1. Locate the shared "Innovationday Artifacts" OneDrive folder. All
#    developers use the same shared folder (owned by the coordination
#    administrator); only the local sync path differs per machine.
if (-not $ArtifactRoot) {
    $candidates = @()
    foreach ($base in @($env:OneDriveCommercial, $env:OneDrive)) {
        if ($base) {
            $candidates += (Join-Path $base "Innovationday Artifacts")
        }
    }
    # SharePoint-style sync places shared libraries under %USERPROFILE%\<org>.
    $candidates += (Join-Path $env:USERPROFILE "Xebia\Innovationday Artifacts")
    # Fall back to a shallow search for a shortcut synced under another name.
    foreach ($base in @($env:OneDriveCommercial, $env:OneDrive)) {
        if ($base -and (Test-Path $base)) {
            $candidates += Get-ChildItem $base -Directory -Depth 1 `
                -Filter "*Innovationday Artifacts*" -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty FullName
        }
    }
    $ArtifactRoot = $candidates |
        Where-Object { $_ -and (Test-Path $_) } |
        Select-Object -First 1
}
if (-not $ArtifactRoot -or -not (Test-Path $ArtifactRoot)) {
    throw ("Could not find the shared 'Innovationday Artifacts' folder in " +
        "your OneDrive. Accept the OneDrive share from the coordination " +
        "administrator, sync it locally, then re-run with " +
        "-ArtifactRoot '<path>' if it lives somewhere non-standard.")
}

Write-Host "`nSetting user environment variables:" -ForegroundColor Cyan
Set-UserEnv "FOOTBALL_ARTIFACT_ROOT" $ArtifactRoot
Set-UserEnv "FOOTBALL_ALFHEIM_PANO" `
    (Join-Path $ArtifactRoot "10-master-data\alfheim\pano")

# 2. Per-user coordination profile (non-secret) copied outside the repository.
$configHome = Join-Path $env:LOCALAPPDATA "FootballVideoPOC"
New-Item -ItemType Directory -Path $configHome -Force | Out-Null
$coordinationConfig = Join-Path $configHome "coordination.json"
if (-not (Test-Path $coordinationConfig)) {
    Copy-Item (Join-Path $repoRoot "config\coordination.example.json") `
        $coordinationConfig
    Write-Host "  Copied coordination.example.json -> $coordinationConfig"
} else {
    Write-Host "  Keeping existing $coordinationConfig"
}
Set-UserEnv "FOOTBALL_COORDINATION_CONFIG" $coordinationConfig

# 3. Secret database URL (prompted; never committed).
if (-not $SkipDatabaseUrl) {
    $existing = [Environment]::GetEnvironmentVariable(
        "FOOTBALL_DATABASE_URL", "User")
    $prompt = "Paste the FOOTBALL_DATABASE_URL from the coordination " +
        "administrator"
    if ($existing) {
        $prompt += " (Enter to keep the existing value)"
    }
    $secure = Read-Host -Prompt $prompt -AsSecureString
    $url = [System.Net.NetworkCredential]::new("", $secure).Password
    if ($url) {
        Set-UserEnv "FOOTBALL_DATABASE_URL" $url | Out-Null
        Write-Host "  FOOTBALL_DATABASE_URL = (set, hidden)"
    } elseif ($existing) {
        Write-Host "  FOOTBALL_DATABASE_URL unchanged"
    } else {
        Write-Warning ("FOOTBALL_DATABASE_URL was not provided. Shared " +
            "PostgreSQL coordination will be unavailable until it is set.")
    }
}

Write-Host "`nDone. Open a NEW terminal so the variables are visible, then:" `
    -ForegroundColor Green
Write-Host "  python .\scripts\serve-local.py --bind 127.0.0.1 --port 8080"
