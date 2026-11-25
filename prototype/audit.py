# SPDX-License-Identifier: Apache-2.0
"""Self-run local audit; heuristics; not proof. CLI only, no network."""
import argparse
from contextlib import redirect_stdout
import ast
from collections import Counter
from dataclasses import dataclass,field
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
if __package__:
    from .trace import repository,git,commit_data,evaluate_commit,parse_snapshots,patch_id,continuation
    from .trace_sources import sessions,read_config,config_path,still_approved,seconds
    from .trace_queries import since_arg
    from .trace_mcp import safe_text
    from .privacy import redact
    from .audit_rules import events,categories,SEVERITY,DESCRIPTIONS,INJECTION,MODIFY,DEPENDENCY,TEST_BUILD,PUBLISH,sensitive_area,executes_download,command_text,rules,modifications,default_scratch,tests_before_commit
else:
    from trace import repository,git,commit_data,evaluate_commit,parse_snapshots,patch_id,continuation
    from trace_sources import sessions,read_config,config_path,still_approved,seconds
    from trace_queries import since_arg
    from trace_mcp import safe_text
    from privacy import redact
    from audit_rules import events,categories,SEVERITY,DESCRIPTIONS,INJECTION,MODIFY,DEPENDENCY,TEST_BUILD,PUBLISH,sensitive_area,executes_download,command_text,rules,modifications,default_scratch,tests_before_commit

NOTICE='self-run local audit; heuristics; not proof'
DEFAULT_IGNORES=['package-lock.json','yarn.lock','pnpm-lock.yaml','poetry.lock','uv.lock','Cargo.lock','*.min.*','build/**','dist/**','*.egg-info/**']
CONTROL_DESCRIPTIONS={'missing_origin':'No substantive originating user request was found in the selected evidence.',
    'no_tests_build':'No recorded test or build run was found after the last recorded modification and before the commit.',
    'autonomous_commit':'No user turn was recorded after the last modification and before the commit.',
    'pushed_published':'A push, tag or publish action was recorded for this work.',
    'sensitive_area':'AI-linked changes touch a sensitive configuration, security-named or dependency area.',
    'partly_explained':'Some non-ignored added lines or files have no covering edit or plausible modifying command.',
    'recorded_but_missing':'A successful recorded commit is absent from reachable history; a rewrite or drop is possible.'}

@dataclass
class AuditRun:
    report:dict
    snapshots:list
    config:Path
    settings:dict
    details:dict=field(default_factory=dict)


def policy(config):
    data=read_config(config);a=data.get('audit',{});t=data.get('trace',{})
    if not isinstance(a,dict) or not isinstance(t,dict):raise ValueError('Invalid audit settings')
    terms=t.get('sensitive_terms',[]);ignore=a.get('ignore_globs',DEFAULT_IGNORES)
    if not isinstance(terms,list) or any(not isinstance(v,str) or not v for v in terms):raise ValueError('Invalid sensitive terms')
    if not isinstance(ignore,list) or any(not isinstance(v,str) or not v or Path(v).is_absolute() for v in ignore):raise ValueError('Ignore globs must be relative patterns')
    scratch=a.get('scratch_dirs',default_scratch())
    if not isinstance(scratch,list) or any(not isinstance(v,str) or not Path(v).expanduser().is_absolute() for v in scratch):raise ValueError('Scratch directories must be absolute paths')
    return {'audit':a,'trace':t,'terms':terms,'ignore':ignore,'scratch':scratch}


def decode_path(value):
    if value.startswith('"'):
        try:value=ast.literal_eval(value)
        except (ValueError,SyntaxError):raise ValueError('Unrecognized diff path')
    return value[2:] if value.startswith(('a/','b/')) else value


def changes(repo,oid):
    parents=git(repo,'show','-s','--format=%P',oid).split()
    base=['diff',parents[0],oid] if parents else ['show','--format=',oid]
    options=['--no-ext-diff','--no-textconv','--no-renames']
    counts=git(repo,*base,*options,'--numstat','-z')
    result={}
    for record in counts.split('\0'):
        parts=record.split('\t',2)
        if len(parts)==3:result[parts[2]]={'added':Counter(),'removed':Counter(),'binary':parts[0]=='-','added_total':int(parts[0]) if parts[0].isdigit() else 0}
    patch=git(repo,'-c','core.quotePath=false',*base,*options,'--unified=0')
    path=None;old=None;hunk=False
    for line in patch.splitlines():
        if line.startswith('diff --git '):path=None;old=None;hunk=False
        elif line.startswith('--- '):old=decode_path(line[4:]);hunk=False
        elif line.startswith('+++ '):path=old if line[4:]=='/dev/null' else decode_path(line[4:]);hunk=False
        elif line.startswith('@@ '):hunk=True
        elif hunk and path in result:
            if line.startswith('+'):result[path]['added'][line[1:]]+=1
            elif line.startswith('-'):result[path]['removed'][line[1:]]+=1
    return result


def checked(run):
    if policy(run.config)!=run.settings or any(not still_approved(run.config,s,allow_append=True) for s in run.snapshots):
        raise ValueError('Audit settings, approval or transcript snapshot changed; no report returned')


def run_audit(repo,config,since=None,range_=None,ignore_extra=()):
    if since is not None and range_ is not None:raise ValueError('Use since or range, not both')
    repo=repository(repo);config=Path(config);settings=policy(config)
    ignore=list(dict.fromkeys([*settings['ignore'],*ignore_extra]))
    if any(not isinstance(v,str) or not v or Path(v).is_absolute() for v in ignore):raise ValueError('Ignore globs must be relative patterns')
    terms=settings['terms'];approved=sessions(config);parsed,parse_counts=parse_snapshots(approved,repo)
    if range_ is not None:
        if not isinstance(range_,str) or range_.startswith('-') or '..' not in range_:raise ValueError('Use a git range')
        ids=git(repo,'rev-list','--reverse','--end-of-options',range_).splitlines();cutoff=None
    else:
        date=since_arg(since or '30d');ids=git(repo,'rev-list','--reverse','--since='+date,'HEAD').splitlines()
        value=git(repo,'rev-parse','--since='+date).strip();cutoff=int(value.split('=',1)[1])
    if len(ids)>1000 or any(not re.fullmatch(r'[a-f0-9]{40,64}',oid) for oid in ids):raise ValueError('Select at most 1000 commits')
    commits={oid:commit_data(repo,oid) for oid in ids};rows={oid:evaluate_commit(repo,commits[oid],parsed,max(1,len(parsed))) for oid in ids}
    used={};detail_map={};findings=[];dedup=set();reconciliation=[];reverse=[]
    def add(category,severity,session,turn,commit=None,extra=None,detail=None,rule=None):
        reference=session.reference(turn.number);rule=rule or category;key=(category,rule,commit,reference['reference'],(extra or {}).get('recorded_commit'))
        if key in dedup:return
        dedup.add(key);used[session.path]=session
        identity=hashlib.sha256(json.dumps(key).encode()).hexdigest()[:16]
        group='notable_actions' if category in SEVERITY else 'reconciliation' if category in ('partly_explained','recorded_but_missing') else 'missing_controls'
        finding={'id':identity,'report':group,'rule':rule,'category':category,'severity':severity,'session_id':session.short_id,**reference,'time':turn.timestamp,
            'description':DESCRIPTIONS.get(category,CONTROL_DESCRIPTIONS.get(category,'Recorded audit observation.'))}
        if commit:finding['commit']=commit
        if extra:finding.update(extra)
        findings.append(finding)
        numbers=[turn.number]+[t.number for t in session.turns if turn.kind=='tool_call' and t.kind=='tool_output' and turn.call_id and t.call_id==turn.call_id]
        if extra and extra.get('preceding_output'):numbers.append(extra['preceding_output']['turn'])
        detail_map[identity]=(session,numbers,detail)
    windows={}
    for row in rows.values():
        for m in row['matches']:
            key=m['_session'].path;windows.setdefault(key,set()).update(m['segment']['turns'])
    times=[v['time'] for v in commits.values()];lower=min(times) if times else None;upper=max(times) if times else None
    if ids and range_ is not None:
        parents=git(repo,'show','-s','--format=%P',ids[0]).split()
        if parents:lower=min(lower,int(git(repo,'show','-s','--format=%ct',parents[0]).strip()))
    all_events={};scope_events={};untimed=0
    for session,action_list in parsed:
        ev=events(session,repo);all_events[session.path]=ev;scoped=[]
        for e in ev:
            when=seconds(e['turn'].timestamp)
            include=(when is None or when>=cutoff) if cutoff is not None else (e['turn'].number in windows.get(session.path,set()) or when is not None and lower is not None and lower<=when<=upper)
            if include:
                scoped.append(e)
                if when is None:untimed+=1
        scope_events[session.path]=scoped
        if scoped:used[session.path]=session
        recent_secrets=[];recent_outputs=[];downloads=[]
        order={n:i for i,n in enumerate(sorted({t.number for t in session.turns}))}
        for e in scoped:
            t=e['turn'];hits=rules(e,repo,settings['scratch'])
            if any(0<order[t.number]-order[n]<=20 and executes_download(e,target) for n,target in downloads) and not any(h['category']=='remote_code' for h in hits):hits.append({'category':'remote_code','rule':'download_file','severity':'high'})
            downloads.extend((t.number,target) for target in e['downloads'])
            for hit in hits:
                category=hit['category'];severity=hit['severity']
                if category=='network' and any(0<order[t.number]-order[n]<=20 for n in recent_secrets):severity='high'
                add(category,severity,session,t,extra={'sequence_escalated':True} if category=='network' and severity=='high' else None,rule=hit['rule'])
                if category=='secrets' and severity=='high':recent_secrets.append(t.number)
            if any(h['severity'] in ('high','medium') for h in hits) and any(0<order[t.number]-order[n]<=10 for n in recent_outputs):
                prior=max(n for n in recent_outputs if 0<order[t.number]-order[n]<=10)
                add('possible_injection_chain','high',session,t,extra={'heuristic':True,'preceding_output':session.reference(prior)})
            if e['output'] and INJECTION.search(e['output'].text):recent_outputs.append(e['output'].number)
        # Tool outputs not attached to a scoped command cannot establish a chain.
    parsed_map={s.path:a for s,a in parsed}
    ignored_files=0;ignored_lines=0
    for oid in ids:
        diff=changes(repo,oid);row=rows[oid];m=row['matches'][0] if row['matches'] else None
        ignored={p for p in diff if any(fnmatch.fnmatchcase(p,g) or fnmatch.fnmatchcase(Path(p).name,g) for g in ignore)}
        active={p:v for p,v in diff.items() if p not in ignored};total=sum(v['added_total'] for v in active.values())
        ignored_files+=len(ignored);ignored_lines+=sum(diff[p]['added_total'] for p in ignored)
        entry={'commit':oid,'classification':'no_ai_record','added_lines':total,'changed_files':len(active),'ignored_files':len(ignored),'ignored_added_lines':sum(diff[p]['added_total'] for p in ignored)}
        if m:
            contributors=[];cover={};modified=[];all_edits=[];tests_seen=False;user_seen=False;origin_seen=False
            for candidate in row['matches']:
                session=candidate['_session'];used[session.path]=session;seg=candidate['segment'];actions=parsed_map[session.path]
                anchors=[e['turn'] for e in candidate['evidence'] if e['type'] in ('commit_command','patch_identity','recorded_patch_identity')]
                anchor=max(anchors) if anchors else seg['end_turn'];by_number={t.number:t for t in session.turns};turn=by_number[anchor]
                previous=max([a.turn for a in actions if a.kind=='commit' and a.turn<anchor]+[0])
                relevant=set(seg['turns'])|{r['turn'] for r in seg['edit_turns']}
                if not seg['origin_found']:relevant.update(a.turn for a in actions if previous<a.turn<=anchor)
                local=[a for a in actions if previous<a.turn<=anchor and a.turn in relevant]
                edits=[a for a in local if a.kind=='edit' and a.path in active];all_edits.extend(edits)
                for a in edits:cover[a.path]=cover.get(a.path,Counter())|a.added_counts
                modifying=[]
                for e in all_events.get(session.path,[]):
                    if not(previous<e['turn'].number<=anchor and e['turn'].number in relevant and e['in_repo']):continue
                    targets=modifications(e)
                    if targets is None or targets:
                        modifying.append(e);modified.append(targets)
                roles=[]
                if edits or modifying:roles.append('author')
                if any(a.kind=='commit' and a.turn==anchor for a in local):roles.append('committer')
                contributors.append({'session_id':session.short_id,'roles':roles,'confidence':candidate['confidence']})
                origin_seen|=bool(seg.get('origin_turns'))
                last_edit=max([a.turn for a in edits]+[e['turn'].number for e in modifying]+[seg['start_turn']-1])
                tests_seen|=any(e['in_repo'] and ((last_edit<e['turn'].number<anchor and TEST_BUILD.search(e['command'])) or e['turn'].number==anchor and tests_before_commit(e['command'])) for e in all_events.get(session.path,[]))
                user_seen|=any(t.kind=='user' and last_edit<t.number<anchor and t.number in seg['turns'] for t in session.turns)
                next_boundary=min([t.number for t in session.turns if t.number>anchor and t.kind=='user' and not continuation(t.text)]+[a.turn for a in actions if a.kind=='commit' and a.turn>anchor]+[float('inf')])
                for e in all_events.get(session.path,[]):
                    if previous<e['turn'].number<next_boundary and (e['turn'].number in relevant or e['turn'].number>anchor) and PUBLISH.search(e['command']):add('pushed_published','medium',session,e['turn'],oid)
            # All approved trace-linked candidates contribute; roles describe
            # recorded edit/commit evidence, not trusted git author identities.
            primary=m['_session'];primary_seg=m['segment']
            anchors=[e['turn'] for e in m['evidence'] if e['type'] in ('commit_command','patch_identity','recorded_patch_identity')]
            anchor=max(anchors) if anchors else primary_seg['end_turn'];turn=next(t for t in primary.turns if t.number==anchor)
            verified=0;command_lines=0;missing=0;missing_paths=[];command_paths=[]
            for path,values in active.items():
                covered=sum((values['added']&cover.get(path,Counter())).values());verified+=covered;rest=values['added_total']-covered
                unknown=(rest>0 or values['binary'] or not values['added_total'] and path not in cover)
                if unknown:
                    if any(targets is None or str(repo/path) in targets for targets in modified):command_lines+=rest;command_paths.append(path)
                    else:missing+=rest;missing_paths.append(path)
            commit_only=not all_edits and not command_paths and any('committer' in c['roles'] for c in contributors)
            classification='commit_only' if commit_only else 'partly_explained' if missing_paths else 'command_modified' if command_paths else 'explained'
            entry.update({'classification':classification,'session_id':primary.short_id,'contributors':contributors,'roles':sorted({role for c in contributors for role in c['roles']}),
                'confidence':m['confidence'],'verified_added_lines':verified,'command_modified_added_lines':command_lines,
                'command_modified_files':len(command_paths),'unaccounted_added_lines':missing,'unaccounted_added_percent':100*missing/total if total else 0,
                'unaccounted_files':len(missing_paths),'unaccounted_file_percent':100*len(missing_paths)/len(active) if active else 0,'ignored_only':not bool(active)})
            if missing_paths and not commit_only:add('partly_explained','medium',primary,turn,oid,detail={'unaccounted_files':missing_paths})
            if not origin_seen:add('missing_origin','medium',primary,turn,oid)
            if not tests_seen:add('no_tests_build','medium',primary,turn,oid)
            if not user_seen:add('autonomous_commit','low',primary,turn,oid)
            if any(sensitive_area(p) for p in active):add('sensitive_area','medium',primary,turn,oid,detail={'sensitive_files':[p for p in active if sensitive_area(p)]})
        reconciliation.append(entry)
    # Successful recorded commits absent from *all* reachable refs, not merely
    # absent from the selected range. Subjects are internal, never exported.
    reachable=git(repo,'rev-list','--all').splitlines();subjects={};reachable_set=set(reachable);patches=None
    for record in git(repo,'log','--all','--format=%H%x00%s').splitlines():
        if '\0' not in record:continue
        oid,title=record.split('\0',1);subjects.setdefault(' '.join(title.casefold().split()),[]).append(oid)
    recorded_seen=set()
    for session,action_list in parsed:
        allowed={e['turn'].number for e in scope_events.get(session.path,[])}
        for action in action_list:
            if action.kind!='commit' or action.turn not in allowed or action.output_turn is None:continue
            # A commit hash line confirms the commit record even if a later
            # command in the same tool call failed (e.g. a push).
            if not action.observed_hash and re.search(r'(?im)^\s*(?:fatal:|error:)|nothing to commit|(?:exit code|exited with code) [1-9]',action.output):continue
            if not action.subject and not action.observed_hash:continue
            present=any(oid.startswith(action.observed_hash) for oid in reachable_set) if action.observed_hash else action.subject in subjects
            if present:continue
            record_key=(str(session.path),action.observed_hash)
            if action.observed_hash and record_key in recorded_seen:continue
            if action.observed_hash:recorded_seen.add(record_key)
            rewrite=[];old_patch=None
            if action.observed_hash:
                old=git(repo,'show','--format=','--no-ext-diff','--no-textconv',action.observed_hash,check=False);old_patch=patch_id(repo,old) if old else None
            if not old_patch:
                previous=max([a.turn for a in action_list if a.kind=='commit' and a.turn<action.turn]+[0])
                prior=[a for a in action_list if a.kind=='diff' and previous<a.turn<action.turn and not any(t.kind=='user' and a.turn<t.number<action.turn and not continuation(t.text) for t in session.turns)]
                if prior:old_patch=patch_id(repo,prior[-1].output)
            if old_patch:
                if patches is None:patches={oid:commit_data(repo,oid)['patch_id'] for oid in reachable}
                rewrite=[oid for oid in reachable if patches[oid]==old_patch]
            turn=next(t for t in session.turns if t.number==action.turn)
            add('recorded_but_missing','medium',session,turn,extra={'recorded_commit':action.observed_hash,'patch_id':old_patch,'patch_id_matches':rewrite,'rewritten':bool(rewrite)})
            reverse.append({'session_id':session.short_id,**session.reference(turn.number),'recorded_commit':action.observed_hash,'patch_id':old_patch,'patch_id_matches':rewrite,'rewritten':bool(rewrite)})
    raw_findings=findings
    findings,detail_map=group_findings(raw_findings,detail_map)
    counts=Counter(e['classification'] for e in reconciliation);severity=Counter(f['severity'] for f in findings);category=Counter(f['category'] for f in findings)
    groups={}
    for name in ('reconciliation','notable_actions','missing_controls'):
        selected=[f for f in findings if f['report']==name]
        groups[name]={'findings':len(selected),'raw_findings':sum(f['occurrences'] for f in selected),'by_category':dict(sorted(Counter(f['category'] for f in selected).items()))}
    output={'notice':NOTICE,'rule_version':2,'ignore_globs':[safe_text(g,terms) for g in ignore],
        'summary':{'commits':len(ids),'reconciliation':dict(sorted(counts.items())),'recorded_but_missing':len(reverse),'ignored_files':ignored_files,'ignored_added_lines':ignored_lines,
            'findings':len(findings),'raw_findings':len(raw_findings),'grouped_findings':len(findings),'scratch_writes':sum(f['category']=='scratch_write' for f in raw_findings),'scratch_cleanups':sum(f['category']=='scratch_cleanup' for f in raw_findings),'raw_by_category':dict(sorted(Counter(f['category'] for f in raw_findings).items())),'raw_by_severity':dict(sorted(Counter(f['severity'] for f in raw_findings).items())),'reports':groups,'by_category':dict(sorted(category.items())),'by_severity':dict(sorted(severity.items())),'untimed_actions_included':untimed,
            'parser_failures':sum(c['parse_failures'] for c in parse_counts)},
        'reconciliation':reconciliation,'recorded_but_missing':reverse,'findings':findings}
    run=AuditRun(output,list(used.values()),config,settings,detail_map);checked(run);return run


LEVEL={'info':0,'low':1,'medium':2,'high':3}

def group_findings(findings,detail_map):
    groups={};merged={}
    for f in findings:
        session,numbers,extra=detail_map[f['id']]
        prior=[t.number for t in session.turns if t.kind=='user' and t.number<=f['turn'] and not continuation(t.text)]
        block=prior[-1] if prior else 0
        # Agent memory/settings are intentionally once per session/path class.
        if f['rule'] in ('agent_claude','agent_codex'):block=0
        key=(session.provider,session.identity,f['category'],f['rule'],block)
        if key not in groups:
            value={**f,'occurrences':0,'first_turn':f['turn'],'last_turn':f['turn'],'first_reference':f['reference'],'last_reference':f['reference'],'first_time':f['time'],'last_time':f['time'],'commits':[]}
            if f['category']=='recorded_but_missing':value.update({'recorded_commits':[],'rewritten_occurrences':0})
            groups[key]=value;merged[value['id']]=[]
        value=groups[key];value['occurrences']+=1
        if LEVEL[f['severity']]>LEVEL[value['severity']]:value['severity']=f['severity']
        if f['turn']<value['first_turn']:value.update(first_turn=f['turn'],first_reference=f['reference'],first_time=f['time'])
        if f['turn']>=value['last_turn']:value.update(last_turn=f['turn'],last_reference=f['reference'],last_time=f['time'])
        if f.get('commit') and f['commit'] not in value['commits']:value['commits'].append(f['commit'])
        if f['category']=='recorded_but_missing':
            if f.get('recorded_commit'):value['recorded_commits'].append(f['recorded_commit'])
            value['rewritten_occurrences']+=int(f.get('rewritten',False));value['rewritten']=value['rewritten_occurrences']>0
            value['patch_id_matches']=sorted(set(value['patch_id_matches'])|set(f['patch_id_matches']))
        merged[value['id']].append((session,numbers,extra))
    for value in groups.values():value.update(turn=value['first_turn'],reference=value['first_reference'],time=value['first_time'])
    return list(groups.values()),merged


def printed(report,min_severity='medium'):
    result={**report,'findings':[f for f in report['findings'] if LEVEL[f['severity']]>=LEVEL[min_severity]],'min_severity':min_severity}
    return result


def details(run,confirm=input,interactive=True):
    if not interactive:raise ValueError('--show-details requires an interactive terminal')
    terms=run.settings['terms'];allowed=set()
    for session in run.snapshots:
        try:answer=confirm('Show redacted audit details for '+session.provider+' session '+session.short_id+'? [y/N] ')
        except (EOFError,KeyboardInterrupt):break
        if answer.strip().casefold() in ('y','yes'):allowed.add(session.path)
    checked(run)
    def safe(value):
        if any(term.casefold() in value.casefold() for term in terms):return '[turn withheld: sensitive term]'
        return re.sub(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b','[REDACTED EMAIL]',redact(value),flags=re.I)
    for finding in run.report['findings']:
        turns=[];path_details={};seen=set()
        for session,numbers,extra in run.details[finding['id']]:
            if session.path not in allowed:continue
            selected=set(numbers)
            for t in session.turns:
                reference=session.reference(t.number)
                if t.number in selected and reference['reference'] not in seen:
                    raw=t.text if t.kind!='tool_call' else json.dumps({'tool':t.tool,'arguments':t.arguments},ensure_ascii=False)
                    turns.append({**reference,'text':safe(raw)});seen.add(reference['reference'])
            if extra:
                for key,paths in extra.items():path_details.setdefault(key,[]).extend(safe(p) for p in paths)
        if turns or path_details:
            finding['details']={'turns':turns}
            if path_details:finding['details']['paths']={key:list(dict.fromkeys(values)) for key,values in path_details.items()}
    checked(run)


def text_report(report):
    summary=report['summary'];lines=[NOTICE,
        'Commits: '+str(summary['commits'])+' | reconciliation: '+json.dumps(summary['reconciliation']),
        'Findings: '+str(summary['raw_findings'])+' raw / '+str(summary['grouped_findings'])+' grouped | severity: '+json.dumps(summary['by_severity']),
        'Scratch: '+str(summary['scratch_writes'])+' writes, '+str(summary['scratch_cleanups'])+' cleanups (info)',
        'Ignored: '+str(summary['ignored_files'])+' files / '+str(summary['ignored_added_lines'])+' added lines',
        'Ignore globs: '+json.dumps(report['ignore_globs']),
        'Grouped findings ('+report.get('min_severity','all')+' and above):']
    for f in report['findings']:
        lines.append(f['severity']+' '+f['category']+' / '+f['rule']+' / '+f['session_id']+' x'+str(f['occurrences'])+' / '+f['first_reference']+' .. '+f['last_reference'])
        if f['category']=='recorded_but_missing':lines.append('  Recorded hash: '+(f.get('recorded_commit') or 'subject-only record')+'; rewritten: '+str(f.get('rewritten_occurrences',0))+'/'+str(f['occurrences']))
        if 'details' in f:lines.append(json.dumps(f['details']))
    return '\n'.join(lines)


def markdown(report):
    lines=['# Local agent audit','',NOTICE,'','## Counts','',json.dumps(report['summary'],sort_keys=True),'','## Grouped findings','']
    for f in report['findings']:
        lines.append('- '+f['category']+' / '+f['severity']+' / '+f['rule']+' / '+f['session_id']+' / occurrences '+str(f['occurrences'])+' / '+f['first_reference']+' .. '+f['last_reference'])
        if f['category']=='recorded_but_missing':lines.append('  Patch-ID matches: '+json.dumps(f['patch_id_matches']))
        if 'details' in f:lines.extend(['','```json',json.dumps(f['details'],indent=2).replace('`','\\u0060'),'```'])
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',nargs='?',choices=['verify']);parser.add_argument('--repo',type=Path,default=Path.cwd())
    scope=parser.add_mutually_exclusive_group();scope.add_argument('--since');scope.add_argument('--range',dest='range_')
    parser.add_argument('--profile');parser.add_argument('--directory',type=Path);parser.add_argument('--ignore',action='append',default=[])
    formats=parser.add_mutually_exclusive_group();formats.add_argument('--json',action='store_true');formats.add_argument('--markdown',action='store_true')
    parser.add_argument('--min-severity',choices=list(LEVEL),default='medium');parser.add_argument('--show-details',action='store_true');parser.add_argument('--fail-on',choices=['high','medium']);parser.add_argument('--seal',action='store_true')
    args=parser.parse_args()
    if args.show_details and not sys.stdin.isatty():parser.error('--show-details requires an interactive terminal')
    try:
        config=config_path(args.directory,args.profile)
        if args.action=='verify':
            if args.seal or args.show_details:raise ValueError('verify cannot seal or reveal details')
            if __package__:from .audit_ledger import verify
            else:from audit_ledger import verify
            result=verify(config);print(json.dumps(result,indent=2));return 0 if result['ok'] else 1
        run=run_audit(args.repo,config,args.since,args.range_,args.ignore)
        if args.seal:
            if __package__:from .audit_ledger import seal
            else:from audit_ledger import seal
            run.report['seal']=seal(run,repository(args.repo))
        if args.show_details:
            with redirect_stdout(sys.stderr if args.json else sys.stdout):details(run)
        view=printed(run.report,args.min_severity)
        print(json.dumps(view,indent=2) if args.json else markdown(view) if args.markdown else text_report(view))
        severities=run.report['summary']['by_severity']
        return 1 if args.fail_on and (severities.get('high',0) or args.fail_on=='medium' and severities.get('medium',0)) else 0
    except (ValueError,OSError,KeyError,TypeError,AttributeError,subprocess.SubprocessError):
        print('Audit could not complete safely; check local repository, profile and ledger settings.',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
