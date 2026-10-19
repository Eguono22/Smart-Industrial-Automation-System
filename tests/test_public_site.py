"""Vercel public pages must render without database access or operational imports."""
import unittest
from unittest.mock import patch

from public_site import app


class PublicSiteTests(unittest.TestCase):
    def test_pages_need_no_database(self):
        with patch('sqlite3.connect', side_effect=AssertionError('Public site must not open SQLite')):
            client = app.test_client()
            for path in ['/', '/founder', '/health', '/ready', '/api/hub/catalog', '/operations']:
                with self.subTest(path=path):
                    self.assertEqual(client.get(path).status_code, 200)
            html = client.get('/').get_data(as_text=True)
            self.assertIn('Eguonoroghene Adomi', html)
            self.assertIn('© 2026 SIAS Hub. All rights reserved.', html)
            self.assertNotIn('href="/login"', html)
            self.assertNotIn('href="/dashboard"', html)
            self.assertNotIn('href="/assets"', html)
            self.assertIn('Build a solution plan', html)

    def test_statics_and_operational_writes(self):
        client = app.test_client()
        for path in ['/static/css/style.css', '/static/js/hub.js', '/static/vendor/bootstrap.min.css']:
            self.assertEqual(client.get(path).status_code, 200)
        self.assertEqual(client.post('/api/auth/login', json={}).status_code, 404)
        self.assertEqual(client.post('/api/registry/customers', json={}).status_code, 404)
        self.assertEqual(client.get('/api/registry').status_code, 404)
        self.assertIn('not available', client.get('/assets').get_data(as_text=True))
