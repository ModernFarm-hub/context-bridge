# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
import json
from pathlib import Path
import tempfile
import unittest
from live_test import prepare, register, write, readiness
from mcp_server import ContextService


class LiveTests(unittest.TestCase):
    def test_only_expected_session_and_revoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, _, _ = prepare(root)
            value = json.loads(config.read_text())
            transcript = root / 'source.jsonl'
            transcript.write_text(json.dumps({'type': 'user', 'sessionId': value['source_session'], 'message': {'role': 'user', 'content': 'ORCHID731 retention 37 days'}}) + '\n')
            self.assertFalse(register(config, {'session_id': 'wrong', 'transcript_path': str(transcript)}))
            self.assertTrue(register(config, {'session_id': value['source_session'], 'transcript_path': str(transcript)}))
            service = ContextService(config)
            try:
                self.assertEqual(len(service.call('context_search', {'query': 'ORCHID731'})['results']), 1)
                value = json.loads(config.read_text())
                value.update(capture_enabled=False, approved_transcripts=[])
                write(config, value)
                self.assertFalse(register(config, {'session_id': value['source_session'], 'transcript_path': str(transcript)}))
                self.assertEqual(service.call('context_search', {'query': 'ORCHID731'})['results'], [])
            finally:
                service.bridge.db.close()


class ReadinessTests(unittest.TestCase):
    def test_missing_empty_and_present_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'source.jsonl'
            value = {'capture_enabled': True, 'approved_transcripts': []}
            self.assertFalse(readiness(value))
            value['approved_transcripts'] = [str(path)]
            self.assertFalse(readiness(value))
            path.touch()
            self.assertFalse(readiness(value))
            path.write_text('{}\n')
            self.assertTrue(readiness(value))
            value['capture_enabled'] = False
            self.assertFalse(readiness(value))
