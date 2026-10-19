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
| **Deterministic Demo Scenario** | Repeatable bearing-overheat sequence: vibration warning, critical fault, thermal trip, PLC safety response |
| **Alarm Management** | Per-sensor alarms with priority levels (critical / warning / info) and ACK support |
| **Production Hardening** | Account sessions, roles, customer access controls and CSRF protection, `/health` + `/ready` + `/metrics`, Dockerfile and GitHub Actions CI |

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

# 2. Create your first administrator (interactive password prompt)
python scripts/manage_users.py

# 3. Run the application
python app.py

# 4. Open browser and log in
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
| `SIAS_DATABASE_PATH` | `instance/sias.sqlite3` | Persistent registry, users, sessions and work-order database |
| `SECRET_KEY` | generated and stored in SQLite | Optional session-signing secret override |
| `SIAS_COOKIE_SECURE` | `0` | Set `1` for HTTPS deployments to require secure session cookies |

## Running Tests

```bash
python -m pytest tests/ -v
```

## Deterministic Demo

Use the **Scenario Demo** controls on the dashboard, or call the API directly:

```bash
# Log in as an administrator in the browser, then use Scenario Demo controls.
# API clients must retain the login cookie and send X-CSRF-Token for writes.
```

Run the automated demo validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo_validation.ps1 -Username "admin" -BaseUrl http://localhost:5000
```

To save a portable evidence report:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo_validation.ps1 -Username "admin" -BaseUrl http://localhost:5000 -ReportPath artifacts/demo-validation.json
```

The built-in `bearing_overheat` scenario is designed for walkthroughs and validation:

| Phase | Expected behavior |
|---|---|
| Healthy baseline | Sensors remain normal and motor runs |
| Early bearing wear | Vibration enters warning range |
| Bearing fault | Vibration becomes critical and alarms are raised |
| Thermal runaway | Temperature/current become critical and PLC interlocks de-energise motor run |
| PLC safety response | Pressure relief energises and alarm horn remains active until ACK |

This gives a repeatable end-to-end maintenance story: normal operation, early warning, predicted risk, PLC safety action and operator alarm handling.

See [docs/demo_walkthrough.md](docs/demo_walkthrough.md) for a presentation-ready walkthrough.

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

# Protected API checks (password prompted, or set SIAS_ADMIN_PASSWORD)
powershell -ExecutionPolicy Bypass -File scripts/smoke_test.ps1 -BaseUrl https://your-deployment-url -Username "admin"
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


## SIAS Hub: industries and solution planning

The home page provides a searchable catalog of 24 industries, potential customer
segments, typical equipment and target KPIs. Select an industry to build a tailored
solution plan, change capability selections, add project requirements and download
JSON. Plans persist in this browser's local storage when available; they are not
stored on the server or shared across users. Exported plans include project notes.
The read-only `GET /api/hub/catalog` endpoint exposes the same catalog.

Four capabilities are available in the existing single-machine demo: monitoring,
predictive maintenance, PLC control and alarms. Asset-linked maintenance work orders
are also available through the persistent registry. Twelve additional capabilities
are explicitly marked **Planned**, including fleet management, OEE,
quality, energy, environmental monitoring, cold chain, inventory, enterprise access,
industrial connectors, enterprise integration, safety workflows and reporting.
Selecting a module creates a discovery plan; it does not implement or activate it.
Industry profiles represent potential applications and customer types, not customer
endorsements or validated industry deployments. Site-specific instrumentation,
engineering and validation remain necessary.

## Customer, site and asset registry

Open **Assets** (`/assets`) to create customers, assign sites and register equipment.
Each customer has an industry; each site belongs to one customer; each asset belongs
to one site. Equipment records include type, optional serial number, criticality and
manually maintained status. The directory supports search, customer filtering and
asset-status filtering, with edit and delete actions. Customers and sites with
dependent records cannot be deleted. An occupied site cannot be transferred to
another customer; reassign its assets first.

Data persists in SQLite at `instance/sias.sqlite3` by default. Set
`SIAS_DATABASE_PATH` to override the file location. The application creates the
schema automatically. Use a writable durable volume and back up the database for
production; ephemeral/serverless filesystems do not provide durable storage. A
Docker deployment can mount `/app/instance` if using the supplied Dockerfile.

API endpoints:

- `GET /api/registry`: customers, sites and assets.
- `POST /api/registry/customers`: `name`, `industry` (industry catalog ID).
- `POST /api/registry/sites`: `name`, integer `customer_id`, optional `location`.
- `POST /api/registry/assets`: `name`, integer `site_id`, `asset_type`, optional
  `serial_number`, `criticality` and `status`.
- `PATCH /api/registry/{customers|sites|assets}/{id}`: update supplied fields.
- `DELETE /api/registry/{customers|sites|assets}/{id}`: remove an unreferenced record.

Criticality values: `low`, `medium` (default), `high`, `critical`.
Status values: `unknown` (default), `operational`, `maintenance`, `offline`.
Registry reads and writes require account sessions. Customer access is enforced
for managers, technicians and viewers; administrators have global access. The
registry does not implement live device connections or per-asset telemetry. Registered assets
are independent of the existing single-machine simulation.


## Maintenance work orders

Open **Work orders** (`/work-orders`) to create maintenance tasks for registered
assets. Tasks include title, description, priority, optional assignee name, required
due date, status and completion notes. Filter by asset to review its maintenance
history, search by task/customer/assignee, filter by status or show overdue tasks.
Overdue means a due date before the current UTC date while open or in progress;
tasks due today, completed tasks and cancelled tasks are not overdue.

Statuses are `open`, `in_progress`, `completed` and `cancelled`. Completion requires
notes and records a UTC completion timestamp. Tasks can be reopened, preserving
prior snapshots in history; reopening clears the current completion timestamp.
Each actual change appends a timestamped snapshot in the same SQLite transaction.
Work orders remain attached to their original asset and cannot be deleted through
the API; cancel unwanted tasks instead. Assets with work orders cannot be deleted.
Assignments use registered technicians belonging to the asset customer. Older
free-text assignments are preserved until reassigned. Notifications remain planned. Work order
status does not change asset status or machine controls. New history entries record the authenticated actor. Older entries retain an
unknown actor rather than inferring an identity.

Work orders use the existing `SIAS_DATABASE_PATH` database and automatically add
their tables to existing installations without replacing registry data:

- `GET /api/work-orders`: list tasks with asset, site and customer names and an
  `overdue` flag.
- `POST /api/work-orders`: create with integer `asset_id`, `title`, `due_date`
  (`YYYY-MM-DD`); optional `description`, `priority`, `assignee_id` (integer or null), `status` and
  `completion_notes`.
- `GET /api/work-orders/{id}`: task details and timestamped snapshot history.
- `PATCH /api/work-orders/{id}`: update supported task fields; asset is immutable.

Priorities are `low`, `medium` (default), `high` and `critical`; status defaults to
`open`. Reads require login; writes additionally require a session CSRF token.


## Accounts and customer access

Create the first administrator with `python scripts/manage_users.py`, using the
same `SIAS_DATABASE_PATH` environment setting as the server. There is no default
account or public registration. Sign in at `/login`, create customers in **Assets**,
then use **Users** (`/users`) to create, edit, reset passwords or disable accounts.
Passwords require 12–256 characters and are stored as salted PBKDF2-SHA256 hashes
with 1,000,000 iterations. Disabled accounts cannot log in; account updates revoke
the account's existing sessions. At least one active administrator must remain.

| Role | Access |
|---|---|
| Admin | All customers, user administration, registry/work orders and shared machine demo |
| Manager | Own customer's records; create/edit/delete sites and assets, create/edit/assign work orders |
| Technician | Read own customer's records; update only status and completion notes on tasks assigned to their account |
| Viewer | Read own customer's records and task history |

Non-admin accounts belong to one customer. Direct API IDs and submitted parent
IDs are checked against that customer, including work-order details/history and
technician lists. Work orders with history cannot move across customers through
asset reassignment. Existing task history is preserved by additive schema changes.
The shared simulated machine, its REST APIs and Socket.IO stream are admin-only.
Stream sessions are revalidated each update, including expiry, logout and account
revocation. This release does not associate the simulator with a tenant's asset.

Session cookies are HttpOnly and SameSite=Lax. Server sessions expire after eight
hours, and logout revokes the session on the server. For HTTPS deployments set
`SIAS_COOKIE_SECURE=1`. A random signing secret persists in SQLite unless
`SECRET_KEY` is supplied; keep the database private and use durable storage.
Login is limited to ten failed attempts per direct client IP in fifteen minutes;
when deployed behind a proxy this may represent the proxy IP. External SSO and
MFA are not implemented.

API clients must use account sessions; the previous `SIAS_API_TOKEN` and
`SIAS_UI_API_TOKEN` settings no longer grant access or inject secrets into pages:

1. `GET /api/auth/me` and retain the session cookie and `csrf_token`.
2. `POST /api/auth/login` with JSON `username` and `password`, the cookie and
   `X-CSRF-Token`. Retain the rotated cookie and returned CSRF token.
3. Include the cookie on protected reads and `X-CSRF-Token` on all writes.
4. `POST /api/auth/logout` with cookie and CSRF token to revoke access.

`GET/POST /api/auth/users` and `PATCH /api/auth/users/{id}` are admin-only.
`GET /api/auth/technicians` returns active technicians visible to the caller.
Work-order writes accept `assignee_id`, not client-supplied assignee names.
Task history includes `actor_id` and `actor_name`; legacy entries have null actors.
Operational PowerShell scripts accept `-Username` (or `SIAS_ADMIN_USERNAME`) and
prompt for a password, or read `SIAS_ADMIN_PASSWORD` for unattended CI. Public
smoke checks require no credentials; protected checks require an admin account.
