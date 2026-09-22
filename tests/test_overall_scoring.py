import unittest

from risk_framework import RiskFramework, normalize_weights, to_json
from tests.helpers import config, rows


class OverallTests(unittest.TestCase):
    def setUp(self):
        self.data = rows('alpha', 'cyber', [80]*100) + rows('alpha', 'financial', [20]*100)

    def test_weighted_score_and_distribution(self):
        result = RiskFramework(self.data, config()).score_entity('alpha', {'cyber': 35, 'financial': 65})
        self.assertAlmostEqual(result.overall.score, 41)
        self.assertAlmostEqual(result.overall.mean, 41)
        self.assertAlmostEqual(result.overall.p10, 41)
        self.assertEqual(result.overall.std, 0)
        self.assertEqual(result.overall.n, 200)
        self.assertAlmostEqual(sum(result.overall.contributions.values()), result.overall.score)
        self.assertEqual(result.overall.coverage, 1)
        self.assertEqual(normalize_weights({'cyber': 35, 'financial': 65}, ['cyber', 'financial']),
                         normalize_weights({'cyber': .35, 'financial': .65}, ['cyber', 'financial']))

    def test_weights_change_overall_but_preserve_categories(self):
        framework = RiskFramework(self.data, config())
        a = framework.score_entity('alpha', {'cyber': 1, 'financial': 0})
        b = framework.score_entity('alpha', {'cyber': 0, 'financial': 1})
        self.assertEqual((a.overall.score, b.overall.score), (80, 20))
        self.assertEqual(a.categories, b.categories)
        self.assertEqual(len(framework.assessments), 200)

    def test_reproducible_independent_of_order_and_other_entities(self):
        data = rows('alpha', 'cyber', list(range(100))) + rows('alpha', 'financial', list(range(100, 0, -1)))
        weights = {'cyber': 3, 'financial': 2}
        first = RiskFramework(data, config()).score_all(weights)
        second = RiskFramework(list(reversed(data)), config()).score_all(dict(reversed(list(weights.items()))))
        self.assertEqual(first.records, second.records)
        self.assertEqual(first.input_digest, second.input_digest)
        third = RiskFramework(data + rows('beta', 'cyber', [4]*10), config()).score_entity('alpha', weights)
        self.assertEqual(first.records[0].overall, third.overall)
        changed = RiskFramework(data, config(overall_simulation={'seed': 99})).score_entity('alpha', weights)
        self.assertNotEqual(third.overall.p10, changed.overall.p10)
        self.assertEqual(third.overall.weighted_category_score, changed.overall.weighted_category_score)
        self.assertEqual(third.overall.score, third.overall.median)
        self.assertEqual(changed.overall.score, changed.overall.median)
        self.assertGreater(third.overall.spread, 0)

    def test_resampling_does_not_pair_run_ids(self):
        data = rows('alpha', 'cyber', [0]*50 + [100]*50) + rows('alpha', 'financial', [100]*50 + [0]*50)
        result = RiskFramework(data, config()).score_entity('alpha', {'cyber': 1, 'financial': 1})
        self.assertEqual(result.overall.score, 50)
        self.assertEqual((result.overall.minimum, result.overall.maximum), (0, 100))

    def test_dynamic_category_without_code_changes(self):
        cfg = config(categories=['new/category'])
        result = RiskFramework(rows('alpha', 'new/category', [72]*10), cfg).score_all({'new/category': 1})
        self.assertEqual(result.records[0].overall.score, 72)
        self.assertIn('new/category', result.records[0].categories)
        self.assertIn('"schema_version": "1.1"', to_json(result))

    def test_large_finite_weights_do_not_overflow(self):
        result = normalize_weights({'a': 1e308, 'b': 1e308}, ['a', 'b'])
        self.assertEqual(result, {'a': .5, 'b': .5})

    def test_snapshot_isolated_from_caller_mutation(self):
        self.data[0]['metadata'] = {'source': ['original']}
        framework = RiskFramework(self.data, config())
        before = framework.score_all({'cyber': 1})
        self.data[0]['risk_score'] = 0
        self.data[0]['metadata']['source'].append('changed')
        framework.assessments[0].metadata['source'].append('also changed')
        before.records[0].categories.clear()
        self.assertEqual(framework.score_entity('alpha', {'cyber': 1}).overall.score, 80)
        self.assertEqual(framework.assessments[0].metadata, {'source': ['original']})
