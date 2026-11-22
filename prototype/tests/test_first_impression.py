# SPDX-License-Identifier: Apache-2.0
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout,redirect_stderr
from unittest.mock import patch
import demo
from import_lifecycle import offer_semantic,finish_import
from session_manager import Sessions


class FirstImpressionTests(unittest.TestCase):
    def test_demo_is_offline_disposable_and_does_not_touch_a_real_library(self):
        real_temp=tempfile.TemporaryDirectory
        with real_temp() as directory:
            root=Path(directory)
            user=root/'user-library';user.mkdir()
            (user/'profile.json').write_text('Do not read or overwrite this user file')
            before=(user/'profile.json').read_bytes()
            created=[]
            def temporary(*args,**kwargs):
                kwargs['dir']=root
                result=real_temp(*args,**kwargs);created.append(Path(result.name));return result
            with patch.dict(os.environ,{'CONTEXT_BRIDGE_HOME':str(user)}), patch.object(demo.tempfile,'TemporaryDirectory',side_effect=temporary), patch('urllib.request.urlopen',side_effect=AssertionError('network')), patch('socket.create_connection',side_effect=AssertionError('network')), redirect_stdout(io.StringIO()) as out:
                demo.main()
            text=out.getvalue()
            self.assertIn('10 invented conversations',text)
            self.assertEqual(text.count('Search 1:'),1)
            self.assertIn('paraphrased question',text)
            for label in ('ChatGPT','Claude','Claude Code'):
                self.assertIn('Source: '+label+' ·',text)
            self.assertIn('previous container image',text)
            self.assertIn(demo.MCP_COMMAND,text)
            self.assertNotIn('alice',text.casefold());self.assertNotIn('bob',text.casefold())
            self.assertTrue(created)
            self.assertTrue(all(not path.exists() for path in created))
            self.assertEqual((user/'profile.json').read_bytes(),before)
            self.assertEqual(list(user.iterdir()),[user/'profile.json'])

    def test_noninteractive_offer_never_prompts_or_creates_state(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(sys.stdin,'isatty',return_value=False), patch('builtins.input',side_effect=AssertionError('must not prompt')):
            root=Path(directory)/'absent'
            offer_semantic(root)
            self.assertFalse(root.exists())

    def test_decline_is_remembered_and_acceptance_enables_once(self):
        for response in ('n','yes'):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as directory, patch.object(sys.stdin,'isatty',return_value=True), patch('builtins.input',return_value=response) as ask, patch('configure_semantic.enable') as enable:
                root=Path(directory)
                offer_semantic(root);offer_semantic(root)
                self.assertEqual(ask.call_count,1)
                self.assertEqual(ask.call_args.args[0],'Enable semantic search for better recall? Downloads about 90 MB, runs locally. [y/N] ')
                self.assertEqual(enable.call_count,1 if response=='yes' else 0)
                self.assertEqual(json.loads(Sessions(root).config.read_text())['semantic_offer'],'accepted' if response=='yes' else 'declined')

    def test_successful_cli_import_offers_once_and_empty_import_does_not(self):
        import imports
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);archive=root/'export.zip'
            def write(conversations):
                with zipfile.ZipFile(archive,'w') as out:
                    out.writestr('conversations.json',json.dumps(conversations))
            argv=['context-bridge import','claude',str(archive),'--directory',str(root/'library')]
            with patch.object(sys,'argv',argv),patch.object(sys.stdin,'isatty',return_value=True),patch('builtins.input',return_value='n') as ask,redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                write([]);imports.main();self.assertEqual(ask.call_count,0)
                write([{'uuid':'one','name':'Plan','chat_messages':[{'uuid':'m','sender':'human','text':'Plan deployment'}]}])
                imports.main();imports.main();self.assertEqual(ask.call_count,1)

    def test_hybrid_warmup_uses_progress_and_configured_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=Sessions(root).config
            data=json.loads(config.read_text());data['retrieval']={'mode':'hybrid'};data['retrieval_python']='/synthetic/semantic/bin/python';config.write_text(json.dumps(data))
            with patch('subprocess.run') as run,redirect_stderr(io.StringIO()) as out:
                finish_import(root)
            self.assertIn('Embedding imported conversations locally',out.getvalue())
            self.assertEqual(run.call_args.args[0][0],'/synthetic/semantic/bin/python')
            self.assertIn('--backfill',run.call_args.args[0])

    def test_product_help_and_dispatch_exclude_archived_commands(self):
        # Load the dispatcher as its installed package, without invoking it.
        import cli
        forbidden=('evaluate','compare','select-retrieval','label-queries','check-support','evaluate-support','setup-demo','live-test','download-support-model')
        self.assertFalse(set(forbidden)&set(cli.COMMANDS))
        with patch.object(sys,'argv',['context-bridge','--help']),redirect_stdout(io.StringIO()) as out:
            cli.main()
        for command in forbidden:
            self.assertNotIn(command,out.getvalue())
        for command in ('demo','import','mcp','semantic','stats','remove'):
            self.assertIn(command,out.getvalue())


@unittest.skipUnless(os.environ.get('CONTEXT_BRIDGE_TEST_MODEL'),'Needs local verified model')
class ImportEmbeddingTests(unittest.TestCase):
    def test_each_provider_embeds_during_import_before_first_search(self):
        from configure_semantic import configure
        from semantic import model
        from imports import import_export,import_code,project_preview
        from codex_capture import import_codex,preview
        from mcp_server import ContextService
        directory=str(Path(os.environ['CONTEXT_BRIDGE_TEST_MODEL']).resolve())
        embedder=model(directory)
        for provider in ('chatgpt','claude','claude-code','codex'):
            with self.subTest(provider=provider),tempfile.TemporaryDirectory() as temporary,redirect_stderr(io.StringIO()) as progress:
                root=Path(temporary).resolve();library=root/'library'
                configure(library,directory)
                if provider in ('chatgpt','claude'):
                    archive=root/'export.zip'
                    if provider=='chatgpt':
                        conversations=[{'id':'one','title':'Planning','current_node':'m','mapping':{'m':{'parent':None,'message':{'id':'m','author':{'role':'user'},'content':{'content_type':'text','parts':['BACKFILL842 approval required']}}}}}]
                    else:
                        conversations=[{'uuid':'one','name':'Planning','chat_messages':[{'uuid':'m','sender':'human','text':'BACKFILL842 approval required'}]}]
                    with zipfile.ZipFile(archive,'w') as out:out.writestr('conversations.json',json.dumps(conversations))
                    import_export(provider,archive,library)
                elif provider=='claude-code':
                    project=root/'projects/project';project.mkdir(parents=True)
                    (project/'one.jsonl').write_text(json.dumps({'type':'user','uuid':'m','sessionId':'one','message':{'role':'user','content':'BACKFILL842 approval required'}})+'\n')
                    import_code(project_preview(root/'projects'),library)
                else:
                    home=root/'codex';sessions=home/'sessions';sessions.mkdir(parents=True)
                    project=str(root/'app')
                    rows=[{'type':'session_meta','payload':{'id':'one'}},{'type':'turn_context','payload':{'cwd':project}},{'type':'response_item','ordinal':1,'payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'BACKFILL842 approval required'}]}}]
                    (sessions/'rollout-one.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
                    import_codex(preview(home),library,home)
                self.assertIn('Embedding imported conversations locally',progress.getvalue())
                service=ContextService(Sessions(library).config)
                before=embedder.inference_calls
                try:
                    result=service.call('context_search',{'query':'BACKFILL842'})
                    self.assertTrue(result['results'])
                    self.assertEqual(embedder.inference_calls-before,1,'Only query inference should remain after import')
                    self.assertEqual(service.bridge.db.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0],1)
                finally:
                    if service.bridge:service.bridge.db.close()

    def test_cli_import_uses_semantic_runtime_and_keeps_stdout_json(self):
        import subprocess
        import shutil
        from configure_semantic import configure
        from mcp_server import ContextService
        from semantic import model
        model_directory=str(Path(os.environ['CONTEXT_BRIDGE_TEST_MODEL']).resolve())
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();library=root/'library'
            configure(library,model_directory)
            archive=root/'export.zip'
            with zipfile.ZipFile(archive,'w') as out:
                out.writestr('conversations.json',json.dumps([{'uuid':'cli','name':'CLI planning','chat_messages':[{'uuid':'m','sender':'human','text':'CLIWARM842 must be approved'}]}]))
            source=root/'source';source.mkdir()
            (source/'context_bridge').symlink_to(Path(__file__).parents[1].resolve(),target_is_directory=True)
            env={**os.environ,'PYTHONPATH':str(source),'HF_HUB_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'}
            launcher=shutil.which('python3') or sys.executable
            run=subprocess.run([launcher,'-m','context_bridge','import','claude',str(archive),'--directory',str(library)],cwd=root,env=env,text=True,capture_output=True,timeout=30)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual(json.loads(run.stdout)['messages_imported'],1)
            self.assertIn('Local embeddings ready',run.stderr)
            self.assertNotIn('Enable semantic search',run.stdout+run.stderr)
            embedder=model(model_directory)
            before=embedder.inference_calls
            service=ContextService(Sessions(library).config)
            try:
                self.assertTrue(service.call('context_search',{'query':'CLIWARM842'})['results'])
                self.assertEqual(embedder.inference_calls-before,1)
            finally:
                if service.bridge:service.bridge.db.close()
