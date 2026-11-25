# SPDX-License-Identifier: Apache-2.0
"""Content-free, profile-local append-only hash chain. No trusted external anchor."""
from collections import Counter
import hashlib
import json
import os
import re
import stat
from pathlib import Path
import fcntl
if __package__:
    from .trace_sources import read_config,approved_paths,excluded
else:
    from trace_sources import read_config,approved_paths,excluded


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def path_id(path):return hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()

def records(text):
    result=[];previous='0'*64
    for line in text.splitlines():
        row=json.loads(line)
        if not isinstance(row,dict) or row.get('previous')!=previous or row.get('hash')!=digest({k:v for k,v in row.items() if k!='hash'}):raise ValueError('Invalid ledger hash chain')
        if row.get('schema')!=1 or not isinstance(row.get('summary'),dict) or not isinstance(row.get('snapshots'),list):raise ValueError('Invalid ledger record')
        for snapshot in row['snapshots']:
            if not isinstance(snapshot,dict) or type(snapshot.get('size')) is not int or snapshot['size']<0 or type(snapshot.get('complete_lines')) is not bool or any(not isinstance(snapshot.get(k),str) or not re.fullmatch(r'[a-f0-9]{64}',snapshot[k]) for k in ('source_id','snapshot_sha256')):raise ValueError('Invalid ledger snapshot')
        previous=row['hash'];result.append(row)
    return result


def seal(run,repo):
    if __package__:from .audit import checked
    else:from audit import checked
    root=run.config.parent.resolve()
    if root.is_relative_to(repo):raise ValueError('Ledger must be outside the repository')
    checked(run);path=root/'audit-ledger.jsonl'
    if path.is_symlink() or path.resolve().is_relative_to(repo):raise ValueError('Ledger target must stay outside the repository')
    fd=os.open(str(path),os.O_RDWR|os.O_CREAT|os.O_APPEND|getattr(os,'O_NOFOLLOW',0),0o600)
    info=os.fstat(fd)
    if info.st_nlink!=1 or not stat.S_ISREG(info.st_mode):
        os.close(fd);raise ValueError('Ledger must be a private regular file')
    os.fchmod(fd,0o600)
    with os.fdopen(fd,'a+') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX);stream.seek(0);old=records(stream.read())
        checked(run)
        snapshots=sorted([{'source_id':path_id(s.path),'snapshot_sha256':s.fingerprint,'size':s.source_size,'complete_lines':s.complete_lines} for s in run.snapshots],key=lambda v:v['source_id'])
        row={'schema':1,'previous':old[-1]['hash'] if old else '0'*64,'repository_id':path_id(repo),'snapshots':snapshots,'summary':run.report['summary']}
        row['hash']=digest(row);stream.seek(0,2);stream.write(json.dumps(row,sort_keys=True)+'\n');stream.flush();os.fsync(stream.fileno())
    return {'ledger_hash':row['hash'],'snapshots':len(snapshots)}


def verify(config):
    config=Path(config);path=config.parent/'audit-ledger.jsonl'
    if not path.is_file():return {'ok':False,'chain_valid':False,'records':0,'status':'no ledger','snapshots':[]}
    try:
        with path.open() as stream:
            fcntl.flock(stream,fcntl.LOCK_SH);rows=records(stream.read())
    except (ValueError,KeyError,TypeError):return {'ok':False,'chain_valid':False,'records':0,'status':'ledger chain invalid','snapshots':[]}
    data=read_config(config)
    eligible={}
    for p,provider,identity in approved_paths(data):
        if identity is not None and excluded(data,provider,identity):continue
        if identity is None and (any(v.startswith(provider+':') for v in data.get('excluded_conversations',[])) or data.get('web_exclusions',{}).get(provider)):continue
        eligible[path_id(p)]=p
    declared={path_id(p):Path(p) for p in data.get('approved_transcripts',[]) if isinstance(p,str) and Path(p).is_absolute()}
    blocked={str(Path(p).resolve()) for p in data.get('excluded_transcripts',[]) if isinstance(p,str)}
    latest={}
    # Verify every seal, including an earlier prefix before a later seal.
    for index,row in enumerate(rows):
        for snapshot in row['snapshots']:
            sid=snapshot['source_id'];p=eligible.get(sid);status='unavailable_or_revoked'
            if p is not None:
                raw=p.read_bytes();size=snapshot['size']
                if len(raw)<size:status='truncated'
                elif hashlib.sha256(raw[:size]).hexdigest()!=snapshot['snapshot_sha256']:status='modified'
                elif len(raw)>size:status='appended' if snapshot['complete_lines'] else 'modified'
                else:status='unchanged'
            elif sid in declared and str(declared[sid].resolve()) not in blocked and not declared[sid].exists():status='deleted'
            latest[(index,sid)]={'seal':index+1,'source_id':sid,'status':status}
    entries=list(latest.values());counts=Counter(e['status'] for e in entries)
    return {'ok':all(e['status'] in ('unchanged','appended') for e in entries),'chain_valid':True,'records':len(rows),'counts':dict(sorted(counts.items())),'snapshots':entries}
