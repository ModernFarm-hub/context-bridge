# SPDX-License-Identifier: Apache-2.0
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock,patch
from savings_real import benchmark,DATA,FakeProvider
from savings_real_journal import Journal
from savings_real_transport import Provider,DefinitelyNotSent,maintain_run,LEGACY_RUNNER_SHA256,disclosure,append_report
from savings_real_costs import rates,reservation
from savings_real_analysis import analyze

class TransportAmendmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve()
        self.prices=rates(2,10,.2,2.5)
        self.body={'model':'fixture','cache_control':{'type':'ephemeral'},'max_tokens':2048,'messages':[{'role':'user','content':'question'}]}
        self.response={'content':[{'type':'text','text':'answer'}],'usage':{'input_tokens':10,'output_tokens':2},'stop_reason':'end_turn'}
    def connection(self,connect_error=None,read_error=None,send_error=None):
        conn=Mock();conn.connect.side_effect=connect_error;conn.request.side_effect=send_error
        response=Mock();response.status=200;response.read.side_effect=read_error
        if read_error is None:response.read.return_value=json.dumps(self.response).encode()
        conn.getresponse.return_value=response
        return conn
    def journal(self):return Journal(self.root/'calls',20,10,self.prices)

    def test_read_timeout_unknown_explicit_abandon_resend_and_permanent_cost(self):
        failed=self.connection(read_error=TimeoutError('fixture read timeout'));success=self.connection()
        journal=self.journal();provider=Provider('secret-fixture',read_timeout=300)
        with patch('savings_real_transport.http.client.HTTPSConnection',side_effect=[failed,success]) as connect:
            with self.assertRaises(TimeoutError):journal.call('B-task-baseline-0-00',self.body,provider)
            self.assertEqual(connect.call_count,1);self.assertEqual(failed.request.call_count,1)
            self.assertEqual(journal.status()['unresolved_calls'],1)
            with self.assertRaisesRegex(RuntimeError,'Unresolved'):journal.call('different',self.body,provider)
            event=journal.abandon('B-task-baseline-0-00','tester','read timeout; outcomes not inspected')
            self.assertEqual(event['retry_key'],'B-task-baseline-0-00--attempt-1')
            reserved=reservation(self.body,self.prices)
            self.assertEqual(journal.status()['recorded_usd'],float(reserved))
            self.assertEqual(journal.call('B-task-baseline-0-00',self.body,provider),self.response)
            self.assertEqual(connect.call_count,2)
            self.assertEqual(journal.tool_results('B-task-baseline-0-00',[]),[])
        self.assertEqual(journal.abandon('B-task-baseline-0-00','someone else','do not rewrite'),event)
        self.assertEqual(len(journal.abandonments()),1)
        resumed=self.journal()
        response_cost=Decimal('.00004')
        self.assertEqual(Decimal(str(resumed.status()['recorded_usd'])),reserved+response_cost)
        self.assertEqual(resumed.call('B-task-baseline-0-00',self.body,lambda b:self.fail('completed retry resent')),self.response)
        self.assertEqual(resumed.tool_results('B-task-baseline-0-00'),[])
        # A late original response never refunds or adds a second measured cost.
        path=self.root/'calls/B-task-baseline-0-00.json';record=json.loads(path.read_text());record['response']=self.response;path.write_text(json.dumps(record))
        self.assertEqual(self.journal().status()['recorded_usd'],float(reserved+response_cost))
        with self.assertRaisesRegex(ValueError,'recorded response'):self.journal().abandon('B-task-baseline-0-00','tester','late response exists')
        self.assertNotIn('secret-fixture',json.dumps(journal.records()))

    def test_connect_error_one_auto_retry_but_errors_after_send_never_retry(self):
        first=self.connection(connect_error=ConnectionRefusedError('not sent'));second=self.connection()
        provider=Provider('fixture',read_timeout=345,connect_timeout=12)
        with patch('savings_real_transport.http.client.HTTPSConnection',side_effect=[first,second]) as factory:
            journal=self.journal();journal.call('connect',self.body,provider)
        self.assertEqual(factory.call_count,2);first.request.assert_not_called();second.request.assert_called_once()
        second.sock.settimeout.assert_called_once_with(345)
        self.assertEqual(len(json.loads((self.root/'calls/connect.json').read_text())['transport']['connect_failures']),1)
        uncertain=self.connection(send_error=ConnectionResetError('could have sent bytes'))
        with patch('savings_real_transport.http.client.HTTPSConnection',return_value=uncertain) as factory:
            with self.assertRaises(ConnectionResetError):journal.call('after-send',self.body,Provider('fixture'))
        self.assertEqual(factory.call_count,1);self.assertIn('after-send',journal.unknown)

    def test_two_connect_failures_are_zero_charge_and_not_reset_by_resume(self):
        conns=[self.connection(connect_error=TimeoutError('pre-send')) for _ in range(2)]
        with patch('savings_real_transport.http.client.HTTPSConnection',side_effect=conns) as factory:
            with self.assertRaises(DefinitelyNotSent):self.journal().call('not-sent',self.body,Provider('fixture'))
            self.assertEqual(factory.call_count,2)
        journal=self.journal();self.assertEqual(journal.status()['recorded_usd'],0);self.assertFalse(journal.unknown)
        with self.assertRaises(DefinitelyNotSent):journal.call('not-sent',self.body,lambda b:self.fail('automatic retry reset'))
        with self.assertRaisesRegex(ValueError,'definitely not sent'):journal.abandon('not-sent','tester','cannot charge')

    def test_resolved_rejected_and_single_resend_cannot_be_extended(self):
        journal=self.journal();journal.call('done',self.body,lambda b:self.response)
        with self.assertRaisesRegex(ValueError,'recorded response'):journal.abandon('done','tester','no')
        for key in ('missing','../done'):
            with self.assertRaises(ValueError):journal.abandon(key,'tester','no')
        def timeout(body):raise TimeoutError('possibly sent')
        with self.assertRaises(TimeoutError):journal.call('one',self.body,timeout)
        journal.abandon('one','tester','timeout')
        with self.assertRaisesRegex(ValueError,'identical'):journal.call('one',{**self.body,'max_tokens':1},timeout)
        with self.assertRaises(TimeoutError):journal.call('one',self.body,timeout)
        journal.abandon('one--attempt-1','tester','retry also timed out')
        with self.assertRaisesRegex(RuntimeError,'exhausted'):journal.call('one',self.body,lambda b:self.fail('third send'))
        self.assertEqual(len(journal.abandonments()),2)
        self.assertAlmostEqual(journal.status()['abandoned_reserved_usd'],2*float(reservation(self.body,self.prices)))

    def test_budget_carries_abandonment_before_new_request(self):
        amount=reservation(self.body,self.prices);journal=Journal(self.root/'calls',20,float(amount),self.prices)
        def timeout(body):raise TimeoutError()
        with self.assertRaises(TimeoutError):journal.call('budget',self.body,timeout)
        journal.abandon('budget','tester','timeout')
        with self.assertRaisesRegex(RuntimeError,'dollar cap'):journal.call('budget',self.body,lambda b:self.fail('budget bypass'))
        self.assertFalse((self.root/'calls/budget--attempt-1.json').exists())

    def test_legacy_metadata_adoption_and_deterministic_resume_only_fake(self):
        def failing_factory(task,phase,arm):
            def fail(body):raise TimeoutError('possibly sent')
            return fail
        kwargs=dict(fake=True,pilot=True,input_price=2,output_price=10,cache_read_price=.2,cache_write_price=2.5,max_usd=5)
        with redirect_stdout(io.StringIO()),self.assertRaises(TimeoutError):benchmark(self.root,provider_factory=failing_factory,**kwargs)
        runfile=self.root/'run.json';run=json.loads(runfile.read_text());run['runner_sha256']=LEGACY_RUNNER_SHA256
        runfile.write_text(json.dumps(run,indent=2)+'\n');original=runfile.read_bytes();(self.root/'infrastructure.json').unlink()
        key='A-research-01-original-0-00'
        with patch('savings_real_transport.Provider',side_effect=AssertionError('offline action constructed provider')):
            maintained=maintain_run(self.root,[key],'independent tester','read timeout; no outcomes inspected',read_timeout=310,data=DATA)
        self.assertTrue(maintained['no_requests_sent']);self.assertEqual(runfile.read_bytes(),original)
        with redirect_stdout(io.StringIO()):result=benchmark(self.root,**kwargs)
        self.assertEqual(runfile.read_bytes(),original)
        self.assertEqual(result['overall']['tasks'],5)
        self.assertEqual(len(result['infrastructure']['abandoned_calls']),1)
        self.assertIn(key,(self.root/'savings-real.md').read_text())
        self.assertGreater(result['budget']['abandoned_reserved_usd'],0)
        self.assertAlmostEqual(result['budget']['recorded_usd'],sum(p['total_usd'] for p in result['user_priced_costs'].values()))
        with redirect_stdout(io.StringIO()),patch('savings_real.FakeProvider.__call__',side_effect=AssertionError('completed calls resent')):
            second=benchmark(self.root,**kwargs)
        self.assertEqual(second['budget'],result['budget'])
        with redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,'Frozen infrastructure'):benchmark(self.root,read_timeout=311,**kwargs)
        self.assertEqual(runfile.read_bytes(),original)

    def test_eligibility_delegates_to_complete_original_analysis_and_discloses(self):
        tasks=json.loads((DATA/'tasks.json').read_text());rows=[]
        for t in tasks:
            for arm in ('baseline','reuse'):
                for rep in range(3):rows.append({'phase':'B','task_id':t['id'],'arm':arm,'repetition':rep,'correct':True,'decision':t['expected_decision'],'usage':{'input_tokens':100 if arm=='baseline' else 80,'output_tokens':5}})
        journal=self.journal()
        def timeout(body):raise TimeoutError()
        with self.assertRaises(TimeoutError):journal.call('B-abandon',self.body,timeout)
        journal.abandon('B-abandon','tester','outcome-blind');journal.call('B-abandon',self.body,lambda b:self.response)
        infra={'connect_timeout_seconds':30,'read_timeout_seconds':300}
        result=disclosure(analyze(rows,tasks),journal,infra,journal.records())
        self.assertTrue(result['claim_eligible']);self.assertEqual(len(result['infrastructure']['abandoned_calls']),1)
        incomplete=disclosure(analyze(rows[:-1],tasks),journal,infra,journal.records())
        self.assertFalse(incomplete['claim_eligible'])
        (self.root/'savings-real.md').write_text('Summary\n');append_report(self.root,result)
        text=(self.root/'savings-real.md').read_text()
        self.assertIn('Permanently charged',text);self.assertIn('outcome-blind',text)

    def test_offline_maintenance_never_reads_outcome_files_and_requires_audit(self):
        def factory(task,phase,arm):
            def fail(body):raise TimeoutError()
            return fail
        with redirect_stdout(io.StringIO()),self.assertRaises(TimeoutError):benchmark(self.root,fake=True,pilot=True,provider_factory=factory)
        key='A-research-01-original-0-00'
        original_read=Path.read_text
        def guarded(path,*args,**kwargs):
            if path.name in ('summary.json','results.jsonl') or path.parent.name=='results':raise AssertionError('Outcome file opened during offline maintenance')
            return original_read(path,*args,**kwargs)
        with patch.object(Path,'read_text',guarded),patch('savings_real_transport.Provider',side_effect=AssertionError('No requests')):
            with self.assertRaisesRegex(ValueError,'required'):maintain_run(self.root,[key],None,'why',data=DATA)
            result=maintain_run(self.root,[key],'tester','infrastructure only',data=DATA)
        self.assertTrue(result['no_requests_sent'])
        event=result['abandoned_calls'][0]
        for field in ('who','when','why','reserved_usd','retry_key'):self.assertIn(field,event)

    def test_global_cap_still_counts_abandoned_attempts(self):
        journal=Journal(self.root/'calls',1,10,self.prices)
        def timeout(body):raise TimeoutError()
        with self.assertRaises(TimeoutError):journal.call('last-slot',self.body,timeout)
        journal.abandon('last-slot','tester','timeout')
        with self.assertRaisesRegex(RuntimeError,'Hard total call cap'):journal.call('last-slot',self.body,lambda b:self.fail('cap enlarged'))

    def test_per_session_cap_counts_abandoned_sends_without_increasing_limit(self):
        from savings_real_journal import SessionCapReached
        journal=Journal(self.root/'calls',20,10,self.prices,session_cap=1)
        def timeout(body):raise TimeoutError()
        key='B-research-01-baseline-0-00'
        with self.assertRaises(TimeoutError):journal.call(key,self.body,timeout)
        journal.abandon(key,'tester','timeout')
        with self.assertRaises(SessionCapReached):journal.call(key,self.body,lambda b:self.fail('per-session cap increased'))
        self.assertFalse((self.root/'calls'/(key+'--attempt-1.json')).exists())

    def test_session_exhausted_by_abandonment_records_original_cap_outcome(self):
        from savings_real import Corpus,load_tasks,run_session,prompt,RESEARCH_TOOLS
        task=load_tasks()[0];(self.root/'results').mkdir()
        body={'cache_control':{'type':'ephemeral'},'model':'fixture','max_tokens':2048,'thinking':{'type':'between_tools'},'output_config':{'effort':'low'},'messages':[{'role':'user','content':prompt(task,'A')}],'tools':RESEARCH_TOOLS}
        journal=Journal(self.root/'calls',20,10,self.prices,session_cap=1)
        def timeout(body):raise TimeoutError()
        key='A-research-01-original-0-00'
        with self.assertRaises(TimeoutError):journal.call(key,body,timeout)
        journal.abandon(key,'tester','timeout')
        corpus=Corpus('v1');self.addCleanup(corpus.close)
        result=run_session(task,'A','original',0,corpus,None,journal,lambda b:self.fail('over-cap send'),'fixture',1,self.root)
        self.assertTrue(result['cap_reached']);self.assertFalse(result['correct']);self.assertFalse(result['final'])
