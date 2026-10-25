# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
import json
from pathlib import Path
import tempfile
import unittest
from label_queries import template, validate, freeze
from evaluate import run


class LabelingTests(unittest.TestCase):
    def case(self):
        data = template(1)
        data['cases'][0].update(origin='synthetic', reviewed=True, reviewed_by='test-reviewer', query='PINE963 deployment approval', records=[{'id': 'evidence-1', 'session': 'example', 'text': 'PINE963 requires deployment approval.'}], expected_evidence=['evidence-1'], required_text={'evidence-1': 'requires deployment approval'})
        return data

    def test_unreviewed_template_cannot_be_scored_as_labeled_data(self):
        self.assertTrue(validate(template()))

    def test_labels_and_quotes_are_validated(self):
        data = self.case()
        self.assertEqual(validate(data), [])
        data['cases'][0]['required_text']['evidence-1'] = 'invented quote'
        self.assertTrue(validate(data))
        data['cases'][0]['expected_evidence'] = ['missing']
        self.assertTrue(validate(data))

    def test_explicit_negative_requires_source_excerpts(self):
        data = self.case()
        data['cases'][0].update(expected_evidence=[], required_text={})
        self.assertEqual(validate(data), [])
        data['cases'][0]['records'] = []
        self.assertTrue(validate(data))

    def test_freeze_preserves_labels_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, destination = Path(tmp) / 'labels.json', Path(tmp) / 'frozen'
            source.write_text(json.dumps(self.case()))
            manifest = freeze(source, destination)
            self.assertEqual(manifest['origin_counts'], {'personal': 0, 'synthetic': 1})
            report = run(json.loads((destination / 'dataset.json').read_text()), repetitions=1)
            self.assertEqual(report['summary']['reading_recall_at_5'], 1)
            with self.assertRaises(ValueError):
                freeze(source, destination)

    def test_duplicate_case_ids_and_fake_review_are_rejected(self):
        data = self.case()
        data['cases'].append(dict(data['cases'][0]))
        self.assertTrue(validate(data))
        data = self.case()
        data['cases'][0]['reviewed'] = 'yes'
        self.assertTrue(validate(data))
