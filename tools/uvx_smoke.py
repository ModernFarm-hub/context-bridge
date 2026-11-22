# SPDX-License-Identifier: Apache-2.0
"""Verify both console names and MCP negotiation through uvx, offline from a wheel."""
import argparse
import json
import email
import shlex
import zipfile
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
        # Exercise the literal README quickstart from the built wheel, offline.
        with zipfile.ZipFile(wheels[0]) as archive:
            metadata_name=next(name for name in archive.namelist() if name.endswith('.dist-info/METADATA'))
            readme=email.message_from_bytes(archive.read(metadata_name)).get_payload()
        quickstart=readme.split('## Try it in 60 seconds',1)[1].split('## Better recall',1)[0]
        home=root/'home';home.mkdir()
        scratch=root/'demo-scratch';scratch.mkdir()
        env.update(HOME=str(home),TMPDIR=str(scratch))
        state=Path(env['CONTEXT_BRIDGE_HOME']);state.mkdir()
        (state/'sentinel').write_text('User library must survive the demo')
        project=home/'.claude/projects/quickstart-app';project.mkdir(parents=True)
        (project/'one.jsonl').write_text(json.dumps({'type':'user','uuid':'one','sessionId':'quickstart','message':{'role':'user','content':'QUICKSTART842 requires approval'}})+'\n')
        lines=[line.strip() for line in quickstart.splitlines() if line.startswith(('uvx --from ','claude mcp add '))]
        assert len(lines)==3,lines
        for line in lines:
            words=shlex.split(line)
            if words[0]=='uvx':
                assert words[:4]==['uvx','--from','context-bridge-local','context-bridge']
                run=subprocess.run([*base,*words[3:]],env=env,cwd=root,capture_output=True,text=True,check=True)
                if words[4:] == ['demo']:
                    assert '10 invented conversations' in run.stdout and 'paraphrased question' in run.stdout
                    assert 'Source: ChatGPT' in run.stdout and 'Source: Claude Code' in run.stdout
                    assert list(state.iterdir())==[state/'sentinel']
                    assert not list(scratch.iterdir()),'Demo left temporary files behind'
                else:
                    assert words[4:]==['import','claude-code']
                    assert 'Preview only' in run.stdout
                    # CI has no interactive terminal: explicitly approve only the synthetic project.
                    subprocess.run([*base,*words[3:],'--select','1','--yes'],env=env,cwd=root,capture_output=True,text=True,check=True)
            else:
                # Claude Code is proprietary and absent in CI. Validate the exact
                # registration argv with a stub; real MCP transport is checked below.
                binary=root/'bin';binary.mkdir(exist_ok=True)
                client=binary/'claude'
                capture=root/'claude-arguments.json'
                client.write_text('#!'+sys.executable+'\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ["CLAUDE_CAPTURE"]).write_text(json.dumps(sys.argv[1:]))\n')
                client.chmod(0o755)
                command_env={**env,'PATH':str(binary)+os.pathsep+env.get('PATH',''),'CLAUDE_CAPTURE':str(capture)}
                subprocess.run(words,env=command_env,cwd=root,capture_output=True,text=True,check=True)
                assert json.loads(capture.read_text())==['mcp','add','--transport','stdio','context-bridge','--','uvx','--from','context-bridge-local','context-bridge','mcp']
        versions=[]
        for name in ['context-bridge','context-bridge-local']:
            run=subprocess.run([*base,name,'--version'],env=env,cwd=root,capture_output=True,text=True,check=True)
            versions.append(run.stdout.strip())
        assert versions[0]==versions[1] and versions[0]
        payload=json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}})+'\n'
        run=subprocess.run([*base,'context-bridge-local','mcp'],env=env,cwd=root,input=payload,capture_output=True,text=True,check=True)
        assert json.loads(run.stdout)['result']['protocolVersion']=='2025-06-18'
        print('uvx offline wheel: README demo/import/registration, both console names and MCP negotiation passed ('+versions[0]+').')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    main(parser.parse_args().directory)
