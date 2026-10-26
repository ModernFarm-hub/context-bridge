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
        assert run(['--version'],env,root).strip()==version('context-bridge-local')
        print('Installed package: import, profile creation, MCP negotiation/search/read, redaction, citations, list/stats/removal, real console project selectors, account guards and profile isolation passed.')


if __name__=='__main__':
    main()
