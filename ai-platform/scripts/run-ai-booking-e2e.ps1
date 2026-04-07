param(
    [string]$ApiBase = "http://127.0.0.1:8000/api/v1",
    [string]$FrontendBase = "http://127.0.0.1:5174",
    [string]$Location = "stockholm",
    [string]$ServiceCategory = "hair",
    [string]$ProviderEmail = "provider@example.com",
    [string]$CustomerEmail = "qa.customer@example.com",
    [string]$ChatUserId = "qa_ig_1",
    [string]$CustomerName = "QA Customer",
    [switch]$SkipProviderOtp
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackendDir = Join-Path $RepoRoot "backend"

function Step($message) {
    Write-Host "`n==> $message" -ForegroundColor Cyan
}

function Assert($condition, $message) {
    if (-not $condition) {
        throw $message
    }
}

function PostJson($url, $body, $headers = @{}) {
    $json = $body | ConvertTo-Json -Depth 10
    return Invoke-RestMethod -Method Post -Uri $url -Headers $headers -ContentType "application/json" -Body $json
}

function GetJson($url, $headers = @{}) {
    return Invoke-RestMethod -Method Get -Uri $url -Headers $headers
}

function Resolve-PythonExe() {
    if (Test-Path ".venv\Scripts\python.exe") { return ".venv\Scripts\python.exe" }
    if (Test-Path "venv\Scripts\python.exe") { return "venv\Scripts\python.exe" }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }

    throw "No Python runtime found. Activate a venv or install Python, then retry."
}

try {
    & (Join-Path $PSScriptRoot "assert-canonical-repo.ps1") -PathToCheck $RepoRoot
    $pythonExe = Resolve-PythonExe

    Step "Checking backend health"
    $healthUrl = ($ApiBase -replace "/api/v1$", "") + "/healthz"
    $health = GetJson $healthUrl
    Assert ($health.status -eq "ok") "Backend health check failed at $healthUrl"
    Write-Host "Backend is healthy." -ForegroundColor Green

    Step "Selecting a provider"
    $providersUrl = "$ApiBase/providers/search?location=$Location&service_category=$ServiceCategory"
    $providers = @(GetJson $providersUrl)
    if ($providers.Count -eq 0) {
        Write-Host "No providers found; running demo seed..." -ForegroundColor Yellow
        Push-Location $BackendDir
        try {
            & $pythonExe -m scripts.seed_demo_providers
            if ($LASTEXITCODE -ne 0) {
                throw "Demo seed failed. Run 'cd backend; $pythonExe -m scripts.seed_demo_providers' manually and retry."
            }
        }
        finally {
            Pop-Location
        }
        $providers = @(GetJson $providersUrl)
    }
    Assert ($providers.Count -gt 0) "No providers found for location='$Location' category='$ServiceCategory' even after seeding."
    $provider = $providers[0]
    $providerId = $provider.provider_id
    Write-Host "Provider selected: $($provider.name) ($providerId)" -ForegroundColor Green

    Step "Creating booking via provider chat runtime"
    $effectiveCustomerEmail = $CustomerEmail
    if ($effectiveCustomerEmail -eq "qa.customer@example.com") {
        $stamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $effectiveCustomerEmail = "qa.customer+$stamp@example.com"
    }

    $chatMessage = "Book a haircut tomorrow at 14:00. My email is $effectiveCustomerEmail. My name is $CustomerName."
    $chatResp = PostJson "$ApiBase/chat/provider/message" @{
        provider_id = $providerId
        thread_id = $ChatUserId
        sender_id = $ChatUserId
        message = $chatMessage
    }
    Write-Host "AI reply: $($chatResp.reply)" -ForegroundColor DarkGray
    Step "Checking provider dashboard visibility"
    $providerDashPublic = GetJson "$ApiBase/dashboard/$providerId"
    $providerTodayCount = @($providerDashPublic.bookings_today).Count
    $providerWeekCount = @($providerDashPublic.bookings_week).Count
    Assert (($providerTodayCount + $providerWeekCount) -gt 0) "Provider dashboard has no upcoming bookings"
    Write-Host "Provider upcoming bookings (today/week): $providerTodayCount/$providerWeekCount" -ForegroundColor Green

    if (-not $SkipProviderOtp) {
        Step "Provider auth (OTP dev flow, optional)"
        try {
            $providerSend = PostJson "$ApiBase/auth/provider/send-code" @{ email = $ProviderEmail }
            Assert ($providerSend.dev_code) "Provider dev_code missing. Ensure ENVIRONMENT=development on backend."

            $providerVerify = PostJson "$ApiBase/auth/provider/verify-code" @{
                email = $ProviderEmail
                code = $providerSend.dev_code
            }
            $providerToken = $providerVerify.access_token
            Assert ($providerToken) "Provider token missing"

            $providerHomeDash = GetJson "$ApiBase/home/dashboard" @{ Authorization = "Bearer $providerToken" }
            $providerHomeCount = @($providerHomeDash.upcoming_bookings).Count
            Write-Host "Provider authenticated home bookings: $providerHomeCount" -ForegroundColor Green
        }
        catch {
            Write-Host "Provider OTP flow failed, continuing with public provider dashboard check." -ForegroundColor Yellow
            Write-Host "Reason: $($_.Exception.Message)" -ForegroundColor DarkYellow
        }
    }

    Step "Customer auth using same email captured by AI"
    $customerSend = PostJson "$ApiBase/auth/customer/send-code" @{ email = $effectiveCustomerEmail }
    Assert ($customerSend.dev_code) "Customer dev_code missing. Ensure ENVIRONMENT=development on backend."

    $customerVerify = PostJson "$ApiBase/auth/customer/verify-code" @{
        email = $effectiveCustomerEmail
        code = $customerSend.dev_code
    }
    $customerToken = $customerVerify.access_token
    Assert ($customerToken) "Customer token missing"

    Step "Checking customer homepage dashboard data"
    $customerDash = GetJson "$ApiBase/customer/me/dashboard" @{ Authorization = "Bearer $customerToken" }
    $customerUpcoming = @($customerDash.upcoming_bookings).Count
    Assert ($customerUpcoming -gt 0) "Customer homepage has no upcoming bookings"
    Write-Host "Customer upcoming bookings: $customerUpcoming" -ForegroundColor Green

    Step "Flow summary"
    Write-Host "PASS: AI booking flow end-to-end is working." -ForegroundColor Green
    Write-Host "Provider homepage: $FrontendBase/provider/home"
    Write-Host "Customer homepage: $FrontendBase/customer/home"
    Write-Host "Provider ID used: $providerId"
    Write-Host "Customer email used: $effectiveCustomerEmail"
    exit 0
}
catch {
    Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
