# SPDX-License-Identifier: Apache-2.0
"""Import completion: opt-in setup and local embedding warmup."""
import json
import os
from pathlib import Path
import subprocess
import sys
if __package__:
    from .session_manager import Sessions,config_lock,atomic_write
else:
    from session_manager import Sessions,config_lock,atomic_write


def backfill(root):
    if __package__:
        from .mcp_server import ContextService
    else:
        from mcp_server import ContextService
    service=ContextService(Sessions(root).config)
    try:
        with config_lock(service.config):
            service.refresh()
            if service.bridge.retrieval_settings.get('mode')!='hybrid':
                return
            service.bridge.search('local context embedding backfill')
    finally:
        if service.bridge:
            service.bridge.db.close()


def finish_import(root):
    """Called after commit and outside the import lock, for every provider."""
    config=Sessions(root).config
    data=json.loads(config.read_text())
    if data.get('retrieval',{}).get('mode')!='hybrid':
        return
    print('Embedding imported conversations locally…',file=sys.stderr,flush=True)
    runtime=data.get('retrieval_python',sys.executable)
    try:
        if os.path.abspath(runtime)!=os.path.abspath(sys.executable):
            subprocess.run([runtime,str(Path(__file__).resolve()),'--backfill',str(Path(root).resolve())],check=True,stdout=sys.stderr)
        else:
            backfill(root)
    except (OSError,subprocess.CalledProcessError,ImportError,ValueError,RuntimeError) as exc:
        raise RuntimeError('Import saved, but embedding failed. Run context-bridge semantic enable to repair the local runtime, then retry the import.') from exc
    print('Local embeddings ready.',file=sys.stderr,flush=True)


def offer_semantic(root):
    """Only the CLI offers setup; automated imports never ask or download."""
    if not sys.stdin.isatty():
        return
    config=Sessions(root).config
    with config_lock(config):
        data=json.loads(config.read_text())
        if data.get('semantic_offer') or data.get('retrieval',{}).get('mode')=='hybrid':
            return
        # Save before waiting for input so interruption/EOF cannot repeat the offer.
        data['semantic_offer']='shown'
        atomic_write(config,data)
    try:
        answer=input('Enable semantic search for better recall? Downloads about 90 MB, runs locally. [y/N] ').strip().casefold()
    except (EOFError,OSError):
        answer='n'
    with config_lock(config):
        data=json.loads(config.read_text())
        data['semantic_offer']='accepted' if answer in ('y','yes') else 'declined'
        atomic_write(config,data)
    if answer in ('y','yes'):
        if __package__:
            from .configure_semantic import enable
            from .setup_semantic import DEFAULT_MODEL
        else:
            from configure_semantic import enable
            from setup_semantic import DEFAULT_MODEL
        enable(root,DEFAULT_MODEL)


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1]!='--backfill':
        raise SystemExit('Internal import backfill worker requires --backfill DIRECTORY')
    backfill(Path(sys.argv[2]))
