# SPDX-License-Identifier: Apache-2.0
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout,redirect_stderr
from unittest.mock import patch
from automation import AGENT_GUIDE,hook_settings,edit_settings,injection,run_hook
from savings_benchmark import offline,corpus,tasks
from savings_live import live
from session_manager import Sessions


class AutomationTests(unittest.TestCase):
    def test_guide_is_short_uses_valid_tools_and_requires_verification(self):
        self.assertLessEqual(len(AGENT_GUIDE.split()),170)
        for text in ('context_search','format="compact"','context_read','cite','Re-verify','untrusted'):
            self.assertIn(text,AGENT_GUIDE)

    def test_print_install_diff_confirm_backup_and_uninstall_preserve_other_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'settings.json'
            original={'env':{'SYNTHETIC_FLAG':'true'},'hooks':{'UserPromptSubmit':[{'hooks':[{'type':'command','command':'echo existing'}]}]}}
            old=json.dumps(original);path.write_text(old)
            settings=hook_settings(root/'library','personal')
            self.assertIn('UserPromptSubmit',settings['hooks'])
            with redirect_stderr(io.StringIO()) as diff:
                result=edit_settings(path,settings,True,confirm=lambda prompt:'n')
            self.assertFalse(result['changed']);self.assertEqual(path.read_text(),old);self.assertIn('(proposed)',diff.getvalue())
            with redirect_stderr(io.StringIO()):result=edit_settings(path,settings,True,confirm=lambda prompt:'yes')
            self.assertEqual(Path(result['backup']).read_text(),old)
            new=json.loads(path.read_text());self.assertEqual(new['env'],original['env'])
            self.assertEqual(len(new['hooks']['UserPromptSubmit']),2)
            self.assertEqual(edit_settings(path,settings,True,confirm=lambda prompt:self.fail('idempotent install must not ask')),{'changed':False})
            with redirect_stderr(io.StringIO()):edit_settings(path,settings,False,confirm=lambda prompt:'yes')
            self.assertEqual(json.loads(path.read_text()),original)

    def test_hook_budgets_are_hard_for_characters_and_conservative_token_bytes(self):
        hits=[{'label':'Synthetic notes','link':'https://chatgpt.com/c/synthetic-'+str(i),'record_id':str(i)*32,'snippet':'秘密'*1000,'more_matches':0} for i in range(6)]
        text,used=injection(hits,max_chars=600,max_tokens=400)
        self.assertTrue(text);self.assertLessEqual(len(used),3);self.assertLessEqual(len(text),600);self.assertLessEqual(len(text.encode()),400)
        self.assertEqual(injection([]),('',[]))

    def test_real_hook_print_run_no_results_and_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manager=corpus(root,tasks()[:2])
            script=str(Path(__file__).parents[1]/'automation.py')
            shown=subprocess.run([sys.executable,script,'hook','--print','--directory',str(manager.root)],text=True,capture_output=True,timeout=10)
            self.assertEqual(shown.returncode,0,shown.stderr)
            self.assertIn('UserPromptSubmit',json.loads(shown.stdout)['hooks'])
            missing=subprocess.run([sys.executable,script,'hook','run','--directory',str(manager.root)],input=json.dumps({'prompt':'UNMATCHED999'}),text=True,capture_output=True,timeout=1)
            self.assertEqual(missing.returncode,0);self.assertEqual(missing.stdout,'')
            # A hybrid profile still uses the bounded lexical hook, without a cold model load.
            config=json.loads(manager.config.read_text());config['retrieval']={'mode':'hybrid','model_directory':'/synthetic/unavailable-model'};manager.config.write_text(json.dumps(config))
            # Call the worker directly: `hook run` deliberately gives it only 200 ms,
            # which a cold CI runner can exceed (then nothing is injected, by design).
            found=subprocess.run([sys.executable,script,'hook','worker','--config',str(manager.config)],input=json.dumps({'prompt':tasks()[0]['question']}),text=True,capture_output=True,timeout=10)
            self.assertEqual(found.returncode,0,found.stderr);self.assertTrue(found.stdout)
            text=json.loads(found.stdout)['hookSpecificOutput']['additionalContext']
            self.assertLessEqual(len(text.encode()),400);self.assertIn('record_id=',text)
            self.assertNotIn(str(root),text)
            with patch.object(sys,'stdin',io.StringIO(json.dumps({'prompt':'test'}))), patch('subprocess.run',side_effect=subprocess.TimeoutExpired('worker',.2)) as call,redirect_stdout(io.StringIO()) as output:
                run_hook(manager.root)
            self.assertEqual(output.getvalue(),'');self.assertLess(call.call_args.kwargs['timeout'],.3)

    def test_real_cli_install_and_uninstall_only_touch_requested_temp_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);settings=root/'settings.json';settings.write_text('{"env":{"KEEP":"yes"}}')
            script=str(Path(__file__).parents[1]/'automation.py')
            for flag in ('--install','--uninstall'):
                # Real pseudo-terminal supplies explicit interactive consent.
                import pty
                master,slave=pty.openpty()
                try:
                    process=subprocess.Popen([sys.executable,script,'hook',flag,'--settings',str(settings),'--directory',str(root/'library')],stdin=slave,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                    os.close(slave);slave=None
                    os.write(master,b'yes\n')
                    stdout,stderr=process.communicate(timeout=10)
                    self.assertEqual(process.returncode,0,stderr);self.assertIn('proposed',stderr);self.assertIn('Apply this settings change?',stdout)
                finally:
                    os.close(master)
                    if slave is not None:os.close(slave)
            self.assertEqual(json.loads(settings.read_text()),{'env':{'KEEP':'yes'}})
            self.assertEqual(len(list(root.glob('*.bak'))),2)

    def test_noninteractive_install_uninstall_and_eof_refuse_without_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);settings=root/'settings.json'
            settings.write_text('{"env":{"KEEP":"synthetic"}}')
            script=str(Path(__file__).parents[1]/'automation.py')
            original=settings.read_bytes()
            for flag in ('--install','--uninstall'):
                for answer in ('','yes\n'):
                    run=subprocess.run([sys.executable,script,'hook',flag,'--settings',str(settings)],input=answer,text=True,capture_output=True,timeout=10)
                    self.assertNotEqual(run.returncode,0)
                    self.assertIn('interactive terminal',run.stderr)
                    self.assertNotIn('Traceback',run.stderr)
                    self.assertEqual(settings.read_bytes(),original)
                    self.assertEqual(list(root.glob('*.bak')),[])
            with redirect_stderr(io.StringIO()), self.assertRaisesRegex(ValueError,'settings unchanged'):
                edit_settings(settings,hook_settings(root/'library'),True,confirm=lambda prompt:(_ for _ in ()).throw(EOFError()))
            self.assertEqual(settings.read_bytes(),original)


class SavingsBenchmarkTests(unittest.TestCase):
    def test_offline_counterfactual_and_negative_examples(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('offline')),patch('socket.create_connection',side_effect=AssertionError('offline')):
            result=offline()
        self.assertTrue(result['target_passed'])
        self.assertEqual(result['tasks'],20)
        self.assertEqual(result['top_1_valid'],1)
        self.assertLess(result['average_compact_search_tokens'],result['average_full_search_tokens'])
        self.assertEqual(set(result['negative_cases']),{'mint','pine','reef'})
        for row in result['results']:
            self.assertLessEqual(row['hook']['conservative_byte_token_ceiling'],400)
            if row['condition'] in ('stale','wrong'):
                self.assertEqual(row['compact']['credit_tokens'],0)
                self.assertLessEqual(row['compact']['estimated_tokens_avoided'],0)
        self.assertEqual(result['compact_estimated_tokens_avoided'],sum(r['compact']['estimated_tokens_avoided'] for r in result['results']))

    def test_live_guards_make_no_network_calls_and_never_run_in_ci(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('No paid call')) as network,patch.dict(os.environ,{'CI':'true'}):
            with self.assertRaisesRegex(ValueError,'forbidden in CI'):live(1,input_price=2,output_price=10,yes=True)
            self.assertEqual(network.call_count,0)
        with patch.dict(os.environ,{},clear=True),patch('urllib.request.urlopen',side_effect=AssertionError('No paid call')) as network,redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(ValueError,'--yes'):live(1,input_price=2,output_price=10,yes=False)
            self.assertIn('Advisory estimate',output.getvalue());self.assertEqual(network.call_count,0)
            with self.assertRaisesRegex(ValueError,'five tasks'):live(6,input_price=2,output_price=10,yes=True)
            with self.assertRaisesRegex(ValueError,'price-per-million'):live(1,input_price=None,output_price=None,yes=True)

    def test_live_harness_can_be_checked_with_fake_provider_usage_only(self):
        # This deterministic unit test never calls a provider or publishes live results.
        class Fake:
            def __init__(self,data):self.data=data
            def __enter__(self):return io.StringIO(json.dumps(self.data))
            def __exit__(self,*args):pass
        n=[0]
        def respond(request,timeout):
            body=json.loads(request.data);self.assertEqual(body['model'],'claude-sonnet-5-5');self.assertEqual(body['max_tokens'],2048)
            n[0]+=1
            content=[{'type':'tool_use','id':'tool','name':'research','input':{'step':1}}] if n[0]%2 else [{'type':'text','text':'Reuse decision: REUSE — stable synthetic finding\nfive attempts'}]
            return Fake({'content':content,'usage':{'input_tokens':100,'output_tokens':10}})
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-never-sent'},clear=True),patch('urllib.request.urlopen',side_effect=respond),redirect_stdout(io.StringIO()):result=live(1,input_price=2,output_price=10,yes=True)
        self.assertEqual(n[0],4)
        self.assertTrue(result['target_passed']);self.assertTrue(all(r['measured_total_tokens']==220 for r in result['results']))

    def test_live_default_mix_depth_guide_prices_and_actual_reuse_fake_only(self):
        from automation import AGENT_GUIDE
        class Fake:
            def __init__(self,data):self.data=data
            def __enter__(self):return io.StringIO(json.dumps(self.data))
            def __exit__(self,*args):pass
        requests=[]
        def respond(request,timeout):
            body=json.loads(request.data);requests.append(body)
            self.assertEqual(body['thinking'],{'type':'between_tools'})
            self.assertEqual(body['output_config'],{'effort':'low'})
            self.assertEqual(body['max_tokens'],2048)
            for key in ('temperature','top_p','top_k','tool_choice'):self.assertNotIn(key,body)
            question=body['messages'][0]['content']
            task=next(t for t in tasks() if t['question']==question)
            history=[block for message in body['messages'] if message['role']=='assistant' for block in message['content'] if block['type']=='tool_use']
            reuse='system' in body
            if reuse:
                self.assertEqual(body['system'],AGENT_GUIDE)
                if not history:name,args='context_search',{'query':question,'format':'compact'}
                elif len(history)==1:
                    result=json.loads(body['messages'][-1]['content'][0]['content'])
                    name,args='context_read',{'record_id':result['results'][0]['record_id']}
                else:name=None
            else:
                name='research' if len(history)<4 else None;args={'step':len(history)+1}
                for message in body['messages'][1:]:
                    if message['role']=='user':
                        text=message['content'][0]['content']
                        self.assertGreater(len(text),12000)
                        if 'step 4 of 4' not in text:self.assertNotIn('Current reference:',text)
            if name:content=[{'type':'tool_use','id':'tool-'+str(len(history)),'name':name,'input':args}]
            else:content=[{'type':'text','text':task['reference']}]
            if reuse and not history:content.insert(0,{'type':'text','text':'Reuse decision: '+task['expected_decision']+' — synthetic test reason'})
            # Signed/thinking blocks must be replayed unchanged on the next turn.
            content=[{'type':'thinking','thinking':'synthetic placeholder','signature':'fake-signature'}]+content
            if history:self.assertEqual(body['messages'][1]['content'][0],{'type':'thinking','thinking':'synthetic placeholder','signature':'fake-signature'})
            return Fake({'content':content,'stop_reason':'tool_use' if name else 'end_turn','usage':{'input_tokens':100,'output_tokens':10,'cache_creation_input_tokens':20,'cache_read_input_tokens':30}})
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-never-sent'},clear=True),patch('urllib.request.urlopen',side_effect=respond),redirect_stdout(io.StringIO()):
            result=live(input_price=2,output_price=10,yes=True)
        self.assertTrue(result['target_passed'])
        self.assertEqual([r['id'] for r in result['positive_results']],[name for name in ('aster','willow','comet') for _ in range(2)])
        self.assertEqual([r['id'] for r in result['negative_results']],[name for name in ('mint','pine') for _ in range(2)])
        self.assertEqual(result['research_steps'],4);self.assertEqual(result['step_cap_per_arm'],8)
        for row in result['results']:
            self.assertEqual(row['called_context_search'],row['reuse_available'])
            self.assertEqual(row['called_context_read'],row['reuse_available'])
            self.assertEqual(row['research_steps_completed'],0 if row['reuse_available'] else 4)
            self.assertAlmostEqual(row['user_priced_usd'],row['calls']*(150*2+10*10)/1e6)
        self.assertEqual(len(requests),40)
        self.assertEqual(result['decision_metrics']['decision_accuracy'],1.0)

    def test_live_refusal_truncation_depth_and_cli_advisory_fake_only(self):
        class Fake:
            def __init__(self,reason):self.reason=reason
            def __enter__(self):return io.StringIO(json.dumps({'content':[{'type':'text','text':'partial'}],'stop_reason':self.reason,'usage':{'output_tokens':2}}))
            def __exit__(self,*args):pass
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-never-sent'},clear=True),patch('urllib.request.urlopen',side_effect=[Fake('refusal'),Fake('max_tokens')]),redirect_stdout(io.StringIO()):
            result=live(1,input_price=2,output_price=10,yes=True,research_steps=3)
        self.assertFalse(result['target_passed']);self.assertEqual(result['step_cap_per_arm'],7)
        self.assertTrue(result['results'][0]['refused']);self.assertTrue(result['results'][1]['truncated'])
        self.assertTrue(all(not r['final_answer_observed'] for r in result['results']))
        with patch.dict(os.environ,{},clear=True),patch('urllib.request.urlopen',side_effect=AssertionError('No paid call')):
            with self.assertRaisesRegex(ValueError,'research-steps'):live(input_price=2,output_price=10,research_steps=11)
        script=str(Path(__file__).resolve().parents[1]/'benchmark.py')
        run=subprocess.run([sys.executable,script,'--savings','--live','--tasks','3','--research-steps','3','--input-price-per-million','2','--output-price-per-million','10'],capture_output=True,text=True,env={key:value for key,value in os.environ.items() if key not in ('CI','ANTHROPIC_API_KEY')})
        self.assertNotEqual(run.returncode,0);self.assertIn('research depth 3',run.stdout)
        self.assertIn('at most 42 API calls',run.stdout);self.assertIn('--yes',run.stderr)
