# Smart Industrial Automation System (SIAS)

Predictive maintenance system for an industrial machine using sensor data and PLC logic.

## Overview

SIAS is a full-stack web application that combines **PLC ladder logic simulation**, **real-time sensor analytics** and an **ML-based anomaly detection engine** to keep industrial machines running safely and efficiently.

## Features

| Area | Details |
|---|---|
| **Sensor Monitoring** | Temperature, Pressure, Vibration, Current, RPM, Oil Level — simulated with realistic drift and noise |
| **PLC Integration** | Built-in simulation plus optional Modbus TCP bridge (`PLC_MODE=modbus`) for real PLC output-coil mirroring |
| **PLC Ladder Logic** | 5 rungs: Motor Run, Coolant Pump, Lube Pump, Pressure Relief, Alarm Horn — with interlocks and safety latches |
| **Predictive ML** | Isolation Forest with rolling-window engineered features, online retraining, drift score and persisted model checkpoint |
| **Live Dashboard** | Real-time sensor gauges, trend charts (Chart.js), health history and anomaly score charts — updated every 2 s via Socket.IO |
| **PLC Monitor** | Ladder rung diagram, input contact and output coil tables, scan-tick counter, alarm log |
| **Maintenance Page** | Health trend, anomaly trend, full sensor status table and complete alarm history |
| **Machine Controls** | Start / Stop / Emergency Stop / Reset E-Stop via REST API |
| **Fault Injection** | Inject or clear artificial sensor faults for demo / testing |
| **Alarm Management** | Per-sensor alarms with priority levels (critical / warning / info) and ACK support |
| **Production Hardening** | API-key protection for mutating endpoints, `/health` + `/ready` + `/metrics`, Dockerfile and GitHub Actions CI |

## Tech Stack

- **Backend** — Python 3.12, Flask 3, Flask-SocketIO (threading mode)
- **ML** — scikit-learn `IsolationForest`, `MinMaxScaler`
- **PLC Bridge** — `pymodbus` (optional; enabled via env vars)
- **Frontend** — Bootstrap 5, Chart.js 4, Socket.IO client (all vendored, no CDN required)
- **Transport** — WebSocket with HTTP polling fallback

## Project Structure

```
├── app.py                  # Flask application & REST/WebSocket endpoints
├── requirements.txt
├── app/
│   ├── models/
│   │   ├── sensor.py       # Sensor simulator (6 sensors, fault injection)
│   │   ├── plc.py          # PLC ladder-logic, alarm management
│   │   ├── plc_adapter.py  # Simulation + Modbus PLC integration adapter
│   │   └── predictor.py    # Predictive engine + model persistence + drift
│   ├── templates/
│   │   ├── base.html       # Shared navbar + script includes
│   │   ├── index.html      # Landing page
│   │   ├── dashboard.html  # Live monitoring dashboard
│   │   ├── plc_monitor.html# PLC ladder logic viewer
│   │   └── maintenance.html# Predictive maintenance page
│   └── static/
│       ├── css/style.css
│       ├── js/dashboard.js
│       ├── js/plc_monitor.js
│       ├── js/maintenance.js
│       └── vendor/         # Bootstrap, Chart.js, Socket.IO (no CDN)
└── tests/
    └── test_core.py        # 44 unit tests (pytest)
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the application
python app.py

# 3. Open browser
open http://localhost:5000
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PLC_MODE` | `sim` | `sim` for software PLC, `modbus` for Modbus bridge |
| `PLC_HOST` | `127.0.0.1` | Modbus PLC host |
| `PLC_PORT` | `502` | Modbus PLC TCP port |
| `PLC_UNIT_ID` | `1` | Modbus unit/slave id |
| `PLC_COIL_MOTOR_RUN` | `0` | Modbus coil address for `motor_run` |
| `PLC_COIL_PUMP_RUN` | `1` | Modbus coil address for `pump_run` |
| `PLC_COIL_ALARM_HORN` | `2` | Modbus coil address for `alarm_horn` |
| `PLC_COIL_ESTOP_LATCH` | `3` | Modbus coil address for `estop_latch` |
| `PLC_COIL_PRESSURE_RELIEF` | `4` | Modbus coil address for `pressure_relief` |
| `PLC_COIL_LUBE_PUMP` | `5` | Modbus coil address for `lube_pump` |
| `SIAS_MODEL_PATH` | `instance/predictor_model.pkl` | Predictor checkpoint path |
| `SIAS_API_TOKEN` | _(empty)_ | If set, required as `X-API-Key` for mutating `/api/*` requests |
| `SIAS_UI_API_TOKEN` | _(empty)_ | Optional token injected into UI JavaScript for browser POST actions |

## Running Tests

```bash
python -m pytest tests/ -v
```

## Docker

```bash
docker build -t sias .
docker run --rm -p 5000:5000 sias
```

## Ops Endpoints

- `GET /health` - liveness
- `GET /ready` - readiness + PLC/model readiness details (includes active `coil_map` in Modbus mode)
- `GET /metrics` - basic request and uptime metrics

## Smoke Test

```powershell
# GET checks only
powershell -ExecutionPolicy Bypass -File scripts/smoke_test.ps1 -BaseUrl https://your-deployment-url

# GET + POST checks (when SIAS_API_TOKEN is enabled)
powershell -ExecutionPolicy Bypass -File scripts/smoke_test.ps1 -BaseUrl https://your-deployment-url -ApiToken "<token>"
```

## Screenshots

### Home Page
![Home](https://github.com/user-attachments/assets/9b6cb32e-d223-4c2b-b3c4-e2c10560749a)

### Live Dashboard
![Dashboard](https://github.com/user-attachments/assets/0b82aacf-f743-40b7-873f-22ccf555a423)

### PLC Monitor
![PLC Monitor](https://github.com/user-attachments/assets/5601468b-c275-4848-8fb1-0ecb2a1a2525)

### Predictive Maintenance
![Maintenance](https://github.com/user-attachments/assets/4597d352-a2fb-44a2-b62d-497352930518)

## PLC Ladder Logic

```
Rung 1 – Motor Run
  |─[/]─I0.0─[ ]─I0.1─[ ]─I0.2─[ ]─I0.3─[ ]─I0.4─[ ]─I0.5─[ ]─I0.6──────( )─ Q0.0 Motor Run |

Rung 2 – Coolant Pump
  |─[ ]─Q0.0──────( )─ Q0.1 Coolant Pump |

Rung 3 – Lube Pump
  |─[ ]─Q0.0──────( )─ Q0.5 Lube Pump |

Rung 4 – Pressure Relief (NC)
  |─[ ]─I0.4──────( )─ Q0.4 Pressure Relief Valve |

Rung 5 – Alarm Horn  (any unacknowledged alarm)
  |──────( )─ Q0.2 Alarm Horn |
```

Interlocks trip automatically when a sensor enters **CRITICAL** state:

| Sensor | Interlock contact | Effect |
|--------|-----------------|--------|
| Temperature | I0.3 Temp OK Switch | De-energises Motor Run |
| Pressure | I0.4 Pressure OK Switch | De-energises Motor Run; opens Pressure Relief Valve |
| Oil Level | I0.5 Oil Level OK Sw. | De-energises Motor Run |
| Current | I0.6 Motor Overload | De-energises Motor Run |

