# SPDX-License-Identifier: Apache-2.0
import io
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
from bridge import Bridge
from paraphrase_benchmark import paraphrase_benchmark
from configure_semantic import enable
from semantic import model


class ParaphraseRecallTests(unittest.TestCase):
    def test_frozen_fixture_and_lexical_benchmark(self):
        result = paraphrase_benchmark()
        self.assertEqual(result['queries'],30)
        self.assertEqual(result['conversations'],30)
        self.assertGreaterEqual(result['top_5'],2/30)
        self.assertGreaterEqual(result['mrr_at_20'],result['top_1'])

    def test_porter_migration_title_weighting_title_refresh_and_handles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'messages.jsonl'
            source.write_text(json.dumps({'type':'user','sessionId':'s','uuid':'m','message':{'role':'user','content':'The gardener cultivated vegetables.'}})+'\n')
            bridge = Bridge(root/'db','library','profile')
            bridge.set_source(source,{'title':'Starting as a Photographer','provider':'chatgpt'})
            bridge.ingest(source)
            rid = bridge.search('photographer')[0]['record_id']
            table = bridge.fts
            # Reproduce a 0.7 index, then reopen through the actual migration.
            for suffix in ('ai','ad','au'):
                bridge.db.execute(f'DROP TRIGGER {table}_{suffix}')
            bridge.db.execute(f'DROP TABLE {table}')
            bridge.db.execute(f'CREATE VIRTUAL TABLE {table} USING fts5(body,tokenize="unicode61 remove_diacritics 0")')
            bridge.db.commit()
            bridge.db.close()
            bridge = Bridge(root/'db','library','profile')
            try:
                self.assertEqual(bridge.search('gardening')[0]['record_id'],rid)
                self.assertIn('gardening',bridge.search('gardening')[0]['matched_terms'])
                self.assertEqual(bridge.search('photographer')[0]['record_id'],rid)
                bridge.set_source(source,{'title':'Learning to bake','provider':'chatgpt'})
                self.assertEqual(bridge.search('photographer'),[])
                self.assertEqual(bridge.search('baking')[0]['record_id'],rid)
                # Same DB, different profile: title and content stay isolated.
                other = Bridge(root/'db','library','other')
                try:
                    self.assertEqual(other.search('baking gardening'),[])
                finally:
                    other.db.close()
            finally:
                bridge.db.close()

    def test_session_deletion_withdraws_persistent_embeddings(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge = Bridge(Path(directory)/'db','library','profile')
            try:
                bridge.db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?)',('library','profile','session','source',1,'hash',None,'user','evidence'))
                bridge.db.execute('INSERT INTO embeddings VALUES (?,?,?,?,?,?,?)',('library','profile','source',1,'signature','model','[]'))
                bridge.db.commit()
                bridge.delete_session('session')
                self.assertEqual(bridge.db.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0],0)
            finally:
                bridge.db.close()

    def test_enable_installs_extra_into_private_runtime_if_dependencies_missing(self):
        with tempfile.TemporaryDirectory() as directory, patch('importlib.util.find_spec',return_value=None), patch('venv.EnvBuilder') as builder, patch('subprocess.run') as run:
            enable(Path(directory),Path(directory)/'model')
            builder.return_value.create.assert_called_once()
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(len(commands),3)
            self.assertIn('pip',commands[0])
            self.assertEqual(commands[0][-2:],['--upgrade','pip'])
            self.assertTrue(commands[1][-1].endswith('[semantic]') or '[semantic]==' in commands[1][-1])
            self.assertIn('enable',commands[2])


@unittest.skipUnless(os.environ.get('CONTEXT_BRIDGE_TEST_MODEL'),'Set CONTEXT_BRIDGE_TEST_MODEL for offline semantic tests')
class ParaphraseModelTests(unittest.TestCase):
    def test_hybrid_recall_on_frozen_paraphrases(self):
        result = paraphrase_benchmark(os.environ['CONTEXT_BRIDGE_TEST_MODEL'])
        self.assertGreaterEqual(result['top_5'],.85)
        self.assertGreaterEqual(result['top_1'],.75)

    def test_one_command_cached_setup_backfill_restart_and_removal_offline(self):
        directory = Path(os.environ['CONTEXT_BRIDGE_TEST_MODEL']).resolve()
        with tempfile.TemporaryDirectory() as temporary:
            from imports import import_export
            from session_manager import Sessions
            from mcp_server import ContextService
            from library import remove
            import zipfile
            root = Path(temporary)
            archive = root/'export.zip'
            with zipfile.ZipFile(archive,'w') as out:
                out.writestr('conversations.json',json.dumps([{'uuid':'one','name':'Starting as a Photographer','chat_messages':[{'uuid':'m','sender':'human','text':'Build a portfolio and sell portraits to clients.'}]}]))
            import_export('claude',archive,root/'library')
            with patch('urllib.request.urlopen',side_effect=AssertionError('network prohibited')), patch('socket.create_connection',side_effect=AssertionError('network prohibited')), patch('sys.stdout',new_callable=io.StringIO):
                enable(root/'library',directory)
            launch = root/'source'
            launch.mkdir()
            (launch/'context_bridge').symlink_to(Path(__file__).parents[1].resolve(),target_is_directory=True)
            env = {**os.environ,'PYTHONPATH':str(launch),'HF_HUB_OFFLINE':'1','CONTEXT_BRIDGE_HOME':str(root/'unused')}
            run = subprocess.run([sys.executable,'-m','context_bridge','semantic','enable','--directory',str(root/'library'),'--model',str(directory)],env=env,cwd=root,text=True,capture_output=True,timeout=30)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertIn('"embedding_records": 1',run.stdout)
            requests = [{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'context_search','arguments':{'query':'taking pictures professionally'}}}]
            # Start via another environment's interpreter when available; mcp must select the configured runtime.
            launcher = Path(__file__).parents[4]/'work/release-tools-venv/bin/python'
            launcher = str(launcher) if launcher.is_file() else sys.executable
            run = subprocess.run([launcher,'-m','context_bridge','mcp','--config',str(Sessions(root/'library').config)],env=env,cwd=root,input=''.join(json.dumps(r)+'\n' for r in requests),text=True,capture_output=True,timeout=30)
            self.assertEqual(run.returncode,0,run.stderr)
            response = [json.loads(line) for line in run.stdout.splitlines() if json.loads(line).get('id')==2][0]
            self.assertFalse(response['result']['isError'],response)
            self.assertTrue(json.loads(response['result']['content'][0]['text'])['results'])
            service = ContextService(Sessions(root/'library').config)
            embedder = model(str(directory))
            before = embedder.inference_calls
            try:
                results = service.call('context_search',{'query':'taking pictures professionally'})['results']
                self.assertTrue(results)
                # Cache survives process/service restart: only the query needs inference.
                self.assertEqual(embedder.inference_calls-before,1)
                self.assertIn('matched_terms',results[0])
                self.assertGreater(service.bridge.db.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0],0)
                remove(root/'library',conversation='one')
                self.assertEqual(service.call('context_search',{'query':'taking pictures professionally'})['results'],[])
                self.assertEqual(service.bridge.db.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0],0)
            finally:
                if service.bridge:
                    service.bridge.db.close()
