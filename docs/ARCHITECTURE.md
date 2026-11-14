```
SIAS MODULE INTEGRATION ARCHITECTURE
=====================================

┌─────────────────────────────────────────────────────────────────────────┐
│                    Smart Industrial Automation System                   │
│                         (Main Repository)                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                   ┌────────────────┼────────────────┐
                   │                │                │
                   ▼                ▼                ▼
        ┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐
        │  server.py       │  │  app/        │  │  modules/        │
        │  (Flask app)     │  │  (SIAS core) │  │  (3SIAS mods)    │
        └──────────────────┘  └──────────────┘  └──────────────────┘
                   │                │                │
                   │         ┌───────┴───────┐      │
                   │         │               │      │
                   │         ▼               ▼      ▼
                   │    modules_          modules_     🔗 Git
                   │    integration.py    routes.py     Submodules
                   │    (Registry)        (REST API)
                   │
                   └──────────────┬─────────────────────────────┐
                                  │                             │
                   ┌──────────────┴─────────────┐               │
                   │                            │               │
                   ▼                            ▼               ▼
        ┌─────────────────┐          ┌─────────────────┐   ┌────────────┐
        │ Module Registry │          │  REST Endpoints │   │ Flask App  │
        └─────────────────┘          └─────────────────┘   └────────────┘
              │                             │
              │ get()                       │ /api/modules/status
              │ register()                  │ /api/modules/*/status
              │ list_modules()              │ /api/modules/*/action
              │
    ┌─────────┼─────────┬──────────────┐
    │         │         │              │
    ▼         ▼         ▼              ▼
┌────────┐ ┌────────┐ ┌────────┐   ┌────────────────┐
│Machine │ │Digital │ │Predictive│   │  Other Modules │
│Simulator│ │ Twin   │ │Maintenance   │  (Future)      │
└────────┘ └────────┘ └────────┘   └────────────────┘
    │         │         │
    ▼         ▼         ▼
[Code]   [Code]   [Code]  ... Each module has:
                         ├─ register_routes()
                         ├─ get_status()
                         ├─ execute_action()
                         └─ Independent tests


DATA FLOW: Request to Module
=================================

User/Client
    │
    ▼
HTTP Request (/api/modules/machine_simulator/status)
    │
    ▼
Flask Route (modules_routes.py)
    │
    ▼
ModuleRegistry.get('machine_simulator')
    │
    ▼
Module Instance (from modules/machine-simulator)
    │
    ▼
Module's get_status() method
    │
    ▼
JSON Response (via Flask)
    │
    ▼
Client receives data


INTEGRATION LAYERS
==================

Layer 1: Git Integration
─────────────────────
├─ Main repo: Smart-Industrial-Automation-System
├─ Submodule 1: modules/machine-simulator
├─ Submodule 2: modules/digital-twin
└─ Submodule 3: modules/predictive-maintenance


Layer 2: Python Integration
──────────────────────────
├─ app/modules_integration.py
│  ├─ ModuleRegistry class
│  ├─ init_modules() function
│  └─ get_module_status() function
│
├─ app/modules_routes.py
│  ├─ /api/modules/status
│  ├─ /api/modules/<name>/status
│  └─ /api/modules/<name>/action
│
└─ server.py
   ├─ init_modules(app)
   └─ register_modules_routes(app)


Layer 3: Runtime Integration
──────────────────────────
├─ Module Loading
│  ├─ Lazy loading on demand
│  ├─ sys.path manipulation
│  └─ Dynamic importing
│
├─ Module Registry
│  ├─ Central registry object
│  ├─ Module caching
│  └─ Error handling
│
└─ API Access
   ├─ REST endpoints
   ├─ Module action dispatch
   └─ Error responses


WORKFLOW: Developing a Module
==============================

1. Create feature in module repo
   modules/machine-simulator
   └─ Create feature branch
   └─ Implement changes
   └─ Push to module repo

2. Test module independently
   cd modules/machine-simulator
   pytest tests/

3. Update main repo reference
   cd /path/to/Smart-Industrial-Automation-System
   cd modules/machine-simulator
   git pull origin main
   cd ../..

4. Commit reference update
   git add modules/machine-simulator
   git commit -m "Update machine-simulator"

5. Push to main repo
   git push origin main


WORKFLOW: Using Modules in SIAS
================================

# In a Flask route
from app.modules_integration import ModuleRegistry

@app.route('/api/machine/status')
def get_machine_status():
    simulator = ModuleRegistry.get('machine_simulator')
    if simulator:
        return jsonify(simulator.get_status())
    return jsonify({'error': 'Module not found'}), 404


# Direct module access
from app.modules_integration import ModuleRegistry

def some_function():
    predictor = ModuleRegistry.get('predictive_maintenance')
    result = predictor.run_analysis(data)
    return result


DEPLOYMENT CONSIDERATIONS
==========================

1. Clone with submodules
   └─ git clone --recurse-submodules <repo>

2. Initialize submodules (if needed)
   └─ git submodule update --init --recursive

3. Install module dependencies
   └─ For each module:
      cd modules/<module_name>
      pip install -r requirements.txt

4. Test integration
   └─ pytest tests/

5. Deploy as usual
   └─ Same deployment process


TROUBLESHOOTING MAP
===================

Issue                        Solution
─────                        ────────
Module not found             └─ Run: git submodule update --init
Import error in module       └─ Check: __init__.py exists in module
API endpoint returns 404     └─ Verify: Module registered successfully
Module method not found      └─ Check: Module implements required interface
Submodule out of sync        └─ Run: git submodule sync && git submodule update
Wrong module version         └─ Run: cd modules/<name> && git pull origin main
```

## Quick Commands Reference

```bash
# Clone everything
git clone --recurse-submodules https://github.com/Eguono22/Smart-Industrial-Automation-System.git

# Initialize submodules (one-time)
git submodule update --init --recursive

# Update all modules to latest
git submodule update --remote

# Update specific module
cd modules/machine-simulator && git pull origin main && cd ../..

# Check module status
curl http://localhost:5000/api/modules/status

# Check specific module
curl http://localhost:5000/api/modules/machine_simulator/status

# In Python: Get a module
from app.modules_integration import ModuleRegistry
sim = ModuleRegistry.get('machine_simulator')

# List all modules
from app.modules_integration import ModuleRegistry
print(ModuleRegistry.list_modules())
```
