"""Checks for the dashboard's connection to saved collection reports."""
import json
import shutil
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from serve import DashboardData, DashboardHandler, ROOT


class DashboardDataTests(unittest.TestCase):
    def test_scores_and_missing_data_come_from_collection(self):
        payload = DashboardData().score()
        rows = {r['entity_id']: r for r in payload['scoreboard']['records']}
        self.assertEqual(payload['score_basis'], 'collector_heuristic')
        self.assertEqual(len(rows), 10)
        self.assertNotIn('sanctions', payload['dashboard']['default_weights'])
        self.assertEqual(len(payload['dashboard']['default_weights']), 4)
        self.assertEqual(payload['scoreboard']['normalized_weights']['sanctions'], 0)
        self.assertEqual(rows['microsoft']['categories']['financial']['score'], 0)
        self.assertEqual(rows['microsoft']['categories']['reputational']['score'], 69)
        self.assertAlmostEqual(rows['microsoft']['overall']['coverage'], 1)
        self.assertEqual(rows['hireright']['overall']['score'], 8)
        self.assertAlmostEqual(rows['hireright']['overall']['coverage'], .166)
        self.assertIsNone(rows['chain-iq']['overall']['score'])
        self.assertTrue(payload['evidence']['hireright']['report']['errors'])
        cyber = DashboardData().score({'cybersecurity': 100})
        ms = next(r for r in cyber['scoreboard']['records'] if r['entity_id'] == 'microsoft')
        self.assertEqual(ms['overall']['score'], 100)
        self.assertEqual(ms['overall']['coverage'], 1)
        reputation = DashboardData().score({'reputational': 100})
        self.assertEqual(sum(r['overall']['score'] is not None for r in reputation['scoreboard']['records']), 9)
        for row in reputation['scoreboard']['records']:
            self.assertEqual(row['overall']['score'], row['categories']['reputational']['score'])
        missing = DashboardData().score({'sanctions': 100})
        self.assertTrue(all(r['overall']['score'] is None for r in missing['scoreboard']['records']))

    def test_updated_report_rebuilds_cached_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'companies', root / 'companies')
            (root / 'examples').mkdir()
            for name in ('collection_config.json', 'dashboard_weights.json'):
                shutil.copy(ROOT / 'examples' / name, root / 'examples' / name)
            data = DashboardData(root)
            first = data.score()
            retained = data.dataset
            data.score({'fraud': 100})
            self.assertIs(data.dataset, retained)
            path = next((root / 'companies/microsoft').glob('microsoft_*.json'))
            report = json.loads(path.read_text())
            report['generated_at'] = '2026-09-23T15:00:00+00:00'
            newer = path.with_name('microsoft_20260923T150000.json')
            newer.write_text(json.dumps(report))
            updated = data.score()
            self.assertIsNot(data.dataset, retained)
            self.assertNotEqual(first['collection_digest'], updated['collection_digest'])
            self.assertEqual(updated['evidence']['microsoft']['generated_at'], report['generated_at'])
            self.assertEqual(updated['evidence']['microsoft']['report_count'], 3)
            ms = next(r for r in updated['scoreboard']['records'] if r['entity_id'] == 'microsoft')
            self.assertEqual(ms['categories']['reputational']['score'], 69)


class DashboardHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class QuietHandler(DashboardHandler):
            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()

    def test_endpoint_matches_framework_for_weight_changes(self):
        weights = {'cybersecurity': 0, 'financial': 100, 'fraud': 0, 'reputational': 0, 'sanctions': 0}
        with urlopen(self.url + '/api/dashboard?' + urlencode({'weights': json.dumps(weights)})) as response:
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            payload = json.load(response)
        self.assertEqual(payload, DashboardData().score(weights))

    def test_invalid_weights_and_non_asset_paths_rejected(self):
        for weights in ('[]', '{', '{"cybersecurity":-1}', '{"cybersecurity":0}'):
            with self.assertRaises(HTTPError) as error:
                urlopen(self.url + '/api/dashboard?' + urlencode({'weights': weights}))
            self.assertEqual(error.exception.code, 400)
            self.assertIn('error', json.load(error.exception))
            error.exception.close()
        for path in ('/.git/config', '/companies/aws/company.json', '/serve.py'):
            with self.assertRaises(HTTPError) as error:
                urlopen(self.url + path)
            self.assertEqual(error.exception.code, 404)
            error.exception.close()
