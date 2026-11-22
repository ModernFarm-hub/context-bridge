# SPDX-License-Identifier: Apache-2.0
"""Local repeat opportunities; similarity is not intent and costs are not savings."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
if __package__:
    from .retrieval import tokens
    from .reuse_policy import signals
    from .usage import research_snapshot
else:
    from retrieval import tokens
    from reuse_policy import signals
    from usage import research_snapshot

RISK=re.compile(r'\b(?:money|financial|stock|options|tax|legal|compliance|security|privacy|production|retention|password|medical|salary)\b',re.I)
NEGATION=re.compile(r'\b(?:not|never|without|disable|disabling)\b',re.I)

def date(value):
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except (ValueError,TypeError,AttributeError):return None

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def conversations(bridge):
    groups={}
    for row in bridge.db.execute('SELECT session,source,line,timestamp,role,body FROM records WHERE tenant=? AND employee=? ORDER BY source,line',bridge.owner):
        row=dict(row);meta=bridge._source_metadata.get(row['source'],{})
        key=(meta.get('provider','claude-code'),meta.get('conversation_id') or row['session'])
        group=groups.setdefault(key,{'key':digest(key),'provider':key[0],'title':meta.get('title') or 'Untitled conversation','date':meta.get('created_at'),'rows':[]})
        group['rows'].append(row)
    result=[]
    for group in groups.values():
        rows=group.pop('rows');questions=[r for r in rows if r['role']=='user'][:2]
        when=date(group['date']) or next((date(r['timestamp']) for r in rows if date(r['timestamp'])),None)
        question='\n'.join(r['body'][:1000] for r in questions)
        last=rows[-1]
        cost=research_snapshot(bridge,last)
        group.update(when=when,date=when.isoformat() if when else None,question=question,terms=set(tokens(question)),cost=cost['original_tokens'],cost_method=cost['method'],likely_redo=bool(RISK.search(' '.join(r['body'] for r in rows))) or any(signals(r['body'])['time_sensitive'] for r in rows))
        result.append(group)
    return sorted(result,key=lambda g:(g['when'] or datetime.max.replace(tzinfo=timezone.utc),g['key']))

def pair_id(a,b):return digest([a['key'],b['key']])

def review_table(bridge):
    bridge.db.execute('CREATE TABLE IF NOT EXISTS repeat_reviews (tenant TEXT, employee TEXT, pair_id TEXT, is_repeat INTEGER, reviewed_at TEXT, PRIMARY KEY(tenant,employee,pair_id))')

def report(bridge,min_similarity=None,_review_pairs=None,_calibration=False):
    mode='hybrid' if bridge.retrieval_settings.get('mode')=='hybrid' else 'bm25'
    threshold=min_similarity if min_similarity is not None else (.78 if mode=='hybrid' else .85)
    if not math.isfinite(threshold) or not 0<=threshold<=1:raise ValueError('--min-similarity must be between 0 and 1')
    floor=min(threshold,.4)
    items=conversations(bridge);pairs=[];parents={};vectors=None
    if mode=='hybrid' and items:
        if __package__:from .semantic import model
        else:from semantic import model
        embedder=model(bridge.retrieval_settings['model_directory'])
        vectors=embedder.encode([g['question'] for g in items])
    index=sqlite3.connect(':memory:')
    try:
        index.execute("CREATE VIRTUAL TABLE questions USING fts5(body,tokenize='porter unicode61')")
        index.executemany('INSERT INTO questions(rowid,body) VALUES (?,?)',[(i+1,g['question']) for i,g in enumerate(items)])
        for i,current in enumerate(items):
            if not current['when'] or not current['terms']:continue
            expression=' OR '.join('"'+term.replace('"','""')+'"' for term in sorted(current['terms']))
            lexical={r[0]-1 for r in index.execute('SELECT rowid FROM questions WHERE questions MATCH ? AND rowid<? ORDER BY bm25(questions) LIMIT 100',(expression,i+1))}
            candidates=range(i) if mode=='hybrid' else lexical
            best=None
            for j in candidates:
                prior=items[j]
                if not prior['terms'] or not prior['when'] or prior['when']>=current['when'] or prior['key']==current['key']:continue
                if bool(NEGATION.search(prior['question']))!=bool(NEGATION.search(current['question'])):continue
                common=current['terms']&prior['terms'];union=current['terms']|prior['terms']
                overlap=len(common)/max(1,len(union))
                score=.85*max(0,float(vectors[i]@vectors[j]))+.15*overlap if vectors is not None else overlap
                if mode=='bm25' and len(common)<3:continue
                if score<floor:continue
                if best is None or score>best[0] or (score==best[0] and prior['when']>items[best[1]]['when']):best=(score,j)
            if best:
                score,j=best;parents[i]=j;pairs.append((i,j,score))
    finally:index.close()
    all_pairs=pairs
    pairs=[p for p in all_pairs if p[2]>=threshold]
    parents={i:j for i,j,_ in pairs}
    review_table(bridge)
    labels={r[0]:bool(r[1]) for r in bridge.db.execute('SELECT pair_id,is_repeat FROM repeat_reviews WHERE tenant=? AND employee=?',bridge.owner)}
    def public(g):return {'title':g['title'],'date':g['date']}
    samples=[]
    ordered=sorted(pairs,key=lambda p:(-p[2],p[0]))
    if _calibration and len(ordered)>10:
        # Cover score bands so weaker candidates can be reviewed even when
        # there are many exact repeats. Deterministic, still selection-biased.
        chosen=[]
        edges=sorted({floor,.5,.6,.7,.8,1.000001})
        for lo,hi in zip(edges,edges[1:]):
            chosen.extend([p for p in ordered if lo<=p[2]<hi][:2])
        ordered=chosen+[p for p in ordered if p not in chosen]
    for i,j,score in ordered[:10]:
        pid=pair_id(items[j],items[i])
        if _review_pairs is not None:_review_pairs.append(pid)
        samples.append({'earlier':public(items[j]),'later':public(items[i])})
    chains={}
    for i in parents:
        root=i
        while root in parents:root=parents[root]
        chains.setdefault(root,{root}).add(i)
    repeated=set(parents);providers={}
    for i,g in enumerate(items):
        row=providers.setdefault(g['provider'],{'conversations':0,'repeats':0,'conservative_research_tokens':0,'cost_methods':{}})
        row['conversations']+=1
        if i in repeated:
            row['repeats']+=1;row['conservative_research_tokens']+=g['cost'];row['cost_methods'][g['cost_method']]=row['cost_methods'].get(g['cost_method'],0)+g['cost']
    for row in providers.values():row['repeat_rate']=row['repeats']/row['conversations']
    current_labels=[labels[pair_id(items[j],items[i])] for i,j,_ in pairs if pair_id(items[j],items[i]) in labels]
    redo=sum(items[i]['likely_redo'] for i in repeated)
    sensitivity=[]
    for cutoff in sorted({.4,.5,.6,.7,threshold}):
        selected=[(i,j,score) for i,j,score in all_pairs if score>=cutoff]
        reviewed=[labels[pair_id(items[j],items[i])] for i,j,_ in selected if pair_id(items[j],items[i]) in labels]
        sensitivity.append({'threshold':cutoff,'repeats':len(selected),'repeat_rate':len(selected)/len(items) if items else 0,'labelled_pairs':len(reviewed),'confirmed_repeats':sum(reviewed),'precision':sum(reviewed)/len(reviewed) if reviewed else None,'review_coverage':len(reviewed)/len(selected) if selected else None})
    return {'sensitivity':sensitivity,'calibration':'Thresholds are library-dependent. Conservative defaults (hybrid 0.78 / lexical 0.85) are synthetic-fixture starting points, not population-calibrated probabilities. Recommended: use --review to label candidate pairs down to threshold 0.4, inspect precision and coverage at each threshold, then choose --min-similarity. A zero at one threshold does not mean no research was repeated. Labelled precision is selection-biased, not recall. No default was tuned to a personal library.','notice':'Reuse opportunity, not proof of savings or repeated intent. No API calls; local data only.','conversations':len(items),'conversations_with_earlier_similar':len(repeated),'repeat_rate':len(repeated)/len(items) if items else 0,'mode':mode,'min_similarity':threshold,
      'conversations_without_dates':sum(g['when'] is None for g in items),'conservative_research_tokens':sum(items[i]['cost'] for i in repeated),'providers':providers,
      'likely_redo':{'repeats':redo,'share':redo/len(repeated) if repeated else 0,'method':'Conservative proxy: time-sensitive hint OR high-stakes term anywhere in indexed conversation. Actual policy may choose CHECK; not a policy verdict.'},
      'top_topics':[{'conversation_titles':[items[i]['title'] for i in sorted(members)],'repeats':len(members)-1} for _,members in sorted(chains.items(),key=lambda p:-len(p[1]))[:10]],
      'sample_pairs':samples,'review_precision':{'labelled_current_pairs':len(current_labels),'confirmed_repeats':sum(current_labels),'precision':sum(current_labels)/len(current_labels) if current_labels else None,'notice':'User-labelled matches only, selection-biased; not recall or population precision.'},
      'method':['First two indexed user messages, at most 1000 characters each; no assistant answers used for matching.','Only strictly earlier dated conversations count; unknown dates and ties excluded. One best earlier match per conversation; chains grouped by root.','BM25/Porter selects up to 100 earlier candidates; threshold uses content-token Jaccard with at least three shared terms. Hybrid compares local opening-question vectors plus lexical overlap (85% cosine/15% Jaccard). Threshold is not a probability.','Negation mismatch veto is conservative, not complete intent detection. Similar questions can be follow-ups, opposing intents or unrelated entities.','Repeated-conversation cost counts once using the savings conservative lower-bound formula through its final indexed message. Exports use lower-quality visible-text estimates; no lookup deduction or dollar/savings claim.']}

def review(bridge,result,confirm=None):
    confirm=confirm or input
    ids=[];candidates=report(bridge,min(.4,result['min_similarity']),ids,_calibration=True)
    for sample,pid in zip(candidates['sample_pairs'],ids):
        print(sample['earlier']['title']+' ('+str(sample['earlier']['date'])+') → '+sample['later']['title']+' ('+str(sample['later']['date'])+')',file=sys.stderr)
        print('Real repeat? [y/n/s=skip] ',end='',file=sys.stderr,flush=True)
        try:answer=confirm().strip().lower()
        except EOFError:break
        if answer not in ('y','yes','n','no'):continue
        with bridge.db:bridge.db.execute('INSERT OR REPLACE INTO repeat_reviews VALUES (?,?,?,?,?)',(*bridge.owner,pid,int(answer in ('y','yes')),datetime.now(timezone.utc).isoformat()))

def main():
    if __package__:
        from .session_manager import Sessions,DEFAULT_ROOT
        from .local_profile import profile_directory
        from .mcp_server import ContextService
    else:
        from session_manager import Sessions,DEFAULT_ROOT
        from local_profile import profile_directory
        from mcp_server import ContextService
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile');parser.add_argument('--directory',type=Path,default=DEFAULT_ROOT)
    parser.add_argument('--json',action='store_true');parser.add_argument('--min-similarity',type=float);parser.add_argument('--review',action='store_true')
    args=parser.parse_args()
    if args.review and not sys.stdin.isatty():parser.error('--review requires an interactive terminal; no labels changed')
    manager=Sessions(profile_directory(args.directory,args.profile),profile_id=args.profile or 'default')
    config=json.loads(manager.config.read_text());runtime=config.get('retrieval_python')
    if runtime and os.path.abspath(runtime)!=os.path.abspath(sys.executable):
        if not Path(runtime).is_file():parser.error('Local semantic runtime missing; repair semantic setup or disable it. No model is downloaded by repeats.')
        os.execv(runtime,[runtime,str(Path(__file__).resolve()),*sys.argv[1:]])
    service=ContextService(manager.config)
    try:
        service.refresh();result=report(service.bridge,args.min_similarity)
        if args.review:review(service.bridge,result);result=report(service.bridge,args.min_similarity)
        if args.json:print(json.dumps(result,indent=2))
        else:
            print(result['notice']);print(str(result['conversations_with_earlier_similar'])+'/'+str(result['conversations'])+' conversations have an earlier similar question ('+format(result['repeat_rate'],'.1%')+').')
            print(result['calibration'])
            print('Threshold | Repeats | Rate | Reviewed | Precision | Review coverage')
            for row in result['sensitivity']:
                print(str(row['threshold'])+' | '+str(row['repeats'])+' | '+format(row['repeat_rate'],'.1%')+' | '+str(row['labelled_pairs'])+' | '+str(row['precision'])+' | '+str(row['review_coverage']))
            print('Repeated research estimate: '+str(result['conservative_research_tokens'])+' tokens (not savings).')
            print('Likely REDO proxy: '+format(result['likely_redo']['share'],'.1%')+'. Review precision: '+str(result['review_precision']['precision']))
            print(json.dumps({'providers':result['providers'],'top_topics':result['top_topics'],'sample_pairs':result['sample_pairs'],'method':result['method']},indent=2))
    except (ValueError,ImportError,OSError) as exc:parser.exit(1,str(exc)+'\n')
    finally:
        if service.bridge:service.bridge.db.close()

if __name__=='__main__':main()
