# SPDX-License-Identifier: Apache-2.0
"""Fixed literal/token rules. Recorded commands and scripts are never executed."""
from pathlib import Path
import os
import shlex
import re
import tempfile
if __package__:
    from .trace_actions import commands,call_cwd,context,shell_parts,executable,git_index,literal_writes
else:
    from trace_actions import commands,call_cwd,context,shell_parts,executable,git_index,literal_writes

SEVERITY={'secrets':'high','remote_code':'high','outside_repo_writes':'high','persistence_config':'medium','destructive':'medium','network':'low','dependencies':'low','possible_injection_chain':'high','scratch_write':'info','scratch_cleanup':'info','log_output':'low'}
DESCRIPTIONS={'log_output':'Recorded log output outside the repository.', 'secrets':'Recorded access to a credential source or credential-like command argument.',
    'remote_code':'Recorded execution of downloaded content.',
    'outside_repo_writes':'Recorded write target outside the repository and configured scratch directories.',
    'persistence_config':'Recorded modification to persistent or agent configuration.',
    'destructive':'Recorded destructive or history-rewriting operation.',
    'network':'Recorded network, push or publish operation.',
    'dependencies':'Recorded dependency installation or dependency-file change.',
    'possible_injection_chain':'Heuristic: instruction-like tool output preceded a notable action within ten turns.',
    'scratch_write':'Recorded write to a configured scratch directory outside the repository.',
    'scratch_cleanup':'Recorded recursive forced cleanup in a configured scratch directory.'}
INJECTION=re.compile(r'ignore (?:all |the )?(?:previous|prior) instructions|you must now run|disregard (?:all |the )?(?:previous|prior) instructions|override (?:your|the) instructions',re.I)
TOKEN=re.compile(r'(?i)\b(?:API_KEY|ACCESS_TOKEN|SECRET_KEY|PASSWORD)\s*=\s*(?!\[REDACTED\])\S+|\b(?:sk-(?:ant-|proj-)?[\w-]{8,}|gh[pousr]_[\w-]{8,}|AKIA[A-Z0-9]{16})\b')

def command_text(command):return command  # Recognition below is token based.

def segments(command):
    try:
        result=[];scopes={():{}}
        for sep,values,scope in shell_parts(command,with_scope=True):
            if scope not in scopes:scopes[scope]=dict(scopes.get(scope[:-1],{}))
            variables=scopes[scope]
            def expand(value):
                return re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)',lambda m:variables.get(m[1] or m[2],m[0]),value)
            assignments=[]
            for value in values:
                m=re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)=(.*)',value)
                if not m:break
                assignments.append((m[1],expand(m[2])))
            if len(assignments)==len(values):
                for key,value in assignments:
                    if value.startswith('/') and '$' not in value and '__CB_SUB_' not in value:variables[key]=value
                    else:variables.pop(key,None)
            v=executable([expand(x) for x in values])
            if v:result.append((sep,v))
        return result
    except ValueError:return []

PLACEHOLDER=re.compile(r'fake|dummy|example|placeholder|test|invalid|xxx|changeme|never-valid',re.I)
SECRET_PATH=re.compile(r'(?i)(?:^|[/\\])(?:\.env(?:\.[^/\\]*)?|\.ssh|\.aws|\.[^/\\]+_key|[^/\\]+\.pem|id_[^/\\]+|\.netrc|\.npmrc|\.pypirc|credentials[^/\\]*)(?:[/\\]|$)')
def credential_severity(value):
    values=[m[0].split('=',1)[-1].strip('"\'') for m in TOKEN.finditer(value)]
    return 'high' if any(len(v)>=16 and not PLACEHOLDER.search(v) for v in values) else 'low'
def clean_target(value):return value.rstrip(')`;}"\'')


def git_args(values):
    i=git_index(values)
    return values[i:] if i is not None else []

def is_test_build(command):
    for _,v in segments(command):
        name=Path(v[0]).name;args=v[1:]
        if name in ('pytest','unittest'):return True
        if re.fullmatch(r'python(?:3(?:\.\d+)?)?',name) and len(args)>=2 and args[0]=='-m' and args[1] in ('pytest','unittest','build'):return True
        if name in ('npm','pnpm','yarn') and (args[:1] in (['test'],['build']) or len(args)>=2 and args[0]=='run' and args[1] in ('test','build')):return True
        if name=='cargo' and args[:1] in (['test'],['build']):return True
        if name=='make' and any(x in ('test','build') for x in args):return True
    return False

def is_dependency(command):
    for _,v in segments(command):
        name=Path(v[0]).name;args=v[1:]
        if name in ('npm','pnpm','yarn') and args and args[0] in ('install','ci','add','update'):return True
        if name in ('pip','pip3') and args[:1]==['install']:return True
        if name in ('python','python3') and args[:3]==['-m','pip','install']:return True
        if name=='uv' and args and args[0] in ('add','sync','lock'):return True
        if name=='cargo' and args and args[0] in ('add','update'):return True
    return False

def is_publish(command):
    for _,v in segments(command):
        g=git_args(v);name=Path(v[0]).name;args=v[1:]
        if g and g[0] in ('push','tag'):return True
        if name in ('npm','pnpm','yarn','cargo') and args[:1]==['publish']:return True
        if name=='twine' and args[:1]==['upload']:return True
        if name=='gh' and args[:2]==['release','create']:return True
    return False

class Recognizer:
    def __init__(self,fn):self.fn=fn
    def search(self,text):return self.fn(text)
TEST_BUILD=Recognizer(is_test_build)
DEPENDENCY=Recognizer(is_dependency)
PUBLISH=Recognizer(is_publish)

def sensitive_area(path):
    return bool(re.search(r'(?i)(?:^|/)(?:\.github/workflows|\.git/hooks|\.claude|\.codex|auth[^/]*|crypto[^/]*|release[^/]*)(?:/|\.|$)|(?:^|/)(?:package\.json|pyproject\.toml|Cargo\.toml|requirements[^/]*\.txt|setup\.py|\.releaserc[^/]*)$',path))
def dependency_path(path):return bool(re.search(r'(?i)(?:^|/)(?:package(?:-lock)?\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|uv\.lock|Cargo\.(?:toml|lock)|requirements[^/]*\.txt|pyproject\.toml)$',path))
def persistent_path(path):return bool(re.search(r'(?i)(?:^|/)(?:\.git/hooks|\.github/workflows|\.claude|\.codex)(?:/|$)|(?:^|/)(?:\.?(?:bashrc|zshrc|profile)|.*release.*|.*permissions.*|.*hooks.*)$',path))

def default_scratch():return list(dict.fromkeys(['/tmp','/private/tmp','/var/folders',tempfile.gettempdir(),*([os.environ['TMPDIR']] if os.environ.get('TMPDIR') else [])]))
def resolved(path,cwd):
    if not isinstance(path,str) or '$' in path:return None
    p=Path(path).expanduser()
    if not p.is_absolute() and not cwd:return None
    return p.resolve() if p.is_absolute() else (Path(cwd)/p).resolve()
def is_scratch(path,repo,scratch):return not path.is_relative_to(repo) and any(path.is_relative_to(Path(p).expanduser().resolve()) for p in scratch)
def agent_class(path):
    for name in ('.claude','.codex'):
        if path.is_relative_to(Path.home()/name):return 'agent_'+name[1:]
    return None

def redirect_paths(v):
    result=[]
    for i,value in enumerate(v[:-1]):
        if value in ('>','>>','>|'):
            dest=clean_target(v[i+1])
            if dest=='&' or dest.startswith('&') or dest.isdigit():continue
            result.append(dest)
    return result

def raw_paths(turn,command):
    args=turn.arguments;tool=turn.tool.lower().rsplit('.',1)[-1];paths=[]
    if isinstance(args,dict) and tool in ('edit','write','multiedit'):
        path=args.get('file_path',args.get('path'))
        if isinstance(path,str):paths.append(path)
    codes=[args] if isinstance(args,str) else [args.get('patch',''),args.get('code','')] if isinstance(args,dict) else []
    for code in codes:
        if isinstance(code,str):
            paths.extend(re.findall(r'^\*\*\* (?:Add|Update|Delete) File: (.+)$',code,re.M))
            # Wrapped patch literals use the same safe literal decoder.
            if __package__:from .trace_actions import literal
            else:from trace_actions import literal
            for m in re.finditer(r'apply_patch\s*\(\s*("(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27)',code):
                patch=literal(m[1])
                if patch:paths.extend(re.findall(r'^\*\*\* (?:Add|Update|Delete) File: (.+)$',patch,re.M))
    for _,v in segments(command):
        name=Path(v[0]).name;values=[x for x in v[1:] if not x.startswith('-') and x not in ('>','>>','<','<<')]
        paths.extend(redirect_paths(v))
        if name in ('cp','mv','install') and values:paths.append(values[-1])
        elif name in ('tee','touch','mkdir','rm'):paths.extend(values)
        if name=='sed' and any(x=='-i' or x.startswith('-i') or x=='--in-place' for x in v[1:]) and values:paths.append(values[-1])
        if name in ('curl','wget'):
            for i,token in enumerate(v[:-1]):
                if token in ('-o','--output','-O'):paths.append(v[i+1])
    paths.extend(w['path'] for w in literal_writes(command))
    return list(dict.fromkeys(p for p in paths if p and p not in ('&1','&2','/dev/null','/dev/stdout','/dev/stderr') and not re.fullmatch(r'/dev/fd/\d+|/proc/(?:self|\d+)/fd/\d+',p)))

def events(session,repo):
    outputs={t.call_id:t for t in session.turns if t.kind=='tool_output' and t.call_id};result=[]
    for t in session.turns:
        if t.kind!='tool_call':continue
        try:
            cwd=call_cwd(t);cmds=commands(t.tool,t.arguments);base=context('',cwd,repo);initiated=context('',t.cwd,repo)
            scoped=[c for c in cmds if context(c,cwd,repo)];direct=raw_paths(t,'')
            direct_scope=any(Path(p).is_absolute() and Path(p).resolve().is_relative_to(repo) for p in direct)
            if not base and not initiated and not scoped and not direct_scope:continue
            command='\n'.join(cmds if base or initiated else scoped);actual=cwd
            for _,v in segments(command):
                if v[0]=='cd' and len(v)==2:
                    target=resolved(v[1],cwd)
                    if target:actual=str(target)
                    break
            paths=[(p,resolved(p,actual)) for p in raw_paths(t,command)];paths=[(p,q) for p,q in paths if q is not None]
            downloads=[]
            for _,v in segments(command):
                if Path(v[0]).name not in ('curl','wget'):continue
                names=redirect_paths(v)+[v[i+1] for i,x in enumerate(v[:-1]) if x in ('-o','--output','-O')]
                downloads.extend(q for q in (resolved(p,actual) for p in names) if q is not None)
            result.append({'turn':t,'cwd':actual,'command':command,'in_repo':bool(context(command,cwd,repo) or direct_scope),'paths':paths,'downloads':downloads,'output':outputs.get(t.call_id)})
        except (ValueError,TypeError,KeyError,AttributeError):continue
    return result

def git_config_write(g):
    if not g or g[0]!='config':return False
    args=g[1:]
    if any(x in ('--get','--get-all','--get-regexp','--get-urlmatch','--get-color','--get-colorbool','--list','-l','get','list') for x in args):return False
    if any(x in ('--unset','--unset-all','--add','--replace-all','set','unset') for x in args):return True
    values=[];i=0
    while i<len(args):
        if args[i] in ('--file','-f','--type','--default'):i+=2;continue
        if not args[i].startswith('-'):values.append(args[i])
        i+=1
    return len(values)>=2

def stdin_interpreter(v):
    if not v:return False
    name=Path(v[0]).name;args=v[1:]
    if name not in ('sh','bash','zsh','python','python3'):return False
    if any(x in ('-c','-m') or x.startswith(('-c','-m')) for x in args):return False
    if name in ('sh','bash','zsh') and '-s' in args:return True
    return not any(not x.startswith('-') for x in args)

def executes_download(event,download):
    for _,v in segments(event['command']):
        name=Path(v[0]).name;args=v[1:]
        target=args[0] if name in ('sh','bash','zsh','python','python3','node') and args and not args[0].startswith('-') else v[0] if v[0].startswith(('./','/')) else None
        if target and resolved(target,event['cwd'])==download:return True
    return False

def modifications(event):
    writes=literal_writes(event['command'])
    if writes:return {str(resolved(w['path'],event['cwd'])) for w in writes if resolved(w['path'],event['cwd']) is not None}
    for _,v in segments(event['command']):
        name=Path(v[0]).name;args=v[1:];g=git_args(v)
        if name in ('python','python3','node') and '<<' in v:continue
        if is_test_build(' '.join(v)):continue
        if name in ('black','gofmt') or name=='ruff' and 'format' in args or name=='prettier' and '--write' in args or name=='cargo' and args[:1]==['fmt']:return None
        if name=='sed' and any(x.startswith('-i') or x=='--in-place' for x in args):return None
        if name in ('python','python3','node','bash','sh','zsh','ruby','perl') and args and not any(x in ('-c','-m','-e') for x in args):return None
        if g and g[0] in ('mv','checkout','restore','merge','cherry-pick','apply'):return None
        if is_dependency(' '.join(v)) or name in ('npm','pnpm','yarn') and args[:1]==['run'] and any(x in ('build','generate','codegen','format') for x in args[1:]):return None
        if re.search(r'(?:generate|codegen)',name):return None
    return set()
MODIFY=Recognizer(lambda c:modifications({'command':c,'cwd':None}) is None)

def rules(event,repo,scratch=None):
    scratch=default_scratch() if scratch is None else scratch;t=event['turn'];parts=segments(event['command']);result=[]
    def add(cat,rule=None,severity=None):
        row={'category':cat,'rule':rule or cat,'severity':severity or SEVERITY[cat]}
        if row not in result:result.append(row)
    try:raw_values=[x for _,v in shell_parts(event['command']) for x in v]
    except ValueError:raw_values=[]
    for x in raw_values:
        if TOKEN.search(x):add('secrets','credential_argument',credential_severity(x))
    access=[]
    args=t.arguments if isinstance(t.arguments,dict) else {}
    if t.tool.lower().rsplit('.',1)[-1] in ('read','read_file'):access.extend(v for k,v in args.items() if k in ('path','file_path') and isinstance(v,str))
    credential_network=False;credential_seen=False
    try:
        for _,raw in shell_parts(event['command']):
            credential_seen|=any(TOKEN.search(x) and credential_severity(x)=='high' for x in raw)
            v=executable(raw)
            if v and Path(v[0]).name in ('curl','wget','ssh','scp') and credential_seen:credential_network=True
    except ValueError:pass
    secret_env=False;presence=False;secret_seen=False
    for i,(sep,v) in enumerate(parts):
        name=Path(v[0]).name
        if name in ('env','printenv'):
            # executable() strips env only when followed by a literal program;
            # raw env|grep presence checks are handled below too.
            nextv=parts[i+1][1] if i+1<len(parts) and parts[i+1][0]=='|' else []
            presence_check=bool(nextv and (Path(nextv[0]).name=='wc' or Path(nextv[0]).name=='grep' and any(x=='-c' or x=='--count' for x in nextv[1:])))
            secret_env|=not presence_check;presence|=presence_check
        if name in ('cat','head','tail','less','more','sed','grep','cp'):access.extend(v[1:])
        if name in ('security','secret-tool') or name=='git' and git_args(v)[:1]==['credential']:secret_env=True
        for x in v:
            if TOKEN.search(x):
                severity=credential_severity(x);add('secrets','credential_argument',severity)
                secret_seen|=severity=='high'
        if name in ('cat','head','tail','less','more','sed','grep','cp') and any(SECRET_PATH.search(x) for x in v[1:]):secret_seen=True
        if name in ('curl','wget','ssh','scp'):add('network',severity='high' if secret_seen or credential_network else 'low')
        if sep=='|' and i and Path(parts[i-1][1][0]).name in ('curl','wget') and stdin_interpreter(v):add('remote_code','download_stdin')
        g=git_args(v)
        if g:
            if g[0] in ('push','tag'):add('network')
            if git_config_write(g):
                add('persistence_config','git_config')
                if any(x in ('--global','--system') for x in g):add('outside_repo_writes','global_git_config')
            if g[0]=='push' and any(x=='--force' or x=='-f' for x in g[1:]):add('destructive','force_push','high')
            elif g[0]=='push' and any(x.startswith('--force-with-lease') for x in g[1:]):add('destructive','lease_push')
            if g[0]=='reset' and '--hard' in g or g[0] in ('filter-branch','filter-repo','rebase'):add('destructive','history_change')
        if name=='chmod' and any('R' in x for x in v[1:] if x.startswith('-')):add('destructive','recursive_permissions')
        if name=='rm':
            flags=''.join(x.lstrip('-') for x in v[1:] if x.startswith('-'))
            if ('r' in flags or 'recursive' in flags) and ('f' in flags or 'force' in flags):
                targets=[resolved(x,event['cwd']) for x in v[1:] if not x.startswith('-')];targets=[p for p in targets if p is not None]
                add('scratch_cleanup' if targets and all(is_scratch(p,repo,scratch) for p in targets) else 'destructive','recursive_remove')
    # Bare env is a command; prefix env assignments/wrappers were removed.
    if re.search(r'(?:^|[;&\n])\s*env\s*\|\s*(?:grep\b[^\n]*\s-c\b|wc\b)',event['command']):presence=True
    elif re.search(r'(?:^|[;&\n])\s*env\s*(?:\||$)',event['command']):secret_env=True
    if secret_env:add('secrets','environment_read')
    if presence:add('secrets','environment_presence','low')
    secret_path=re.compile(r'(?i)(?:^|[/\\])(?:\.env(?:\.[^/\\]*)?|\.ssh|\.aws|\.[^/\\]+_key|[^/\\]+\.pem|id_[^/\\]+|\.netrc|\.npmrc|\.pypirc|credentials[^/\\]*)(?:[/\\]|$)')
    if any(secret_path.search(p.strip('"\x27')) for p in access if isinstance(p,str)):add('secrets','credential_source')
    for raw,path in event['paths']:
        cls=agent_class(path)
        if cls:add('persistence_config',cls);continue
        log_targets={resolved(x,event['cwd']) for _,v in parts for x in redirect_paths(v)+([clean_target(x) for x in v[1:] if not x.startswith('-')] if Path(v[0]).name=='tee' else [])}
        if not path.is_relative_to(repo) and path.suffix.casefold()=='.log' and path in log_targets and not persistent_path(raw) and not sensitive_area(raw) and not SECRET_PATH.search(raw):
            add('log_output');continue
        if is_scratch(path,repo,scratch):
            if not any(r['category']=='scratch_cleanup' for r in result):add('scratch_write')
            continue
        if not path.is_relative_to(repo):add('outside_repo_writes')
        if persistent_path(raw):add('persistence_config','configuration_path')
        if dependency_path(raw):add('dependencies')
    if is_dependency(event['command']):add('dependencies')
    tool=t.tool.lower()
    if any(word in tool for word in ('webfetch','web_fetch','fetch_url','web.run','web__run','http_request')) or is_publish(event['command']):add('network')
    # In one call, only execution *after* a literal download qualifies.
    downloaded=set()
    for _,v in parts:
        name=Path(v[0]).name
        if name in ('curl','wget'):
            names=redirect_paths(v)+[v[i+1] for i,x in enumerate(v[:-1]) if x in ('-o','--output','-O')]
            downloaded.update(p for p in (resolved(x,event['cwd']) for x in names) if p is not None)
        else:
            fragment={**event,'command':shlex.join(v)}
            if any(executes_download(fragment,target) for target in downloaded):add('remote_code','download_file')
    return result

def categories(event,repo):return [r['category'] for r in rules(event,repo)]


def tests_before_commit(command):
    parts=segments(command);last_mod=-1
    for i,(_,v) in enumerate(parts):
        g=git_args(v)
        if g and g[0]=='commit':return any(j>last_mod and is_test_build(' '.join(parts[j][1])) for j in range(i))
        fragment=' '.join(v)
        targets=modifications({'command':fragment,'cwd':None})
        if targets is None or Path(v[0]).name in ('python','python3','node') and '<<' in v and literal_writes(command):last_mod=i
    return False
