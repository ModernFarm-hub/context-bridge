# SPDX-License-Identifier: Apache-2.0
"""Table-driven credential regression cases. All values are invented."""
import json
from pathlib import Path
import tempfile
import unittest
from bridge import Bridge
from privacy import redact, REDACTION_VERSION

POSITIVE_CASES = [
    ('stripe_live', 'sk_live_'+'a'*24),
    ('stripe_test', 'sk_test_'+'b'*24),
    ('stripe_restricted', 'rk_live_'+'c'*24),
    ('stripe_restricted_test', 'rk_test_'+'d'*24),
    ('google', 'AIza'+'g'*35),
    ('openai_project', 'sk-proj-'+'p'*40),
    ('openai_service_account', 'sk-svcacct-'+'s'*40),
    ('openai', 'sk-'+'o'*32),
    ('anthropic', 'sk-ant-'+'a'*32),
    ('aws', 'AKIA'+'A'*16),
    ('github', 'ghp_'+'h'*32),
    ('slack', 'xoxb-123456789-abcdefghi'),
    ('jwt', 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzeW50aGV0aWMifQ.fakeSignature842'),
    ('url', 'https://alice:password842@example.test/path'),
    ('url_encoded', 'postgresql://alice:p%40ss%3Aword@example.test/db'),
    ('url_colon', 'redis://alice:p:a:ss@example.test:6379'),
    ('json_api_key', '{"api_key": "syntheticKey842"}'),
    ('json_password', '{"password": "syntheticPassword842"}'),
    ('json_secret', '{"secret": "syntheticSecret842"}'),
    ('json_token', '{"token": "syntheticToken842"}'),
    ('yaml_api_key', 'api_key: syntheticKey842'),
    ('yaml_secret', "secret: 'syntheticSecret842'"),
    ('json_camel', '{"apiKey": "syntheticKey842"}'),
    ('yaml_token', 'token: "syntheticToken842"'),
    ('uppercase_key', 'API_KEY: syntheticKey842'),
    ('env', 'API_KEY=syntheticKey842'),
    ('env_password', 'export PASSWORD="spaced password842"'),
    ('bearer', 'Authorization: Bearer syntheticBearer842'),
    ('private_key', '-----BEGIN RSA PRIVATE KEY-----\nSYNTHETIC842\n-----END RSA PRIVATE KEY-----'),
]
NEGATIVE_CASES = [
    'RETENTION_DAYS=45',
    'monkey: banana',
    'HOCKEY=Saturday',
    'https://alice:@example.test',
    'current retention policy requires customer records to be deleted after 45 days.',
    'Maya must approve changes to the cleanup job before deployment.',
    'Kafka uses exponential backoff and five retry attempts.',
    'Discuss API key rotation without recording the value.',
    'https://example.test/path',
    'https://alice@example.test/path',
    'release 1.2.3',
    'eyJheader.only-two-segments',
    'sk_live_',
    'AIza-not-a-real-key',
    '{"retention_days": 45}',
    'retention_days: 45',
    '{"token": null}',
    'api_key: [REDACTED]',
    '{"password": "[REDACTED]"}',
]


class CredentialTableTests(unittest.TestCase):
    def test_positive_cases_are_redacted_and_idempotent(self):
        for name,value in POSITIVE_CASES:
            with self.subTest(family=name):
                filtered=redact(value)
                self.assertNotEqual(filtered,value)
                self.assertIn('[REDACTED]',filtered)
                self.assertEqual(redact(filtered),filtered)

    def test_negative_cases_stay_intact_and_searchable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            bridge=Bridge(root/'db','local','default')
            try:
                path=root/'source.jsonl'
                path.write_text(''.join(json.dumps({'type':'user','uuid':str(i),'sessionId':'s','message':{'role':'user','content':f'KEEP{i} '+text}})+'\n' for i,text in enumerate(NEGATIVE_CASES)))
                bridge.ingest(path)
                for i,value in enumerate(NEGATIVE_CASES):
                    with self.subTest(case=i):
                        self.assertEqual(redact(value),value)
                        self.assertIn(value,bridge.search(f'KEEP{i}')[0]['body'])
                self.assertTrue(bridge.search('RETENTION_DAYS 45'))
                self.assertTrue(bridge.search('Maya approve cleanup'))
            finally:
                bridge.db.close()

    def test_url_filters_password_only_and_json_stays_valid(self):
        self.assertEqual(redact('https://alice:password842@example.test/path'),'https://alice:[REDACTED]@example.test/path')
        value=json.loads(redact('{"api_key": "fake\\\"quoted842", "retention_days": 45}'))
        self.assertEqual(value,{'api_key':'[REDACTED]','retention_days':45})

    def test_version_two_migrates_existing_records_metadata_and_fts(self):
        self.assertGreaterEqual(REDACTION_VERSION,2)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            bridge=Bridge(root/'db','local','default')
            with bridge.db:
                bridge.db.execute("DELETE FROM local_migrations WHERE name='redaction-2'")
                bridge.db.execute('INSERT OR IGNORE INTO local_migrations VALUES (?,?,?)',(*bridge.owner,'redaction-1'))
                bridge.db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?)',(*bridge.owner,'s','legacy',1,'fp',None,'user','LEGACY842 sk_live_'+'a'*24))
                bridge.db.execute('INSERT INTO source_metadata VALUES (?,?,?,?)',(*bridge.owner,'legacy',json.dumps({'provider':'chatgpt','title':'api_key: oldSecret842'})))
            bridge.db.close()
            migrated=Bridge(root/'db','local','default')
            try:
                body=migrated.db.execute('SELECT body FROM records').fetchone()[0]
                metadata=migrated.db.execute('SELECT metadata FROM source_metadata').fetchone()[0]
                self.assertNotIn('sk_live_',body)
                self.assertNotIn('oldSecret842',metadata)
                self.assertIn('[REDACTED]',body)
                self.assertTrue(migrated.search('LEGACY842'))
                self.assertEqual(migrated.search('a'*24),[])
            finally:
                migrated.db.close()
