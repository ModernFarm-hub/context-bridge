# SPDX-License-Identifier: Apache-2.0
"""Conservative transcript action parsing. Never execute recorded commands."""
from dataclasses import dataclass,field
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
    pattern=r'\b'+re.escape(key)+r'["\x27]?\s*:\s*("(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27)'
    return [s for s in (literal(m.group(1)) for m in re.finditer(pattern,code)) if s is not None]

def commands(tool,args):
    if isinstance(args,dict):
        value=args.get('command',args.get('cmd'))
        if isinstance(value,list):
            if len(value)>=3 and value[0] in ('bash','sh','zsh','/bin/bash','/bin/sh') and value[1] in ('-c','-lc'):return [value[2]]
            return [shlex.join(str(x) for x in value)]
        if isinstance(value,str):return [value]
        code=args.get('code','')
        if isinstance(code,str):return embedded_strings(code,'cmd')+embedded_strings(code,'command')
    if isinstance(args,str):
        name=tool.lower().rsplit('.',1)[-1]
        if name in ('exec','functions','js','javascript','parallel'):
            return embedded_strings(args,'cmd')+embedded_strings(args,'command')
        if name in ('bash','exec_command','shell','shell_command'):return [args]
    return []

def shell_tokens(command):
    """Tokenize literal shell syntax across quoted newlines; never evaluate it."""
    lexer=shlex.shlex(command,posix=True,punctuation_chars=';&|')
    lexer.whitespace_split=True;lexer.commenters=''
    return list(lexer)

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
    try:tokens=shell_tokens(command)
    except ValueError:tokens=[]
    if any(t in ('--git-dir','--work-tree') or t.startswith(('--git-dir=','--work-tree=','GIT_DIR=','GIT_WORK_TREE=')) for t in tokens):return None
    for i,t in enumerate(tokens):
        if t=='-C' and i and tokens[i-1] in ('git',) and i+1<len(tokens):
            target=tokens[i+1]
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
    if not re.search(r'(?:^|[;&\n])\s*(?:git\s+|cd\s+[^\n]+&&\s*git\s+)',command) and not re.match(r'\s*git\s+',command):return None,False
    docs=heredocs(command)
    # Parse literal heredoc substitution without evaluating any shell code.
    substituted=False
    for marker,content in docs.items():
        pattern=r'(?P<q>"?)\$\(\s*cat\s+<<-?\s*[\'"]?'+re.escape(marker)+r'[\'"]?[^\n]*\n[\s\S]*?^\s*'+re.escape(marker)+r'\s*\n\s*\)(?P=q)'
        command,count=re.subn(pattern,lambda m:shlex.quote(content),command,flags=re.M)
        substituted=substituted or bool(count)
    try:parts=shell_tokens(command)
    except ValueError:return None,False
    ci=None
    for gi,token in enumerate(parts):
        if token!='git':continue
        j=gi+1
        if j<len(parts) and parts[j]=='-C':j+=2
        if j<len(parts) and parts[j]=='commit':ci=j;break
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
            result.append(Action(turn.number,turn.timestamp,'edit',cwd,p,lines('\n'.join(added)),lines('\n'.join(removed)) if mode!='Delete' else lines(old)))
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

def actions(session,repo):
    result=[];known={};last_subject=None;outputs={t.call_id:t for t in session.turns if t.kind=='tool_output' and t.call_id}
    for turn in session.turns:
        if turn.kind!='tool_call':continue
        args=turn.arguments;tool=turn.tool.lower().rsplit('.',1)[-1]
        cwd=turn.cwd
        code=args if isinstance(args,str) and tool in ('exec','functions','js','javascript','parallel') else args.get('code','') if isinstance(args,dict) else ''
        directories=embedded_strings(code,'workdir')+embedded_strings(code,'cwd') if isinstance(code,str) else []
        if len(set(directories))>1:continue
        if directories:
            directory=Path(directories[0])
            if not directory.is_absolute() and not cwd:continue
            cwd=str((Path(cwd)/directory).resolve()) if not directory.is_absolute() else str(directory.resolve())
        if isinstance(args,dict):
            directory=args.get('workdir',args.get('cwd'))
            if isinstance(directory,str):
                if not Path(directory).is_absolute() and not cwd:continue
                cwd=str((Path(cwd)/directory).resolve()) if not Path(directory).is_absolute() else directory
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
                edits=args.get('edits',[args]);added=set();removed=set()
                for edit in edits:
                    if tool=='write':a,r=lines(edit.get('content','')),set()
                    else:a,r=additions(edit.get('old_string',''),edit.get('new_string',''))
                    added.update(a);removed.update(r)
                result.append(Action(turn.number,turn.timestamp,'edit',file_cwd,p,added,removed))
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
        for command in commands(tool,args):
            actual=context(command,raw_cwd,repo)
            if not actual:continue
            for marker,body in heredocs(command).items():
                match=re.search(r'\bcat\b[^\n]*?>\s*("[^"]+"|\x27[^\x27]+\x27|[^\s<>]+)',command.split('\n',1)[0])
                if match:
                    try:path=shlex.split(match.group(1))[0]
                    except ValueError:continue
                    known[str((Path(actual)/path).resolve())]=body
                    p=relative(path,actual,repo)
                    if p:result.append(Action(turn.number,turn.timestamp,'edit',actual,p,lines(body)))
            for match in re.finditer(r'\b(?:echo|printf)\s+("(?:\\.|[^"\\])*"|\x27[^\x27]*\x27)\s*(?:>>|>)\s*([^\s;&]+)',command):
                try:value=shlex.split(match.group(1))[0];path=shlex.split(match.group(2))[0]
                except ValueError:continue
                value=value.replace('\\n','\n');known[str((Path(actual)/path).resolve())]=value
                p=relative(path,actual,repo)
                if p:result.append(Action(turn.number,turn.timestamp,'edit',actual,p,lines(value)))
            cat=re.fullmatch(r'\s*cat\s+("[^"]+"|\x27[^\x27]+\x27|[^\s;&|]+)\s*',command)
            if cat and output:
                try:filename=shlex.split(cat.group(1))[0]
                except ValueError:filename=None
                if filename:known[str((Path(actual)/filename).resolve())]=output.text
            title,is_commit=commit_subject(command,known,actual)
            action=Action(turn.number,turn.timestamp,'commit' if is_commit else 'shell',actual,command=command,subject=title,output_turn=output.number if output else None,output=output.text if output else '')
            if is_commit and action.subject is None and '--amend' in command and '--no-edit' in command:action.subject=last_subject
            if is_commit and output:
                match=re.search(r'^\[[^\n\]]*?\b([a-f0-9]{7,40})\]\s+([^\n]+)',output.text,re.M)
                if match:action.observed_hash=match.group(1);action.subject=action.subject or subject(match.group(2))
            if is_commit and action.subject:last_subject=action.subject
            if re.search(r'\bgit\s+(?:diff|show)\b',command) and output and 'diff --git ' in output.text:action.kind='diff'
            result.append(action)
    return result
