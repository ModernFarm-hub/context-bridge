# SPDX-License-Identifier: Apache-2.0
"""Explicit local import of provider exports; never extracts ZIP members to disk."""
import argparse
if __package__:
    from .privacy import redact, REDACTION_VERSION
else:
    from privacy import redact, REDACTION_VERSION
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import zipfile
from urllib.parse import quote
if __package__:
    from .session_manager import Sessions, DEFAULT_ROOT, config_lock, atomic_write
    from .bridge import Bridge
else:
    from session_manager import Sessions, DEFAULT_ROOT, config_lock, atomic_write
    from bridge import Bridge
if __package__:
    from .local_profile import local_identity
else:
    from local_profile import local_identity


MAX_EXPORT_BYTES = 512 * 1024 * 1024


def iso(value):
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')
        except (ValueError, OSError, OverflowError):
            return None
    return value if isinstance(value, str) and value else None


def text_blocks(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ''
    return '\n'.join(block['text'] for block in content if isinstance(block, dict) and block.get('type') == 'text' and isinstance(block.get('text'), str))


def export_conversations(path):
    try:
        with zipfile.ZipFile(path) as archive:
            entries = [item for item in archive.infolist() if PurePosixPath(item.filename).name == 'conversations.json' and not item.is_dir() and not item.filename.startswith('__MACOSX/')]
            if len(entries) != 1:
                raise ValueError('Export must contain exactly one conversations.json. Use the original provider export ZIP.')
            entry = entries[0]
            if entry.file_size > MAX_EXPORT_BYTES:
                raise ValueError('conversations.json exceeds the 512 MB import limit. Split the export before importing.')
            with archive.open(entry) as stream:
                payload = stream.read(MAX_EXPORT_BYTES + 1)
            if len(payload) > MAX_EXPORT_BYTES:
                raise ValueError('Export expands beyond the 512 MB import limit.')
            data = json.loads(payload)
    except (zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid export ZIP or conversations.json; download a fresh official export.') from exc
    if not isinstance(data, list):
        raise ValueError('conversations.json must contain a list of conversations.')
    return data


def chatgpt_messages(conversation):
    mapping = conversation.get('mapping')
    if not isinstance(mapping, dict) or not mapping:
        return []
    current = conversation.get('current_node')
    if current is None:
        # Older exports without current_node: choose one latest leaf, not every branch.
        leaves = [(key, node) for key, node in mapping.items() if isinstance(node, dict) and not node.get('children')]
        def time_of(pair):
            message = pair[1].get('message') or {}
            value = message.get('create_time')
            return value if isinstance(value, (int, float)) else float('-inf')
        current = max(leaves, key=time_of)[0] if leaves else None
    branch, seen = [], set()
    while current is not None:
        if not isinstance(current, str) or current in seen or current not in mapping:
            raise ValueError('Conversation has a cyclic or incomplete current branch.')
        seen.add(current)
        node = mapping[current]
        if not isinstance(node, dict):
            raise ValueError('Conversation contains an invalid mapping node.')
        branch.append(node.get('message'))
        current = node.get('parent')
    result = []
    for message in reversed(branch):
        if not isinstance(message, dict):
            continue
        author = message.get('author') or {}
        role = author.get('role')
        if role not in ('user', 'assistant') or message.get('recipient') not in (None, 'all'):
            continue
        metadata = message.get('metadata') or {}
        if metadata.get('is_visually_hidden_from_conversation'):
            continue
        content = message.get('content') or {}
        if not isinstance(content, dict):
            continue
        body = '\n'.join(part for part in content.get('parts', []) if isinstance(part, str)) if content.get('content_type') in ('text', 'multimodal_text') else ''
        if body.strip():
            result.append((str(message.get('id') or hashlib.sha256(body.encode()).hexdigest()), role, body, iso(message.get('create_time'))))
    return result


def claude_messages(conversation):
    result = []
    for message in conversation.get('chat_messages') or []:
        if not isinstance(message, dict):
            continue
        role = {'human': 'user', 'assistant': 'assistant'}.get(message.get('sender'))
        if role is None:
            continue
        body = text_blocks(message['content']) if isinstance(message.get('content'), list) else text_blocks(message.get('text'))
        if body.strip():
            result.append((str(message.get('uuid') or hashlib.sha256(body.encode()).hexdigest()), role, body, iso(message.get('created_at'))))
    return result


def redact_managed_copies(data, root):
    """Upgrade owned normalized copies; never modify original exports/transcripts."""
    if data.get('redaction_version', 0) >= REDACTION_VERSION:
        return False
    for source, meta in data.get('sources', {}).items():
        meta['title'] = redact(meta.get('title'))
        provider, cid = meta.get('provider'), meta.get('conversation_id')
        if provider not in ('chatgpt','claude') or not isinstance(cid,str):
            continue
        path = Path(source)
        expected = Path(root)/'imports'/provider/(hashlib.sha256(cid.encode()).hexdigest()+'.jsonl')
        if path!=expected or path.is_symlink() or not path.is_file():
            continue
        original = path.read_bytes()
        output = []
        changed = False
        for raw in original.splitlines(keepends=True):
            try:
                item = json.loads(raw)
                message = item.get('message', {}) if isinstance(item,dict) else {}
                body = message.get('content') if isinstance(message,dict) else None
                filtered = redact(body)
                if isinstance(body,str) and filtered!=body:
                    message['content'] = filtered
                    raw = json.dumps(item,ensure_ascii=False).encode()+ (b'\n' if raw.endswith(b'\n') else b'')
                    changed = True
            except (ValueError,UnicodeDecodeError):
                pass
            output.append(raw)
        if changed:
            payload = b''.join(output)
            temp = path.with_suffix('.tmp')
            temp.write_bytes(payload); temp.chmod(0o600); temp.replace(path)
            meta['content_sha256'] = hashlib.sha256(payload).hexdigest()
    for session in data.get('sessions', {}).values():
        if isinstance(session.get('name'),str):
            session['name'] = redact(session['name'])
    data['redaction_version'] = REDACTION_VERSION
    return True


def import_export(provider, archive, directory=DEFAULT_ROOT, progress=None):
    if provider not in ('chatgpt', 'claude'):
        raise ValueError('Use chatgpt or claude for a provider export')
    conversations = export_conversations(archive)
    manager = Sessions(directory)
    count, messages, skipped, present = 0, 0, [], set()
    authoritative = True
    if __package__:
        from .library import discard_sources
    else:
        from library import discard_sources
    with config_lock(manager.config):
        data = json.loads(manager.config.read_text())
        approved = set(data.get('approved_transcripts', []))
        bridge = Bridge(data['database'], *local_identity(data))
        try:
            with bridge.transaction():
                redact_managed_copies(data, manager.root)
                for position, conversation in enumerate(conversations, 1):
                    if progress and (position == 1 or position % 100 == 0 or position == len(conversations)):
                        progress(position, len(conversations))
                    if not isinstance(conversation, dict):
                        authoritative = False
                        skipped.append({'conversation':position, 'reason':'Invalid conversation object'})
                        continue
                    cid = (conversation.get('id') or conversation.get('conversation_id')) if provider=='chatgpt' else conversation.get('uuid')
                    if not isinstance(cid, str) or not cid or len(cid)>200:
                        authoritative = False
                        skipped.append({'conversation':position, 'reason':'Missing or invalid conversation ID'})
                        continue
                    # Present-but-malformed conversations are not deleted as if
                    # they were absent from the export.
                    present.add(cid)
                    try:
                        records = chatgpt_messages(conversation) if provider=='chatgpt' else claude_messages(conversation)
                    except (ValueError, TypeError, AttributeError) as exc:
                        skipped.append({'conversation':position, 'reason':str(exc) if isinstance(exc, ValueError) else 'Malformed message structure'})
                        continue
                    title = conversation.get('title') if provider=='chatgpt' else conversation.get('name')
                    title = title if isinstance(title, str) and title.strip() else 'Untitled conversation'
                    created = iso(conversation.get('create_time') if provider=='chatgpt' else conversation.get('created_at'))
                    path = manager.root/'imports'/provider/(hashlib.sha256(cid.encode()).hexdigest()+'.jsonl')
                    source = str(path)
                    sid = provider+':'+cid
                    payload = ''.join(json.dumps({'type':role, 'uuid':mid, 'sessionId':sid, 'timestamp':timestamp, 'message':{'role':role, 'content':redact(body)}}, ensure_ascii=False)+'\n' for mid,role,body,timestamp in records)
                    digest = hashlib.sha256(payload.encode()).hexdigest()
                    metadata = {'provider':provider, 'title':redact(title), 'conversation_id':cid, 'created_at':created, 'link':('https://chatgpt.com/c/' if provider=='chatgpt' else 'https://claude.ai/chat/')+quote(cid,safe=''), 'content_sha256':digest}
                    previous = data.get('sources', {}).get(source, {})
                    if previous.get('content_sha256')!=digest or not path.is_file():
                        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                        temp = path.with_suffix('.tmp')
                        temp.write_text(payload, encoding='utf-8'); temp.chmod(0o600); temp.replace(path)
                    data.setdefault('sources', {})[source] = metadata
                    approved.add(source)
                    bridge.set_source(source, metadata, resolved=True)
                    bridge.ingest(source, resolved=True)
                    count += 1; messages += len(records)
                data['approved_transcripts'] = sorted(approved)
                removed = {source for source,meta in data.get('sources', {}).items() if authoritative and meta.get('provider')==provider and meta.get('conversation_id') not in present}
                copies = discard_sources(data, bridge, removed, manager.root)
                atomic_write(manager.config, data)
            for path in copies:
                path.unlink(missing_ok=True)
        finally:
            bridge.db.close()
    return {'provider':provider, 'conversations_imported':count, 'messages_imported':messages, 'conversations_removed':len(removed), 'pruning_skipped':not authoritative, 'skipped':skipped}


class ProjectSelection(dict):
    def __init__(self):
        super().__init__()
        self.roots = {}


def project_preview(projects_root):
    base = Path(projects_root).expanduser().resolve()
    projects = ProjectSelection()
    if not base.is_dir():
        return projects
    for path in sorted(base.rglob('*.jsonl')):
        if path.is_symlink() or not path.resolve().is_relative_to(base):
            continue
        relative = path.relative_to(base)
        project = relative.parts[0] if len(relative.parts) > 1 else '(root)'
        projects.setdefault(project, []).append(path.resolve())
        projects.roots[project] = base if project=='(root)' else base/project
    return projects


def code_metadata(path):
    title, created, session = None, None, path.stem
    with path.open('rb') as stream:
        for raw in stream:
            try:
                item = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                continue
            if not isinstance(item, dict):
                continue
            if item.get('type') == 'ai-title':
                candidate = item.get('aiTitle') or item.get('title')
                if isinstance(candidate, str) and candidate.strip():
                    title = candidate
            if item.get('type') in ('user', 'assistant'):
                created = created or iso(item.get('timestamp'))
                candidate = item.get('sessionId')
                if isinstance(candidate, str) and candidate:
                    session = candidate
    return {'provider': 'claude-code', 'title': redact(title or 'Claude Code session ' + session[:8]), 'created_at': created, 'conversation_id': session, 'link': None}


def discover_projects(data, bridge):
    """Discover only explicitly approved directories, on every refresh."""
    known = set(data.get('sources', {}))
    excluded = set(data.get('excluded_transcripts', []))
    new = []
    for entry in data.get('approved_projects', []):
        root = Path(entry['path'])
        if not root.is_dir() or root.is_symlink():
            continue
        paths = root.rglob('*.jsonl') if entry.get('recursive', True) else root.glob('*.jsonl')
        for path in paths:
            source = str(path)
            if source in known or source in excluded or path.is_symlink():
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                continue
            source = str(resolved)
            if source in known or source in excluded:
                continue
            metadata = code_metadata(resolved)
            if 'claude-code:'+metadata['conversation_id'] in data.get('excluded_conversations', []):
                continue
            data.setdefault('sources', {})[source] = metadata
            bridge.set_source(source, metadata, resolved=True)
            known.add(source)
            new.append(source)
    if new:
        data['approved_transcripts'] = sorted(set(data.get('approved_transcripts', [])) | set(new))
    return len(new)


def import_code(projects, directory=DEFAULT_ROOT):
    manager = Sessions(directory)
    imported = 0
    with config_lock(manager.config):
        data = json.loads(manager.config.read_text())
        approved = set(data.get('approved_transcripts', []))
        excluded = set(data.get('excluded_transcripts', []))
        roots = {entry['path']:entry for entry in data.get('approved_projects', [])}
        bridge = Bridge(data['database'], *local_identity(data))
        try:
            with bridge.transaction():
                for name, paths in projects.items():
                    # The preview approves each displayed project directory, so
                    # future sessions in that directory become searchable too.
                    if paths:
                        root = getattr(projects, 'roots', {}).get(name) or Path(os.path.commonpath([str(Path(p).parent) for p in paths])).resolve()
                        roots[str(root)] = {'name':name, 'path':str(root), 'recursive':name!='(root)'}
                    for path in paths:
                        path = Path(path).resolve()
                        metadata = code_metadata(path)
                        data.setdefault('sources', {})[str(path)] = metadata
                        approved.add(str(path)); excluded.discard(str(path))
                        cid = 'claude-code:'+metadata['conversation_id']
                        data['excluded_conversations'] = [key for key in data.get('excluded_conversations', []) if key!=cid]
                        bridge.set_source(path, metadata, resolved=True)
                        bridge.ingest(path, resolved=True)
                        imported += 1
                data['approved_transcripts'] = sorted(approved)
                data['approved_projects'] = sorted(roots.values(), key=lambda entry:entry['path'])
                data['excluded_transcripts'] = sorted(excluded)
                atomic_write(manager.config, data)
        finally:
            bridge.db.close()
    return {'provider':'claude-code', 'transcripts_imported':imported, 'projects_imported':len(projects), 'new_sessions_auto_discovered':True}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('provider', choices=('chatgpt', 'claude', 'claude-code'))
    parser.add_argument('archive', type=Path, nargs='?')
    parser.add_argument('--directory', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--projects-root', type=Path, default=Path.home() / '.claude/projects')
    parser.add_argument('--project', action='append', help='Import only a listed project (repeatable)')
    parser.add_argument('--yes', action='store_true', help='Explicitly approve importing listed Claude Code projects')
    args = parser.parse_args()
    try:
        if args.provider == 'claude-code':
            projects = project_preview(args.projects_root)
            if args.project:
                missing = set(args.project) - set(projects)
                if missing:
                    parser.error('Unknown project selection: ' + ', '.join(sorted(missing)))
                for key in list(projects):
                    if key not in args.project:
                        del projects[key]
            print('Claude Code project preview (nothing imported yet):')
            for project, paths in projects.items():
                print(f'  {project}: {len(paths)} transcripts (including future sessions)')
            if not projects:
                print('No projects found.'); return
            if not args.yes:
                if not sys.stdin.isatty() or input('Approve these project directories, including future sessions? [y/N] ').strip().casefold() not in ('y', 'yes'):
                    print('Preview only. Repeat with --yes to approve this list.'); return
            result = import_code(projects, args.directory)
        else:
            if args.archive is None:
                parser.error('Supply the official export ZIP file')
            result = import_export(args.provider, args.archive, args.directory, progress=lambda current,total: print(f'Importing {args.provider}: {current}/{total} conversations', file=sys.stderr))
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
