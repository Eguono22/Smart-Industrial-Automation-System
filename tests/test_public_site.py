"""Original SIAS application works on Vercel without database or hardware access."""
import re
import unittest
from unittest.mock import patch

from demo_app import create_demo_app


class PublicSiteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_demo_app()
        self.app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
        self.client = self.app.test_client()
        html = self.client.get('/').get_data(as_text=True)
        self.csrf = re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)

    def post(self, path, data=None):
        return self.client.post(path, json=data, headers={'X-CSRF-Token': self.csrf})

    def test_original_pages_and_live_payload_need_no_database(self):
        with patch('sqlite3.connect', side_effect=AssertionError('Simulator must not open SQLite')):
            for path in ['/', '/dashboard', '/plc-monitor', '/maintenance', '/health', '/ready']:
                self.assertEqual(self.client.get(path).status_code, 200, path)
            html = self.client.get('/').get_data(as_text=True)
            self.assertIn('Smart Industrial Automation System', html)
            self.assertIn('href="/dashboard"', html)
            self.assertIn('href="/plc-monitor"', html)
            self.assertIn('href="/maintenance"', html)
            self.assertNotIn('Build a solution plan', html)
            self.assertNotIn('sias-light bg-light', html)
            self.assertNotIn('href="/founder"', html)
            self.assertIn('© 2026 SIAS Hub. All rights reserved.', html)
            payload = self.client.get('/api/demo/data').get_json()
            self.assertEqual(len(payload['sensors']), 6)
            self.assertEqual(payload['plc']['plc_mode'], 'sim')
            self.assertIn('health_score', payload['prediction'])

    def test_machine_controls_and_estop(self):
        self.assertEqual(self.post('/api/plc/stop').status_code, 200)
        self.assertFalse(self.client.get('/api/plc/status').get_json()['coils']['motor_run']['state'])
        self.post('/api/plc/start')
        self.assertTrue(self.client.get('/api/plc/status').get_json()['coils']['motor_run']['state'])
        self.post('/api/plc/estop')
        self.assertFalse(self.client.get('/api/plc/status').get_json()['coils']['motor_run']['state'])
        self.post('/api/plc/start')
        self.assertFalse(self.client.get('/api/plc/status').get_json()['coils']['motor_run']['state'])
        self.post('/api/plc/reset-estop')
        self.post('/api/plc/start')
        self.assertTrue(self.client.get('/api/plc/status').get_json()['coils']['motor_run']['state'])

    def test_operations_previews_do_not_open_customer_database(self):
        with patch('sqlite3.connect', side_effect=AssertionError('Preview must not open SQLite')):
            overview = self.client.get('/operations').get_data(as_text=True)
            self.assertIn('Workspace preview', overview)
            self.assertIn('not connected to this deployment yet', overview)
            for module in ['assets', 'work-orders', 'telemetry', 'notifications', 'users']:
                response = self.client.get('/operations/' + module)
                self.assertEqual(response.status_code, 200, module)
                html = response.get_data(as_text=True)
                self.assertIn('Example records only.', html)
                self.assertIn('id="module-search"', html)
                self.assertNotIn('type="password"', html)
            self.assertEqual(self.client.get('/operations/unknown').status_code, 404)
        self.assertEqual(self.client.get('/api/registry').status_code, 404)

    def test_operations_navigation_preserves_machine_state_and_industry_planning(self):
        self.post('/api/plc/stop')
        html = self.client.get('/operations/assets').get_data(as_text=True)
        for path in ['/dashboard', '/plc-monitor', '/maintenance']:
            self.assertIn('href="' + path + '"', html)
        self.assertFalse(self.client.get('/api/plc/status').get_json()['coils']['motor_run']['state'])
        response = self.client.get('/operations/industries')
        self.assertEqual(response.location, '/industry-hub')
        html = self.client.get('/industry-hub').get_data(as_text=True)
        self.assertIn('id="plan-export"', html)
        self.assertIn('href="/dashboard"', html)
        self.assertNotIn('href="/assets"', html)
        self.assertEqual(self.client.get('/static/js/operations.js').status_code, 200)

    def test_optional_operations_workspace_links_require_clean_https_url(self):
        with patch.dict('os.environ', {'SIAS_OPERATIONS_URL': 'https://workspace.example.test/'}):
            html = self.client.get('/operations/assets').get_data(as_text=True)
            self.assertIn('href="https://workspace.example.test/assets"', html)
        for value in ['http://workspace.example.test', 'https://user:pass@example.test', 'https://example.test?token=private']:
            with patch.dict('os.environ', {'SIAS_OPERATIONS_URL': value}):
                with self.assertRaises(ValueError):
                    self.client.get('/operations')

    def test_simulator_is_isolated_between_browsers(self):
        self.post('/api/plc/stop')
        other = self.app.test_client()
        self.assertTrue(other.get('/api/plc/status').get_json()['coils']['motor_run']['state'])
        self.assertFalse(self.client.get('/api/plc/status').get_json()['coils']['motor_run']['state'])

    def test_controls_survive_worker_changes_with_shared_signing_secret(self):
        self.post('/api/plc/stop')
        cookie = self.client.get_cookie('session').value
        other_app = create_demo_app()
        other_app.config.update(TESTING=True, SECRET_KEY=self.app.secret_key, SESSION_COOKIE_SECURE=False)
        other = other_app.test_client()
        other.set_cookie('session', cookie)
        status = other.get('/api/plc/status').get_json()
        self.assertFalse(status['coils']['motor_run']['state'])
        self.post('/api/plc/estop')
        other.set_cookie('session', self.client.get_cookie('session').value)
        status = other.get('/api/plc/status').get_json()
        self.assertTrue(status['coils']['estop_latch']['state'])
        self.assertFalse(status['coils']['motor_run']['state'])
        self.assertLess(len(self.client.get_cookie('session').value), 3800)

    def test_commands_require_csrf_and_validate_input(self):
        self.assertEqual(self.client.post('/api/plc/stop').status_code, 403)
        self.assertEqual(self.post('/api/plc/monitor/command', {'command': 'bogus'}).status_code, 400)
        self.assertEqual(self.post('/api/fault/inject', {'sensor': 'invalid'}).status_code, 400)
        self.assertEqual(self.post('/api/fault/inject', {'sensor': 'temperature', 'magnitude': float('inf')}).status_code, 400)
        self.assertEqual(self.post('/api/plc/monitor/acknowledge', {}).status_code, 400)
        self.assertEqual(self.client.get('/api/sensors/history?n=invalid').status_code, 400)

    def test_fault_scenario_and_histories(self):
        self.assertEqual(self.post('/api/demo/start').status_code, 200)
        self.assertTrue(self.client.get('/api/demo/status').get_json()['demo']['active'])
        self.assertEqual(self.post('/api/demo/stop').status_code, 200)
        self.assertFalse(self.client.get('/api/demo/status').get_json()['demo']['active'])
        self.assertEqual(self.post('/api/fault/inject', {'sensor': 'temperature', 'magnitude': 3.0}).status_code, 200)
        self.assertEqual(self.post('/api/fault/clear').status_code, 200)
        self.assertTrue(self.client.get('/api/prediction/health-history').get_json())
        self.assertTrue(self.client.get('/api/prediction/anomaly-history').get_json())

    def test_no_customer_endpoints_or_real_plc_configuration(self):
        with patch.dict('os.environ', {'PLC_MODE': 'modbus', 'PLC_HOST': '192.0.2.1'}):
            app = create_demo_app()
            self.assertEqual(app.test_client().get('/api/plc/status').get_json()['plc_mode'], 'sim')
        for path in ['/api/auth/login', '/api/registry/customers', '/api/telemetry/1/credential']:
            self.assertEqual(self.post(path, {}).status_code, 404)
        self.assertEqual(self.client.get('/api/registry').status_code, 404)

    def test_prediction_is_memory_only(self):
        with patch('app.models.predictor.PredictiveMaintenanceEngine._load_model') as load:
            app = create_demo_app()
            client = app.test_client()
            client.get('/api/demo/data')
            load.assert_not_called()
        machine = next(iter(app.extensions['demo_machines'].values()))
        self.assertFalse(machine.predictor._persist_enabled)

    def test_static_assets_and_payload_not_cached(self):
        for path in ['/static/css/style.css', '/static/js/dashboard.js', '/static/vendor/chart.umd.min.js']:
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get('/api/demo/data').headers['Cache-Control'], 'no-store')
