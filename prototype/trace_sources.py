# SPDX-License-Identifier: Apache-2.0
"""Read explicitly approved tool transcripts without refreshing or changing a profile."""
from dataclasses import dataclass,field
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
if __package__:
    from .codex_capture import user_text
    from .privacy import redact
    from .local_profile import profile_directory
    from .paths import data_home
else:
    from codex_capture import user_text
    from privacy import redact
    from local_profile import profile_directory
    from paths import data_home

@dataclass
class Turn:
    number:int
    kind:str
    text:str
    timestamp:str=None
    tool:str=None
    arguments:object=None
    call_id:str=None
    cwd:str=None
    output_chunks:object=None

@dataclass
class Session:
    provider:str
    identity:str
    path:Path
    turns:list=field(default_factory=list)
    fingerprint:str=''
    source_size:int=0
    complete_lines:bool=False
    @property
    def short_id(self):return hashlib.sha256((self.provider+':'+self.identity).encode()).hexdigest()[:12]
    def reference(self,number):
        source=hashlib.sha256((self.provider+':'+self.identity+':'+str(self.path)).encode()).hexdigest()[:24]
        return {'turn':number,'reference':'urn:context-bridge:turn:'+source+':'+str(number)}

def seconds(value):
    try:
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        if dt.tzinfo is None:return None
        return dt.timestamp()
    except (ValueError,TypeError,AttributeError):return None

def config_path(directory=None,profile=None):
    root=profile_directory(Path(directory) if directory is not None else data_home()/'manager',profile)
    return root/('enrollment.json' if (root/'enrollment.json').is_file() else 'profile.json')

def read_config(path):
    path=Path(path)
    if not path.is_file():raise ValueError('Profile does not exist; trace creates no library')
    return json.loads(path.read_text())

def approved_paths(data):
    blocked={str(Path(p).expanduser().resolve()) for p in data.get('excluded_transcripts',[])}
    for value in data.get('sessions',{}).values():
        if not value.get('approved',False):
            blocked.update(str(Path(p).resolve()) for p in [value.get('transcript')]+[a.get('transcript') for a in value.get('aliases',[])] if p)
    result=[]
    for raw in data.get('approved_transcripts',[]):
        path=Path(raw)
        if not path.is_absolute() or path.is_symlink() or not path.is_file():continue
        resolved=path.resolve()
        if str(resolved) in blocked:continue
        # Do not follow symlinked parent directories after approval.
        if path.absolute()!=resolved:continue
        meta=data.get('sources',{}).get(str(path),data.get('sources',{}).get(str(resolved),{}))
        provider=meta.get('provider')
        if provider is None:
            managed={str(Path(p).resolve()) for s in data.get('sessions',{}).values() if s.get('approved') for p in [s.get('transcript')]+[a.get('transcript') for a in s.get('aliases',[])] if p}
            if str(resolved) not in managed:continue
            provider='claude-code'
        if provider not in ('claude-code','codex'):continue
        result.append((resolved,provider,meta.get('conversation_id')))
    return result

def excluded(data,provider,identity):
    if provider=='claude-code':
        for sid,value in data.get('sessions',{}).items():
            if not value.get('approved',False) and identity in [sid]+[a.get('session_id') for a in value.get('aliases',[])]:return True
    if provider+':'+identity in data.get('excluded_conversations',[]):return True
    digest=hashlib.sha256((provider+':'+identity).encode()).hexdigest()
    return digest in data.get('web_exclusions',{}).get(provider,[])

def content_text(content,types=('text','input_text','output_text')):
    if isinstance(content,str):return content
    if not isinstance(content,list):return ''
    return '\n'.join(b.get('text','') for b in content if isinstance(b,dict) and b.get('type') in types and isinstance(b.get('text'),str))

def tool_text(value,depth=0):
    if depth>10:return ''
    if isinstance(value,str):
        try:decoded=json.loads(value)
        except ValueError:
            # Multiple wrapper results can be concatenated JSON objects.
            decoder=json.JSONDecoder();chunks=[];offset=0
            while offset<len(value):
                while offset<len(value) and value[offset].isspace():offset+=1
                if offset==len(value):break
                try:item,end=decoder.raw_decode(value,offset)
                except ValueError:return value
                chunks.append(tool_text(item,depth+1));offset=end
            return '\n'.join(chunks) if chunks else value
        return tool_text(decoded,depth+1) if isinstance(decoded,(dict,list)) else value
    if isinstance(value,list):return '\n'.join(tool_text(v,depth+1) for v in value if isinstance(v,(dict,str)))
    if isinstance(value,dict):
        if value.get('type') in ('image','image_url','audio','resource','resource_link'):return ''
        prefix='exit code '+str(value['exit_code'])+'\n' if type(value.get('exit_code')) is int and value['exit_code']!=0 else 'error: tool failed\n' if value.get('isError') is True else ''
        for key in ('output','content','text','result'):
            if isinstance(value.get(key),(str,list,dict)):return prefix+tool_text(value[key],depth+1)
        return prefix+json.dumps(value)
    return ''


def tool_chunks(value,depth=0):
    """Preserve separate literal wrapper results, including empty quiet output."""
    if depth>10:return []
    if isinstance(value,str):
        decoder=json.JSONDecoder();items=[];offset=0
        while offset<len(value):
            while offset<len(value) and value[offset].isspace():offset+=1
            if offset==len(value):break
            try:item,end=decoder.raw_decode(value,offset)
            except ValueError:return [value]
            items.append(item);offset=end
        if not items:return [value]
        if all(isinstance(item,(dict,list)) for item in items):return [chunk for item in items for chunk in tool_chunks(item,depth+1)]
        return [value]
    if isinstance(value,list):return [chunk for item in value for chunk in tool_chunks(item,depth+1)]
    if isinstance(value,dict):
        if 'output' in value or 'result' in value:return [tool_text(value)]
        for key in ('content','text'):
            if key in value:return tool_chunks(value[key],depth+1)
        return [tool_text(value)]
    return []


def read_session(path,provider,identity,data):
    raw=path.read_bytes();fingerprint=hashlib.sha256(raw).hexdigest()
    turns=[];cwd=None;sid=identity
    for number,line in enumerate(raw.splitlines(),1):
        if len(line)>16_000_000:continue
        try:item=json.loads(line)
        except (ValueError,UnicodeDecodeError):continue
        if not isinstance(item,dict):continue
        when=seconds(item.get('timestamp'))
        timestamp=datetime.fromtimestamp(when,timezone.utc).isoformat() if when is not None else None
        if provider=='codex':
            p=item.get('payload',{})
            if not isinstance(p,dict):continue
            if item.get('type')=='session_meta':
                actual=p.get('id')
                if actual and sid and actual!=sid:return None
                sid=sid or actual;cwd=p.get('cwd',cwd)
                continue
            if item.get('type')=='turn_context':cwd=p.get('cwd',cwd);continue
            if item.get('type')!='response_item':continue
            kind=p.get('type')
            if kind=='message' and p.get('role') in ('user','assistant'):
                text=content_text(p.get('content'))
                if p['role']=='user':text=user_text(text)
                if text.strip():turns.append(Turn(number,p['role'],text,timestamp,cwd=cwd))
            elif kind in ('function_call','custom_tool_call'):
                args=p.get('arguments',p.get('input',{}))
                if isinstance(args,str):
                    try:args=json.loads(args)
                    except ValueError:pass
                turns.append(Turn(number,'tool_call','',timestamp,p.get('name',''),args,p.get('call_id') or p.get('id'),cwd))
            elif kind in ('function_call_output','custom_tool_call_output'):
                value=p.get('output','')
                turns.append(Turn(number,'tool_output',tool_text(value),timestamp,call_id=p.get('call_id'),cwd=cwd,output_chunks=tool_chunks(value)))
        else:
            actual=item.get('sessionId')
            if actual and sid and actual!=sid:continue
            sid=sid or actual
            if sid and excluded(data,provider,sid):continue
            cwd=item.get('cwd',cwd);message=item.get('message',{})
            if not isinstance(message,dict):continue
            role=message.get('role',item.get('type'));content=message.get('content')
            if role in ('user','assistant'):
                text=content_text(content)
                if role=='user':text=user_text(text)
                if text.strip():turns.append(Turn(number,role,text,timestamp,cwd=cwd))
            if isinstance(content,list):
                for b in content:
                    if not isinstance(b,dict):continue
                    if b.get('type')=='tool_use':turns.append(Turn(number,'tool_call','',timestamp,b.get('name',''),b.get('input',{}),b.get('id'),cwd))
                    elif b.get('type')=='tool_result':turns.append(Turn(number,'tool_output',tool_text(b.get('content')),timestamp,call_id=b.get('tool_use_id'),cwd=cwd,output_chunks=tool_chunks(b.get('content'))))
    if not isinstance(sid,str) or not sid or excluded(data,provider,sid):return None
    return Session(provider,sid,path,turns,fingerprint,len(raw),raw.endswith(b'\n'))

def sessions(config):
    data=read_config(config);result=[]
    for path,provider,identity in approved_paths(data):
        if identity and excluded(data,provider,identity):continue
        try:value=read_session(path,provider,identity,data)
        except (OSError,ValueError):continue
        if value:result.append(value)
    return result

def still_approved(config,session,allow_append=False):
    data=read_config(config)
    allowed={(p,provider,identity) for p,provider,identity in approved_paths(data)}
    if not any(p==session.path and provider==session.provider and (identity is None or identity==session.identity) for p,provider,identity in allowed):return False
    if excluded(data,session.provider,session.identity):return False
    try:
        raw=session.path.read_bytes()
        if allow_append and session.complete_lines and len(raw)>=session.source_size:
            raw=raw[:session.source_size]
        return hashlib.sha256(raw).hexdigest()==session.fingerprint
    except OSError:return False
