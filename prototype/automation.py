# SPDX-License-Identifier: Apache-2.0
"""Opt-in local consultation; installation always shows a diff and asks."""
import argparse
from datetime import datetime,timezone
import difflib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

if __package__:from .reuse_policy import agent_guide,HOOK_POLICY
else:from reuse_policy import agent_guide,HOOK_POLICY
AGENT_GUIDE=agent_guide()
MARKER='Context Bridge: checking past conversations'


def hook_settings(directory,profile=None,min_score=1e-5,max_chars=1200,max_tokens=400):
    command=[sys.executable,str(Path(__file__).resolve()),'hook','run','--directory',str(Path(directory).resolve())]
    if profile:command+=['--profile',profile]
    command+=['--min-score',str(min_score),'--max-chars',str(max_chars),'--max-tokens',str(max_tokens)]
    return {'hooks':{'UserPromptSubmit':[{'hooks':[{'type':'command','command':shlex.join(command),'timeout':.25,'statusMessage':MARKER}]}]}}


def is_ours(hook):
    return isinstance(hook,dict) and hook.get('statusMessage')==MARKER


def edit_settings(path,addition,install,confirm=None):
    confirm=confirm or input
    path=Path(path).expanduser()
    old=path.read_text() if path.exists() else '{}\n'
    data=json.loads(old)
    if not isinstance(data,dict):raise ValueError('Settings must contain a JSON object')
    events=data.setdefault('hooks',{});groups=events.get('UserPromptSubmit',[])
    clean=[]
    for group in groups:
        if not isinstance(group,dict) or not isinstance(group.get('hooks'),list):
            clean.append(group);continue
        kept=[hook for hook in group['hooks'] if not is_ours(hook)]
        if kept:clean.append({**group,'hooks':kept})
    if install:clean.extend(addition['hooks']['UserPromptSubmit'])
    if clean:events['UserPromptSubmit']=clean
    else:events.pop('UserPromptSubmit',None)
    if not events:data.pop('hooks',None)
    new=json.dumps(data,indent=2)+'\n'
    if json.loads(old)==data:return {'changed':False}
    print(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=str(path),tofile=str(path)+' (proposed)',n=0)),file=sys.stderr)
    try:answer=confirm('Apply this settings change? [y/N] ').strip().casefold()
    except EOFError:raise ValueError('No confirmation received; settings unchanged. Run in an interactive terminal or use --print.') from None
    if answer not in ('y','yes'):
        return {'changed':False,'declined':True}
    path.parent.mkdir(parents=True,exist_ok=True)
    backup=None
    if path.exists():
        import uuid
        backup=path.with_name(path.name+'.context-bridge-'+uuid.uuid4().hex[:8]+'.bak')
        shutil.copy2(path,backup);backup.chmod(0o600)
    if __package__:from .session_manager import atomic_write
    else:from session_manager import atomic_write
    atomic_write(path,data)
    return {'changed':True,'backup':str(backup) if backup else None}


def injection(results,max_chars=1200,max_tokens=400):
    # UTF-8 bytes form a deliberately conservative token ceiling for ordinary
    # byte-token models, not an exact Anthropic tokenizer measurement.
    text=HOOK_POLICY
    used=[]
    for hit in results[:3]:
        block='- '+hit['label']+' — '+hit['link']+' [record_id='+hit['record_id']+']\n'
        room=min(max_chars-len(text)-len(block),max_tokens-len((text+block).encode()))
        if room<16:continue
        snippet=hit['snippet'][:min(room-1,160)]
        while len((text+block+snippet+'\n').encode())>max_tokens:snippet=snippet[:-1]
        if not snippet:continue
        text+=block+snippet+'\n';used.append(hit)
    return (text,used) if used else ('',[])


def consult(config,prompt,min_score=1e-5,max_chars=1200,max_tokens=400):
    if __package__:from .mcp_server import ContextService
    else:from mcp_server import ContextService
    service=ContextService(config);service.client_name='claude-code-hook';service.minimum_search_score=min_score
    service.retrieval_override={'mode':'lexical'}  # Bounded cold-start hook; normal MCP keeps its configured mode.
    try:
        args={'query':prompt[:800],'limit':3,'format':'compact'}
        data=service.call('context_search',args,log=False)
        text,hits=injection(data['results'],max_chars,max_tokens)
        # Only injected model-facing text is charged to hook accounting, not
        # the intermediate local search JSON that the model never sees.
        service.record_usage('context_search',{**args,'format':'hook-compact'}, {'results':hits},[{'type':'text','text':text}])
        return text
    finally:
        if service.bridge:service.bridge.db.close()


def run_hook(directory,profile=None,min_score=1e-5,max_chars=1200,max_tokens=400):
    # Never create a library or download anything from a prompt hook.
    if __package__:
        from .local_profile import profile_directory
    else:from local_profile import profile_directory
    root=profile_directory(directory,profile)
    config=root/('enrollment.json' if (root/'enrollment.json').exists() else 'profile.json')
    if not config.is_file():return
    try:
        raw=sys.stdin.read(16384)
        payload=json.loads(raw)
        if not isinstance(payload,dict):return
        prompt=payload.get('prompt','')
        if not isinstance(prompt,str) or not prompt.strip():return
        args=[sys.executable,str(Path(__file__).resolve()),'hook','worker','--config',str(config),'--min-score',str(min_score),'--max-chars',str(max_chars),'--max-tokens',str(max_tokens)]
        result=subprocess.run(args,input=json.dumps({'prompt':prompt}),text=True,capture_output=True,timeout=.20)
        if result.returncode==0 and result.stdout:
            value=json.loads(result.stdout)
            context=value.get('hookSpecificOutput',{}).get('additionalContext','')
            if context and len(context)<=max_chars and len(context.encode())<=max_tokens:print(result.stdout.strip())
    except (ValueError,OSError,subprocess.SubprocessError):return


def main():
    if __package__:from .session_manager import DEFAULT_ROOT
    else:from session_manager import DEFAULT_ROOT
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('kind',choices=('hook',))
    parser.add_argument('action',nargs='?',choices=('run','worker'),default=None)
    actions=parser.add_mutually_exclusive_group();actions.add_argument('--print',dest='show',action='store_true');actions.add_argument('--install',action='store_true');actions.add_argument('--uninstall',action='store_true')
    parser.add_argument('--settings',type=Path,default=Path.home()/'.claude/settings.json');parser.add_argument('--directory',type=Path,default=DEFAULT_ROOT);parser.add_argument('--profile');parser.add_argument('--config',type=Path)
    parser.add_argument('--min-score',type=float,default=1e-5);parser.add_argument('--max-chars',type=int,default=1200);parser.add_argument('--max-tokens',type=int,default=400)
    args=parser.parse_args()
    if not 128<=args.max_chars<=2000 or not 128<=args.max_tokens<=600 or args.min_score<0:parser.error('Use bounded budgets: chars 128–2000, tokens 128–600, score >= 0')
    if args.show:print(json.dumps(hook_settings(args.directory,args.profile,args.min_score,args.max_chars,args.max_tokens),indent=2))
    elif args.install or args.uninstall:
        if not sys.stdin.isatty():parser.error('Hook installation/removal requires an interactive terminal for confirmation; settings unchanged. Use --print to inspect the configuration.')
        try:print(json.dumps(edit_settings(args.settings,hook_settings(args.directory,args.profile,args.min_score,args.max_chars,args.max_tokens),args.install)))
        except (ValueError,EOFError) as exc:parser.exit(1,str(exc)+'\n')
    elif args.action=='run':run_hook(args.directory,args.profile,args.min_score,args.max_chars,args.max_tokens)
    elif args.action=='worker':
        try:
            payload=json.loads(sys.stdin.read(16384));text=consult(args.config,payload.get('prompt',''),args.min_score,args.max_chars,args.max_tokens)
            if text:print(json.dumps({'hookSpecificOutput':{'hookEventName':'UserPromptSubmit','additionalContext':text}}))
        except (ValueError,OSError,RuntimeError,ImportError):pass
    else:parser.error('Use --print, --install, --uninstall, or run')


if __name__=='__main__':main()
