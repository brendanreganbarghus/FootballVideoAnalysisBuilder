from pathlib import Path


ROOT = Path(__file__).parents[1]
STARTUP = ROOT / "scripts" / "start-innovation-review.ps1"
INSTALLER = ROOT / "scripts" / "install-innovation-review-startup.ps1"


def test_restart_bootstrap_restores_review_dependencies() -> None:
    startup = STARTUP.read_text(encoding="utf-8")

    assert "Docker Desktop.exe" in startup
    assert "docker update --restart unless-stopped" in startup
    assert '$databaseContainer = "postgresql-container"' in startup
    assert "pg_isready -q" in startup
    assert '"FOOTBALL_DATABASE_URL", "User"' in startup
    assert "scripts\\serve-local.py" in startup
    assert "/api/coordination/health" in startup
    assert '$script:health.mode -eq "available"' in startup
    assert "-WindowStyle Hidden" in startup
    assert "Get-CimInstance Win32_Process" in startup
    assert "Stop-Process -Id $listener.OwningProcess" in startup
    assert "function Test-PythonCoordination" in startup
    assert '"import football_poc, psycopg"' in startup


def test_logon_installer_adds_current_repository_bootstrap_to_startup() -> None:
    installer = INSTALLER.read_text(encoding="utf-8")

    assert "start-innovation-review.ps1" in installer
    assert "-RepositoryRoot" in installer
    assert '$configHome = Join-Path $env:LOCALAPPDATA "FootballVideoPOC"' in installer
    assert "[System.IO.File]::WriteAllText" in installer
    assert '"Microsoft\\Windows\\Start Menu\\Programs\\Startup"' in installer
    assert "FootballVideoAnalysisBuilder-InnovationReview.cmd" in installer
    assert "schtasks.exe" not in installer
