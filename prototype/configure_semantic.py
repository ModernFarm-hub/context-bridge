# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""Enable/disable local hybrid search without changing source approvals."""
import argparse
import json
import os
from pathlib import Path
import sys
if __package__:
    from .session_manager import Sessions, DEFAULT_ROOT, config_lock, atomic_write
else:
    from session_manager import Sessions, DEFAULT_ROOT, config_lock, atomic_write
if __package__:
    from .setup_semantic import DEFAULT_MODEL
else:
    from setup_semantic import DEFAULT_MODEL


def configure(root, directory, disable=False, settings=None):
    sessions = Sessions(root)
    if settings is not None:
        if settings.get('mode') != 'hybrid':
            raise ValueError('Frozen settings must select hybrid retrieval')
        directory = settings['model_directory']
    if not disable:
        if __package__:
            from .semantic import model
        else:
            from semantic import model
        embedder = model(str(Path(directory).resolve()))
        embedder.chunks('Local embedding health check.', (settings or {}).get('token_window', 200), (settings or {}).get('sentence_chunks', False))
        threshold = (settings or {}).get('minimum_similarity', .35)
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
            raise ValueError('Invalid similarity threshold')
        if not isinstance((settings or {}).get('gate_lexical', False), bool):
            raise ValueError('Invalid lexical gate')
        embedder.encode(['Local embedding health check.'])
    with config_lock(sessions.config):
        data = json.loads(sessions.config.read_text())
        if disable:
            data['retrieval'] = {'mode': 'lexical'}
            data.pop('retrieval_python', None)
        else:
            data['retrieval'] = {'mode': 'hybrid', 'model_directory': str(Path(directory).resolve()), 'minimum_similarity': .35}
            if settings is not None:
                data['retrieval'].update({k: settings[k] for k in ('minimum_similarity', 'token_window', 'gate_lexical', 'sentence_chunks') if k in settings})
            data['retrieval_python'] = sys.executable
        atomic_write(sessions.config, data)
    Sessions(root)  # regenerate the reader config with the correct runtime
    return data['retrieval']['mode']


def enable(root, directory, from_source=None):
    """Explicit opt-in setup; package/model downloads never receive chat text."""
    import importlib.util
    import subprocess
    import time
    import venv
    start = time.perf_counter()
    checkout = Path(from_source).expanduser().resolve() if from_source else Path(__file__).resolve().parents[1]
    if from_source:
        import re
        manifest = checkout/'pyproject.toml'
        if not manifest.is_file() or not re.search(r'''name\s*=\s*['"]context-bridge-local['"]''',manifest.read_text()):
            raise SystemExit('--from-source must name the Context Bridge checkout containing pyproject.toml')
    missing = [name for name in ('numpy', 'onnxruntime', 'tokenizers') if importlib.util.find_spec(name) is None]
    if missing:
        runtime = Sessions(root).root/'semantic-runtime'
        print('Installing optional local semantic runtime (downloads packages, no chat upload).', file=sys.stderr)
        venv.EnvBuilder(with_pip=True).create(runtime)
        python = runtime/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        if (checkout/'pyproject.toml').is_file():
            target = str(checkout)+'[semantic]'
        else:
            if __package__:
                from . import __version__
            else:
                from __init__ import __version__
            target = 'context-bridge-local[semantic]=='+__version__
        try:
            subprocess.run([str(python), '-m', 'pip', 'install', '--upgrade', 'pip'],check=True,stdout=sys.stderr)
        except subprocess.CalledProcessError as exc:
            raise SystemExit('Could not upgrade pip inside the semantic runtime. Check network/package-index access and retry semantic enable.') from exc
        try:
            subprocess.run([str(python), '-m', 'pip', 'install', target],check=True,stdout=sys.stderr)
        except subprocess.CalledProcessError as exc:
            if (checkout/'pyproject.toml').is_file():
                message = 'Could not install the semantic extra from '+str(checkout)+'. Check the pip error above and retry: context-bridge semantic enable --from-source '+str(checkout)
            else:
                message = ('Could not install '+target+'. This version may not be on PyPI (for example, an unreleased or non-editable source install). '
                           'Use your source checkout instead: context-bridge semantic enable --from-source /path/to/context-bridge '
                           '(the folder containing pyproject.toml), or install its extra with: python3 -m pip install "/path/to/context-bridge[semantic]".')
            raise SystemExit(message) from exc
        subprocess.run([str(python), str(Path(__file__).resolve()), 'enable', '--directory', str(root), '--model', str(directory)],check=True)
        return
    if __package__:
        from .setup_semantic import download_model
        from .mcp_server import ContextService
    else:
        from setup_semantic import download_model
        from mcp_server import ContextService
    print('Verifying/downloading pinned MiniLM weights; conversations remain local.',file=sys.stderr)
    directory = download_model(directory)
    configure(root,directory)
    service = ContextService(Sessions(root).config)
    try:
        service.refresh()
        # A neutral query builds every approved record's chunks, even when no hit is returned.
        service.bridge.search('local context embedding backfill')
        count = service.bridge.db.execute('SELECT COUNT(*) FROM embeddings WHERE tenant=? AND employee=?',service.bridge.owner).fetchone()[0]
    finally:
        if service.bridge:
            service.bridge.db.close()
    size = sum(p.stat().st_size for p in Path(directory).rglob('*') if p.is_file())
    print(json.dumps({'mode':'hybrid','model_bytes':size,'embedding_records':count,'elapsed_seconds':round(time.perf_counter()-start,2),'offline_search':True,'runtime':sys.executable}))


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=('enable','disable'))
    parser.add_argument('--from-source',type=Path,help='Install optional dependencies from this checkout when the version is not on PyPI')
    parser.add_argument('--profile')
    parser.add_argument('--directory', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--model', type=Path, default=DEFAULT_MODEL)
    parser.add_argument('--retrieval-config', type=Path, help='Use settings from a frozen model comparison')
    parser.add_argument('--disable', action='store_true')
    args = parser.parse_args()
    if __package__:
        from .local_profile import profile_directory
    else:
        from local_profile import profile_directory
    args.directory = profile_directory(args.directory,args.profile)
    if args.profile:
        Sessions(args.directory,profile_id=args.profile)
    if args.action=='enable':
        enable(args.directory,args.model,args.from_source)
        raise SystemExit(0)
    args.disable = args.disable or args.action=='disable'
    settings = json.loads(args.retrieval_config.read_text()) if args.retrieval_config else None
    mode = configure(args.directory, args.model, args.disable, settings)
    print('Configured ' + mode + ' retrieval. Source approvals are unchanged. Open a fresh reader to use the updated runtime.')
