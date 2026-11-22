# SPDX-License-Identifier: Apache-2.0
import json
from datetime import datetime,timezone
from pathlib import Path
import subprocess
import sys
import unittest
from reuse_policy import agent_guide,PRESETS,signals,parse_decision,decision_report,HOOK_POLICY
from automation import injection
from savings_benchmark import tasks

class ReusePolicyTests(unittest.TestCase):
    def test_guide_snapshots_cli_and_invariants(self):
        snapshots=json.loads((Path(__file__).parent/'fixtures/reuse-guides.json').read_text())
        for policy in PRESETS:
            guide=agent_guide(policy)
            self.assertEqual(guide,snapshots[policy]);self.assertLessEqual(len(guide.split()),170)
            self.assertIn('High stakes with volatility, or conflicting evidence, always require REDO',guide)
            self.assertIn('Higher stakes favor CHECK/REDO, never cost saving',guide)
            self.assertIn('never present reuse as freshly verified',guide)
            run=subprocess.run([sys.executable,'-c','from prototype.cli import main; main()','agent-guide','--policy',policy],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(run.stdout.strip(),guide.strip())

    def test_signals_dates_uncertainty_and_false_positives(self):
        now=datetime(2026,11,22,tzinfo=timezone.utc)
        r=signals('Latest v2.3 costs $20 in 2026. I think it might change.','2026-11-20T00:00:00Z',now)
        self.assertEqual(r['age_days'],2);self.assertEqual(r['time_sensitive_terms'],['v2.3','$20','2026'])
        self.assertTrue(r['uncertainty']);self.assertFalse(r['conflicts'])
        for body in ('five attempts','45 days','currency parser','version control design'):
            self.assertFalse(signals(body)['time_sensitive'],body)
        # Documented false positives: historical years, electrical current, programming TODO.
        for body in ('Founded in 2020','TODO: format this example'):
            self.assertTrue(signals(body)['time_sensitive'] or signals(body)['uncertainty'])
        self.assertIsNone(signals('stable','broken')['age_days'])
        self.assertEqual(signals('stable','2030-01-01T00:00:00Z',now)['age_days'],0)

    def test_labelled_fixture_has_decision_coverage_and_signal_metrics(self):
        definitions=tasks()
        for choice in ('REUSE','CHECK','REDO'):
            self.assertGreaterEqual(sum(t['expected_decision']==choice for t in definitions),2)
        for t in definitions:
            result=signals(t['title']+': '+t.get('past_answer',t['reference'])+'. '+t['past_note'])
            for field in ('time_sensitive','uncertainty'):self.assertEqual(result[field],t['expected_'+field],t['id'])
        pine=next(t for t in definitions if t['id']=='pine')
        self.assertEqual((pine['stakes'],pine['volatility'],pine['expected_decision']),('high','volatile','REDO'))

    def test_hook_policy_is_inside_budget_and_empty_stays_empty(self):
        hit={'label':'Synthetic','link':'urn:test','record_id':'abc','snippet':'A stable settled finding.'}
        text,used=injection([hit]);self.assertTrue(text.startswith(HOOK_POLICY))
        self.assertIn('REDO high-risk volatile/conflicts',text);self.assertLessEqual(len(text.encode()),400)
        self.assertTrue(used);self.assertEqual(injection([]),('',[]))

    def test_decision_parser_and_class_report(self):
        self.assertEqual(parse_decision('Answer\nReuse decision: CHECK — verify price\nmore'),'CHECK')
        for text in ('REUSE','Reuse decision: MAYBE — unsure','Reuse decision: REDONE','Reuse decision: REUSE — yes\nReuse decision: REDO — no'):
            self.assertIsNone(parse_decision(text))
        rows=[]
        for choice in ('REUSE','CHECK','REDO'):
            base={'id':choice,'expected_decision':choice,'stakes':'high' if choice=='REDO' else 'low','volatility':'volatile' if choice!='REUSE' else 'stable','final_answer_observed':True,'accuracy_reference_substring':choice!='REDO','decision_correct':True}
            rows+=[dict(base,reuse_available=False,measured_total_tokens=1000,user_priced_usd=.1),dict(base,reuse_available=True,measured_total_tokens=200,user_priced_usd=.02)]
        report=decision_report(rows)
        self.assertEqual(report['decision_accuracy'],1)
        self.assertEqual(report['check_path']['tokens'],200)
        self.assertEqual(report['check_path']['baseline_tokens'],1000)
        self.assertEqual(report['high_stakes_or_volatile']['wrong_final_answers'],1)
        self.assertEqual(report['low_stakes_stable']['tokens_avoided'],800)

    def test_live_check_subset_and_cautious_guide_fake_only(self):
        import io,os
        from contextlib import redirect_stdout
        from unittest.mock import patch
        from savings_live import live
        class Fake:
            def __init__(self,data):self.data=data
            def __enter__(self):return io.StringIO(json.dumps(self.data))
            def __exit__(self,*args):pass
        def respond(request,timeout):
            body=json.loads(request.data);reuse='system' in body
            if reuse:self.assertEqual(body['system'],agent_guide('cautious'))
            task=next(t for t in tasks() if t['question']==body['messages'][0]['content'])
            return Fake({'content':[{'type':'text','text':'Reuse decision: CHECK — verify changed facts\n'+task['reference']}],'stop_reason':'end_turn','usage':{'input_tokens':100 if reuse else 1000,'output_tokens':10}})
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'fake-never-sent'},clear=True),patch('urllib.request.urlopen',side_effect=respond),redirect_stdout(io.StringIO()):
            result=live(input_price=2,output_price=10,yes=True,policy='cautious',task_ids=['lantern','orbit'])
        self.assertEqual(result['policy'],'cautious')
        check=result['decision_metrics']['check_path']
        self.assertEqual(check['tasks'],2);self.assertEqual(check['decision_accuracy'],1.0)
        self.assertEqual(check['tokens'],220);self.assertEqual(check['baseline_tokens'],2020)


    def test_expanded_volatility_fixture_and_documented_misses(self):
        from reuse_policy import volatility_fixture_metrics
        cases=json.loads((Path(__file__).parents[1]/'evals/volatility-signals.json').read_text())
        for case in cases:
            detected=signals(case['text'])['time_sensitive']
            self.assertEqual(detected,case['expected'] and not case.get('documented_miss',False),case['id'])
        result=volatility_fixture_metrics()
        self.assertEqual(result['false_positive'],0)
        self.assertEqual(result['false_negative'],2)
        self.assertEqual(set(result['misses']),{'unsupported-slang','unsupported-wording'})
        self.assertEqual(result['precision'],1.0)

    def test_live_cap_completion_no_answer_and_missing_decision_fake_only(self):
        import io,os
        from contextlib import redirect_stdout
        from unittest.mock import patch
        from savings_live import live
        class Fake:
            def __init__(self,data):self.data=data
            def __enter__(self):return io.StringIO(json.dumps(self.data))
            def __exit__(self,*args):pass
        pine=next(t for t in tasks() if t['id']=='pine')
        for scenario in ('complete','cap','missing','last_call'):
            counts={False:0,True:0}
            def respond(request,timeout):
                body=json.loads(request.data);reuse='system' in body;counts[reuse]+=1;n=counts[reuse]
                content=[]
                if scenario=='missing':content=[{'type':'text','text':pine['reference']}];reason='end_turn'
                elif scenario=='cap':
                    content=[{'type':'tool_use','id':str(n),'name':'research','input':{'step':1}}];reason='tool_use'
                elif reuse and n==1:
                    content=[{'type':'tool_use','id':str(n),'name':'context_search','input':{'query':pine['question']}}];reason='tool_use'
                elif reuse and n==2:
                    result=json.loads(body['messages'][-1]['content'][0]['content'])
                    content=[{'type':'tool_use','id':str(n),'name':'context_read','input':{'record_id':result['results'][0]['record_id']}}];reason='tool_use'
                elif scenario=='last_call' and reuse and n==7:
                    content=[{'type':'tool_use','id':str(n),'name':'context_search','input':{'query':pine['question']}}];reason='tool_use'
                elif n<=(6 if reuse else 4):
                    content=[{'type':'tool_use','id':str(n),'name':'research','input':{'step':n-2 if reuse else n}}];reason='tool_use'
                else:content=[{'type':'text','text':pine['reference']}];reason='end_turn'
                if reuse and n==1 and scenario!='missing':content.insert(0,{'type':'text','text':'Reuse decision: REDO — stale volatile policy'})
                return Fake({'content':content,'stop_reason':reason,'usage':{'input_tokens':100,'output_tokens':10}})
            with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'fake-never-sent'},clear=True),patch('urllib.request.urlopen',side_effect=respond),redirect_stdout(io.StringIO()):
                result=live(input_price=2,output_price=10,yes=True,task_ids=['pine'])
            self.assertEqual(result['step_cap_per_arm'],8)
            reuse=result['results'][1];baseline=result['results'][0]
            if scenario in ('complete','last_call'):
                self.assertEqual((baseline['calls'],reuse['calls']),(5,8 if scenario=='last_call' else 7))
                self.assertTrue(result['target_passed']);self.assertFalse(reuse['cap_reached'])
                self.assertEqual(reuse['answer_status'],'correct')
            elif scenario=='cap':
                self.assertEqual((baseline['calls'],reuse['calls']),(8,8))
                for row in result['results']:
                    self.assertTrue(row['cap_reached']);self.assertEqual(row['answer_status'],'no_answer')
                    self.assertIsNone(row['accuracy_reference_substring'])
                risk=result['decision_metrics']['high_stakes_or_volatile']
                self.assertEqual(risk['unanswered'],1);self.assertEqual(risk['wrong_final_answers'],0)
                self.assertEqual(result['decision_metrics']['by_expected_decision']['REDO']['no_answer'],1)
            else:
                self.assertFalse(result['target_passed']);self.assertFalse(reuse['decision_compliant'])
                self.assertIsNone(baseline['decision_compliant'])
                self.assertEqual(reuse['answer_status'],'correct')
                self.assertEqual(result['decision_metrics']['compliance']['non_compliant_missing_or_ambiguous'],1)
                self.assertFalse(reuse['cap_reached'])
