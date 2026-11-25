# SPDX-License-Identifier: Apache-2.0
"""Experimental, read-only commit-to-approved-turn evidence. No network."""
import argparse
import copy
from contextlib import redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
if __package__:
    from .trace_sources import sessions,config_path,still_approved,seconds
    from .trace_actions import actions,lines,subject,commands
    from .privacy import redact
else:
    from trace_sources import sessions,config_path,still_approved,seconds
    from trace_actions import actions,lines,subject,commands
    from privacy import redact


def git(repo,*args,input=None,check=True):
    env={**os.environ,'GIT_ALLOW_PROTOCOL':'','GIT_NO_LAZY_FETCH':'1','GIT_OPTIONAL_LOCKS':'0','GIT_TERMINAL_PROMPT':'0','GIT_PAGER':'cat'}
    # External git environment must not redirect this read into another repo.
    for name in ('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES','GIT_CONFIG_PARAMETERS','GIT_CONFIG_COUNT'):env.pop(name,None)
    result=subprocess.run(['git','--no-pager','-c','core.fsmonitor=false','-c','color.ui=false','-C',str(repo),*args],input=input,text=True,capture_output=True,env=env,timeout=30)
    if check and result.returncode:raise ValueError('Git reference/repository could not be read; no changes made')
    return result.stdout if result.returncode==0 else ''


def repository(path):
    root=git(Path(path).expanduser().resolve(),'rev-parse','--show-toplevel').strip()
    if not root:raise ValueError('An existing working-tree repository is required')
    partial=git(Path(root),'config','--get-regexp',r'^(extensions\.partialclone|remote\..*\.promisor)$',check=False)
    if any(line.rsplit(None,1)[-1].casefold() not in ('false','no','0') for line in partial.splitlines()):raise ValueError('Partial/promisor repositories are not traced; hydrate locally outside trace first')
    return Path(root).resolve()


def commit_ids(repo,revision,limit=1000):
    if not isinstance(revision,str) or revision.startswith('-') or not revision.strip():raise ValueError('Use a commit-ish or git revision range')
    if revision.endswith(('^!','^-')):revision=revision[:-2]
    if '..' in revision:
        ids=git(repo,'rev-list','--reverse','--max-count='+str(limit+1),'--end-of-options',revision).splitlines()
    else:
        value=git(repo,'rev-parse','--verify','--end-of-options',revision+'^{commit}').strip();ids=[value]
    if len(ids)>limit:raise ValueError('Range exceeds 1000 commits; select a narrower range')
    if any(not re.fullmatch(r'[a-f0-9]{40,64}',v) for v in ids):raise ValueError('Invalid commit resolution')
    return ids


def patch_id(repo,diff):
    if 'diff --git ' not in diff:return None
    output=git(repo,'patch-id','--stable',input=diff[diff.index('diff --git '):],check=False)
    match=re.search(r'^([a-f0-9]{40,64})\b',output)
    return match.group(1) if match else None


def commit_data(repo,oid):
    metadata=git(repo,'show','-s','--format=%H%x00%ct%x00%s',oid).strip().split('\x00',2)
    diff=git(repo,'show','--format=','--no-ext-diff','--no-textconv','--no-renames','--unified=3',oid)
    added={};removed={};path=None
    for line in diff.splitlines():
        if line.startswith('+++ b/'):path=line[6:];added.setdefault(path,set())
        elif line.startswith('--- a/'):removed.setdefault(line[6:],set())
        elif line.startswith('+') and not line.startswith('+++') and path:added[path].update(lines(line[1:]))
    path=None
    for line in diff.splitlines():
        if line.startswith('--- a/'):path=line[6:]
        elif line.startswith('-') and not line.startswith('---') and path:removed[path].update(lines(line[1:]))
    return {'oid':metadata[0],'time':int(metadata[1]),'subject':subject(metadata[2]),'diff':diff,'patch_id':patch_id(repo,diff),'added':added,'removed':removed}


def informative(values):
    boring={'return','true','false','none','self','import','from','def','class','pass','else','if'}
    result=set()
    for value in values:
        words=set(re.findall(r'[a-zA-Z_][a-zA-Z_0-9]*|\b[0-9]+\b',value.casefold()))-boring
        if len(value)>=12 and words and (len(words)>=2 or len(value)>=24):result.add(value)
    return result


def continuation(text):
    # Only a small, explicit vocabulary of approvals; task-bearing short prompts
    # (e.g. "fix TLS validation") remain substantive boundaries.
    if len(text.split())>=12:return False
    return bool(re.fullmatch(r"\s*(?:yes(?: to both)?|ok(?:ay)?|continue|proceed|do it|still going|go ahead|approve|commit(?: (?:it|this|the changes))?(?: and push)?|run (?:the )?tests(?: and commit)?|fix (?:it|that)|thanks)[.!]?\s*",text,re.I))


def segment(session,edits,anchor,all_actions):
    # Substantive user turns define independent work blocks; generic follow-ups
    # stay in that block. A commit does not reset the originating request.
    starts=[];origin_for={};current=None
    for turn in session.turns:
        if turn.kind=='user' and (current is None or not continuation(turn.text)):
            current=turn.number;starts.append(current)
        origin_for[turn.number]=current
    targets={origin_for.get(e.turn) for e in edits} if edits else {origin_for.get(anchor.turn)}
    targets.discard(None)
    chosen=set();request_turns=set()
    for turn in session.turns:
        if turn.number>anchor.turn:continue
        if origin_for.get(turn.number) in targets:
            chosen.add(turn.number)
            if turn.kind=='user':request_turns.add(turn.number)
    chosen.add(anchor.turn)
    if anchor.output_turn:chosen.add(anchor.output_turn)
    # A later generic commit prompt can be included without pulling the
    # intervening unrelated substantive request or its answer into the segment.
    prior=[t for t in session.turns if t.kind=='user' and t.number<=anchor.turn]
    if prior and continuation(prior[-1].text):chosen.add(prior[-1].number);request_turns.add(prior[-1].number)
    evidence=[]
    by_id={t.call_id:t for t in session.turns if t.kind=='tool_call' and t.call_id}
    for turn in session.turns:
        if turn.number not in chosen or turn.kind!='tool_output':continue
        call=by_id.get(turn.call_id)
        command=json.dumps(call.arguments) if call else ''
        kind='tool_output'
        if re.search(r'\b(?:pytest|unittest|npm test|cargo test)\b',command) and re.search(r'FAILED|Traceback|AssertionError|exit code [1-9]',turn.text):kind='test_failure'
        elif re.search(r'gh\s+(?:run|pr)\b|--log|\bCI\b',command):kind='ci_log'
        evidence.append({**session.reference(turn.number),'type':kind})
    numbers=sorted(chosen)
    return {'origin_found':any(t.kind=='user' and t.number in request_turns and not continuation(t.text) for t in session.turns),'start_turn':numbers[0],'end_turn':numbers[-1],'turns':numbers,'request_turns':[session.reference(n) for n in sorted(request_turns)],
        'origin_turns':[session.reference(n) for n in sorted(request_turns) if not continuation(next(t.text for t in session.turns if t.number==n))],
        'go_ahead_turns':[session.reference(n) for n in sorted(request_turns) if continuation(next(t.text for t in session.turns if t.number==n))],
        'edit_turns':[session.reference(n) for n in sorted({e.turn for e in edits})],'tool_evidence':evidence,'selection':'Request blocks containing relevant edits plus commit references; intervening unrelated request blocks excluded.'}


def match(repo,commit,session,action_list,cache=None):
    cache={} if cache is None else cache
    candidates=[];edit_matches=[];total=sum(len(informative(v)) for v in commit['added'].values())
    for action in action_list:
        when=seconds(action.timestamp)
        if action.kind=='edit' and when is not None and when<=commit['time']:
            overlap=informative(action.added)&informative(commit['added'].get(action.path,set()))
            deletion=informative(action.removed)&informative(commit['removed'].get(action.path,set()))
            if overlap or deletion:edit_matches.append((action,len(overlap),len(deletion)))
    for action in action_list:
        if action.kind!='commit':continue
        evidence=[];score=0
        failed=not action.observed_hash and bool(re.search(r'(?m)^\s*(?:fatal:|error:)|nothing to commit|(?:exit code|exited with code) [1-9]',action.output,re.I))
        if action.subject and action.subject==commit['subject'] and not failed:
            score=((78 if not action.observed_hash else 82) if action.output_turn is not None else 65) if len(action.subject)>=8 and len(action.subject.split())>=2 else 35
            evidence.append({'type':'commit_command','turn':action.turn,'subject_matched':True,'tool_result_present':action.output_turn is not None})
        if action.observed_hash:
            key=('object',str(repo),action.observed_hash)
            if key not in cache:
                prior=git(repo,'show','--format=','--no-ext-diff','--no-textconv','--no-renames',action.observed_hash,check=False)
                cache[key]=patch_id(repo,prior) if prior else None
            if commit['patch_id'] and cache[key]==commit['patch_id']:
                score=100;evidence.append({'type':'patch_identity','turn':action.turn,'rewritten_hash':not commit['oid'].startswith(action.observed_hash)})
        # A recorded pre-commit diff can survive even if old git objects expired.
        for diff in action_list:
            if diff.kind=='diff' and diff.turn<action.turn and diff.output and commit['patch_id']:
                key=('diff',str(repo),diff.output)
                if key not in cache:cache[key]=patch_id(repo,diff.output)
                if cache[key]!=commit['patch_id']:continue
                # A recorded diff belongs to the next recorded commit action,
                # independent of the requested range (including amend).
                if any(a.kind=='commit' and diff.turn<a.turn<action.turn for a in action_list):continue
                # Do not borrow a diff from another substantive work block.
                users=[t for t in session.turns if t.kind=='user' and diff.turn<t.number<action.turn and not continuation(t.text)]
                if not users:score=max(score,97);evidence.append({'type':'recorded_patch_identity','turn':diff.turn})
        if score:
            local=[e for e,n,d in edit_matches if e.turn<=action.turn]
            if any(e['type'] in ('patch_identity','recorded_patch_identity') for e in evidence):
                local=[e for e in action_list if e.kind=='edit' and e.turn<=action.turn and ((informative(e.added)&informative(commit['added'].get(e.path,set()))) or (informative(e.removed)&informative(commit['removed'].get(e.path,set()))))]
            overlap=set()
            for e in local:overlap|=informative(e.added)&informative(commit['added'].get(e.path,set()))
            if overlap:
                coverage=len(overlap)/max(1,total)
                score=min(100,score+min(10,int(coverage*10)))
                evidence.append({'type':'added_line_overlap','matched_lines':len(overlap),'commit_added_lines':total,'coverage':round(coverage,4),'turns':sorted({e.turn for e in local})})
            candidates.append((score,action,evidence,local))
    if edit_matches:
        matched=set()
        for e,n,d in edit_matches:matched|=informative(e.added)&informative(commit['added'].get(e.path,set()))
        coverage=len(matched)/max(1,total)
        if matched and coverage>=.35:
            edits=[e for e,n,d in edit_matches if n]
            anchor=copy.copy(max(edits,key=lambda e:e.turn))
            boundary=next((t.number for t in session.turns if t.kind=='user' and t.number>anchor.turn and not continuation(t.text)),float('inf'))
            eligible=[t for t in session.turns if anchor.turn<=t.number<boundary and seconds(t.timestamp) is not None and seconds(t.timestamp)<=commit['time']]
            if eligible:
                tail=max(eligible,key=lambda t:t.number);anchor.turn=tail.number;anchor.timestamp=tail.timestamp
            # Segment includes a later commit command only when that command has
            # matching subject or patch evidence; unrelated later work stays out.
            candidates.append((min(76,50+int(coverage*20)),anchor,[{'type':'added_line_overlap','matched_lines':len(matched),'commit_added_lines':total,'coverage':round(coverage,4),'turns':sorted({e.turn for e in edits})}],edits))
    if not candidates and not total:
        deleted=set()
        for e,n,d in edit_matches:deleted|=informative(e.removed)&informative(commit['removed'].get(e.path,set()))
        if deleted:
            edits=[e for e,n,d in edit_matches if d]
            candidates.append((65,max(edits,key=lambda e:e.turn),[{'type':'removed_line_overlap','matched_lines':len(deleted),'turns':sorted({e.turn for e in edits})}],edits))
    if not candidates:return None
    score,anchor,evidence,edits=max(candidates,key=lambda x:x[0])
    if score<50:return None
    # Time is never a source of links or a substitute for content evidence.
    when=seconds(anchor.timestamp)
    if when is not None:
        score+=max(0,2-abs(commit['time']-when)/86400)
        evidence.append({'type':'time_proximity','weak_tiebreaker':True})
    seg=segment(session,edits,anchor,action_list)
    timestamps=[t.timestamp for t in session.turns if t.number in seg['turns'] and t.timestamp]
    return {'provider':session.provider,'session_id':session.short_id,'time_range':{'start':min(timestamps) if timestamps else None,'end':max(timestamps) if timestamps else None},
        'confidence':'high' if score>=82 else 'medium' if score>=65 else 'low','evidence':evidence,'segment':seg,'_score':score,'_session':session}


def evaluate_commit(repo,commit,parsed,max_results):
    """Evaluate one commit against immutable parsed transcript snapshots.

    No used-action sets or cross-commit cache. Memoized object/diff patch IDs
    are functions of repository plus recorded hash/diff, local to this commit.
    Approval checks belong to the enclosing snapshot transaction, not scoring.
    """
    matches=[];cache={}
    for session,action_list in parsed:
        found=match(repo,commit,session,action_list,cache)
        if found:matches.append(found)
    matches.sort(key=lambda m:(-m['_score'],m['session_id']))
    if len(matches)>1 and abs(matches[0]['_score']-matches[1]['_score'])<3:
        for value in matches[:2]:value['confidence']='medium';value['ambiguous']=True
    return {'commit':commit['oid'],'confidence':matches[0]['confidence'] if matches else 'none',
        'status':'candidate AI evidence found' if matches else 'no AI session found','matches':matches[:max_results]}


def parse_snapshots(approved,repo):
    parsed=[];counts=[]
    for session in approved:
        action_list=[];parse_failed=False
        try:action_list=actions(session,repo);parsed.append((session,action_list))
        except (ValueError,TypeError,KeyError,AttributeError):parse_failed=True
        calls=[t for t in session.turns if t.kind=='tool_call']
        counts.append({'provider':session.provider,'session_id':session.short_id,'tool_calls':len(calls),
            'commands':sum(bool(commands(t.tool,t.arguments)) for t in calls),
            'commits':sum(a.kind=='commit' for a in action_list),'edits':sum(a.kind=='edit' for a in action_list),'parse_failures':int(parse_failed)})
    return parsed,counts


def trace_commits(repo,revision,config,max_results=3,coverage=None,coverage_differences=None,resolved_ids=None):
    if not 1<=max_results<=20:raise ValueError('--max-results must be 1–20 per commit')
    repo=repository(repo);approved=sessions(config)
    parsed,counts=parse_snapshots(approved,repo)
    result=[];differences=[]
    ids=commit_ids(repo,revision) if resolved_ids is None else list(resolved_ids)
    if len(ids)>1000 or any(not isinstance(oid,str) or not re.fullmatch(r'[a-f0-9]{40,64}',oid) for oid in ids):raise ValueError('Invalid resolved commit batch')
    for oid in ids:
        row=evaluate_commit(repo,commit_data(repo,oid),parsed,max_results)
        result.append(row)
        if coverage is not None or coverage_differences is not None:
            # Cold single-commit evaluation: independently parse the same fixed
            # input snapshots, reload the commit, and use a fresh patch-ID cache.
            single_parsed,_=parse_snapshots(approved,repo)
            single=evaluate_commit(repo,commit_data(repo,oid),single_parsed,max_results)
            if public_results([row])!=public_results([single]):differences.append(oid)
    # A live transcript may append complete new turns; those turns are outside
    # this invocation's snapshot. Changed old bytes, deletion or revoked approval
    # invalidate the entire result, rather than silently dropping later links.
    if any(not still_approved(config,session,allow_append=True) for session in approved):
        raise ValueError('Approval or transcript snapshot changed; no results returned. Run trace again.')
    if coverage is not None:coverage.extend(counts)
    if coverage_differences is not None:coverage_differences.extend(differences)
    return result


def public_results(results):
    return [{k:([{key:val for key,val in m.items() if not key.startswith('_')} for m in v] if k=='matches' else v) for k,v in r.items()} for r in results]


def sensitive(text,terms):
    if redact(text)!=text:return True
    if re.search(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',text,re.I):return True
    return any(term.casefold() in text.casefold() for term in terms if term.strip())


def reveal(results,config,terms,confirm=input,interactive=True):
    if not interactive:raise ValueError('--show-text requires an interactive terminal; no text shown')
    for row in results:
        for match in row['matches']:
            session=match['_session'];numbers=set(match['segment']['turns'])
            selected=[t for t in session.turns if t.number in numbers]
            texts=[t.text if t.kind!='tool_call' else json.dumps({'tool':t.tool,'arguments':t.arguments},ensure_ascii=False) for t in selected]
            warning=sensitive('\n'.join(texts),terms)
            label=session.provider+' session '+session.short_id
            if warning:print('Warning: sensitive terms, credentials or email patterns occur in the selected segment of '+label+'.',file=sys.stderr)
            try:answer=confirm('Show redacted segment turns for '+label+'? [y/N] ')
            except (EOFError,KeyboardInterrupt):return
            if answer.strip().casefold() not in ('y','yes'):continue
            if not still_approved(config,session):raise ValueError('Approval or transcript changed; text not shown. Run trace again.')
            match['segment_text']=[{**session.reference(t.number),'kind':t.kind,'text':redact(text)} for t,text in zip(selected,texts)]


def render(results):
    for row in public_results(results):
        print(row['commit']+' · '+row['confidence']+' · '+row['status'])
        for m in row['matches']:
            print('  '+m['provider']+' session '+m['session_id']+' · turns '+str(m['segment']['turns'])+' · '+m['confidence'])
            print('  evidence: '+', '.join(e['type'] for e in m['evidence']))
            for ref in m['segment']['request_turns']:print('  request '+ref['reference'])
            for ref in m['segment']['tool_evidence']:print('  '+ref['type']+' '+ref['reference'])
            for t in m.get('segment_text',[]):print('  turn '+str(t['turn'])+' '+t['text'])


def main():
    if len(sys.argv)>1 and sys.argv[1] in ('enable-mcp','disable-mcp','sensitive'):
        if __package__:from .trace_mcp import settings_main
        else:from trace_mcp import settings_main
        settings_main(sys.argv[1:]);return
    if len(sys.argv)>1 and sys.argv[1]=='report':
        if __package__:from .trace_queries import report_main
        else:from trace_queries import report_main
        report_main(sys.argv[2:]);return
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path');parser.add_argument('--line',type=int)
    parser.add_argument('revision',nargs='?');parser.add_argument('--repo',type=Path,default=Path.cwd());parser.add_argument('--profile');parser.add_argument('--directory',type=Path)
    parser.add_argument('--explain-coverage',action='store_true',help='Show per-approved-session parser counts only')
    parser.add_argument('--json',action='store_true');parser.add_argument('--show-text',action='store_true');parser.add_argument('--max-results',type=int,default=3)
    parser.add_argument('--sensitive-term',action='append',default=[],help='Warn before revealing a segment containing this term (repeatable)')
    args=parser.parse_args()
    if args.show_text and not sys.stdin.isatty():parser.error('--show-text requires an interactive terminal; no text shown')
    try:
        config=config_path(args.directory,args.profile);coverage=[] if args.explain_coverage else None;differences=[]
        revision=args.revision
        if args.path is not None or args.line is not None:
            if __package__:from .trace_queries import resolve
            else:from trace_queries import resolve
            _,ids,_=resolve(args.repo,commit=revision,path=args.path,line=args.line);revision=ids[0]
        if revision is None:raise ValueError('Supply a commit/range or --path with optional --line')
        result=trace_commits(args.repo,revision,config,args.max_results,coverage,differences if args.explain_coverage else None)
        if args.show_text:
            with redirect_stdout(sys.stderr if args.json else sys.stdout):reveal(result,config,args.sensitive_term,interactive=sys.stdin.isatty())
        if args.json:print(json.dumps({'results':public_results(result),'coverage':coverage,'coverage_differences':differences} if coverage is not None else public_results(result),indent=2))
        else:
            render(result)
            if coverage is not None:
                for row in coverage:print('Coverage '+row['provider']+' session '+row['session_id']+': '+', '.join(str(row[k])+' '+k for k in ('tool_calls','commands','commits','edits','parse_failures')))
                print('Single/range differences: '+json.dumps(differences))
    except (ValueError,OSError,subprocess.SubprocessError) as exc:parser.exit(1,'Trace could not complete safely: '+(str(exc) if isinstance(exc,ValueError) else 'local input unavailable')+'\n')

if __name__=='__main__':main()
