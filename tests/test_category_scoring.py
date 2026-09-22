import unittest

from risk_framework import score_category
from helpers import config


class CategoryTests(unittest.TestCase):
    def test_identical_hundred_values(self):
        result = score_category([62] * 100, config())
        self.assertEqual(result.score, 62)
        self.assertEqual((result.p10, result.p90, result.n), (62, 62, 100))
        self.assertEqual((result.std, result.spread, result.iqr, result.mad), (0, 0, 0, 0))
        self.assertEqual(result.stability, "HIGH")
        self.assertFalse(result.below_preferred_runs)

    def test_outlier_median_robust(self):
        result = score_category([20] * 99 + [100], config())
        self.assertEqual(result.score, 20)
        self.assertEqual(result.maximum, 100)
        self.assertAlmostEqual(result.mean, 20.8)
        self.assertEqual(result.spread, 0)

    def test_known_descriptive_statistics(self):
        result = score_category([0, 10, 20, 30, 40], config(minimum_runs={"minimum_required": 1}))
        self.assertEqual((result.p10, result.p25, result.median, result.p75, result.p90), (4, 10, 20, 30, 36))
        self.assertAlmostEqual(result.std, 200**0.5)
        self.assertEqual((result.iqr, result.mad), (20, 10))
        self.assertEqual(result.stability, "LOW")

    def test_aggregation_methods(self):
        values = [20] * 9 + [100]
        for method, expected, options in [
            ("median", 20, {}), ("mean", 28, {}),
            ("percentile", 100, {"percentile": 100}),
            ("risk_adjusted", 24, {"alpha": .5}),
        ]:
            with self.subTest(method=method):
                result = score_category(values, config(category_aggregation={"method": method, **options}))
                self.assertAlmostEqual(result.score, expected)

    def test_threshold_boundaries_and_custom_labels(self):
        cfg = config(stability={"high_max_p10_p90_spread": 10, "medium_max_p10_p90_spread": 20})
        self.assertEqual([cfg.stability_label(v) for v in [10, 10.1, 20, 20.1]],
                         ["HIGH", "MEDIUM", "MEDIUM", "LOW"])
        self.assertEqual([cfg.risk_level(v) for v in [0, 20, 40, 60, 80, 100]],
                         ["LOW", "GUARDED", "MODERATE", "HIGH", "CRITICAL", "CRITICAL"])
        custom = config(risk_levels=[{"label": "REVIEW", "upper": 100}])
        self.assertEqual(score_category([85]*10, custom).risk_level, "REVIEW")

    def test_insufficient_and_singleton(self):
        result = score_category([40], config())
        self.assertEqual((result.n, result.median, result.std), (1, 40, 0))
        self.assertIsNone(result.score)
        self.assertIsNone(result.stability)
        self.assertEqual(result.status, "insufficient_runs")
        eligible = score_category([40], config(minimum_runs={"minimum_required": 1}))
        self.assertEqual(eligible.score, 40)
