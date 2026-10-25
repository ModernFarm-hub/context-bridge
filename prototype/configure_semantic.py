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


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--model', type=Path, default=DEFAULT_MODEL)
    parser.add_argument('--retrieval-config', type=Path, help='Use settings from a frozen model comparison')
    parser.add_argument('--disable', action='store_true')
    args = parser.parse_args()
    settings = json.loads(args.retrieval_config.read_text()) if args.retrieval_config else None
    mode = configure(args.directory, args.model, args.disable, settings)
    print('Configured ' + mode + ' retrieval. Source approvals are unchanged. Open a fresh reader to use the updated runtime.')
