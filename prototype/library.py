# SPDX-License-Identifier: Apache-2.0
"""Inspect and remove explicitly approved local conversation data."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse, unquote
if __package__:
    from .bridge import Bridge
    from .local_profile import local_identity, profile_directory
    from .privacy import redact
    from .session_manager import Sessions, DEFAULT_ROOT, config_lock, atomic_write
else:
    from bridge import Bridge
    from local_profile import local_identity, profile_directory
    from privacy import redact
    from session_manager import Sessions, DEFAULT_ROOT, config_lock, atomic_write

PROVIDERS = ('chatgpt', 'claude', 'claude-code')


def discard_sources(data, bridge, paths, root):
    """Remove all index state; return owned working copies to unlink after commit."""
    copies = []
    removed = set(paths)
    excluded = set(data.get('excluded_transcripts', []))
    for source in removed:
        meta = data.get('sources', {}).pop(source, {})
        path = Path(source)
        if meta.get('provider') in ('chatgpt', 'claude') and path.parent.resolve().is_relative_to((Path(root)/'imports').resolve()):
            copies.append(path)
        elif meta.get('provider') == 'claude-code':
            excluded.add(source)
            cid = 'claude-code:'+str(meta.get('conversation_id'))
            data['excluded_conversations'] = sorted(set(data.get('excluded_conversations', [])) | {cid})
        bridge.remove_source(source, purge=True)
    data['approved_transcripts'] = sorted(set(data.get('approved_transcripts', [])) - removed)
    data['excluded_transcripts'] = sorted(excluded)
    for session in data.get('sessions', {}).values():
        paths = [session.get('transcript')] + [a['transcript'] for a in session.get('aliases', [])]
        if any(path in removed for path in paths):
            session['approved'] = False
    return copies


def list_conversations(data, bridge):
    rows = bridge.db.execute('SELECT source,MIN(session) AS session,MIN(timestamp) AS created_at,COUNT(*) AS messages FROM records WHERE tenant=? AND employee=? GROUP BY source', bridge.owner)
    counts = {row['source']:dict(row) for row in rows}
    result = []
    approved = set(data.get('approved_transcripts', []))
    for source in sorted(set(data.get('sources', {})) | set(counts)):
        if source not in approved:
            continue
        meta = data.get('sources', {}).get(source, {})
        row = counts.get(source, {})
        sid = meta.get('conversation_id') or row.get('session')
        title = meta.get('title') or data.get('sessions', {}).get(sid, {}).get('name') or sid or 'Untitled conversation'
        result.append({'provider':meta.get('provider', 'claude-code'), 'conversation_id':sid, 'title':redact(title), 'date':(meta.get('created_at') or row.get('created_at') or '')[:10] or None, 'message_count':row.get('messages', 0), 'link':meta.get('link')})
    return result


def remove(directory=DEFAULT_ROOT, conversation=None, provider=None):
    manager = Sessions(directory)
    with config_lock(manager.config):
        data = json.loads(manager.config.read_text())
        bridge = Bridge(data['database'], *local_identity(data))
        try:
            sources = data.get('sources', {})
            candidates = set()
            if provider:
                data.get('provider_accounts', {}).pop(provider, None)
                candidates = {source for source, meta in sources.items() if meta.get('provider') == provider}
                if provider == 'claude-code':
                    data['approved_projects'] = []
                    for entry in data.get('sessions', {}).values():
                        entry['approved'] = False
                        candidates.update(path for path in [entry.get('transcript')]+[a['transcript'] for a in entry.get('aliases', [])] if path)
                    candidates.update(row[0] for row in bridge.db.execute('SELECT DISTINCT source FROM records WHERE tenant=? AND employee=?', bridge.owner) if row[0] not in sources)
            else:
                selected_provider, cid = None, conversation
                if '://' in conversation:
                    url = urlparse(conversation)
                    parts = url.path.strip('/').split('/')
                    expected = {'chatgpt.com':('chatgpt','c'), 'chat.openai.com':('chatgpt','c'), 'claude.ai':('claude','chat')}.get(url.hostname)
                    if not expected or len(parts)!=2 or parts[0]!=expected[1]:
                        raise ValueError('Use a ChatGPT /c/<id> link, Claude /chat/<id> link, or conversation ID')
                    selected_provider, cid = expected[0], unquote(parts[1])
                candidates = {source for source, meta in sources.items() if meta.get('conversation_id')==cid and (not selected_provider or meta.get('provider')==selected_provider)}
                if not candidates and selected_provider is None:
                    candidates = {row[0] for row in bridge.db.execute('SELECT DISTINCT source FROM records WHERE tenant=? AND employee=? AND session=?', (*bridge.owner, cid))}
                if len(candidates)>1 and len({sources.get(p,{}).get('provider','claude-code') for p in candidates})>1:
                    raise ValueError('That ID exists in multiple providers. Supply the conversation link.')
            with bridge.transaction():
                copies = discard_sources(data, bridge, candidates, manager.root)
                atomic_write(manager.config, data)
            for path in copies:
                path.unlink(missing_ok=True)
            return {'conversations_removed':len(candidates), 'provider':provider, 'conversation':conversation}
        finally:
            bridge.db.close()


def inspect_library(directory=DEFAULT_ROOT):
    if __package__:
        from .mcp_server import ContextService
    else:
        from mcp_server import ContextService
    manager = Sessions(directory)
    service = ContextService(manager.config)
    try:
        with config_lock(manager.config):
            capture = service.refresh()
            conversations = list_conversations(service._config_data, service.bridge)
        return conversations, capture
    finally:
        if service.bridge:
            service.bridge.db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('list', 'stats', 'remove'):
        command = commands.add_parser(name)
        command.add_argument('--directory', type=Path, default=DEFAULT_ROOT)
        command.add_argument('--profile', help='Named local library')
        if name=='remove':
            selection = command.add_mutually_exclusive_group(required=True)
            selection.add_argument('--conversation', help='Conversation ID or provider conversation URL')
            selection.add_argument('--provider', choices=PROVIDERS)
    args = parser.parse_args(argv)
    try:
        args.directory = profile_directory(args.directory, args.profile)
        if args.profile:
            Sessions(args.directory, profile_id=args.profile)
        if args.command=='remove':
            result = remove(args.directory, args.conversation, args.provider)
        else:
            conversations, capture = inspect_library(args.directory)
            if args.command=='list':
                result = {'conversations':conversations}
            else:
                providers = {}
                for row in conversations:
                    item = providers.setdefault(row['provider'], {'conversations':0, 'messages':0})
                    item['conversations'] += 1
                    item['messages'] += row['message_count']
                result = {'conversations':len(conversations), 'messages':sum(r['message_count'] for r in conversations), 'providers':providers, 'capture_status':capture}
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, str(exc)+'\n')


if __name__=='__main__':
    main()
