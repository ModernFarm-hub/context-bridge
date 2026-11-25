# SPDX-License-Identifier: Apache-2.0
"""Run with the installed artifact's Python, from outside the checkout."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from importlib.metadata import version


def run(args, env, cwd, payload=None):
    return subprocess.run([str(Path(sys.executable).parent/'context-bridge'), *args], env=env, cwd=cwd, input=payload, capture_output=True, text=True, check=True).stdout


def main():
    with tempfile.TemporaryDirectory(prefix='context-bridge-package-') as tmp:
        root=Path(tmp)
        env={**os.environ,'CONTEXT_BRIDGE_HOME':str(root/'state')}
        env.pop('PYTHONPATH',None)
        demo=run(['demo'],env,root)
        assert '10 invented conversations' in demo and 'paraphrased question' in demo
        assert not (root/'state').exists(), 'Demo touched the real library'
        help_text=run(['--help'],env,root)
        assert 'semantic' in help_text and 'live-test' not in help_text and 'evaluate' not in help_text
        # The lightweight runtime wheel carries the harness, not its public corpus.
        missing=subprocess.run([str(Path(sys.executable).parent/'context-bridge'),'savings-real','--fake','--pilot','--output',str(root/'benchmark')],env=env,cwd=root,capture_output=True,text=True)
        assert missing.returncode!=0 and '--corpus-dir' in missing.stderr,missing.stderr
        assert not (root/'benchmark').exists(), 'Missing corpus created benchmark state'
        archive=root/'export.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('conversations.json',json.dumps([{'uuid':'package-smoke','name':'Synthetic package check','chat_messages':[{'uuid':'message-1','sender':'human','text':'PACKAGE842 requires approval. KEY=syntheticSecret842'}]}]))
        result=json.loads(run(['import','claude',str(archive)],env,root))
        assert result['messages_imported']==1
        assert (root/'state/manager/profile.json').exists()
        def call(name,arguments):
            messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':name,'arguments':arguments}}]
            output=run(['mcp'],env,root,''.join(json.dumps(m)+'\n' for m in messages))
            response=json.loads(output.splitlines()[-1])['result']
            assert not response['isError'],response
            assert str(root) not in output
            assert 'syntheticSecret842' not in output
            return json.loads(response['content'][0]['text'])
        hit=call('context_search',{'query':'PACKAGE842'})['results'][0]
        assert hit['link']=='https://claude.ai/chat/package-smoke'
        assert '[REDACTED]' in hit['body']
        record=call('context_read',{'record_id':hit['record_id']})['record']
        assert 'PACKAGE842 requires approval.' in record['body']
        listed=json.loads(run(['list'],env,root))['conversations']
        assert listed[0]['provider']=='claude' and listed[0]['message_count']==1
        assert json.loads(run(['stats'],env,root))['messages']==1
        assert json.loads(run(['remove','--conversation',hit['link']],env,root))['conversations_removed']==1
        assert json.loads(run(['stats'],env,root))['messages']==0
        assert not call('context_search',{'query':'PACKAGE842'})['results']
        assert archive.exists()
        projects=root/'projects'
        project=projects/'-Users-alice-code-app'
        project.mkdir(parents=True)
        original=root/'my-app'
        original.mkdir()
        (project/'code.jsonl').write_text(json.dumps({'type':'user','sessionId':'code','uuid':'code-message','cwd':str(original),'message':{'role':'user','content':'CODE843 preserve primary_key: id'}})+'\n')
        other=projects/'-Users-alice-code-other'
        other.mkdir()
        (other/'other.jsonl').write_text(json.dumps({'type':'user','sessionId':'other','uuid':'other-message','message':{'role':'user','content':'UNAPPROVED844 hidden'}})+'\n')
        for selection in [['--project','-Users-alice-code-app'],['--select','1'],['--path',str(original)]]:
            run(['import','claude-code','--projects-root',str(projects),*selection,'--yes'],env,root)
        code=call('context_search',{'query':'CODE843'})['results'][0]
        assert 'my-app' in code['source_label'] and 'primary_key: id' in code['body']
        assert not call('context_search',{'query':'UNAPPROVED844'})['results']
        def account_export(path,cid,account):
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('conversations.json',json.dumps([{'uuid':cid,'name':cid,'chat_messages':[{'uuid':'m1','sender':'human','text':cid+' finding'}]}]))
                z.writestr('user.json',json.dumps({'id':account}))
        account_export(root/'personal.zip','PERSONAL845','account-one')
        account_export(root/'work.zip','WORK846','account-two')
        run(['import','claude',str(root/'personal.zip'),'--profile','personal'],env,root)
        try:
            run(['import','claude',str(root/'work.zip'),'--profile','personal'],env,root)
        except subprocess.CalledProcessError as exc:
            assert '--confirm-account-switch' in exc.stderr
        else:
            raise AssertionError('Account switch was not blocked')
        run(['import','claude',str(root/'work.zip'),'--profile','work'],env,root)
        assert json.loads(run(['stats','--profile','personal'],env,root))['messages']==1
        assert json.loads(run(['stats','--profile','work'],env,root))['messages']==1
        assert not call('context_search',{'query':'PERSONAL845 WORK846'})['results']
        # Synthetic trace smoke; no real repository or transcript is read.
        trace_env={**env,'GIT_CONFIG_GLOBAL':os.devnull,'GIT_CONFIG_NOSYSTEM':'1','GIT_AUTHOR_NAME':'Synthetic','GIT_AUTHOR_EMAIL':'synthetic@example.invalid','GIT_COMMITTER_NAME':'Synthetic','GIT_COMMITTER_EMAIL':'synthetic@example.invalid'}
        def git_trace(*args):
            return subprocess.run(['git','-c','commit.gpgsign=false','-C',str(original),*args],env=trace_env,text=True,capture_output=True,check=True).stdout.strip()
        git_trace('init','-q')
        (original/'synthetic.py').write_text("TRACE_FIXTURE_STATE = 'enabled'\n")
        git_trace('add','synthetic.py');git_trace('commit','-qm','Synthetic trace smoke')
        with (project/'code.jsonl').open('a') as stream:
            stream.write(json.dumps({'type':'user','sessionId':'code','cwd':str(original),'message':{'role':'user','content':'Build the synthetic trace smoke fixture.'}})+'\n')
            stream.write(json.dumps({'type':'assistant','sessionId':'code','cwd':str(original),'message':{'role':'assistant','content':[{'type':'tool_use','id':'trace-smoke','name':'Bash','input':{'command':"git commit -m 'Synthetic trace smoke'"}}]}})+'\n')
        traced=json.loads(run(['trace','HEAD','--repo',str(original),'--json'],trace_env,root))
        assert traced[0]['matches'] and 'segment_text' not in traced[0]['matches'][0]
        assert 'Build the synthetic' not in json.dumps(traced)
        run(['trace','enable-mcp'],env,root)
        ai_evidence=call('context_trace',{'commit':'HEAD','repo':str(original)})
        assert ai_evidence['matches'] and 'Untrusted evidence' in ai_evidence['notice']
        assert len(json.dumps(ai_evidence))<=6000 and ai_evidence['git']['files_total']==1
        assert ai_evidence['git']['files_omitted']==0
        assert 'Build the synthetic' in json.dumps(ai_evidence)
        run(['trace','disable-mcp'],env,root)
        audited=json.loads(run(['audit','--repo',str(original),'--since','2025-01-01','--json'],trace_env,root))
        assert audited['notice']=='self-run local audit; heuristics; not proof'
        assert audited['summary']['commits']==1
        assert str(root) not in json.dumps(audited) and 'Build the synthetic' not in json.dumps(audited)
        assert run(['--version'],env,root).strip()==version('context-bridge-local')
        print('Installed package: import, profile creation, MCP negotiation/search/read, redaction, citations, list/stats/removal, real console project selectors, account guards and profile isolation passed.')


if __name__=='__main__':
    main()
