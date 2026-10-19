"""Asset credentials, scoped telemetry, freshness, validation and retention."""
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from flask import Flask
from werkzeug.security import generate_password_hash
from app.auth import create_user, install_auth
from app.asset_routes import assets_bp
from app.models.assets import AssetRegistry, RegistryError
from app.telemetry import telemetry_bp, ingest_batch, rotate_credential, telemetry_snapshot, HISTORY_LIMIT


class TelemetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hashed = generate_password_hash('test-password-long', method='pbkdf2:sha256:1000')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = AssetRegistry(os.path.join(self.tmp.name, 'sias.sqlite3'))
        self.customers, self.assets = [], []
        for name in ['A', 'B']:
            customer = self.store.save('customers', dict(name=name, industry='water'))
            self.customers.append(customer)
            site = self.store.save('sites', dict(name=name, customer_id=customer['id']))
            self.assets.append(self.store.save('assets', dict(name='Pump ' + name, site_id=site['id'], asset_type='Pump')))
        self.users = {}
        with patch('app.auth.generate_password_hash', return_value=self.hashed):
            for name, role, owner in [('admin', 'admin', None), ('manager', 'manager', 0), ('viewer', 'viewer', 0), ('technician', 'technician', 0), ('other', 'manager', 1)]:
                self.users[name] = create_user(self.store, dict(username=name, name=name, role=role, password='test-password-long', customer_id=self.customers[owner]['id'] if owner is not None else None))
            self.app = Flask(__name__, template_folder=os.path.abspath('app/templates'))
            self.app.config.update(TESTING=True, SIAS_DATABASE_PATH=self.store.path)
            self.app.register_blueprint(assets_bp)
            self.app.register_blueprint(telemetry_bp)
            install_auth(self.app)
        self.client = self.app.test_client()
        self.asset = self.assets[0]['id']
        self.token = rotate_credential(self.store, self.asset, self.users['admin'])
        self.payload = {'readings': {'temperature': {'value': 71.2, 'unit': '°C'}, 'flow': {'value': 10, 'unit': 'L/min'}}}
        self.now = datetime.now(timezone.utc)

    def login(self, username):
        csrf = self.client.get('/api/auth/me').get_json()['csrf_token']
        response = self.client.post('/api/auth/login', json=dict(username=username, password='test-password-long'), headers={'X-CSRF-Token': csrf})
        self.assertEqual(response.status_code, 200)
        return {'X-CSRF-Token': response.get_json()['csrf_token']}

    def post(self, payload=None, token=None, asset=None):
        return self.client.post(f'/api/telemetry/{asset or self.asset}/readings', json=self.payload if payload is None else payload,
            headers={'Authorization': 'Bearer ' + (token or self.token)})

    def test_device_ingestion_persists_and_never_grants_reads(self):
        response = self.post()
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(self.client.get(f'/api/telemetry/{self.asset}', headers={'Authorization': 'Bearer ' + self.token}).status_code, 401)
        self.login('viewer')
        result = self.client.get(f'/api/telemetry/{self.asset}').get_json()
        self.assertEqual(result['connection_status'], 'connected')
        self.assertEqual(result['latest']['readings'], self.payload['readings'])
        self.assertNotIn(self.token, json.dumps(result))
        self.assertNotIn('token_hash', json.dumps(result))
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT token_hash FROM device_credentials').fetchone()[0], hashlib.sha256(self.token.encode()).hexdigest())
        self.assertEqual(telemetry_snapshot(AssetRegistry(self.store.path), self.asset, self.users['viewer'])['latest'], result['latest'])

    def test_wrong_asset_wrong_token_and_rotation(self):
        self.assertEqual(self.post(asset=self.assets[1]['id']).status_code, 401)
        self.assertEqual(self.post(token='x' * 43).status_code, 401)
        replacement = rotate_credential(self.store, self.asset, self.users['manager'])
        self.assertEqual(self.post().status_code, 401)
        self.assertEqual(self.post(token=replacement).status_code, 201)
        rotate_credential(self.store, self.asset, self.users['manager'], revoke=True)
        self.assertEqual(self.post(token=replacement).status_code, 401)

    def test_customer_boundaries_and_credential_permissions(self):
        headers = self.login('other')
        self.assertEqual(self.client.get(f'/api/telemetry/{self.asset}').status_code, 404)
        self.assertEqual(self.client.post(f'/api/telemetry/{self.asset}/credential', headers=headers).status_code, 404)
        for username in ['technician', 'viewer']:
            headers = self.login(username)
            self.assertEqual(self.client.get(f'/api/telemetry/{self.asset}').status_code, 200)
            self.assertEqual(self.client.post(f'/api/telemetry/{self.asset}/credential', headers=headers).status_code, 403)
        headers = self.login('manager')
        self.assertEqual(self.client.post(f'/api/telemetry/{self.asset}/credential').status_code, 403)
        response = self.client.post(f'/api/telemetry/{self.asset}/credential', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers['Cache-Control'])

    def test_freshness_uses_measurement_time_and_out_of_order_packets(self):
        state = telemetry_snapshot(self.store, self.asset, self.users['viewer'], now=self.now)
        self.assertEqual(state['connection_status'], 'never_seen')
        ingest_batch(self.store, self.asset, self.token, self.payload, now=self.now)
        state = telemetry_snapshot(self.store, self.asset, self.users['viewer'], now=self.now + timedelta(seconds=120))
        self.assertEqual(state['connection_status'], 'connected')
        old = dict(self.payload, timestamp=(self.now - timedelta(minutes=10)).isoformat())
        ingest_batch(self.store, self.asset, self.token, old, now=self.now + timedelta(seconds=121))
        state = telemetry_snapshot(self.store, self.asset, self.users['viewer'], now=self.now + timedelta(seconds=121))
        self.assertEqual(state['connection_status'], 'stale')
        self.assertEqual(state['latest']['timestamp'], self.now.isoformat())
        self.assertEqual(len(state['history']), 2)

    def test_malformed_and_nonfinite_values_rejected_without_storing(self):
        invalid = [[], {}, {'readings': {}}, {'extra': True, **self.payload},
            {'readings': {'x': {'value': True, 'unit': 'A'}}},
            {'readings': {'x': {'value': float('nan'), 'unit': 'A'}}},
            {'readings': {'x': {'value': float('inf'), 'unit': 'A'}}},
            {'readings': {'bad name': {'value': 1, 'unit': 'A'}}},
            {'readings': {'x': {'value': 1, 'unit': ''}}},
            {'readings': {'x': {'value': 1}}},
            dict(self.payload, timestamp='2026-01-01'),
            dict(self.payload, timestamp=(self.now + timedelta(minutes=5)).isoformat()),
            dict(self.payload, timestamp=(self.now - timedelta(days=31)).isoformat())]
        for payload in invalid:
            with self.subTest(payload=str(payload)[:100]):
                self.assertEqual(self.post(payload=payload).status_code, 400)
        self.assertEqual(telemetry_snapshot(self.store, self.asset, self.users['admin'])['history'], [])
        self.assertEqual(self.client.post(f'/api/telemetry/{self.asset}/readings', data='x' * 32769, content_type='application/json').status_code, 413)

    def test_history_bound_and_unit_changes_are_preserved(self):
        with self.store.connect() as db:
            for index in range(HISTORY_LIMIT + 2):
                stamp = (self.now - timedelta(seconds=index + 1)).isoformat()
                db.execute('INSERT INTO telemetry_batches (asset_id, measured_at, received_at, readings) VALUES (?, ?, ?, ?)', (self.asset, stamp, stamp, json.dumps(self.payload['readings'])))
        ingest_batch(self.store, self.asset, self.token, {'readings': {'temperature': {'value': 160, 'unit': '°F'}}}, now=self.now)
        result = telemetry_snapshot(self.store, self.asset, self.users['admin'], limit=300)
        self.assertEqual(len(result['history']), HISTORY_LIMIT)
        self.assertEqual(result['latest']['readings']['temperature']['unit'], '°F')
        self.assertEqual(result['history'][1]['readings']['temperature']['unit'], '°C')
        delayed_receive = self.now + timedelta(seconds=10)
        ingest_batch(self.store, self.asset, self.token, dict(self.payload, timestamp=(self.now - timedelta(days=1)).isoformat()), now=delayed_receive)
        result = telemetry_snapshot(self.store, self.asset, self.users['admin'], limit=300)
        self.assertEqual(result['last_received_at'], delayed_receive.isoformat())
        self.assertEqual(len(result['history']), HISTORY_LIMIT)
        self.assertEqual(result['latest']['timestamp'], self.now.isoformat())

    def test_history_prevents_cross_customer_move_and_deletion(self):
        self.post()
        destination = self.store.snapshot()['sites'][1]['id']
        with self.assertRaises(RegistryError):
            self.store.save('assets', {'site_id': destination}, self.asset, actor=self.users['admin'])
        with self.assertRaises(RegistryError):
            self.store.delete('assets', self.asset, actor=self.users['admin'])

    def test_old_credentials_do_not_follow_an_empty_asset_between_customers(self):
        destination = self.store.snapshot()['sites'][1]['id']
        self.store.save('assets', {'site_id': destination}, self.asset, actor=self.users['admin'])
        self.assertEqual(self.post().status_code, 401)
        self.store.save('assets', {'site_id': self.assets[0]['site_id']}, self.asset, actor=self.users['admin'])
        self.assertEqual(self.post().status_code, 401)

    def test_page_and_history_limit_validation(self):
        self.login('viewer')
        self.assertEqual(self.client.get('/telemetry').status_code, 200)
        for limit in ['0', '301', 'x']:
            self.assertEqual(self.client.get(f'/api/telemetry/{self.asset}?limit={limit}').status_code, 400)
        self.assertEqual(self.client.get('/api/telemetry/9999').status_code, 404)
