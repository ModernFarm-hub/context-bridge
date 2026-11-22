# SPDX-License-Identifier: Apache-2.0
import io
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from mcp_server import ContextService
from session_manager import Sessions,atomic_write
from usage import report,research_snapshot,main as usage_main


class UsageSavingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.manager=Sessions(self.root/'library')
        self.path=self.root/'source.jsonl'
        def message(mid,body,usage=None):
            return {'type':'assistant','uuid':mid,'sessionId':'session','message':{'id':mid,'role':'assistant','content':body,**({'usage':usage} if usage else {})}}
        first={'input_tokens':100,'output_tokens':20,'cache_read_input_tokens':30,'cache_creation_input_tokens':40}
        self.rows=[{'type':'user','uuid':'u','sessionId':'session','message':{'role':'user','content':'Research this invented policy'}},message('a','PRIOR842 synthetic finding',first),message('a','PRIOR842 repeated recorded assistant',first),message('b','FINAL842 the answer is five attempts',{'input_tokens':50,'output_tokens':10,'cache_read_input_tokens':5,'cache_creation_input_tokens':5})]
        self.path.write_text(''.join(json.dumps(row)+'\n' for row in self.rows))
        data=json.loads(self.manager.config.read_text());data['approved_transcripts']=[str(self.path)]
        data['sources']={str(self.path):{'provider':'claude-code','conversation_id':'session','title':'Synthetic policy'}};atomic_write(self.manager.config,data)
        self.service=ContextService(self.manager.config)
        self.addCleanup(lambda:self.service.bridge and self.service.bridge.db.close())

    def search(self,query='FINAL842',**kwargs):return self.service.call('context_search',{'query':query,**kwargs})
    def events(self):return [dict(row) for row in self.service.bridge.db.execute('SELECT * FROM usage_calls ORDER BY id')]

    def test_known_usage_dedup_paging_and_counterfactual_math(self):
        hit=self.search()['results'][0]
        for _ in range(2):self.service.call('context_read',{'record_id':hit['record_id'],'context':0})
        self.search('NEVERMATCH999')
        self.search('FINAL842')  # Search after the last read is not credited as reuse.
        result=report(self.service.bridge,1.25)
        self.assertEqual(result['original_research_tokens'],30)
        self.assertEqual(len(result['conversations']),1)
        self.assertEqual(result['lookup_tokens'],sum(row['estimated_tokens'] for row in self.events()))
        self.assertEqual(result['estimated_tokens_avoided'],30-result['lookup_tokens'])
        self.assertEqual(result['estimated_usd_avoided'],result['estimated_tokens_avoided']*1.25/1e6)
        self.assertEqual(result['searches_without_read'],2)
        self.assertEqual(result['empty_searches'],1)
        self.assertEqual(sum(c['lookup_tokens'] for c in result['conversations'])+result['unassigned_lookup_tokens'],result['lookup_tokens'])
        for price in (-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):report(self.service.bridge,price)

    def test_trivial_turn_excludes_37000_cached_tokens_and_old_logs_are_reinterpreted(self):
        rows=[{'type':'user','uuid':'question','sessionId':'session','message':{'role':'user','content':'Test finding: SYNTHETIC842 has a retention period of 37 days. Please acknowledge.'}},
              {'type':'assistant','uuid':'ack','sessionId':'session','message':{'id':'ack','role':'assistant','content':'Acknowledged: SYNTHETIC842 has a 37-day retention period.','usage':{'input_tokens':2,'output_tokens':136,'cache_read_input_tokens':24840,'cache_creation_input_tokens':12121}}}]
        rows.append(dict(rows[-1]))  # Replayed message ID must not double-count output or overhead.
        self.path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        rid=self.search('SYNTHETIC842')['results'][0]['record_id']
        self.service.call('context_read',{'record_id':rid})
        result=report(self.service.bridge)
        self.assertEqual(result['incremental_research_credit_tokens'],136)
        self.assertEqual(result['all_in_upper_bound_tokens'],37099)
        self.assertLess(result['estimated_tokens_avoided'],0)
        row=self.service.bridge.db.execute("SELECT id,research FROM usage_calls WHERE tool='context_read'").fetchone()
        old=json.loads(row['research'])
        old[0]['original_tokens']=37099
        for key in ('incremental_credit_tokens','all_in_upper_bound_tokens','excluded_cache_read_tokens','baseline_context_tokens','cited_context_tokens'):old[0].pop(key,None)
        with self.service.bridge.db:self.service.bridge.db.execute('UPDATE usage_calls SET research=? WHERE id=?',(json.dumps(old),row['id']))
        # Existing logs must be fixed immediately, without a re-import or source scan.
        corrected=report(self.service.bridge)
        self.assertEqual(corrected['incremental_research_credit_tokens'],136)
        self.assertEqual(corrected['all_in_upper_bound_tokens'],37099)
        self.assertLess(corrected['estimated_tokens_avoided'],0)
        self.assertEqual(json.loads(self.service.bridge.db.execute('SELECT research FROM usage_calls WHERE id=?',(row['id'],)).fetchone()[0])[0]['original_tokens'],37099)

    def test_context_growth_plus_outputs(self):
        self.rows[-1]['message']['usage']={'input_tokens':200,'output_tokens':10,'cache_read_input_tokens':100,'cache_creation_input_tokens':70}
        self.path.write_text(''.join(json.dumps(row)+'\n' for row in self.rows))
        hit=self.search()['results'][0]
        self.service.call('context_read',{'record_id':hit['record_id'],'context':0})
        result=report(self.service.bridge)
        # First context 170, cited context 370, outputs 20+10; duplicate first ID excluded.
        self.assertEqual(result['incremental_research_credit_tokens'],230)
        self.assertEqual(result['all_in_upper_bound_tokens'],570)

    def test_default_has_no_query_text_and_config_can_opt_in_and_disable(self):
        self.service.client_name='local-test-client'
        self.search('PRIVATEQUERY999')
        row=self.events()[0]
        self.assertIsNone(row['query_text']);self.assertNotIn('PRIVATEQUERY999',json.dumps(row))
        self.assertEqual(row['client'],'local-test-client');self.assertTrue(row['timestamp'])
        self.assertEqual(row['estimated_tokens'],math.ceil(row['response_chars']/4))
        data=json.loads(self.manager.config.read_text());data['usage']={'store_queries':True};atomic_write(self.manager.config,data)
        self.search('OPTIN842 api_key: synthetic-secret')
        self.assertIn('OPTIN842',self.events()[-1]['query_text']);self.assertNotIn('synthetic-secret',self.events()[-1]['query_text'])
        data['usage']['enabled']=False;atomic_write(self.manager.config,data)
        count=len(self.events());self.search();self.assertEqual(len(self.events()),count)

    def test_read_window_accounts_only_visible_messages_and_handles_following_codex_usage(self):
        hit=self.search('PRIOR842')['results'][0]
        self.service.call('context_read',{'record_id':hit['record_id'],'context':0})
        self.assertEqual(report(self.service.bridge)['original_research_tokens'],20)
        # Codex usage arrives after the assistant text; cached input is already in input.
        home=self.root/'codex';path=home/'sessions/rollout-test.jsonl';path.parent.mkdir(parents=True)
        rows=[{'type':'session_meta','payload':{'id':'codex-thread'}},{'type':'turn_context','payload':{'cwd':str(self.root/'app')}},{'type':'response_item','ordinal':1,'payload':{'type':'message','role':'assistant','content':[{'type':'output_text','text':'CODEXCOST842 answer'}]}},{'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':1000,'cached_input_tokens':400,'output_tokens':150,'reasoning_output_tokens':70}}}}]
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        from codex_capture import preview,import_codex
        import_codex(preview(home),self.manager.root,home)
        hit=self.search('CODEXCOST842')['results'][0]
        self.service.call('context_read',{'record_id':hit['record_id'],'context':0})
        result=report(self.service.bridge)
        row=next(r for r in result['conversations'] if r['method']=='codex-recorded')
        self.assertEqual(row['original_tokens'],150)
        self.assertEqual(row['all_in_upper_bound_tokens'],1150)
        # A second Codex turn has input 1,500, including 900 cached; cumulative input is 2,500.
        more=[{'type':'response_item','ordinal':2,'payload':{'type':'message','role':'assistant','content':[{'type':'output_text','text':'CODEXGROWTH842 answer'}]}},{'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':2500,'cached_input_tokens':1300,'output_tokens':200},'last_token_usage':{'input_tokens':1500,'cached_input_tokens':900,'output_tokens':50}}}}]
        with path.open('a') as stream:stream.write(''.join(json.dumps(item)+'\n' for item in more))
        hit=self.search('CODEXGROWTH842')['results'][0]
        self.service.call('context_read',{'record_id':hit['record_id'],'context':0})
        row=next(r for r in report(self.service.bridge)['conversations'] if r['method']=='codex-recorded')
        self.assertEqual(row['original_tokens'],700)  # 200 outputs + (1,500 - 1,000) context.
        self.assertEqual(row['all_in_upper_bound_tokens'],2700)

    def test_off_page_neighbors_do_not_get_research_credit(self):
        body='PAGED842 '+('background '*80)
        rows=[{'type':'user','uuid':'long','sessionId':'session','message':{'role':'user','content':body}}, {'type':'assistant','uuid':'answer','sessionId':'session','message':{'id':'answer','role':'assistant','content':'A recorded answer','usage':{'input_tokens':10000,'output_tokens':100}}}]
        self.path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        rid=self.search('PAGED842')['results'][0]['record_id']
        self.service.call('context_read',{'record_id':rid,'context':1,'max_chars':256})
        first=report(self.service.bridge)
        self.assertLess(first['original_research_tokens'],100)
        self.assertEqual(first['original_research_tokens'],0)
        self.assertEqual(first['conversations'][0]['method'],'claude-code-recorded')
        self.service.call('context_read',{'record_id':rid,'context':1,'max_chars':256,'start':len(body)+2})
        self.assertEqual(report(self.service.bridge)['original_research_tokens'],100)

    def test_exports_are_labelled_visible_text_estimates_and_no_read_gets_no_credit(self):
        self.search()
        result=report(self.service.bridge)
        self.assertEqual(result['original_research_tokens'],0)
        self.assertLessEqual(result['estimated_tokens_avoided'],0)
        from imports import import_export
        import zipfile
        archive=self.root/'export.zip'
        with zipfile.ZipFile(archive,'w') as out:
            out.writestr('conversations.json',json.dumps([{'uuid':'export','name':'Exported notes','chat_messages':[{'uuid':'m','sender':'human','text':'EXPORT842 '+('visible text '*10)}]}]))
        import_export('claude',archive,self.manager.root)
        hit=self.search('EXPORT842')['results'][0]
        self.service.call('context_read',{'record_id':hit['record_id'],'context':0})
        row=next(r for r in report(self.service.bridge)['conversations'] if r['method']=='visible-text-estimate')
        self.assertGreater(row['original_tokens'],0)

    def test_real_stdio_compact_full_client_sizes_errors_and_clear(self):
        rid=self.search()['results'][0]['record_id']
        with self.service.bridge.db:self.service.bridge.db.execute('DELETE FROM usage_calls')
        calls=[('context_search',{'query':'FINAL842','format':'compact'}),('context_search',{'query':'FINAL842'}),('context_read',{'record_id':rid,'context':0}),('context_search',{'query':'NEVERMATCH999','format':'compact'}),('context_search',{'query':'bad','format':'invalid'})]
        requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','clientInfo':{'name':'stdio-accounting','version':'1'}}},{'jsonrpc':'2.0','method':'notifications/initialized'}]+[{'jsonrpc':'2.0','id':i+2,'method':'tools/call','params':{'name':name,'arguments':arguments}} for i,(name,arguments) in enumerate(calls)]
        run=subprocess.run([sys.executable,str(Path(__file__).parents[1]/'mcp_server.py'),'--config',str(self.manager.config)],input=''.join(json.dumps(r)+'\n' for r in requests),text=True,capture_output=True,timeout=15)
        self.assertEqual(run.returncode,0,run.stderr)
        responses={r['id']:r['result'] for r in map(json.loads,run.stdout.splitlines())}
        compact=json.loads(responses[2]['content'][0]['text'])
        self.assertEqual(set(compact),{'results'})
        self.assertIn('age_days',compact['results'][0])
        self.assertEqual(set(compact['results'][0]),{'label','link','record_id','snippet','more_matches','age_days','time_sensitive','time_sensitive_terms'})
        full=json.loads(responses[3]['content'][0]['text'])
        self.assertIn('capture_status',full)
        self.assertTrue({'age_days','time_sensitive','time_sensitive_terms','uncertainty','conflicts'}<=set(full['results'][0]))
        self.assertNotIn('uncertainty',compact['results'][0])
        self.assertNotIn('conflicts',compact['results'][0])
        self.assertTrue(responses[6]['isError'])
        for i,row in enumerate(self.events()):
            chars=sum(len(block['text']) for block in responses[i+2]['content'])
            self.assertEqual(row['response_chars'],chars)
            self.assertEqual(row['client'],'stdio-accounting');self.assertIsNone(row['query_text'])
        argv=['context-bridge usage','clear','--directory',str(self.manager.root),'--json']
        with patch.object(sys,'argv',argv),redirect_stdout(io.StringIO()) as out:usage_main()
        self.assertEqual(json.loads(out.getvalue())['deleted_calls'],5)
        self.assertEqual(self.events(),[])
        # Profile isolation: clearing here never deletes another owner's events.
        self.service.bridge.db.execute("INSERT INTO usage_calls (tenant,employee,tool) VALUES ('other','other','context_search')");self.service.bridge.db.commit()
        with patch.object(sys,'argv',argv),redirect_stdout(io.StringIO()):usage_main()
        self.assertEqual(self.service.bridge.db.execute('SELECT COUNT(*) FROM usage_calls').fetchone()[0],1)
