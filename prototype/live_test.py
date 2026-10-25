# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""Opt-in two-terminal test. Captures only the newly launched source session."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import uuid

if __package__:
    from .paths import data_home
else:
    from paths import data_home

ROOT = data_home() / 'live-test'


def write(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def prepare(root):
    root.mkdir(parents=True, exist_ok=True)
    config = root / 'enrollment.json'
    if not config.exists():
        write(config, {'tenant': 'live-test-company', 'employee': 'live-test-employee', 'database': str(root / 'context.db'), 'approved_transcripts': [], 'source_session': str(uuid.uuid4()), 'capture_enabled': True})
    settings = root / 'source-settings.json'
    command = shlex.join([sys.executable, str(Path(__file__).resolve()), '--directory', str(root), 'register'])
    write(settings, {'hooks': {event: [{'hooks': [{'type': 'command', 'command': command}]}] for event in ('SessionStart', 'Stop')}})
    mcp = root / 'reader-mcp.json'
    write(mcp, {'mcpServers': {'context-bridge-live': {'command': sys.executable, 'args': [str(Path(__file__).with_name('mcp_server.py')), '--config', str(config)]}}})
    return config, settings, mcp


def register(config, event):
    value = json.loads(config.read_text())
    if not value.get('capture_enabled') or event.get('session_id') != value['source_session']:
        return False
    transcript = event.get('transcript_path')
    if not isinstance(transcript, str) or not Path(transcript).is_absolute():
        raise ValueError('Missing absolute transcript path')
    value['approved_transcripts'] = [str(Path(transcript).resolve())]
    write(config, value)
    return True


def readiness(value):
    paths = value.get('approved_transcripts', [])
    ready = bool(paths) and all(Path(p).is_file() and Path(p).stat().st_size > 0 for p in paths)
    return bool(value.get('capture_enabled')) and ready


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT)
    parser.add_argument('mode', choices=['source', 'reader', 'register', 'status', 'revoke'])
    args = parser.parse_args()
    root = args.directory.resolve()
    if args.mode == 'register':
        register(root / 'enrollment.json', json.load(sys.stdin))
        return
    config, settings, mcp = prepare(root)
    value = json.loads(config.read_text())
    if args.mode == 'revoke':
        value['capture_enabled'] = False
        value['approved_transcripts'] = []
        write(config, value)
        # Withdraw stored rows now as well as on the next reader request.
        if __package__:
            from .mcp_server import ContextService
        else:
            from mcp_server import ContextService
        service = ContextService(config)
        service.refresh()
        service.bridge.db.close()
        print('Source capture revoked and its indexed records withdrawn. Existing Claude chat answers cannot be recalled.')
        return
    if args.mode == 'status':
        print(json.dumps({'capture_enabled': value['capture_enabled'], 'approved_transcripts': value['approved_transcripts'], 'files_exist': [Path(p).is_file() for p in value['approved_transcripts']], 'ready_for_reader': readiness(value)}, indent=2))
        return
    claude = shutil.which('claude')
    if not claude:
        candidate = Path.home() / '.local/bin/claude'
        if candidate.is_file():
            claude = str(candidate)
    if not claude:
        raise SystemExit('Claude Code not found. Add ~/.local/bin to PATH first.')
    if args.mode == 'source':
        if not value['capture_enabled']:
            raise SystemExit('This test was revoked. Use a new --directory for a new test.')
        if readiness(value):
            command = [claude, '--resume', value['source_session'], '--settings', str(settings)]
        else:
            # A SessionStart event can register a path before any transcript exists.
            # Starting explicitly again recovers a failed launch with a fresh ID.
            value['source_session'] = str(uuid.uuid4())
            value['approved_transcripts'] = []
            write(config, value)
            command = [claude, '--session-id', value['source_session'], '--settings', str(settings)]
        print('Starting a fresh source session. Only this test session will be approved for capture.', flush=True)
    else:
        if not readiness(value):
            raise SystemExit('Source is not ready. In Tab A, run source mode and send the test finding. Wait for its reply, then run status here. Reader requires ready_for_reader: true.')
        command = [claude, '--mcp-config', str(mcp), '--strict-mcp-config', '--tools', '', '--append-system-prompt', 'This is a Context Bridge integration test. Use only context_search and context_read for cross-session retrieval. If either tool is unavailable or fails, report the connection error. Never imitate a tool call or use shell/file access as a workaround.']
        print('Starting the reader. Search/read tools will refresh only the approved source transcript.', flush=True)
    raise SystemExit(subprocess.call(command, cwd=root))


if __name__ == '__main__':
    main()
