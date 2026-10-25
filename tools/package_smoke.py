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
    return subprocess.run([sys.executable, '-m', 'context_bridge', *args], env=env, cwd=cwd, input=payload, capture_output=True, text=True, check=True).stdout


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
        assert run(['--version'],env,root).strip()==version('context-bridge-local')
        print('Installed package: import, profile creation, MCP negotiation/search/read, redaction and citations passed.')


if __name__=='__main__':
    main()
