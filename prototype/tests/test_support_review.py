# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
import unittest
from evaluate_support import select_cases


class ReviewGateTests(unittest.TestCase):
    def data(self):
        return {'review_required': True, 'cases': [
            {'id': 'a', 'group_id': 'g1', 'split': 'development', 'passage': 'Original text.', 'claim': 'Original text.', 'expected_accept': True, 'reviewed': True, 'reviewed_by': 'human'},
            {'id': 'b', 'group_id': 'g1', 'split': 'development', 'passage': 'Original text.', 'claim': 'Different unsupported claim.', 'expected_accept': False, 'reviewed': True, 'reviewed_by': 'human'},
            {'id': 'c', 'group_id': 'g2', 'split': 'heldout', 'passage': 'Another source.', 'claim': 'Another claim.', 'expected_accept': True, 'reviewed': False, 'reviewed_by': ''}]}

    def test_cannot_accidentally_mix_splits(self):
        with self.assertRaisesRegex(ValueError, 'Choose development or heldout'):
            select_cases(self.data())

    def test_unreviewed_cases_block_before_model_loading(self):
        data = self.data()
        data['cases'][0]['reviewed'] = False
        with self.assertRaisesRegex(ValueError, 'human label review'):
            select_cases(data, 'development')

    def test_only_selected_reviewed_development_cases_are_returned(self):
        self.assertEqual([c['id'] for c in select_cases(self.data(), 'development')], ['a', 'b'])

    def test_scenario_pairs_cannot_leak_between_splits(self):
        data = self.data()
        data['cases'][1]['split'] = 'heldout'
        with self.assertRaisesRegex(ValueError, 'group cannot cross'):
            select_cases(data, 'development')

    def test_labels_require_boolean_and_both_classes(self):
        data = self.data()
        data['cases'][0]['expected_accept'] = 'yes'
        with self.assertRaisesRegex(ValueError, 'boolean'):
            select_cases(data, 'development')
        data = self.data()
        data['cases'][1]['expected_accept'] = True
        with self.assertRaisesRegex(ValueError, 'supported and unsupported'):
            select_cases(data, 'development')
