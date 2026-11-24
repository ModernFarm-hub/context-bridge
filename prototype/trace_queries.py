# SPDX-License-Identifier: Apache-2.0
"""Read-only git selectors and counts-only self-reports."""
import argparse
from collections import Counter
from pathlib import Path
import re
import json
import subprocess
if __package__:
    from .trace import repository,git,commit_ids,trace_commits
    from .trace_sources import config_path
else:
    from trace import repository,git,commit_ids,trace_commits
    from trace_sources import config_path


def inside_path(repo,path):
    if not isinstance(path,str) or not path.strip():raise ValueError('Supply a repository path')
    value=(repo/path).resolve()
    if not value.is_relative_to(repo) or value==repo:raise ValueError('Path must be inside the selected repository')
    return value.relative_to(repo).as_posix()


def since_arg(value):
    if not isinstance(value,str) or not value.strip() or value.startswith('-') or len(value)>100:raise ValueError('Supply a relative duration or date')
    m=re.fullmatch(r'(\d+)([dhw])',value)
    return m[1]+' '+{'d':'days','h':'hours','w':'weeks'}[m[2]]+' ago' if m else value


def resolve(repo,commit=None,path=None,line=None,range_=None,since=None,cap=10):
    repo=repository(repo);relative=inside_path(repo,path) if path is not None else None
    if sum(v is not None for v in (commit,range_,since))>1:raise ValueError('Choose commit, range or since')
    if line is not None and (relative is None or type(line) is not int or line<1 or any(v is not None for v in (commit,range_,since))):raise ValueError('line requires path alone and a positive line number')
    if commit is not None:
        if relative is not None or not isinstance(commit,str) or '..' in commit:raise ValueError('Use one commit ref, or path with optional range/since')
        return repo,commit_ids(repo,commit),0
    if line is not None:
        # Blame committed HEAD rather than uncommitted working-tree text.
        output=git(repo,'blame','--porcelain','-L',str(line)+','+str(line),'HEAD','--',relative)
        oid=output.split(None,1)[0] if output else ''
        if not re.fullmatch(r'[a-f0-9]{40,64}',oid) or set(oid)=={'0'}:raise ValueError('No committed line found')
        return repo,[oid],0
    args=['log','--format=%H','--date-order']
    if since is not None:args.append('--since='+since_arg(since))
    if range_ is not None:
        if not isinstance(range_,str) or range_.startswith('-') or '..' not in range_:raise ValueError('Supply a git revision range')
        args.extend(['--end-of-options',range_])
    else:args.extend(['--end-of-options','HEAD'])
    if relative is not None:args.extend(['--',':(literal)'+relative])
    ids=git(repo,*args).splitlines()
    if not all(re.fullmatch(r'[a-f0-9]{40,64}',oid) for oid in ids):raise ValueError('Invalid commit resolution')
    if range_ is None and since is None:
        if relative is None:raise ValueError('Supply commit, path, range or since')
        if not ids:raise ValueError('No commit touches this path')
        return repo,ids[:1],0
    return repo,ids[:cap],max(0,len(ids)-cap)


def report(repo,config,since='30d'):
    repo=repository(repo)
    ids=git(repo,'log','--format=%H','--since='+since_arg(since),'HEAD').splitlines()
    providers=Counter();confidence=Counter();linked=0;total_lines=0;linked_lines=0
    for oid in ids:
        row=trace_commits(repo,oid,config)[0]
        counts=git(repo,'show','--format=','--numstat','--no-ext-diff','--no-textconv',oid)
        changed=sum(int(v) for line in counts.splitlines() for v in line.split('\t',2)[:2] if v.isdigit())
        total_lines+=changed
        if row['matches']:
            linked+=1;linked_lines+=changed;confidence[row['confidence']]+=1
            for provider in {m['provider'] for m in row['matches']}:providers[provider]+=1
    return {'commits':len(ids),'commits_with_evidence':linked,'by_provider':dict(sorted(providers.items())),
        'by_confidence':dict(sorted(confidence.items())),'commits_without_evidence':len(ids)-linked,
        'changed_lines':total_lines,'changed_lines_in_commits_with_evidence':linked_lines,
        'percent_changed_lines_in_commits_with_evidence':100*linked_lines/total_lines if total_lines else None}


def report_main(argv):
    parser=argparse.ArgumentParser(prog='context-bridge trace report',description='Local counts-only developer self-report; evidence is not proof of authorship.')
    parser.add_argument('--repo',type=Path,default=Path.cwd());parser.add_argument('--since',default='30d');parser.add_argument('--profile');parser.add_argument('--directory',type=Path);parser.add_argument('--json',action='store_true')
    args=parser.parse_args(argv)
    try:result=report(args.repo,config_path(args.directory,args.profile),args.since)
    except (ValueError,OSError,subprocess.SubprocessError,KeyError,TypeError,AttributeError):parser.exit(1,'Counts report unavailable; check local repository and profile settings.\n')
    if args.json:print(json.dumps(result,indent=2))
    else:
        for key,value in result.items():print(key+': '+json.dumps(value))
