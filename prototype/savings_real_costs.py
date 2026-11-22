# SPDX-License-Identifier: Apache-2.0
"""Local text-only request reservations and cache-aware accounting, no network."""
from decimal import Decimal
import json
import math

FIELDS=('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')
# Enforced before every Messages request, not an assumed average prompt size.
MAX_INPUT_BOUND=1_000_000
FRAMING_RESERVE=16384

class BudgetExceeded(RuntimeError):pass

def rates(input_price=0,output_price=0,cache_read_price=0,cache_write_price=0):
    values=(input_price,cache_read_price,cache_write_price,output_price)
    if any(v is None or not math.isfinite(v) or v<0 for v in values):raise ValueError('Supply finite, nonnegative input/output/cache-read/cache-write prices')
    return dict(zip(FIELDS,(str(v) for v in values)))

def amount(usage,prices):
    result=Decimal(0)
    for key in FIELDS:
        value=usage.get(key,0)
        if type(value) is not int or value<0:raise ValueError('Invalid recorded usage counter: '+key)
        result+=Decimal(value)*Decimal(prices[key])/Decimal(1_000_000)
    return result

def input_bound(body):
    """Byte-token ceiling for local text plus explicit structural framing reserve.

    JSON escapes are included (overcounting rather than character/4 estimates).
    No images, remote documents, server tools or provider-side history permitted.
    The framing reserve includes 256 tokens per message/content block/tool schema.
    """
    blocks=len(body.get('tools',[]))+len(body.get('messages',[]))
    for tool in body.get('tools',[]):
        if 'type' in tool:raise ValueError('Budget guard supports local tools only')
    def content(value):
        nonlocal blocks
        if isinstance(value,str):return
        if not isinstance(value,list):raise ValueError('Budget guard requires inline text content')
        for b in value:
            blocks+=1
            if b.get('type') not in ('text','thinking','redacted_thinking','tool_use','tool_result'):raise ValueError('Unsupported budgeted content type')
            if b['type']=='tool_result':content(b.get('content',''))
    for message in body.get('messages',[]):content(message['content'])
    if 'system' in body:content(body['system'])
    return len(json.dumps(body,ensure_ascii=True).encode('utf-8'))+FRAMING_RESERVE+256*blocks

def reservation(body,prices):
    bound=input_bound(body)
    if bound>MAX_INPUT_BOUND:raise BudgetExceeded('Request exceeds enforced text-input bound; incomplete run')
    # Any partition of input across uncached/read/write is covered by the maximum.
    input_rate=max(Decimal(prices[k]) for k in FIELDS[:-1])
    return Decimal(bound)*input_rate/Decimal(1_000_000)+Decimal(body['max_tokens'])*Decimal(prices['output_tokens'])/Decimal(1_000_000)

def planning_worst_case(calls,price_sets):
    cost=max(Decimal(MAX_INPUT_BOUND)*max(Decimal(p[k]) for k in FIELDS[:-1])/Decimal(1_000_000)+Decimal(2048)*Decimal(p['output_tokens'])/Decimal(1_000_000) for p in price_sets)
    return float(cost*calls)

def observations(records,rows,prices,grader_prices,full_calls):
    """Pilot extrapolation is descriptive, never a budget admission rule."""
    successful=[r for r in records if 'response' in r]
    sessions=[r for r in rows if r['phase'] in ('A','B')]
    def means(usages):
        return {k:sum(u.get(k,0) for u in usages)/len(usages) if usages else 0 for k in FIELDS}
    calls=[r for r in successful if not r['key'].startswith('grader-')]
    strata={};projected={k:0.0 for k in FIELDS}
    for phase,arm,count in [('A','original',40),('B','baseline',120),('B','reuse',120)]:
        group=[r for r in sessions if r['phase']==phase and r['arm']==arm]
        mean=means([r['usage'] for r in group]);strata[phase+'-'+arm]={'sessions':len(group),'mean_tokens_per_session':mean}
        for k in FIELDS:projected[k]+=count*mean[k]
    estimated=sum(Decimal(str(projected[k]))*Decimal(prices[k])/Decimal(1_000_000) for k in FIELDS)
    graders=[r for r in successful if r['key'].startswith('grader-')]
    grader_mean=means([r['response']['usage'] for r in graders])
    grader_estimate=sum(Decimal(str(grader_mean[k]))*240*Decimal(grader_prices[k])/Decimal(1_000_000) for k in FIELDS) if graders else Decimal(0)
    return {'mean_tokens_per_call':means([r['response']['usage'] for r in calls]),'mean_tokens_per_session':means([r['usage'] for r in sessions]),'grader_mean_tokens_per_call':grader_mean,'by_phase_arm':strata,
        'mean_characters_read_per_session':sum(r.get('characters_read',0) for r in sessions)/len(sessions) if sessions else 0,
        'full_run_projected_tokens':projected,'full_run_estimated_research_usd':float(estimated),'full_run_estimated_grader_usd':float(grader_estimate),
        'full_run_estimated_usd':float(estimated+grader_estimate),'full_run_worst_case_usd':planning_worst_case(full_calls,[prices,grader_prices] if graders else [prices]),
        'full_run_call_limit':full_calls,'notice':'Measured pilot extrapolation by phase/arm, not a guarantee or confidence interval. Grader estimate assumes 240 judgments (no deduplication savings). Fake tokens remain fabricated; use a separate full-run directory.'}

def recorded_costs(records,prices,grader_prices):
    """Include responses from unfinished sessions, not just finalized result rows."""
    result={}
    for phase in ('A','B','grader'):
        usage={k:0 for k in FIELDS}
        for record in records:
            if not record['key'].startswith(phase+'-') or 'response' not in record:continue
            counters=record['response'].get('usage',{})
            for k in FIELDS:
                value=counters.get(k,0)
                if type(value) is int and value>=0:usage[k]+=value
        p=grader_prices if phase=='grader' else prices
        result[phase]={**usage,'total_input_tokens':sum(usage[k] for k in FIELDS[:-1]),'total_usd':float(amount(usage,p)),
            **{k.replace('_tokens','')+'_usd':float(amount({k:usage[k]},p)) for k in FIELDS}}
    return result
