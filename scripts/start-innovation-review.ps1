[CmdletBinding()]
param(
    [string]$RepositoryRoot,
    [int]$Port = 8080,
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
if (-not $RepositoryRoot) {
    $RepositoryRoot = Split-Path `
        -Parent `
        (Split-Path -Parent $MyInvocation.MyCommand.Path)
}

function Test-DockerReady {
    & docker info --format "{{.ServerVersion}}" 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function Get-CoordinationHealth {
    try {
        return Invoke-RestMethod `
            -Uri "http://127.0.0.1:$Port/api/coordination/health" `
            -TimeoutSec 3
    }
    catch {
        return $null
    }
}

function Test-PythonCoordination {
    param([string]$Python)

    $probe = (
        '"' + $Python + '" -c "import football_poc, psycopg" >nul 2>nul'
    )
    & $env:ComSpec /d /c $probe
    return $LASTEXITCODE -eq 0
}

function Wait-Until {
    param(
        [scriptblock]$Condition,
        [string]$FailureMessage
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (& $Condition) {
            return
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    throw $FailureMessage
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not installed or is not on PATH."
}

if (-not (Test-DockerReady)) {
    $dockerDesktop = Join-Path `
        $env:ProgramFiles `
        "Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path -LiteralPath $dockerDesktop)) {
        throw "Docker Desktop is not running and its executable was not found."
    }
    Start-Process -FilePath $dockerDesktop | Out-Null
    Wait-Until `
        -Condition { Test-DockerReady } `
        -FailureMessage "Docker Desktop did not become ready."
}

$databaseContainer = "postgresql-container"
& docker inspect $databaseContainer 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Required PostgreSQL container '$databaseContainer' does not exist."
}

& docker update --restart unless-stopped $databaseContainer | Out-Null
$databaseRunning = & docker inspect `
    --format "{{.State.Running}}" `
    $databaseContainer
if ($databaseRunning -ne "true") {
    & docker start $databaseContainer | Out-Null
}

Wait-Until `
    -Condition {
        & docker exec $databaseContainer pg_isready -q 2>$null
        return $LASTEXITCODE -eq 0
    } `
    -FailureMessage "PostgreSQL container did not become ready."

$env:FOOTBALL_COORDINATION_CONFIG = `
    [Environment]::GetEnvironmentVariable(
        "FOOTBALL_COORDINATION_CONFIG",
        "User"
    )
$env:FOOTBALL_DATABASE_URL = `
    [Environment]::GetEnvironmentVariable("FOOTBALL_DATABASE_URL", "User")
$env:FOOTBALL_ARTIFACT_ROOT = `
    [Environment]::GetEnvironmentVariable("FOOTBALL_ARTIFACT_ROOT", "User")
$env:PYTHONPATH = Join-Path $RepositoryRoot "src"

if (-not $env:FOOTBALL_COORDINATION_CONFIG) {
    throw "FOOTBALL_COORDINATION_CONFIG is not configured for this user."
}
if (-not $env:FOOTBALL_DATABASE_URL) {
    throw "FOOTBALL_DATABASE_URL is not configured for this user."
}

$health = Get-CoordinationHealth
if ($health -and $health.mode -ne "available") {
    $listener = Get-NetTCPConnection `
        -LocalPort $Port `
        -State Listen `
        -ErrorAction SilentlyContinue |
        Select-Object -First 1
    $process = if ($listener) {
        Get-CimInstance Win32_Process `
            -Filter "ProcessId = $($listener.OwningProcess)"
    }
    $expectedServer = Join-Path $RepositoryRoot "scripts\serve-local.py"
    if (-not $process -or $process.CommandLine -notlike "*$expectedServer*") {
        throw (
            "Port $Port is occupied by a process that is not this " +
            "repository's review server."
        )
    }
    Stop-Process -Id $listener.OwningProcess
    Wait-Until `
        -Condition {
            -not (
                Get-NetTCPConnection `
                    -LocalPort $Port `
                    -State Listen `
                    -ErrorAction SilentlyContinue
            )
        } `
        -FailureMessage "The stale review server did not stop."
    $health = $null
}

if (-not $health) {
    $pythonCandidates = @(
        (Join-Path $RepositoryRoot ".venv\Scripts\python.exe"),
        (Get-Command python -ErrorAction SilentlyContinue).Source
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
        Select-Object -Unique
    $python = $pythonCandidates |
        Where-Object { Test-PythonCoordination $_ } |
        Select-Object -First 1
    if (-not $python) {
        throw (
            "No Python interpreter with football_poc and psycopg support " +
            "is available."
        )
    }

    $logDirectory = Join-Path $env:LOCALAPPDATA "FootballVideoPOC\logs"
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    $stdout = Join-Path $logDirectory "innovation-review-server.log"
    $stderr = Join-Path $logDirectory "innovation-review-server-error.log"
    $arguments = @(
        (Join-Path $RepositoryRoot "scripts\serve-local.py"),
        "--bind", "127.0.0.1",
        "--port", [string]$Port,
        "--directory", $RepositoryRoot
    )
    Start-Process `
        -FilePath $python `
        -ArgumentList $arguments `
        -WorkingDirectory $RepositoryRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr | Out-Null
}

Wait-Until `
    -Condition {
        $script:health = Get-CoordinationHealth
        return $script:health -and $script:health.mode -eq "available"
    } `
    -FailureMessage "Review server did not reach writable coordination mode."

Write-Output (
    "Innovation review environment ready at http://127.0.0.1:$Port " +
    "(authority: $($script:health.deployment.authorityId))."
)
