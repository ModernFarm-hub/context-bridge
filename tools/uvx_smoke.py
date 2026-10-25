# SPDX-License-Identifier: Apache-2.0
"""Verify both console names and MCP negotiation through uvx, offline from a wheel."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main(directory):
    wheels=list(directory.resolve().glob('*.whl'))
    if len(wheels)!=1:
        raise ValueError('Supply a directory containing exactly one release wheel')
    uvx=shutil.which('uvx') or str(Path(sys.executable).parent/'uvx')
    with tempfile.TemporaryDirectory(prefix='context-bridge-uvx-') as tmp:
        root=Path(tmp)
        env={**os.environ,'UV_CACHE_DIR':str(root/'cache'),'UV_TOOL_DIR':str(root/'tools'),'UV_TOOL_BIN_DIR':str(root/'bin'),'CONTEXT_BRIDGE_HOME':str(root/'library')}
        base=[uvx,'--offline','--python',sys.executable,'--from',str(wheels[0])]
        versions=[]
        for name in ['context-bridge','context-bridge-local']:
            run=subprocess.run([*base,name,'--version'],env=env,cwd=root,capture_output=True,text=True,check=True)
            versions.append(run.stdout.strip())
        assert versions[0]==versions[1] and versions[0]
        payload=json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}})+'\n'
        run=subprocess.run([*base,'context-bridge-local','mcp'],env=env,cwd=root,input=payload,capture_output=True,text=True,check=True)
        assert json.loads(run.stdout)['result']['protocolVersion']=='2025-06-18'
        print('uvx offline wheel: both console names and MCP negotiation passed ('+versions[0]+').')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    main(parser.parse_args().directory)
