param(
    [int]$ApiPort = 8002,
    [int]$WebPort = 5174,
    [string]$BindHost = "127.0.0.1",
    [switch]$SkipMigrations,
    [switch]$SkipFrontendInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$LogsDir = Join-Path $RepoRoot "logs"
$RuntimeDir = Join-Path (Join-Path $RepoRoot "dev") "runtime"
$PidFile = Join-Path $RuntimeDir "dev-up.pids.json"

function Step($message) {
    Write-Host "`n==> $message" -ForegroundColor Cyan
}

function Resolve-PythonExe() {
    if (Test-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")) { return (Join-Path $RepoRoot ".venv\Scripts\python.exe") }
    if (Test-Path (Join-Path $RepoRoot "venv\Scripts\python.exe")) { return (Join-Path $RepoRoot "venv\Scripts\python.exe") }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return "$($py.Source) -3" }

    throw "No Python runtime found. Create/activate a venv and retry."
}

function Is-Running([int]$Pid) {
    try {
        Get-Process -Id $Pid -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
& (Join-Path $PSScriptRoot "assert-canonical-repo.ps1") -PathToCheck $RepoRoot

if (Test-Path $PidFile) {
    try {
        $existing = Get-Content $PidFile -Raw | ConvertFrom-Json
        $backendUp = $existing.backend_pid -and (Is-Running -Pid ([int]$existing.backend_pid))
        $frontendUp = $existing.frontend_pid -and (Is-Running -Pid ([int]$existing.frontend_pid))
        if ($backendUp -or $frontendUp) {
            throw "dev-up appears to already be running. Run scripts\dev-down.ps1 first."
        }
    }
    catch {
        Write-Host "Cleaning stale pid file: $PidFile" -ForegroundColor Yellow
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

$pythonExe = Resolve-PythonExe

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "npm.cmd not found. Install Node.js and retry."
}

if (-not $SkipMigrations) {
    Step "Bootstrapping database schema"
    Push-Location $BackendDir
    try {
        if ($pythonExe -match " -3$") {
            & py -3 -m app.db.bootstrap
        }
        else {
            & $pythonExe -m app.db.bootstrap
        }
        if ($LASTEXITCODE -ne 0) {
            throw "database bootstrap failed"
        }
    }
    finally {
        Pop-Location
    }
}

if (-not $SkipFrontendInstall -and -not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Step "Installing frontend dependencies (npm ci)"
    Push-Location $FrontendDir
    try {
        npm.cmd ci
        if ($LASTEXITCODE -ne 0) {
            throw "npm ci failed"
        }
    }
    finally {
        Pop-Location
    }
}

$BackendLog = Join-Path $LogsDir "backend-dev.log"
$BackendErr = Join-Path $LogsDir "backend-dev.err.log"
$FrontendLog = Join-Path $LogsDir "frontend-dev.log"
$FrontendErr = Join-Path $LogsDir "frontend-dev.err.log"

Set-Content -Path $BackendLog -Value ""
Set-Content -Path $BackendErr -Value ""
Set-Content -Path $FrontendLog -Value ""
Set-Content -Path $FrontendErr -Value ""

$backendPyCmd = if ($pythonExe -match " -3$") {
    "py -3 -m uvicorn app.main:app --reload --host $BindHost --port $ApiPort"
}
else {
    "`"$pythonExe`" -m uvicorn app.main:app --reload --host $BindHost --port $ApiPort"
}

$BackendCmd = "cd /d `"$BackendDir`" && $backendPyCmd"
$FrontendCmd = "cd /d `"$FrontendDir`" && set VITE_API_TARGET=http://$BindHost`:$ApiPort && npm.cmd run dev -- --host $BindHost --port $WebPort"

Step "Starting backend"
$backendProc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $BackendCmd -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendErr -PassThru

Start-Sleep -Seconds 2

Step "Starting frontend"
$frontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $FrontendCmd -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendErr -PassThru

$runtimeState = [ordered]@{
    started_at = (Get-Date).ToString("s")
    host = $BindHost
    api_port = $ApiPort
    web_port = $WebPort
    backend_pid = $backendProc.Id
    frontend_pid = $frontendProc.Id
    backend_log = $BackendLog
    backend_error_log = $BackendErr
    frontend_log = $FrontendLog
    frontend_error_log = $FrontendErr
}
$runtimeState | ConvertTo-Json | Set-Content $PidFile

Step "Waiting for backend health"
$healthOk = $false
for ($i = 0; $i -lt 25; $i++) {
    try {
        $health = Invoke-RestMethod -Method Get -Uri "http://$BindHost`:$ApiPort/healthz" -TimeoutSec 2
        if ($health.status -eq "ok") {
            $healthOk = $true
            break
        }
    }
    catch {
    }
    Start-Sleep -Seconds 1
}

if ($healthOk) {
    Write-Host "Backend is healthy." -ForegroundColor Green
}
else {
    Write-Host "Backend health check timed out. Check logs:" -ForegroundColor Yellow
    Write-Host "- $BackendLog"
    Write-Host "- $BackendErr"
}

Step "Dev stack started"
Write-Host "API:      http://$BindHost`:$ApiPort"
Write-Host "Frontend: http://$BindHost`:$WebPort"
Write-Host "PID file: $PidFile"
Write-Host "Stop with: powershell -ExecutionPolicy Bypass -File scripts\dev-down.ps1"

