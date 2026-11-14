# Phase 1: Module Exploration - Complete Analysis

## 🎯 Exploration Results

### Module 1: Machine Simulator ✓
**Status:** Ready | **Framework:** FastAPI | **Port:** 8000

**Key Capabilities:**
- Generates synthetic industrial telemetry for extruders, coating systems, dryers, compressors
- Fault scenario simulation (wear, thermal stress, pressure spikes, coating drift, electrical faults)
- REST API endpoints for live monitoring
- Browser-based dashboard
- Machine snapshots and telemetry samples

**Main Functions:**
```
get_fault_scenarios()           → Available fault types
build_machine_catalog()         → List of all machines
get_machine(machine_id)         → Specific machine details
get_telemetry_sample()          → Live sensor readings
generate_telemetry()            → Bulk telemetry generation
get_machine_snapshot()          → Point-in-time machine state
```

**Dependencies:**
- fastapi >= 0.115
- uvicorn >= 0.30

**Startup:**
```bash
cd modules/machine-simulator
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Dashboard at http://localhost:8000
```

---

### Module 2: Digital Twin ✓
**Status:** Ready | **Framework:** Next.js + FastAPI | **Stack:** Full-stack

**Key Capabilities:**
- Full-stack research platform (extrusion & coating machines)
- Frontend: Next.js + TypeScript + React + Three.js (3D visualization)
- Backend: Python FastAPI + PostgreSQL + TimescaleDB
- Real-time WebSocket integration
- 30-day retention telemetry storage
- REST + WebSocket APIs

**Main Functions:**
```
reference(machine_id, elapsed)      → Reference telemetry
sample(machine_id, elapsed)         → Sampled readings
validate(machine_id)                → Machine validation
require_fresh(machine_id)           → Freshness check
```

**Storage:**
- PostgreSQL + TimescaleDB hypertable (production)
- In-memory storage with 1,800 sample limit (dev without DATABASE_URL)

**Startup:**
```bash
# Backend
cd modules/digital-twin/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# Frontend (in another terminal)
cd modules/digital-twin/frontend
npm ci
npm run dev
# Dashboard at http://localhost:3000/digital-twin
```

---

### Module 3: Predictive Maintenance ✓
**Status:** Ready | **Framework:** FastAPI + Next.js | **ML:** Scikit-learn + PyTorch

**Key Capabilities:**
- Predictive maintenance using Isolation Forest (scikit-learn)
- PyTorch tensor operations for anomaly detection
- Four demo machines with temperature, vibration, pressure, current
- SIAS simulator integration
- Three scenarios: normal, bearing degradation, overheating
- Work order management (open, in-progress, completed)
- SQLite telemetry storage (1,000 readings/machine)
- Sensor rules and fault diagnostics

**Main Functions:**
```
read_fleet(scenario)            → Fleet assessment
assess(reading)                 → Analyze sensor readings
assess_deviation(z, faults)     → Anomaly detection
predict(reading)                → Make prediction
record_machine(machine, ts)     → Save telemetry
work_orders()                   → Retrieve work orders
create_work_order()             → Create new order
update_work_order()             → Update order status
```

**Scenarios:**
- `normal` - Standard operation
- `bearing` - Bearing degradation simulation
- `overheating` - Thermal stress simulation

**Startup:**
```bash
# Backend
cd modules/predictive-maintenance/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (in another terminal)
cd modules/predictive-maintenance/frontend
npm install
npm run dev
# Dashboard at http://localhost:3000/predictive-maintenance
```

---

## 📋 Capability Comparison

| Feature | Machine Simulator | Digital Twin | Predictive Maintenance |
|---------|-------------------|--------------|----------------------|
| **Framework** | FastAPI | Next.js + FastAPI | FastAPI + Next.js |
| **UI** | Browser dashboard | 3D + Charts | Dashboard |
| **Data** | Synthetic telemetry | Real-time + historical | Historical + predictions |
| **Storage** | In-memory | PostgreSQL + TimescaleDB | SQLite |
| **ML** | None | None | Isolation Forest + PyTorch |
| **Scenarios** | 6 fault types | Continuous | 3 scenarios |
| **Integration** | Standalone API | REST + WebSocket | SIAS simulator |

---

## 🔌 Integration Points

### Machine Simulator → Digital Twin
**How They Connect:**
- Simulator generates telemetry
- Twin consumes via REST API: `/machines` endpoint
- Twin stores and models in 3D

**Expected Flow:**
```
Simulator (port 8000) → Twin Backend (port 8000) → Twin Frontend (port 3000)
                         │
                         └─→ PostgreSQL/TimescaleDB
```

### Machine Simulator → Predictive Maintenance
**How They Connect:**
- Predictor reads from Simulator
- Set `SIAS_SIMULATOR_URL` environment variable
- Dashboard selects "SIAS Hub simulator" source

**Expected Flow:**
```
Simulator (port 8000) → Predictor Backend (port 8000) → Dashboard (port 3000)
                        │
                        └─→ SQLite (telemetry)
                        └─→ Work Orders (maintenance)
```

### All Three Together
```
┌─────────────────────┐
│ Machine Simulator   │ (Generates data)
│ Port: 8000          │
└────────────┬────────┘
             │
      ┌──────┴──────┐
      │             │
      ▼             ▼
┌──────────────┐  ┌─────────────────────────┐
│ Digital Twin │  │ Predictive Maintenance  │
│ Port: 8000   │  │ Port: 8000              │
│ (Models)     │  │ (Predicts)              │
└──────┬───────┘  └──────┬──────────────────┘
       │                 │
       ▼                 ▼
┌──────────────────────────────────────────┐
│ Dashboards (Port: 3000)                  │
│ - /digital-twin (3D visualization)       │
│ - /predictive-maintenance (health/risk)  │
└──────────────────────────────────────────┘
```

---

## 🛠️ Dependencies Summary

**Machine Simulator:**
- fastapi >= 0.115
- uvicorn >= 0.30

**Digital Twin:**
- Backend: See `backend/requirements-dev.txt`
- Frontend: Node.js 20.9+

**Predictive Maintenance:**
- Backend: See `backend/requirements.txt`
  - scikit-learn (Isolation Forest)
  - PyTorch (tensor operations)
  - fastapi, uvicorn
- Frontend: Node.js 20.9+

---

## 📊 Data Flow Architecture

### Simulator → Twin → Predictor

```
STEP 1: Simulator generates data
├─ /machines endpoint → machine catalog
├─ /fleet/telemetry endpoint → live readings
└─ Fault scenarios applied

STEP 2: Twin ingests and models
├─ Fetches from /machines
├─ Stores in TimescaleDB
├─ Renders 3D visualization
└─ Provides REST + WebSocket APIs

STEP 3: Predictor analyzes
├─ Reads historical data
├─ Applies ML models
├─ Detects anomalies
├─ Generates work orders
└─ Displays risk scores
```

---

## 🚀 Next: Phase 2 - Module Features

You now understand what each module does. Next phase (3-5 days):

1. **Add REST routes to each module** in main SIAS app
2. **Implement status endpoints** that return module health
3. **Create action handlers** for module-specific operations
4. **Wire up dependencies** between modules

See `DEVELOPMENT_ROADMAP.md` Phase 2 for detailed code templates.

---

## 💡 Quick Start Commands

### Test Simulator
```bash
cd modules/machine-simulator
pip install -r requirements.txt
uvicorn app.main:app --port 8000
# Then: curl http://localhost:8000/machines
```

### Test Digital Twin (Backend only)
```bash
cd modules/digital-twin/backend
pip install -r requirements-dev.txt
uvicorn app.main:app --port 8000
# Then: curl http://localhost:8000/docs
```

### Test Predictive Maintenance
```bash
cd modules/predictive-maintenance/backend
pip install -r requirements.txt
uvicorn app.main:app --port 8000
# Then: curl http://localhost:8000/api/machines
```

### Load Modules in Python
```python
from app.modules_integration import ModuleRegistry, init_modules
from flask import Flask

app = Flask(__name__)
init_modules(app)

for module_name in ModuleRegistry.list_modules():
    print(f"Module: {module_name}")
    module = ModuleRegistry.get(module_name)
    if hasattr(module, 'get_status'):
        print(f"  Status: {module.get_status()}")
```

---

## ✅ Phase 1 Checklist

- [x] Explored Machine Simulator structure
- [x] Explored Digital Twin architecture
- [x] Explored Predictive Maintenance capabilities
- [x] Identified main functions in each module
- [x] Understood dependencies
- [x] Mapped data flow between modules
- [x] Created quick start guides

## ⏭️ What's Next?

**Choose your path:**

**Option A: Deep Dive into One Module**
- Pick the module most interesting to you
- Run it locally
- Explore its dashboard
- Read its API documentation at `/docs`

**Option B: Skip to Phase 2 - Module Features**
- Add routes to SIAS server.py
- Implement status and action endpoints
- Wire modules to REST API

**Option C: Skip to Phase 3 - Build UI**
- Create module dashboards in SIAS frontend
- Display module status and data
- Build control interfaces

---

## 📚 Files to Read Next

1. **Module READMEs** (detailed usage)
   - `modules/machine-simulator/README.md`
   - `modules/digital-twin/README.md`
   - `modules/predictive-maintenance/README.md`

2. **DEVELOPMENT_ROADMAP.md** (Phase 2 implementation)

3. **API Docs** (run each module locally and visit `/docs`)

---

## 🎯 Summary

**Machine Simulator:** FastAPI app that generates realistic sensor data  
**Digital Twin:** Full-stack 3D + TimescaleDB platform that models assets  
**Predictive Maintenance:** ML-powered service that predicts failures + manages work orders

**All three can work independently or together to create a complete IIoT system.**

You've completed Phase 1! Ready to move to Phase 2 (Module Features)?
