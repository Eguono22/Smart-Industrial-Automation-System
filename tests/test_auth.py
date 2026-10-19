"""Exercise authentication and customer boundaries through the real Flask middleware."""
import os
import tempfile
import unittest
from unittest.mock import patch
from werkzeug.security import generate_password_hash

from flask import Flask
from app.auth import create_user, install_auth
from app.asset_routes import assets_bp
from app.models.assets import AssetRegistry


class AccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse a real production-strength fixture hash; login still verifies it.
        cls.fixture_hash = generate_password_hash('strong-test-password-123', method='pbkdf2:sha256:1000000')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'auth.sqlite3')
        self.registry = AssetRegistry(self.path)
        self.customers = [self.registry.save('customers', dict(name=name, industry='water')) for name in ['A', 'B']]
        self.assets = []
        for customer in self.customers:
            site = self.registry.save('sites', dict(name='Plant ' + customer['name'], customer_id=customer['id']))
            self.assets.append(self.registry.save('assets', dict(name='Pump ' + customer['name'], site_id=site['id'], asset_type='Pump')))
        self.password = 'strong-test-password-123'
        self.hash_patch = patch('app.auth.generate_password_hash', return_value=self.fixture_hash)
        self.hash_patch.start()
        self.addCleanup(self.hash_patch.stop)
        self.users = {}
        for role, customer in [('admin', None), ('manager', 0), ('technician', 0), ('viewer', 0), ('othertech', 1)]:
            self.users[role] = create_user(self.registry, dict(username=role, name=role, password=self.password,
                role='technician' if role == 'othertech' else role, customer_id=self.customers[customer]['id'] if customer is not None else None))
        self.app = Flask(__name__, template_folder=os.path.abspath('app/templates'))
        self.app.config.update(TESTING=True, SIAS_DATABASE_PATH=self.path)
        self.app.register_blueprint(assets_bp)
        install_auth(self.app)
        self.app.add_url_rule('/api/plc/start', view_func=lambda: {'ok': True}, methods=['POST'])
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def csrf(self):
        return self.client.get('/api/auth/me').get_json()['csrf_token']

    def send(self, path, data=None, method='POST', token=True):
        return self.client.open(path, method=method, json=data,
            headers={'X-CSRF-Token': self.csrf()} if token else {})

    def login(self, name='admin'):
        response = self.send('/api/auth/login', dict(username=name, password=self.password))
        self.assertEqual(response.status_code, 200, response.get_json())
        return response

    def order(self, asset=0, assignee=None):
        return self.registry.save_work_order(dict(asset_id=self.assets[asset]['id'], title='Inspect', due_date='2026-01-01', assignee_id=assignee))

    def test_anonymous_and_csrf_and_logout(self):
        self.assertEqual(self.client.get('/api/registry').status_code, 401)
        self.assertEqual(self.client.get('/assets').status_code, 302)
        self.assertEqual(self.send('/api/auth/login', dict(username='admin', password=self.password), token=False).status_code, 403)
        self.login()
        self.assertEqual(self.send('/api/registry/customers', dict(name='C', industry='water'), token=False).status_code, 403)
        cookie = self.client.get_cookie('session').value
        self.assertEqual(self.send('/api/auth/logout').status_code, 200)
        self.client.set_cookie('session', cookie)
        self.assertEqual(self.client.get('/api/registry').status_code, 401)

    def test_customer_lists_and_direct_id_boundaries(self):
        own, other = self.order(), self.order(1)
        self.login('manager')
        result = self.client.get('/api/registry').get_json()
        self.assertEqual([r['id'] for r in result['customers']], [self.customers[0]['id']])
        self.assertEqual([r['id'] for r in result['assets']], [self.assets[0]['id']])
        self.assertEqual([r['id'] for r in self.client.get('/api/work-orders').get_json()['work_orders']], [own['id']])
        for method in ['GET', 'PATCH']:
            self.assertEqual(self.send(f"/api/work-orders/{other['id']}", {'title': 'steal'}, method).status_code, 404)
        self.assertEqual(self.send(f"/api/registry/assets/{self.assets[1]['id']}", {'name': 'steal'}, 'PATCH').status_code, 404)
        self.assertEqual(self.send('/api/work-orders', dict(asset_id=self.assets[1]['id'], title='X', due_date='2026-01-01')).status_code, 404)
        self.assertEqual(self.client.get('/api/auth/users').status_code, 403)
        self.assertEqual(self.send('/api/plc/start').status_code, 403)

    def test_viewer_cannot_write_and_manager_cannot_create_customers(self):
        self.login('viewer')
        self.assertEqual(self.client.get('/api/registry').status_code, 200)
        self.assertEqual(self.send('/api/registry/sites', dict(name='X', customer_id=self.customers[0]['id'])).status_code, 403)
        self.assertEqual(self.send('/api/work-orders', dict(asset_id=self.assets[0]['id'], title='X', due_date='2026-01-01')).status_code, 403)
        self.send('/api/auth/logout')
        self.login('manager')
        self.assertEqual(self.send('/api/registry/customers', dict(name='X', industry='water')).status_code, 403)
        self.assertEqual(self.send('/api/registry/sites', dict(name='X', customer_id=self.customers[0]['id'])).status_code, 201)
        self.assertEqual(self.send('/api/registry/sites', dict(name='X', customer_id=self.customers[1]['id'])).status_code, 404)

    def test_registered_assignment_and_actor_history(self):
        self.login('manager')
        data = dict(asset_id=self.assets[0]['id'], title='Inspect', due_date='2026-01-01', assignee_id=self.users['technician']['id'])
        response = self.send('/api/work-orders', data)
        self.assertEqual(response.status_code, 201, response.get_json())
        order = response.get_json()['record']
        detail = self.client.get(f"/api/work-orders/{order['id']}").get_json()['record']
        self.assertEqual(detail['history'][0]['actor_id'], self.users['manager']['id'])
        self.assertEqual(detail['assignee'], 'technician')
        data['assignee_id'] = self.users['othertech']['id']
        self.assertEqual(self.send('/api/work-orders', data).status_code, 400)
        data.pop('assignee_id'); data['assignee'] = 'forged name'
        self.assertEqual(self.send('/api/work-orders', data).status_code, 400)
        self.assertEqual([u['id'] for u in self.client.get('/api/auth/technicians').get_json()['technicians']], [self.users['technician']['id']])

    def test_technician_only_updates_assigned_status_and_notes(self):
        assigned = self.order(assignee=self.users['technician']['id'])
        unassigned = self.order()
        self.login('technician')
        self.assertEqual(self.send(f"/api/work-orders/{assigned['id']}", {'status': 'completed', 'completion_notes': 'Done'}, 'PATCH').status_code, 200)
        detail = self.client.get(f"/api/work-orders/{assigned['id']}").get_json()['record']
        self.assertEqual(detail['history'][-1]['actor_name'], 'technician')
        self.assertEqual(self.send(f"/api/work-orders/{assigned['id']}", {'priority': 'low'}, 'PATCH').status_code, 403)
        self.assertEqual(self.send(f"/api/work-orders/{unassigned['id']}", {'status': 'in_progress'}, 'PATCH').status_code, 403)

    def test_account_updates_revoke_sessions_and_preserve_last_admin(self):
        self.login('manager')
        admin = self.app.test_client()
        old_client = self.client
        self.client = admin; self.login()
        response = self.send(f"/api/auth/users/{self.users['manager']['id']}", {'active': False}, 'PATCH')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(old_client.get('/api/registry').status_code, 401)
        self.assertEqual(self.send(f"/api/auth/users/{self.users['admin']['id']}", {'active': False}, 'PATCH').status_code, 409)
        self.assertNotIn('password_hash', str(self.client.get('/api/auth/users').get_json()))
        self.assertEqual(self.send('/api/auth/users', dict(username='short', name='Short', role='admin', password='weak')).status_code, 400)

    def test_login_failures_are_generic_and_throttled(self):
        for i in range(10):
            result = self.send('/api/auth/login', dict(username='unknown', password='wrong'))
            self.assertEqual(result.status_code, 401)
            self.assertEqual(result.get_json()['error'], 'Invalid credentials')
        self.assertEqual(self.send('/api/auth/login', dict(username='admin', password=self.password)).status_code, 429)

    def test_expired_session_and_public_pages(self):
        self.login()
        with self.registry.connect() as db:
            db.execute("UPDATE auth_sessions SET expires_at='2000-01-01'")
        self.assertEqual(self.client.get('/api/registry').status_code, 401)
        self.assertEqual(self.client.get('/login').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me').headers['Cache-Control'], 'no-store')

    def test_owner_transfer_with_history_is_blocked(self):
        self.order()
        self.login()
        destination = self.registry.snapshot()['sites'][1]
        self.assertEqual(self.send(f"/api/registry/assets/{self.assets[0]['id']}", {'site_id': destination['id']}, 'PATCH').status_code, 409)
        self.assertEqual(self.client.get('/users').status_code, 200)


class AuthMigrationTests(unittest.TestCase):
    def test_existing_work_orders_and_unknown_actors_survive_upgrade(self):
        import json
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'legacy.sqlite3')
            with sqlite3.connect(path) as db:
                db.executescript('''
                    CREATE TABLE work_orders (
                        id INTEGER PRIMARY KEY, asset_id INTEGER NOT NULL,
                        title TEXT NOT NULL, description TEXT NOT NULL,
                        priority TEXT NOT NULL, assignee TEXT NOT NULL,
                        due_date TEXT NOT NULL, status TEXT NOT NULL,
                        completion_notes TEXT NOT NULL, completed_at TEXT,
                        created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                    CREATE TABLE work_order_history (
                        id INTEGER PRIMARY KEY, work_order_id INTEGER NOT NULL,
                        changed_at TEXT NOT NULL, snapshot TEXT NOT NULL);
                    INSERT INTO work_orders VALUES
                        (1, 1, 'Legacy task', '', 'medium', 'Old team', '2026-01-01',
                         'open', '', NULL, '2026-01-01', '2026-01-01');
                ''')
                db.execute('INSERT INTO work_order_history VALUES (1, 1, ?, ?)',
                           ('2026-01-01', json.dumps({'title': 'Legacy task', 'assignee': 'Old team'})))
            upgraded = AssetRegistry(path).work_order_detail(1)
            self.assertEqual(upgraded['title'], 'Legacy task')
            self.assertEqual(upgraded['assignee'], 'Old team')
            self.assertIsNone(upgraded['assignee_id'])
            self.assertIsNone(upgraded['history'][0]['actor_id'])
            self.assertIsNone(upgraded['history'][0]['actor_name'])


if __name__ == '__main__':
    unittest.main()
