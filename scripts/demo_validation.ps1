param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [string]$ApiToken = "",

    [int]$TimeoutSeconds = 120,

    [int]$PollSeconds = 2,

    [switch]$LeaveRunning
)

$ErrorActionPreference = "Stop"

function New-SiasHeaders {
    $headers = @{}
    if ($ApiToken) {
        $headers["X-API-Key"] = $ApiToken
    }
    return $headers
}

function Invoke-SiasGet {
    param(
        [string]$Url,
        [hashtable]$Headers
    )
    return Invoke-RestMethod -Uri $Url -Method GET -Headers $Headers
}

function Invoke-SiasPost {
    param(
        [string]$Url,
        [hashtable]$Headers
    )
    return Invoke-RestMethod -Uri $Url -Method POST -Headers $Headers -Body "{}" -ContentType "application/json"
}

function Assert-Ok {
    param(
        [object]$Response,
        [string]$Name
    )
    if (-not $Response.ok) {
        throw "$Name returned ok=false"
    }
}

function Mark-PassOnce {
    param(
        [hashtable]$State,
        [string]$Key,
        [string]$Message
    )
    if (-not $State[$Key]) {
        $State[$Key] = $true
        Write-Host "[PASS] $Message"
    }
}

$root = $BaseUrl.TrimEnd("/")
$headers = New-SiasHeaders
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$checks = @{
    baseline = $false
    vibrationWarning = $false
    vibrationCritical = $false
    thermalTrip = $false
    plcInterlock = $false
    pressureRelief = $false
}

Write-Host "Running SIAS deterministic demo validation against: $root"

try {
    $health = Invoke-SiasGet -Url "$root/health" -Headers @{}
    Assert-Ok -Response $health -Name "/health"
    if ($health.status -ne "healthy") {
        throw "Unexpected health status: $($health.status)"
    }
    Write-Host "[PASS] Health endpoint is healthy"

    $start = Invoke-SiasPost -Url "$root/api/demo/start" -Headers $headers
    Assert-Ok -Response $start -Name "/api/demo/start"
    Write-Host "[PASS] Demo scenario started: $($start.demo.scenario)"

    while ((Get-Date) -lt $deadline) {
        $demo = Invoke-SiasGet -Url "$root/api/demo/status" -Headers @{}
        $sensors = Invoke-SiasGet -Url "$root/api/sensors" -Headers @{}
        $plc = Invoke-SiasGet -Url "$root/api/plc/status" -Headers @{}
        $prediction = Invoke-SiasGet -Url "$root/api/prediction" -Headers @{}

        Assert-Ok -Response $demo -Name "/api/demo/status"

        $phase = $demo.demo.phase
        $progress = $demo.demo.progress_percent
        Write-Host ("[{0,5}%] {1,-20} vib={2,-8} temp={3,-8} current={4,-8} motor={5}" -f `
            $progress,
            $phase,
            $sensors.vibration.status,
            $sensors.temperature.status,
            $sensors.current.status,
            $plc.coils.motor_run.state)

        if ($demo.demo.active -and $sensors.vibration.status -eq "normal" -and $plc.coils.motor_run.state) {
            Mark-PassOnce -State $checks -Key "baseline" -Message "Healthy baseline observed with motor running"
        }

        if ($sensors.vibration.status -eq "warning") {
            Mark-PassOnce -State $checks -Key "vibrationWarning" -Message "Early bearing wear creates vibration warning"
        }

        if ($sensors.vibration.status -eq "critical") {
            Mark-PassOnce -State $checks -Key "vibrationCritical" -Message "Bearing fault creates critical vibration alarm"
        }

        if ($sensors.temperature.status -eq "critical" -or $sensors.current.status -eq "critical") {
            Mark-PassOnce -State $checks -Key "thermalTrip" -Message "Thermal/current trip condition observed"
        }

        if (-not $plc.coils.motor_run.state -and (-not $plc.contacts.temp_sw.state -or -not $plc.contacts.motor_overload.state)) {
            Mark-PassOnce -State $checks -Key "plcInterlock" -Message "PLC interlock de-energised motor run"
        }

        if ($plc.coils.pressure_relief.state) {
            Mark-PassOnce -State $checks -Key "pressureRelief" -Message "Pressure relief output energised"
        }

        if ($prediction.health_score -lt 70) {
            Write-Host "[INFO] Maintenance health degraded to $($prediction.health_score) with RUL $($prediction.rul_label)"
        }

        $missing = @($checks.Keys | Where-Object { -not $checks[$_] })
        if ($missing.Count -eq 0) {
            Write-Host "Demo validation completed successfully."
            return
        }

        Start-Sleep -Seconds $PollSeconds
    }

    $remaining = @($checks.Keys | Where-Object { -not $checks[$_] })
    throw "Demo validation timed out. Missing checks: $($remaining -join ', ')"
}
finally {
    if (-not $LeaveRunning) {
        try {
            $null = Invoke-SiasPost -Url "$root/api/demo/stop" -Headers $headers
            Write-Host "[INFO] Demo scenario stopped"
        }
        catch {
            Write-Host "[WARN] Unable to stop demo scenario: $($_.Exception.Message)"
        }
    }
}
