# 3SIAS Module Integration - Quick Reference

## ✅ Integration Complete

Your Smart Industrial Automation System is now connected to three specialized 3SIAS modules:

### Modules Integrated

| Module | Path | Repository |
|--------|------|------------|
| **Machine Simulator** | `modules/machine-simulator` | `sias-hub-industrial-machine-simulator` |
| **Digital Twin** | `modules/digital-twin` | `sias-hub-industrial-digital-twin` |
| **Predictive Maintenance** | `modules/predictive-maintenance` | `sias-hub-ai-predictive-maintenance` |

## 🚀 Quick Start

### 1. Check Module Status

```bash
# List all modules
curl http://localhost:5000/api/modules/status

# Check specific module
curl http://localhost:5000/api/modules/machine_simulator/status
```

### 2. Access Modules in Code

```python
from app.modules_integration import ModuleRegistry

# Get a module
simulator = ModuleRegistry.get('machine_simulator')

# List all modules
modules = ModuleRegistry.list_modules()
# Output: ['machine_simulator', 'digital_twin', 'predictive_maintenance']
```

### 3. Use Module APIs

```python
# Example: Execute action in machine simulator
module = ModuleRegistry.get('machine_simulator')
result = module.execute_action('start', speed=1000)
```

## 📋 Integration Files

| File | Purpose |
|------|---------|
| `app/modules_integration.py` | Module registry and initialization logic |
| `app/modules_routes.py` | REST API endpoints for module access |
| `server.py` | Updated with module initialization |
| `docs/MODULES_INTEGRATION.md` | Full integration documentation |
| `.gitmodules` | Git submodule configuration |

## 🔄 Workflow: Update a Module

```bash
# 1. Go to module directory
cd modules/machine-simulator

# 2. Pull latest changes
git pull origin main

# 3. Return to root
cd ../..

# 4. Commit the update
git add modules/machine-simulator
git commit -m "Update machine-simulator to latest version"

# 5. Push
git push origin main
```

## 🔧 Common Operations

### Clone repo with modules
```bash
git clone --recurse-submodules \
  https://github.com/Eguono22/Smart-Industrial-Automation-System.git
```

### Initialize submodules (if cloned without --recurse-submodules)
```bash
git submodule update --init --recursive
```

### Update all submodules
```bash
git submodule update --remote
```

### Sync submodule configuration
```bash
git submodule sync
```

## 📡 API Endpoints

All module interactions go through these endpoints:

```
GET    /api/modules/status
GET    /api/modules/<module_name>/status
POST   /api/modules/<module_name>/action
```

### Example: Execute machine simulator action
```bash
curl -X POST http://localhost:5000/api/modules/machine_simulator/action \
  -H "Content-Type: application/json" \
  -d '{
    "action": "start",
    "params": {
      "speed": 1000,
      "mode": "full"
    }
  }'
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Test module integration
python -c "from app.modules_integration import ModuleRegistry; print(ModuleRegistry.list_modules())"
```

## 📚 Documentation

- **Full Integration Guide**: See `docs/MODULES_INTEGRATION.md`
- **Module Details**: Check each module's `README.md`
  - `modules/machine-simulator/README.md`
  - `modules/digital-twin/README.md`
  - `modules/predictive-maintenance/README.md`

## ✨ Key Features

✅ **Modular Architecture** - Separate repos, integrated seamlessly  
✅ **Version Control** - Git submodules track module versions  
✅ **Independent Development** - Develop modules independently  
✅ **API Integration** - Access modules via REST API  
✅ **Direct Access** - Import and use modules directly in code  
✅ **Easy Updates** - Pull latest changes with `git submodule update`  

## 🛠️ Configuration

Set these environment variables in `.env`:

```env
# Enable/disable modules
SIAS_MODULE_MACHINE_SIMULATOR_ENABLED=1
SIAS_MODULE_DIGITAL_TWIN_ENABLED=1
SIAS_MODULE_PREDICTIVE_MAINTENANCE_ENABLED=1

# Module-specific settings
MACHINE_SIMULATOR_MODE=full
DIGITAL_TWIN_UPDATE_INTERVAL=2000
PREDICTIVE_MAINTENANCE_MODEL_PATH=/path/to/model
```

## 🔍 Troubleshooting

### Modules not loading?
```bash
# Initialize submodules
git submodule update --init --recursive

# Verify structure
ls -la modules/machine-simulator
```

### Import errors?
```bash
# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/modules"

# Or install as editable
cd modules/machine-simulator
pip install -e .
```

### Submodule out of sync?
```bash
# Sync configuration
git submodule sync

# Update to latest
git submodule update --remote
```

## 📞 Support

- **Main Repo Issues**: GitHub Issues in main repository
- **Module-Specific Issues**: GitHub Issues in module repositories
- **Integration Questions**: See `docs/MODULES_INTEGRATION.md`

---

**Integration Date**: 2026-11-13  
**Main Repo**: `Eguono22/Smart-Industrial-Automation-System`  
**Method**: Git Submodules
