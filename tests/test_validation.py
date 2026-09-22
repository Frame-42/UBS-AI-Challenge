import unittest
from risk_framework import Assessment, RiskFramework, ValidationError, load_config, normalize_weights
from risk_framework.validation import parse_json
from helpers import config, rows


class ValidationTests(unittest.TestCase):
    def test_bad_scores_rejected(self):
        for value in [-1, 101, float('nan'), float('inf'), -float('inf'), True, '72', None, 10**400]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                Assessment('a', 'cyber', value)
        for value in [0, 100, 72.5]:
            self.assertEqual(Assessment('a', 'cyber', value).risk_score, value)

    def test_required_fields_and_unknown_fields(self):
        for row in [{}, {'entity_id': 'a', 'category': 'cyber'},
                    {'entity_id': 'a', 'category': 'cyber', 'risk_score': 70, 'risk_socre': 70},
                    {'entity_id': ' ', 'category': 'cyber', 'risk_score': 70},
                    {'entity_id': 'a', 'category': ' cyber', 'risk_score': 70}]:
            with self.subTest(row=row), self.assertRaises(ValidationError):
                Assessment.from_dict(row)

    def test_metadata_timestamp_and_run_id(self):
        Assessment('a', 'cyber', 70, timestamp='2026-09-22T12:00:00Z', metadata={'sources': ['example']})
        for kwargs in [{'timestamp': 'yesterday'}, {'timestamp': '2026-09-22T12:00:00'}, {'timestamp': '20260922T120000Z'},
                       {'run_id': True}, {'run_id': -1}, {'run_id': 1.0},
                       {'metadata': {'value': float('nan')}}, {'metadata': []},
                       {'metadata': {1: 'bad key'}}, {'agent_id': ''}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                Assessment('a', 'cyber', 70, **kwargs)

    def test_duplicate_run_ids_rejected_regardless_of_agent(self):
        data = rows('a', 'cyber', [70])
        for run_id in [0, '0']:
            with self.assertRaisesRegex(ValidationError, 'Duplicate run_id'):
                RiskFramework(data + [{**data[0], 'run_id': run_id, 'agent_id': 'other'}])
        # IDs can be reused in another category or entity; anonymous repeats are valid.
        RiskFramework(data + rows('a', 'financial', [60]) + rows('b', 'cyber', [50]))
        self.assertEqual(len(RiskFramework([{'entity_id': 'a', 'category': 'cyber', 'risk_score': 60}]*10).assessments), 10)

    def test_conflicting_entity_metadata_rejected(self):
        for field in ['entity_name', 'entity_type']:
            data = rows('a', 'cyber', [70, 80])
            data[0][field], data[1][field] = 'first', 'second'
            with self.assertRaisesRegex(ValidationError, 'Conflicting'):
                RiskFramework(data)

    def test_invalid_weights(self):
        for weights in [{}, {'cyber': 0}, {'cyber': -1}, {'cyber': True}, {'cyber': '40'},
                        {'cyber': float('nan')}, {'typo': 1}, {'cyber': 1e308, 'financial': 1e-308}]:
            with self.subTest(weights=weights), self.assertRaises(ValidationError):
                normalize_weights(weights, ['cyber', 'financial'])

    def test_config_validation(self):
        invalid = [
            {'oops': 1}, {'categories': []}, {'categories': ['a', 'a']}, {'categories': 'a'},
            {'category_aggregation': {'method': 'typo'}}, {'category_aggregation': {'alpha': 1.1}},
            {'category_aggregation': {'percentile': 101}}, {'category_aggregation': {'oops': 1}},
            {'overall_simulation': {'runs': 0}}, {'overall_simulation': {'seed': True}},
            {'minimum_runs': {'minimum_required': 101}}, {'minimum_runs': {'preferred': 0}},
            {'stability': {'high_max_p10_p90_spread': 31}}, {'missing_categories': 'zero'},
            {'risk_levels': []}, {'risk_levels': [{'label': 'LOW', 'upper': 99}]},
            {'risk_levels': [{'label': 'LOW', 'upper': 80}, {'label': 'LOW', 'upper': 100}]},
            {'risk_scale': {'min': -1}}, {'risk_scale': {'max': 0}},
        ]
        for override in invalid:
            with self.subTest(override=override), self.assertRaises(ValidationError):
                load_config(overrides=override)

    def test_strict_categories_and_unknown_entity(self):
        with self.assertRaisesRegex(ValidationError, 'Unknown assessment category'):
            RiskFramework(rows('a', 'typo', [70]*10), config(categories=['cyber']))
        framework = RiskFramework(rows('a', 'cyber', [70]*10), config(categories=['cyber']))
        with self.assertRaisesRegex(ValidationError, 'Unknown weight category'):
            framework.score_all({'typo': 1})
        with self.assertRaisesRegex(ValidationError, 'Unknown entity_id'):
            framework.score_entity('unknown', {'cyber': 1})

    def test_json_duplicate_keys_and_nonfinite_numbers(self):
        for value in ['{"a": 1, "a": 2}', '[NaN]', '[Infinity]', '[1e999]', 'not JSON']:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_json(value)
