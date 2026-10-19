"""Persistent registry integration tests without the unrelated ML engine."""
import os
import tempfile
import unittest

from flask import Flask
from app.asset_routes import assets_bp
from app.models.assets import AssetRegistry


class AssetRegistryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.directory.name, 'registry.sqlite3')
        self.app = Flask(__name__, template_folder=os.path.abspath('app/templates'))
        self.app.config.update(TESTING=True, SIAS_DATABASE_PATH=self.path)
        self.app.register_blueprint(assets_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def create(self, kind, **values):
        response = self.client.post('/api/registry/' + kind, json=values)
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['record']

    def hierarchy(self):
        customer = self.create('customers', name='Example owner', industry='manufacturing')
        site = self.create('sites', name='Plant 1', customer_id=customer['id'], location='Rotterdam')
        asset = self.create('assets', name='Pump 1', site_id=site['id'], asset_type='Pump')
        return customer, site, asset

    def test_records_survive_new_registry_instance(self):
        customer, site, asset = self.hierarchy()
        snapshot = AssetRegistry(self.path).snapshot()
        self.assertEqual(snapshot['customers'], [customer])
        self.assertEqual(snapshot['sites'], [site])
        self.assertEqual(snapshot['assets'], [asset])
        self.assertEqual(asset['status'], 'unknown')
        self.assertEqual(asset['criticality'], 'medium')

    def test_partial_update_preserves_fields(self):
        _, _, asset = self.hierarchy()
        response = self.client.patch(f"/api/registry/assets/{asset['id']}", json={'status': 'maintenance'})
        self.assertEqual(response.status_code, 200)
        record = response.get_json()['record']
        self.assertEqual(record['status'], 'maintenance')
        self.assertEqual(record['name'], asset['name'])
        self.assertEqual(record['created_at'], asset['created_at'])

    def test_parents_cannot_be_deleted_until_children_removed(self):
        customer, site, asset = self.hierarchy()
        self.assertEqual(self.client.delete(f"/api/registry/customers/{customer['id']}").status_code, 409)
        self.assertEqual(self.client.delete(f"/api/registry/sites/{site['id']}").status_code, 409)
        for kind, record in [('assets', asset), ('sites', site), ('customers', customer)]:
            self.assertEqual(self.client.delete(f"/api/registry/{kind}/{record['id']}").status_code, 200)
        self.assertEqual(self.client.get('/api/registry').get_json()['assets'], [])

    def test_bad_inputs_and_missing_records_return_json_errors(self):
        customer, site, asset = self.hierarchy()
        cases = [
            ('customers', {'name': ' ', 'industry': 'manufacturing'}),
            ('customers', {'name': 'A', 'industry': 'not-an-industry'}),
            ('customers', {'name': 17, 'industry': 'manufacturing'}),
            ('customers', {'name': 'x' * 201, 'industry': 'manufacturing'}),
            ('sites', {'name': 'A', 'customer_id': True}),
            ('sites', {'name': 'A', 'customer_id': 9999}),
            ('assets', {'name': 'A', 'site_id': site['id'], 'asset_type': 'Pump', 'status': 'bad'}),
            ('assets', {'name': 'A', 'site_id': site['id'], 'asset_type': 'Pump', 'criticality': 'bad'}),
            ('customers', {'name': 'A', 'industry': 'manufacturing', 'id': 999}),
            ('customers', []),
        ]
        for kind, payload in cases:
            with self.subTest(payload=payload):
                response = self.client.post('/api/registry/' + kind, json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.get_json()['ok'])
        self.assertEqual(self.client.patch('/api/registry/assets/9999', json={'name': 'X'}).status_code, 404)
        self.assertEqual(self.client.delete('/api/registry/assets/9999').status_code, 404)
        self.assertEqual(self.client.post('/api/registry/invalid', json={}).status_code, 404)

    def test_occupied_site_cannot_transfer_customers(self):
        _, site, _ = self.hierarchy()
        other = self.create('customers', name='Another customer', industry='water')
        response = self.client.patch(f"/api/registry/sites/{site['id']}", json={'customer_id': other['id']})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(AssetRegistry(self.path).snapshot()['sites'][0]['customer_id'], site['customer_id'])

    def test_asset_can_be_reassigned(self):
        customer, _, asset = self.hierarchy()
        destination = self.create('sites', name='Plant 2', customer_id=customer['id'])
        response = self.client.patch(f"/api/registry/assets/{asset['id']}", json={'site_id': destination['id']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['record']['site_id'], destination['id'])

    def test_template_renders(self):
        # base.html expects the main application static endpoint.
        response = self.client.get('/assets')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'form-assets', response.data)
        self.assertIn(b'form-customers', response.data)
        self.assertIn(b'form-sites', response.data)


if __name__ == '__main__':
    unittest.main()
