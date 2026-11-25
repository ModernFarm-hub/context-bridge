# SPDX-License-Identifier: Apache-2.0
"""Synthetic, offline savings counterfactual. No private data or hidden labels in search."""
import json
import hashlib
import platform
import sqlite3
from pathlib import Path
import subprocess
import sys
import tempfile
import time
if __package__:
    from .session_manager import Sessions,atomic_write
    from .mcp_server import ContextService,public_result,response_content
    from .usage import estimated_tokens,research_snapshot,costs_for_read
else:
    from session_manager import Sessions,atomic_write
    from mcp_server import ContextService,public_result,response_content
    from usage import estimated_tokens,research_snapshot,costs_for_read


def tasks():
    return json.loads((Path(__file__).parent/'evals/savings-tasks.json').read_text())


def corpus(root,definitions):
    manager=Sessions(Path(root)/'library');data=json.loads(manager.config.read_text())
    for i,task in enumerate(definitions):
        path=Path(root)/(task['id']+'.jsonl')
        answer=task.get('past_answer',task['reference'])
        counts=task['recorded_usage']
        planning={key:(min(40,value//2) if key=='output_tokens' else value//3) for key,value in counts.items()}
        final={key:counts[key]-planning[key] for key in counts}
        final_text=task['title']+': '+answer+'. '+task['past_note']
        rows=[{'type':'user','uuid':'q','sessionId':task['id'],'message':{'role':'user','content':task['question']}},
              {'type':'assistant','uuid':'planning','sessionId':task['id'],'message':{'id':'planning-'+task['id'],'role':'assistant','usage':planning,'content':[{'type':'tool_use','id':'synthetic-research','name':'research','input':{'topic':task['title']}}]}},
              {'type':'user','uuid':'notes','sessionId':task['id'],'message':{'role':'user','content':[{'type':'tool_result','tool_use_id':'synthetic-research','content':'Invented source notes, not real policy. '*100}]}},
              {'type':'assistant','uuid':'a','timestamp':'2026-10-01T12:00:00Z','sessionId':task['id'],'message':{'id':'answer-'+task['id'],'role':'assistant','usage':final,'content':[{'type':'thinking','thinking':'Synthetic placeholder, not actual model reasoning. '*max(0,(final['output_tokens']*4-len(final_text))//50)},{'type':'text','text':final_text}]}}]
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        data['approved_transcripts'].append(str(path))
        data.setdefault('sources',{})[str(path)]={'provider':'claude-code','conversation_id':task['id'],'title':task['title'],'created_at':'2026-10-01T12:00:00Z'}
    atomic_write(manager.config,data)
    return manager


def lookup(service,name,arguments):
    data=service.call(name,arguments,log=False)
    wire=public_result(data);content=response_content(name,wire)
    service.record_usage(name,arguments,data,content)
    return wire,estimated_tokens(''.join(block['text'] for block in content)),sum(len(block['text']) for block in content)


def offline(count=20):
    definitions=tasks()[:count]
    with tempfile.TemporaryDirectory(prefix='context-bridge-savings-') as directory:
        root=Path(directory).resolve();manager=corpus(root,definitions)
        service=ContextService(manager.config);service.client_name='synthetic-savings-benchmark'
        results=[];full_sizes=[];compact_sizes=[];legacy_compact_sizes=[];hook_tokens=[];hook_times=[]
        try:
            for task in definitions:
                row={'stakes':task['stakes'],'volatility':task['volatility'],'expected_decision':task['expected_decision'],'id':task['id'],'question':task['question'],'reference':task['reference'],'condition':task['condition'],'methods':{'original':'invented Claude Code usage counters, not a measured provider bill','lookup':'actual returned tool text, ceil(characters/4)','answer_check':'case-insensitive reference substring in the read passage; not model answer accuracy'}}
                for format in ('full','compact'):
                    start=time.perf_counter()
                    search,cost,chars=lookup(service,'context_search',{'query':task['question'],'limit':5,'format':format})
                    (full_sizes if format=='full' else compact_sizes).append(cost)
                    if format=='compact':
                        legacy={'results':[{k:v for k,v in hit.items() if k not in ('age_days','time_sensitive','time_sensitive_terms')} for hit in search['results']]}
                        legacy_compact_sizes.append(estimated_tokens(''.join(b['text'] for b in response_content('context_search',legacy))))
                    target=next((j+1 for j,hit in enumerate(search['results']) if service.bridge._source_metadata[service.bridge.locate(hit['record_id'])['source']]['conversation_id']==task['id']),None)
                    row['rank']=target
                    correct=False;original=0;upper=None;method='no-read'
                    if search['results']:
                        hit=search['results'][0]
                        read,read_cost,_=lookup(service,'context_read',{'record_id':hit['record_id'],'context':2})
                        cost+=read_cost
                        correct=task['reference'].casefold() in read['record']['body'].casefold()
                        snapshot=costs_for_read(service.bridge,{**read['record'],**service.bridge.locate(read['record']['record_id'])})[0]
                        original=snapshot['original_tokens'];upper=snapshot['all_in_upper_bound_tokens'];method=snapshot['method']
                    credit=original if correct and task['condition'] not in ('stale','wrong') else 0
                    row[format]={'original_tokens':original,'incremental_research_tokens':original,'all_in_upper_bound_including_fixed_context_tokens':upper,'credit_tokens':credit,'lookup_tokens':cost,'estimated_tokens_avoided':credit-cost,'answer_passage_correct':correct,'seconds':round(time.perf_counter()-start,6),'original_method':method}
                command=[sys.executable,str(Path(__file__).with_name('automation.py')),'hook','run','--directory',str(manager.root)]
                start=time.perf_counter()
                run=subprocess.run(command,input=json.dumps({'prompt':task['question']}),text=True,capture_output=True,timeout=1)
                duration=(time.perf_counter()-start)*1000
                injection=''
                if run.stdout:
                    injection=json.loads(run.stdout)['hookSpecificOutput']['additionalContext']
                overhead=estimated_tokens(injection)
                hook_tokens.append(overhead);hook_times.append(duration)
                row['hook']={'estimated_overhead_tokens':overhead,'characters':len(injection),'conservative_byte_token_ceiling':len(injection.encode()),'wall_ms':round(duration,3),'injected':bool(injection)}
                row['compact_plus_hook_estimated_tokens_avoided']=row['compact']['estimated_tokens_avoided']-overhead
                results.append(row)
        finally:
            if service.bridge:service.bridge.db.close()
        if __package__:from .reuse_policy import signals,volatility_fixture_metrics
        else:from reuse_policy import signals,volatility_fixture_metrics
        signal_metrics={}
        for field in ('time_sensitive','uncertainty'):
            pairs=[(signals(t['title']+': '+t.get('past_answer',t['reference'])+'. '+t['past_note'])[field],t['expected_'+field]) for t in definitions]
            tp=sum(a and b for a,b in pairs);fp=sum(a and not b for a,b in pairs);fn=sum(not a and b for a,b in pairs)
            signal_metrics[field]={'true_positive':tp,'false_positive':fp,'false_negative':fn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None}
        valid=[r for r in results if r['condition'] not in ('stale','wrong')]
        return {'version':'0.12.0a3','fixture_sha256':hashlib.sha256((Path(__file__).parent/'evals/savings-tasks.json').read_bytes()).hexdigest(),'runtime':{'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'platform':platform.system()+' '+platform.machine()},'sampling':'One search/read pipeline per task per format; one hook invocation per task. No model generation.','mode':'offline-synthetic','tasks':len(results),'signal_metrics':signal_metrics,'expanded_volatility_fixture':volatility_fixture_metrics(),'compact_signal_fields':['age_days','time_sensitive','time_sensitive_terms'],'method':'Synthetic conservative lower-bound research credit (outputs plus context growth) versus measured tool response text estimates; no model ran and no API was called. Alternatives are separate arms, not additive savings. Invalid past answers receive zero credit.','limits':['Counterfactual assumes one research redo per task. Counters are invented; fixed first-turn context is excluded from credit and all-in totals are upper bounds only. Character token estimates exclude request/model generation, setup and CPU costs.','Passage/reference checks are not generated answer accuracy. No real-library or dollar savings claim.','Hook overhead counts additionalContext only; Claude Code host framing and request serialization are excluded. Byte ceiling is conservative for ordinary byte-token models, not exact tokenizer measurement.'],
          'top_1_valid':sum(r['rank']==1 for r in valid)/len(valid),'top_5_valid':sum(r['rank'] is not None and r['rank']<=5 for r in valid)/len(valid),
          'all_in_upper_bound_including_fixed_context_tokens':sum((r['compact']['all_in_upper_bound_including_fixed_context_tokens'] or 0) for r in results if r['compact']['credit_tokens']>0),'hypothetical_redo_credit_tokens':sum(r['compact']['credit_tokens'] for r in results),'full_lookup_tokens':sum(r['full']['lookup_tokens'] for r in results),'compact_lookup_tokens':sum(r['compact']['lookup_tokens'] for r in results),'hook_overhead_tokens':sum(hook_tokens),'answer_passage_check_rate_all':sum(r['compact']['answer_passage_correct'] for r in results)/len(results),'full_estimated_tokens_avoided':sum(r['full']['estimated_tokens_avoided'] for r in results),'compact_estimated_tokens_avoided':sum(r['compact']['estimated_tokens_avoided'] for r in results),'compact_plus_hook_estimated_tokens_avoided':sum(r['compact_plus_hook_estimated_tokens_avoided'] for r in results),
          'average_compact_search_tokens_without_signals':sum(legacy_compact_sizes)/len(legacy_compact_sizes),'compact_signal_added_tokens_per_search':sum(a-b for a,b in zip(compact_sizes,legacy_compact_sizes))/len(compact_sizes),'average_full_search_tokens':sum(full_sizes)/len(full_sizes),'average_compact_search_tokens':sum(compact_sizes)/len(compact_sizes),'average_hook_overhead_tokens':sum(hook_tokens)/len(hook_tokens),'hook_wall_p95_ms':round(sorted(hook_times)[max(0,int(len(hook_times)*.95+.999999)-1)],3),'hook_worker_timeout_ms':200,
          'negative_cases':[r['id'] for r in results if r['compact']['estimated_tokens_avoided']<=0],'results':results,'target_passed':all(r['compact']['answer_passage_correct'] for r in valid)}
