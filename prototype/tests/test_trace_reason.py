# SPDX-License-Identifier: Apache-2.0
"""Synthetic reason evidence, query selectors, and aggregate privacy fixtures."""
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
import test_trace as fixture
import test_trace_mcp as mcp_fixture
from trace import trace_commits,continuation
from trace_mcp import context_trace,serialized_size,TRACE_TOOL
from trace_queries import resolve,report,since_arg

class TraceReasonTests(unittest.TestCase):
    setUp=fixture.TraceTests.setUp
    g=fixture.TraceTests.g
    save=fixture.TraceTests.save
    commit=fixture.TraceTests.commit
    user=fixture.TraceTests.user
    call=fixture.TraceTests.call
    output=fixture.TraceTests.output
    source=fixture.TraceTests.source
    edit=fixture.TraceTests.edit
    enable=mcp_fixture.TraceMCPTests.enable
    rpc=mcp_fixture.TraceMCPTests.rpc

    def assistant(self,text):return {'type':'assistant','sessionId':'synthetic','message':{'role':'assistant','content':text}}

    def test_body_redaction_origin_go_ahead_and_decision_priority(self):
        oid=self.commit('Bound the synthetic queue\n\nBecause retries grow without bound, cap queue capacity.\nAPI_KEY=sk-syntheticsecret0001\nContact synthetic@example.invalid at /synthetic/private')
        self.source([self.user('UNRELATED_PRIVATE_BLOCK'),self.assistant('UNRELATED_PRIVATE_RESPONSE'),
            self.user('Bound queue memory because retries must not accumulate.'),self.assistant('LOW_PRIORITY_NOISE '*1000),self.edit(),
            self.assistant('We rejected an unbounded queue because retries accumulate; instead of dropping work, apply backpressure.'),
            self.user('yes to both'),self.call('Bash',{'command':'git commit -q -m "Bound the synthetic queue"'},'commit'),self.output('commit','')])
        self.enable();result=context_trace(self.config,{'commit':oid,'repo':str(self.repo)})
        encoded=json.dumps(result)
        self.assertIn('Because retries grow without bound',result['git']['message']);self.assertTrue(result['git']['author_date'].startswith('2026-01-01'))
        for value in ['UNRELATED_PRIVATE','sk-syntheticsecret0001','synthetic@example.invalid','/synthetic/private','PRIVATE_TITLE']:
            self.assertNotIn(value,encoded)
        self.assertEqual(result['origin'][0]['text'],'Bound queue memory because retries must not accumulate.')
        self.assertEqual(result['go_ahead'][0]['text'],'yes to both')
        self.assertTrue(result['decisions'][0]['reason_or_alternative']);self.assertIn('rejected',result['decisions'][0]['text'])
        self.assertLessEqual(serialized_size(result),6000)
        cli=trace_commits(self.repo,oid,self.config)[0]['matches'][0]['segment']
        self.assertEqual(len(cli['origin_turns']),1);self.assertEqual(len(cli['go_ahead_turns']),1)
        for text in ['commit and push','yes','ok','do it','still going','yes to both','go ahead','approve','continue']:
            self.assertTrue(continuation(text),text)
        self.assertFalse(continuation('Fix TLS validation'))
        self.assertIn('2–5 sentences',TRACE_TOOL['description']);self.assertIn('Alternatives or caveats',TRACE_TOOL['description'])

    def test_fixed_tool_summaries_never_commands_or_outputs(self):
        oid=self.commit()
        patch='*** Begin Patch\n*** Add File: a.py\n+SYNTHETIC_ALPHA = True\n*** Add File: b.py\n+SYNTHETIC_BETA = True\n*** Add File: c.py\n+SYNTHETIC_GAMMA = True\n*** End Patch'
        self.source([self.user(),self.edit(),self.call('apply_patch',patch,'patch'),
            self.call('Bash',{'command':'pytest --fiction RAW_COMMAND_SENTINEL'},'tests'),self.output('tests','278 passed RAW_OUTPUT_SENTINEL'),
            self.call('Bash',{'command':'python -m build --fiction RAW_BUILD_SENTINEL'},'build'),self.output('build','Build successful RAW_BUILD_OUTPUT'),
            self.call('Bash',{'command':'gh run view --log'},'ci'),self.output('ci','failed (2 jobs) RAW_CI_OUTPUT'),
            self.call('Bash',{'command':'git commit -q -m "Implement bounded synthetic queue"'},'commit'),self.output('commit','')])
        self.enable();result=context_trace(self.config,{'commit':oid,'repo':str(self.repo),'max_chars':12000})
        summaries='\n'.join(t['text'] for t in result['tool_summaries'])
        for expected in ['edited 3 files (a.py, b.py, c.py)','ran tests: 278 passed','ran: git commit','ran: build','CI log read: failed (2 jobs)']:
            self.assertIn(expected,summaries)
        for forbidden in ['RAW_COMMAND','RAW_OUTPUT','RAW_BUILD','RAW_CI','Recorded tool','pytest --','python -m build','gh run view','SYNTHETIC_ALPHA =']:
            self.assertNotIn(forbidden,json.dumps(result))
        self.data['trace']['sensitive_terms']=['RAW_COMMAND_SENTINEL'];self.save()
        result=context_trace(self.config,{'commit':oid,'repo':str(self.repo),'max_chars':12000})
        self.assertIn('[turn withheld: sensitive term]',json.dumps(result));self.assertNotIn('RAW_COMMAND',json.dumps(result))

    def test_path_line_latest_outside_and_cli(self):
        first=self.commit();content="QUEUE_POLICY = 'bounded-synthetic'\nQUEUE_CAPACITY = 128\n";second=self.commit('Increase synthetic capacity',content)
        self.source([self.user(),self.edit(),self.call('Bash',{'command':'git commit -m "Implement bounded synthetic queue"'},'first'),self.output('first','[main '+first[:12]+'] Implement bounded synthetic queue'),
            self.edit(content),self.user('do it'),self.call('Bash',{'command':'git commit -m "Increase synthetic capacity"'},'second'),self.output('second','[main '+second[:12]+'] Increase synthetic capacity')]);self.enable()
        for args,expected in [({'path':'feature.py','line':1},first),({'path':'feature.py','line':2},second),({'path':'feature.py'},second)]:
            result=context_trace(self.config,{**args,'repo':str(self.repo)})
            self.assertEqual(result['commit'],expected)
        outside=self.root/'outside.py';outside.write_text('SYNTHETIC_OUTSIDE = True\n');(self.repo/'escape.py').symlink_to(outside)
        for path in [str(outside),'../outside.py','escape.py']:
            with self.assertRaises(ValueError):context_trace(self.config,{'path':path,'repo':str(self.repo)})
        for args in [{'path':'feature.py','line':0},{'line':1},{'path':'feature.py','line':1,'since':'2d'},{'commit':first,'path':'feature.py'}]:
            with self.assertRaises(ValueError):context_trace(self.config,{**args,'repo':str(self.repo)})
        cmd=[sys.executable,'-c','from prototype.cli import main; main()','trace','--path','feature.py','--line','1','--repo',str(self.repo),'--directory',str(self.library),'--json']
        p=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)[0]['commit'],first)

    def test_range_since_cap_path_filter_and_shared_budget(self):
        ids=[];rows=[self.user('Bound synthetic generations because each version needs an explicit limit.')]
        for i in range(15):
            title='Synthetic generation '+str(i);content="SYNTHETIC_GENERATION = 'bounded-%d'\n"%i
            oid=self.commit(title+('\n\n'+('\"\\é'*2000) if i==14 else ''),content);ids.append(oid);rows.extend([self.edit(content),self.call('Bash',{'command':'git commit -q -m "'+title+'"'},str(i)),self.output(str(i),'')])
        self.source(rows);self.enable()
        for args,total in [({'range':ids[0]+'..HEAD'},14),({'since':'2025-01-01'},15),({'since':'2025-01-01','path':'feature.py'},15)]:
            result=context_trace(self.config,{**args,'repo':str(self.repo),'max_chars':12000})
            self.assertEqual([r['commit'] for r in result['commits']],list(reversed(ids))[:10])
            self.assertEqual(result['omitted'],total-10);self.assertLessEqual(serialized_size(result),12000)
            self.assertTrue(all(len(r['origin'])<=300 for r in result['commits']))
            self.assertTrue(all(r['origin'].startswith('Bound synthetic generations') for r in result['commits']))
            tight=context_trace(self.config,{**args,'repo':str(self.repo),'max_chars':2048})
            self.assertLessEqual(serialized_size(tight),2048);self.assertEqual(len(tight['commits'])+tight['omitted'],total)
            self.assertEqual([r['commit'] for r in tight['commits']],list(reversed(ids))[:len(tight['commits'])])
        result=context_trace(self.config,{'since':'2025-01-01','path':'missing.py','repo':str(self.repo)})
        self.assertEqual(result['commits'],[]);self.assertEqual(result['omitted'],0)
        self.assertEqual(since_arg('2d'),'2 days ago')
        self.data['trace']['sensitive_terms']=['Bound synthetic generations'];self.save()
        withheld=context_trace(self.config,{'since':'2025-01-01','repo':str(self.repo),'max_chars':2048})
        self.assertTrue(all(r['origin'] in ('','[turn withheld: sensitive term]') for r in withheld['commits']))
        self.assertLessEqual(serialized_size(withheld),2048)

    def test_counts_report_has_no_identifiers_or_text_and_is_cli_only(self):
        first=self.commit();second=self.commit('Human synthetic change',"HUMAN_SYNTHETIC_CONSTANT = 'handwritten'\n")
        self.source([self.user('PRIVATE_REQUEST_SENTINEL'),self.edit()]);self.enable()
        result=report(self.repo,self.config,since='2025-01-01')
        self.assertEqual(result['commits'],2);self.assertEqual(result['commits_with_evidence'],1);self.assertEqual(result['commits_without_evidence'],1)
        self.assertEqual(result['by_provider'],{'claude-code':1});self.assertEqual(result['percent_changed_lines_in_commits_with_evidence'],40)
        encoded=json.dumps(result)
        for forbidden in [first,second,str(self.root),'PRIVATE_REQUEST','feature.py','session_id','synthetic','title']:
            self.assertNotIn(forbidden,encoded)
        cmd=[sys.executable,'-c','from prototype.cli import main; main()','trace','report','--repo',str(self.repo),'--since','2025-01-01','--directory',str(self.library),'--json']
        p=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout),result)
        listing=self.rpc({'jsonrpc':'2.0','id':1,'method':'tools/list'})[0]['result']['tools']
        self.assertNotIn('trace_report',[t['name'] for t in listing])
        call={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'context_trace','arguments':{'report':True}}}
        self.assertTrue(self.rpc(call)[0]['result']['isError'])

    def test_human_commit_keeps_git_baseline_without_session_text(self):
        oid=self.commit('Human synthetic repair\n\nBecause a bounded default prevents overflow, set the limit.\nAPI_KEY=sk-inventedsecret888')
        self.enable();result=context_trace(self.config,{'commit':oid,'repo':str(self.repo)})
        self.assertEqual(result['status'],'no AI session found');self.assertEqual(result['confidence'],'none')
        self.assertIn('Because a bounded default prevents overflow',result['git']['message'])
        self.assertNotIn('sk-inventedsecret888',json.dumps(result))
        for section in ['origin','go_ahead','decisions','tool_summaries','citations','matches']:self.assertEqual(result[section],[])
        self.assertLessEqual(serialized_size(result),6000)
