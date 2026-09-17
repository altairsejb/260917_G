import unittest
import os
import sys

# Ensure my_webapp directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# DATABASE_URL must point at a Supabase/Postgres instance before app import.
# MOLIT_API_KEY is intentionally left unset so tests run against the
# deterministic mock data path (no network dependency on the MOLIT API).
os.environ.pop('MOLIT_API_KEY', None)

from app import app, init_db, get_db, execute

GANGNAM_LAWD_CD = '11680'


class ApartmentPriceTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

        with app.app_context():
            db = get_db()
            execute(db, 'TRUNCATE TABLE apartment_trades RESTART IDENTITY')
            db.commit()
            init_db()

    def tearDown(self):
        with app.app_context():
            db = get_db()
            execute(db, 'TRUNCATE TABLE apartment_trades RESTART IDENTITY')
            db.commit()

    def test_health_check(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'ok')
        self.assertFalse(data['molit_api_configured'])

    def test_index_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('아파트'.encode('utf-8'), response.data)

    def test_regions_endpoint(self):
        response = self.client.get('/api/regions')
        self.assertEqual(response.status_code, 200)
        regions = response.get_json()
        self.assertEqual(len(regions), 25)
        self.assertIn('11680', [r['code'] for r in regions])

    def test_trades_requires_params(self):
        response = self.client.get('/api/trades')
        self.assertEqual(response.status_code, 400)

    def test_trades_returns_mock_data(self):
        response = self.client.get(f'/api/trades?lawd_cd={GANGNAM_LAWD_CD}&deal_ymd=202508')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['source'], 'mock')
        self.assertGreater(data['count'], 0)
        item = data['items'][0]
        self.assertIn('price_per_pyeong', item)
        self.assertGreater(item['price_per_pyeong'], 0)

    def test_trades_are_cached(self):
        first = self.client.get(f'/api/trades?lawd_cd={GANGNAM_LAWD_CD}&deal_ymd=202508').get_json()
        second = self.client.get(f'/api/trades?lawd_cd={GANGNAM_LAWD_CD}&deal_ymd=202508').get_json()
        self.assertEqual(first['count'], second['count'])
        self.assertEqual(
            sorted(i['apt_name'] for i in first['items']),
            sorted(i['apt_name'] for i in second['items']),
        )

    def test_analysis_requires_lawd_cd(self):
        response = self.client.get('/api/analysis')
        self.assertEqual(response.status_code, 400)

    def test_analysis_returns_estimate(self):
        response = self.client.get(f'/api/analysis?lawd_cd={GANGNAM_LAWD_CD}&months=3&premium_rate=0.05')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['source'], 'mock')
        self.assertEqual(len(data['monthly']), 3)
        self.assertGreater(data['sample_count'], 0)
        self.assertIsNotNone(data['estimate'])
        self.assertGreater(
            data['estimate']['estimated_new_presale_price_per_pyeong'],
            data['estimate']['recent_avg_price_per_pyeong'],
        )


if __name__ == '__main__':
    unittest.main()
