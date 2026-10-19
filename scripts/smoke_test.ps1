param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [string]$Username = $env:SIAS_ADMIN_USERNAME
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot/auth_session.ps1"

function Invoke-CheckedGet {
    param(
        [string]$Url,
        [hashtable]$Headers = @{}
    )
    $resp = Invoke-RestMethod -Uri $Url -Method GET -WebSession $auth.Session -Headers $Headers
    if (-not $resp.ok) {
        throw "GET failed: $Url"
    }
    Write-Host "[PASS] GET $Url"
    return $resp
}

function Invoke-CheckedPost {
    param(
        [string]$Url,
        [string]$Body = "{}",
        [hashtable]$Headers = @{}
    )
    $resp = Invoke-RestMethod -Uri $Url -Method POST -WebSession $auth.Session -Headers $Headers -Body $Body -ContentType "application/json"
    if (-not $resp.ok) {
        throw "POST failed: $Url"
    }
    Write-Host "[PASS] POST $Url"
    return $resp
}

$root = $BaseUrl.TrimEnd("/")
$auth = if ($Username) { New-SiasSession -Root $root -Username $Username } else { @{ Session = (New-Object Microsoft.PowerShell.Commands.WebRequestSession); Headers = @{} } }
$headers = $auth.Headers

Write-Host "Running SIAS smoke test against: $root"

$health = Invoke-CheckedGet -Url "$root/health"
if ($health.status -ne "healthy") {
    throw "Unexpected /health status: $($health.status)"
}

$ready = Invoke-CheckedGet -Url "$root/ready"
if ($ready.status -ne "ready") {
    throw "Unexpected /ready status: $($ready.status)"
}

if ($Username) {
    $null = Invoke-RestMethod -Uri "$root/api/sensors" -WebSession $auth.Session
    $null = Invoke-RestMethod -Uri "$root/api/plc/status" -WebSession $auth.Session
    $null = Invoke-RestMethod -Uri "$root/api/prediction" -WebSession $auth.Session
    $null = Invoke-CheckedPost -Url "$root/api/plc/start" -Headers $headers
    $null = Invoke-CheckedPost -Url "$root/api/fault/inject" -Headers $headers -Body '{"sensor":"vibration","magnitude":2.0}'
    $null = Invoke-CheckedPost -Url "$root/api/fault/clear" -Headers $headers
}
else {
    Write-Host "[SKIP] Protected API checks (no administrator username provided)"
}

Write-Host "Smoke test completed successfully."
