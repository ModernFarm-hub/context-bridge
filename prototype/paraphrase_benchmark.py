# SPDX-License-Identifier: Apache-2.0
"""Frozen synthetic paraphrases; conversation-level ranks, not message duplicates."""
import json
import hashlib
from pathlib import Path
import tempfile
import time
import zipfile
if __package__:
    from .imports import import_export
    from .session_manager import Sessions, atomic_write
    from .mcp_server import ContextService
else:
    from imports import import_export
    from session_manager import Sessions, atomic_write
    from mcp_server import ContextService


def paraphrase_benchmark(model=None):
    fixture = Path(__file__).parent/'evals/paraphrases.json'
    cases = json.loads(fixture.read_text())
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        archive = root/'export.zip'
        conversations = [{'id':c['id'],'title':c['title'],'current_node':'m','mapping':{'m':{'parent':None,'message':{'id':'m','author':{'role':'user'},'content':{'content_type':'text','parts':[c['body']]}}}}} for c in cases]
        with zipfile.ZipFile(archive,'w') as out:
            out.writestr('conversations.json',json.dumps(conversations))
        import_export('chatgpt',archive,root/'library')
        manager = Sessions(root/'library')
        if model:
            data = json.loads(manager.config.read_text())
            data['retrieval'] = {'mode':'hybrid','model_directory':str(Path(model).resolve()),'minimum_similarity':.35}
            atomic_write(manager.config,data)
        service = ContextService(manager.config)
        ranks, details = [], []
        start = time.perf_counter()
        try:
            for case in cases:
                hits = service.call('context_search',{'query':case['query'],'limit':20})['results']
                ids = list(dict.fromkeys(h['link'].rsplit('/',1)[-1] for h in hits))
                rank = ids.index(case['id'])+1 if case['id'] in ids else None
                ranks.append(rank)
                details.append({'id':case['id'],'query':case['query'],'rank':rank})
        finally:
            if service.bridge:
                service.bridge.db.close()
        return {'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),'conversations':len(cases),'queries':len(cases),'mode':'hybrid' if model else 'bm25','top_1':sum(r==1 for r in ranks)/len(ranks),'top_5':sum(r is not None and r<=5 for r in ranks)/len(ranks),'mrr_at_20':sum(1/r if r else 0 for r in ranks)/len(ranks),'seconds':round(time.perf_counter()-start,3),'cases':details}
