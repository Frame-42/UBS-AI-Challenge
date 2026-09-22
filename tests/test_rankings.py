import unittest
from risk_framework import RiskFramework, rank_entities
from tests.helpers import config, rows


class RankingTests(unittest.TestCase):
    def test_highest_risk_first_and_weights_reverse_ranking(self):
        data = (rows('alpha', 'cyber', [80]*10) + rows('alpha', 'financial', [20]*10)
                + rows('beta', 'cyber', [20]*10) + rows('beta', 'financial', [80]*10))
        framework = RiskFramework(data, config())
        a = framework.score_all({'cyber': 4, 'financial': 1}).records
        b = framework.score_all({'cyber': 1, 'financial': 4}).records
        self.assertEqual([r.entity_id for r in a], ['alpha', 'beta'])
        self.assertEqual([r.entity_id for r in b], ['beta', 'alpha'])
        self.assertEqual([r.rank for r in a], [1, 2])
        self.assertEqual(a[0].categories, b[1].categories)
        self.assertEqual(rank_entities(reversed(a)), a)

    def test_exact_ties_competition_rank_then_null_last(self):
        data = rows('b', 'risk', [80]*10) + rows('a', 'risk', [80]*10) + rows('c', 'risk', [40]*10)
        result = RiskFramework(data, config(), entities={'d': 'No data'}).score_all({'risk': 1})
        self.assertEqual([r.entity_id for r in result.records], ['a', 'b', 'c', 'd'])
        self.assertEqual([r.rank for r in result.records], [1, 1, 3, None])
