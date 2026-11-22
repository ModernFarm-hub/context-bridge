# SPDX-License-Identifier: Apache-2.0
"""Re-grade a completed saved pilot locally. No provider, library or network code."""
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
if __package__:
    from .savings_real_grading import grade_details, AMENDMENT
    from .reuse_policy import parse_decision
    from .savings_real_analysis import analyze, tokens
else:
    from savings_real_grading import grade_details, AMENDMENT
    from reuse_policy import parse_decision
    from savings_real_analysis import analyze, tokens

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def regrade(pilot,data,output):
    pilot=Path(pilot);data=Path(data);output=Path(output)
    run=json.loads((pilot/'run.json').read_text())
    if not run.get('pilot'):raise ValueError('Regrading command is restricted to saved pilots')
    if run['tasks_sha256']!=sha(data/'tasks.json'):raise ValueError('Saved pilot task hash differs from frozen tasks')
    if run['manifest_sha256']!=sha(data/'manifest.json'):raise ValueError('Saved pilot corpus manifest differs')
    prereg=(data/'PREREGISTRATION.md').read_text()
    for name in ('savings_real_analysis.py','savings_real_grading.py','reuse_policy.py','savings_real_regrade.py'):
        registered=re.findall(r'^- prototype/'+re.escape(name)+r': `([a-f0-9]{64})`',prereg,re.M)
        if not registered or registered[-1]!=sha(Path(__file__).with_name(name)):raise ValueError('Amendment hash mismatch: '+name)
    rows=[json.loads(line) for line in (pilot/'results.jsonl').read_text().splitlines() if line.strip()]
    definitions={t['id']:t for t in json.loads((data/'tasks.json').read_text())}
    b_ids={r['task_id'] for r in rows if r['phase']=='B'}
    if len(b_ids)!=5:raise ValueError('Expected five complete pilot task pairs')
    for task_id in b_ids:
        for arm in ('baseline','reuse'):
            if sum(r['phase']=='B' and r['task_id']==task_id and r['arm']==arm for r in rows)!=1:raise ValueError('Incomplete or duplicate pilot arm')
    selected=[t for t in definitions.values() if t['id'] in b_ids]
    raw=[json.loads(line) for line in (pilot/'raw-calls.jsonl').read_text().splitlines() if line.strip()]
    amended=copy.deepcopy(rows);sessions=[]
    for old,new in zip(rows,amended):
        if old['phase'] not in ('A','B'):continue
        name=old['phase']+'-'+old['task_id']+'-'+old['arm']+'-'+str(old['repetition'])+'-'
        calls=sorted([r for r in raw if r['key'].startswith(name)],key=lambda r:r['key'])
        if not calls or any('response' not in r for r in calls):raise ValueError('Missing completed saved responses: '+name)
        response=calls[-1]['response']
        answer='\n'.join(b['text'] for b in response['content'] if b.get('type')=='text')
        usage={k:sum(r['response']['usage'].get(k,0) for r in calls) for k in old['usage']}
        if answer!=old['answer'] or usage!=old['usage'] or len(calls)!=len(old['stop_reasons']):raise ValueError('Saved result does not match raw responses: '+name)
        task=definitions[old['task_id']]
        reference=task['original_reference_answer'] if old['phase']=='A' else task['required_facts']
        grading=grade_details(answer,reference,final=old['final'])
        new.update(correct=grading['correct'],grading_method=grading['method'],grading_amendment=AMENDMENT,decision=parse_decision(answer) if old['final'] else None)
        applicable=old['phase']=='B' and old['arm']=='reuse'
        sessions.append({'phase':old['phase'],'task_id':old['task_id'],'arm':old['arm'],'repetition':old['repetition'],
            'before_correct':old['correct'],'after_correct':new['correct'],'grading_method':grading['method'],'missing_facts':grading['missing_facts'],
            'before_decision':old.get('decision'),'after_decision':new['decision'],
            'before_compliant':old.get('decision') is not None if applicable else None,'after_compliant':new['decision'] is not None if applicable else None,
            'expected_decision':task['expected_decision'] if applicable else None,
            'after_decision_correct':new['decision']==task['expected_decision'] if applicable else None,
            'answer_sha256':hashlib.sha256(answer.encode()).hexdigest(),'tokens':tokens(old),'calls':len(calls)})
    prices=run['prices'];gp=run.get('grader_prices',{})
    args=dict(repetitions=1,input_price=float(prices['input_tokens']),output_price=float(prices['output_tokens']),cache_read_price=float(prices['cache_read_input_tokens']),cache_write_price=float(prices['cache_creation_input_tokens']),grader_input_price=float(gp.get('input_tokens',0)),grader_output_price=float(gp.get('output_tokens',0)),grader_cache_read_price=float(gp.get('cache_read_input_tokens',0)),grader_cache_write_price=float(gp.get('cache_creation_input_tokens',0)))
    before=analyze(rows,selected,**args);after=analyze(amended,selected,**args)
    comparisons=[]
    for task in selected:
        pair={r['arm']:r for r in rows if r['phase']=='B' and r['task_id']==task['id']}
        b=pair['baseline'];r=pair['reuse']
        comparisons.append({'task_id':task['id'],'baseline_tokens':tokens(b),'reuse_tokens':tokens(r),'reuse_to_baseline_ratio':tokens(r)/tokens(b),'reuse_costs_more_tokens':tokens(r)>tokens(b),'baseline_calls':len(b['stop_reasons']),'reuse_calls':len(r['stop_reasons'])})
    inputs={name:sha(pilot/name) for name in ('run.json','results.jsonl','summary.json','raw-calls.jsonl')}
    result={'amendment':AMENDMENT,'reason':'pilot found formatting-only false negatives','source_run':pilot.name,'source_file_sha256':inputs,
        'requested_model':run['model'],'source_is_fake':run['fake'],'no_new_api_calls':True,'claim_eligible':False,
        'registered_hashes':{p.name:sha(p) for p in (Path(__file__).with_name('savings_real_analysis.py'),Path(__file__).with_name('savings_real_grading.py'),Path(__file__).with_name('reuse_policy.py'),Path(__file__))},
        'sessions':sessions,'before':before,'after':after,'per_task_tokens':comparisons,
        'correctness_changes':sum(r['before_correct']!=r['after_correct'] for r in sessions),
        'reported_source_usd':json.loads((pilot/'summary.json').read_text()).get('budget',{}).get('recorded_usd'),
        'notice':'Before correctness and decisions are the original saved labels. After labels come only from local final-answer regrading. Tokens, prices, calls and answers were not changed. Pilot is exploratory, never confirmatory. No library was loaded; no secondary model grader was called.'}
    output.mkdir(parents=True,exist_ok=True)
    # New sidecars only: never rewrite original run, calls, answers or labels.
    targets=[output/'regrade.json',output/'regrade.md',output/'amended-results.json']
    if any(p.resolve() in {(pilot/n).resolve() for n in inputs} for p in targets):raise ValueError('Cannot overwrite source pilot')
    targets[0].write_text(json.dumps(result,indent=2)+'\n')
    targets[2].write_text(json.dumps(amended,indent=2)+'\n')
    lines=['# Pilot regrading: '+AMENDMENT,'','Reason: pilot found formatting-only false negatives. No new API calls.','',
        'Source: '+pilot.name+'. The original artifacts remain unchanged. This five-task pilot is exploratory, not a qualifying result.','',
        '| Phase | Task | Arm | Correct before | Correct after | Grading method | Decision before | Decision after | Compliant before → after | Tokens | Calls |',
        '|---|---|---|---|---|---|---|---|---|---:|---:|']
    for s in sessions:
        lines.append('| '+' | '.join(str(s[k]) for k in ('phase','task_id','arm','before_correct','after_correct','grading_method','before_decision','after_decision'))+' | '+str(s['before_compliant'])+' → '+str(s['after_compliant'])+' | '+str(s['tokens'])+' | '+str(s['calls'])+' |')
    lines+=['','Correctness changes: '+str(result['correctness_changes']), '', 'Fallback: '+json.dumps(after['fallback_grading']), '', 'Decision compliance: '+json.dumps(after['decision_compliance']), '',
        'Decision accuracy (distinct from compliance): '+str(after['overall'].get('decision_accuracy')), '',
        '| Task | Baseline tokens | Reuse tokens | Ratio | Baseline calls | Reuse calls |','|---|---:|---:|---:|---:|---:|']
    for c in comparisons:lines.append('| '+c['task_id']+' | '+str(c['baseline_tokens'])+' | '+str(c['reuse_tokens'])+' | '+str(round(c['reuse_to_baseline_ratio'],4))+' | '+str(c['baseline_calls'])+' | '+str(c['reuse_calls'])+' |')
    lines+=['', 'Reuse used more tokens in '+str(sum(c['reuse_costs_more_tokens'] for c in comparisons))+' of 5 tasks. These are documentation lookups; deeper research is a separate future question.', '',
        'Each session retains its original usage and call count. No task, corpus, arm, call cap, metric formula, bootstrap setting or threshold changed.', '',
        'A colon after a decision is now accepted. A period followed by prose remains unsupported under the specified separators. All saved final answers in this pilot contain facts JSON; its observed fallback share is zero. A separately labelled prose-only regression fixture tests the new fallback without claiming it occurred in these saved finals.', '',
        'Source artifact SHA-256 hashes: '+json.dumps(inputs,sort_keys=True),'']
    targets[1].write_text('\n'.join(lines))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot-dir',required=True,type=Path);parser.add_argument('--data-dir',type=Path,default=Path(__file__).parent/'evals/savings-real');parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    try:result=regrade(args.pilot_dir,args.data_dir,args.output)
    except (ValueError,OSError,KeyError) as exc:parser.exit(1,str(exc)+'\n')
    print('Locally regraded '+str(len(result['sessions']))+' sessions; '+str(result['correctness_changes'])+' correctness changes; no API calls.')

if __name__=='__main__':main()
