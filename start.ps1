<#
    start.ps1 - one-command startup for the Nightingale stack (Windows / PowerShell).

    What it does, in order:
      0. If -Bootstrap is passed: create the .venv (if missing), pip install the
         Python deps, and npm install the frontend deps. Run this once on a fresh
         machine (e.g. the demo device).
      1. Verifies Docker is running.
      2. Ensures the postgres + redis containers are up (compose up -d if not),
         then waits for them to be healthy.
      3. Runs `alembic upgrade head` (idempotent - a no-op if already at head).
      4. If -Seed is passed: wipes tenant data and re-seeds the demo dataset.
         Without -Seed: leaves existing data untouched.
      5. Starts the backend (uvicorn) in its own window and waits for :8000.
      6. Starts the frontend (vite dev) in its own window.

    Usage:
      .\start.ps1                      # start everything, keep existing DB data
      .\start.ps1 -Seed                # start + reset+seed the demo dataset
      .\start.ps1 -Bootstrap -Seed     # fresh machine: install deps, then start + seed
#>

[CmdletBinding()]
param(
    [switch]$Seed,
    [switch]$Bootstrap
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

# Names must match docker-compose.yml.
$RequiredContainers = @("postgres_db", "redis_cache")
$BackendUrl = "http://127.0.0.1:8000/openapi.json"
$FrontendDir = Join-Path $ProjectRoot "frontend"

# Prefer the project venv's python if present, else fall back to `python`.
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    OK  $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "    ERR $msg" -ForegroundColor Red }

# -- 0. Bootstrap (fresh machine): create venv + install python/frontend deps --
if ($Bootstrap) {
    Write-Step "Bootstrapping dependencies (-Bootstrap given)"

    if (-not (Test-Path $VenvPython)) {
        Write-Host "    Creating virtualenv at .venv"
        python -m venv (Join-Path $ProjectRoot ".venv")
        if ($LASTEXITCODE -ne 0) { Write-Err "python -m venv failed (is Python on PATH?)."; exit 1 }
    } else {
        Write-Host "    .venv already exists - reusing it"
    }
    # venv now exists: use its python for the rest of the run.
    $Python = $VenvPython

    Write-Host "    Installing Python deps (pip install -r requirements.txt)"
    & $Python -m pip install --upgrade pip | Out-Null
    & $Python -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
    if ($LASTEXITCODE -ne 0) { Write-Err "pip install failed."; exit 1 }

    Write-Host "    Installing frontend deps (npm install)"
    Push-Location $FrontendDir; npm install; $npmExit = $LASTEXITCODE; Pop-Location
    if ($npmExit -ne 0) { Write-Err "npm install failed (is Node installed?)."; exit 1 }

    Write-Ok "Bootstrap complete"
}

# Re-resolve python in case bootstrap just created the venv.
if (Test-Path $VenvPython) { $Python = $VenvPython }

# -- 1. Docker daemon ---------------------------------------------------------
Write-Step "Checking Docker is running"
try {
    docker info --format '{{.ServerVersion}}' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker info failed" }
    Write-Ok "Docker daemon is up"
} catch {
    Write-Err "Docker is not running. Start Docker Desktop and re-run this script."
    exit 1
}

# -- 2. Containers ------------------------------------------------------------
Write-Step "Checking required containers: $($RequiredContainers -join ', ')"
$running = docker ps --format '{{.Names}}'
$missing = $RequiredContainers | Where-Object { $running -notcontains $_ }

if ($missing.Count -gt 0) {
    Write-Host "    Missing: $($missing -join ', ') - bringing them up with docker compose"
    docker compose up -d
    if ($LASTEXITCODE -ne 0) { Write-Err "docker compose up failed."; exit 1 }
}

# Wait for both to report healthy (compose healthchecks are defined).
Write-Host "    Waiting for containers to become healthy..."
foreach ($name in $RequiredContainers) {
    $healthy = $false
    for ($i = 0; $i -lt 30; $i++) {
        $status = docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $name 2>$null
        # containers without a healthcheck report 'none' but are running -> accept
        if ($status -eq "healthy" -or $status -eq "none") { $healthy = $true; break }
        Start-Sleep -Seconds 1
    }
    if ($healthy) { Write-Ok "$name ready" }
    else { Write-Err "$name did not become healthy in time."; exit 1 }
}

# -- 3. Alembic migrations (idempotent) ---------------------------------------
Write-Step "Applying database migrations (alembic upgrade head)"
& $Python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Write-Err "alembic upgrade head failed."; exit 1 }
Write-Ok "Database is at head (no-op if it already was)"

# -- 4. Optional demo seed ----------------------------------------------------
if ($Seed) {
    Write-Step "Seeding demo data (-Seed given): reset + seed"
    & $Python -m src.utils.scripts.reset_tenant_data --yes
    if ($LASTEXITCODE -ne 0) { Write-Err "reset failed."; exit 1 }
    & $Python -m src.utils.scripts.seed_demo_dataset
    if ($LASTEXITCODE -ne 0) { Write-Err "seed failed."; exit 1 }
    Write-Ok "Demo dataset seeded (admin1/admin2, worker1.. all password 'password')"
} else {
    Write-Step "Skipping seed (pass -Seed to reset + load demo data)"
}

# -- 5. Backend in its own window, then wait for it ---------------------------
Write-Step "Starting backend (uvicorn) in a new window"
$backendCmd = "Set-Location '$ProjectRoot'; & '$Python' -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd | Out-Null

Write-Host "    Waiting for backend on :8000..."
$backendUp = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $r = Invoke-WebRequest -Uri $BackendUrl -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $backendUp = $true; break }
    } catch { Start-Sleep -Seconds 1 }
}
if ($backendUp) { Write-Ok "Backend is up at http://127.0.0.1:8000" }
else { Write-Err "Backend did not come up in time - check its window for errors."; exit 1 }

# -- 6. Frontend in its own window --------------------------------------------
Write-Step "Starting frontend (vite) in a new window"
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "    node_modules missing - running npm install first"
    Push-Location $FrontendDir; npm install; Pop-Location
}
$frontendCmd = "Set-Location '$FrontendDir'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd | Out-Null
Write-Ok "Frontend starting (usually http://localhost:5173)"

Write-Host "`n==> Stack is up." -ForegroundColor Cyan
Write-Host "    Backend : http://127.0.0.1:8000  (docs at /docs)"
Write-Host "    Frontend: http://localhost:5173"
Write-Host "    Web login   : admin1 (nurse co) / admin2 (tech co) - password 'password'"
Write-Host "    Mobile login: worker1.. - password 'password'"
Write-Host "    (Each service runs in its own window; close a window to stop it.)"
Write-Host "    Fresh machine? run once: .\start.ps1 -Bootstrap -Seed"
