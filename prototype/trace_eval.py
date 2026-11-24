# SPDX-License-Identifier: Apache-2.0
"""Interactive local feasibility labels. This is not a measured quality claim."""
from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime,timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
if __package__:
    from .trace import repository,git,trace_commits,public_results,render,reveal,sensitive
    from .trace_sources import config_path
    from .privacy import redact
else:
    from trace import repository,git,trace_commits,public_results,render,reveal,sensitive
    from trace_sources import config_path
    from privacy import redact


def metrics(labels):
    linked=[r for r in labels if r['linked']]
    judged=[r for r in linked if r['right_session'] in ('yes','no')]
    why=Counter(str(r['why']) for r in labels if r['why'] in (0,1,2))
    baseline=Counter(str(r['baseline_why']) for r in labels if r['baseline_why'] in (0,1,2))
    paired=[r for r in labels if r['why'] in (0,1,2) and r['baseline_why'] in (0,1,2)]
    return {'reviewed_commits':len(labels),'linked_commits':len(linked),'coverage':len(linked)/len(labels) if labels else None,
        'session_precision':sum(r['right_session']=='yes' for r in judged)/len(judged) if judged else None,'session_precision_denominator':len(judged),
        'session_unsure':sum(r['right_session']=='unsure' for r in linked),'why_score_distribution':{str(k):why[str(k)] for k in (0,1,2)},
        'privacy_incidents':sum(r['private_material']=='yes' for r in labels),
        'baseline':{'method':'git log message + diff only','why_score_distribution':{str(k):baseline[str(k)] for k in (0,1,2)},'paired_labels':len(paired),
            'mean_trace_minus_baseline_why':sum(r['why']-r['baseline_why'] for r in paired)/len(paired) if paired else None},
        'segment_shown':sum(r['segment_shown'] for r in labels),'baseline_shown':sum(r['baseline_shown'] for r in labels),
        'notice':'Human labels for sampled commits only. Unsure session labels are excluded from precision; unsure why scores are excluded from distributions/comparisons. Coverage is not precision and matching is not proof of why. No labels or text leave this machine.'}


def ask(prompt,choices,input_fn):
    while True:
        value=input_fn(prompt).strip().casefold()
        if value in choices:return choices[value]
        print('Choose one of: '+', '.join(choices),file=sys.stderr)


def evaluate(repo,config,sample=20,seed=0,review_file=None,input_fn=input,interactive=True,sensitive_terms=()):
    if not interactive:raise ValueError('trace-eval requires an interactive terminal; no labels written')
    if not 1<=sample<=1000:raise ValueError('--sample must be 1–1000')
    repo=repository(repo);config=Path(config)
    destination=Path(review_file) if review_file else config.parent/'trace-eval-reviews.jsonl'
    if destination.resolve().is_relative_to(repo):raise ValueError('Evaluation labels must be stored outside the repository')
    ids=git(repo,'rev-list','--all').splitlines()
    if not ids:raise ValueError('Repository has no commits to sample')
    chosen=random.Random(seed).sample(sorted(ids),min(sample,len(ids)))
    labels=[];repo_id=hashlib.sha256(str(repo).encode()).hexdigest()
    for oid in chosen:
        result=trace_commits(repo,oid,config,max_results=1);render(result)
        match=result[0]['matches'][0] if result[0]['matches'] else None
        try:
            if match:
                reveal(result,config,sensitive_terms,confirm=input_fn,interactive=True)
                for turn in match.get('segment_text',[]):print('Turn '+str(turn['turn'])+' '+turn['text'])
            baseline=git(repo,'show','--format=medium','--no-ext-diff','--no-textconv','--no-color',oid)
            if sensitive(baseline,sensitive_terms):print('Warning: sensitive patterns in git baseline for '+oid+'.',file=sys.stderr)
            baseline_shown=ask('Show redacted git-message/diff baseline for commit '+oid+'? [y/N] ',{'y':True,'yes':True,'':False,'n':False,'no':False},input_fn)
            if baseline_shown:print(redact(baseline))
            right=ask('Right session? [yes/no/unsure] ',{'yes':'yes','y':'yes','no':'no','n':'no','unsure':'unsure','u':'unsure'},input_fn) if match else None
            why=ask('Does the segment explain why? [0=no/1=partly/2=yes/u=unsure] ',{'0':0,'1':1,'2':2,'u':None,'unsure':None},input_fn)
            private=ask('Was unrelated private material shown? [yes/no] ',{'yes':'yes','y':'yes','no':'no','n':'no'},input_fn)
            baseline_why=ask('Git-message/diff baseline why score? [0/1/2/u=unsure] ',{'0':0,'1':1,'2':2,'u':None,'unsure':None},input_fn)
        except (EOFError,KeyboardInterrupt):break
        label={'schema':1,'repository_id':repo_id,'commit':oid,'sample_seed':seed,'reviewed_at':datetime.now(timezone.utc).isoformat(),
            'linked':bool(match),'session_id':match['session_id'] if match else None,'segment_turns':match['segment']['turns'] if match else [],
            'right_session':right,'why':why,'private_material':private,'baseline_why':baseline_why,'segment_shown':bool(match and match.get('segment_text')),'baseline_shown':baseline_shown}
        destination.parent.mkdir(parents=True,exist_ok=True)
        # A private append-only local label log; no source text, titles or paths.
        fd=os.open(str(destination),os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        import fcntl
        with os.fdopen(fd,'a') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX);stream.write(json.dumps(label)+'\n');stream.flush()
        labels.append(label)
    return {'sample_seed':seed,'sampled_commits':len(chosen),'metrics':metrics(labels),'storage':'Local profile review log; no session text or titles stored.'}


def ai_metrics(labels):
    count=len(labels)
    return {'reviewed_commits':count,'mean_q1_why':sum(r['q1_why'] for r in labels)/count if count else None,
        'mean_q2_why':sum(r['q2_why'] for r in labels)/count if count else None,
        'mean_paired_difference':sum(r['q1_why']-r['q2_why'] for r in labels)/count if count else None,
        'invented_reason_count':sum(r['invented_reason']=='yes' for r in labels),
        'privacy_incident_count':sum(r['private_material']=='yes' for r in labels),
        'notice':"One person's judgments on one repository; not a general explanation-quality claim. Only complete paired ratings from this invocation are reported."}


def evaluate_ai(repo,config,sample=10,seed=0,review_file=None,input_fn=input,interactive=True):
    if not interactive:raise ValueError('trace-eval --ai requires an interactive terminal; no labels written')
    if not 1<=sample<=1000:raise ValueError('--sample must be 1–1000')
    if __package__:from .trace_mcp import enabled
    else:from trace_mcp import enabled
    if not enabled(config):raise ValueError('Enable context_trace for this profile with trace enable-mcp before AI evaluation')
    repo=repository(repo);config=Path(config)
    destination=Path(review_file) if review_file else config.parent/'trace-eval-reviews.jsonl'
    if destination.resolve().is_relative_to(repo):raise ValueError('Evaluation labels must be stored outside the repository')
    ids=sorted(set(git(repo,'rev-list','--all').splitlines()));random.Random(seed).shuffle(ids)
    chosen=[];scanned=0
    # Rejection sampling from a seeded permutation is uniform among linked
    # commits. No session text is revealed during selection.
    for oid in ids:
        scanned+=1;result=trace_commits(repo,oid,config,max_results=1)
        if result[0]['matches']:chosen.append((oid,result[0]['matches'][0]))
        if len(chosen)>=sample:break
    labels=[];repo_id=hashlib.sha256(str(repo).encode()).hexdigest()
    print('Use a client whose context_trace server and git tools point at this selected repository. Paste each question into your AI client in separate chats. Q2 should use only git show, without context_trace or session evidence. Ratings stay local; Q1 evidence goes to your AI client and its model provider.')
    for oid,match in chosen:
        print('Q1 (with trace): Use context_trace for commit '+oid+' and explain in 2–5 sentences why it was made. Use Reason, supported Alternatives or caveats, and Sources. Cite turns.')
        print('Q2 (baseline): Using only git show '+oid+', explain in 2–5 sentences why commit '+oid+' was made. Use Reason, supported Alternatives or caveats, and Sources.')
        try:
            q1=ask('Q1 why-quality? [0=no/1=partly/2=yes] ',{'0':0,'1':1,'2':2},input_fn)
            q2=ask('Q2 why-quality? [0=no/1=partly/2=yes] ',{'0':0,'1':1,'2':2},input_fn)
            invented=ask('Any invented or unsupported reason in Q1? [yes/no] ',{'yes':'yes','y':'yes','no':'no','n':'no'},input_fn)
            private=ask('Any unrelated private material in Q1? [yes/no] ',{'yes':'yes','y':'yes','no':'no','n':'no'},input_fn)
        except (EOFError,KeyboardInterrupt):break
        label={'schema':2,'mode':'ai','repository_id':repo_id,'commit':oid,'sample_seed':seed,
            'reviewed_at':datetime.now(timezone.utc).isoformat(),'session_id':match['session_id'],'segment_turns':match['segment']['turns'],
            'q1_why':q1,'q2_why':q2,'invented_reason':invented,'private_material':private}
        destination.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(str(destination),os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        import fcntl
        with os.fdopen(fd,'a') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX);stream.write(json.dumps(label)+'\n');stream.flush()
        labels.append(label)
    return {'mode':'ai','sample_seed':seed,'requested_sample':sample,'sampled_commits':len(chosen),'scanned_commits':scanned,
        'metrics':ai_metrics(labels),'storage':'Local ratings only; no AI answers, session text, titles or paths stored.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True);parser.add_argument('--sample',type=int);parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--profile');parser.add_argument('--directory',type=Path);parser.add_argument('--review-file',type=Path);parser.add_argument('--json',action='store_true')
    parser.add_argument('--sensitive-term',action='append',default=[])
    parser.add_argument('--ai',action='store_true',help='Rate short answers from your AI client, with a git-only baseline')
    args=parser.parse_args()
    if not sys.stdin.isatty():parser.error('trace-eval requires an interactive terminal; no labels written')
    try:
        with redirect_stdout(sys.stderr if args.json else sys.stdout):
            config=config_path(args.directory,args.profile)
            if args.ai:result=evaluate_ai(args.repo,config,args.sample if args.sample is not None else 10,args.seed,args.review_file,interactive=True)
            else:result=evaluate(args.repo,config,args.sample if args.sample is not None else 20,args.seed,args.review_file,interactive=True,sensitive_terms=args.sensitive_term)
    except (ValueError,OSError) as exc:parser.exit(1,str(exc) if isinstance(exc,ValueError) else 'Local evaluation input unavailable')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
