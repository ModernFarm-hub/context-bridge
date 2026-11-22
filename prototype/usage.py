# SPDX-License-Identifier: Apache-2.0
"""Profile-local accounting. Character estimates are not provider billing tokens."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import sys

TOKEN_METHOD='ceil(response text characters / 4); excludes requests, model answers and protocol envelope'
ASSUMPTIONS=[
    'Estimate, not measured savings or proof that a read answer was used or correct.',
    'Credit each conversation once, using the maximum cumulative research cost through the latest indexed message actually returned in a read page/window.',
    'Subtract every logged lookup response, including misses and searches without a read. Negative totals mean overhead.',
    'Lookup tokens use ceil(characters/4), not a model tokenizer; full MCP text includes readable Source lines.',
    'Conservative lower-bound estimate: cumulative assistant output + max(0, cited-turn context - first-assistant-turn context). Claude Code context = input + cache creation + cache read; Codex context = per-turn input (cached input is already included). Reasoning remains counted once inside output.',
    'The old all-in counter total is an upper bound including fixed context overhead, never the credit used for estimated avoided tokens. Legacy snapshots without context baselines receive output-only credit; re-read passages to obtain context-growth snapshots. Context compaction can undercount growth, and growth is not proof of useful research.',
    'Export costs estimate only indexed visible text through the passage: lower-quality, not the unknown original research bill.',
    'Shared search costs are assigned once to the first later read of a returned ID; this temporal heuristic is not causal attribution. Unassigned costs reduce only the total.',
    'A read may be stale, wrong, paginated, or never used. No freshness or factual verification is inferred.',
    'Redo once per conversation is a counterfactual assumption; it may not describe your workflow. Request tokens, answer generation, hook host framing, embedding and CPU costs are not billed-token measurements.'
]


def estimated_tokens(text):
    return math.ceil(len(text)/4)


def number(value):
    return value if type(value) is int and value>=0 else 0


def update_research(item,state,provider,line=0):
    """Consume only numeric usage; return whether this line supplies a cost event."""
    if not isinstance(item,dict):return False
    if provider!='codex':
        msg=item.get('message',{})
        if item.get('type')!='assistant' or not isinstance(msg,dict) or msg.get('role')!='assistant' or not isinstance(msg.get('usage'),dict):return False
        usage=msg['usage']
        key=hashlib.sha256(str(msg.get('id') or item.get('uuid') or ('line:'+str(line))).encode()).hexdigest()
        values=[number(usage.get(k)) for k in ('input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens')]
        previous=state.setdefault('seen',{}).get(key,[0]*4)
        state['counts']=[old+new-prior for old,new,prior in zip(state.get('counts',[0]*4),values,previous)]
        state['seen'][key]=values
        context=values[0]+values[2]+values[3]
        state.setdefault('baseline_context',context)
        state['current_context']=context
        state['method']='claude-code-recorded'
        return True
    payload=item.get('payload',{})
    if not isinstance(payload,dict):return False
    kind=payload.get('type') if item.get('type')=='event_msg' else item.get('type')
    if kind not in ('token_count','token_usage_record'):return False
    info=payload.get('info') or payload
    if not isinstance(info,dict):return False
    usage=info.get('total_token_usage')
    cumulative=isinstance(usage,dict)
    if not cumulative:usage=info.get('last_token_usage') or info.get('usage') or (info if 'input_tokens' in info or 'output_tokens' in info else None)
    if not isinstance(usage,dict):return False
    values=[number(usage.get('input_tokens')),number(usage.get('output_tokens')),number(usage.get('cached_input_tokens')),0]
    previous_counts=state.get('counts',[0]*4)
    if cumulative:state['counts']=values
    else:
        key=hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()
        if key in state.setdefault('seen',{}):return False
        state['seen'][key]=True
        state['counts']=[a+b for a,b in zip(state.get('counts',[0]*4),values)]
    last=info.get('last_token_usage')
    context=number(last.get('input_tokens')) if isinstance(last,dict) and 'input_tokens' in last else (max(0,values[0]-previous_counts[0]) if cumulative else values[0])
    state.setdefault('baseline_context',context)
    state['current_context']=context
    state['method']='codex-recorded'
    return True


def incremental_credit(snapshot):
    """Normalize both new snapshots and previously logged all-in snapshots."""
    item=dict(snapshot);method=item.get('method')
    if method in ('claude-code-recorded','codex-recorded'):
        breakdown=item.get('token_breakdown')
        if isinstance(breakdown,dict):
            i,o,c,w=[number(breakdown.get(key)) for key in ('input_tokens','output_tokens','cached_input_tokens','cache_creation_input_tokens')]
        elif isinstance(item.get('counts'),list) and len(item['counts'])==4:
            i,o,c,w=[number(value) for value in item['counts']]
        else:
            item.update(original_tokens=0,incremental_credit_tokens=0,all_in_upper_bound_tokens=number(item.get('original_tokens')),quality='Legacy snapshot lacks a usage breakdown; no incremental credit')
            return item
        upper=max(i+o+(c+w if method=='claude-code-recorded' else 0),number(item.get('all_in_upper_bound_tokens')))
        baseline=item.get('baseline_context_tokens');current=item.get('cited_context_tokens')
        growth=max(0,current-baseline) if type(baseline) is int and type(current) is int else 0
        credit=o+growth
        item.update(original_tokens=credit,incremental_credit_tokens=credit,all_in_upper_bound_tokens=upper,context_growth_tokens=growth,quality='conservative lower-bound estimate; output plus context growth, redo remains hypothetical')
    else:
        item.update(incremental_credit_tokens=item['original_tokens'],all_in_upper_bound_tokens=None)
    return item


def research_snapshot(bridge,record):
    source,line=record['source'],record['line']
    meta=bridge._source_metadata.get(source,{})
    provider=meta.get('provider','claude-code')
    cid=meta.get('conversation_id') or record['session']
    key=hashlib.sha256(json.dumps([provider,cid]).encode()).hexdigest()
    row=bridge.db.execute('SELECT method,counts FROM research_costs WHERE tenant=? AND employee=? AND source=? AND line=?',(*bridge.owner,source,line)).fetchone()
    stored={}
    if row:
        method=row['method'];stored=json.loads(row['counts']);counts=stored['counts'] if isinstance(stored,dict) else stored
        total=counts[0]+counts[1]+(sum(counts[2:]) if method=='claude-code-recorded' else 0)
    else:
        later=bridge.db.execute('SELECT method FROM research_costs WHERE tenant=? AND employee=? AND source=? ORDER BY line LIMIT 1',(*bridge.owner,source)).fetchone()
        if later and provider in ('claude-code','codex'):
            # Known recorded usage exists, but none precedes this early message.
            method=later['method'];counts=[0]*4;total=0
        else:
            characters=bridge.db.execute('SELECT COALESCE(SUM(LENGTH(body)),0) FROM records WHERE tenant=? AND employee=? AND source=? AND session=? AND line<=?',(*bridge.owner,source,record['session'],line)).fetchone()[0]
            total=math.ceil(characters/4);counts=[total,0,0,0];method='visible-text-estimate'
    return incremental_credit({'conversation':key,'label':record.get('source_label') or meta.get('title') or provider,'link':record.get('link'),'record_id':record.get('record_id'),'original_tokens':total,'baseline_context_tokens':stored.get('baseline_context') if isinstance(stored,dict) else None,'cited_context_tokens':stored.get('current_context') if isinstance(stored,dict) else None,'token_breakdown':dict(zip(('input_tokens','output_tokens','cached_input_tokens','cache_creation_input_tokens'),counts)) if method!='visible-text-estimate' else {'visible_text_estimated_tokens':total},'method':method,'quality':'lower-quality visible-text estimate' if method=='visible-text-estimate' else 'recorded incremental counters; redo remains hypothetical'})


def costs_for_read(bridge,record):
    candidates=[]
    for message in record.get('messages',[]):
        if message.get('in_page'):
            candidates.append(research_snapshot(bridge,{**record,**message,'source':record['source'],'session':record['session']}))
    if not record.get('messages'):candidates=[research_snapshot(bridge,record)]
    if not candidates:return []
    selected=dict(max(candidates,key=lambda value:value['original_tokens']))
    bounds=[item['all_in_upper_bound_tokens'] for item in candidates if item.get('all_in_upper_bound_tokens') is not None]
    if bounds:selected['all_in_upper_bound_tokens']=max(bounds)
    return [selected]


def log_call(service,name,arguments,content,data,error=False):
    settings=service._config_data.get('usage',{})
    if settings is False:return
    if not isinstance(settings,dict):raise ValueError('usage config must be an object or false')
    if settings.get('enabled',True) is not True:return
    if name not in ('context_search','context_read'):return
    if __package__:
        from .privacy import redact
    else:from privacy import redact
    hits=data.get('results',[]) if isinstance(data,dict) else []
    read=data.get('record') if isinstance(data,dict) else None
    ids=[hit['record_id'] for hit in hits if 'record_id' in hit]
    snapshots=[]
    if read and not error:
        ids=list(dict.fromkeys([read['record_id']]+[m['record_id'] for m in read.get('messages',[]) if m.get('in_page')]))
        snapshots=[{key:value for key,value in snapshot.items() if key not in ('label','link')} for snapshot in costs_for_read(service.bridge,read)]
    text=''.join(block['text'] for block in content if block.get('type')=='text')
    query=redact(arguments['query'][:2000]) if settings.get('store_queries',False) is True and isinstance(arguments.get('query'),str) else None
    with service.bridge.transaction():
        service.bridge.db.execute('INSERT INTO usage_calls (tenant,employee,timestamp,tool,client,record_ids,response_chars,estimated_tokens,format,query_text,research,error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
          (*service.bridge.owner,datetime.now(timezone.utc).isoformat(),name,redact(str(getattr(service,'client_name','python-api')))[:128],json.dumps(ids),len(text),estimated_tokens(text),str(arguments.get('format','full'))[:64],query,json.dumps(snapshots),int(error)))


def report(bridge,price=None):
    if price is not None and (not math.isfinite(price) or price<0):raise ValueError('Price must be a finite nonnegative USD per million tokens')
    rows=[dict(row) for row in bridge.db.execute('SELECT * FROM usage_calls WHERE tenant=? AND employee=? ORDER BY id',bridge.owner)]
    conversations={};reads=[];read_conversations={};bounds={}
    for row in rows:
        if row['tool']=='context_read' and not row['error']:
            ids=set(json.loads(row['record_ids']))
            reads.append((row['id'],ids))
            for snapshot in json.loads(row['research']):
                item=incremental_credit(snapshot)
                if item.get('all_in_upper_bound_tokens') is not None:bounds[item['conversation']]=max(bounds.get(item['conversation'],0),item['all_in_upper_bound_tokens'])
                for rid in ids:read_conversations[rid]=item['conversation']
                previous=conversations.get(item['conversation'])
                if previous is None or item['original_tokens']>previous['original_tokens']:conversations[item['conversation']]=dict(item)
    searches=[row for row in rows if row['tool']=='context_search']
    unused=[row for row in searches if not any(sid>row['id'] and ids & set(json.loads(row['record_ids'])) for sid,ids in reads)]
    lookup=sum(row['estimated_tokens'] for row in rows)
    original=sum(item['original_tokens'] for item in conversations.values())
    for item in conversations.values():
        item['all_in_upper_bound_tokens']=bounds.get(item['conversation'])
        item['lookup_tokens']=0
        item['label']='Removed or unavailable conversation';item['link']=None
        try:
            locator=bridge.locate(item['record_id'])
            record=bridge.db.execute('SELECT session,source,line,timestamp,role FROM records WHERE tenant=? AND employee=? AND source=? AND line=?',(*bridge.owner,locator['source'],locator['line'])).fetchone()
            if record:
                decorated=bridge.decorate(dict(record));item['label']=decorated['source_label'];item['link']=decorated['link']
        except ValueError:pass
    unassigned=0
    for row in rows:
        ids=set(json.loads(row['record_ids']))
        target=None
        if row['tool']=='context_read' and not row['error']:
            target=next((read_conversations[rid] for rid in ids if rid in read_conversations),None)
        else:
            for sid,read_ids in reads:
                matched=ids & read_ids
                if sid>row['id'] and matched:
                    target=read_conversations[next(iter(matched))];break
        if target in conversations:conversations[target]['lookup_tokens']+=row['estimated_tokens']
        else:unassigned+=row['estimated_tokens']
    for item in conversations.values():
        item['estimated_tokens_avoided']=item['original_tokens']-item['lookup_tokens']
        if price is not None:item['estimated_usd_avoided']=item['estimated_tokens_avoided']*price/1e6
    result={'estimate':True,'lookup_method':TOKEN_METHOD,'conversations':list(conversations.values()),'original_research_tokens':original,'incremental_research_credit_tokens':original,'conservative_research_credit_tokens':original,'all_in_upper_bound_tokens':sum(bounds.values()) if len(bounds)==len(conversations) else None,'upper_bound_notice':'Including fixed context overhead; not used to calculate estimated avoided tokens. Unknown for visible-text estimates.','lookup_tokens':lookup,'unassigned_lookup_tokens':unassigned,'estimated_tokens_avoided':original-lookup,'calls':len(rows),'searches_without_read':len(unused),'empty_searches':sum(not json.loads(row['record_ids']) for row in searches),'assumptions':ASSUMPTIONS}
    if price is not None:result.update(uniform_usd_per_million_tokens=price,estimated_usd_avoided=(original-lookup)*price/1e6,price_notice='User-supplied uniform price across all token types; not a provider invoice or cache-specific tariff.')
    return result


def open_profile(directory,profile=None):
    if __package__:
        from .session_manager import Sessions
        from .local_profile import profile_directory,local_identity
        from .bridge import Bridge
    else:
        from session_manager import Sessions
        from local_profile import profile_directory,local_identity
        from bridge import Bridge
    manager=Sessions(profile_directory(directory,profile),profile_id=profile or 'default')
    data=json.loads(manager.config.read_text())
    return manager,Bridge(data['database'],*local_identity(data))


def main(savings=False):
    if __package__:from .session_manager import DEFAULT_ROOT,config_lock,atomic_write
    else:from session_manager import DEFAULT_ROOT,config_lock,atomic_write
    parser=argparse.ArgumentParser(description='Local estimates, never telemetry.')
    if not savings:
        parser.add_argument('action',nargs='?',choices=('show','clear','configure'),default='show')
        parser.add_argument('--no-query-text',action='store_true')
        parser.add_argument('--store-queries',action='store_true',help='Explicitly opt in to storing redacted query text locally')
        parser.add_argument('--disable',action='store_true');parser.add_argument('--enable',action='store_true')
    parser.add_argument('--directory',type=Path,default=DEFAULT_ROOT);parser.add_argument('--profile');parser.add_argument('--json',action='store_true');parser.add_argument('--explain',action='store_true');parser.add_argument('--price-per-million',type=float)
    args=parser.parse_args()
    if not savings and args.action!='configure' and (args.store_queries or args.no_query_text or args.disable or args.enable):parser.error('Use usage configure with logging or query-text flags')
    manager,bridge=open_profile(args.directory,args.profile)
    try:
        with config_lock(manager.config):
            if not savings and args.action=='clear':
                with bridge.transaction():
                    n=bridge.db.execute('DELETE FROM usage_calls WHERE tenant=? AND employee=?',bridge.owner).rowcount
                result={'deleted_calls':n}
            elif not savings and args.action=='configure':
                if args.disable and args.enable:parser.error('Choose --enable or --disable')
                data=json.loads(manager.config.read_text());settings=data.get('usage',{})
                if settings is False:settings={'enabled':False}
                if not isinstance(settings,dict):raise ValueError('usage config must be an object or false')
                data['usage']=settings
                if args.disable:settings['enabled']=False
                if args.enable:settings['enabled']=True
                if args.store_queries and args.no_query_text:parser.error('Choose --store-queries or --no-query-text')
                if args.store_queries:settings['store_queries']=True
                if args.no_query_text:settings['store_queries']=False
                atomic_write(manager.config,data);result={'usage':settings}
            else:result=report(bridge,args.price_per_million)
        if args.json:print(json.dumps(result,indent=2))
        elif 'estimated_tokens_avoided' in result:
            print('Estimate: '+str(result['estimated_tokens_avoided'])+' tokens avoided (can be negative).')
            print('Conservative lower-bound research credit (assumes a redo): '+str(result['original_research_tokens'])+'; lookup responses: '+str(result['lookup_tokens'])+' estimated tokens.')
            for item in result['conversations']:print(item['label']+': '+str(item['original_tokens'])+' conservative lower-bound credit, '+str(item['lookup_tokens'])+' lookup, '+str(item['estimated_tokens_avoided'])+' avoided ['+item['method']+'; '+item.get('quality','')+']')
            if result['all_in_upper_bound_tokens'] is not None:print('All-in upper bound (including fixed context overhead; not savings credit): '+str(result['all_in_upper_bound_tokens']))
            print(str(result['searches_without_read'])+' searches did not lead to a read.')
            if 'estimated_usd_avoided' in result:print('Estimated USD avoided: '+str(round(result['estimated_usd_avoided'],6)))
            print('Read ≠ verified reuse. Use --explain for methods and limits.')
            if args.explain:print('\n'.join(ASSUMPTIONS))
        else:print(json.dumps(result,indent=2))
    finally:bridge.db.close()


if __name__=='__main__':main()
