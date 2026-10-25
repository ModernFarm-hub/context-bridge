# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""Run a disposable synthetic four-session demonstration."""
import json
from pathlib import Path
import tempfile
if __package__:
    from .bridge import Bridge
else:
    from bridge import Bridge

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    alice = Bridge(root / 'demo.db', 'example-company', 'alice')
    bob = Bridge(root / 'demo.db', 'example-company', 'bob')
    for owner, session, text in [
        (alice, 'confluence-research', 'Confluence policy: client data retention is 90 days. Source: https://confluence.example/policy/retention'),
        (alice, 'code-exploration', 'cleanup.py implements the retention policy using RETENTION_DAYS.'),
        (alice, 'client-request', 'Client requests an explanation of retention controls.'),
        (alice, 'deployment', 'Release procedure uses a staged rollout.'),
        (bob, 'bob-private', 'Confidential retention exception for another client.'),
    ]:
        path = root / (session + '.jsonl')
        path.write_text(json.dumps({'type': 'assistant', 'sessionId': session, 'timestamp': '2026-10-23T10:00:00Z', 'message': {'role': 'assistant', 'content': text}}) + '\n')
        owner.ingest(path)
    print('Alice searches across her sessions for retention:')
    print(json.dumps(alice.search('retention'), indent=2))
    assert alice.search('Confidential') == []
    print('\nPASS: Bob’s private context is excluded.')
    alice.db.close()
    bob.db.close()
