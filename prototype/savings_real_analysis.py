# SPDX-License-Identifier: Apache-2.0
"""Frozen paired analysis for the realistic research experiment (stdlib only)."""
import csv
import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
if __package__:
    from .savings_real_costs import rates,amount
else:
    from savings_real_costs import rates,amount

USAGE_FIELDS=('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')

def tokens(row):
    return sum(row['usage'].get(k,0) for k in USAGE_FIELDS)

def interval(values, seed=104729, samples=10000):
    if not values:return None
    rng=random.Random(seed)
    means=sorted(statistics.mean(rng.choices(values,k=len(values))) for _ in range(samples))
    return [means[int(samples*.025)],means[min(samples-1,int(samples*.975))]]

def analyze(rows, definitions, repetitions=3, input_price=0, output_price=0, grader_input_price=0, grader_output_price=0, cache_read_price=0, cache_write_price=0, grader_cache_read_price=0, grader_cache_write_price=0):
    """No outcome-based exclusions: incomplete cells block the confirmatory claim."""
    grouped=defaultdict(list)
    for row in rows:
        if row['phase']=='B':grouped[(row['task_id'],row['arm'])].append(row)
    paired=[];incomplete=[]
    for task in definitions:
        arms={arm:grouped[(task['id'],arm)] for arm in ('baseline','reuse')}
        if any(len(v)!=repetitions or len({r['repetition'] for r in v})!=repetitions for v in arms.values()):
            incomplete.append(task['id']);continue
        baseline=statistics.median(tokens(r) for r in arms['baseline'])
        reuse=statistics.median(tokens(r) for r in arms['reuse'])
        if baseline<=0:incomplete.append(task['id']);continue
        paired.append({'id':task['id'],'variant':task['variant'],'expected_decision':task['expected_decision'],
            'ratio':reuse/baseline,'baseline_median_tokens':baseline,'reuse_median_tokens':reuse,
            **{arm+'_accuracy':statistics.mean(bool(r['correct']) for r in rs) for arm,rs in arms.items()},
            'decision_accuracy':statistics.mean(r.get('decision')==task['expected_decision'] for r in arms['reuse'])})
    def group(subset):
        if not subset:return {'tasks':0}
        ratios=[r['ratio'] for r in subset];deltas=[r['reuse_accuracy']-r['baseline_accuracy'] for r in subset]
        ci=interval(ratios);accuracy_ci=interval(deltas)
        return {'tasks':len(subset),'mean_paired_ratio':statistics.mean(ratios),'ratio_95_interval':ci,
            'fewer_tokens_percent':100*(1-statistics.mean(ratios)), 'fewer_tokens_95_interval_percent':[100*(1-ci[1]),100*(1-ci[0])],
            'baseline_accuracy':statistics.mean(r['baseline_accuracy'] for r in subset),'reuse_accuracy':statistics.mean(r['reuse_accuracy'] for r in subset),
            'accuracy_difference':statistics.mean(deltas),'accuracy_difference_95_interval':accuracy_ci,
            'decision_accuracy':statistics.mean(r['decision_accuracy'] for r in subset),'reuse_loses_tasks':[r['id'] for r in subset if r['ratio']>1]}
    overall=group(paired);stale=group([r for r in paired if r['variant']=='stale'])
    noninferior=bool(paired) and overall['accuracy_difference_95_interval'][0]>=-.05
    stale_safe=stale.get('tasks',0)>0 and stale['reuse_accuracy']>=stale['baseline_accuracy']
    counts={arm:{k:sum(bool(r.get(k)) for r in rows if r['phase']=='B' and r['arm']==arm) for k in ('cap_reached','refused','truncated','error')} for arm in ('baseline','reuse')}
    dollars={}
    for phase in ('A','B','grader'):
        subset=[r for r in rows if r['phase']==phase]
        usage={k:sum(r['usage'].get(k,0) for r in subset) for k in USAGE_FIELDS}
        prices=rates(grader_input_price,grader_output_price,grader_cache_read_price,grader_cache_write_price) if phase=='grader' else rates(input_price,output_price,cache_read_price,cache_write_price)
        dollars[phase]={**usage,'total_input_tokens':sum(usage[k] for k in USAGE_FIELDS[:-1]),'total_usd':float(amount(usage,prices)),
            **{k.replace('_tokens','')+'_usd':float(amount({k:usage[k]},prices)) for k in USAGE_FIELDS}}
    return {'method':'Mean paired per-task ratio of medians; task bootstrap percentile interval, 10000 draws, seed 104729. Accuracy: mean of three binary repetitions per task, paired task bootstrap. Failures count incorrect.','overall':overall,
        'per_variant':{k:group([r for r in paired if r['variant']==k]) for k in ('same','paraphrase','related','stale')},
        'per_expected_decision':{k:group([r for r in paired if r['expected_decision']==k]) for k in ('REUSE','CHECK','REDO')},
        'paired_tasks':paired,'incomplete_tasks':incomplete,'counts':counts,'phase_a':{'sessions':sum(r['phase']=='A' for r in rows),'correct':sum(bool(r.get('correct')) for r in rows if r['phase']=='A'),**{k:sum(bool(r.get(k)) for r in rows if r['phase']=='A') for k in ('cap_reached','refused','truncated','error')}},'user_priced_costs':dollars,'mean_characters_read_per_session':statistics.mean(r.get('characters_read',0) for r in rows if r['phase'] in ('A','B')) if any(r['phase'] in ('A','B') for r in rows) else 0,
        'accuracy_noninferiority_passed':noninferior,'stale_safety_passed':stale_safe,
        'claim_eligible':not incomplete and len(paired)==len(definitions) and repetitions==3 and noninferior and stale_safe and overall.get('ratio_95_interval',[1,1])[1]<1}

def export(root,summary,rows):
    root=Path(root);(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    rng=random.Random(271828)
    with (root/'spot-check.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['arm','task_id','repetition','answer','human_correct','notes'])
        for arm in ('baseline','reuse'):
            pool=[r for r in rows if r['phase']=='B' and r['arm']==arm]
            for r in rng.sample(pool,min(10,len(pool))):writer.writerow([arm,r['task_id'],r['repetition'],r['answer'],'',''])
    lines=['# Realistic research savings benchmark','',summary.get('notice','No paid run has been performed. Fake results test the harness only.'),'',
        'This controlled, public-document corpus is not a population estimate. Repeated-question detection measures opportunity, not savings.','',
        '| Group | Tasks | Fewer tokens % (95% interval) | Baseline accuracy | Reuse accuracy | Decision accuracy |','|---|---:|---|---:|---:|---:|']
    for label,g in [('Overall',summary['overall'])]+list(summary['per_variant'].items())+list(summary['per_expected_decision'].items()):
        if not g['tasks']:lines.append('| '+label+' | 0 | unavailable | | |');continue
        lines.append('| '+label+' | '+str(g['tasks'])+' | '+str(round(g['fewer_tokens_percent'],2))+' '+str([round(x,2) for x in g['fewer_tokens_95_interval_percent']])+' | '+str(round(g['baseline_accuracy'],3))+' | '+str(round(g['reuse_accuracy'],3))+' | '+str(round(g['decision_accuracy'],3))+' |')
    lines+=['','Claim eligible: '+str(summary['claim_eligible']), '', 'Accuracy non-inferiority passed (5-point margin, paired interval): '+str(summary['accuracy_noninferiority_passed']), '', 'Stale safety passed: '+str(summary['stale_safety_passed']), '', 'Incomplete tasks: '+str(summary['incomplete_tasks']), '', 'Phase B failures: '+json.dumps(summary['counts']), '', 'Original research outcomes: '+json.dumps(summary.get('phase_a',{})), '', 'Uncached input, cache reads, cache writes and output costs (separate supplied rates): '+json.dumps(summary['user_priced_costs']), '', 'Mean document characters read per session: '+str(summary.get('mean_characters_read_per_session',0)), '', 'Budget: '+json.dumps(summary.get('budget',{})), '', 'Pilot/full usage observations: '+json.dumps(summary.get('usage_observations',{})), '', 'Reuse loses: '+str(summary['overall'].get('reuse_loses_tasks',[])), '', 'Requested model: '+str(summary.get('model')), 'Resolved models: '+str(summary.get('resolved_models',[])), '']
    (root/'savings-real.md').write_text('\n'.join(lines))
