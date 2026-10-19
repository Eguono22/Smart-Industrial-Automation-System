"""Asset registry routes, registered on the main SIAS Flask application."""
import sqlite3
from flask import Blueprint, current_app, jsonify, render_template, request, g
from app.models.assets import AssetRegistry, RegistryError
from app.models.hub import INDUSTRIES

assets_bp = Blueprint('assets', __name__)


def registry():
    return AssetRegistry(current_app.config['SIAS_DATABASE_PATH'])


@assets_bp.errorhandler(RegistryError)
def registry_error(error):
    return jsonify(ok=False, error=str(error)), error.status


@assets_bp.errorhandler(sqlite3.IntegrityError)
def relationship_error(error):
    return jsonify(ok=False, error='A related record changed. Refresh the registry and try again.'), 409


@assets_bp.errorhandler(sqlite3.OperationalError)
def storage_error(error):
    current_app.logger.error('Asset database unavailable: %s', error)
    return jsonify(ok=False, error='Asset storage unavailable. Check the server database configuration.'), 503


@assets_bp.route('/assets')
def asset_page():
    return render_template('assets.html', industries=INDUSTRIES)


@assets_bp.route('/api/registry')
def asset_snapshot():
    return jsonify(ok=True, **registry().snapshot(g.get('user')))


@assets_bp.route('/api/registry/<kind>', methods=['POST'])
@assets_bp.route('/api/registry/<kind>/<int:record_id>', methods=['PATCH'])
def save_record(kind, record_id=None):
    record = registry().save(kind, request.get_json(silent=True), record_id, actor=g.get('user'))
    return jsonify(ok=True, record=record), 201 if record_id is None else 200


@assets_bp.route('/api/registry/<kind>/<int:record_id>', methods=['DELETE'])
def delete_record(kind, record_id):
    registry().delete(kind, record_id, actor=g.get('user'))
    return jsonify(ok=True)


@assets_bp.route('/work-orders')
def work_orders_page():
    return render_template('work_orders.html')


@assets_bp.route('/api/work-orders', methods=['GET', 'POST'])
def work_orders():
    if request.method == 'POST':
        record = registry().save_work_order(request.get_json(silent=True), actor=g.get('user'))
        return jsonify(ok=True, record=record), 201
    records = registry().work_orders(g.get('user'))
    return jsonify(ok=True, work_orders=records)


@assets_bp.route('/api/work-orders/<int:record_id>', methods=['GET', 'PATCH'])
def work_order(record_id):
    if request.method == 'PATCH':
        record = registry().save_work_order(request.get_json(silent=True), record_id, actor=g.get('user'))
    else:
        record = registry().work_order_detail(record_id, actor=g.get('user'))
    return jsonify(ok=True, record=record)
