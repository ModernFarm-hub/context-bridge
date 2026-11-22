# SPDX-License-Identifier: Apache-2.0
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from savings_real import Journal,benchmark,DATA,load_tasks
from savings_real_costs import BudgetExceeded,rates,amount,input_bound,reservation,observations
from savings_real_analysis import analyze

class CostControlsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve()
        self.prices=rates(2,10,.2,2.5)
        self.body={'model':'fixture','cache_control':{'type':'ephemeral'},'max_tokens':2048,'messages':[{'role':'user','content':'hello'}]}
        self.usage={'input_tokens':100,'cache_creation_input_tokens':10,'cache_read_input_tokens':20,'output_tokens':2}
    def response(self,body):return {'content':[{'type':'text','text':'fixture'}],'usage':self.usage,'stop_reason':'end_turn'}

    def test_cache_pricing_and_resume_admission_exact_decimal_boundary(self):
        bound=reservation(self.body,self.prices);journal=Journal(self.root,10,bound,self.prices)
        first=journal.call('first',self.body,self.response)
        self.assertEqual(amount(first['usage'],self.prices),Decimal('.000249'))
        self.assertEqual(journal.status()['recorded_usd'],.000249)
        with self.assertRaises(BudgetExceeded):journal.call('second',self.body,lambda b:self.fail('over-budget call sent'))
        self.assertFalse((self.root/'second.json').exists())
        resumed=Journal(self.root,10,bound,self.prices)
        self.assertEqual(resumed.call('first',self.body,lambda b:self.fail('cached response sent again')),first)
        with self.assertRaises(BudgetExceeded):resumed.call('second',self.body,lambda b:self.fail('resume bypassed budget'))
        self.assertEqual(resumed.status()['recorded_usd'],.000249)
        # A larger context must reserve more; admission never predicts cache hits.
        longer={**self.body,'messages':[{'role':'user','content':'hello'*10000}]}
        self.assertGreater(reservation(longer,self.prices),bound)

    def test_grader_is_costed_at_its_own_four_rates_and_unresolved_blocks(self):
        grader_prices=rates(8,30,.8,10);journal=Journal(self.root,10,100,self.prices,grader_prices)
        journal.call('grader-fixture',self.body,self.response)
        self.assertEqual(journal.status()['recorded_usd'],float(amount(self.usage,grader_prices)))
        def interrupted(body):raise OSError('fixture interrupted')
        with self.assertRaises(OSError):journal.call('pending',self.body,interrupted)
        with self.assertRaisesRegex(RuntimeError,'Unresolved'):journal.call('different',self.body,lambda b:self.fail('unknown charge bypassed'))

    def test_request_ceiling_and_unexpected_usage_fail_closed(self):
        with patch('savings_real_costs.MAX_INPUT_BOUND',1),self.assertRaises(BudgetExceeded):reservation(self.body,self.prices)
        bad={**self.body,'messages':[{'role':'user','content':[{'type':'image','source':{'type':'url','url':'https://example.invalid'}}]}]}
        with self.assertRaises(ValueError):input_bound(bad)
        journal=Journal(self.root,10,1,self.prices)
        def unexpected(body):return {'usage':{'input_tokens':10_000_000,'output_tokens':1},'content':[],'stop_reason':'end_turn'}
        with self.assertRaisesRegex(BudgetExceeded,'exceeded'):journal.call('unexpected',self.body,unexpected)
        self.assertTrue((self.root/'unexpected.json').is_file())
        with self.assertRaises(BudgetExceeded):journal.call('next',self.body,lambda b:self.fail('overspend continued'))

    def test_cap_stops_fake_run_incomplete_and_paid_cap_required(self):
        with redirect_stdout(io.StringIO()),patch('urllib.request.urlopen',side_effect=AssertionError('network')):
            with self.assertRaises(BudgetExceeded):benchmark(self.root,fake=True,pilot=True,max_usd=.00001,input_price=2,output_price=10,cache_read_price=.2,cache_write_price=2.5)
        summary=json.loads((self.root/'summary.json').read_text())
        self.assertTrue(summary['incomplete_run']);self.assertFalse(summary['claim_eligible'])
        self.assertEqual(summary['budget']['stop_reason'],'max_usd');self.assertEqual(len(list((self.root/'calls').glob('*.json'))),0)
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'fake-never-sent'},clear=True),redirect_stdout(io.StringIO()),patch('urllib.request.urlopen',side_effect=AssertionError('network')):
            with self.assertRaisesRegex(ValueError,'--max-usd'):benchmark(self.root,yes=True)
            with self.assertRaisesRegex(ValueError,'input/output'):benchmark(self.root,yes=True,max_usd=1,cache_read_price=.2,cache_write_price=2.5)
            with self.assertRaisesRegex(ValueError,'cache-read'):benchmark(self.root,yes=True,max_usd=1,input_price=2,output_price=10)
        for bad in (0,-1,float('nan'),float('inf')):
            with redirect_stdout(io.StringIO()),self.assertRaises(ValueError):benchmark(self.root,fake=True,max_usd=bad)

    def test_fake_cache_usage_pilot_projection_and_read_meter(self):
        with redirect_stdout(io.StringIO()) as stdout,patch('urllib.request.urlopen',side_effect=AssertionError('network')):
            summary=benchmark(self.root,fake=True,pilot=True,max_usd=100,input_price=2,output_price=10,cache_read_price=.2,cache_write_price=2.5,grader_model='fixture',grader_input_price=8,grader_output_price=30,grader_cache_read_price=.8,grader_cache_write_price=10)
        calls=[json.loads(p.read_text()) for p in (self.root/'calls').glob('*.json')]
        self.assertTrue(all(r['request']['cache_control']=={'type':'ephemeral'} for r in calls))
        for field in ('cache_read_input_tokens','cache_creation_input_tokens'):
            self.assertGreater(sum(r['response']['usage'].get(field,0) for r in calls),0)
            self.assertGreater(summary['usage_observations']['mean_tokens_per_call'][field],0)
        self.assertIn('Pilot measurements',stdout.getvalue())
        self.assertGreater(summary['mean_characters_read_per_session'],0)
        rows=[json.loads(p.read_text()) for p in (self.root/'results').glob('*.json')]
        expected=sum(r['characters_read'] for r in rows)/len(rows)
        self.assertEqual(summary['mean_characters_read_per_session'],expected)
        self.assertEqual(summary['usage_observations']['mean_characters_read_per_session'],expected)
        for r in calls:
            for result in r.get('tool_results',[]):
                value=json.loads(result['content'])
                if isinstance(value,dict) and 'total_length' in value:self.assertLessEqual(value['length'],12000)
        self.assertAlmostEqual(summary['budget']['recorded_usd'],sum(v['total_usd'] for v in summary['user_priced_costs'].values()))
        projected=summary['usage_observations'];self.assertLess(projected['full_run_estimated_usd'],projected['full_run_worst_case_usd'])
        self.assertEqual(set(projected['mean_tokens_per_session']),set(self.usage))

    def test_wheel_missing_corpus_error_explains_source_install(self):
        with self.assertRaisesRegex(ValueError,'--corpus-dir'):load_tasks(self.root)

    def test_unfinished_session_spend_is_reported_and_overrun_stays_blocked_on_resume(self):
        calls=[]
        def factory(task,phase,arm):
            def response(body):
                calls.append(body)
                return {'usage':{'input_tokens':100000,'output_tokens':1},'content':[{'type':'text','text':'fixture'}],'stop_reason':'end_turn'}
            return response
        kwargs=dict(fake=True,pilot=True,max_usd=10,input_price=2,output_price=10,cache_read_price=.2,cache_write_price=2.5,provider_factory=factory)
        with redirect_stdout(io.StringIO()),self.assertRaises(BudgetExceeded):benchmark(self.root,**kwargs)
        summary=json.loads((self.root/'summary.json').read_text())
        self.assertEqual(summary['phase_a']['sessions'],0)
        self.assertAlmostEqual(summary['user_priced_costs']['A']['total_usd'],.20001)
        self.assertAlmostEqual(summary['budget']['recorded_usd'],.20001)
        self.assertEqual(summary['budget']['stop_reason'],'reservation_exceeded')
        with redirect_stdout(io.StringIO()),self.assertRaises(BudgetExceeded):benchmark(self.root,**kwargs)
        self.assertEqual(len(calls),1)

    def test_missing_usage_remains_unknown_across_resume(self):
        journal=Journal(self.root,10,1,self.prices)
        with self.assertRaisesRegex(ValueError,'Incomplete recorded usage'):
            journal.call('missing',self.body,lambda b:{'content':[],'usage':{'input_tokens':1}})
        resumed=Journal(self.root,10,1,self.prices)
        self.assertEqual(resumed.status()['unresolved_calls'],1)
        with self.assertRaisesRegex(RuntimeError,'Unresolved'):resumed.call('next',self.body,lambda b:self.fail('unknown billing continued'))
