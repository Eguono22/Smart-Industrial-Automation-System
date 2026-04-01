param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [string]$ApiToken = ""
)

$ErrorActionPreference = "Stop"

function Invoke-CheckedGet {
    param(
        [string]$Url,
        [hashtable]$Headers = @{}
    )
    $resp = Invoke-RestMethod -Uri $Url -Method GET -Headers $Headers
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
    $resp = Invoke-RestMethod -Uri $Url -Method POST -Headers $Headers -Body $Body -ContentType "application/json"
    if (-not $resp.ok) {
        throw "POST failed: $Url"
    }
    Write-Host "[PASS] POST $Url"
    return $resp
}

$root = $BaseUrl.TrimEnd("/")
$headers = @{}
if ($ApiToken) {
    $headers["X-API-Key"] = $ApiToken
}

Write-Host "Running SIAS smoke test against: $root"

$health = Invoke-CheckedGet -Url "$root/health"
if ($health.status -ne "healthy") {
    throw "Unexpected /health status: $($health.status)"
}

$ready = Invoke-CheckedGet -Url "$root/ready"
if ($ready.status -ne "ready") {
    throw "Unexpected /ready status: $($ready.status)"
}

$null = Invoke-CheckedGet -Url "$root/api/sensors"
$null = Invoke-CheckedGet -Url "$root/api/plc/status"
$null = Invoke-CheckedGet -Url "$root/api/prediction"

if ($ApiToken) {
    $null = Invoke-CheckedPost -Url "$root/api/plc/start" -Headers $headers
    $null = Invoke-CheckedPost -Url "$root/api/fault/inject" -Headers $headers -Body '{"sensor":"vibration","magnitude":2.0}'
    $null = Invoke-CheckedPost -Url "$root/api/fault/clear" -Headers $headers
}
else {
    Write-Host "[SKIP] POST checks (no ApiToken provided)"
}

Write-Host "Smoke test completed successfully."
