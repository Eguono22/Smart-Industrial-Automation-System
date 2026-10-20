"""Main application access checks; mock only the unrelated predictive engine."""
import importlib
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash
from app.auth import create_user
from app.models.assets import AssetRegistry


class ServerAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = os.path.join(cls.tmp.name, 'sias.sqlite3')
        predictor = types.ModuleType('app.models.predictor')
        class Engine:
            def update(self, data):
                return {}
        predictor.PredictiveMaintenanceEngine = Engine
        cls.environment = patch.dict(os.environ, {'VERCEL': '1', 'SIAS_DATABASE_PATH': cls.path})
        cls.environment.start()
        with patch.dict(sys.modules, {'app.models.predictor': predictor}):
            cls.server = importlib.import_module('server')
        cls.registry = AssetRegistry(cls.path)
        # Fast fixture hash keeps socket integration tests focused on access control.
        hashed = generate_password_hash('test-password-long', method='pbkdf2:sha256:1000')
        with patch('app.auth.generate_password_hash', return_value=hashed):
            create_user(cls.registry, dict(username='operator', name='Operator', role='admin', password='test-password-long'))
            customer = cls.registry.save('customers', dict(name='Customer', industry='water'))
            create_user(cls.registry, dict(username='viewer', name='Viewer', role='viewer', customer_id=customer['id'], password='test-password-long'))

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()
        cls.tmp.cleanup()
        sys.modules.pop('server', None)

    def setUp(self):
        self.client = self.server.app.test_client()

    def login(self, username):
        csrf = self.client.get('/api/auth/me').get_json()['csrf_token']
        response = self.client.post('/api/auth/login', json=dict(username=username, password='test-password-long'), headers={'X-CSRF-Token': csrf})
        self.assertEqual(response.status_code, 200)
        return response.get_json()['csrf_token']

    def test_home_uses_shared_copyright_footer_without_biography(self):
        html = self.client.get('/').get_data(as_text=True)
        self.assertEqual(html.count('<footer'), 1)
        self.assertIn('© 2026 SIAS Hub. All rights reserved.', html)
        self.assertIn('Third-party material retains', html)
        self.assertNotIn('Eguonoroghene Adomi', html)
        self.assertNotIn('href="/founder"', html)

    def test_shared_machine_endpoints_require_admin(self):
        self.assertEqual(self.client.get('/api/sensors').status_code, 401)
        self.login('viewer')
        for path in ['/api/sensors', '/api/plc/status', '/api/prediction', '/metrics', '/dashboard', '/plc-monitor', '/maintenance']:
            self.assertEqual(self.client.get(path).status_code, 403, path)
        self.assertEqual(self.client.get('/assets').status_code, 200)
        self.assertEqual(self.client.get('/work-orders').status_code, 200)

    def test_socket_rejection_and_logout_revocation(self):
        socket = self.server.socketio.test_client(self.server.app, flask_test_client=self.client)
        self.assertFalse(socket.is_connected())
        token = self.login('operator')
        socket = self.server.socketio.test_client(self.server.app, flask_test_client=self.client)
        self.assertTrue(socket.is_connected())
        self.server._broadcast_update({'test': True})
        self.assertTrue(any(event['name'] == 'data_update' for event in socket.get_received()))
        self.assertEqual(self.client.post('/api/auth/logout', headers={'X-CSRF-Token': token}).status_code, 200)
        self.server._broadcast_update({'test': False})
        self.assertFalse(socket.is_connected())

    def test_operations_requires_login_and_limits_modules_by_role(self):
        for path in ['/operations', '/operations/assets', '/operations/users']:
            self.assertEqual(self.client.get(path).location, '/login', path)
        self.login('viewer')
        response = self.client.get('/operations')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('href="/assets"', html)
        self.assertNotIn('href="/users"', html)
        self.assertNotIn('Example preview', html)
        self.assertEqual(self.client.get('/operations/assets').location, '/assets')
        self.assertEqual(self.client.get('/operations/users').status_code, 403)
        self.assertEqual(self.client.get('/users').status_code, 403)
        self.assertEqual(self.client.get('/industry-hub').status_code, 200)

    def test_administrator_operations_opens_existing_modules(self):
        self.login('operator')
        html = self.client.get('/operations').get_data(as_text=True)
        self.assertIn('href="/users"', html)
        for module in ['assets', 'work-orders', 'telemetry', 'notifications', 'users']:
            self.assertEqual(self.client.get('/operations/' + module).location, '/' + module)
        self.assertEqual(self.client.get('/operations/industries').location, '/industry-hub')

    def test_customer_socket_rejected(self):
        self.login('viewer')
        socket = self.server.socketio.test_client(self.server.app, flask_test_client=self.client)
        self.assertFalse(socket.is_connected())
