# SPDX-License-Identifier: Apache-2.0
"""Optional transport check with the official MCP v1 client (Python 3.10+)."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    with tempfile.TemporaryDirectory(prefix='context-bridge-sdk-') as tmp:
        root=Path(tmp)
        env={**os.environ,'CONTEXT_BRIDGE_HOME':str(root/'state')}
        archive=root/'export.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('conversations.json',json.dumps([{'uuid':'sdk-conversation','name':'SDK smoke','chat_messages':[{'uuid':'sdk-message','sender':'human','text':'SDK842 requires approval.'}]}]))
        subprocess.run([sys.executable,'-m','context_bridge','import','claude',str(archive)],env=env,capture_output=True,text=True,check=True)
        params=StdioServerParameters(command=sys.executable,args=['-m','context_bridge','mcp'],env=env)
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as client:
                await client.initialize()
                tools=await client.list_tools()
                assert {t.name for t in tools.tools}=={'context_search','context_read'}
                search=await client.call_tool('context_search',{'query':'SDK842'})
                assert not search.isError
                hit=json.loads(search.content[0].text)['results'][0]
                read_result=await client.call_tool('context_read',{'record_id':hit['record_id']})
                assert not read_result.isError
                assert 'SDK842' in read_result.content[0].text
                assert str(root) not in read_result.content[0].text
    print('Official MCP v1 client: initialize, list_tools, search and read passed.')


if __name__=='__main__':
    asyncio.run(main())
