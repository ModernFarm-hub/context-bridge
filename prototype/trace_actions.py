# SPDX-License-Identifier: Apache-2.0
"""Conservative transcript action parsing. Never execute recorded commands."""
from dataclasses import dataclass,field
from collections import Counter
import ast
import difflib
import json
from pathlib import Path
import re
import shlex

@dataclass
class Action:
    turn:int
    timestamp:str
    kind:str
    cwd:str
    path:str=None
    added:set=field(default_factory=set)
    removed:set=field(default_factory=set)
    command:str=''
    subject:str=None
    observed_hash:str=None
    output_turn:int=None
    output:str=''
    added_counts:object=field(default_factory=Counter)
    removed_counts:object=field(default_factory=Counter)

def line_counts(text):return Counter(str(text).splitlines())

def change_counts(old,new):
    added=Counter();removed=Counter()
    for line in difflib.ndiff(str(old).splitlines(),str(new).splitlines()):
        if line.startswith('+ '):added[line[2:]]+=1
        elif line.startswith('- '):removed[line[2:]]+=1
    return added,removed


def lines(text):
    return {s.strip() for s in str(text).splitlines() if len(s.strip())>=5 and re.search(r'[A-Za-z0-9_]',s)}

def additions(old,new):
    added=set();removed=set()
    for line in difflib.ndiff(str(old).splitlines(),str(new).splitlines()):
        if line.startswith('+ '):added.update(lines(line[2:]))
        elif line.startswith('- '):removed.update(lines(line[2:]))
    return added,removed

def literal(value):
    try:
        result=json.loads(value) if value.startswith('"') else ast.literal_eval(value)
        return result if isinstance(result,str) else None
    except (ValueError,SyntaxError):return None

def embedded_strings(code,key):
    pattern=r'\b'+('(?:cmd|command)' if key=='__commands__' else re.escape(key))+r'["\x27]?\s*:\s*("(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27)'
    return [s for s in (literal(m.group(1)) for m in re.finditer(pattern,code)) if s is not None]

def commands(tool,args):
    if isinstance(args,dict):
        value=args.get('command',args.get('cmd'))
        if isinstance(value,list):
            if len(value)>=3 and value[0] in ('bash','sh','zsh','/bin/bash','/bin/sh') and value[1] in ('-c','-lc'):return [value[2]]
            return [shlex.join(str(x) for x in value)]
        if isinstance(value,str):return [value]
        code=args.get('code','')
        if isinstance(code,str):return embedded_strings(code,'__commands__')
    if isinstance(args,str):
        name=tool.lower().rsplit('.',1)[-1]
        if name in ('exec','functions','js','javascript','parallel'):
            return embedded_strings(args,'__commands__')
        if name in ('bash','exec_command','shell','shell_command'):return [args]
    return []

def shell_tokens(command):
    """Tokenize literal shell syntax across quoted newlines; never evaluate it."""
    lexer=shlex.shlex(command,posix=True,punctuation_chars=';&|')
    lexer.whitespace_split=True;lexer.commenters=''
    return list(lexer)

def _shell_parts(command):
    """Literal segments with separators; quoted newlines remain message data."""
    spans=[]
    for m in re.finditer(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?[^\n]*\n",command):
        end=re.search(r'^\s*'+re.escape(m[1])+r'\s*$',command[m.end():],re.M)
        if end:spans.append((m.end(),m.end()+end.end()))
    for start,end in reversed(spans):command=command[:start]+command[end:]
    result=[];quote=None;escaped=False
    for char in command:
        if escaped:
            if char=='\n':result.pop()
            else:result.append(char)
            escaped=False;continue
        if char=='\\' and quote!="'":result.append(char);escaped=True;continue
        if char in ("'",'"'):
            if quote==char:quote=None
            elif quote is None:quote=char
        result.append(';' if char=='\n' and quote is None else char)
    lexer=shlex.shlex(''.join(result),posix=True,punctuation_chars=';&|<>')
    lexer.whitespace_split=True;lexer.commenters=''
    parts=[];current=[];separator=''
    for token in lexer:
        if token in ('&&',';','||','|','&',';;'):
            if current:parts.append((separator,current))
            current=[];separator=token
        else:current.append(token)
    if current:parts.append((separator,current))
    return parts


def shell_parts(command,with_scope=False,_scope=()):
    """Expose nested literal commands in execution order, without evaluation.

    Substitution output is opaque; quoted text and heredoc data are not commands.
    """
    spans=[]
    for m in re.finditer(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?[^\n]*\n",command):
        end=re.search(r'^\s*'+re.escape(m[1])+r'\s*$',command[m.end():],re.M)
        if end:spans.append((m.end(),m.end()+end.end()))
    for start,end in reversed(spans):command=command[:start]+command[end:]
    nested={};out=[];i=0;quote=None
    while i<len(command):
        c=command[i]
        if c=='\\' and quote!="'" and i+1<len(command):out.extend(command[i:i+2]);i+=2;continue
        if c in ("'",'"'):
            if quote==c:quote=None
            elif quote is None:quote=c
            out.append(c);i+=1;continue
        if quote!="'" and (command.startswith('$(',i) or c=='`'):
            tick=c=='`';start=i+1 if tick else i+2;j=start;depth=1;inner=None
            while j<len(command):
                x=command[j]
                if x=='\\' and inner!="'":j+=2;continue
                if x in ("'",'"'):
                    if inner==x:inner=None
                    elif inner is None:inner=x
                if inner is None:
                    if tick and x=='`':break
                    if not tick:
                        if x=='(':depth+=1
                        elif x==')':
                            depth-=1
                            if depth==0:break
                j+=1
            if j<len(command):
                marker='__CB_SUB_'+str(len(nested))+'__';nested[marker]=command[start:j]
                out.append(marker);i=j+1;continue
        out.append(c);i+=1
    result=[]
    for sep,values in _shell_parts(''.join(out)):
        for value in values:
            for marker,body in nested.items():
                if marker in value:result.extend(shell_parts(body,with_scope,_scope+(marker,)))
        result.append((sep,values,_scope) if with_scope else (sep,values))
    return result


def executable(tokens):
    """Skip literal assignments/env and loop-body markers; never expand vars."""
    i=0
    while i<len(tokens) and tokens[i] in ('do','then','{','(','while','until','if'):i+=1
    if i<len(tokens) and tokens[i] in ('for','done','fi'):return []
    while i<len(tokens) and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=',tokens[i]):i+=1
    if i<len(tokens) and Path(tokens[i]).name=='env':
        env_start=i;i+=1
        while i<len(tokens):
            value=tokens[i]
            if value in ('-u','--unset'):
                i+=2;continue
            if value in ('-i','--ignore-environment','--') or value.startswith('--unset=') or re.match(r'^[A-Za-z_][A-Za-z0-9_]*=',value) or re.fullmatch(r'\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[^}]+\})',value):i+=1;continue
            break
        if i>=len(tokens):return tokens[env_start:]
    return tokens[i:]


def git_index(tokens):
    if not tokens or Path(tokens[0]).name!='git':return None
    i=1
    while i<len(tokens):
        value=tokens[i]
        if value in ('-c','-C','--config-env'):i+=2
        elif value in ('--no-pager','--paginate','--no-optional-locks','--literal-pathspecs','--no-replace-objects'):i+=1
        elif value.startswith(('-c','-C','--config-env=')) and len(value)>2:i+=1
        elif value.startswith('-'):return None
        else:return i
    return None


def context(command,cwd,repo):
    """Recognize explicit leading cd and git -C without evaluating shell syntax."""
    current=Path(cwd).expanduser().resolve() if isinstance(cwd,str) and '$' not in cwd else None
    cd=re.match(r'\s*cd\s+("[^"]*"|\x27[^\x27]*\x27|[^;&\n]+)\s*&&',command)
    if cd:
        try:parts=shlex.split(cd.group(1))
        except ValueError:return None
        if len(parts)!=1 or '$' in parts[0]:return None
        if not Path(parts[0]).is_absolute() and current is None:return None
        current=(current/parts[0]).resolve() if not Path(parts[0]).is_absolute() else Path(parts[0]).resolve()
    try:
        raw_segments=[values for _,values in shell_parts(command)]
        unsafe=[v for values in raw_segments for v in values]
        if any(v.startswith(('GIT_DIR=','GIT_WORK_TREE=','--git-dir','--work-tree','core.worktree=')) for v in unsafe):return None
        segments=[executable(values) for values in raw_segments]
        git_segments=[values for values in segments if git_index(values) is not None]
        selected=next((values for values in git_segments if values[git_index(values)]=='commit'),git_segments[-1] if git_segments else [])
        tokens=selected
    except ValueError:tokens=[]
    if any(t in ('--git-dir','--work-tree') or t.startswith(('--git-dir=','--work-tree=','GIT_DIR=','GIT_WORK_TREE=')) for t in tokens):return None
    for i,t in enumerate(tokens):
        if (t=='-C' and i+1<len(tokens)) or (t.startswith('-C') and len(t)>2):
            target=tokens[i+1] if t=='-C' else t[2:]
            if '$' in target:return None
            if not Path(target).is_absolute() and current is None:return None
            current=Path(target).resolve() if Path(target).is_absolute() else (current/target).resolve()
    if current is None or not current.is_relative_to(repo):return None
    parent=current
    while parent!=repo:
        if (parent/'.git').exists():return None
        parent=parent.parent
    return str(current)

def relative(path,cwd,repo):
    if not isinstance(path,str) or not cwd or '$' in path:return None
    value=(Path(cwd)/path).resolve()
    return str(value.relative_to(repo)) if value.is_relative_to(repo) else None

def heredocs(command):
    result={}
    for m in re.finditer(r'<<-?\s*[\x27"]?([A-Za-z_][A-Za-z0-9_]*)[\x27"]?[^\n]*\n',command):
        end=re.search(r'^\s*'+re.escape(m.group(1))+r'\s*$',command[m.end():],re.M)
        if end:result[m.group(1)]=command[m.end():m.end()+end.start()]
    return result

def subject(value):return ' '.join(value.splitlines()[0].split()).casefold() if value and value.splitlines() else None

def commit_subject(command,known_files,cwd):
    docs=heredocs(command)
    # Parse literal heredoc substitution without evaluating any shell code.
    substituted=False
    for marker,content in docs.items():
        pattern=r'(?P<q>"?)\$\(\s*cat\s+<<-?\s*[\'"]?'+re.escape(marker)+r'[\'"]?[^\n]*\n[\s\S]*?^\s*'+re.escape(marker)+r'\s*\n\s*\)(?P=q)'
        command,count=re.subn(pattern,lambda m:shlex.quote(content),command,flags=re.M)
        substituted=substituted or bool(count)
    try:segments=[executable(values) for _,values in shell_parts(command)]
    except ValueError:return None,False
    parts=None;ci=None
    for values in segments:
        j=git_index(values)
        if j is not None and values[j]=='commit':parts=values;ci=j;break
    if ci is None:return None,False
    messages=[];i=ci+1
    while i<len(parts):
        token=parts[i]
        if token in ('&&',';','||','&','|'):break
        if token in ('-m','--message','-F','--file'):
            if i+1>=len(parts):return None,True
            value=parts[i+1];i+=2
            if token in ('-F','--file'):
                if value=='-' and docs:messages.append(next(iter(docs.values())))
                else:messages.append(known_files.get(str((Path(cwd)/value).resolve()),''))
            else:messages.append(value)
            continue
        if token.startswith(('--message=','--file=')):
            name,value=token.split('=',1)
            messages.append(value if name=='--message' else known_files.get(str((Path(cwd)/value).resolve()),''))
        elif re.match(r'^-[aqvs]*m',token):
            value=token[token.index('m')+1:]
            if not value:
                if i+1>=len(parts):return None,True
                i+=1;value=parts[i]
            messages.append(value)
        elif token.startswith('-F') and len(token)>2:messages.append(known_files.get(str((Path(cwd)/token[2:]).resolve()),''))
        i+=1
    return subject(messages[0]) if messages and messages[0] else None,True

def patch_actions(text,turn,cwd,repo,known):
    result=[];current=None;added=[];removed=[];mode=None
    def finish():
        if current is None:return
        p=relative(current,cwd,repo)
        if p:
            old=known.get(str((Path(cwd)/current).resolve()),'')
            result.append(Action(turn.number,turn.timestamp,'edit',cwd,p,lines('\n'.join(added)),lines('\n'.join(removed)) if mode!='Delete' else lines(old),added_counts=Counter(added),removed_counts=Counter(removed) if mode!='Delete' else line_counts(old)))
        if mode=='Add':known[str((Path(cwd)/current).resolve())]='\n'.join(added)
    for line in text.splitlines():
        match=re.match(r'^\*\*\* (Add|Update|Delete) File: (.+)$',line)
        if match:
            finish();mode,current=match.groups();added=[];removed=[]
        elif line.startswith('*** End Patch'):finish();current=None
        elif current is not None:
            if line.startswith('+'):added.append(line[1:])
            elif line.startswith('-'):removed.append(line[1:])
    finish();return result

def call_cwd(turn):
    args=turn.arguments;tool=turn.tool.lower().rsplit('.',1)[-1]
    cwd=turn.cwd
    code=args if isinstance(args,str) and tool in ('exec','functions','js','javascript','parallel') else args.get('code','') if isinstance(args,dict) else ''
    directories=embedded_strings(code,'workdir')+embedded_strings(code,'cwd') if isinstance(code,str) else []
    if len(set(directories))>1:raise ValueError('Ambiguous working directory')
    if directories:
        directory=Path(directories[0])
        if not directory.is_absolute() and not cwd:raise ValueError('Unknown working directory')
        cwd=str((Path(cwd)/directory).resolve()) if not directory.is_absolute() else str(directory.resolve())
    if isinstance(args,dict):
        directory=args.get('workdir',args.get('cwd'))
        if isinstance(directory,str):
            if not Path(directory).is_absolute() and not cwd:raise ValueError('Unknown working directory')
            cwd=str((Path(cwd)/directory).resolve()) if not Path(directory).is_absolute() else directory
    return cwd

def literal_writes(command):
    """Inspect literal Python/Node stdin scripts. No eval, imports or file reads."""
    try:heads=[executable(v) for _,v in shell_parts(command)]
    except ValueError:return []
    python=any(v and re.fullmatch(r'python(?:3(?:\.\d+)?)?',Path(v[0]).name) and not any(x in ('-c','-m') for x in v[1:]) for v in heads)
    node=any(v and Path(v[0]).name=='node' and not any(x in ('-e','--eval','-p') for x in v[1:]) for v in heads)
    if not (python or node):return []
    result=[]
    for body in heredocs(command).values():
        if node:
            # Only identifiers in executable JS, never quoted examples/comments.
            mask=[];quote=None;escaped=False;comment=None;i=0
            while i<len(body):
                c=body[i];pair=body[i:i+2]
                if comment=='line':
                    mask.append(' ' if c!='\n' else '\n')
                    if c=='\n':comment=None
                elif comment=='block':
                    if pair=='*/':mask.extend('  ');i+=1;comment=None
                    else:mask.append(' ')
                elif quote:
                    mask.append(' ')
                    if escaped:escaped=False
                    elif c=='\\':escaped=True
                    elif c==quote:quote=None
                elif pair in ('//','/*'):mask.extend('  ');i+=1;comment='line' if pair=='//' else 'block'
                elif c in ('"',"'",'`'):quote=c;mask.append(' ')
                else:mask.append(c)
                i+=1
            executable_mask=''.join(mask)
            string=r'("(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27)'
            for m in re.finditer(r'\bwriteFile(?:Sync)?\s*\(\s*'+string+r'\s*,',body):
                if not executable_mask[m.start():].startswith('writeFile'):continue
                path=literal(m[1]);value=re.match(r'\s*'+string,body[m.end():]);text=literal(value[1]) if value else None
                if path is not None:result.append({'path':path,'counts':line_counts(text) if text is not None else Counter()})
        if not python:continue
        try:tree=ast.parse(body)
        except SyntaxError:continue
        paths={};texts={};handles={}
        def string(n):return n.value if isinstance(n,ast.Constant) and isinstance(n.value,str) else None
        def target(n):
            value=string(n)
            if value is not None:return value
            if isinstance(n,ast.Name):return paths.get(n.id)
            if isinstance(n,ast.Call) and n.args and ((isinstance(n.func,ast.Name) and n.func.id=='Path') or isinstance(n.func,ast.Attribute) and n.func.attr=='Path'):return string(n.args[0])
            return None
        def text(n):
            value=string(n)
            if value is not None:return line_counts(value)
            if isinstance(n,ast.Name):return texts.get(n.id,Counter())
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='replace' and len(n.args)>=2 and string(n.args[0]) is not None and string(n.args[1]) is not None:return line_counts(string(n.args[1]))
            return Counter()
        def ordered(node):
            yield node
            for child in ast.iter_child_nodes(node):yield from ordered(child)
        for n in ordered(tree):
            if isinstance(n,ast.Assign):
                for name in n.targets:
                    if isinstance(name,ast.Name):
                        value=target(n.value)
                        if value is not None:paths[name.id]=value
                        texts[name.id]=text(n.value)
            if isinstance(n,ast.With):
                for item in n.items:
                    call=item.context_expr
                    if isinstance(item.optional_vars,ast.Name) and isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='open' and len(call.args)>=2 and string(call.args[1]) and any(x in string(call.args[1]) for x in 'wax'):
                        value=target(call.args[0])
                        if value is not None:handles[item.optional_vars.id]=value
            if not isinstance(n,ast.Call) or not isinstance(n.func,ast.Attribute):continue
            if n.func.attr in ('write_text','write_bytes'):
                value=target(n.func.value)
                if value is not None:result.append({'path':value,'counts':text(n.args[0]) if n.args else Counter()})
            elif n.func.attr=='write':
                value=handles.get(n.func.value.id) if isinstance(n.func.value,ast.Name) else None
                call=n.func.value
                if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='open' and len(call.args)>=2 and string(call.args[1]) and any(x in string(call.args[1]) for x in 'wax'):value=target(call.args[0])
                if value is not None:result.append({'path':value,'counts':text(n.args[0]) if n.args else Counter()})
    return result


def actions(session,repo):
    result=[];known={};last_subject=None;outputs={t.call_id:t for t in session.turns if t.kind=='tool_output' and t.call_id}
    for turn in session.turns:
        if turn.kind!='tool_call':continue
        args=turn.arguments;tool=turn.tool.lower().rsplit('.',1)[-1]
        try:cwd=call_cwd(turn)
        except ValueError:continue
        file_cwd=str(Path(cwd).resolve()) if isinstance(cwd,str) and '$' not in cwd else None
        raw_cwd=cwd
        if file_cwd is None and isinstance(args,dict) and isinstance(args.get('file_path'),str) and Path(args['file_path']).is_absolute():file_cwd=str(repo)
        output=outputs.get(turn.call_id)
        cwd=context('',cwd,repo)
        if isinstance(args,dict) and tool in ('edit','write','multiedit') and file_cwd:
            path=args.get('file_path',args.get('path'))
            p=relative(path,file_cwd,repo)
            if tool=='write' and isinstance(path,str):known[str((Path(file_cwd)/path).resolve())]=args.get('content','')
            if p:
                edits=args.get('edits',[args]);added=set();removed=set();ac=Counter();rc=Counter()
                for edit in edits:
                    if tool=='write':a,r=lines(edit.get('content','')),set()
                    else:a,r=additions(edit.get('old_string',''),edit.get('new_string',''))
                    added.update(a);removed.update(r)
                    ca,cr=(line_counts(edit.get('content','')),Counter()) if tool=='write' else change_counts(edit.get('old_string',''),edit.get('new_string',''))
                    ac.update(ca);rc.update(cr)
                result.append(Action(turn.number,turn.timestamp,'edit',file_cwd,p,added,removed,added_counts=ac,removed_counts=rc))
                if tool=='write':known[str((Path(file_cwd)/path).resolve())]=args.get('content','')
        if isinstance(args,dict) and tool in ('read','read_file') and output and file_cwd:
            p=args.get('file_path',args.get('path'))
            if isinstance(p,str):known[str((Path(file_cwd)/p).resolve())]=re.sub(r'(?m)^\s*[0-9]+(?:→|\t|:)[ \t]?', '',output.text)
        patches=[]
        if tool=='apply_patch':patches=[args if isinstance(args,str) else args.get('patch',args.get('input',''))]
        if isinstance(args,dict) and isinstance(args.get('code'),str):
            for match in re.finditer(r'apply_patch\s*\(\s*("(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27)',args['code']):
                value=literal(match.group(1))
                if value:patches.append(value)
        if file_cwd:
            for patch in patches:
                if isinstance(patch,str):result.extend(patch_actions(patch,turn,file_cwd,repo,known))
        decoded_commands=commands(tool,args)
        for command_index,command in enumerate(decoded_commands):
            actual=context(command,raw_cwd,repo)
            if not actual:continue
            for write in literal_writes(command):
                path=write['path']
                if path.startswith('~'):continue
                p=relative(path,actual,repo)
                if p:
                    counts=write['counts'];result.append(Action(turn.number,turn.timestamp,'edit' if counts else 'script',actual,p,set(v.strip() for v in counts if len(v.strip())>=5),added_counts=counts))
            for marker,body in heredocs(command).items():
                match=re.search(r'\bcat\b[^\n]*?>\s*("[^"]+"|\x27[^\x27]+\x27|[^\s<>]+)',command.split('\n',1)[0])
                if match:
                    try:path=shlex.split(match.group(1))[0]
                    except ValueError:continue
                    known[str((Path(actual)/path).resolve())]=body
                    p=relative(path,actual,repo)
                    if p:result.append(Action(turn.number,turn.timestamp,'edit',actual,p,lines(body),added_counts=line_counts(body)))
            for match in re.finditer(r'\b(?:echo|printf)\s+("(?:\\.|[^"\\])*"|\x27[^\x27]*\x27)\s*(?:>>|>)\s*([^\s;&]+)',command):
                try:value=shlex.split(match.group(1))[0];path=shlex.split(match.group(2))[0]
                except ValueError:continue
                value=value.replace('\\n','\n');known[str((Path(actual)/path).resolve())]=value
                p=relative(path,actual,repo)
                if p:result.append(Action(turn.number,turn.timestamp,'edit',actual,p,lines(value),added_counts=line_counts(value)))
            cat=re.fullmatch(r'\s*cat\s+("[^"]+"|\x27[^\x27]+\x27|[^\s;&|]+)\s*',command)
            if cat and output:
                try:filename=shlex.split(cat.group(1))[0]
                except ValueError:filename=None
                if filename:known[str((Path(actual)/filename).resolve())]=output.text
            try:commit_commands=[shlex.join(v) for _,raw in shell_parts(command) if (v:=executable(raw)) and (j:=git_index(v)) is not None and v[j]=='commit']
            except ValueError:commit_commands=[]
            # Keep heredoc message data for the single-commit form.
            if len(commit_commands)<=1:commit_commands=[command]
            for commit_command in commit_commands:
                title,is_commit=commit_subject(commit_command,known,actual)
                action=Action(turn.number,turn.timestamp,'commit' if is_commit else 'shell',actual,command=command,subject=title,output_turn=output.number if output else None,output=output.text if output else '')
                if output and output.output_chunks is not None and len(output.output_chunks)==len(decoded_commands):action.output=output.output_chunks[command_index]
                if is_commit and action.subject is None and '--amend' in command and '--no-edit' in command:action.subject=last_subject
                if is_commit and action.subject:last_subject=action.subject
                if re.search(r'\bgit\s+(?:diff|show)\b',command) and output and 'diff --git ' in output.text:action.kind='diff'
                result.append(action)
        # A wrapper may return several JSON result chunks. Each hash is used once.
        pending=[a for a in result if a.turn==turn.number and a.kind=='commit']
        if output and pending:
            text=re.sub(r'\x1b\[[0-9;]*m','',output.text)
            records=list(re.finditer(r'^\s*\[[^\n\]]*?\s([a-f0-9]{7,64})\]\s*([^\n]*)',text,re.M))
            unused=list(range(len(records)));paired={}
            # Reserve all exact-subject matches before assigning order fallbacks.
            for n,action in enumerate(pending):
                chosen=next((i for i in unused if subject(records[i][2])==action.subject),None)
                if chosen is not None:paired[n]=chosen;unused.remove(chosen)
            for n,action in enumerate(pending):
                if n not in paired and unused and (not action.subject or len(records)==len(pending)):
                    paired[n]=unused.pop(0)
            for n,action in enumerate(pending):
                chosen=paired.get(n)
                if chosen is None:continue
                record=records[chosen]
                action.observed_hash=record[1];action.subject=action.subject or subject(record[2])
                end=records[chosen+1].start() if chosen+1<len(records) else len(text)
                action.output=text[record.start():end]
    return result
