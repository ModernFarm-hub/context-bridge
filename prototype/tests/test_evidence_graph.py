# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
import unittest
from evidence_graph import anchors, components, sentence_spans


class EvidenceGraphTests(unittest.TestCase):
    def test_shared_action_does_not_link_different_actors(self):
        self.assertEqual(len(components('Alice approves quarterly reports. Ben approves quarterly budgets.')), 2)
        self.assertEqual(len(components('Alice approves deployments. Ben approves refunds.')), 2)

    def test_shared_named_task_connects_owner_and_deadline(self):
        groups = components('Task Willow belongs to Amira. Task Willow is due Tuesday.')
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]['spans']), 2)
        self.assertTrue(groups[0]['links'])

    def test_service_phrase_connects_different_sentences(self):
        self.assertEqual(len(components('Ticket CASE913 concerns the export worker. The export worker is maintained by Sal.')), 1)

    def test_shared_first_name_does_not_merge_full_names(self):
        self.assertEqual(len(components('Alex King maintains the desktop SDK. Alex Reed maintains the web SDK.')), 2)

    def test_conflicting_numeric_assignments_keep_joint_context(self):
        self.assertEqual(len(components('An old note sets the request limit to 3. A current note sets the request limit to 8.')), 1)

    def test_number_alone_does_not_connect_unrelated_subjects(self):
        self.assertEqual(len(components('Requests expire after 30 seconds. Invoices expire after 30 days.')), 2)

    def test_original_unicode_offsets_and_determinism(self):
        text = '  Café notes.\n\nTask Willow has an owner. Task Willow is due Tuesday. '
        groups = components(text)
        self.assertEqual(groups, components(text))
        for group in groups:
            for span in group['spans']:
                self.assertEqual(span['text'], text[span['start']:span['end']])
        self.assertEqual(len(sentence_spans(text)), 3)

    def test_nearby_identifiers_do_not_match(self):
        self.assertFalse(anchors('CASE913') & anchors('CASE914'))

    def test_unique_short_definite_reference_links_prior_subject(self):
        groups = components('The emergency repair is authorized. The repair is scheduled for Thursday.')
        self.assertEqual(len(groups), 1)
        self.assertTrue(any('definite-reference:' in key for link in groups[0]['links'] for key in link['shared_anchors']))

    def test_competing_subjects_do_not_resolve_short_reference(self):
        from evidence_graph import binding_risks
        text = 'The production upgrade is approved. The staging upgrade is approved. The upgrade is scheduled for Monday.'
        self.assertTrue(binding_risks(text)['ambiguous_references'])
        self.assertEqual(len(components(text)), 3)

    def test_short_reference_does_not_link_future_antecedent(self):
        self.assertEqual(len(components('The repair is scheduled for Thursday. The emergency repair is authorized.')), 2)

    def test_different_heads_are_not_resolved(self):
        self.assertEqual(len(components('The production rollout is authorized. The archive is scheduled for Thursday.')), 2)
