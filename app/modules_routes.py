"""
3SIAS Modules API Routes
Provides endpoints to interact with integrated 3SIAS modules.
"""

from flask import Blueprint, jsonify, request
from app.modules_integration import ModuleRegistry, get_module_status

modules_bp = Blueprint('modules', __name__, url_prefix='/api/modules')


@modules_bp.route('/status', methods=['GET'])
def get_modules_status():
    """Get status of all integrated modules."""
    return jsonify(get_module_status())


@modules_bp.route('/<module_name>/status', methods=['GET'])
def get_module_status_detail(module_name):
    """Get detailed status of a specific module."""
    module = ModuleRegistry.get(module_name)
    
    if not module:
        return jsonify({'error': f'Module {module_name} not found'}), 404
    
    status = {
        'name': module_name,
        'available': True,
        'has_routes': hasattr(module, 'register_routes'),
    }
    
    # Include module-specific status if available
    if hasattr(module, 'get_status'):
        try:
            status['module_status'] = module.get_status()
        except Exception as e:
            status['status_error'] = str(e)
    
    return jsonify(status)


@modules_bp.route('/<module_name>/action', methods=['POST'])
def execute_module_action(module_name):
    """Execute an action in a specific module."""
    module = ModuleRegistry.get(module_name)
    
    if not module:
        return jsonify({'error': f'Module {module_name} not found'}), 404
    
    data = request.get_json()
    action = data.get('action')
    params = data.get('params', {})
    
    if not hasattr(module, 'execute_action'):
        return jsonify({
            'error': f'Module {module_name} does not support actions'
        }), 400
    
    try:
        result = module.execute_action(action, **params)
        return jsonify({'result': result, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 400


def register_modules_routes(app):
    """Register module routes with the Flask app."""
    app.register_blueprint(modules_bp)
