# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""Prepare persistent, synthetic transcripts and a Claude MCP configuration."""
if __package__:
    from .paths import data_home
else:
    from paths import data_home
import argparse
import json
import os
from pathlib import Path
import shlex
import sys


def setup(directory):
    os.umask(0o077)
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    for session, body in [('research', 'Confluence: Project Cedar retention period is 90 days. Synthetic policy source: https://confluence.example/cedar/retention'), ('code', 'Project Cedar retention cleanup uses cleanup.py and RETENTION_DAYS.'), ('client', 'The Cedar client asks how retention is enforced.'), ('deployment', 'Project Cedar releases use staged rollout.')]:
        path = root / (session + '.jsonl')
        if not path.exists():
            path.write_text(json.dumps({'type': 'assistant', 'sessionId': 'demo-' + session, 'timestamp': '2026-10-23T10:00:00Z', 'message': {'role': 'assistant', 'content': body}}) + '\n')
        paths.append(str(path))
    config = root / 'enrollment.json'
    if not config.exists():
        config.write_text(json.dumps({'tenant': 'demo-company', 'employee': 'demo-employee', 'database': str(root / 'context.db'), 'approved_transcripts': paths}, indent=2) + '\n')
    server = Path(__file__).with_name('mcp_server.py').resolve()
    definition = {'mcpServers': {'context-bridge-demo': {'command': sys.executable, 'args': [str(server), '--config', str(config)]}}}
    mcp = root / 'mcp-demo.json'
    mcp.write_text(json.dumps(definition, indent=2) + '\n')
    command = ['claude', '--mcp-config', str(mcp)]
    print('Demo ready. In this same project folder, launch Claude with:')
    print(shlex.join(command))
    print('\nThen ask: Use context_search to find Project Cedar retention findings from my other sessions. Cite the session and source line.')
    return config


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', default=str(data_home() / 'demo'))
    setup(parser.parse_args().directory)
