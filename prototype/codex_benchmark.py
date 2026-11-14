# SPDX-License-Identifier: Apache-2.0
"""Disposable Codex discovery scale check; no personal rollouts are read."""
import json
from pathlib import Path
import tempfile
import time
import zipfile
if __package__:
    from .imports import import_export
    from .mcp_server import ContextService
    from .session_manager import Sessions,atomic_write
else:
    from imports import import_export
    from mcp_server import ContextService
    from session_manager import Sessions,atomic_write


def p95(values):
    return sorted(values)[max(0,min(len(values)-1,int(len(values)*.95+.999999)-1))]


def codex_benchmark(files=200, bytes_per_file=5*1024*1024, approved=5, runs=30):
    if files<=approved or approved<1 or bytes_per_file<2048 or runs<3:
        raise ValueError('Use more rollout files than approved files, at least 2048 bytes, and 3 runs')
    with tempfile.TemporaryDirectory(prefix='context-bridge-codex-scale-') as directory:
        root=Path(directory).resolve()
        home=root/'codex'
        rollouts=home/'sessions/2026/11/14'
        rollouts.mkdir(parents=True)
        selected=str(root/'approved-project')
        rejected=str(root/'unapproved-project')
        names=[]
        for i in range(files):
            thread='synthetic-'+str(i)
            headers=[{'type':'session_meta','timestamp':'2026-11-14T12:00:00Z','payload':{'id':thread}},
                     {'type':'turn_context','payload':{'cwd':selected if i<approved else rejected}},
                     {'type':'response_item','ordinal':1,'payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'CODEX842 deployment approval'}]}}]
            prefix=''.join(json.dumps(row)+'\n' for row in headers).encode()
            tool_prefix=b'{"type":"response_item","payload":{"type":"custom_tool_call_output","output":"'
            suffix=b'"}}\n'
            with (rollouts/('rollout-2026-11-14-'+thread+'.jsonl')).open('wb') as out:
                out.write(prefix+tool_prefix)
                out.write(b'x'*(bytes_per_file-len(prefix)-len(tool_prefix)-len(suffix)))
                out.write(suffix)
            names.append({'id':thread,'thread_name':'Synthetic thread '+str(i)})
        (home/'session_index.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in names))
        archive=root/'export.zip'
        with zipfile.ZipFile(archive,'w') as out:
            out.writestr('conversations.json',json.dumps([{'uuid':'baseline','name':'Baseline','chat_messages':[{'uuid':'m','sender':'human','text':'BASELINE842 recorded decision'}]}]))
        import_export('claude',archive,root/'library')
        manager=Sessions(root/'library')
        service=ContextService(manager.config)
        def search():
            start=time.perf_counter()
            value=service.call('context_search',{'query':'BASELINE842'})
            assert value['results']
            return (time.perf_counter()-start)*1000
        try:
            search()
            baseline=[search() for _ in range(runs)]
            data=json.loads(manager.config.read_text())
            data['approved_codex_projects']=[{'home':str(home),'path':selected}]
            atomic_write(manager.config,data)
            first=search()  # Includes classification and ingestion of five approved files.
            steady=[search() for _ in range(runs)]
            cached=service.bridge.db.execute('SELECT COUNT(*) FROM codex_classifications WHERE tenant=? AND employee=?',service.bridge.owner).fetchone()[0]
            source_count=sum(meta.get('provider')=='codex' for meta in service._config_data.get('sources',{}).values())
            delta=p95(steady)-p95(baseline)
            return {'files':files,'bytes_per_file':bytes_per_file,'total_rollout_bytes':files*bytes_per_file,
                    'approved_files':source_count,'cached_unapproved_files':cached,'runs':runs,
                    'no_codex_p95_ms':round(p95(baseline),3),'first_refresh_ms':round(first,3),
                    'steady_codex_p95_ms':round(p95(steady),3),'p95_over_baseline_ms':round(delta,3),
                    'target_extra_ms':10,'target_passed':delta<=10 and source_count==approved and cached==files-approved,
                    'scope':'Same synthetic web library, before and after project approval; first refresh includes discovery and initial ingestion. Tails are excluded tool output. Steady-state includes directory scanning, stat checks and incremental ingestion checks.'}
        finally:
            if service.bridge:
                service.bridge.db.close()
