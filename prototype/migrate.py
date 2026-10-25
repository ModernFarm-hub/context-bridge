# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""Explicit same-computer migration; original data is never deleted."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import tempfile
if __package__:
    from .session_manager import DEFAULT_ROOT, Sessions, atomic_write
else:
    from session_manager import DEFAULT_ROOT, Sessions, atomic_write
if __package__:
    from .local_profile import local_identity
else:
    from local_profile import local_identity



def migrate(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError('Destination already exists; choose an unused --to directory. No files overwritten.')
    config_name = 'enrollment.json' if (source / 'enrollment.json').exists() else 'profile.json'
    data = json.loads((source / config_name).read_text())
    if not isinstance(data.get('sessions'), dict):
        raise ValueError('Not a supported local profile')
    library, profile = local_identity(data)
    data['library_id'], data['profile_id'] = library, profile
    old_db = Path(data['database']).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.context-bridge-migrate-', dir=destination.parent) as tmp:
        stage = Path(tmp) / 'manager'
        stage.mkdir(mode=0o700)
        if old_db.exists():
            original = sqlite3.connect(old_db.as_uri() + '?mode=ro', uri=True)
            copied = sqlite3.connect(stage / 'context.db')
            try:
                original.backup(copied)
            finally:
                copied.close(); original.close()
        data['database'] = str(destination / 'context.db')
        atomic_write(stage / config_name, data)
        stage.rename(destination)
    Sessions(destination)
    return {'destination': str(destination), 'sessions': len(data['sessions']), 'source_preserved': True, 'note': 'Original transcript files remain in place; migrated state references them on this computer. Restart readers and reopen sources through the new manager.'}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from', dest='source', type=Path, required=True)
    parser.add_argument('--to', dest='destination', type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    try:
        result = migrate(args.source, args.destination)
    except (ValueError, OSError, KeyError, sqlite3.Error) as exc:
        parser.exit(1, str(exc) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
