# SPDX-License-Identifier: Apache-2.0
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from savings_real import Corpus,DATA,FakeProvider,Journal,benchmark,grade,load_tasks,run_session,make_library
from savings_real_analysis import analyze,tokens
from usage import research_snapshot

class RealBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.tasks=load_tasks()

    def test_frozen_corpus_licenses_versions_tools_and_balance(self):
        manifest=json.loads((DATA/'manifest.json').read_text())
        self.assertGreater(sum((DATA/e['path']).stat().st_size for e in manifest['files']),10_000_000)
        a=Corpus('v1');b=Corpus('v2');self.addCleanup(a.close);self.addCleanup(b.close)
        self.assertNotIn('suggest_on_error=False',a.docs['library/argparse.rst'])
        self.assertIn('suggest_on_error=False',b.docs['library/argparse.rst'])
        self.assertEqual(a.docs['library/json.rst'],b.docs['library/json.rst'])
        self.assertTrue(a.call('search_docs',{'query':'ensure_ascii'}))
        self.assertIn('library/json.rst',a.call('list_docs',{'prefix':'library/json'})['paths'])
        self.assertEqual(a.call('read_doc',{'path':'library/json.rst','start':10,'length':100})['text'],a.docs['library/json.rst'][10:110])
        for args in ({'path':'../../etc/passwd'},{'path':'library/json.rst','start':-1},{'path':'library/json.rst','length':12001}):
            with self.assertRaises(ValueError):a.call('read_doc',args)
        self.assertEqual(len(self.tasks),40)
        self.assertEqual(sum(t['variant']=='stale' for t in self.tasks),10)

    def test_exact_fact_grading_rejects_negations_and_missing_facts(self):
        self.assertTrue(grade('```json\n{"facts":{"x":"false","n":"28"}}\n```',{'x':'false','n':'28'}))
        self.assertFalse(grade('{"facts":{"x":"not false","n":"28"}}',{'x':'false','n':'28'}))
        self.assertFalse(grade('{"facts":{"x":"false"}}',{'x':'false','n':'28'}))
        self.assertFalse(grade('not 28',{'n':'28'}))

    def test_phase_a_import_uses_recorded_usage_and_full_blocks(self):
        task=self.tasks[0];corpus=Corpus('v1');self.addCleanup(corpus.close)
        (self.root/'results').mkdir();journal=Journal(self.root/'calls',20)
        provider=FakeProvider(task,'A','original')
        def signed(body):
            response=provider(body)
            response['content'].insert(0,{'type':'thinking','thinking':'Fixture thought','signature':'FIXTURE-SIGNATURE'})
            if len(body['messages'])>1:
                prior=body['messages'][-2]['content'][0]
                self.assertEqual(prior['signature'],'FIXTURE-SIGNATURE')
            for field in ('temperature','top_p','tool_choice'):self.assertNotIn(field,body)
            self.assertEqual(body['thinking'],{'type':'between_tools'})
            return response
        result=run_session(task,'A','original',0,corpus,None,journal,signed,'fixture',12,self.root)
        service=make_library(self.root,[task]);self.addCleanup(service.bridge.db.close)
        hit=service.call('context_search',{'query':task['original_question'],'format':'compact'},log=False)['results'][0]
        record=dict(service.bridge.db.execute("SELECT * FROM records WHERE role='assistant' ORDER BY line DESC LIMIT 1").fetchone())
        self.assertGreater(research_snapshot(service.bridge,record)['original_tokens'],0)
        rows=[json.loads(x) for x in (self.root/'transcripts'/ (task['id']+'.jsonl')).read_text().splitlines()]
        self.assertEqual(sum(r['message'].get('usage',{}).get('output_tokens',0) for r in rows),result['usage']['output_tokens'])
        self.assertEqual(result['usage']['input_tokens'],300)

    def test_journal_resume_pending_reservations_and_total_cap(self):
        journal=Journal(self.root/'calls',2);calls=[]
        def provider(body):calls.append(body);return {'content':[],'usage':{},'stop_reason':'end_turn'}
        body={'model':'fixture','max_tokens':20,'messages':[{'role':'user','content':'a'}]}
        first=journal.call('one',body,provider)
        self.assertEqual(journal.call('one',body,lambda b:self.fail('completed call reran')),first)
        with self.assertRaisesRegex(ValueError,'differs'):journal.call('one',{'a':2},provider)
        def broken(body):raise OSError('fixture interruption')
        with self.assertRaises(OSError):journal.call('pending',body,broken)
        with self.assertRaisesRegex(RuntimeError,'Unresolved'):journal.call('pending',body,provider)
        with self.assertRaisesRegex(RuntimeError,'Hard total'):journal.call('three',body,provider)
        self.assertEqual(len(calls),1)

    def test_refusal_truncation_and_session_call_cap(self):
        corpus=Corpus('v1');self.addCleanup(corpus.close);(self.root/'results').mkdir()
        for i,reason in enumerate(('refusal','max_tokens','tool_use')):
            task=dict(self.tasks[0],id='stop'+str(i))
            def provider(body):return {'content':[{'type':'text','text':'{"facts":{"ensure_ascii":"true","compression":"ZIP_STORED"}}'}] if reason!='tool_use' else [{'type':'tool_use','id':'x','name':'list_docs','input':{}}], 'usage':{'input_tokens':3,'output_tokens':2},'stop_reason':reason}
            result=run_session(task,'B','baseline',0,corpus,None,Journal(self.root/('calls'+str(i)),3),provider,'fixture',1,self.root)
            self.assertFalse(result['correct']);self.assertFalse(result['final']);self.assertTrue(result['cap_reached'])
            self.assertEqual(result['refused'],reason=='refusal');self.assertEqual(result['truncated'],reason=='max_tokens')

    def test_analysis_retains_losers_incomplete_and_safety_failures(self):
        tasks=[self.tasks[0],self.tasks[-1]];rows=[]
        for task in tasks:
            for arm in ('baseline','reuse'):
                for rep in range(3):
                    rows.append({'phase':'B','task_id':task['id'],'arm':arm,'repetition':rep,'usage':{'input_tokens':100 if arm=='baseline' else 150,'output_tokens':10},'correct':not(arm=='reuse' and task['variant']=='stale'),'decision':task['expected_decision']})
        summary=analyze(rows,tasks,input_price=2,output_price=10)
        self.assertLess(summary['overall']['fewer_tokens_percent'],0)
        self.assertEqual(len(summary['overall']['reuse_loses_tasks']),2)
        self.assertFalse(summary['stale_safety_passed']);self.assertFalse(summary['accuracy_noninferiority_passed']);self.assertFalse(summary['claim_eligible'])
        self.assertEqual(summary['user_priced_costs']['B']['output_usd'],.0012)
        self.assertTrue(analyze(rows[:-1],tasks)['incomplete_tasks'])
        for key in ('per_variant','per_expected_decision'):self.assertIn(key,summary)

    def test_paid_guards_clear_ci_for_other_validations(self):
        with patch.dict(os.environ,{'CI':'true'}),patch('urllib.request.urlopen',side_effect=AssertionError('network')):
            with self.assertRaisesRegex(ValueError,'forbidden in CI'):benchmark(self.root,yes=True)
        with patch.dict(os.environ,{},clear=True),redirect_stdout(io.StringIO()),patch('urllib.request.urlopen',side_effect=AssertionError('network')):
            with self.assertRaisesRegex(ValueError,'--yes'):benchmark(self.root)
            with self.assertRaisesRegex(ValueError,'API_KEY'):benchmark(self.root,yes=True)
        self.assertFalse((self.root/'library').exists())

    def test_pilot_end_to_end_resume_no_network_or_real_library(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('network')),patch('usage.log_call',side_effect=AssertionError('usage log')),redirect_stdout(io.StringIO()):
            summary=benchmark(self.root,fake=True,pilot=True,grader_model='fixture-grader')
            self.assertFalse(summary['claim_eligible']);self.assertEqual(summary['overall']['tasks'],5)
            self.assertTrue(summary['overall']['reuse_loses_tasks'])
            calls=len(list((self.root/'calls').glob('*.json')))
            with patch('savings_real.FakeProvider.__call__',side_effect=AssertionError('completed calls reran')):benchmark(self.root,fake=True,pilot=True,grader_model='fixture-grader')
            self.assertEqual(calls,len(list((self.root/'calls').glob('*.json'))))
        self.assertTrue((self.root/'raw-calls.jsonl').is_file())
        self.assertTrue((self.root/'spot-check.csv').is_file())
        self.assertIn('context_read',[name for p in (self.root/'results').glob('B-*.json') for name in json.loads(p.read_text())['tools_used']])
        for path in (self.root/'calls').glob('grader-*.json'):
            body=json.loads(path.read_text())['request']
            self.assertNotIn('Reuse decision:',body['messages'][0]['content'])
            self.assertNotIn('"arm"',body['messages'][0]['content'])

    def test_partial_total_cap_writes_report_and_resumes_completed_calls(self):
        with redirect_stdout(io.StringIO()),self.assertRaisesRegex(RuntimeError,'Hard total'):
            benchmark(self.root,fake=True,pilot=True,total_cap=1)
        self.assertTrue(json.loads((self.root/'summary.json').read_text())['incomplete_run'])
        self.assertEqual(len(list((self.root/'calls').glob('*.json'))),1)
        with redirect_stdout(io.StringIO()),patch('savings_real.FakeProvider.__call__',side_effect=AssertionError('rerun')),self.assertRaisesRegex(RuntimeError,'Hard total'):
            benchmark(self.root,fake=True,pilot=True,total_cap=1)

    def test_interrupted_session_replays_completed_calls_and_saved_tool_outputs(self):
        task=self.tasks[0];corpus=Corpus('v1');self.addCleanup(corpus.close)
        (self.root/'results').mkdir();journal=Journal(self.root/'calls',20)
        provider=FakeProvider(task,'A','original');sent=[]
        def measured(body):sent.append(body);return provider(body)
        original=journal.call
        def crash_after_response(key,body,call):
            response=original(key,body,call)
            if key.endswith('-01'):raise RuntimeError('process interrupted after durable response')
            return response
        with patch.object(journal,'call',side_effect=crash_after_response),self.assertRaisesRegex(RuntimeError,'process interrupted'):
            run_session(task,'A','original',0,corpus,None,journal,measured,'fixture',12,self.root)
        stored=json.loads(next((self.root/'calls').glob('*-00.json')).read_text())['tool_results']
        # The earlier search output is replayed even if local retrieval now differs.
        original_corpus_call=corpus.call
        def changed(name,args):
            if name=='search_docs':self.fail('completed tool result recomputed')
            return original_corpus_call(name,args)
        with patch.object(corpus,'call',side_effect=changed):
            result=run_session(task,'A','original',0,corpus,None,journal,measured,'fixture',12,self.root)
        self.assertTrue(result['correct']);self.assertEqual(len(sent),3)
        self.assertEqual(sent[1]['messages'][-1]['content'],stored)
