# SPDX-License-Identifier: Apache-2.0
"""Disposable synthetic end-to-end MCP search benchmark. No real chats are read."""
import argparse
import json
from pathlib import Path
import statistics
import tempfile
import time
import zipfile
if __package__:
    from .session_manager import Sessions, atomic_write
    from .mcp_server import ContextService
    from .imports import import_export
else:
    from session_manager import Sessions, atomic_write
    from mcp_server import ContextService
    from imports import import_export


def percentile(values, fraction):
    return sorted(values)[max(0, min(len(values)-1, int(len(values)*fraction + .999999)-1))]


def benchmark(messages=None, runs=30, files=5000, min_messages=2, max_messages=40):
    if (messages is not None and messages < 100) or runs < 3 or files<1 or min_messages<1 or max_messages<min_messages:
        raise ValueError('Use at least 100 messages and 3 runs')
    with tempfile.TemporaryDirectory(prefix='context-bridge-benchmark-') as tmp:
        root = Path(tmp)
        manager = Sessions(root/'library')
        import_ms = reimport_ms = None
        if messages is None:
            conversations, messages = [], 0
            for i in range(files):
                mapping, previous = {}, None
                for j in range(min_messages+i % (max_messages-min_messages+1)):
                    mid = f'{i}-{j}'
                    content = f'Planning discussion {i}. Customer records require retention review. Kafka retries use exponential backoff and a dead letter queue. Deployment needs approval.'
                    if i % 100 == 0 and j==0:
                        content += ' TARGET842 decision: retry budget is five attempts.'
                    mapping[mid] = {'parent':previous, 'message':{'id':mid, 'author':{'role':'user' if j%2==0 else 'assistant'}, 'content':{'content_type':'text','parts':[content]}}}
                    previous = mid
                    messages += 1
                conversations.append({'id':f'synthetic-{i}', 'title':f'Kafka planning discussion {i}', 'create_time':1792540800, 'current_node':previous, 'mapping':mapping})
            archive = root/'export.zip'
            with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('conversations.json',json.dumps(conversations))
            del conversations
            start = time.perf_counter()
            import_export('chatgpt',archive,manager.root)
            import_ms = (time.perf_counter()-start)*1000
            start = time.perf_counter()
            import_export('chatgpt',archive,manager.root)
            reimport_ms = (time.perf_counter()-start)*1000
            config = json.loads(manager.config.read_text())
            transcript = Path(config['approved_transcripts'][0])
        else:
            files = 1
            transcript = root/'synthetic.jsonl'
            with transcript.open('w') as stream:
                for i in range(messages):
                    content = f'Planning discussion {i}. Customer records require retention review. Kafka retries use exponential backoff and a dead letter queue. Deployment needs approval.'
                    if i % 1000 == 0:
                        content += ' TARGET842 decision: retry budget is five attempts.'
                    stream.write(json.dumps({'type':'user', 'uuid':str(i), 'sessionId':'synthetic', 'message':{'role':'user', 'content':content}})+'\n')
            config = json.loads(manager.config.read_text())
            config['approved_transcripts'] = [str(transcript)]
            atomic_write(manager.config, config)
        service = ContextService(manager.config)
        try:
            start = time.perf_counter()
            service.call('context_search', {'query':'TARGET842'})
            initial = (time.perf_counter()-start)*1000
            elapsed = []
            queries = ['TARGET842', 'Kafka retries', 'retention review', 'unmatched999', 'deployment approval']
            for i in range(runs):
                start = time.perf_counter()
                service.call('context_search', {'query':queries[i % len(queries)]})
                elapsed.append((time.perf_counter()-start)*1000)
            with transcript.open('a') as stream:
                stream.write(json.dumps({'type':'user','uuid':'appended','sessionId':'synthetic','message':{'role':'user','content':'FRESH842 newly recorded decision'}})+'\n')
            start = time.perf_counter()
            fresh = service.call('context_search', {'query':'FRESH842'})
            append_ms = (time.perf_counter()-start)*1000
            p95 = percentile(elapsed, .95)
            return {'files':files,'messages':messages,'messages_per_file_min':min_messages if files>1 else messages,'messages_per_file_max':max_messages if files>1 else messages,'import_ms':round(import_ms,2) if import_ms is not None else None,'unchanged_reimport_ms':round(reimport_ms,2) if reimport_ms is not None else None,'runs':runs,'initial_ingestion_and_search_ms':round(initial,2),'search_refresh_p50_ms':round(statistics.median(elapsed),2),'search_refresh_p95_ms':round(p95,2),'search_refresh_max_ms':round(max(elapsed),2),'append_refresh_search_ms':round(append_ms,2),'append_visible':bool(fresh['results']),'target_ms':300,'target_passed':p95 < 300 and bool(fresh['results']),'scope':'Local lexical search including per-file freshness checks and cached profile metadata; initial server query and export import/reimport are reported separately.'}
        finally:
            if service.bridge:
                service.bridge.db.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--messages',type=int,help='Legacy single-file benchmark; omit for the realistic multi-file layout')
    parser.add_argument('--files',type=int,default=5000)
    parser.add_argument('--min-messages',type=int,default=2)
    parser.add_argument('--max-messages',type=int,default=40)
    parser.add_argument('--runs',type=int,default=30)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=benchmark(args.messages,args.runs,args.files,args.min_messages,args.max_messages)
    payload=json.dumps(result,indent=2)
    if args.output:
        args.output.write_text(payload+'\n')
    print(payload)
    if not result['target_passed']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
