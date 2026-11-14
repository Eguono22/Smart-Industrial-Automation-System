"""
Phase 2: Module Features Implementation Layer
Adds routes, status endpoints, and actions for all 3SIAS modules
"""

from flask import Blueprint, jsonify, request
from app.modules_integration import ModuleRegistry
from typing import Dict, Any
import os

# Create blueprint for module-specific features
module_features_bp = Blueprint('module_features', __name__, url_prefix='/api/modules')


# ============================================================================
# MACHINE SIMULATOR FEATURES
# ============================================================================

@module_features_bp.route('/machine-simulator/machines', methods=['GET'])
def machine_simulator_machines():
    """List all available machines in the simulator"""
    try:
        module = ModuleRegistry.get('machine_simulator')
        if not module or not hasattr(module, 'build_machine_catalog'):
            return jsonify({'error': 'Machine simulator not available'}), 503
        
        machines = module.build_machine_catalog()
        return jsonify({
            'status': 'success',
            'count': len(machines),
            'machines': machines
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 400


@module_features_bp.route('/machine-simulator/machine/<machine_id>', methods=['GET'])
def machine_simulator_machine_detail(machine_id: str):
    """Get details for a specific machine"""
    try:
        module = ModuleRegistry.get('machine_simulator')
        if not module or not hasattr(module, 'get_machine'):
            return jsonify({'error': 'Machine simulator not available'}), 503
        
        machine = module.get_machine(machine_id)
        if not machine:
            return jsonify({'error': f'Machine {machine_id} not found'}), 404
        
        return jsonify({
            'status': 'success',
            'machine': machine
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 400


@module_features_bp.route('/machine-simulator/machine/<machine_id>/snapshot', methods=['GET'])
def machine_simulator_snapshot(machine_id: str):
    """Get current snapshot of machine state"""
    try:
        module = ModuleRegistry.get('machine_simulator')
        if not module or not hasattr(module, 'get_machine_snapshot'):
            return jsonify({'error': 'Machine simulator not available'}), 503
        
        snapshot = module.get_machine_snapshot(machine_id)
        if not snapshot:
            return jsonify({'error': f'Could not get snapshot for {machine_id}'}), 400
        
        return jsonify({
            'status': 'success',
            'snapshot': snapshot
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 400


@module_features_bp.route('/machine-simulator/machine/<machine_id>/telemetry', methods=['GET'])
def machine_simulator_telemetry(machine_id: str):
    """Get telemetry sample for a machine"""
    try:
        scenario = request.args.get('scenario', 'normal')
        index = float(request.args.get('index', 0))
        
        module = ModuleRegistry.get('machine_simulator')
        if not module or not hasattr(module, 'get_telemetry_sample'):
            return jsonify({'error': 'Machine simulator not available'}), 503
        
        telemetry = module.get_telemetry_sample(machine_id, index, scenario)
        if not telemetry:
            return jsonify({'error': f'Could not get telemetry for {machine_id}'}), 400
        
        return jsonify({
            'status': 'success',
            'telemetry': telemetry,
            'scenario': scenario
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 400


@module_features_bp.route('/machine-simulator/faults', methods=['GET'])
def machine_simulator_faults():
    """Get available fault scenarios"""
    try:
        module = ModuleRegistry.get('machine_simulator')
        if not module or not hasattr(module, 'get_fault_scenarios'):
            return jsonify({'error': 'Machine simulator not available'}), 503
        
        faults = module.get_fault_scenarios()
        return jsonify({
            'status': 'success',
            'faults': faults,
            'count': len(faults)
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 400


# ============================================================================
# DIGITAL TWIN FEATURES
# ============================================================================

@module_features_bp.route('/digital-twin/assets', methods=['GET'])
def digital_twin_assets():
    """List all digital twin assets"""
    try:
        module = ModuleRegistry.get('digital_twin')
        if not module:
            return jsonify({'error': 'Digital twin not available'}), 503
        
        # If module has get_assets method, use it
        if hasattr(module, 'get_assets'):
            assets = module.get_assets()
            return jsonify({
                'status': 'success',
                'assets': assets,
                'count': len(assets)
            })
        
        # Otherwise return placeholder
        return jsonify({
            'status': 'available',
            'message': 'Digital twin module loaded',
            'api_docs': 'http://localhost:8000/docs'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 400


@module_features_bp.route('/digital-twin/asset/<asset_id>', methods=['GET'])
def digital_twin_asset(asset_id: str):
    """Get digital twin state for specific asset"""
    try:
        module = ModuleRegistry.get('digital_twin')
        if not module:
            return jsonify({'error': 'Digital twin not available'}), 503
        
        # If module has get_asset method
        if hasattr(module, 'get_asset'):
            asset = module.get_asset(asset_id)
            if not asset:
                return jsonify({'error': f'Asset {asset_id} not found'}), 404
            
            return jsonify({
                'status': 'success',
                'asset': asset
            })
        
        return jsonify({
            'status': 'available',
            'message': f'Digital twin available for asset {asset_id}',
            'note': 'Use direct API at http://localhost:8000/docs'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 400


@module_features_bp.route('/digital-twin/sync', methods=['POST'])
def digital_twin_sync():
    """Sync digital twin with latest data"""
    try:
        data = request.get_json() or {}
        asset_id = data.get('asset_id')
        
        module = ModuleRegistry.get('digital_twin')
        if not module:
            return jsonify({'error': 'Digital twin not available'}), 503
        
        if hasattr(module, 'sync'):
            result = module.sync(asset_id)
            return jsonify({
                'status': 'success',
                'result': result
            })
        
        return jsonify({
            'status': 'available',
            'message': 'Sync request noted',
            'use_api': 'http://localhost:8000/docs'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 400


# ============================================================================
# PREDICTIVE MAINTENANCE FEATURES
# ============================================================================

@module_features_bp.route('/predictive-maintenance/machines', methods=['GET'])
def predictive_maintenance_machines():
    """Get fleet assessment from predictive maintenance"""
    try:
        scenario = request.args.get('scenario', 'normal')
        source = request.args.get('source', 'local')  # 'local' or 'sias'
        
        module = ModuleRegistry.get('predictive_maintenance')
        if not module:
            return jsonify({'error': 'Predictive maintenance not available'}), 503
        
        if hasattr(module, 'read_fleet'):
            machines = module.read_fleet(scenario)
            return jsonify({
                'status': 'success',
                'machines': machines,
                'scenario': scenario,
                'source': source
            })
        
        return jsonify({
            'status': 'available',
            'message': 'Predictive maintenance module loaded',
            'scenarios': ['normal', 'bearing', 'overheating'],
            'api_docs': 'http://localhost:8000/docs'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 400


@module_features_bp.route('/predictive-maintenance/predict', methods=['POST'])
def predictive_maintenance_predict():
    """Make a prediction based on sensor readings"""
    try:
        data = request.get_json() or {}
        
        module = ModuleRegistry.get('predictive_maintenance')
        if not module:
            return jsonify({'error': 'Predictive maintenance not available'}), 503
        
        if hasattr(module, 'predict'):
            prediction = module.predict(data)
            return jsonify({
                'status': 'success',
                'prediction': prediction
            })
        
        return jsonify({
            'status': 'available',
            'message': 'Send readings to predict',
            'expected_fields': ['temperature', 'vibration', 'pressure', 'current']
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 400


@module_features_bp.route('/predictive-maintenance/machine/<machine_id>/health', methods=['GET'])
def predictive_maintenance_health(machine_id: str):
    """Get health status for a machine"""
    try:
        module = ModuleRegistry.get('predictive_maintenance')
        if not module:
            return jsonify({'error': 'Predictive maintenance not available'}), 503
        
        if hasattr(module, 'get_health'):
            health = module.get_health(machine_id)
            return jsonify({
                'status': 'success',
                'machine_id': machine_id,
                'health': health
            })
        
        return jsonify({
            'status': 'available',
            'message': f'Health data available for {machine_id}',
            'use_api': 'http://localhost:8000/docs'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 400


@module_features_bp.route('/predictive-maintenance/machine/<machine_id>/history', methods=['GET'])
def predictive_maintenance_history(machine_id: str):
    """Get historical data for a machine"""
    try:
        limit = int(request.args.get('limit', 1000))
        
        module = ModuleRegistry.get('predictive_maintenance')
        if not module:
            return jsonify({'error': 'Predictive maintenance not available'}), 503
        
        if hasattr(module, 'get_history'):
            history = module.get_history(machine_id, limit)
            return jsonify({
                'status': 'success',
                'machine_id': machine_id,
                'count': len(history),
                'history': history
            })
        
        return jsonify({
            'status': 'available',
            'message': f'Historical data available for {machine_id}',
            'use_api': 'http://localhost:8000/docs'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 400


@module_features_bp.route('/predictive-maintenance/work-orders', methods=['GET'])
def predictive_maintenance_work_orders():
    """Get maintenance work orders"""
    try:
        status = request.args.get('status', None)  # open, in_progress, completed
        
        module = ModuleRegistry.get('predictive_maintenance')
        if not module:
            return jsonify({'error': 'Predictive maintenance not available'}), 503
        
        if hasattr(module, 'get_work_orders'):
            orders = module.get_work_orders(status)
            return jsonify({
                'status': 'success',
                'orders': orders,
                'count': len(orders),
                'filter': status
            })
        
        return jsonify({
            'status': 'available',
            'message': 'Work orders available',
            'use_api': 'http://localhost:8000/docs'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 400


@module_features_bp.route('/predictive-maintenance/work-orders', methods=['POST'])
def predictive_maintenance_create_order():
    """Create a new maintenance work order"""
    try:
        data = request.get_json() or {}
        
        module = ModuleRegistry.get('predictive_maintenance')
        if not module:
            return jsonify({'error': 'Predictive maintenance not available'}), 503
        
        if hasattr(module, 'create_work_order'):
            order = module.create_work_order(data)
            return jsonify({
                'status': 'success',
                'order': order
            })
        
        return jsonify({
            'status': 'available',
            'message': 'Work order creation available',
            'use_api': 'http://localhost:8000/docs'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 400


# ============================================================================
# UNIFIED STATUS ENDPOINT
# ============================================================================

@module_features_bp.route('/features/status', methods=['GET'])
def features_status():
    """Get status of all module features"""
    status = {
        'machine_simulator': {
            'available': ModuleRegistry.get('machine_simulator') is not None,
            'endpoints': [
                '/machines',
                '/machine/<id>',
                '/machine/<id>/snapshot',
                '/machine/<id>/telemetry?scenario=<scenario>',
                '/faults'
            ]
        },
        'digital_twin': {
            'available': ModuleRegistry.get('digital_twin') is not None,
            'endpoints': [
                '/assets',
                '/asset/<id>',
                '/sync'
            ]
        },
        'predictive_maintenance': {
            'available': ModuleRegistry.get('predictive_maintenance') is not None,
            'endpoints': [
                '/machines?scenario=<scenario>',
                '/predict (POST)',
                '/machine/<id>/health',
                '/machine/<id>/history',
                '/work-orders',
                '/work-orders (POST)'
            ]
        }
    }
    
    return jsonify({
        'status': 'success',
        'features': status,
        'base_url': '/api/modules'
    })


def register_module_features(app):
    """Register all module feature routes with Flask app"""
    app.register_blueprint(module_features_bp)
    print('[SIAS] Module features registered successfully')
