"""Producer-to-website integration stays offline and never fabricates AI runs."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from risk_collector.models import Company, RiskCategory, RiskSignal, Severity, Source
from risk_collector.pipeline import RiskReport, summarise
from risk_framework import RiskFramework, ValidationError, WebsiteDataset, export_json, load_collection, load_config, load_json
from risk_framework.collection import validate_report
from tests.helpers import rows

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = load_json(ROOT/'examples/collection_weights.json')
CONFIG = load_config(ROOT/'examples/collection_config.json')


def producer_report(name='Acme', timestamp='2026-09-22T12:00:00Z'):
    source = Source('Example source', 'Example publisher', 'https://example.org/evidence', retrieved_at=timestamp)
    signal = RiskSignal(RiskCategory.CYBERSECURITY, 'Example finding', 'Fictional test evidence',
                        Severity.HIGH, [source], 'fixture', confidence=.8)
    categories = [RiskCategory.CYBERSECURITY, RiskCategory.FINANCIAL]
    return RiskReport(Company(name), timestamp, {'categories': [c.value for c in categories]},
                      [signal], [], [], summarise([signal], categories)).to_dict()


class CollectionExportTests(unittest.TestCase):
    def test_reputation_addition_preserves_every_existing_category_and_finding(self):
        collection = load_collection(ROOT/'companies')
        payload = WebsiteDataset(collection, CONFIG).score(WEIGHTS)
        records = {r['entity_id']: r for r in payload['scoreboard']['records']}
        for directory in sorted((ROOT/'companies').iterdir()):
            if not directory.is_dir():
                continue
            evidence = payload['evidence'][directory.name]
            original_path = next(directory.glob('*_20260922T14*.json'))
            original = load_json(original_path)
            for summary in original['summary']:
                category = summary['category']
                self.assertEqual(records[directory.name]['categories'][category]['score'],
                                 summary['score'] if summary['signals'] else None)
                provenance = evidence['category_reports'][category]
                self.assertEqual(provenance['generated_at'], original['generated_at'])
                self.assertTrue(provenance['report_file'].endswith(original_path.name))
            for signal in original['signals']:
                self.assertIn(signal, evidence['report']['signals'])
            for error in original['errors']:
                self.assertIn(error, evidence['report']['errors'])
        self.assertEqual(sum(len(e['report']['signals']) for e in payload['evidence'].values()), 234)

    def test_category_refresh_keeps_other_scores_but_never_backfills_empty_results(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = producer_report(timestamp='2026-09-20T12:00:00Z')
            (root/'old.json').write_text(json.dumps(original))
            reputation = deepcopy(original)
            reputation['generated_at'] = '2026-09-21T12:00:00Z'
            reputation['parameters']['categories'] = ['reputational']
            reputation['signals'][0]['category'] = 'reputational'
            reputation['summary'] = [dict(original['summary'][0], category='reputational')]
            (root/'reputation.json').write_text(json.dumps(reputation))
            data = load_collection(root)
            self.assertEqual({a.category for a in data.assessments}, {'cybersecurity', 'reputational'})
            self.assertEqual({a.category: a.timestamp for a in data.assessments}, {
                'cybersecurity': original['generated_at'], 'reputational': reputation['generated_at']})
            empty = deepcopy(original)
            empty['generated_at'] = '2026-09-22T12:00:00Z'
            empty['signals'] = []
            empty['summary'][0].update(score=0, signals=0)
            empty['errors'] = ['Cyber collection failed']
            (root/'empty.json').write_text(json.dumps(empty))
            data = load_collection(root)
            self.assertEqual([a.category for a in data.assessments], ['reputational'])
            self.assertIn('Cyber collection failed', data.evidence['acme']['report']['errors'])
            self.assertEqual(set(data.evidence['acme']['report_files']), {'empty.json', 'reputation.json'})

    def test_disjoint_categories_can_share_timestamp_but_overlaps_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = producer_report()
            (root/'cyber.json').write_text(json.dumps(original))
            reputation = deepcopy(original)
            reputation['parameters']['categories'] = ['reputational']
            reputation['signals'][0]['category'] = 'reputational'
            reputation['summary'] = [dict(original['summary'][0], category='reputational')]
            (root/'reputation.json').write_text(json.dumps(reputation))
            self.assertEqual(len(load_collection(root).assessments), 2)
            (root/'duplicate.json').write_text(json.dumps(reputation))
            with self.assertRaisesRegex(ValidationError, 'Ambiguous latest'):
                load_collection(root)

    def test_actual_collected_dataset_preserves_scores_and_citations(self):
        collection = load_collection(ROOT/'companies')
        with patch('socket.socket', side_effect=AssertionError('No network')):
            with patch('random.Random', side_effect=AssertionError('No simulated heuristic uncertainty')):
                payload = WebsiteDataset(collection, CONFIG).score(WEIGHTS)
        self.assertEqual(payload['score_basis'], 'collector_heuristic')
        self.assertEqual(payload['distribution_semantics'], 'not_available')
        board = payload['scoreboard']
        self.assertEqual(len(board['records']), 10)
        self.assertEqual(board['assessment_count'], 33)
        self.assertEqual(board['config']['minimum_runs']['minimum_required'], 1)
        for entity in board['records']:
            self.assertEqual(entity['overall']['n'], 0)
            self.assertIsNone(entity['overall']['stability'])
            self.assertIsNone(entity['overall']['p90'])
            evidence = payload['evidence'][entity['entity_id']]
            self.assertEqual(evidence['report_count'], 2)
            for summary in evidence['report']['summary']:
                category = entity['categories'][summary['category']]
                self.assertEqual(category['score'], summary['score'] if summary['signals'] else None)
                self.assertEqual(category['n'], 1 if summary['signals'] else 0)
                self.assertIsNone(category['p10'])
                self.assertIsNone(category['stability'])
            self.assertEqual(entity['categories']['sanctions']['status'], 'missing')
        microsoft = payload['evidence']['microsoft']['report']
        original = load_json(ROOT/'companies/microsoft/microsoft_20260922T143313.json')
        self.assertTrue(all(signal in microsoft['signals'] for signal in original['signals']))
        selected = payload['evidence']['microsoft']['selected_reports']
        self.assertEqual(selected['microsoft/microsoft_20260922T143313.json'], original)
        reputation = load_json(ROOT/'companies/microsoft/microsoft_20260922T150918.json')
        self.assertTrue(all(signal in microsoft['signals'] for signal in reputation['signals']))
        self.assertEqual(len(microsoft['signals']), len(original['signals']) + len(reputation['signals']))
        self.assertTrue(payload['evidence']['hireright']['report']['errors'])
        unscored = [r['entity_id'] for r in board['records'] if r['rank'] is None]
        self.assertEqual(unscored, ['chain-iq'])

    def test_collected_zero_with_sourced_information_is_distinct_from_no_signals(self):
        payload = WebsiteDataset(load_collection(ROOT/'companies'), CONFIG).score(WEIGHTS)
        microsoft = next(r for r in payload['scoreboard']['records'] if r['entity_id']=='microsoft')
        self.assertEqual(microsoft['categories']['financial']['score'], 0)
        self.assertAlmostEqual(microsoft['overall']['coverage'], .9)
        chain = next(r for r in payload['scoreboard']['records'] if r['entity_id']=='chain-iq')
        self.assertIsNone(chain['categories']['financial']['score'])
        self.assertEqual(chain['overall']['coverage'], 0)

    def test_actual_producer_model_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'acme.json'
            path.write_text(json.dumps(producer_report()))
            collection = load_collection(path)
            payload = WebsiteDataset(collection).score({'cybersecurity': 1, 'financial': 1})
            row = payload['scoreboard']['records'][0]
            self.assertEqual((row['entity_id'], row['overall']['score'], row['overall']['coverage']), ('acme', 12, .5))

    def test_latest_timestamp_not_filename_or_multiple_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'z_old.json').write_text(json.dumps(producer_report(timestamp='2026-09-21T12:00:00Z')))
            latest = producer_report(timestamp='2026-09-22T13:00:00+02:00')
            (root/'a_new.json').write_text(json.dumps(latest))
            data = load_collection(root)
            self.assertEqual(len(data.assessments), 1)
            self.assertEqual(data.evidence['acme']['report_count'], 2)
            self.assertEqual(data.evidence['acme']['report']['generated_at'], latest['generated_at'])
            self.assertEqual(data.evidence['acme']['report_file'], 'a_new.json')
            (root/'duplicate.json').write_text(json.dumps(latest))
            with self.assertRaisesRegex(ValidationError, 'Ambiguous latest'):
                load_collection(root)

    def test_manifest_only_entities_and_single_company_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); company=root/'stable-vendor-id'; company.mkdir()
            (company/'company.json').write_text(json.dumps({'name':'Acme'}))
            data=load_collection(root)
            row=WebsiteDataset(data).score({'cybersecurity':1})['scoreboard']['records'][0]
            self.assertEqual(row['entity_id'], 'stable-vendor-id')
            self.assertIsNone(row['overall']['score'])
            report=company/'report.json'; report.write_text(json.dumps(producer_report()))
            for path in [root, company, report]:
                data=load_collection(path)
                self.assertEqual(set(data.entities), {'stable-vendor-id'})
                self.assertEqual(data.assessments[0].entity_id, 'stable-vendor-id')

    def test_conflicting_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'company.json').write_text(json.dumps({'name':'Another company'}))
            path=root/'report.json'; path.write_text(json.dumps(producer_report()))
            for input_path in [root,path]:
                with self.assertRaisesRegex(ValidationError, 'company|Conflicting'):
                    load_collection(input_path)

    def test_malformed_report_rejects_instead_of_silently_dropping(self):
        base = producer_report()
        variants = []
        for key,value in [('score',101),('signals',2),('score',True)]:
            bad=deepcopy(base); bad['summary'][0][key]=value; variants.append(bad)
        bad=deepcopy(base); bad['signals'][0]['sources']=[]; variants.append(bad)
        bad=deepcopy(base); bad['summary'].append(bad['summary'][0]); variants.append(bad)
        bad=deepcopy(base); bad['generated_at']='yesterday'; variants.append(bad)
        bad=deepcopy(base); bad['summary'][1]['score']=20; variants.append(bad)
        bad=deepcopy(base); bad['parameters']['categories']=[]; variants.append(bad)
        for bad in variants:
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_report(bad)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaisesRegex(ValidationError, 'No JSON'):
                load_collection(root)
            (root/'broken.json').write_text('{}')
            with self.assertRaisesRegex(ValidationError, 'broken.json'):
                load_collection(root)

    def test_weight_changes_reuse_data_and_preserve_category_scores(self):
        dataset=WebsiteDataset(load_collection(ROOT/'companies'),CONFIG)
        first=dataset.score(WEIGHTS)
        second=dataset.score({'financial':1})
        before=first['scoreboard']['records']; after=second['scoreboard']['records']
        self.assertNotEqual([r['entity_id'] for r in before],[r['entity_id'] for r in after])
        self.assertEqual({r['entity_id']:r['categories'] for r in before}, {r['entity_id']:r['categories'] for r in after})
        self.assertEqual(first['evidence'], second['evidence'])
        self.assertEqual(first['collection_digest'], second['collection_digest'])
        first['evidence'].clear()
        self.assertEqual(len(dataset.score(WEIGHTS)['evidence']),10)

    def test_real_assessments_replace_heuristics_without_blending(self):
        data=load_collection(ROOT/'companies')
        assessments=rows('microsoft','cybersecurity',list(range(20,40)))
        cfg=load_config(overrides={'categories':list(WEIGHTS),'overall_simulation':{'runs':200}})
        payload=WebsiteDataset(data,cfg,assessments=assessments).score(WEIGHTS)
        expected=RiskFramework(assessments,cfg,entities=data.entities).score_all(WEIGHTS).to_dict()
        self.assertEqual(payload['scoreboard'],expected)
        self.assertEqual(payload['score_basis'],'ai_assessments')
        self.assertEqual(payload['distribution_semantics'],'ai_assessment_disagreement')
        self.assertEqual(payload['scoreboard']['assessment_count'],20)
        row=payload['scoreboard']['records'][0]
        self.assertEqual(row['entity_id'],'microsoft')
        self.assertEqual(row['overall']['n'],200)
        self.assertGreater(row['overall']['spread'],0)
        empty=WebsiteDataset(data,cfg,assessments=[]).score(WEIGHTS)
        self.assertTrue(all(r['overall']['score'] is None for r in empty['scoreboard']['records']))
        with self.assertRaisesRegex(ValidationError,'entity IDs'):
            WebsiteDataset(data,cfg,assessments=rows('typo','cybersecurity',[70]*10))

    def test_custom_categories_and_withhold_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            report=producer_report()
            report['signals'][0]['category']='custom-risk'
            report['summary'][0]['category']='custom-risk'
            report['parameters']['categories'][0]='custom-risk'
            path=Path(temp)/'report.json'; path.write_text(json.dumps(report))
            cfg=load_config(overrides={'categories':['custom-risk','financial'],'missing_categories':'withhold'})
            payload=WebsiteDataset(load_collection(path),cfg).score({'custom-risk':1,'financial':1})
            row=payload['scoreboard']['records'][0]
            self.assertEqual(row['categories']['custom-risk']['score'],12)
            self.assertEqual(row['overall']['status'],'incomplete_withheld')

    def test_cli_export_atomic_file_and_protected_input(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'nested/data.json'
            args=[sys.executable,'-m','risk_framework','export','--reports',str(ROOT/'companies'),
                  '--weights',str(ROOT/'examples/collection_weights.json'),'--config',str(ROOT/'examples/collection_config.json')]
            result=subprocess.run([*args,'--output',str(path)],cwd=ROOT,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            expected=WebsiteDataset(load_collection(ROOT/'companies'),CONFIG).score(WEIGHTS)
            self.assertEqual(load_json(path),expected)
            result=subprocess.run([*args,'--output',str(ROOT/'companies/output.json')],cwd=ROOT,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,2)
            self.assertFalse((ROOT/'companies/output.json').exists())
            before=path.read_bytes()
            with patch('os.replace',side_effect=OSError('simulated interruption')):
                with self.assertRaises(OSError):
                    export_json({'new':'data'},path)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(list(path.parent.glob('*.tmp')),[])
            with self.assertRaises(ValidationError):
                export_json({},path,protected_paths=[path])

    def test_cli_agent_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); assessments=root/'assessments.json'; output=root/'output.json'
            assessments.write_text(json.dumps(rows('microsoft','cybersecurity',[60]*10)))
            result=subprocess.run([sys.executable,'-m','risk_framework','export',
                '--reports',str(ROOT/'companies'),'--weights',str(ROOT/'examples/collection_weights.json'),
                '--assessments',str(assessments),'--output',str(output)],cwd=ROOT,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(load_json(output)['score_basis'],'ai_assessments')
