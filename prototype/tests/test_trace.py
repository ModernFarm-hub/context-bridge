# SPDX-License-Identifier: Apache-2.0
import hashlib
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
from trace import trace_commits,public_results,reveal,patch_id,commit_data
from trace_actions import commit_subject
from trace_eval import evaluate,metrics

class TraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.repo=self.root/'repo';self.repo.mkdir()
        self.library=self.root/'library';self.library.mkdir();self.config=self.library/'profile.json'
        self.env={**os.environ,'GIT_CONFIG_GLOBAL':os.devnull,'GIT_CONFIG_NOSYSTEM':'1','GIT_AUTHOR_NAME':'Synthetic Author','GIT_AUTHOR_EMAIL':'synthetic@example.invalid','GIT_COMMITTER_NAME':'Synthetic Author','GIT_COMMITTER_EMAIL':'synthetic@example.invalid','GIT_AUTHOR_DATE':'2026-01-01T02:00:00+00:00','GIT_COMMITTER_DATE':'2026-01-01T02:00:00+00:00','FILTER_BRANCH_SQUELCH_WARNING':'1'}
        self.g('init','-q','-b','main');self.data={'approved_transcripts':[],'sources':{},'sessions':{}}
        self.save()
    def g(self,*args):
        p=subprocess.run(['git','-c','commit.gpgsign=false','-C',str(self.repo),*args],env=self.env,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);return p.stdout.strip()
    def save(self):self.config.write_text(json.dumps(self.data))
    def commit(self,message='Implement bounded synthetic queue',content="QUEUE_POLICY = 'bounded-synthetic'\nQUEUE_CAPACITY = 64\n"):
        (self.repo/'feature.py').write_text(content);self.g('add','feature.py');self.g('commit','-qm',message);return self.g('rev-parse','HEAD')
    def user(self,text='Implement a bounded queue because memory must remain bounded.',time='2026-01-01T00:00:00Z'):
        return {'type':'user','sessionId':'synthetic','timestamp':time,'message':{'role':'user','content':text}}
    def call(self,name,args,cid,time='2026-01-01T01:00:00Z'):
        return {'type':'assistant','sessionId':'synthetic','cwd':str(self.repo),'timestamp':time,'message':{'role':'assistant','content':[{'type':'tool_use','id':cid,'name':name,'input':args}]}}
    def output(self,cid,text):
        return {'type':'user','sessionId':'synthetic','timestamp':'2026-01-01T01:00:01Z','message':{'role':'user','content':[{'type':'tool_result','tool_use_id':cid,'content':text}]}}
    def source(self,rows,name='source',provider='claude-code',identity='synthetic'):
        path=self.root/(name+'.jsonl');path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        self.data['approved_transcripts'].append(str(path));self.data['sources'][str(path)]={'provider':provider,'conversation_id':identity,'title':'PRIVATE_TITLE_SENTINEL'};self.save();return path
    def edit(self,content="QUEUE_POLICY = 'bounded-synthetic'\nQUEUE_CAPACITY = 64\n"):
        return self.call('Write',{'file_path':str(self.repo/'feature.py'),'content':content},'edit')
    def trace(self,oid):return trace_commits(self.repo,oid,self.config)
    def test_range_order_property_and_input_immutability(self):
        import copy,random
        from trace import match,commit_data
        from trace_actions import actions
        from trace_sources import sessions
        root=self.commit('Synthetic human root',"ROOT_SYNTHETIC = 'root-only'\n")
        first_text="FIRST_SYNTHETIC_POLICY = 'bounded-alpha'\n"
        first=self.commit('Implement synthetic alpha',first_text)
        second_text="SECOND_SYNTHETIC_POLICY = 'bounded-beta'\n"
        second=self.commit('Implement synthetic beta',second_text)
        amended_text=second_text+"BETA_SYNTHETIC_CAPACITY = 128\n"
        amended=self.commit('Implement synthetic beta',amended_text)
        # Actually amend the previous commit, retaining its subject.
        self.g('reset','--soft','HEAD^');self.g('commit','--amend','--no-edit')
        amended=self.g('rev-parse','HEAD')
        third_text="THIRD_SYNTHETIC_POLICY = 'bounded-gamma'\n"
        third=self.commit('Implement synthetic gamma',third_text)
        human=self.commit('Human synthetic final',"HUMAN_SYNTHETIC_FINAL = 'handwritten-only'\n")
        def confirmed(cid,oid,title):return self.output(cid,'[main '+oid[:12]+'] '+title)
        self.source([self.user(),self.edit(first_text),self.call('Bash',{'command':'git commit -q -m "Implement synthetic alpha"'},'a'),self.output('a',''),
            self.edit(second_text),self.call('Bash',{'command':'git commit -m "Implement synthetic beta"'},'b'),confirmed('b',second,'Implement synthetic beta'),
            self.edit(amended_text),self.call('Bash',{'command':'git commit --amend --no-edit'},'amend'),confirmed('amend',amended,'Implement synthetic beta')])
        self.source([self.user('Implement the synthetic gamma policy.'),self.edit(third_text),self.call('Bash',{'command':'git commit -q -m "Implement synthetic gamma"'},'g'),self.output('g','')],'other')
        ids=[first,second,amended,third,human]
        singles={oid:public_results(self.trace(oid))[0] for oid in ids}
        self.assertEqual(singles[human]['matches'],[])
        ordered=public_results(self.trace(root+'..HEAD'))
        self.assertEqual(ordered,[singles[row['commit']] for row in ordered])
        for seed in range(5):
            shuffled=ids[:];random.Random(seed).shuffle(shuffled)
            with patch('trace.commit_ids',return_value=shuffled):
                result=public_results(self.trace('HEAD'))
            self.assertEqual(result,[singles[oid] for oid in shuffled])
        for session in sessions(self.config):
            parsed=actions(session,self.repo);before=copy.deepcopy(parsed)
            for oid in ids:match(self.repo,commit_data(self.repo,oid),session,parsed)
            self.assertEqual(parsed,before)
        coverage=[];differences=[]
        trace_commits(self.repo,root+'..HEAD',self.config,coverage=coverage,coverage_differences=differences)
        self.assertEqual(differences,[])
        cli=[sys.executable,'-c','from prototype.cli import main; main()','trace',root+'..HEAD',
            '--repo',str(self.repo),'--directory',str(self.library),'--json','--explain-coverage']
        output=subprocess.run(cli,capture_output=True,text=True)
        self.assertEqual(output.returncode,0,output.stderr)
        diagnostic=json.loads(output.stdout)
        self.assertEqual(diagnostic['coverage_differences'],[])
        self.assertEqual(diagnostic['results'],ordered)
        self.assertNotIn('PRIVATE_TITLE',output.stdout)
        self.assertNotIn(str(self.root),output.stdout)
        self.assertNotIn('bounded-alpha',output.stdout)
        # Ensure diagnostics compare results rather than returning a constant [].
        import trace as module
        real_evaluate=module.evaluate_commit;calls={}
        def inconsistent(repo,commit,parsed,max_results):
            result=real_evaluate(repo,commit,parsed,max_results)
            calls[commit['oid']]=calls.get(commit['oid'],0)+1
            if calls[commit['oid']]>1:result['confidence']='injected-test-difference'
            return result
        with patch('trace.evaluate_commit',side_effect=inconsistent):
            trace_commits(self.repo,root+'..HEAD',self.config,coverage=[],coverage_differences=differences)
        self.assertEqual(set(differences),{row['commit'] for row in ordered})

    def test_append_only_snapshot_does_not_drop_later_matches(self):
        from trace import commit_data as original
        first=self.commit();second=self.commit('Implement synthetic followup',"FOLLOWUP_SYNTHETIC_POLICY = 'bounded-delta'\n")
        source=self.source([self.user(),self.edit(),self.call('Bash',{'command':'git commit -m "Implement bounded synthetic queue"'},'one'),self.output('one',''),
            self.edit("FOLLOWUP_SYNTHETIC_POLICY = 'bounded-delta'\n"),self.call('Bash',{'command':'git commit -m "Implement synthetic followup"'},'two'),self.output('two','')])
        expected=public_results(self.trace(first))+public_results(self.trace(second))
        def append_during_evaluation(repo,oid):
            with source.open('a') as stream:stream.write(json.dumps(self.user('Unrelated new synthetic block.'))+'\n')
            return original(repo,oid)
        with patch('trace.commit_data',side_effect=append_during_evaluation),patch('trace.commit_ids',return_value=[first,second]):
            self.assertEqual(public_results(self.trace('HEAD')),expected)
        # Rewriting old bytes or withdrawing approval aborts the entire result.
        def rewrite(repo,oid):
            source.write_text(source.read_text().replace('Implement a bounded queue','Changed synthetic request'))
            return original(repo,oid)
        with patch('trace.commit_data',side_effect=rewrite):
            with self.assertRaisesRegex(ValueError,'changed|Approval'):self.trace(first)
        def revoke(repo,oid):
            self.data['approved_transcripts']=[];self.save();return original(repo,oid)
        with patch('trace.commit_data',side_effect=revoke):
            with self.assertRaisesRegex(ValueError,'changed|Approval'):self.trace(first)

    def test_real_shape_multiline_quiet_chain_and_codex_exec(self):
        from trace_actions import actions
        from trace_sources import sessions
        oid=self.commit()
        message="Implement bounded synthetic queue\n\nInvented body with a quoted value.\n\nCo-Authored-By: Synthetic <synthetic@example.invalid>"
        command='cd '+str(self.repo)+' && git add -A && git commit -q -m '+json.dumps(message).replace('\\n','\n')+' && git push -q example.invalid -m "Wrong later message"'
        self.source([self.user(),self.call('Bash',{'command':command},'quiet'),self.output('quiet','')])
        parsed=actions(sessions(self.config)[0],self.repo)
        commits=[a for a in parsed if a.kind=='commit']
        self.assertEqual(len(commits),1);self.assertEqual(commits[0].subject,'implement bounded synthetic queue')
        found=self.trace(oid)[0]['matches'][0]
        self.assertEqual(found['confidence'],'medium')
        self.assertIn('commit_command',[e['type'] for e in found['evidence']])
        cmd="cat > feature.py <<'EOF'\nQUEUE_POLICY = \"bounded-synthetic\"\nQUEUE_CAPACITY = 64\nEOF\ngit add -A && git commit -q -m \"Implement bounded synthetic queue\n\nSynthetic body\""
        code='text(await tools.exec_command({cmd:'+json.dumps(cmd)+', workdir:"repo"}));'
        rows=[{'type':'session_meta','payload':{'id':'desktop','cwd':str(self.root)}},
            {'type':'response_item','timestamp':'2026-01-01T00:00:00Z','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'Implement the bounded synthetic queue.'}]}},
            {'type':'response_item','timestamp':'2026-01-01T01:00:00Z','payload':{'type':'custom_tool_call','name':'exec','call_id':'exec1','input':code}},
            {'type':'response_item','timestamp':'2026-01-01T01:00:01Z','payload':{'type':'custom_tool_call_output','call_id':'exec1','output':''}}]
        self.source(rows,'desktop','codex','desktop')
        desktop=sessions(self.config)[1];parsed=actions(desktop,self.repo)
        self.assertEqual([a.subject for a in parsed if a.kind=='commit'],['implement bounded synthetic queue'])
        self.assertTrue(any(a.kind=='edit' and a.path=='feature.py' and 'QUEUE_CAPACITY = 64' in a.added for a in parsed))
        coverage=[]
        traced=trace_commits(self.repo,oid+'^!',self.config,coverage=coverage)
        self.assertEqual(traced[0]['commit'],oid)
        self.assertEqual(trace_commits(self.repo,oid+'^-',self.config)[0]['commit'],oid)
        self.assertEqual(coverage[1]['tool_calls'],1);self.assertEqual(coverage[1]['commands'],1)
        self.assertEqual(coverage[1]['commits'],1);self.assertEqual(coverage[1]['edits'],1)
        self.assertNotIn('Synthetic body',json.dumps(coverage));self.assertNotIn(str(self.root),json.dumps(coverage))
        # A wrapper scoped outside the repository must yield no scoped actions.
        rows[2]['payload']['input']=code.replace('workdir:"repo"','workdir:"elsewhere"')
        self.source(rows,'outside','codex','desktop')
        self.assertEqual(actions(sessions(self.config)[2],self.repo),[])

    def test_commit_command_forms_subject_normalization_and_no_shell_execution(self):
        subject='Implement bounded synthetic queue';oid=self.commit(subject)
        forms=["git commit -m 'Implement bounded synthetic queue'", "git commit -am 'Implement bounded synthetic queue'", "git commit -qam 'Implement bounded synthetic queue'", "git commit -m 'Implement bounded synthetic queue' -m 'Explanation body'", "git commit -F - <<'EOF'\nImplement bounded synthetic queue\n\nExplanation\nEOF", 'git commit -m "$(cat <<\'EOF\'\nImplement bounded synthetic queue\n\nExplanation\nEOF\n)"', 'git commit -F message.txt','git commit --amend -m "Implement bounded synthetic queue"']
        for command in forms:
            with self.subTest(command=command):
                self.data['approved_transcripts']=[];self.data['sources']={};self.save()
                rows=[self.user(),self.edit(),self.call('Write',{'file_path':str(self.repo/'message.txt'),'content':subject+'\n\nBody'},'message'),self.call('Bash',{'command':command},'commit'),self.output('commit','[main '+oid[:12]+'] Implement bounded synthetic queue')]
                self.source(rows)
                result=self.trace(oid)[0];self.assertTrue(result['matches']);self.assertEqual(result['confidence'],'high')
                self.assertIn('commit_command',[e['type'] for e in result['matches'][0]['evidence']])
                self.assertFalse((self.repo/'message.txt').exists())
        sentinel=self.root/'must-not-exist'
        parsed,is_commit=commit_subject('git commit -m "$(touch '+str(sentinel)+')"',{},str(self.repo))
        self.assertFalse(sentinel.exists())

    def test_file_overlap_right_session_wins_and_human_commit_abstains(self):
        oid=self.commit()
        self.source([self.user(),self.edit("UNRELATED_POLICY = 'different-synthetic'\nOTHER_CAPACITY = 999\n")],name='wrong')
        rows=[{'type':'session_meta','timestamp':'2026-01-01T00:00:00Z','payload':{'id':'codex-synthetic','cwd':str(self.repo)}},
              {'type':'response_item','timestamp':'2026-01-01T00:00:01Z','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'Implement a bounded synthetic queue for a memory limit.'}]}},
              {'type':'response_item','timestamp':'2026-01-01T01:00:00Z','payload':{'type':'custom_tool_call','call_id':'patch','name':'apply_patch','input':"*** Begin Patch\n*** Add File: feature.py\n+QUEUE_POLICY = 'bounded-synthetic'\n+QUEUE_CAPACITY = 64\n*** End Patch"}}]
        self.source(rows,name='right',provider='codex',identity='codex-synthetic')
        result=self.trace(oid)[0];self.assertEqual(result['matches'][0]['provider'],'codex')
        self.assertEqual(len(result['matches']),1)
        human=self.commit('Human-only unrelated edit',"HUMAN_ONLY_CONSTANT = 'handwritten-synthetic'\n")
        result=self.trace(human)[0];self.assertEqual(result['confidence'],'none');self.assertEqual(result['status'],'no AI session found')

    def test_rewritten_hashes_amend_rebase_filter_branch_use_patch_identity(self):
        oid=self.commit();self.source([self.user(),self.edit(),self.call('Bash',{'command':"git commit -m 'Implement bounded synthetic queue'"},'commit'),self.output('commit','[main '+oid[:12]+'] Implement bounded synthetic queue')])
        self.g('commit','--amend','--no-edit','--author','Synthetic Alternate <alternate@example.invalid>');amended=self.g('rev-parse','HEAD')
        self.assertNotEqual(amended,oid)
        evidence=self.trace(amended)[0]['matches'][0]['evidence']
        self.assertTrue(any(e['type']=='patch_identity' and e['rewritten_hash'] for e in evidence))
        self.g('filter-branch','-f','--env-filter','GIT_AUTHOR_EMAIL=rewritten@example.invalid; export GIT_AUTHOR_EMAIL','HEAD')
        filtered=self.g('rev-parse','HEAD');self.assertNotEqual(filtered,amended)
        self.assertIn('patch_identity',[e['type'] for e in self.trace(filtered)[0]['matches'][0]['evidence']])
        # Rebase a feature onto a different parent while preserving its patch.
        self.g('checkout','--orphan','newbase');self.g('rm','-rf','.')
        (self.repo/'base.txt').write_text('Synthetic new base\n');self.g('add','base.txt');self.g('commit','-qm','Create synthetic base')
        base=self.g('rev-parse','HEAD');self.g('checkout','main');self.g('rebase','--onto',base,'--root')
        rebased=self.g('rev-parse','HEAD');self.assertNotEqual(rebased,filtered)
        self.assertIn('patch_identity',[e['type'] for e in self.trace(rebased)[0]['matches'][0]['evidence']])

    def test_origin_spans_earlier_commit_and_amend_without_reset(self):
        first=self.commit();second_content="QUEUE_POLICY = 'bounded-synthetic'\nQUEUE_CAPACITY = 128\n"
        (self.repo/'feature.py').write_text(second_content);self.g('add','feature.py');self.g('commit','--amend','--no-edit');second=self.g('rev-parse','HEAD')
        self.source([self.user(),self.edit(),self.call('Bash',{'command':"git commit -m 'Implement bounded synthetic queue'"},'first'),self.output('first','[main '+first[:12]+'] Implement bounded synthetic queue'),self.call('Edit',{'file_path':str(self.repo/'feature.py'),'old_string':'QUEUE_CAPACITY = 64','new_string':'QUEUE_CAPACITY = 128'},'fix'),self.call('Bash',{'command':'git commit --amend --no-edit'},'second'),self.output('second','[main '+second[:12]+'] Implement bounded synthetic queue')])
        segment=self.trace(second)[0]['matches'][0]['segment']
        self.assertEqual(segment['request_turns'][0]['turn'],1)
        self.assertIn(2,[t['turn'] for t in segment['edit_turns']]);self.assertIn(5,[t['turn'] for t in segment['edit_turns']])

    def test_mixed_purpose_default_references_only_and_reveal_scoped_redacted(self):
        oid=self.commit()
        rows=[self.user('Implement queue for synthetic memory bound. KEY=syntheticSecret842'),self.edit(),self.call('Bash',{'command':'python -m unittest'},'tests'),self.output('tests','FAILED synthetic test run'),self.call('Bash',{'command':'gh run view 123 --log'},'ci'),self.output('ci','Synthetic CI failure log'),self.user('PRIVATE_TOPIC_SENTINEL: plan an unrelated fictional surprise party.'),{'type':'assistant','sessionId':'synthetic','message':{'role':'assistant','content':'PRIVATE_ANSWER_SENTINEL'}},self.user('commit it'),self.call('Bash',{'command':"git commit -m 'Implement bounded synthetic queue'"},'commit'),self.output('commit','[main '+oid[:12]+'] Implement bounded synthetic queue'),self.user('LATER_TOPIC_SENTINEL unrelated request')]
        self.source(rows);result=self.trace(oid)
        text=json.dumps(public_results(result))
        for secret in ('PRIVATE_TOPIC','PRIVATE_ANSWER','LATER_TOPIC','PRIVATE_TITLE','syntheticSecret842','Implement queue','feature.py'):
            self.assertNotIn(secret,text)
        segment=result[0]['matches'][0]['segment']
        self.assertNotIn(7,segment['turns']);self.assertNotIn(8,segment['turns']);self.assertNotIn(12,segment['turns'])
        self.assertIn('test_failure',[e['type'] for e in segment['tool_evidence']]);self.assertIn('ci_log',[e['type'] for e in segment['tool_evidence']])
        with redirect_stderr(io.StringIO()) as warning:reveal(result,self.config,['memory'],confirm=lambda prompt:'yes')
        self.assertIn('Warning',warning.getvalue())
        shown=json.dumps(public_results(result));self.assertIn('[REDACTED]',shown)
        for secret in ('PRIVATE_TOPIC','PRIVATE_ANSWER','LATER_TOPIC','syntheticSecret842','PRIVATE_TITLE'):self.assertNotIn(secret,shown)
        with self.assertRaises(ValueError):reveal(result,self.config,[],interactive=False)

    def test_approvals_exclusions_deletions_web_exports_and_revocation(self):
        oid=self.commit();rows=[self.user(),self.edit(),self.call('Bash',{'command':"git commit -m 'Implement bounded synthetic queue'"},'c')]
        path=self.source(rows)
        self.data['excluded_transcripts']=[str(path)];self.save()
        with patch.object(Path,'read_bytes',side_effect=AssertionError('Excluded source opened')):self.assertFalse(self.trace(oid)[0]['matches'])
        self.data['excluded_transcripts']=[];self.data['sources'][str(path)]['provider']='claude';self.save();self.assertFalse(self.trace(oid)[0]['matches'])
        self.data['sources'][str(path)]['provider']='claude-code';self.data['sessions']={'synthetic':{'approved':False,'transcript':str(path)}};self.save();self.assertFalse(self.trace(oid)[0]['matches'])
        self.data['sessions']={};self.data['excluded_conversations']=['claude-code:synthetic'];self.save();self.assertFalse(self.trace(oid)[0]['matches'])
        self.data['excluded_conversations']=[];self.save();result=self.trace(oid)
        def revoke(prompt):self.data['approved_transcripts']=[];self.save();return 'yes'
        with self.assertRaisesRegex(ValueError,'Approval'):reveal(result,self.config,[],confirm=revoke)
        self.assertNotIn('segment_text',result[0]['matches'][0])
        self.data['approved_transcripts']=[str(path)];self.save();path.unlink();self.assertFalse(self.trace(oid)[0]['matches'])

    def test_wrong_repository_future_edits_no_time_only_link_and_read_only(self):
        oid=self.commit();other=self.root/'other';other.mkdir()
        rows=[self.user(),self.edit(),self.call('Bash',{'command':"git -C '"+str(other)+"' commit -m 'Implement bounded synthetic queue'"},'wrong')]
        rows[1]['timestamp']='2026-01-02T00:00:00Z';self.source(rows)
        self.assertFalse(self.trace(oid)[0]['matches'])
        self.data['approved_transcripts']=[];self.data['sources']={};self.save();self.source([self.user(),self.edit()])
        def snapshot():return {str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        before=snapshot();self.trace(oid);self.assertEqual(before,snapshot())

    def test_range_and_real_cli_noninteractive_text_refusal(self):
        first=self.commit();second=self.commit('Human distinct later change',"DISTINCT_HUMAN_FEATURE = 'synthetic-only'\n")
        self.source([self.user(),self.edit()])
        result=trace_commits(self.repo,first+'..'+second,self.config);self.assertEqual([r['commit'] for r in result],[second])
        cmd=[sys.executable,'-c','from prototype.cli import main; main()','trace',first,'--repo',str(self.repo),'--directory',str(self.library),'--json']
        run=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(json.loads(run.stdout)[0]['commit'],first);self.assertNotIn('PRIVATE_TITLE',run.stdout)
        refused=subprocess.run(cmd+['--show-text'],input='',capture_output=True,text=True)
        self.assertNotEqual(refused.returncode,0);self.assertIn('interactive',refused.stderr)

    def test_eval_label_metrics_baseline_and_local_storage(self):
        oid=self.commit();self.source([self.user(),self.edit()])
        answers=iter(['yes','yes','yes','2','no','1'])
        labels=self.library/'reviews.jsonl'
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):result=evaluate(self.repo,self.config,1,42,labels,input_fn=lambda prompt:next(answers))
        m=result['metrics'];self.assertEqual(m['coverage'],1);self.assertEqual(m['session_precision'],1);self.assertEqual(m['why_score_distribution']['2'],1)
        self.assertEqual(m['baseline']['mean_trace_minus_baseline_why'],1);self.assertEqual(m['privacy_incidents'],0)
        stored=labels.read_text();self.assertNotIn('PRIVATE_TITLE',stored);self.assertNotIn('bounded',stored);self.assertNotIn(str(self.repo),stored)
        with self.assertRaises(ValueError):evaluate(self.repo,self.config,interactive=False)
        with self.assertRaises(ValueError):evaluate(self.repo,self.config,review_file=self.repo/'labels.jsonl')
        sample=[{'linked':False,'right_session':None,'why':0,'baseline_why':2,'private_material':'yes','segment_shown':False,'baseline_shown':True}]
        report=metrics(sample);self.assertEqual(report['coverage'],0);self.assertIsNone(report['session_precision']);self.assertEqual(report['privacy_incidents'],1)

    def test_multiedit_shell_writes_and_embedded_codex_exec_actions(self):
        oid=self.commit()
        rows=[self.user(),self.call('MultiEdit',{'file_path':str(self.repo/'feature.py'),'edits':[{'old_string':'','new_string':"QUEUE_POLICY = 'bounded-synthetic'"},{'old_string':'','new_string':'QUEUE_CAPACITY = 64'}]},'multi')]
        self.source(rows);self.assertTrue(self.trace(oid)[0]['matches'])
        self.data['approved_transcripts']=[];self.data['sources']={};self.save()
        self.source([self.user(),self.call('Bash',{'command':"cat > feature.py <<'EOF'\nQUEUE_POLICY = 'bounded-synthetic'\nQUEUE_CAPACITY = 64\nEOF\ngit add feature.py && git commit -qam 'Implement bounded synthetic queue'"},'shell')])
        result=self.trace(oid)[0];self.assertTrue(result['matches'])
        self.data['approved_transcripts']=[];self.data['sources']={};self.save()
        code='text(await tools.exec_command('+json.dumps({'cmd':"git add feature.py && git commit -m 'Implement bounded synthetic queue'",'workdir':str(self.repo)})+'))'
        rows=[{'type':'session_meta','payload':{'id':'embedded','cwd':str(self.root)}}, {'type':'response_item','timestamp':'2026-01-01T00:00:00Z','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'Create a synthetic bounded queue.'}]}}, {'type':'response_item','timestamp':'2026-01-01T01:00:00Z','payload':{'type':'function_call','name':'functions.exec','call_id':'exec','arguments':json.dumps({'code':code})}}]
        self.source(rows,provider='codex',identity='embedded')
        self.assertIn('commit_command',[e['type'] for e in self.trace(oid)[0]['matches'][0]['evidence']])

    def test_recorded_patch_identity_without_old_object_and_no_file_text_by_default(self):
        oid=self.commit('Changed synthetic subject after history rewrite');diff=commit_data(self.repo,oid)['diff']
        self.source([self.user(),self.call('Bash',{'command':'git diff --cached'},'diff'),self.output('diff',diff),self.call('Bash',{'command':"git commit -m 'Old synthetic subject'"},'commit'),self.output('commit','[main deadbeef1234] Old synthetic subject')])
        result=self.trace(oid)[0]
        self.assertIn('recorded_patch_identity',[e['type'] for e in result['matches'][0]['evidence']])
        self.assertNotIn('QUEUE_POLICY',json.dumps(public_results([result])))

    def test_file_only_segment_includes_following_test_failure_before_commit(self):
        oid=self.commit()
        self.source([self.user(),self.edit(),self.call('Bash',{'command':'python -m unittest'},'tests'),self.output('tests','FAILED synthetic assertion')])
        m=self.trace(oid)[0]['matches'][0]
        self.assertEqual(m['segment']['request_turns'][0]['turn'],1)
        self.assertIn('test_failure',[e['type'] for e in m['segment']['tool_evidence']])

    def test_command_tie_uses_content_and_malicious_timestamp_does_not_leak(self):
        oid=self.commit();command=self.call('Bash',{'command':"git commit -m 'Implement bounded synthetic queue'"},'commit')
        command['timestamp']='PRIVATE_TIMESTAMP_SENTINEL'
        self.source([self.user(),self.edit("OTHER_FEATURE_STATE = 'unrelated'\n"),command],name='wrong-command')
        self.source([self.user(),self.edit(),command],name='right-command',identity='right-identity')
        # Update fixture session IDs to match the metadata for the second file.
        path=self.root/'right-command.jsonl';raw=[json.loads(x) for x in path.read_text().splitlines()]
        for row in raw:row['sessionId']='right-identity'
        path.write_text(''.join(json.dumps(r)+'\n' for r in raw))
        result=self.trace(oid)[0]
        self.assertEqual(result['matches'][0]['session_id'],hashlib.sha256(b'claude-code:right-identity').hexdigest()[:12])
        self.assertNotIn('PRIVATE_TIMESTAMP_SENTINEL',json.dumps(public_results([result])))

    def test_codex_patch_update_and_delete_with_captured_old_content(self):
        self.commit();new="QUEUE_POLICY = 'bounded-synthetic'\nQUEUE_CAPACITY = 128\n"
        oid=self.commit('Increase synthetic capacity',new)
        def codex_rows(patch,read=False):
            rows=[{'type':'session_meta','payload':{'id':'patch-synthetic','cwd':str(self.repo)}},{'type':'response_item','timestamp':'2026-01-01T00:00:00Z','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'Adjust synthetic capacity for the demo.'}]}}]
            if read:
                rows.extend([{'type':'response_item','timestamp':'2026-01-01T00:30:00Z','payload':{'type':'function_call','name':'exec_command','call_id':'read','arguments':json.dumps({'cmd':'cat feature.py'})}},{'type':'response_item','timestamp':'2026-01-01T00:30:01Z','payload':{'type':'function_call_output','call_id':'read','output':new}}])
            rows.append({'type':'response_item','timestamp':'2026-01-01T01:00:00Z','payload':{'type':'custom_tool_call','name':'apply_patch','call_id':'patch','input':patch}})
            return rows
        self.source(codex_rows('*** Begin Patch\n*** Update File: feature.py\n@@\n-QUEUE_CAPACITY = 64\n+QUEUE_CAPACITY = 128\n*** End Patch'),provider='codex',identity='patch-synthetic')
        self.assertTrue(self.trace(oid)[0]['matches'])
        self.g('rm','feature.py');self.g('commit','-qm','Remove synthetic queue');deleted=self.g('rev-parse','HEAD')
        self.data['approved_transcripts']=[];self.data['sources']={};self.save()
        self.source(codex_rows('*** Begin Patch\n*** Delete File: feature.py\n*** End Patch',read=True),name='delete',provider='codex',identity='patch-synthetic')
        self.assertIn('removed_line_overlap',[e['type'] for e in self.trace(deleted)[0]['matches'][0]['evidence']])

    def test_unknown_provider_export_is_not_opened_and_absolute_git_c_can_scope(self):
        oid=self.commit()
        row=self.call('Bash',{'command':"git -C '"+str(self.repo)+"' commit -m 'Implement bounded synthetic queue'"},'commit');row.pop('cwd')
        path=self.source([self.user(),row])
        self.assertTrue(self.trace(oid)[0]['matches'])
        self.data['sources'][str(path)].pop('provider');self.save()
        with patch.object(Path,'read_bytes',side_effect=AssertionError('Unclassified source opened')):self.assertFalse(self.trace(oid)[0]['matches'])

    def test_eval_json_cli_keeps_prompts_on_stderr_and_labels_local(self):
        import pty
        oid=self.commit();self.source([self.user(),self.edit()])
        master,slave=pty.openpty()
        try:
            cmd=[sys.executable,'-c','from prototype.cli import main; main()','trace-eval','--repo',str(self.repo),'--directory',str(self.library),'--sample','1','--json']
            process=subprocess.Popen(cmd,stdin=slave,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            os.close(slave);slave=None
            os.write(master,b'n\nn\nyes\n1\nno\n0\n')
            output,error=process.communicate(timeout=15)
            self.assertEqual(process.returncode,0,error)
            result=json.loads(output);self.assertEqual(result['metrics']['session_precision'],1)
            self.assertNotIn('PRIVATE_TITLE',output+error);self.assertNotIn('QUEUE_POLICY',output+error)
            self.assertEqual(result['metrics']['baseline_shown'],0)
        finally:
            os.close(master)
            if slave is not None:os.close(slave)

    def test_partial_clone_is_refused_without_lazy_fetch_or_profile_reads(self):
        oid=self.commit();self.g('config','remote.synthetic.promisor','true')
        before={str(p.relative_to(self.repo)):p.read_bytes() for p in self.repo.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError,'Partial/promisor'):self.trace(oid)
        after={str(p.relative_to(self.repo)):p.read_bytes() for p in self.repo.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_patch_identity_keeps_origin_when_committer_dates_are_rewritten(self):
        old=self.commit()
        self.source([self.user(),self.edit(),self.call('Bash',{'command':"git commit -m 'Implement bounded synthetic queue'"},'commit'),self.output('commit','[main '+old[:12]+'] Implement bounded synthetic queue')])
        self.env['GIT_COMMITTER_DATE']='2025-01-01T00:00:00+00:00'
        self.g('commit','--amend','--no-edit');new=self.g('rev-parse','HEAD')
        m=self.trace(new)[0]['matches'][0]
        self.assertIn('patch_identity',[e['type'] for e in m['evidence']])
        self.assertEqual(m['segment']['request_turns'][0]['turn'],1)
        self.assertIn(2,[t['turn'] for t in m['segment']['edit_turns']])
