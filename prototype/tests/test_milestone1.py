# SPDX-License-Identifier: Apache-2.0
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from unittest.mock import patch
from mcp_server import ContextService, serve
from session_manager import Sessions
from setup_demo import setup


class ReproducedBugTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        with redirect_stdout(io.StringIO()):
            self.config = setup(self.root / 'demo')
        self.service = ContextService(self.config)
        self.addCleanup(lambda: self.service.bridge and self.service.bridge.db.close())

    def rpc(self, name, arguments):
        messages = [dict(jsonrpc='2.0', id=1, method='initialize', params={'protocolVersion': '2025-06-18'}),
                    dict(jsonrpc='2.0', method='notifications/initialized'),
                    dict(jsonrpc='2.0', id=2, method='tools/call', params={'name': name, 'arguments': arguments})]
        out = io.StringIO()
        with self.assertLogs('context_bridge.mcp', level='WARNING') as log:
            serve(self.service, io.StringIO(''.join(json.dumps(x)+'\n' for x in messages)), out)
        self.assertTrue(log.output)
        return json.loads(out.getvalue().splitlines()[-1])['result']

    def test_bad_lines_with_valid_messages_after_them_do_not_break_any_search(self):
        config = json.loads(self.config.read_text())
        path = Path(config['approved_transcripts'][0])
        with path.open('ab') as handle:
            handle.write(b'bad-json\n\xff\n')
            handle.write((json.dumps({'type': 'user', 'sessionId': 'demo-research', 'message': {'role': 'user', 'content': 'afterbadline special finding'}})+'\n').encode())
        for query in ('retention', 'afterbadline'):
            result = self.service.call('context_search', {'query': query})
            self.assertTrue(result['results'])
            self.assertEqual(result['capture_status']['malformed_line_count'], 2)
            self.assertEqual(result['capture_status']['malformed_files'][0]['file'], str(path.resolve()))
        # A repaired file clears the warning rather than keeping a stale count.
        path.write_text('{}\n')
        self.assertEqual(self.service.call('context_search', {'query': 'retention'})['capture_status']['malformed_line_count'], 0)

    def test_clear_uuid_is_linked_renamed_and_revoked_with_original_source(self):
        manager = Sessions(self.root / 'manager')
        original = manager.create('Named research')
        successor = str(uuid.uuid4())
        for sid, text in [(original, 'FIRST123 earlier fact'), (successor, 'NEXT456 later fact')]:
            path = self.root / (sid+'.jsonl')
            path.write_text(json.dumps({'type': 'user', 'sessionId': sid, 'message': {'role': 'user', 'content': text}})+'\n')
            manager.register(original, {'session_id': sid, 'transcript_path': str(path)})
        service = ContextService(manager.config)
        try:
            manager.rename(original, 'Renamed research')
            self.assertEqual(service.call('context_search', {'query': 'NEXT456'})['results'][0]['session_name'], 'Renamed research')
            self.assertTrue(service.call('context_search', {'query': 'FIRST123'})['results'])
            with patch.object(manager, 'claude', return_value='/test/claude'):
                command = manager.launch_command(original)
            self.assertIn(successor, command)
            manager.approve(original, False)
            manager.register(original, {'session_id': successor, 'transcript_path': str(self.root / (successor+'.jsonl'))})
            self.assertEqual(service.call('context_search', {'query': 'NEXT456'})['results'], [])
            self.assertEqual(service.call('context_search', {'query': 'FIRST123'})['results'], [])
        finally:
            service.bridge.db.close()

    def test_long_natural_question_no_longer_has_32_word_limit(self):
        question = 'Please explain ' + 'the background of ' * 30 + 'retention'
        self.assertTrue(self.service.call('context_search', {'query': question})['results'])
        result = self.rpc('context_search', {'query': 'a'*2001})
        self.assertEqual(json.loads(result['content'][0]['text'])['error'], 'query_too_long')
        self.assertTrue(result['isError'])

    def test_record_changed_revoked_and_no_matches_have_distinct_actionable_status(self):
        hit = self.service.call('context_search', {'query': 'Confluence'})['results'][0]
        record = self.service.call('context_read', {'source': hit['source'], 'line': hit['line']})['record']
        path = Path(hit['source'])
        path.write_text(path.read_text().replace('90 days', '91 days'))
        result = self.rpc('context_read', {'record_id': hit['record_id'], 'expected_sha256': record['record_sha256']})
        self.assertEqual(json.loads(result['content'][0]['text'])['error'], 'record_changed')
        config = json.loads(self.config.read_text())
        config['approved_transcripts'].remove(hit['source'])
        self.config.write_text(json.dumps(config))
        result = self.rpc('context_read', {'record_id': hit['record_id']})
        self.assertEqual(json.loads(result['content'][0]['text'])['error'], 'source_revoked')
        self.assertEqual(self.service.call('context_search', {'query': 'totallyunmentionedterm'})['status'], 'no_matches')

    def test_protocol_versions_echo_supported_client_version(self):
        for version in ('2025-06-18', '2025-11-25'):
            out = io.StringIO()
            serve(self.service, io.StringIO(json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':version}})+'\n'), out)
            self.assertEqual(json.loads(out.getvalue())['result']['protocolVersion'], version)
