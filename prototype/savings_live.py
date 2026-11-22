# SPDX-License-Identifier: Apache-2.0
"""Explicit paid synthetic agent experiment. Never called by CI or normal usage."""
import json
import math
import os
from pathlib import Path
import tempfile
import time
import urllib.request
if __package__:
    from .savings_benchmark import tasks,corpus
    from .mcp_server import ContextService,public_result
    from .reuse_policy import agent_guide,parse_decision,decision_report,PRESETS
else:
    from savings_benchmark import tasks,corpus
    from mcp_server import ContextService,public_result
    from reuse_policy import agent_guide,parse_decision,decision_report,PRESETS


def research_notes(task,step,depth):
    # Fixed synthetic source depth, not a model of real browsing difficulty.
    notes=('Invented notebook entry: compare assumptions, inspect dependencies, and verify source dates. '
           'This supporting material contains no final answer.\n')*90
    suffix=('Current reference: '+task['reference']) if step==depth else ('Continue with research step '+str(step+1)+'.')
    return 'Synthetic research step '+str(step)+' of '+str(depth)+'.\n'+notes+suffix


def live(count=5,model='claude-sonnet-5-5',input_price=None,output_price=None,yes=False,research_steps=4,policy='balanced',task_ids=None):
    if policy not in PRESETS:raise ValueError('Unknown reuse policy')
    if os.environ.get('CI'):raise ValueError('Live savings benchmark is forbidden in CI')
    pool={task['id']:task for task in tasks()}
    if task_ids is not None:
        if not task_ids or len(set(task_ids))!=len(task_ids) or any(k not in pool for k in task_ids):raise ValueError('Choose distinct known --task-ids')
        count=len(task_ids)
    if not 1<=count<=5:raise ValueError('Live mode is capped at five tasks')
    if not 1<=research_steps<=10:raise ValueError('--research-steps must be 1–10')
    if any(price is None or not math.isfinite(price) or price<0 for price in (input_price,output_price)):
        raise ValueError('Supply --input-price-per-million and --output-price-per-million for a live cost estimate')
    step_cap=research_steps+2
    # Growing notes, assistant/tool framing and product guide are included approximately.
    assumed_input_per_call=12000+research_steps*4000+step_cap*2048
    calls_cap=count*2*step_cap
    estimated_input=calls_cap*assumed_input_per_call
    estimated_output=calls_cap*2048
    estimated_budget=estimated_input+estimated_output
    advisory_usd=(estimated_input*input_price+estimated_output*output_price)/1e6
    print('Paid synthetic experiment: at most '+str(calls_cap)+' API calls, 2048 output tokens per call, research depth '+str(research_steps)+'. Advisory estimate: '+str(estimated_budget)+' tokens / USD '+str(round(advisory_usd,6))+'. Assumes '+str(assumed_input_per_call)+' input tokens per call; not a guaranteed spending cap. Separate user-supplied input/output prices, no cache discounts.',flush=True)
    if not yes:raise ValueError('No API calls made. Review the estimate and repeat with --yes to consent to paid execution.')
    key=os.environ.get('ANTHROPIC_API_KEY')
    if not key:raise ValueError('Set ANTHROPIC_API_KEY; no API calls made')
    pool={task['id']:task for task in tasks()}
    definitions=[pool[name] for name in (task_ids or ('aster','willow','comet','mint','pine'))][:count]
    definitions.sort(key=lambda t:t['condition']!='valid');results=[]
    research_tool={'name':'research','description':'Inspect invented source notebooks sequentially. Request step 1 first, then the next step indicated by each result. The current answer is available only at the final step ('+str(research_steps)+'). No real-world facts.','input_schema':{'type':'object','properties':{'step':{'type':'integer','minimum':1,'maximum':research_steps}},'required':['step'],'additionalProperties':False}}
    with tempfile.TemporaryDirectory(prefix='context-bridge-live-synthetic-') as temporary:
        manager=corpus(Path(temporary),definitions);service=ContextService(manager.config);service.client_name='synthetic-live-benchmark'
        try:
            for task in definitions:
                for reuse in (False,True):
                    messages=[{'role':'user','content':task['question']}]
                    tools=[research_tool]
                    if reuse:
                        if __package__:from .mcp_server import TOOLS
                        else:from mcp_server import TOOLS
                        tools+=[{'name':t['name'],'description':t['description'],'input_schema':t['inputSchema']} for t in TOOLS]
                    totals={'input_tokens':0,'output_tokens':0,'cache_read_input_tokens':0,'cache_creation_input_tokens':0};calls=0;research_completed=0;stop_reasons=[];decision_text='';answer='';error=None;start=time.perf_counter();tool_names=[];final=False;resolved_model=model
                    try:
                        for step in range(step_cap):
                            body={'model':model,'max_tokens':2048,'thinking':{'type':'between_tools'},'output_config':{'effort':'low'},'messages':messages,'tools':tools}
                            if reuse:body['system']=agent_guide(policy)
                            request=urllib.request.Request('https://api.anthropic.com/v1/messages',data=json.dumps(body).encode(),headers={'x-api-key':key,'anthropic-version':'2023-06-01','content-type':'application/json'},method='POST')
                            with urllib.request.urlopen(request,timeout=30) as response:data=json.load(response)
                            calls+=1
                            resolved_model=data.get('model',model)
                            for field in totals:totals[field]+=data.get('usage',{}).get(field,0)
                            content=data.get('content',[]);messages.append({'role':'assistant','content':content})
                            reason=data.get('stop_reason','end_turn');stop_reasons.append(reason)
                            if reason in ('refusal','max_tokens'):break
                            answer='';pending=[]
                            for block in content:
                                if block.get('type')=='text':
                                    answer+=block.get('text','')+'\n'
                                    decision_text+=block.get('text','')+'\n'
                                if block.get('type')!='tool_use':continue
                                name=block['name'];tool_names.append(name)
                                if name=='research':
                                    requested=block.get('input',{}).get('step')
                                    if type(requested) is int and requested==research_completed+1 and requested<=research_steps:
                                        research_completed=requested
                                        output=research_notes(task,requested,research_steps)
                                    else:output='Request the next sequential research step: '+str(research_completed+1)+'. No new notes supplied.'
                                elif reuse and name in ('context_search','context_read'):
                                    output=json.dumps(public_result(service.call(name,block.get('input',{}))))
                                else:output='Unknown tool'
                                pending.append({'type':'tool_result','tool_use_id':block['id'],'content':output})
                            if not pending:
                                final=data.get('stop_reason','end_turn')=='end_turn'
                                break
                            messages.append({'role':'user','content':pending})
                    except Exception as exc:error=type(exc).__name__
                    total=sum(totals.values())
                    results.append({'id':task['id'],'stakes':task['stakes'],'volatility':task['volatility'],'expected_decision':task['expected_decision'],'decision':parse_decision(decision_text),'decision_correct':parse_decision(decision_text)==task['expected_decision'],'case_group':'positive' if task['condition']=='valid' else 'negative','condition':task['condition'],'reuse_available':reuse,'model':model,'resolved_model':resolved_model,'final_answer_observed':final,'turn_limit_reached':calls==step_cap and not final,'usage':totals,'measured_total_tokens':total,'calls':calls,'seconds':round(time.perf_counter()-start,3),'answer':answer,'accuracy_reference_substring':final and task['reference'].casefold() in answer.casefold(),'tools_used':tool_names,'called_context_search':'context_search' in tool_names,'called_context_read':'context_read' in tool_names,'research_steps_completed':research_completed,'stop_reasons':stop_reasons,'refused':'refusal' in stop_reasons,'truncated':'max_tokens' in stop_reasons,'error':error,'user_priced_usd':((totals['input_tokens']+totals['cache_read_input_tokens']+totals['cache_creation_input_tokens'])*input_price+totals['output_tokens']*output_price)/1e6})
        finally:
            if service.bridge:service.bridge.db.close()
    return {'mode':'live-paid-synthetic','model':model,'policy':policy,'decision_metrics':decision_report(results),'research_steps':research_steps,'step_cap_per_arm':step_cap,'max_output_tokens_per_call':2048,'prices':{'input_usd_per_million':input_price,'output_usd_per_million':output_price},
      'method':'Same neutral question in both arms; sequential synthetic notes available to both. Reuse arm adds the product agent-guide system prompt and Context Bridge tools. Positive tasks run first; negative cases are reported separately. Provider usage and wall time measured only when explicitly run.',
      'limits':['Synthetic tasks, fixed assumed research depth and small n cannot establish real-world savings. Artificial note volume and sequential gating influence the outcome.',
      'Reference-substring scoring can reject correct paraphrases or accept text without reasoning.',
      'Tool choice is model-dependent; report actual search/read calls, refusals and truncation. No guarantee of reuse or lower cost.',
      'User input/output prices are not an invoice; input rate is applied to cache tokens without discounts or creation surcharges. Failed responses may have unreported charges. Advisory input size is not a hard cap.',
      'No real private library is sent; only synthetic materials go to Anthropic after --yes.'],
      'advisory_pre_run_tokens':estimated_budget,'advisory_pre_run_usd':advisory_usd,'assumed_input_tokens_per_call':assumed_input_per_call,
      'positive_results':[r for r in results if r['case_group']=='positive'],'negative_results':[r for r in results if r['case_group']=='negative'],
      'results':results,'target_passed':all(row['error'] is None and row['final_answer_observed'] and not row['refused'] and not row['truncated'] for row in results)}
