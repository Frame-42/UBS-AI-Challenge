"""Synthetic assessments are reproducible demo inputs, never evidence or real AI runs."""
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from risk_framework import (RiskFramework, ValidationError, WebsiteDataset, load_collection,
                            load_config, load_json, simulate_assessments)
from tests.helpers import rows

ROOT = Path(__file__).resolve().parents[1]


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.collection = load_collection(ROOT/'companies')
        self.config = load_config(ROOT/'examples/collection_config.json')

    def test_hundred_runs_spread_bounds_and_financial_exclusion(self):
        data = simulate_assessments(self.collection, self.config)
        counts = Counter((a.entity_id, a.category) for a in data)
        self.assertEqual(len(data), 2500)
        self.assertEqual(set(counts.values()), {100})
        self.assertEqual({a.category for a in data}, {'cybersecurity', 'fraud', 'reputational'})
        self.assertNotIn('chain-iq', {a.entity_id for a in data})
        self.assertEqual({a.category for a in data if a.entity_id == 'hireright'}, {'reputational'})
        for entity, category in counts:
            group = [a for a in data if (a.entity_id,a.category)==(entity,category)]
            self.assertEqual({a.run_id for a in group}, set(range(100)))
            self.assertGreater(max(a.risk_score for a in group)-min(a.risk_score for a in group),0)
        for assessment in data:
            self.assertTrue(0 <= assessment.risk_score <= 100)
            self.assertTrue(assessment.metadata['synthetic'])
            self.assertTrue(4 <= assessment.metadata['spread_std'] <= 12)
            self.assertEqual(assessment.metadata['collection_digest'], self.collection.digest)

    def test_reproducibility_and_independence_of_other_entities(self):
        first=simulate_assessments(self.collection,self.config)
        reverse=replace(self.collection,assessments=tuple(reversed(self.collection.assessments)))
        self.assertEqual(first,simulate_assessments(reverse,self.config))
        subset=replace(self.collection,assessments=tuple(a for a in self.collection.assessments if a.entity_id=='microsoft'))
        self.assertEqual(tuple(a for a in first if a.entity_id=='microsoft'),simulate_assessments(subset,self.config))
        changed=load_config(overrides={'assessment_simulation':{'seed':43}})
        self.assertNotEqual([a.risk_score for a in first], [a.risk_score for a in simulate_assessments(self.collection,changed)])

    def test_simulation_parameters_are_configurable(self):
        cfg=load_config(overrides={'categories':['fraud'], 'assessment_simulation':{
            'runs':12,'spread_std_min':2,'spread_std_max':2,'excluded_categories':[]}})
        data=simulate_assessments(self.collection,cfg)
        self.assertEqual(len(data),8*12)
        self.assertEqual({a.category for a in data},{'fraud'})
        self.assertEqual({a.metadata['spread_std'] for a in data},{2})
        for override in [{'runs':0},{'seed':True},{'spread_std_min':0},
                         {'spread_std_max':3},{'excluded_categories':'financial'},
                         {'excluded_categories':['financial','financial']}]:
            with self.subTest(override=override), self.assertRaises(ValidationError):
                load_config(overrides={'assessment_simulation':override})

    def test_website_labels_mock_data_mc_headline_and_missing_financial(self):
        dataset=WebsiteDataset(self.collection,self.config,assessments=simulate_assessments(self.collection,self.config))
        weights=load_json(ROOT/'examples/collection_weights.json')
        payload=dataset.score(weights)
        self.assertEqual(payload['score_basis'],'simulated_ai_assessments')
        self.assertEqual(payload['distribution_semantics'],'synthetic_assessment_spread')
        self.assertEqual(payload['schema_version'],'1.1')
        self.assertTrue(payload['scoreboard']['contains_synthetic_assessments'])
        for entity in payload['scoreboard']['records']:
            overall=entity['overall']
            self.assertIsNone(entity['categories']['financial']['score'])
            self.assertEqual(entity['categories']['financial']['n'],0)
            self.assertIn('financial',overall['missing_categories'])
            self.assertTrue(overall['incomplete'])
            self.assertEqual(overall['score'],overall['median'])
            self.assertEqual(overall['score_method'],'monte_carlo_median')
            if overall['score'] is not None:
                self.assertEqual(overall['n'],5000)
                self.assertAlmostEqual(overall['coverage'], .15 if entity['entity_id'] == 'hireright' else .65)
                self.assertGreater(overall['spread'],0)
                self.assertLessEqual(overall['p10'],overall['score'])
                self.assertGreaterEqual(overall['p90'],overall['score'])
        updated=dataset.score({**weights,'fraud':70})
        self.assertEqual({r['entity_id']:r['categories'] for r in payload['scoreboard']['records']},
                         {r['entity_id']:r['categories'] for r in updated['scoreboard']['records']})
        self.assertNotEqual([r['overall']['score'] for r in payload['scoreboard']['records']],
                            [r['overall']['score'] for r in updated['scoreboard']['records']])

    def test_mc_headline_differs_from_weighted_category_medians(self):
        # Each category's median is zero, while independent combined draws are often 50.
        data=rows('a','x',[0]*60+[100]*40)+rows('a','y',[0]*60+[100]*40)
        framework=RiskFramework(data)
        overall=framework.score_entity('a',{'x':1,'y':1}).overall
        self.assertEqual(overall.weighted_category_score,0)
        self.assertEqual(overall.score,50)
        self.assertEqual(overall.risk_level,'MODERATE')
        self.assertEqual(sum(overall.contributions.values()),0)
        # Ranking must follow Monte Carlo headline, not the old weighted reference.
        ranked=RiskFramework(data+rows('b','x',[30]*100)+rows('b','y',[30]*100)).score_all({'x':1,'y':1})
        self.assertEqual([r.entity_id for r in ranked.records],['a','b'])
        for method in ['weighted_categories','monte_carlo_mean']:
            cfg=load_config(overrides={'overall_simulation':{'headline_method':method}})
            result=RiskFramework(data,cfg).score_entity('a',{'x':1,'y':1}).overall
            self.assertEqual(result.score,result.weighted_category_score if method=='weighted_categories' else result.mean)
        with self.assertRaisesRegex(ValidationError,'requires simulation'):
            framework.score_all({'x':1,'y':1},simulate=False)
        with self.assertRaises(ValidationError):
            load_config(overrides={'overall_simulation':{'headline_method':'typo'}})

    def test_mixing_synthetic_and_real_is_rejected(self):
        data=list(simulate_assessments(self.collection,self.config))
        real=asdict(data[0]); real['metadata']={}; real['run_id']='real-run'
        with self.assertRaisesRegex(ValidationError,'mix synthetic'):
            WebsiteDataset(self.collection,self.config,assessments=[*data,real])

    def test_financial_is_ready_for_real_assessments(self):
        # Demo exclusions must not discard actual future assessments.
        data=rows('microsoft','financial',[65]*100)
        payload=WebsiteDataset(self.collection,self.config,assessments=data).score({'financial':1})
        entity=payload['scoreboard']['records'][0]
        self.assertEqual(payload['score_basis'],'ai_assessments')
        self.assertEqual(entity['overall']['score'],65)
        self.assertEqual(entity['overall']['coverage'],1)

    def test_cli_simulate_then_export(self):
        with tempfile.TemporaryDirectory() as temp:
            raw=Path(temp)/'simulated.json'; output=Path(temp)/'website.json'
            common=['--reports',str(ROOT/'companies'),'--config',str(ROOT/'examples/collection_config.json')]
            process=subprocess.run([sys.executable,'-m','risk_framework','simulate',*common,'--output',str(raw)],
                                   cwd=ROOT,capture_output=True,text=True,timeout=30)
            self.assertEqual(process.returncode,0,process.stderr)
            self.assertIn('SYNTHETIC',process.stdout)
            self.assertEqual(len(load_json(raw)),2500)
            process=subprocess.run([sys.executable,'-m','risk_framework','export',*common,
                '--weights',str(ROOT/'examples/collection_weights.json'),'--assessments',str(raw),'--output',str(output)],
                cwd=ROOT,capture_output=True,text=True,timeout=30)
            self.assertEqual(process.returncode,0,process.stderr)
            self.assertEqual(load_json(output)['score_basis'],'simulated_ai_assessments')
