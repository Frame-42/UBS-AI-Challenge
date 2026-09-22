import unittest
from risk_framework import RiskFramework
from tests.helpers import config, rows


class MissingDataTests(unittest.TestCase):
    def test_missing_weights_renormalized_and_coverage_exposed(self):
        data = rows('alpha', 'cyber', [80]*20) + rows('alpha', 'financial', [20]*10)
        result = RiskFramework(data, config()).score_entity('alpha', {'cyber': 40, 'financial': 30, 'regulatory': 30})
        self.assertAlmostEqual(result.overall.score, (40*80 + 30*20)/70)
        self.assertAlmostEqual(result.overall.coverage, .7)
        self.assertAlmostEqual(result.overall.effective_weights['cyber'], 4/7)
        self.assertTrue(result.overall.incomplete)
        self.assertEqual(result.overall.missing_categories, ('regulatory',))
        self.assertEqual(result.categories['regulatory'].n, 0)
        self.assertIsNone(result.categories['regulatory'].median)
        self.assertIsNone(result.categories['regulatory'].score)
        self.assertTrue(result.categories['financial'].below_preferred_runs)

    def test_insufficient_category_excluded_but_described(self):
        data = rows('alpha', 'cyber', [80]*10) + rows('alpha', 'financial', [0]*9)
        result = RiskFramework(data, config()).score_entity('alpha', {'cyber': 1, 'financial': 1})
        self.assertEqual(result.overall.score, 80)
        self.assertEqual(result.overall.coverage, .5)
        self.assertEqual(result.overall.insufficient_categories, ('financial',))
        self.assertEqual(result.categories['financial'].median, 0)
        self.assertIsNone(result.categories['financial'].score)

    def test_withhold_policy(self):
        result = RiskFramework(rows('alpha', 'cyber', [80]*10), config(missing_categories='withhold')).score_entity(
            'alpha', {'cyber': 1, 'financial': 1})
        self.assertIsNone(result.overall.score)
        self.assertEqual(result.overall.status, 'incomplete_withheld')
        self.assertEqual(result.overall.coverage, .5)
        self.assertEqual(result.overall.n, 0)
        self.assertEqual(result.overall.effective_weights, {})
        self.assertEqual(result.categories['cyber'].score, 80)

    def test_all_missing_or_insufficient_produces_null_not_zero(self):
        framework = RiskFramework(rows('alpha', 'cyber', [80]), config(), entities={'beta': 'Vendor Beta'})
        result = framework.score_all({'cyber': 1})
        for row in result.records:
            self.assertIsNone(row.overall.score)
            self.assertIsNone(row.overall.p10)
            self.assertEqual(row.overall.coverage, 0)
            self.assertIsNone(row.rank)
            self.assertEqual(row.overall.status, 'unscorable')

    def test_zero_weight_missing_category_does_not_reduce_coverage(self):
        result = RiskFramework(rows('alpha', 'cyber', [80]*10), config(categories=['cyber', 'financial'])).score_entity(
            'alpha', {'cyber': 1})
        self.assertFalse(result.overall.incomplete)
        self.assertEqual(result.overall.coverage, 1)
        self.assertEqual(result.categories['financial'].status, 'missing')

    def test_empty_input_explicit_empty_scoreboard(self):
        result = RiskFramework([], config()).score_all({'cyber': 1})
        self.assertEqual(result.records, ())
        self.assertEqual(result.assessment_count, 0)
