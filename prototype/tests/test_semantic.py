# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bridge import Bridge
from evaluate import Fixture
from semantic import identifiers, model


class SemanticPolicyTests(unittest.TestCase):
    def test_identifier_canonicalization_preserves_distinct_numbers(self):
        self.assertEqual(identifiers('PINE-963 PINE_963 pine963'), {'pine963'})
        self.assertNotEqual(identifiers('PINE963'), identifiers('PINE964'))


@unittest.skipUnless(os.environ.get('CONTEXT_BRIDGE_TEST_MODEL'), 'Set CONTEXT_BRIDGE_TEST_MODEL to run real offline embedding tests')
class LocalModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = str(Path(os.environ['CONTEXT_BRIDGE_TEST_MODEL']).resolve())
        cls.embedder = model(cls.directory)
        cls.settings = {'mode': 'hybrid', 'model_directory': cls.directory, 'minimum_similarity': .35}

    def test_inference_does_not_request_network(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('Network prohibited')), patch('socket.create_connection', side_effect=AssertionError('Network prohibited')):
            vectors = self.embedder.encode(['Deployment approval is required.', 'Release permission must be granted.'])
        self.assertEqual(vectors.shape, (2, 384))
        self.assertGreater(float(vectors[0] @ vectors[1]), .35)

    def test_token_chunks_are_original_nonempty_and_cover_late_text(self):
        text = 'Ordinary unrelated background. ' * 400 + 'Final deployment exception requires approval.'
        chunks = self.embedder.chunks(text)
        self.assertTrue(chunks)
        self.assertTrue(all(start < end and body == text[start:end] for start,end,body in chunks))
        self.assertIn('Final deployment exception requires approval.', chunks[-1][2])

    def test_chunk_sizes_preserve_offsets_and_reject_invalid_windows(self):
        text = 'Unicode café and release notes. ' * 100 + 'Final recovery instruction.'
        for window in (32, 64, 200):
            chunks = self.embedder.chunks(text, window)
            self.assertTrue(all(body == text[start:end] for start, end, body in chunks))
            self.assertTrue(all(len(self.embedder.splitter.encode(body, add_special_tokens=False).ids) <= window + 2 for _, _, body in chunks))
            self.assertIn('Final recovery instruction.', chunks[-1][2])
        for window in (True, 0, 600, '64'):
            with self.assertRaises(ValueError):
                self.embedder.chunks(text, window)

    def test_sentence_chunks_preserve_complete_statements_and_neighbor_context(self):
        text = 'Background details. ' * 90 + 'Recovery uses the previous release. Its configuration must be restored too.\n\nFinal notes.'
        chunks = self.embedder.chunks(text, 64, sentence_chunks=True)
        bodies = [body for _, _, body in chunks]
        self.assertIn('Recovery uses the previous release.', bodies)
        self.assertIn('Recovery uses the previous release. Its configuration must be restored too.', bodies)
        self.assertTrue(all(text[start:end] == body for start, end, body in chunks))
        self.assertEqual(len(chunks), len({(start, end) for start, end, _ in chunks}))
        for _, _, body in chunks:
            self.assertLessEqual(len(self.embedder.splitter.encode(body, add_special_tokens=False).ids), 66)
        with self.assertRaises(ValueError):
            self.embedder.chunks(text, 64, sentence_chunks='yes')

    def test_chunk_strategy_change_clears_cached_vectors(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(Path(tmp), self.settings)
            try:
                fixture.load([fixture.record('a', 'Deployment approval is required.')])
                fixture.search('deployment approval')
                bridge = fixture.service.bridge
                self.assertTrue(bridge._embedding_cache)
                bridge.configure_retrieval(dict(self.settings, sentence_chunks=True))
                self.assertFalse(bridge._embedding_cache)
            finally:
                fixture.close()

    def test_foreign_owner_data_never_reaches_embedder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            mine, foreign = Bridge(root / 'db', 'company', 'alice'), Bridge(root / 'db', 'company', 'bob')
            try:
                for bridge, name, text in [(mine, 'mine', 'Credentials belong in the managed vault.'), (foreign, 'foreign', 'BOB_PRIVATE_VAULT_DATA never shared')]:
                    path = root / (name + '.jsonl')
                    path.write_text(json.dumps({'type': 'user', 'sessionId': name, 'message': {'role': 'user', 'content': text}}) + '\n')
                    bridge.ingest(path)
                mine.configure_retrieval(self.settings)
                with patch.object(self.embedder, 'encode', wraps=self.embedder.encode) as encode:
                    mine.search('Where should secrets be kept?')
                observed = [text for call in encode.call_args_list for text in call.args[0]]
                self.assertTrue(observed)
                self.assertFalse(any('BOB_PRIVATE' in text for text in observed))
                self.assertFalse(foreign._embedding_cache)
            finally:
                mine.db.close(); foreign.db.close()

    def test_revocation_clears_vectors_before_search_or_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(Path(tmp), self.settings)
            try:
                fixture.load([fixture.record('a', 'Credentials belong in the managed vault.')])
                hits = fixture.search('Credentials')
                self.assertTrue(hits)
                self.assertTrue(fixture.service.bridge._embedding_cache)
                fixture.data['approved_transcripts'] = []
                fixture.flush()
                self.assertEqual(fixture.search('Credentials'), [])
                self.assertFalse(fixture.service.bridge._embedding_cache)
                with self.assertRaises(ValueError):
                    fixture.service.call('context_read', {'source': hits[0]['source'], 'line': hits[0]['line']})
            finally:
                fixture.close()

    def test_nearby_identifier_is_not_retrieved_semantically(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(Path(tmp), self.settings)
            try:
                fixture.load([fixture.record('near', 'LOTUS818 requires deployment approval.')])
                self.assertEqual(fixture.search('LOTUS817 deployment approval'), [])
            finally:
                fixture.close()

    def test_configuration_preserves_approvals_and_selects_correct_runtime(self):
        from configure_semantic import configure
        from session_manager import Sessions
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            manager = Sessions(tmp)
            sid = manager.create('Private research')
            manager.approve(sid, False)
            before = json.loads(manager.config.read_text())
            configure(tmp, self.directory)
            after = json.loads(manager.config.read_text())
            self.assertEqual(before['sessions'], after['sessions'])
            self.assertEqual(before['approved_transcripts'], after['approved_transcripts'])
            mcp = json.loads(manager.mcp.read_text())
            self.assertEqual(mcp['mcpServers']['context-bridge']['command'], sys.executable)
            self.assertEqual(after['retrieval']['mode'], 'hybrid')
            configure(tmp, self.directory, disable=True)
            self.assertEqual(json.loads(manager.config.read_text())['retrieval']['mode'], 'lexical')

    def test_hybrid_retrieval_through_real_stdio_server(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(Path(tmp), self.settings)
            try:
                fixture.load([fixture.record('vault', 'Client information retention duration: ninety days.')])
                messages = [
                    {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25'}},
                    {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'context_search', 'arguments': {'query': 'How long do we keep customer records?'}}}
                ]
                server = Path(__file__).resolve().parents[1] / 'mcp_server.py'
                proc = subprocess.run([sys.executable, str(server), '--config', str(fixture.config)], input=''.join(json.dumps(m)+'\n' for m in messages), capture_output=True, text=True, timeout=20)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                result = json.loads(proc.stdout.splitlines()[-1])['result']
                self.assertFalse(result['isError'])
                hits = json.loads(result['content'][0]['text'])['results']
                self.assertTrue(hits)
                self.assertIn('semantic', hits[0]['retrieval_channels'])
            finally:
                fixture.close()

    def test_question_focused_read_uses_meaning_without_word_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(Path(tmp), self.settings)
            try:
                fixture.load([fixture.record('policy', 'Client information retention duration: ninety days.')])
                record = fixture.service.call('context_read', {'source': str(fixture.root / 'policy.jsonl'), 'line': 1, 'query': 'How long do we keep customer records?'})['record']
                self.assertIn('ninety days', record['body'])
                self.assertEqual(record['read_mode'], 'question_focused')
                self.assertFalse(record['focused_window_truncated'])
            finally:
                fixture.close()

    def test_frozen_configuration_preserves_retrieval_parameters(self):
        from configure_semantic import configure
        from session_manager import Sessions
        with tempfile.TemporaryDirectory() as tmp:
            settings = dict(self.settings, token_window=64, gate_lexical=True)
            configure(tmp, self.directory, settings=settings)
            data = json.loads(Sessions(tmp).config.read_text())
            self.assertEqual(data['retrieval'], settings)
            for invalid in (dict(settings, token_window=0), dict(settings, minimum_similarity=True), dict(settings, gate_lexical='yes')):
                with self.assertRaises(ValueError):
                    configure(tmp, self.directory, settings=invalid)
                self.assertEqual(json.loads(Sessions(tmp).config.read_text())['retrieval'], settings)

    def test_unknown_model_manifest_is_rejected(self):
        from semantic import LocalEmbedder
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'manifest.json').write_text(json.dumps({'model': 'untrusted/model', 'revision': 'moving-main'}))
            with self.assertRaisesRegex(ValueError, 'Unknown or unpinned'):
                LocalEmbedder(tmp)

    def test_corrupt_model_fails_before_inference(self):
        from semantic import LocalEmbedder
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'onnx').mkdir()
            (root / 'onnx/model.onnx').write_bytes(b'corrupt graph')
            with self.assertRaises(ValueError):
                LocalEmbedder(root)


