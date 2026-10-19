"""Customer-scoped equipment telemetry over authenticated HTTP."""
import hashlib
import json
import math
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, g, jsonify, render_template, request
from app.models.assets import AssetRegistry, RegistryError

telemetry_bp = Blueprint('telemetry', __name__)
HISTORY_LIMIT = 300
STALE_SECONDS = 120


def registry():
    return AssetRegistry(current_app.config['SIAS_DATABASE_PATH'])


def rotate_credential(store, asset_id, actor, revoke=False):
    store.require_role(actor, 'admin', 'manager')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        store.authorize(db, 'assets', asset_id, actor)
        row = db.execute('SELECT s.customer_id FROM assets a JOIN sites s ON s.id=a.site_id WHERE a.id=?', (asset_id,)).fetchone()
        if not row:
            raise RegistryError('Asset not found', 404)
        if revoke:
            db.execute('DELETE FROM device_credentials WHERE asset_id=?', (asset_id,))
            return None
        token = secrets.token_urlsafe(32)
        db.execute('''INSERT INTO device_credentials (asset_id, token_hash, customer_id, rotated_at)
            VALUES (?, ?, ?, ?) ON CONFLICT(asset_id) DO UPDATE SET
            token_hash=excluded.token_hash, customer_id=excluded.customer_id, rotated_at=excluded.rotated_at''',
            (asset_id, hashlib.sha256(token.encode()).hexdigest(), row['customer_id'], datetime.now(timezone.utc).isoformat()))
        return token


def parse_batch(data, now):
    if not isinstance(data, dict) or set(data) - {'timestamp', 'readings'}:
        raise RegistryError('Provide timestamp (optional) and readings in a JSON object')
    readings = data.get('readings')
    if not isinstance(readings, dict) or not 1 <= len(readings) <= 32:
        raise RegistryError('readings must contain 1 to 32 sensor channels')
    clean = {}
    for name, reading in readings.items():
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', name):
            raise RegistryError('Sensor names must use lowercase letters, digits or underscores and start with a letter (max 64 characters)')
        if not isinstance(reading, dict) or set(reading) != {'value', 'unit'}:
            raise RegistryError('Each sensor requires exactly value and unit')
        value, unit = reading['value'], reading['unit']
        if type(value) not in (int, float):
            raise RegistryError('Sensor values must be finite numbers')
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise RegistryError('Sensor values must be finite numbers')
        if not isinstance(unit, str) or not unit.strip() or len(unit) > 32 or not unit.isprintable():
            raise RegistryError('Sensor units must contain 1 to 32 printable characters')
        clean[name] = dict(value=value, unit=unit.strip())
    measured = now
    if 'timestamp' in data:
        timestamp = data['timestamp']
        try:
            if not isinstance(timestamp, str) or len(timestamp) > 40:
                raise ValueError()
            measured = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            if measured.tzinfo is None:
                raise ValueError()
            measured = measured.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            raise RegistryError('timestamp must be an ISO 8601 timestamp with timezone') from None
    if measured > now + timedelta(seconds=30) or measured < now - timedelta(days=30):
        raise RegistryError('timestamp must be within the last 30 days and no more than 30 seconds ahead')
    return measured.isoformat(), clean


def ingest_batch(store, asset_id, token, data, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(token, str) or not 20 <= len(token) <= 200:
        raise RegistryError('Invalid device credential', 401)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        credential = db.execute('''SELECT d.token_hash FROM device_credentials d
            JOIN assets a ON a.id=d.asset_id JOIN sites s ON s.id=a.site_id
            WHERE d.asset_id=? AND d.customer_id=s.customer_id''', (asset_id,)).fetchone()
        if not credential or not secrets.compare_digest(credential['token_hash'], hashlib.sha256(token.encode()).hexdigest()):
            raise RegistryError('Invalid device credential', 401)
        measured, readings = parse_batch(data, now)
        cursor = db.execute('INSERT INTO telemetry_batches (asset_id, measured_at, received_at, readings) VALUES (?, ?, ?, ?)',
                            (asset_id, measured, now.isoformat(), json.dumps(readings, allow_nan=False)))
        record_id = cursor.lastrowid
        db.execute('''INSERT INTO telemetry_state (asset_id, last_received_at) VALUES (?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET last_received_at=MAX(telemetry_state.last_received_at, excluded.last_received_at)''', (asset_id, now.isoformat()))
        # A bounded per-asset history prevents unbounded growth from regular polling.
        db.execute('''DELETE FROM telemetry_batches WHERE asset_id=? AND id NOT IN (
            SELECT id FROM telemetry_batches WHERE asset_id=? ORDER BY measured_at DESC, id DESC LIMIT ?)''', (asset_id, asset_id, HISTORY_LIMIT))
        return dict(id=record_id, asset_id=asset_id, timestamp=measured, received_at=now.isoformat())


def telemetry_snapshot(store, asset_id, actor, limit=60, now=None):
    now = now or datetime.now(timezone.utc)
    with store.connect() as db:
        store.authorize(db, 'assets', asset_id, actor)
        asset = db.execute('SELECT * FROM assets WHERE id=?', (asset_id,)).fetchone()
        if not asset:
            raise RegistryError('Asset not found', 404)
        batches = [dict(id=row['id'], timestamp=row['measured_at'], received_at=row['received_at'], readings=json.loads(row['readings']))
                   for row in db.execute('SELECT * FROM telemetry_batches WHERE asset_id=? ORDER BY measured_at DESC, id DESC LIMIT ?', (asset_id, limit))]
        credential = db.execute('''SELECT d.rotated_at FROM device_credentials d JOIN sites s ON s.id=?
            WHERE d.asset_id=? AND d.customer_id=s.customer_id''', (asset['site_id'], asset_id)).fetchone()
        latest = batches[0] if batches else None
        age = max(0, (now - datetime.fromisoformat(latest['timestamp'])).total_seconds()) if latest else None
        received_row = db.execute('SELECT last_received_at FROM telemetry_state WHERE asset_id=?', (asset_id,)).fetchone()
        received = received_row[0] if received_row else (max(batch['received_at'] for batch in batches) if batches else None)
        return dict(asset=dict(asset), connection_status='never_seen' if latest is None else 'stale' if age > STALE_SECONDS else 'connected',
                    stale_after_seconds=STALE_SECONDS, age_seconds=age, last_received_at=received,
                    credential_configured=credential is not None, credential_rotated_at=credential['rotated_at'] if credential else None,
                    latest=latest, history=batches)


@telemetry_bp.errorhandler(RegistryError)
def telemetry_error(error):
    return jsonify(ok=False, error=str(error)), error.status


@telemetry_bp.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@telemetry_bp.route('/telemetry')
def telemetry_page():
    return render_template('telemetry.html')


@telemetry_bp.route('/api/telemetry/<int:asset_id>/credential', methods=['POST', 'DELETE'])
def credential(asset_id):
    token = rotate_credential(registry(), asset_id, g.user, revoke=request.method == 'DELETE')
    return jsonify(ok=True, token=token)


@telemetry_bp.route('/api/telemetry/<int:asset_id>/readings', methods=['POST'])
def ingest(asset_id):
    # Bearer credentials authorize this write only, never account reads or controls.
    authorization = request.headers.get('Authorization', '')
    token = authorization[7:] if authorization.startswith('Bearer ') else ''
    if request.content_length is not None and request.content_length > 32768:
        raise RegistryError('Payload exceeds 32 KiB', 413)
    raw = request.stream.read(32769)
    if len(raw) > 32768:
        raise RegistryError('Payload exceeds 32 KiB', 413)
    try:
        data = json.loads(raw) if request.is_json else None
    except (ValueError, UnicodeDecodeError):
        data = None
    return jsonify(ok=True, record=ingest_batch(registry(), asset_id, token, data)), 201


@telemetry_bp.route('/api/telemetry/<int:asset_id>')
def snapshot(asset_id):
    try:
        limit = int(request.args.get('limit', '60'))
        if not 1 <= limit <= HISTORY_LIMIT:
            raise ValueError()
    except ValueError:
        raise RegistryError('limit must be an integer from 1 to 300') from None
    return jsonify(ok=True, **telemetry_snapshot(registry(), asset_id, g.user, limit))
