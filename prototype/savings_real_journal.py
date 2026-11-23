# SPDX-License-Identifier: Apache-2.0
"""Durable call journal with explicit, permanently charged abandonment."""
from datetime import datetime,timezone
from decimal import Decimal
import json
from pathlib import Path
import re
if __package__:
    from .session_manager import atomic_write
    from .savings_real_costs import rates,amount,reservation,BudgetExceeded
    from .savings_real_transport import DefinitelyNotSent
else:
    from session_manager import atomic_write
    from savings_real_costs import rates,amount,reservation,BudgetExceeded
    from savings_real_transport import DefinitelyNotSent

class SessionCapReached(RuntimeError):pass

class Journal:
    """Write-ahead reservations count uncertain calls. Never automatically retry them."""
    def __init__(self,root,cap,max_usd=None,prices=None,grader_prices=None,load=True,session_cap=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.cap=cap;self.session_cap=session_cap
        self.max_usd=Decimal(str(max_usd)) if max_usd is not None else None
        self.prices=prices or rates();self.grader_prices=grader_prices or self.prices
        self.ledger=self.root.parent/'abandonments.json'
        self.abandoned=json.loads(self.ledger.read_text()) if self.ledger.exists() else {}
        self.costs={k:self.abandoned_cost(v) for k,v in self.abandoned.items()};self.unknown=set();self.stop_reason=None
        if not load:return
        for path in self.root.glob('*.json'):
            record=json.loads(path.read_text());key=record['key']
            if key in self.abandoned:continue
            if record.get('definitely_not_sent'):
                self.costs[key]=Decimal(0);continue
            if 'response' not in record:self.unknown.add(key)
            else:
                try:self.costs[key]=self.usage_cost(key,record['response'].get('usage'))
                except ValueError:self.unknown.add(key);continue
                if self.costs[key]>Decimal(record.get('reserved_usd','Infinity')):self.stop_reason='reservation_exceeded'
    def price_set(self,key):return self.grader_prices if key.startswith('grader-') else self.prices
    def usage_cost(self,key,usage):
        if not isinstance(usage,dict):raise ValueError('Missing recorded usage; cost unknown')
        if any(Decimal(v)>0 for v in self.price_set(key).values()) and not {'input_tokens','output_tokens'}<=set(usage):raise ValueError('Incomplete recorded usage; cost unknown')
        return amount(usage,self.price_set(key))
    @staticmethod
    def abandoned_cost(event):
        value=Decimal(event['reserved_usd'])
        if not value.is_finite() or value<0:raise ValueError('Invalid abandoned reservation')
        return value
    def abandonments(self):return [self.abandoned[k] for k in sorted(self.abandoned)]
    def validate_abandon(self,key):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,240}',key):raise ValueError('Supply the exact safe reservation key')
        path=self.root/(key+'.json')
        if not path.is_file():raise ValueError('Unknown reservation key: '+key)
        record=json.loads(path.read_text())
        if record.get('key')!=key:raise ValueError('Reservation key/file mismatch')
        if 'response' in record:raise ValueError('Refusing to abandon a call with a recorded response')
        if record.get('definitely_not_sent'):raise ValueError('This call was definitely not sent; cannot mark it possibly billed')
        self.abandoned_cost(record)
        return record
    def abandon(self,key,who,why):
        if not isinstance(who,str) or not who.strip() or not isinstance(why,str) or not why.strip():raise ValueError('Explicit --abandon-by and --abandon-reason are required')
        record=self.validate_abandon(key)
        if key in self.abandoned:return self.abandoned[key]
        event={'key':key,'reserved_usd':record['reserved_usd'],'who':who.strip(),'when':datetime.now(timezone.utc).isoformat(),'why':why.strip(),'possibly_billed':True,'never_refunded':True,
            'retry_key':None if key.endswith('--attempt-1') else key+'--attempt-1'}
        # Ledger is authoritative and written first. A crash before annotating
        # the call record cannot erase its permanent conservative charge.
        self.abandoned[key]=event;atomic_write(self.ledger,self.abandoned)
        self.costs[key]=self.abandoned_cost(event);self.unknown.discard(key)
        record['abandoned']=event;atomic_write(self.root/(key+'.json'),record)
        return event
    def resolve(self,key):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,240}',key):raise ValueError('Invalid call key')
        if key not in self.abandoned:return key
        retry=self.abandoned[key]['retry_key']
        if retry is None or retry in self.abandoned:raise RuntimeError('The one explicitly authorized resend is exhausted; run incomplete')
        if not (self.root/(key+'.json')).is_file():raise RuntimeError('Abandoned reservation missing; no new request permitted')
        return retry
    def records(self):
        result=[]
        for path in sorted(self.root.glob('*.json')):
            record=json.loads(path.read_text())
            if record['key'] in self.abandoned:record['abandoned']=self.abandoned[record['key']]
            result.append(record)
        return result
    def status(self):
        abandoned=sum((self.abandoned_cost(v) for v in self.abandoned.values()),Decimal(0))
        spent=sum(self.costs.values(),Decimal(0))
        return {'max_usd':float(self.max_usd) if self.max_usd is not None else None,'recorded_usd':float(spent),'recorded_response_usd':float(spent-abandoned),'abandoned_reserved_usd':float(abandoned),'abandoned_calls':self.abandonments(),'unresolved_calls':len(self.unknown),'stop_reason':self.stop_reason,'basis':'Supplied rates, with abandoned reservations permanently charged in full in addition to successful response costs; no assumed cache hits.'}
    def call(self,key,body,provider):
        if self.stop_reason=='reservation_exceeded':raise BudgetExceeded('Prior usage exceeded reservation; incomplete run, no new calls')
        logical_key=key
        key=self.resolve(key)
        if key!=logical_key:
            original=json.loads((self.root/(logical_key+'.json')).read_text())
            if original['request']!=body:raise ValueError('Abandoned request differs; resend must be identical')
        path=self.root/(key+'.json')
        if path.exists():
            record=json.loads(path.read_text())
            if record['request']!=body:raise ValueError('Resume request differs from frozen request')
            if record.get('definitely_not_sent'):raise DefinitelyNotSent('Pre-send retry exhausted; no automatic retry on resume')
            if key in self.unknown or 'response' not in record:raise RuntimeError('Unresolved provider call '+key+'; inspect before any retry (it may have been billed)')
            return record['response']
        session=re.fullmatch(r'([AB]-.+-(?:original|baseline|reuse)-[0-9]+-)[0-9]{2}(?:--attempt-1)?',logical_key)
        if session and self.session_cap is not None and len(list(self.root.glob(session.group(1)+'*.json')))>=self.session_cap:raise SessionCapReached('Original per-session request cap reached, including abandoned attempts')
        if len(list(self.root.glob('*.json')))>=self.cap:raise RuntimeError('Hard total call cap reached')
        if self.unknown:raise RuntimeError('Unresolved provider calls; unknown billed usage blocks new requests')
        prices=self.price_set(key)
        try:reserved=reservation(body,prices)
        except BudgetExceeded:
            self.stop_reason='request_input_bound';raise
        if self.max_usd is not None and sum(self.costs.values(),Decimal(0))+reserved>self.max_usd:
            self.stop_reason='max_usd'
            raise BudgetExceeded('Hard dollar cap: next request reservation would exceed --max-usd; incomplete run')
        record={'logical_key':logical_key,'reserved_usd':str(reserved),'key':key,'request':body,'reserved_at':datetime.now(timezone.utc).isoformat()}
        atomic_write(path,record);self.unknown.add(key)
        try:response=provider(body)
        except DefinitelyNotSent as exc:
            record.update(error=type(exc).__name__,definitely_not_sent=True,transport=getattr(provider,'last_transport',{}))
            self.costs[key]=Decimal(0);self.unknown.discard(key);atomic_write(path,record);raise
        except Exception as exc:
            record.update(error=type(exc).__name__,transport=getattr(provider,'last_transport',{}));atomic_write(path,record);raise
        record.update(transport=getattr(provider,'last_transport',{}),response=response,recorded_at=datetime.now(timezone.utc).isoformat());atomic_write(path,record)
        cost=self.usage_cost(key,response.get('usage'));self.costs[key]=cost;self.unknown.discard(key)
        record['recorded_usd']=str(cost);atomic_write(path,record)
        if cost>reserved:
            self.stop_reason='reservation_exceeded'
            raise BudgetExceeded('Provider usage exceeded the conservative reservation; incomplete run, no further requests')
        return response
    def tool_results(self,key,results=None):
        key=self.resolve(key)
        path=self.root/(key+'.json');record=json.loads(path.read_text())
        if results is not None:
            record['tool_results']=results;atomic_write(path,record)
        return record.get('tool_results')
    def raw(self,path):
        with Path(path).open('w') as f:
            for record in self.records():f.write(json.dumps(record)+'\n')
