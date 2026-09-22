"""Checks for the dashboard's connection to saved collection reports."""
import json
import shutil
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from serve import DashboardData, DashboardHandler, ROOT, SnapshotError, query_weights


class DashboardDataTests(unittest.TestCase):
    def test_scores_and_missing_data_come_from_collection(self):
        payload = DashboardData().score()
        rows = {r['entity_id']: r for r in payload['scoreboard']['records']}
        self.assertEqual(payload['score_basis'], 'collector_heuristic')
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows['microsoft']['categories']['financial']['score'], 0)
        self.assertIsNone(rows['microsoft']['categories']['reputational']['score'])
        self.assertEqual(rows['microsoft']['overall']['coverage'], .75)
        self.assertIsNone(rows['hireright']['overall']['score'])
        self.assertTrue(payload['evidence']['hireright']['report']['errors'])
        cyber = DashboardData().score({'cybersecurity': 100})
        ms = next(r for r in cyber['scoreboard']['records'] if r['entity_id'] == 'microsoft')
        self.assertEqual(ms['overall']['score'], 100)
        self.assertEqual(ms['overall']['coverage'], 1)
        missing = DashboardData().score({'reputational': 100})
        self.assertTrue(all(r['overall']['score'] is None for r in missing['scoreboard']['records']))

    def test_updated_report_rebuilds_cached_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'companies', root / 'companies')
            (root / 'examples').mkdir()
            for name in ('collection_config.json', 'collection_weights.json'):
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
            self.assertEqual(updated['evidence']['microsoft']['report_count'], 2)


    def test_response_metadata_cannot_mutate_defaults(self):
        data = DashboardData()
        first = data.score()
        first['dashboard']['default_weights'].clear()
        second = data.score()
        self.assertTrue(second['dashboard']['default_weights'])
        self.assertEqual(first['scoreboard'], second['scoreboard'])

    def test_invalid_snapshot_keeps_cache_and_recovers_after_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'companies', root / 'companies')
            shutil.copytree(ROOT / 'examples', root / 'examples')
            data = DashboardData(root)
            first = data.score()
            retained = data.dataset
            path = root / 'examples/collection_weights.json'
            original = path.read_text()
            path.write_text('{"financial": -1}')
            with self.assertRaises(SnapshotError):
                data.score()
            self.assertIs(data.dataset, retained)
            path.write_text(original)
            self.assertEqual(data.score(), first)

    def test_policy_file_change_invalidates_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            defaults = Path(directory) / 'defaults.json'
            defaults.write_text('{}')
            with patch('serve.POLICY_DEFAULTS', defaults):
                data = DashboardData()
                data.score()
                retained = data.dataset
                defaults.write_text('{"changed":true}')
                data.score()
                self.assertIsNot(data.dataset, retained)

    def test_query_contract_rejects_ambiguous_inputs(self):
        self.assertIsNone(query_weights(''))
        self.assertEqual(query_weights('weights=%7B%22financial%22%3A100%7D'), {'financial':100})
        for query in ['weights=', 'weights', 'weights=null', 'weights=[]',
                      'weights={"fraud":1,"fraud":2}', 'weights={"fraud":NaN}',
                      'weights={"fraud":1}&weights={"fraud":2}', 'other=1']:
            with self.subTest(query=query), self.assertRaises(ValueError):
                query_weights(query)


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
        for weights in ('[]', 'null', '{', '{"cybersecurity":-1}', '{"cybersecurity":0}', '{"fraud":1,"fraud":2}', '{"fraud":NaN}'):
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

    def test_unavailable_snapshot_returns_503_not_bad_request(self):
        with patch.object(self.server.RequestHandlerClass.data, 'score', side_effect=SnapshotError('invalid saved report')):
            with self.assertRaises(HTTPError) as error:
                urlopen(self.url + '/api/dashboard')
            self.assertEqual(error.exception.code, 503)
            self.assertIn('snapshot unavailable', json.load(error.exception)['error'])
            error.exception.close()

    def test_dashboard_assets_are_served(self):
        for path in ('/', '/index.html', '/styles.css', '/app.js'):
            with self.subTest(path=path), urlopen(self.url + path) as response:
                self.assertEqual(response.status, 200)
                self.assertTrue(response.read())
