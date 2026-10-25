# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
import json
from pathlib import Path
import tempfile
import unittest
from evaluate import Fixture, percentile, retrieval, run, render
from unittest.mock import patch
from compare_evaluations import compare

HERE = Path(__file__).resolve().parents[1]


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = json.loads((HERE / 'evals/scenarios.json').read_text())

    def case(self, identifier):
        return next(c for c in self.dataset['cases'] if c['id'] == identifier)

    def test_manifest_has_thirty_cases_and_gold_matches_source_ids(self):
        cases = self.dataset['cases']
        self.assertEqual(len(cases), 30)
        self.assertEqual(len({c['id'] for c in cases}), 30)
        self.assertEqual({c['split'] for c in cases}, {'development', 'heldout'})
        for case in cases:
            if case['kind'] == 'retrieval':
                self.assertTrue(set(case['expected_evidence']) <= {r['id'] for r in case['records']})

    def test_recall_counts_all_required_evidence_and_locators(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(Path(tmp))
            try:
                result = retrieval(self.case('R08'), fixture, 5)
                self.assertEqual(result['recall_at_k'], 1)
                self.assertEqual(result['provenance_valid'], result['provenance_total'])
                self.assertTrue(result['passed'])
            finally:
                fixture.close()

    def test_long_passage_does_not_get_credit_for_hidden_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(Path(tmp))
            try:
                original_call = fixture.service.call
                def hide_support(name, arguments):
                    result = original_call(name, arguments)
                    for hit in result.get('results', []):
                        hit['body'] = 'Routine background text.'
                    return result
                with patch.object(fixture.service, 'call', side_effect=hide_support):
                    result = retrieval(self.case('R14'), fixture, 5)
                self.assertEqual(result['returned_evidence'], ['long'])
                self.assertEqual(result['recall_at_k'], 0)
                self.assertFalse(result['passed'])
            finally:
                fixture.close()

    def test_bad_read_cannot_receive_credit_from_good_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(Path(tmp))
            try:
                original_call = fixture.service.call
                def bad_read(name, arguments):
                    result = original_call(name, arguments)
                    if name == 'context_read':
                        result['record']['body'] = 'Unsupported substitute.'
                    return result
                with patch.object(fixture.service, 'call', side_effect=bad_read):
                    result = retrieval(self.case('R01'), fixture, 5)
                self.assertEqual(result['recall_at_k'], 1)
                self.assertEqual(result['reading_recall_at_k'], 0)
                self.assertEqual(result['read_span_valid'], 0)
            finally:
                fixture.close()

    def test_read_recall_counts_missed_search_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(Path(tmp))
            try:
                result = retrieval(self.case('R05'), fixture, 5)
                self.assertEqual(result['reading_recall_at_k'], 0)
                self.assertEqual(result['read_trace'], [])
            finally:
                fixture.close()

    def test_failed_evaluation_is_in_denominator(self):
        broken = {'version': 'test', 'k': 5, 'cases': [{'id': 'broken', 'kind': 'retrieval', 'category': 'test', 'split': 'development', 'query': 'test', 'records': [{'id': 'bad'}], 'expected_evidence': ['bad']}]}
        report = run(broken, repetitions=1)
        self.assertEqual(report['summary']['macro_recall_at_5'], 0)
        self.assertEqual(report['passing_cases'], 0)
        self.assertFalse(report['acceptance_passed'])

    def test_report_states_unmeasured_answer_quality(self):
        data = {**self.dataset, 'cases': [self.case('R01'), self.case('C01')]}
        report = run(data, repetitions=1)
        page = render(report)
        self.assertIn('not a model citation-quality score', page)
        self.assertIn('answer_completeness', report['unmeasured'])
        self.assertIsNone(report['environment']['model'])
        self.assertEqual(report['environment']['model_calls'], 0)

    def test_percentile_uses_nearest_rank(self):
        self.assertEqual(percentile(list(range(1, 21))), 19)
        self.assertIsNone(percentile([]))


class ComparisonTests(unittest.TestCase):
    def report(self, passed=True, digest='same'):
        return {'dataset_sha256': digest, 'repetitions': 1, 'split': 'all', 'runs': [{'case_id': 'probe', 'passed': passed}], 'summary': {'macro_recall_at_5': 1.0 if passed else 0.0}, 'acceptance_passed': passed}

    def test_regression_and_recall_change_are_detected(self):
        result = compare(self.report(), self.report(False))
        self.assertEqual(result['regressed_cases'], ['probe'])
        self.assertEqual(result['recall_change_percentage_points'], -100)

    def test_different_datasets_are_not_compared(self):
        with self.assertRaises(ValueError):
            compare(self.report(), self.report(digest='different'))
