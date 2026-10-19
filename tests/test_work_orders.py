"""Work order lifecycle, history, validation and persistence integration tests."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from flask import Flask
from app.asset_routes import assets_bp
from app.models.assets import AssetRegistry


class WorkOrderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.directory.name, 'sias.sqlite3')
        self.app = Flask(__name__, template_folder=os.path.abspath('app/templates'))
        self.app.config.update(TESTING=True, SIAS_DATABASE_PATH=self.path)
        self.app.register_blueprint(assets_bp)
        self.client = self.app.test_client()
        registry = AssetRegistry(self.path)
        customer = registry.save('customers', {'name': 'Owner', 'industry': 'water'})
        site = registry.save('sites', {'name': 'Plant', 'customer_id': customer['id']})
        self.asset = registry.save('assets', {'name': 'Pump', 'asset_type': 'Pump', 'site_id': site['id']})
        self.today = datetime.now(timezone.utc).date()
        self.payload = dict(asset_id=self.asset['id'], title='Inspect pump seal', due_date=self.today.isoformat())

    def tearDown(self):
        self.directory.cleanup()

    def create(self, **overrides):
        response = self.client.post('/api/work-orders', json={**self.payload, **overrides})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['record']

    def patch(self, record, **values):
        return self.client.patch(f"/api/work-orders/{record['id']}", json=values)

    def detail(self, record):
        return self.client.get(f"/api/work-orders/{record['id']}").get_json()['record']

    def test_lifecycle_and_history_persist(self):
        record = self.create(assignee='Team A', description='Check leakage')
        self.assertEqual(record['status'], 'open')
        self.assertEqual(self.patch(record, status='in_progress', priority='high').status_code, 200)
        self.assertEqual(self.patch(record, status='completed', completion_notes='Seal replaced').status_code, 200)
        detail = self.detail(record)
        self.assertIsNotNone(detail['completed_at'])
        self.assertEqual([event['snapshot']['status'] for event in detail['history']], ['open', 'in_progress', 'completed'])
        self.assertEqual(detail['history'][0]['snapshot']['priority'], 'medium')
        self.assertEqual(detail['completion_notes'], 'Seal replaced')
        self.assertEqual(AssetRegistry(self.path).work_order_detail(record['id']), detail)
        listed = self.client.get('/api/work-orders').get_json()['work_orders'][0]
        self.assertEqual((listed['asset_name'], listed['site_name'], listed['customer_name']), ('Pump', 'Plant', 'Owner'))

    def test_completion_requires_notes_and_invalid_change_is_atomic(self):
        record = self.create()
        self.assertEqual(self.patch(record, status='completed').status_code, 400)
        self.assertEqual(self.patch(record, status='completed', completion_notes='  ').status_code, 400)
        detail = self.detail(record)
        self.assertEqual(detail['status'], 'open')
        self.assertEqual(len(detail['history']), 1)
        self.assertIsNone(detail['completed_at'])

    def test_overdue_boundaries_and_closed_tasks(self):
        yesterday = (self.today - timedelta(days=1)).isoformat()
        old = self.create(due_date=yesterday)
        self.assertTrue(old['overdue'])
        self.assertFalse(self.create()['overdue'])
        self.assertFalse(self.create(due_date=(self.today + timedelta(days=1)).isoformat())['overdue'])
        self.assertFalse(self.patch(old, status='cancelled').get_json()['record']['overdue'])
        completed = self.create(due_date=yesterday, status='completed', completion_notes='Done')
        self.assertFalse(completed['overdue'])

    def test_reopening_and_noop_edits(self):
        record = self.create(status='completed', completion_notes='Done')
        response = self.patch(record, assignee='Team B').get_json()['record']
        self.assertEqual(response['completed_at'], record['completed_at'])
        count = len(self.detail(record)['history'])
        self.assertEqual(self.patch(record, assignee='Team B').status_code, 200)
        self.assertEqual(len(self.detail(record)['history']), count)
        reopened = self.patch(record, status='open').get_json()['record']
        self.assertIsNone(reopened['completed_at'])
        self.assertEqual(reopened['completion_notes'], 'Done')
        self.assertEqual(len(self.detail(record)['history']), count + 1)

    def test_invalid_payloads(self):
        invalid = [None, [], {'id': 99}, {'title': '  '}, {'asset_id': True}, {'asset_id': 9999},
                   {'status': 'invalid'}, {'priority': 'urgent'}, {'due_date': '2026-02-30'},
                   {'due_date': '2026-1-01'}, {'due_date': '2026-01-01T00:00:00'},
                   {'description': 'x' * 4001}, {'assignee': 42}]
        for change in invalid:
            payload = {**self.payload, **change} if isinstance(change, dict) else change
            with self.subTest(payload=str(payload)[:120]):
                response = self.client.post('/api/work-orders', json=payload)
                self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(self.client.get('/api/work-orders').get_json()['work_orders'], [])

    def test_original_asset_and_history_are_protected(self):
        record = self.create()
        self.assertEqual(self.client.delete(f"/api/registry/assets/{self.asset['id']}").status_code, 409)
        self.assertEqual(self.patch(record, asset_id=self.asset['id'] + 1).status_code, 409)
        self.assertEqual(self.client.delete(f"/api/work-orders/{record['id']}").status_code, 405)
        self.assertEqual(len(self.detail(record)['history']), 1)

    def test_missing_records_and_rendering(self):
        self.assertEqual(self.client.get('/api/work-orders/9999').status_code, 404)
        self.assertEqual(self.client.patch('/api/work-orders/9999', json={'title': 'X'}).status_code, 404)
        response = self.client.get('/work-orders')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'work-form', response.data)
        self.assertIn(b'work-overdue', response.data)
        self.assertIn(b'work-filter-asset', response.data)


if __name__ == '__main__':
    unittest.main()
