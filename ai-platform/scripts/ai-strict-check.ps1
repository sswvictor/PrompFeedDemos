param(
    [switch]$SkipPython,
    [switch]$SkipFrontend,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

function Say($msg) {
    if (-not $Quiet) { Write-Host $msg }
}

function Warn($msg) {
    Write-Host "WARN: $msg" -ForegroundColor Yellow
}

function Fail($msg) {
    Write-Host "FAIL: $msg" -ForegroundColor Red
    exit 1
}

Say "== AI Strict Check =="

$repoGuard = Join-Path $PSScriptRoot "assert-canonical-repo.ps1"
if (Test-Path $repoGuard) {
    try {
        & $repoGuard
    } catch {
        Fail $_.Exception.Message
    }
}

$issues = @()
$warnings = @()

# 1) Git state snapshot
try {
    $status = git status --porcelain
    $count = ($status | Measure-Object).Count
    Say "Changed entries: $count"
    if ($count -gt 40) {
        $warnings += "Large working set ($count). High merge-risk for parallel AI edits."
    }
} catch {
    $warnings += "Could not read git status."
}

# 2) Merge marker scan
$markersText = ""
try {
    $markersText = git grep -n -E "^(<<<<<<<|=======|>>>>>>>)" -- "*.py" "*.js" "*.jsx" "*.ts" "*.tsx" "*.md"
    if ($LASTEXITCODE -ne 0) { $markersText = "" }
} catch {
    $markersText = ""
}
if ($markersText) {
    $issues += "Merge markers found in source files."
}

# 3) Provider shell contract (stable UX)
function Read-RawOrIssue($path, $label) {
    if (-not (Test-Path $path)) {
        $script:issues += "$label missing: $path"
        return $null
    }
    return Get-Content -Raw -Path $path
}

$routeCatalog = Read-RawOrIssue 'frontend/web/src/app/routeCatalog.js' 'Route catalog'
$providerTabBar = Read-RawOrIssue 'frontend/web/src/personas/provider/navigation/ProviderTabBar.jsx' 'Provider tab bar'
$appRouter = Read-RawOrIssue 'frontend/web/src/App.jsx' 'App router'
$providerProfile = Read-RawOrIssue 'frontend/web/src/personas/provider/profile/ProviderProfilePage.jsx' 'Provider profile page'

if ($routeCatalog) {
    foreach ($routeKey in @('home', 'finance', 'profile')) {
        if ($routeCatalog -notmatch "provider:\s*\{[\s\S]*${routeKey}:\s*'/provider/${routeKey}'") {
            $issues += "Provider route missing or changed: /provider/${routeKey}"
        }
    }
}

if ($providerTabBar) {
    $ids = [regex]::Matches($providerTabBar, "id:\s*'([^']+)'") | ForEach-Object { $_.Groups[1].Value }
    foreach ($id in @('home', 'finance', 'profile')) {
        if ($ids -notcontains $id) {
            $issues += "Provider tab bar missing tab id '$id'."
        }
    }
    if ($ids.Count -ne 3) {
        $issues += "Provider tab bar must have exactly 3 tabs (home, finance, profile)."
    }
}

if ($appRouter) {
    if ($appRouter -notmatch "import ProviderFinancePage from './personas/provider/home/ProviderFinancePage';") {
        $issues += 'ProviderFinancePage import missing in App.jsx.'
    }
    if ($appRouter -notmatch 'ROUTES\.provider\.home[\s\S]*<ProviderHomePage\s*/>') {
        $issues += 'App route mapping missing for /provider/home -> ProviderHomePage.'
    }
    if ($appRouter -notmatch 'ROUTES\.provider\.finance[\s\S]*<ProviderFinancePage\s*/>') {
        $issues += 'App route mapping missing for /provider/finance -> ProviderFinancePage.'
    }
    if ($appRouter -notmatch 'ROUTES\.provider\.profile[\s\S]*<ProviderProfilePage\s*/>') {
        $issues += 'App route mapping missing for /provider/profile -> ProviderProfilePage.'
    }
}

if ($providerProfile) {
    if ($providerProfile -notmatch 'function TabRow') {
        $issues += 'ProviderProfilePage must keep the Instagram-style middle tab row (TabRow).'
    }
    if ($providerProfile -notmatch '<TabRow') {
        $issues += 'ProviderProfilePage is not rendering TabRow.'
    }
}

# 4) Resolve Python executable
$pythonExe = $null
if (-not $SkipPython) {
    if (Test-Path '.venv\Scripts\python.exe') { $pythonExe = '.venv\Scripts\python.exe' }
    elseif (Test-Path 'venv\Scripts\python.exe') { $pythonExe = 'venv\Scripts\python.exe' }
    else {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) { $pythonExe = $cmd.Source }
    }
}

if (-not $SkipPython) {
    if (-not $pythonExe) {
        $warnings += 'Python executable not found in this shell context; skipped runtime checks.'
    } else {
        Say "Using Python: $pythonExe"

        # 5) Compile backend package
        Push-Location backend
        try {
            & $pythonExe -m compileall app 1>$null
            if ($LASTEXITCODE -ne 0) {
                $issues += 'Python compileall failed for app/.'
            }

            # 6) Import smoke for critical modules
            & $pythonExe -c "import importlib; mods=['app.orchestrators.base','app.orchestrators.tools','app.api.routes']; [importlib.import_module(m) for m in mods]; print('import-ok')" 1>$null
            if ($LASTEXITCODE -ne 0) {
                $issues += 'Python import smoke failed for critical modules.'
            }
        } finally {
            Pop-Location
        }
    }
}

# 7) Optional frontend smoke
if (-not $SkipFrontend) {
    if (Test-Path 'frontend\package.json') {
        $npm = Get-Command npm -ErrorAction SilentlyContinue
        if ($npm) {
            Push-Location frontend\\web
            try {
                if (Test-Path 'node_modules') {
                    npm run -s build 1>$null
                    if ($LASTEXITCODE -ne 0) {
                        $warnings += 'Frontend build check failed (npm run build).'
                    }
                } else {
                    $warnings += 'frontend/web/node_modules missing; skipped frontend build check.'
                }
            } finally {
                Pop-Location
            }
        } else {
            $warnings += 'npm not available; skipped frontend check.'
        }
    }
}

# 8) Report
if ($warnings.Count -gt 0) {
    foreach ($w in $warnings) { Warn $w }
}
if ($issues.Count -gt 0) {
    foreach ($i in $issues) { Write-Host "ISSUE: $i" -ForegroundColor Red }
    Fail 'AI strict check failed.'
}

Say 'PASS: AI strict check completed.'
exit 0
