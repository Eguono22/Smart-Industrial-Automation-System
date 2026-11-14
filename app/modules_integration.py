"""
3SIAS Module Integration Layer
Integrates specialized modules into the main SIAS application.
"""

import os
import sys
from pathlib import Path

# Add modules to Python path
MODULES_DIR = Path(__file__).parent.parent / "modules"
sys.path.insert(0, str(MODULES_DIR))


class ModuleRegistry:
    """Registry for managing integrated 3SIAS modules."""
    
    _modules = {}
    
    @classmethod
    def register(cls, name: str, module):
        """Register a module with the registry."""
        cls._modules[name] = module
        print(f"[SIAS] Registered module: {name}")
    
    @classmethod
    def get(cls, name: str):
        """Retrieve a registered module."""
        return cls._modules.get(name)
    
    @classmethod
    def list_modules(cls):
        """List all registered modules."""
        return list(cls._modules.keys())
    
    @classmethod
    def load_all(cls):
        """Dynamically load all available modules."""
        modules_to_load = {
            'machine_simulator': 'machine-simulator',
            'digital_twin': 'digital-twin',
            'predictive_maintenance': 'predictive-maintenance',
        }
        
        for module_name, module_dir in modules_to_load.items():
            module_path = MODULES_DIR / module_dir
            if module_path.exists():
                try:
                    # Try to import the module's main entry point
                    sys.path.insert(0, str(module_path))
                    module = __import__(module_name.replace('_', '-'))
                    cls.register(module_name, module)
                except Exception as e:
                    print(f"[SIAS] Warning: Could not load module {module_name}: {e}")


def init_modules(app):
    """Initialize all modules and inject them into Flask app context."""
    
    # Load modules
    ModuleRegistry.load_all()
    
    # Make modules available in app context
    app.config['SIAS_MODULES'] = ModuleRegistry
    
    # Register module routes (if they exist)
    for module_name in ModuleRegistry.list_modules():
        module = ModuleRegistry.get(module_name)
        
        # Check if module has a register_routes function
        if hasattr(module, 'register_routes'):
            try:
                module.register_routes(app)
                print(f"[SIAS] Registered routes for module: {module_name}")
            except Exception as e:
                print(f"[SIAS] Warning: Could not register routes for {module_name}: {e}")
    
    return ModuleRegistry


def get_module_status():
    """Get status of all integrated modules."""
    status = {
        'registered_modules': ModuleRegistry.list_modules(),
        'module_paths': {
            name: str(MODULES_DIR / name.replace('_', '-'))
            for name in ModuleRegistry.list_modules()
        }
    }
    return status
