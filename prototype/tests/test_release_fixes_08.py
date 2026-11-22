# SPDX-License-Identifier: Apache-2.0
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from unittest.mock import patch
from configure_semantic import enable
from imports import import_export
from library import main as library_main
from mcp_server import ContextService
from session_manager import Sessions


class ConversationGroupingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.library = self.root/'library'
        self.archive = self.root/'export.zip'
        conversations = []
        for i in range(5):
            mapping = {}
            previous = None
            for j in range(10 if i==0 else 1):
                mid = str(j)
                mapping[mid] = {'parent':previous,'message':{'id':mid,'author':{'role':'user'},'create_time':1720000000+j,'content':{'content_type':'text','parts':[('release approval '*(j+1))+'GROUP842 recorded decision']}}}
                previous = mid
            conversations.append({'id':str(i),'title':'New chat','current_node':previous,'mapping':mapping})
        with zipfile.ZipFile(self.archive,'w') as out:
            out.writestr('conversations.json',json.dumps(conversations))
        import_export('chatgpt',self.archive,self.library)
        self.service = ContextService(Sessions(self.library).config)
        self.addCleanup(lambda:self.service.bridge and self.service.bridge.db.close())

    def assert_grouped(self,results):
        self.assertEqual(len(results),5)
        self.assertEqual(len({hit['link'] for hit in results}),5)
        dominant = next(hit for hit in results if hit['link']=='https://chatgpt.com/c/0')
        self.assertEqual(dominant['more_matches_in_conversation'],9)
        self.assertTrue(all(hit['more_matches_in_conversation']==0 for hit in results if hit is not dominant))
        self.assertTrue(all(hit['record_id'] for hit in results))

    def test_bm25_and_temporal_limits_are_conversations_with_complete_counts(self):
        for query in ('GROUP842 release approval','latest release approval'):
            with self.subTest(query=query):
                result = self.service.call('context_search',{'query':query,'limit':5})
                self.assert_grouped(result['results'])
                self.assertEqual(result['capture_status']['retrieval_mode'],'bm25')
        # There must be no hidden 200-message candidate cap before grouping.
        data = json.loads(Sessions(self.library).config.read_text())
        source = next(path for path,meta in data['sources'].items() if meta['conversation_id']=='0')
        with Path(source).open('a') as out:
            for i in range(250):
                out.write(json.dumps({'type':'user','uuid':'extra-'+str(i),'sessionId':'chatgpt:0','message':{'role':'user','content':'GROUP842 release approval'}})+'\n')
        results = self.service.call('context_search',{'query':'GROUP842 release approval','limit':5})['results']
        self.assertEqual(len(results),5)
        self.assertEqual(next(r for r in results if r['link'].endswith('/0'))['more_matches_in_conversation'],259)

    def test_real_stdio_sources_are_one_per_conversation_and_stats_reports_mode(self):
        requests = [{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'context_search','arguments':{'query':'GROUP842 release approval','limit':5}}}]
        run = subprocess.run([sys.executable,str(Path(__file__).parents[1]/'mcp_server.py'),'--config',str(Sessions(self.library).config)],input=''.join(json.dumps(r)+'\n' for r in requests),text=True,capture_output=True,timeout=15)
        self.assertEqual(run.returncode,0,run.stderr)
        response = next(r for r in map(json.loads,run.stdout.splitlines()) if r.get('id')==2)['result']
        self.assert_grouped(json.loads(response['content'][0]['text'])['results'])
        self.assertEqual(sum(block['text'].startswith('Source: ') for block in response['content']),5)
        with redirect_stdout(io.StringIO()) as out:
            library_main(['stats','--directory',str(self.library)])
        stats = json.loads(out.getvalue())
        self.assertEqual(stats['retrieval_mode'],'bm25')
        self.assertEqual(stats['capture_status']['retrieval_mode'],'bm25')

    @unittest.skipUnless(os.environ.get('CONTEXT_BRIDGE_TEST_MODEL'),'Needs local model')
    def test_hybrid_groups_after_fusion_and_reports_mode(self):
        config = Sessions(self.library).config
        data = json.loads(config.read_text())
        data['retrieval'] = {'mode':'hybrid','model_directory':os.environ['CONTEXT_BRIDGE_TEST_MODEL'],'minimum_similarity':.35}
        config.write_text(json.dumps(data))
        result = self.service.call('context_search',{'query':'GROUP842 release approval','limit':5})
        self.assert_grouped(result['results'])
        self.assertEqual(result['capture_status']['retrieval_mode'],'hybrid')
        with redirect_stdout(io.StringIO()) as out:
            library_main(['stats','--directory',str(self.library)])
        self.assertEqual(json.loads(out.getvalue())['retrieval_mode'],'hybrid')


class SemanticInstallFailureTests(unittest.TestCase):
    def test_unpublished_noneditable_install_explains_recovery_and_upgrades_pip_first(self):
        import configure_semantic
        with tempfile.TemporaryDirectory() as directory, patch.object(configure_semantic,'__file__',str(Path(directory)/'site-packages/context_bridge/configure_semantic.py')), patch('importlib.util.find_spec',return_value=None), patch('venv.EnvBuilder'), patch('subprocess.run') as run:
            run.side_effect = [subprocess.CompletedProcess([],0),subprocess.CalledProcessError(1,['pip'])]
            with self.assertRaises(SystemExit) as error:
                enable(Path(directory)/'library',Path(directory)/'model')
            message = str(error.exception)
            self.assertIn('may not be on PyPI',message)
            self.assertIn('--from-source /path/to/context-bridge',message)
            self.assertIn('[semantic]',message)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(commands[0][-2:],['--upgrade','pip'])
            self.assertEqual(commands[1][-1],'context-bridge-local[semantic]==0.10.0b1')

    def test_explicit_source_checkout_is_used_instead_of_pypi(self):
        import configure_semantic
        with tempfile.TemporaryDirectory() as directory, patch.object(configure_semantic,'__file__',str(Path(directory)/'site-packages/context_bridge/configure_semantic.py')), patch('importlib.util.find_spec',return_value=None), patch('venv.EnvBuilder'), patch('subprocess.run') as run:
            root = Path(directory)
            source = root/'source'
            source.mkdir()
            (source/'pyproject.toml').write_text('[project]\nname="context-bridge-local"\n')
            enable(root/'library',root/'model',source)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(commands[1][-1],str(source.resolve())+'[semantic]')
            self.assertEqual(commands[0][-2:],['--upgrade','pip'])
            self.assertIn('enable',commands[2])

    def test_bad_source_path_and_pip_upgrade_failures_are_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(SystemExit,'pyproject.toml'):
                enable(Path(directory),Path(directory)/'model',Path(directory)/'missing')
            with patch('importlib.util.find_spec',return_value=None), patch('venv.EnvBuilder'), patch('subprocess.run',side_effect=subprocess.CalledProcessError(1,['pip'])):
                with self.assertRaisesRegex(SystemExit,'Could not upgrade pip'):
                    enable(Path(directory),Path(directory)/'model')
