param(
    [int]$ApiPort = 8002,
    [int]$WebPort = 5174,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RuntimeDir = Join-Path (Join-Path $RepoRoot "dev") "runtime"
$PidFile = Join-Path $RuntimeDir "dev-up.pids.json"

& (Join-Path $PSScriptRoot "assert-canonical-repo.ps1") -PathToCheck $RepoRoot
function Stop-IfRunning([int]$Pid, [string]$Label) {
    try {
        $proc = Get-Process -Id $Pid -ErrorAction Stop
        Stop-Process -Id $proc.Id -Force:$Force
        Write-Host "Stopped $Label (PID $Pid)" -ForegroundColor Green
    }
    catch {
        Write-Host "$Label PID $Pid is not running." -ForegroundColor DarkYellow
    }
}

function Stop-ByPort([int]$Port) {
    $pids = @()
    try {
        $pids = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
    }
    catch {
        return
    }

    foreach ($pid in $pids) {
        if (-not $pid -or $pid -le 0) {
            continue
        }
        try {
            Stop-Process -Id $pid -Force:$Force -ErrorAction Stop
            Write-Host "Stopped process on port $Port (PID $pid)" -ForegroundColor Green
        }
        catch {
            Write-Host "Could not stop PID $pid on port $Port" -ForegroundColor Yellow
        }
    }
}

if (Test-Path $PidFile) {
    try {
        $state = Get-Content $PidFile -Raw | ConvertFrom-Json
        if ($state.backend_pid) { Stop-IfRunning -Pid ([int]$state.backend_pid) -Label "backend" }
        if ($state.frontend_pid) { Stop-IfRunning -Pid ([int]$state.frontend_pid) -Label "frontend" }
    }
    catch {
        Write-Host "Could not parse pid file. Falling back to port stop." -ForegroundColor Yellow
    }

    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}
else {
    Write-Host "No dev-up pid file found. Falling back to port stop." -ForegroundColor Yellow
}

Stop-ByPort -Port $ApiPort
Stop-ByPort -Port $WebPort

Write-Host "Dev stack stop complete." -ForegroundColor Green

