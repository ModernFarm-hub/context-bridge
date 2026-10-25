# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile
from bridge import Bridge
from imports import import_export
from local_profile import local_identity
from mcp_server import ContextService, public_result
from privacy import redact
from session_manager import Sessions, atomic_write, PAGE


class TrustScaleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def bridge(self, library='local', profile='default'):
        bridge=Bridge(self.root/'index.db',library,profile)
        self.addCleanup(bridge.db.close)
        return bridge

    def message(self, body, mid='m1'):
        return json.dumps({'type':'user','uuid':mid,'sessionId':'s1','message':{'role':'user','content':body}})+'\n'

    def test_all_requested_secret_families_are_filtered_idempotently(self):
        secrets=['sk-'+'a'*32, 'sk-ant-'+'b'*32, 'AKIA'+'A'*16, 'ghp_'+'c'*32, 'xoxb-123456789-abcdefghi', '-----BEGIN RSA PRIVATE KEY-----\nVERYPRIVATE842\n-----END RSA PRIVATE KEY-----', 'bearer '+ 'my-secret-token-842', 'API_KEY=customValue842', 'export PASSWORD="a spaced password842"', 'KEY=plainsecret842', 'DATABASE_URL=postgres://user:password@localhost/db']
        for secret in secrets:
            with self.subTest(secret_family=secret.split('-')[0][:12]):
                filtered=redact(secret)
                self.assertIn('[REDACTED]',filtered)
                self.assertEqual(redact(filtered),filtered)
                self.assertNotEqual(filtered,secret)
        self.assertEqual(redact('RETENTION_DAYS=45 and approval by Maya.'),'RETENTION_DAYS=45 and approval by Maya.')
        self.assertEqual(redact('-----BEGIN PRIVATE KEY-----\nunfinished842'),'[REDACTED]')

    def test_redacted_before_index_read_and_wire_with_stable_offsets(self):
        secret='sk-ant-'+'c'*32
        path=self.root/'source.jsonl'
        path.write_text(self.message('FIND842 API_KEY="envsecret842" '+secret+' safe ending'))
        bridge=self.bridge()
        bridge.ingest(path)
        stored=bridge.db.execute('SELECT body FROM records').fetchone()[0]
        self.assertNotIn(secret,stored)
        self.assertNotIn('envsecret842',stored)
        self.assertEqual(bridge.search(secret),[])
        hit=bridge.search('FIND842')[0]
        read=bridge.read(hit['source'],hit['line'])
        self.assertEqual(read['body'],stored[read['passage_start']:read['passage_end']])
        # Last-boundary defense also covers metadata or values introduced later.
        wire=public_result({'body':'Bearer unexpectedsecret842','source':str(path)})
        self.assertEqual(wire,{'body':'Bearer [REDACTED]'})

    def test_export_managed_copy_and_title_are_redacted(self):
        archive=self.root/'export.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('conversations.json',json.dumps([{'uuid':'c1','name':'TITLE842 KEY=titleSecret842','chat_messages':[{'uuid':'m1','sender':'human','text':'BODY842 TOKEN=bodySecret842'}]}]))
        library=self.root/'library'
        import_export('claude',archive,library)
        config=json.loads(Sessions(library).config.read_text())
        self.assertNotIn('titleSecret842',json.dumps(config))
        managed=Path(config['approved_transcripts'][0]).read_text()
        self.assertNotIn('bodySecret842',managed)
        self.assertIn('[REDACTED]',managed)

    def test_tool_thinking_and_replayed_bodies_are_excluded(self):
        path=self.root/'source.jsonl'
        path.write_text(self.message([{'type':'tool_use','name':'shell','input':{'command':'TOOLUSE842'}}, {'type':'tool_result','content':'TOOLRESULT842'}, {'type':'thinking','thinking':'THINK842'}, {'type':'text','text':'HUMAN842 permitted'}]))
        bridge=self.bridge()
        bridge.ingest(path)
        self.assertTrue(bridge.search('HUMAN842'))
        for token in ['TOOLUSE842','TOOLRESULT842','THINK842']:
            self.assertEqual(bridge.search(token),[])

    def test_incremental_offsets_partial_line_restart_and_malformed_status(self):
        path=self.root/'source.jsonl'
        first=self.message('FIRST842 finding')
        path.write_text(first)
        bridge=self.bridge()
        bridge.ingest(path)
        self.assertEqual(bridge.ingest(path),0)
        self.assertEqual(bridge.ingest_status['bytes_read'],0)
        second=self.message('SECOND842 finding','m2')
        with path.open('a') as stream:
            stream.write('bad json\n'+second[:15])
        bridge.ingest(path)
        self.assertTrue(bridge.ingest_status['incremental'])
        self.assertEqual(bridge.ingest_status['malformed_lines'],[2])
        self.assertEqual(bridge.search('SECOND842'),[])
        with path.open('a') as stream:
            stream.write(second[15:])
        restarted=self.bridge()
        self.assertEqual(restarted.ingest(path),1)
        self.assertEqual(restarted.ingest_status['bytes_read'],len(second.encode()))
        self.assertEqual(restarted.ingest_status['malformed_lines'],[2])
        self.assertTrue(restarted.search('SECOND842'))
        state=json.loads(restarted.db.execute('SELECT state FROM ingestion_state').fetchone()[0])
        self.assertEqual(state['offset'],path.stat().st_size)
        self.assertEqual(state['line'],3)

    def test_rewrite_truncate_atomic_replace_remove_stale_fts_entries(self):
        path=self.root/'source.jsonl'
        bridge=self.bridge()
        path.write_text(self.message('ORIGINAL842 finding'))
        bridge.ingest(path)
        path.write_text(self.message('REPLACED842 finding'))
        bridge.ingest(path)
        self.assertEqual(bridge.search('ORIGINAL842'),[])
        self.assertTrue(bridge.search('REPLACED842'))
        other=self.root/'replacement.jsonl'
        other.write_text(self.message('ATOMIC842 finding'))
        other.replace(path)
        bridge.ingest(path)
        self.assertEqual(bridge.search('REPLACED842'),[])
        self.assertTrue(bridge.search('ATOMIC842'))
        path.write_text('')
        bridge.ingest(path)
        self.assertEqual(bridge.search('ATOMIC842'),[])

    def test_revoke_reapprove_unchanged_file_reindexes_and_missing_withdraws(self):
        manager=Sessions(self.root/'library')
        path=self.root/'source.jsonl'
        path.write_text(self.message('APPROVED842 finding'))
        config=json.loads(manager.config.read_text())
        config['approved_transcripts']=[str(path)]
        atomic_write(manager.config,config)
        service=ContextService(manager.config)
        self.addCleanup(lambda: service.bridge and service.bridge.db.close())
        self.assertTrue(service.call('context_search',{'query':'APPROVED842'})['results'])
        config['approved_transcripts']=[]
        atomic_write(manager.config,config)
        self.assertEqual(service.call('context_search',{'query':'APPROVED842'})['results'],[])
        config['approved_transcripts']=[str(path)]
        atomic_write(manager.config,config)
        self.assertTrue(service.call('context_search',{'query':'APPROVED842'})['results'])
        path.unlink()
        self.assertEqual(service.call('context_search',{'query':'APPROVED842'})['results'],[])

    def test_legacy_database_redaction_migration_keeps_other_profile_isolated(self):
        db=sqlite3.connect(self.root/'index.db')
        db.execute('CREATE TABLE records (tenant TEXT, employee TEXT, session TEXT, source TEXT, line INTEGER, fingerprint TEXT, timestamp TEXT, role TEXT, body TEXT, PRIMARY KEY(tenant,employee,source,line))')
        db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?)',('old-library','old-user','s','legacy',1,'fp',None,'user','LEGACY842 KEY=legacySecret842'))
        db.commit(); db.close()
        bridge=self.bridge('old-library','old-user')
        self.assertIn('[REDACTED]',bridge.search('LEGACY842')[0]['body'])
        self.assertEqual(bridge.search('legacySecret842'),[])
        self.assertEqual(self.bridge('other','default').search('LEGACY842'),[])
        self.assertEqual(local_identity({'tenant':'old-library','employee':'old-user'}),('old-library','old-user'))
        manager=Sessions(self.root/'new-library')
        self.assertEqual(manager.config.name,'profile.json')
        config=json.loads(manager.config.read_text())
        self.assertIn('profile_id',config)
        self.assertNotIn('employee',config)
        self.assertNotIn('ONE EMPLOYEE',PAGE)

    def test_legacy_configuration_remains_usable_without_relabeling_identity(self):
        root=self.root/'legacy'
        root.mkdir()
        old={'tenant':'old-library','employee':'old-user','database':str(root/'context.db'),'approved_transcripts':[],'sessions':{}}
        atomic_write(root/'enrollment.json',old)
        manager=Sessions(root)
        self.assertEqual(manager.config.name,'enrollment.json')
        self.assertEqual(json.loads(manager.config.read_text()),old)
        service=ContextService(manager.config)
        try:
            self.assertEqual(service.call('context_search',{'query':'nothing'})['results'],[])
        finally:
            service.bridge.db.close()

    def test_fts_queries_do_not_load_entire_corpus_into_python(self):
        path=self.root/'source.jsonl'
        path.write_text(self.message('Needle842 matching message')+self.message('unrelated background','m2'))
        bridge=self.bridge()
        bridge.ingest(path)
        statements=[]
        bridge.db.set_trace_callback(statements.append)
        self.assertTrue(bridge.search('Needle842'))
        self.assertTrue(any('bm25(' in sql for sql in statements))
        self.assertFalse(any(sql.startswith('SELECT session,source,line,timestamp,role,body FROM records WHERE tenant=') for sql in statements))

    def test_disposable_benchmark_checks_append_freshness(self):
        from benchmark import benchmark
        result=benchmark(messages=100,runs=5)
        self.assertTrue(result['append_visible'])
        self.assertEqual(result['messages'],100)
