# 3SIAS Module Integration Guide

## Overview

Your Smart Industrial Automation System (SIAS) is now integrated with three specialized 3SIAS modules:

1. **Industrial Machine Simulator** - Simulates industrial machine behavior
2. **Industrial Digital Twin** - Creates digital representation of physical assets
3. **AI Predictive Maintenance** - Provides ML-based maintenance predictions

## Architecture

```
Smart-Industrial-Automation-System/
├── app/
│   ├── modules_integration.py       # Module registry and initialization
│   ├── modules_routes.py            # API endpoints for module access
│   └── [other SIAS modules]
├── modules/                         # Integrated 3SIAS modules (git submodules)
│   ├── machine-simulator/
│   ├── digital-twin/
│   └── predictive-maintenance/
└── server.py                        # Main app with module initialization
```

## Integration Points

### 1. Module Registry (`app/modules_integration.py`)

The `ModuleRegistry` class manages all integrated modules:

```python
from app.modules_integration import ModuleRegistry, init_modules

# Initialize all modules at app startup
init_modules(app)

# Access modules
machine_sim = ModuleRegistry.get('machine_simulator')
digital_twin = ModuleRegistry.get('digital_twin')
predictor = ModuleRegistry.get('predictive_maintenance')

# List all available modules
modules = ModuleRegistry.list_modules()
```

### 2. API Endpoints

All modules are accessible via REST API:

```
GET  /api/modules/status                    # Status of all modules
GET  /api/modules/<module_name>/status      # Status of specific module
POST /api/modules/<module_name>/action      # Execute module action
```

**Example: Check module status**
```bash
curl http://localhost:5000/api/modules/status
```

**Response:**
```json
{
  "registered_modules": [
    "machine_simulator",
    "digital_twin",
    "predictive_maintenance"
  ],
  "module_paths": {
    "machine_simulator": "/path/to/modules/machine-simulator",
    "digital_twin": "/path/to/modules/digital-twin",
    "predictive_maintenance": "/path/to/modules/predictive-maintenance"
  }
}
```

### 3. Module Interface

Each module should implement this interface for full integration:

```python
# Optional: Module entry point
def register_routes(app):
    """Register Flask routes for this module."""
    pass

def get_status():
    """Return module status."""
    return {
        'status': 'active',
        'version': '1.0.0',
        # module-specific data
    }

def execute_action(action, **params):
    """Execute an action within this module."""
    if action == 'start':
        # implementation
    elif action == 'stop':
        # implementation
    # etc.
```

## Usage Patterns

### Pattern 1: Direct Module Access

```python
from app.modules_integration import ModuleRegistry

# Get a module
simulator = ModuleRegistry.get('machine_simulator')

# Use module directly
result = simulator.run_simulation()
```

### Pattern 2: API-Based Access

```bash
# Get machine simulator status
curl http://localhost:5000/api/modules/machine_simulator/status

# Execute an action
curl -X POST http://localhost:5000/api/modules/machine_simulator/action \
  -H "Content-Type: application/json" \
  -d '{"action": "start", "params": {"speed": 1000}}'
```

### Pattern 3: Flask App Context

```python
# In Flask routes or functions
from flask import current_app

modules = current_app.config['SIAS_MODULES']
simulator = modules.get('machine_simulator')
```

## Managing Submodules

### Clone with submodules

```bash
git clone --recurse-submodules \
  https://github.com/Eguono22/Smart-Industrial-Automation-System.git
```

### Update submodules

```bash
# Initial submodule setup (if cloned without --recurse-submodules)
git submodule update --init --recursive

# Update all submodules to latest
git submodule update --remote

# Update specific submodule
cd modules/machine-simulator
git pull origin main
cd ../..
```

### Update submodule in main repo

```bash
# Stage submodule change
git add modules/machine-simulator

# Commit change
git commit -m "Update machine-simulator to latest version"

# Push
git push origin main
```

## Configuration

### Environment Variables

Add to `.env`:

```env
# Module configuration
SIAS_MODULE_MACHINE_SIMULATOR_ENABLED=1
SIAS_MODULE_DIGITAL_TWIN_ENABLED=1
SIAS_MODULE_PREDICTIVE_MAINTENANCE_ENABLED=1

# Module-specific settings
MACHINE_SIMULATOR_MODE=full
DIGITAL_TWIN_UPDATE_INTERVAL=2000
PREDICTIVE_MAINTENANCE_MODEL_PATH=/path/to/model
```

### Runtime Configuration

```python
# In server.py or initialization code
import os

config = {
    'machine_simulator': {
        'enabled': os.environ.get('SIAS_MODULE_MACHINE_SIMULATOR_ENABLED', '1') == '1',
        'mode': os.environ.get('MACHINE_SIMULATOR_MODE', 'full')
    },
    'digital_twin': {
        'enabled': os.environ.get('SIAS_MODULE_DIGITAL_TWIN_ENABLED', '1') == '1',
        'update_interval': int(os.environ.get('DIGITAL_TWIN_UPDATE_INTERVAL', '2000'))
    },
    'predictive_maintenance': {
        'enabled': os.environ.get('SIAS_MODULE_PREDICTIVE_MAINTENANCE_ENABLED', '1') == '1',
        'model_path': os.environ.get('PREDICTIVE_MAINTENANCE_MODEL_PATH')
    }
}
```

## Development Workflow

### Local Development

1. **Clone main repo with modules:**
   ```bash
   git clone --recurse-submodules \
     https://github.com/Eguono22/Smart-Industrial-Automation-System.git
   cd Smart-Industrial-Automation-System
   ```

2. **Create feature branch:**
   ```bash
   git checkout -b feature/my-feature
   ```

3. **Work on a module:**
   ```bash
   cd modules/machine-simulator
   git checkout -b feature/my-module-feature
   # Make changes
   git commit -am "Implement feature"
   git push origin feature/my-module-feature
   ```

4. **Create PR in module repo** - Get it merged

5. **Update main repo to use new module version:**
   ```bash
   cd modules/machine-simulator
   git pull origin main
   cd ../..
   git add modules/machine-simulator
   git commit -m "Update machine-simulator to include new feature"
   git push origin feature/my-feature
   ```

6. **Create PR in main repo**

### Testing Modules

```bash
# Test main SIAS
pytest tests/

# Test specific module integration
pytest tests/test_modules.py

# Test module individually (in module directory)
cd modules/machine-simulator
pytest tests/
```

### Debugging

```python
# Get detailed module information
from app.modules_integration import ModuleRegistry, get_module_status

status = get_module_status()
print(status)

# Check if module loaded
if ModuleRegistry.get('machine_simulator'):
    print("Machine simulator loaded successfully")
else:
    print("Machine simulator failed to load")
```

## Troubleshooting

### Module not loading

**Problem:** Module shows as not registered

**Solution:**
```bash
# Verify submodule is cloned
ls -la modules/machine-simulator

# If empty, initialize submodules
git submodule update --init --recursive

# Check module has proper __init__.py
ls -la modules/machine-simulator/__init__.py
```

### Import errors

**Problem:** `ModuleNotFoundError` when accessing module

**Solution:**
```bash
# Ensure PYTHONPATH includes modules
export PYTHONPATH="${PYTHONPATH}:/path/to/modules"

# Or, install module as editable package
cd modules/machine-simulator
pip install -e .
```

### Submodule sync issues

**Problem:** Submodule at wrong commit

**Solution:**
```bash
# See which commits submodules are tracking
git config --file .gitmodules --list

# Sync submodules
git submodule sync

# Update to latest
git submodule update --remote
```

## Next Steps

1. **Implement module-specific routes** - Add routes to each module's `register_routes()` function
2. **Add module configuration** - Create module-specific `.env` settings
3. **Build module UI components** - Create dashboard widgets for each module
4. **Implement SocketIO events** - Add real-time module data broadcasting
5. **Add module documentation** - Document each module's API and capabilities

## Resources

- [Git Submodules Documentation](https://git-scm.com/book/en/v2/Git-Tools-Submodules)
- [Flask Application Factory Pattern](https://flask.palletsprojects.com/en/latest/patterns/appfactories/)
- [REST API Best Practices](https://restfulapi.net/)
