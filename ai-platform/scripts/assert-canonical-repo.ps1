param(
    [string]$PathToCheck = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $PathToCheck) {
    $PathToCheck = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$normalized = $PathToCheck.Replace("/", "\")
if ($normalized -match "\\\.claude\\worktrees\\" -or $normalized -match "\\\.codex\\") {
    throw "Refusing to run from AI tool worktree path: $PathToCheck. Use canonical AI-Platform repo root."
}

$backendDir = Join-Path $PathToCheck "backend"
$frontendDir = Join-Path $PathToCheck "frontend"
if (-not (Test-Path $backendDir) -or -not (Test-Path $frontendDir)) {
    throw "Invalid repo root: $PathToCheck. Expected backend/ and frontend/ directories."
}

$gitDir = Join-Path $PathToCheck ".git"
if (-not (Test-Path $gitDir)) {
    throw "Invalid repo root: $PathToCheck. Missing .git directory."
}

$branch = (git -C $PathToCheck branch --show-current 2>$null).Trim()
if ($branch) {
    if ($branch -match "(^|/)(codex|claude)(/|$)" -or $branch -match "worktree") {
        throw "Refusing to run app from branch '$branch'. Switch to a production branch."
    }
}

Write-Host "Repo guard passed: $PathToCheck" -ForegroundColor Green

