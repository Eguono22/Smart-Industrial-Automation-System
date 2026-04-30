# SIAS Demo Walkthrough

This walkthrough demonstrates the core industrial story: the system detects early bearing wear, escalates to a critical fault, and shows the PLC safety response.

## Setup

Start the app:

```powershell
$env:UV_CACHE_DIR = ".\.uv-cache"
uv run --with-requirements requirements.txt python app.py
```

Open:

```text
http://localhost:5000/dashboard
```

## Live Demo Flow

1. Start on the dashboard and confirm the machine is running with normal sensor status.
2. Under **Scenario Demo**, click **Run**.
3. Watch the phase indicator move through:
   - Healthy baseline
   - Early bearing wear
   - Bearing fault
   - Thermal runaway
   - PLC safety response
4. Switch the trend chart to **Vibration** if it is not already selected.
5. Point out the vibration warning, then critical vibration alarm.
6. Watch temperature/current become critical and the machine status move to stopped.
7. Open **PLC Monitor** and show:
   - Temp OK Switch or Motor Overload opens
   - Motor Run coil turns off
   - Alarm Horn turns on
   - Pressure Relief turns on during the final phase
8. Acknowledge active alarms to demonstrate operator handling.

## Automated Validation

Run the proof script against a local or deployed URL:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo_validation.ps1 -BaseUrl http://localhost:5000
```

For protected deployments:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo_validation.ps1 -BaseUrl https://your-deployment-url -ApiToken "<token>"
```

Expected result:

```text
[PASS] Health endpoint is healthy
[PASS] Demo scenario started: bearing_overheat
[PASS] Healthy baseline observed with motor running
[PASS] Early bearing wear creates vibration warning
[PASS] Bearing fault creates critical vibration alarm
[PASS] Thermal/current trip condition observed
[PASS] PLC interlock de-energised motor run
[PASS] Pressure relief output energised
Demo validation completed successfully.
```

## Success Message

The demo proves SIAS can connect machine telemetry, predictive maintenance signals, PLC safety logic and operator alarm handling into one repeatable workflow.
