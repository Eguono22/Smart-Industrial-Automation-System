param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [string]$ApiToken = "",

    [int]$TimeoutSeconds = 120,

    [int]$PollSeconds = 2,

    [string]$ReportPath = "",

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
        [string]$Message,
        [System.Collections.Generic.List[object]]$Events
    )
    if (-not $State[$Key]) {
        $State[$Key] = $true
        Write-Host "[PASS] $Message"
        Add-ReportEvent -Events $Events -Type "pass" -Message $Message -Data @{ check = $Key }
    }
}

function Add-ReportEvent {
    param(
        [System.Collections.Generic.List[object]]$Events,
        [string]$Type,
        [string]$Message,
        [hashtable]$Data = @{}
    )
    $Events.Add([ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        type = $Type
        message = $Message
        data = $Data
    }) | Out-Null
}

function Write-ValidationReport {
    param(
        [string]$Path,
        [bool]$Succeeded,
        [string]$Root,
        [datetime]$StartedAt,
        [hashtable]$Checks,
        [System.Collections.Generic.List[object]]$Events,
        [object]$FinalSnapshot,
        [string]$FailureMessage
    )
    if (-not $Path) {
        return
    }

    $finishedAt = Get-Date
    $reportDir = Split-Path -Parent $Path
    if ($reportDir) {
        New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
    }

    $report = [ordered]@{
        ok = $Succeeded
        base_url = $Root
        started_at = $StartedAt.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        finished_at = $finishedAt.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        duration_seconds = [math]::Round(($finishedAt - $StartedAt).TotalSeconds, 2)
        checks = $Checks
        final_snapshot = $FinalSnapshot
        events = @($Events)
        failure = $FailureMessage
    }

    $report | ConvertTo-Json -Depth 12 | Set-Content -Path $Path -Encoding UTF8
    Write-Host "[INFO] Validation report written to $Path"
}

$root = $BaseUrl.TrimEnd("/")
$headers = New-SiasHeaders
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$startedAt = Get-Date
$events = [System.Collections.Generic.List[object]]::new()
$finalSnapshot = $null
$validationSucceeded = $false
$failureMessage = ""
$checks = @{
    baseline = $false
    vibrationWarning = $false
    vibrationCritical = $false
    thermalTrip = $false
    plcInterlock = $false
    pressureRelief = $false
}

Write-Host "Running SIAS deterministic demo validation against: $root"
Add-ReportEvent -Events $events -Type "start" -Message "Started deterministic demo validation" -Data @{ base_url = $root }

try {
    $health = Invoke-SiasGet -Url "$root/health" -Headers @{}
    Assert-Ok -Response $health -Name "/health"
    if ($health.status -ne "healthy") {
        throw "Unexpected health status: $($health.status)"
    }
    Write-Host "[PASS] Health endpoint is healthy"
    Add-ReportEvent -Events $events -Type "pass" -Message "Health endpoint is healthy" -Data @{ status = $health.status }

    $start = Invoke-SiasPost -Url "$root/api/demo/start" -Headers $headers
    Assert-Ok -Response $start -Name "/api/demo/start"
    Write-Host "[PASS] Demo scenario started: $($start.demo.scenario)"
    Add-ReportEvent -Events $events -Type "pass" -Message "Demo scenario started" -Data @{ scenario = $start.demo.scenario }

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

        $finalSnapshot = [ordered]@{
            demo = $demo.demo
            sensors = [ordered]@{
                vibration = $sensors.vibration
                temperature = $sensors.temperature
                current = $sensors.current
                pressure = $sensors.pressure
            }
            plc = [ordered]@{
                motor_run = $plc.coils.motor_run
                pressure_relief = $plc.coils.pressure_relief
                alarm_horn = $plc.coils.alarm_horn
                temp_sw = $plc.contacts.temp_sw
                motor_overload = $plc.contacts.motor_overload
                active_alarm_count = $plc.active_alarms.Count
            }
            prediction = [ordered]@{
                health_score = $prediction.health_score
                anomaly_score = $prediction.anomaly_score
                rul_label = $prediction.rul_label
                model_trained = $prediction.model_trained
            }
        }

        if ($demo.demo.active -and $sensors.vibration.status -eq "normal" -and $plc.coils.motor_run.state) {
            Mark-PassOnce -State $checks -Key "baseline" -Message "Healthy baseline observed with motor running" -Events $events
        }

        if ($sensors.vibration.status -eq "warning") {
            Mark-PassOnce -State $checks -Key "vibrationWarning" -Message "Early bearing wear creates vibration warning" -Events $events
        }

        if ($sensors.vibration.status -eq "critical") {
            Mark-PassOnce -State $checks -Key "vibrationCritical" -Message "Bearing fault creates critical vibration alarm" -Events $events
        }

        if ($sensors.temperature.status -eq "critical" -or $sensors.current.status -eq "critical") {
            Mark-PassOnce -State $checks -Key "thermalTrip" -Message "Thermal/current trip condition observed" -Events $events
        }

        if (-not $plc.coils.motor_run.state -and (-not $plc.contacts.temp_sw.state -or -not $plc.contacts.motor_overload.state)) {
            Mark-PassOnce -State $checks -Key "plcInterlock" -Message "PLC interlock de-energised motor run" -Events $events
        }

        if ($plc.coils.pressure_relief.state) {
            Mark-PassOnce -State $checks -Key "pressureRelief" -Message "Pressure relief output energised" -Events $events
        }

        if ($prediction.health_score -lt 70) {
            Write-Host "[INFO] Maintenance health degraded to $($prediction.health_score) with RUL $($prediction.rul_label)"
        }

        $missing = @($checks.Keys | Where-Object { -not $checks[$_] })
        if ($missing.Count -eq 0) {
            Write-Host "Demo validation completed successfully."
            Add-ReportEvent -Events $events -Type "success" -Message "Demo validation completed successfully"
            $validationSucceeded = $true
            break
        }

        Start-Sleep -Seconds $PollSeconds
    }

    if (-not $validationSucceeded) {
        $remaining = @($checks.Keys | Where-Object { -not $checks[$_] })
        throw "Demo validation timed out. Missing checks: $($remaining -join ', ')"
    }
}
catch {
    $failureMessage = $_.Exception.Message
    Add-ReportEvent -Events $events -Type "failure" -Message $failureMessage
    throw
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
    Write-ValidationReport `
        -Path $ReportPath `
        -Succeeded $validationSucceeded `
        -Root $root `
        -StartedAt $startedAt `
        -Checks $checks `
        -Events $events `
        -FinalSnapshot $finalSnapshot `
        -FailureMessage $failureMessage
}
