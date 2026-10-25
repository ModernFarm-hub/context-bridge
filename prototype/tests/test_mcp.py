# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from mcp_server import ContextService, serve
from setup_demo import setup
from contextlib import redirect_stdout


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        with redirect_stdout(io.StringIO()):
            self.config = setup(self.tmp.name)
        self.service = ContextService(self.config)
        self.addCleanup(lambda: self.service.bridge and self.service.bridge.db.close())

    def call(self, query):
        return self.service.call('context_search', {'query': query})['results']

    def test_refresh_append_and_allowlist_revocation(self):
        self.assertEqual(len(self.call('retention')), 3)
        config = json.loads(self.config.read_text())
        path = Path(config['approved_transcripts'][0])
        with path.open('a') as stream:
            stream.write(json.dumps({'type': 'user', 'sessionId': 'demo-research', 'message': {'role': 'user', 'content': 'liveupdate confirmed'}}) + '\n')
        self.assertEqual(len(self.call('liveupdate')), 1)
        config['approved_transcripts'].remove(str(path))
        self.config.write_text(json.dumps(config))
        self.assertEqual(self.call('liveupdate'), [])

    def test_truncation_and_missing_file_withdrawal(self):
        hit = self.call('Confluence')[0]
        path = Path(hit['source'])
        path.write_text('')
        self.assertEqual(self.call('Confluence'), [])
        path.unlink()
        self.assertEqual(self.call('Confluence'), [])

    def test_read_scoped_and_no_identity_override(self):
        hit = self.call('Confluence')[0]
        value = self.service.call('context_read', {'source': hit['source'], 'line': hit['line']})
        self.assertIn('90 days', value['record']['body'])
        with self.assertRaises(ValueError):
            self.service.call('context_read', {'source': '/etc/passwd', 'line': 1})
        with self.assertRaises(ValueError):
            self.service.call('context_search', {'query': 'retention', 'employee': 'bob'})

    def test_invalid_capture_skips_bad_file_without_blocking_other_sources(self):
        self.call('retention')
        config = json.loads(self.config.read_text())
        Path(config['approved_transcripts'][0]).write_text('bad-json\n')
        result = self.service.call('context_search', {'query': 'retention'})
        self.assertTrue(result['results'])
        self.assertEqual(result['capture_status']['malformed_line_count'], 1)

    def test_subprocess_handshake_and_search(self):
        requests = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '1'}}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'context_search', 'arguments': {'query': 'Confluence'}}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'context_search', 'arguments': {'query': 'retention', 'employee': 'bob'}}},
        ]
        server = Path(__file__).resolve().parents[1] / 'mcp_server.py'
        process = subprocess.run([sys.executable, str(server), '--config', str(self.config)], input=''.join(json.dumps(r) + '\n' for r in requests), text=True, capture_output=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        responses = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(len(responses), 4)
        self.assertEqual(len(responses[1]['result']['tools']), 2)
        self.assertFalse(responses[2]['result']['isError'])
        self.assertTrue(responses[3]['result']['isError'])
        payload = json.loads(responses[2]['result']['content'][0]['text'])
        self.assertEqual(len(payload['results']), 1)

    def test_protocol_errors_do_not_crash(self):
        output = io.StringIO()
        serve(self.service, io.StringIO('bad\n[]\n' + json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}) + '\n'), output)
        codes = [json.loads(line)['error']['code'] for line in output.getvalue().splitlines()]
        self.assertEqual(codes, [-32700, -32600, -32000])
