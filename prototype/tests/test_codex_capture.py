# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from codex_capture import preview, import_codex, message, user_text
from library import remove, exclusions
from mcp_server import ContextService, public_result
from session_manager import Sessions


class CodexCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = self.root/'codex'
        self.library = self.root/'library'
        self.project = str(self.root/'app')
        self.other = str(self.root/'other')
        self.home.mkdir()
        (self.home/'session_index.jsonl').write_text(json.dumps({'id':'thread-one','thread_name':'Release planning'})+'\n{bad\n')
        self.first = self.rollout('thread-one',self.project,'CAPTURE842 first user')
        self.rollout('thread-other',self.other,'OTHER842 private')

    def text(self,body,role='user',ordinal=1):
        return {'type':'response_item','timestamp':'2026-11-14T12:00:00Z','ordinal':ordinal,'payload':{'type':'message','role':role,'content':[{'type':'input_text' if role=='user' else 'output_text','text':body}]}}

    def rollout(self,thread,project,body):
        folder = self.home/'sessions/2026/11/14'
        folder.mkdir(parents=True,exist_ok=True)
        path = folder/('rollout-2026-11-14T12-00-00-'+thread+'.jsonl')
        rows = [{'type':'session_meta','timestamp':'2026-11-14T12:00:00Z','payload':{'id':thread}}, {'type':'turn_context','payload':{'cwd':project}},self.text(body)]
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        return path

    def approve(self):
        projects = preview(self.home)
        return import_codex({self.project:projects[self.project]},self.library,self.home)

    def service(self):
        service = ContextService(Sessions(self.library).config)
        self.addCleanup(lambda: service.bridge and service.bridge.db.close())
        return service

    def search(self,service,query):
        return service.call('context_search',{'query':query})

    def test_preview_consent_titles_cwd_and_exclusions(self):
        with patch.dict(os.environ,{'CODEX_HOME':str(self.home)}):
            projects = preview()
        self.assertEqual(set(projects),{self.project,self.other})
        self.assertFalse(self.library.exists())
        original = self.first.read_bytes()
        self.approve()
        service = self.service()
        hit = self.search(service,'CAPTURE842')['results'][0]
        self.assertEqual(hit['source_label'],"ChatGPT desktop · 'Release planning' · 2026-11-14")
        self.assertEqual(hit['link'],'codex://threads/thread-one')
        self.assertEqual(self.search(service,'OTHER842')['results'],[])
        self.assertNotIn(str(self.root),json.dumps(public_result(hit)))
        remove(self.library,conversation='codex://threads/thread-one')
        self.assertEqual(self.search(service,'CAPTURE842')['results'],[])
        self.approve()  # Re-approval alone does not undo a deliberate conversation exclusion.
        self.assertEqual(self.search(service,'CAPTURE842')['results'],[])
        self.assertNotIn('thread-one',json.dumps(exclusions(self.library)))
        exclusions(self.library,'codex://threads/thread-one')
        self.assertTrue(self.search(service,'CAPTURE842')['results'])
        self.assertEqual(self.first.read_bytes(),original)

    def test_only_text_messages_all_other_types_and_injections_are_excluded(self):
        self.approve()
        excluded = ['reasoning','custom_tool_call','custom_tool_call_output','function_call','function_call_output','event_msg','token_count','token_usage_record','turn_context','world_state','unknown-new-type']
        rows = [{'type':kind,'payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'LEAK999 '+kind}]}} for kind in excluded]
        rows += [{'type':'response_item','payload':{'type':kind,'role':'assistant','encrypted_content':'ENCRYPTED999','content':[{'type':'output_text','text':'LEAK999'}]}} for kind in excluded]
        rows += [self.text('DEVELOPER999','developer'),self.text('SYSTEM999','system'),self.text('<environment_context>ENV999 private</environment_context>\nACTUAL842 keep'), self.text('# AGENTS.md instructions for /private\n<INSTRUCTIONS>AGENT999</INSTRUCTIONS>'),self.text('ACK842 assistant','assistant',5)]
        with self.first.open('a') as out:
            out.write('{bad-json\n')
            for row in rows:
                out.write(json.dumps(row)+'\n')
        service = self.service()
        hit = self.search(service,'ACTUAL842')['results'][0]
        window = service.call('context_read',{'record_id':hit['record_id'],'context':10})['record']['body']
        self.assertIn('ACTUAL842',window)
        self.assertIn('ACK842',window)
        for token in ('LEAK999','DEVELOPER999','SYSTEM999','ENV999','AGENT999','ENCRYPTED999'):
            self.assertNotIn(token,window)
            self.assertEqual(self.search(service,token)['results'],[])
        self.assertEqual(self.search(service,'CAPTURE842')['capture_status']['malformed_line_count'],1)
        self.assertEqual(user_text('# AGENTS.md instructions for /private\nNever disclose AGENT999'),'')
        self.assertEqual(user_text('Please review AGENTS.md'),'Please review AGENTS.md')
        self.assertIsNone(message({'type':'response_item','payload':{'type':'message','role':'assistant','content':[{'type':'reasoning','text':'THINK999'}]}},'thread'))
        for tag in ('environment_context','INSTRUCTIONS','skills_instructions','user_instructions'):
            self.assertEqual(user_text('<'+tag+'>secret'),'')

    def test_new_threads_only_approved_project_and_incremental_append_redaction(self):
        self.approve()
        service = self.service()
        self.search(service,'CAPTURE842')
        path = self.rollout('thread-new',self.project,'FRESH842 password: "sensitive-value"')
        self.rollout('thread-unapproved',self.other,'HIDDEN842')
        hit = self.search(service,'FRESH842')['results'][0]
        self.assertIn('FRESH842',hit['source_label'])
        self.assertNotIn('sensitive-value',json.dumps(hit))
        self.assertEqual(self.search(service,'HIDDEN842')['results'],[])
        old_size = path.stat().st_size
        with path.open('a') as out:
            out.write(json.dumps(self.text('GROW842 new turn','assistant',2))+'\n')
        self.assertTrue(self.search(service,'GROW842')['results'])
        self.assertTrue(service.bridge._states[str(path)]['offset'] > old_size)
        # A partially written final line is held until its newline arrives.
        with path.open('a') as out:
            out.write(json.dumps(self.text('PARTIAL842 pending','assistant',3)))
        self.assertEqual(self.search(service,'PARTIAL842')['results'],[])
        with path.open('a') as out:
            out.write('\n')
        self.assertTrue(self.search(service,'PARTIAL842')['results'])
        state = service.bridge._states[str(path)]
        self.assertEqual(state['offset'],path.stat().st_size)
        self.assertGreater(state['offset'],old_size)
        # Unchanged files perform no transcript reads.
        service.bridge.ingest(path,resolved=True)
        self.assertEqual(service.bridge.ingest_status['bytes_read'],0)
        remove(self.library,provider='codex')
        self.rollout('thread-after-revoke',self.project,'REVOKED842')
        self.assertEqual(self.search(service,'REVOKED842')['results'],[])
        self.assertEqual(self.search(service,'GROW842')['results'],[])
        self.assertTrue(path.exists())

    def test_symlink_and_unknown_lines_do_not_capture(self):
        (self.home/'sessions/2026/11/14/rollout-link.jsonl').symlink_to(self.first)
        projects = preview(self.home)
        self.assertEqual(len(projects[self.project]),1)
        for value in ({'type':'new-type'}, {'type':'response_item','payload':None}, {'type':'response_item','payload':{'type':'message','role':'user','content':'not-list'}}):
            self.assertIsNone(message(value,'thread'))

    def test_negative_classification_cache_survives_restart_and_invalidates(self):
        import codex_capture
        self.approve()
        rejected = self.rollout('thread-rejected',self.other,'NEVER_STORE_SECRET_TEXT')
        failed = self.home/'sessions/2026/11/14/rollout-unclassifiable.jsonl'
        failed.write_text('{bad-json\n'+json.dumps(self.text('NEVER_STORE_SECRET_TEXT'))+'\n')
        service = self.service()
        with patch.object(codex_capture,'metadata',wraps=codex_capture.metadata) as classify:
            self.search(service,'CAPTURE842')
            self.assertEqual(classify.call_count,2)
            self.search(service,'CAPTURE842')
            self.assertEqual(classify.call_count,2)
        restarted = self.service()
        with patch.object(codex_capture,'metadata',wraps=codex_capture.metadata) as classify:
            self.search(restarted,'CAPTURE842')
            self.assertEqual(classify.call_count,0)
            with rejected.open('a') as out:
                out.write(json.dumps(self.text('changed tail'))+'\n')
            self.search(restarted,'CAPTURE842')
            self.assertEqual(classify.call_count,1)
            # Failed classifications also refresh after new headers arrive.
            with failed.open('a') as out:
                out.write(json.dumps({'type':'session_meta','payload':{'id':'fixed-thread'}})+'\n')
                out.write(json.dumps({'type':'turn_context','payload':{'cwd':self.project}})+'\n')
            self.search(restarted,'CAPTURE842')
            self.assertEqual(classify.call_count,2)
        cached = [tuple(row) for row in restarted.bridge.db.execute('SELECT * FROM codex_classifications')]
        self.assertNotIn('NEVER_STORE_SECRET_TEXT',json.dumps(cached))
        # A new approval changes the cache epoch, so an unchanged rejected file is eligible.
        projects=preview(self.home)
        import_codex({self.other:projects[self.other]},self.library,self.home)
        self.assertTrue(self.search(restarted,'OTHER842')['results'])
        self.assertTrue(self.search(restarted,'NEVER_STORE_SECRET_TEXT')['results'])

    def test_header_only_metadata_and_preview_skip_chat_json_and_stop_early(self):
        import codex_capture
        path=self.home/'sessions/2026/11/14/rollout-prefix.jsonl'
        rows=[self.text('DO_NOT_DECODE_CHAT_TEXT'),
              {'type':'response_item','payload':{'type':'turn_context','cwd':'DO_NOT_DECODE_CHAT_TEXT'}},
              {'type':'session_meta','payload':{'id':'header-only'}},
              {'type':'turn_context','payload':{'cwd':self.other}}]
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows)+'NOT_JSON_AFTER_HEADERS\n')
        loads=json.loads
        def headers_only(raw,*args,**kwargs):
            self.assertNotIn(b'DO_NOT_DECODE_CHAT_TEXT',raw)
            return loads(raw,*args,**kwargs)
        with patch.object(codex_capture.json,'loads',side_effect=headers_only) as decode:
            self.assertEqual(codex_capture.metadata(path)['conversation_id'],'header-only')
            self.assertEqual(decode.call_count,2)
        with patch.object(codex_capture,'title_excerpt',side_effect=AssertionError('Preview must not read excerpts')):
            self.assertIn(path.resolve(),preview(self.home)[self.other])

    def test_unreadable_classification_is_cached_and_benchmark_layout_is_checked(self):
        import codex_capture
        self.approve()
        self.rollout('thread-unreadable',self.other,'NOT_READ')
        service=self.service()
        with patch.object(codex_capture,'metadata',side_effect=PermissionError('unreadable')) as classify:
            self.search(service,'CAPTURE842')
            self.assertEqual(classify.call_count,1)
            self.search(service,'CAPTURE842')
            self.assertEqual(classify.call_count,1)
        from codex_benchmark import codex_benchmark
        result=codex_benchmark(files=8,bytes_per_file=4096,approved=2,runs=3)
        self.assertEqual(result['approved_files'],2)
        self.assertEqual(result['cached_unapproved_files'],6)
        self.assertEqual(result['total_rollout_bytes'],8*4096)
        self.assertGreaterEqual(result['first_refresh_ms'],0)

    def test_real_cli_preview_selection_path_and_stdio_citation(self):
        launch = self.root/'source'
        launch.mkdir()
        (launch/'context_bridge').symlink_to(Path(__file__).parents[1].resolve(),target_is_directory=True)
        env = {**os.environ,'CODEX_HOME':str(self.home),'PYTHONPATH':str(launch),'PYTHONDONTWRITEBYTECODE':'1'}
        base = [sys.executable,'-m','context_bridge']
        run = subprocess.run(base+['import','codex','--directory',str(self.library)],env=env,cwd=self.root,text=True,capture_output=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn('Preview only',run.stdout)
        self.assertFalse(self.library.exists())
        number = list(preview(self.home)).index(self.project)+1
        run = subprocess.run(base+['import','codex','--select',str(number),'--yes','--directory',str(self.library)],env=env,cwd=self.root,text=True,capture_output=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        requests = [{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'context_search','arguments':{'query':'CAPTURE842'}}}]
        run = subprocess.run(base+['mcp','--directory',str(self.library)],env=env,cwd=self.root,input=''.join(json.dumps(r)+'\n' for r in requests),text=True,capture_output=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        replies = {r['id']:r for r in map(json.loads,run.stdout.splitlines())}
        hit = json.loads(replies[2]['result']['content'][0]['text'])['results'][0]
        self.assertEqual(hit['link'],'codex://threads/thread-one')
        self.assertNotIn(str(self.root),run.stdout)
        run = subprocess.run(base+['import','codex','--path',self.project,'--yes','--directory',str(self.library)],env=env,cwd=self.root,text=True,capture_output=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
