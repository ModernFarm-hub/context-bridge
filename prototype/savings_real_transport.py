# SPDX-License-Identifier: Apache-2.0
"""Outcome-blind transport/configuration support. No outcome files are inspected."""
from datetime import datetime,timezone
from decimal import Decimal
import hashlib
import http.client
import json
import math
from pathlib import Path
if __package__:
    from .session_manager import atomic_write
else:
    from session_manager import atomic_write

AMENDMENT='2026-11-22-outcome-blind-transport'
LEGACY_RUNNER_SHA256='d00e51bd497d05ac40aca97dca98f5914074cd8219e1d7a188ba55f3faa91810'

class DefinitelyNotSent(OSError):pass

class Provider:
    def __init__(self,key,read_timeout=300,connect_timeout=30):
        self.key=key;self.read_timeout=read_timeout;self.connect_timeout=connect_timeout;self.last_transport={}
    def __call__(self,body):
        self.last_transport={'connect_failures':[],'read_timeout_seconds':self.read_timeout,'connect_timeout_seconds':self.connect_timeout}
        payload=json.dumps(body).encode()
        for attempt in range(2):
            conn=None
            try:
                conn=http.client.HTTPSConnection('api.anthropic.com',timeout=self.connect_timeout)
                conn.connect()  # No HTTP headers or body have been sent here.
            except (OSError,http.client.HTTPException) as exc:
                if conn:conn.close()
                self.last_transport['connect_failures'].append({'attempt':attempt+1,'error':type(exc).__name__,'definitely_not_sent':True})
                if attempt==0:continue
                self.last_transport['phase']='connect_failed_not_sent'
                raise DefinitelyNotSent('Both pre-send connection attempts failed; no Messages request sent') from exc
            break
        try:
            conn.sock.settimeout(self.read_timeout)
            self.last_transport['phase']='possibly_sent'
            conn.request('POST','/v1/messages',body=payload,headers={'x-api-key':self.key,'anthropic-version':'2023-06-01','content-type':'application/json'})
            response=conn.getresponse()
            data=response.read()
            if not 200<=response.status<300:raise OSError('Messages HTTP status '+str(response.status)+'; no automatic retry')
            result=json.loads(data)
            self.last_transport['phase']='response_received'
            return result
        finally:conn.close()

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def configuration(root,read_timeout=None,connect_timeout=None,adoption=None):
    """Freeze transport separately; original run.json is never rewritten."""
    root=Path(root);path=root/'infrastructure.json'
    old=json.loads(path.read_text()) if path.exists() else None
    read=read_timeout if read_timeout is not None else (old['read_timeout_seconds'] if old else 300)
    connect=connect_timeout if connect_timeout is not None else (old['connect_timeout_seconds'] if old else 30)
    if any(not math.isfinite(x) or x<=0 for x in (read,connect)):raise ValueError('Transport timeouts must be finite and positive')
    folder=Path(__file__).parent
    frozen={'amendment':AMENDMENT,'read_timeout_seconds':read,'connect_timeout_seconds':connect,
        'runner_sha256':digest(folder/'savings_real.py'),'transport_sha256':digest(__file__),'journal_sha256':digest(folder/'savings_real_journal.py')}
    if old:
        if any(old.get(k)!=v for k,v in frozen.items()):raise ValueError('Frozen infrastructure configuration differs')
        return old
    runfile=root/'run.json'
    if runfile.exists():
        run=json.loads(runfile.read_text())
        if run['runner_sha256']!=frozen['runner_sha256']:
            if adoption is None:raise ValueError('Legacy resume requires explicit offline --abandon-unresolved adoption of the registered infrastructure amendment')
            if run['runner_sha256']!=LEGACY_RUNNER_SHA256:raise ValueError('Unsupported legacy runner; cannot change frozen experiment')
            frozen['adoption']={**adoption,'when':datetime.now(timezone.utc).isoformat(),'original_runner_sha256':run['runner_sha256'],'original_run_sha256':digest(runfile)}
    atomic_write(path,frozen);return frozen

def validate_resume(previous,current,infra,runfile):
    if previous==current:return
    modified=dict(previous);modified['runner_sha256']=current['runner_sha256']
    adoption=infra.get('adoption',{})
    if modified!=current or previous['runner_sha256']!=LEGACY_RUNNER_SHA256 or adoption.get('original_runner_sha256')!=previous['runner_sha256'] or adoption.get('original_run_sha256')!=digest(runfile):
        raise ValueError('Resume configuration differs; only the registered transport runner migration is permitted')

def disclosure(summary,journal,infra,records):
    """Accounting/report annotations only; primary analysis stays unchanged."""
    abandoned=journal.abandonments()
    if journal.unknown:summary['claim_eligible']=False
    summary['infrastructure']={**infra,'abandoned_calls':abandoned,'abandoned_reserved_usd':float(sum((journal.abandoned_cost(r) for r in abandoned),start=Decimal(0))),
        'connect_failures':sum(len(r.get('transport',{}).get('connect_failures',[])) for r in records),
        'rule':'Abandon/retry does not by itself disqualify a run. All tasks, arms and repetitions must complete and all existing accuracy/token/safety criteria must pass; abandonments must be disclosed. Unknown abandoned token usage is not invented or substituted into the token metric.'}
    for phase in ('A','B','grader'):
        cost=sum((journal.abandoned_cost(r) for r in abandoned if r['key'].startswith(phase+'-')),start=Decimal(0))
        row=summary['user_priced_costs'][phase]
        row['abandoned_reserved_usd']=float(cost);row['total_usd']+=float(cost)
    return summary

def append_report(root,summary):
    infra=summary['infrastructure'];path=Path(root)/'savings-real.md'
    lines=['','## Infrastructure amendment and abandoned requests','',infra['rule'],'',
        'Frozen connect/read timeouts (seconds): '+str(infra['connect_timeout_seconds'])+' / '+str(infra['read_timeout_seconds']),
        '', 'Conservatively charged abandoned reservations: USD '+str(infra['abandoned_reserved_usd']), '',
        '| Exact attempt key | Permanently charged USD | Who | When (UTC) | Why |','|---|---:|---|---|---|']
    def cell(value):return str(value).replace('|','\\|').replace('\n',' ')
    for event in infra['abandoned_calls']:lines.append('| '+' | '.join(cell(event[k]) for k in ('key','reserved_usd','who','when','why'))+' |')
    if not infra['abandoned_calls']:lines.append('| None | 0 | | | |')
    lines+=['','These charges remain even if a later response or cheaper retry is recorded. Abandoned token usage is unknown; no token counters are fabricated.','']
    path.write_text(path.read_text()+'\n'.join(lines))

def maintain_run(root,keys,who,why,read_timeout=None,connect_timeout=None,data=None):
    """Explicit offline maintenance: no results, summaries, libraries or providers."""
    if not keys or not who or not who.strip() or not why or not why.strip():raise ValueError('Exact --abandon-unresolved key, --abandon-by and --abandon-reason are required')
    if len(keys)!=len(set(keys)):raise ValueError('Duplicate abandonment key')
    import fcntl
    import re
    if __package__:from .savings_real_journal import Journal
    else:from savings_real_journal import Journal
    root=Path(root);runfile=root/'run.json'
    if not runfile.is_file():raise ValueError('Existing run.json required; no run created')
    with (root/'RUNNING').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another benchmark process holds this run')
        run=json.loads(runfile.read_text());folder=Path(__file__).parent
        data=Path(data or folder/'evals/savings-real')
        expected={'tasks_sha256':digest(data/'tasks.json'),'manifest_sha256':digest(data/'manifest.json'),
            **{key:digest(folder/name) for key,name in [('analysis_sha256','savings_real_analysis.py'),('grader_sha256','savings_real_grading.py'),('decision_parser_sha256','reuse_policy.py'),('costs_sha256','savings_real_costs.py')]}}
        if any(run.get(k)!=v for k,v in expected.items()):raise ValueError('Protected experiment hashes differ; cannot adopt infrastructure amendment')
        prereg=(data/'PREREGISTRATION.md').read_text()
        for name in ('savings_real.py','savings_real_transport.py','savings_real_journal.py'):
            hashes=re.findall(r'^- prototype/'+re.escape(name)+r': `([a-f0-9]{64})`',prereg,re.M)
            if not hashes or hashes[-1]!=digest(folder/name):raise ValueError('Infrastructure amendment hash mismatch: '+name)
        journal=Journal(root/'calls',run['total_cap'],run['max_usd'],run['prices'],run.get('grader_prices'),load=False)
        for key in keys:journal.validate_abandon(key)
        infra=configuration(root,read_timeout,connect_timeout,adoption={'who':who.strip(),'why':why.strip(),'outcome_blind':True})
        events=[journal.abandon(key,who,why) for key in keys]
        return {'amendment':AMENDMENT,'abandoned_calls':events,'transport':infra,'no_requests_sent':True,'notice':'Offline maintenance only. Permanent charges are carried into the next resumed summary/report. Resume separately with the original frozen experiment settings.'}
