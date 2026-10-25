# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from session_manager import Sessions, handler
from mcp_server import ContextService


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.manager = Sessions(self.tmp.name)

    def test_two_sources_names_and_revocation_survives_hook(self):
        first = self.manager.create('Research')
        second = self.manager.create('Code')
        for sid, text in [(first, 'ORCHID731 retention 37 days'), (second, 'Retention uses cleanup.py')]:
            path = Path(self.tmp.name) / (sid + '.jsonl')
            path.write_text(json.dumps({'type': 'user', 'sessionId': sid, 'message': {'role': 'user', 'content': text}}) + '\n')
            self.manager.register(sid, {'session_id': sid, 'transcript_path': str(path)})
        service = ContextService(self.manager.config)
        try:
            hits = service.call('context_search', {'query': 'retention'})['results']
            self.assertEqual({h['session_name'] for h in hits}, {'Research', 'Code'})
            self.manager.rename(first, 'Confluence research')
            self.assertEqual(service.call('context_search', {'query': 'ORCHID731'})['results'][0]['session_name'], 'Confluence research')
            self.manager.approve(first, False)
            self.manager.register(first, {'session_id': first, 'transcript_path': str(Path(self.tmp.name) / (first + '.jsonl'))})
            self.assertEqual(service.call('context_search', {'query': 'ORCHID731'})['results'], [])
            self.assertEqual(self.manager.status()['approved_count'], 1)
            self.manager.approve(first, True)
            self.assertEqual(len(service.call('context_search', {'query': 'ORCHID731'})['results']), 1)
        finally:
            service.bridge.db.close()

    def test_registration_and_names_validated(self):
        with self.assertRaises(ValueError):
            self.manager.create('bad\nname')
        sid = self.manager.create('Research')
        with self.assertRaises(ValueError):
            self.manager.register(sid, {'session_id': 'wrong', 'transcript_path': '/tmp/unapproved'})

    def test_terminal_commands_are_scoped(self):
        sid = self.manager.create('Source')
        with patch.object(self.manager, 'claude', return_value='/test/claude'):
            command = self.manager.launch_command(sid)
            self.assertIn('--session-id', command)
            self.assertIn(sid, command)
            reader = self.manager.launch_command()
            self.assertIn('--mcp-config', reader)
            self.assertIn('--mcp-config', command)
            self.assertNotIn('--tools', reader)
            self.manager.approve(sid, False)
            with self.assertRaises(ValueError):
                self.manager.launch_command(sid)

    def test_launch_failure_returns_usable_terminal_command(self):
        from types import SimpleNamespace
        sid = self.manager.create('Launch test')
        with patch.object(self.manager, 'claude', return_value='/test/claude'), patch('session_manager.subprocess.run', return_value=SimpleNamespace(returncode=1)):
            result = self.manager.launch(sid)
        self.assertFalse(result['opened'])
        self.assertIn('terminal-source', result['command'])
        self.assertIn(sid, result['command'])
        self.assertIn('macOS blocked', result['message'])

    def test_http_rejects_missing_token_foreign_origin_and_host(self):
        # Exercise the real HTTP parser/handler over an in-memory socket.
        import io
        from types import SimpleNamespace
        class Socket:
            def __init__(self, request):
                self.request = io.BytesIO(request)
                self.response = bytearray()
            def makefile(self, *args):
                return self.request
            def sendall(self, data):
                self.response.extend(data)
        def request(method, path, headers=None, body=None):
            payload = json.dumps(body).encode() if body else b''
            fields = {'Host': '127.0.0.1:8123', 'Content-Length': str(len(payload)), **(headers or {})}
            raw = (method + ' ' + path + ' HTTP/1.0\r\n' + ''.join(k + ': ' + v + '\r\n' for k, v in fields.items()) + '\r\n').encode() + payload
            sock = Socket(raw)
            handler(self.manager, 'test-token')(sock, ('127.0.0.1', 50000), SimpleNamespace(server_port=8123))
            head, data = bytes(sock.response).split(b'\r\n\r\n', 1)
            return int(head.split()[1]), data
        self.assertEqual(request('GET', '/state')[0], 403)
        self.assertEqual(request('POST', '/action', {'X-Bridge-Token': 'test-token', 'Origin': 'https://evil.example'}, {'action': 'create', 'name': 'blocked'})[0], 403)
        self.assertEqual(request('GET', '/state', {'X-Bridge-Token': 'test-token', 'Host': 'evil.example'})[0], 403)
        self.assertEqual(request('POST', '/action', {'X-Bridge-Token': 'test-token'}, {'action': 'create', 'name': '<script>not executed</script>'})[0], 200)
        code, body = request('GET', '/state', {'X-Bridge-Token': 'test-token'})
        self.assertEqual(code, 200)
        self.assertEqual(len(json.loads(body)['sessions']), 1)
