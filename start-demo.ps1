# Starts the local ClinCase demo (Postgres in Docker, backend on :8000, frontend on :5173)
# and opens the sign-in page. Safe to re-run: anything already running is left alone.
$root = $PSScriptRoot
$backendHealth = "http://127.0.0.1:8000/api/v1/healthz"
$frontendRoot = "http://127.0.0.1:5173/"

function Test-Url([string]$url) {
    try { return (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch { return $false }
}

function Test-Docker {
    cmd /c "docker info >nul 2>&1"
    return $LASTEXITCODE -eq 0
}

function Wait-For([string]$what, [int]$seconds, [scriptblock]$check) {
    Write-Host "Waiting for $what" -NoNewline
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        if (& $check) { Write-Host " - ready"; return }
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }
    Write-Host ""
    throw "$what did not come up within $seconds seconds."
}

function Start-Window([string]$title, [string]$dir, [string]$command) {
    $ps = "`$host.UI.RawUI.WindowTitle='$title'; Set-Location '$dir'; $command"
    Start-Process powershell -ArgumentList "-NoExit -NoProfile -Command $ps" -WindowStyle Minimized
}

try {
    if (-not (Test-Docker)) {
        Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        Wait-For "Docker Desktop" 180 { Test-Docker }
    }

    cmd /c "docker compose -f `"$root\docker-compose.yml`" up -d postgres"
    Wait-For "Postgres" 60 { (cmd /c "docker inspect --format={{.State.Health.Status}} clincase-postgres 2>nul") -eq "healthy" }

    if (-not (Test-Url $backendHealth)) {
        Start-Window "ClinCase backend (keep open)" "$root\backend" "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
        Wait-For "backend on port 8000" 120 { Test-Url $backendHealth }
    }

    if (-not (Test-Url $frontendRoot)) {
        if (-not (Test-Path "$root\frontend\node_modules")) {
            cmd /c "cd /d `"$root\frontend`" && npm ci"
        }
        Start-Window "ClinCase frontend (keep open)" "$root\frontend" "npm run dev"
        Wait-For "frontend on port 5173" 90 { Test-Url $frontendRoot }
    }

    Start-Process "${frontendRoot}login"
    Write-Host ""
    Write-Host "ClinCase is running at ${frontendRoot}login"
    Write-Host "Click a demo account to sign in (password: clincase2026)."
} catch {
    Write-Host ""
    Write-Host "Startup failed: $_" -ForegroundColor Red
    exit 1
}
