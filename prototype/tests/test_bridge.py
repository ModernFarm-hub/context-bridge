# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
import json
from pathlib import Path
import tempfile
import unittest
from bridge import Bridge


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.a = Bridge(self.root / 'context.db', 'company', 'alice')
        self.b = Bridge(self.root / 'context.db', 'company', 'bob')
        self.c = Bridge(self.root / 'context.db', 'other-company', 'alice')
        for bridge in (self.a, self.b, self.c):
            self.addCleanup(bridge.db.close)

    def write(self, name, session, text, role='assistant'):
        path = self.root / name
        path.write_text(json.dumps({'type': role, 'sessionId': session, 'timestamp': '2026-10-23T10:00:00Z', 'message': {'role': role, 'content': text}}) + '\n')
        return path

    def test_four_sessions_and_employee_tenant_isolation(self):
        for session, text in [('research', 'Confluence retention is 90 days'), ('code', 'Retention is enforced by cleanup.py'), ('request', 'Client requests retention details'), ('other', 'Deployment procedure')]:
            self.a.ingest(self.write(session, session, text))
        self.b.ingest(self.write('bob', 'private-bob', 'retention secret-bob'))
        self.c.ingest(self.write('tenant', 'private-tenant', 'retention secret-tenant'))
        hits = self.a.search('retention')
        self.assertEqual({h['session'] for h in hits}, {'research', 'code', 'request'})
        self.assertTrue(all(h['line'] == 1 and h['timestamp'] for h in hits))
        self.assertEqual(self.a.search('secret'), [])

    def test_append_partial_restart_and_retry(self):
        path = self.write('live', 's', 'old finding')
        self.assertEqual(self.a.ingest(path), 1)
        self.assertEqual(self.a.ingest(path), 0)
        record = json.dumps({'type': 'user', 'sessionId': 's', 'message': {'role': 'user', 'content': 'new finding'}})
        with path.open('a') as stream:
            stream.write(record[:20])
        self.assertEqual(self.a.ingest(path), 0)
        with path.open('a') as stream:
            stream.write(record[20:] + '\n')
        restarted = Bridge(self.root / 'context.db', 'company', 'alice')
        self.addCleanup(restarted.db.close)
        self.assertEqual(restarted.ingest(path), 1)
        self.assertEqual(len(restarted.search('finding')), 2)

    def test_tool_output_excluded_and_scoped_delete(self):
        path = self.write('tool', 'same-session', [{'type': 'tool_result', 'content': [{'type': 'text', 'text': 'TOOLONLY842 hidden result'}]}, {'type':'text', 'text':'Confluence retention evidence'}], 'user')
        self.a.ingest(path)
        self.b.ingest(path)
        self.assertEqual(len(self.a.search('Confluence')), 1)
        self.assertEqual(self.a.search('TOOLONLY842'), [])
        self.assertEqual(self.a.delete_session('same-session'), 1)
        self.assertEqual(self.a.search('Confluence'), [])
        self.assertEqual(len(self.b.search('Confluence')), 1)

    def test_malformed_record_skips_bad_line_and_preserves_valid_records(self):
        path = self.write('bad', 's', 'finding')
        with path.open('a') as stream:
            stream.write('not-json\n')
        self.a.ingest(path)
        self.assertEqual(len(self.a.search('finding')), 1)
        self.assertEqual(self.a.ingest_status['malformed_lines'], [2])

    def test_internal_blobs_excluded_and_old_index_entries_withdrawn(self):
        path = self.write('mixed', 's', 'real finding')
        blob = {'type': 'api-request-blob', 'sessionId': 's', 'message': {'role': 'user', 'content': 'private-reminder replayed finding'}}
        mismatch = {'type': 'assistant', 'sessionId': 's', 'message': {'role': 'user', 'content': 'invalid-envelope'}}
        unknown = {'sessionId': 's', 'message': {'role': 'user', 'content': 'untyped-internal'}}
        with path.open('a') as stream:
            for item in (blob, mismatch, unknown):
                stream.write(json.dumps(item) + '\n')
        # Simulate an index row created by the previous permissive adapter.
        with self.a.db:
            self.a.db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?)', (*self.a.owner, 's', str(path.resolve()), 2, 'legacy', None, 'user', 'private-reminder replayed finding'))
        self.a.ingest(path)
        self.assertEqual(len(self.a.search('finding')), 1)
        self.assertEqual(self.a.search('private-reminder invalid-envelope untyped-internal'), [])

    def test_foreign_corpus_cannot_change_authorized_scores(self):
        self.a.ingest(self.write('mine', 'a', 'Retention policy requires approval.'))
        before = self.a.search('retention approval')
        self.b.ingest(self.write('foreign', 'b', 'Retention retention retention approval approval.'))
        self.c.ingest(self.write('tenant-foreign', 'c', 'Retention approval policy.'))
        self.assertEqual(self.a.search('retention approval'), before)

    def test_missing_identity_rejected(self):
        with self.assertRaises(ValueError):
            Bridge(':memory:', 'company', '')


if __name__ == '__main__':
    unittest.main()
