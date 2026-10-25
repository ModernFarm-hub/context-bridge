# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from support import SupportChecker, checker


@unittest.skipUnless(os.environ.get('CONTEXT_BRIDGE_TEST_SUPPORT_MODEL'), 'Set local support model path for real offline inference')
class SupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = checker(str(Path(os.environ['CONTEXT_BRIDGE_TEST_SUPPORT_MODEL']).resolve()))

    def test_exact_supported_claim_offline(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('Network prohibited')), patch('socket.create_connection', side_effect=AssertionError('Network prohibited')):
            result = self.engine.check('Records must be deleted after 45 days.', 'Records must be deleted after 45 days.')
        self.assertEqual(result['status'], 'model_supported')
        self.assertEqual(result['threshold'], .90)
        self.assertIn('Not independent fact verification', result['notice'])

    def test_different_activity_is_not_accepted(self):
        result = self.engine.check('Maya must approve cleanup-job changes before deployment.', 'Maya must approve customer refunds.')
        self.assertNotEqual(result['status'], 'model_supported')

    def test_cross_sentence_role_swap_requires_review(self):
        result = self.engine.check('Maya approves cleanup deployments. Sam approves refunds.', 'Maya approves refunds.')
        self.assertNotEqual(result['status'], 'model_supported')

    def test_linked_owner_deadline_and_service_evidence(self):
        pairs = [
            ('Task Willow belongs to Amira. Task Willow is due Tuesday.', 'The task owned by Amira is due Tuesday.'),
            ('Ticket CASE913 concerns the export worker. The export worker is maintained by Sal.', 'Sal maintains the worker referenced by Ticket CASE913.')]
        for passage, claim in pairs:
            result = self.engine.check(passage, claim)
            self.assertEqual(result['status'], 'model_supported')
            self.assertEqual(result['support_method'], 'linked_component')
            self.assertEqual(len(result['supporting_spans']), 2)
            for span in result['supporting_spans']:
                self.assertEqual(span['text'], passage[span['start']:span['end']])

    def test_generic_shared_predicate_does_not_mix_roles(self):
        result = self.engine.check('Alice approves quarterly reports. Ben approves quarterly budgets.', 'Alice approves quarterly budgets.')
        self.assertNotEqual(result['status'], 'model_supported')

    def test_new_number_and_identifier_are_not_accepted(self):
        for passage, claim in [('Records are deleted after 30 days.', 'Records are deleted after 45 days.'), ('ORBIT624 requires approval.', 'ORBIT625 requires approval.')]:
            self.assertNotEqual(self.engine.check(passage, claim)['status'], 'model_supported')

    def test_long_inputs_abstain_without_truncation_or_inference(self):
        before = self.engine.inference_calls
        result = self.engine.check('A lengthy background sentence. ' * 200, 'Maya approves refunds.')
        self.assertEqual(result['status'], 'needs_review')
        self.assertIsNone(result['scores'])
        self.assertEqual(before, self.engine.inference_calls)

    def test_invalid_arguments_fail_closed(self):
        for passage, claim in [('', 'A claim'), ('text', ''), ('text', None), ('a' * 12001, 'claim')]:
            with self.assertRaises(ValueError):
                self.engine.check(passage, claim)

    def test_unknown_support_model_manifest_is_rejected(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'manifest.json').write_text(json.dumps({'model': 'unknown/model', 'revision': 'main'}))
            with self.assertRaisesRegex(ValueError, 'Unknown or unpinned'):
                SupportChecker(tmp)

    def test_corrupt_assets_fail_before_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'onnx').mkdir()
            (root / 'onnx/model.onnx').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                SupportChecker(root)


class ReferenceGuardLogicTests(unittest.TestCase):
    def test_ambiguous_local_support_cannot_pass_from_model_confidence_alone(self):
        engine = SupportChecker.__new__(SupportChecker)
        engine.threshold = .90
        score = {'status': 'model_supported', 'scores': {'entailment': .99, 'neutral': .005, 'contradiction': .005}}
        text = 'The production upgrade is approved. The staging upgrade is approved. The upgrade is scheduled for Monday.'
        # Only the ambiguous short-reference sentence is predicted to support
        # the compound claim; that proposed binding must still be withheld.
        def fake(passage, claim):
            if passage == text or passage.startswith('The upgrade is'):
                return dict(score)
            return {'status': 'needs_review', 'scores': {'entailment': .5, 'neutral': .5, 'contradiction': 0}}
        with patch.object(engine, '_score_passage', side_effect=fake):
            result = engine.check(text, 'The production upgrade is scheduled for Monday.')
        self.assertNotEqual(result['status'], 'model_supported')

    def test_invalid_calibration_cutoffs_are_rejected_before_asset_loading(self):
        for threshold in (True, .1, 1.0, float('nan')):
            with self.assertRaises(ValueError):
                SupportChecker('/not-a-model-directory', threshold=threshold)
