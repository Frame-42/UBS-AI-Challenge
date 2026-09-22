import importlib
import json
from pathlib import Path
import pkgutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import risk_framework
from risk_framework import RiskFramework, ValidationError, load_assessments, load_config, load_json, to_json

ROOT = Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    def test_sample_json_programmatic_and_cli_match(self):
        args = ['--input', str(ROOT/'examples/sample_assessments.json'),
                '--weights', str(ROOT/'examples/sample_weights.json'),
                '--config', str(ROOT/'examples/sample_config.json')]
        process = subprocess.run([sys.executable, '-m', 'risk_framework', 'score', *args],
                                 cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)
        expected = RiskFramework(load_assessments(args[1]), load_config(args[5])).score_all(load_json(args[3]))
        payload = json.loads(process.stdout)
        self.assertEqual(payload, json.loads(to_json(expected)))
        self.assertEqual(payload['assessment_count'], 395)
        self.assertEqual(len(payload['records']), 3)
        gamma = next(r for r in payload['records'] if r['entity_id'] == 'vendor-gamma')
        self.assertAlmostEqual(gamma['overall']['coverage'], .75)
        self.assertTrue(gamma['overall']['incomplete'])
        table = subprocess.run([sys.executable, '-m', 'risk_framework', 'score', *args, '--format', 'table'],
                               cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(table.returncode, 0, table.stderr)
        self.assertIn('INCOMPLETE', table.stdout)
        self.assertIn('below preferred runs', table.stdout)

    def test_jsonl_and_located_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'input.jsonl'
            path.write_text('\n{"entity_id":"a","category":"cyber","risk_score":72}\n')
            self.assertEqual(load_assessments(path)[0].risk_score, 72)
            path.write_text('\n{"entity_id":"a","category":"cyber","risk_score":101}\n')
            with self.assertRaisesRegex(ValidationError, 'line 2'):
                load_assessments(path)
            path = Path(temp)/'input.json'
            path.write_text('{}')
            with self.assertRaisesRegex(ValidationError, 'array'):
                load_assessments(path)

    def test_null_policy_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'config.json'
            path.write_text('null')
            with self.assertRaisesRegex(ValidationError, 'JSON object'):
                load_config(path)

    def test_cli_invalid_input_fails_without_partial_output(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'bad.json'
            path.write_text('[{"entity_id":"a","category":"cyber","risk_score":101}]')
            process = subprocess.run([sys.executable, '-m', 'risk_framework', 'score', '--input', str(path),
                                      '--weights', str(ROOT/'examples/sample_weights.json')],
                                     cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 2)
            self.assertEqual(process.stdout, '')
            self.assertIn('risk_score', process.stderr)
            self.assertNotIn('Traceback', process.stderr)

    def test_cli_output_and_input_overwrite_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'output.json'
            args = [sys.executable, '-m', 'risk_framework', 'score',
                    '--input', str(ROOT/'examples/sample_assessments.json'),
                    '--weights', str(ROOT/'examples/sample_weights.json')]
            result = subprocess.run([*args, '--output', str(path)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, '')
            self.assertEqual(load_json(path)['schema_version'], '1.1')
            before = (ROOT/'examples/sample_weights.json').read_bytes()
            result = subprocess.run([*args, '--output', str(ROOT/'examples/sample_weights.json')],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual((ROOT/'examples/sample_weights.json').read_bytes(), before)

    def test_all_modules_import_without_network(self):
        with patch('socket.socket', side_effect=AssertionError('Unexpected network use')):
            for module in pkgutil.walk_packages(risk_framework.__path__, 'risk_framework.'):
                importlib.import_module(module.name)
