"""Keep industry solution plans internally consistent and honest about scope."""
import unittest

from app.models.hub import CAPABILITIES, INDUSTRIES


class HubCatalogTests(unittest.TestCase):
    def test_industry_suggestions_reference_unique_known_capabilities(self):
        capability_ids = {item['id'] for item in CAPABILITIES}
        self.assertEqual(len(capability_ids), len(CAPABILITIES))
        self.assertEqual(len({item['id'] for item in INDUSTRIES}), len(INDUSTRIES))
        for industry in INDUSTRIES:
            with self.subTest(industry=industry['id']):
                self.assertTrue(industry['customers'])
                self.assertTrue(industry['assets'])
                self.assertTrue(industry['kpis'])
                self.assertTrue(set(industry['capabilities']) <= capability_ids)
                self.assertEqual(len(industry['capabilities']), len(set(industry['capabilities'])))

    def test_demo_scope_is_distinguished_from_future_modules(self):
        available = {item['id'] for item in CAPABILITIES if item['status'] == 'Available'}
        self.assertEqual(available, {'monitoring', 'prediction', 'control', 'alarms', 'workorders'})
        self.assertTrue(all(item['status'] in {'Available', 'Planned'} for item in CAPABILITIES))


if __name__ == '__main__':
    unittest.main()
