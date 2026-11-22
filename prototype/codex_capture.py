# SPDX-License-Identifier: Apache-2.0
"""Opt-in Codex rollout import. Read originals without rewriting them."""
import hashlib
import json
import os
from pathlib import Path
import re
if __package__:
    from .privacy import redact
    from .session_manager import Sessions, config_lock, atomic_write, DEFAULT_ROOT
    from .local_profile import local_identity
    from .bridge import Bridge
else:
    from privacy import redact
    from session_manager import Sessions, config_lock, atomic_write, DEFAULT_ROOT
    from local_profile import local_identity
    from bridge import Bridge


def codex_home():
    return Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex'))).expanduser().resolve()


def user_text(text):
    # Known host-injected user-role envelopes are metadata, never conversation.
    if re.match(r'^\s*#\s*AGENTS\.md\b',text,flags=re.I) and not re.search(r'</INSTRUCTIONS\s*>',text,flags=re.I):
        return ''
    tags = ('environment_context','INSTRUCTIONS','user_instructions','system-reminder',
            'skills_instructions','permissions','collaboration_mode','external_codex_apps_open_page',
            'in-app-browser-context','turn_aborted')
    for tag in tags:
        text = re.sub(r'<'+re.escape(tag)+r'\b[^>]*>.*?</'+re.escape(tag)+r'\s*>', '', text, flags=re.S|re.I)
        # Incomplete injected envelopes are excluded conservatively.
        text = re.sub(r'<'+re.escape(tag)+r'\b[^>]*>.*$', '', text, flags=re.S|re.I)
    text = re.sub(r'^\s*#\s*AGENTS\.md(?: instructions)?[^\n]*\n?', '', text, flags=re.I)
    if text.lstrip().startswith(('You are a coding agent', 'The user provided the following instructions')):
        return ''
    return text.strip()


def message(item, thread):
    if item.get('type') != 'response_item':
        return None
    payload = item.get('payload')
    if not isinstance(payload,dict) or payload.get('type')!='message' or payload.get('role') not in ('user','assistant'):
        return None
    role = payload['role']
    content = payload.get('content')
    if not isinstance(content,list):
        return None
    body = '\n'.join(block['text'] for block in content if isinstance(block,dict) and block.get('type') in ('input_text','output_text') and isinstance(block.get('text'),str))
    body = user_text(body) if role=='user' else body
    if not body.strip():
        return None
    return {'type':role,'sessionId':thread,'uuid':payload.get('id') or item.get('ordinal'), 'timestamp':item.get('timestamp'), 'message':{'role':role,'content':body}}


def titles(home):
    result = {}
    path = Path(home)/'session_index.jsonl'
    if path.is_file():
        with path.open('rb') as stream:
            for raw in stream:
                try:
                    item = json.loads(raw)
                    if isinstance(item,dict) and isinstance(item.get('id'),str) and isinstance(item.get('thread_name'),str):
                        result[item['id']] = redact(item['thread_name'])
                except (ValueError,UnicodeDecodeError):
                    continue
    return result


HEADER_TYPE = re.compile(rb'"type"\s*:\s*"([^"]+)"')


def metadata(path, names=None):
    """Classify from headers only. Never decode message bodies for a preview."""
    thread, cwd, created = None, None, None
    with Path(path).open('rb') as stream:
        for raw in stream:
            kind = HEADER_TYPE.search(raw)
            if not kind or kind.group(1) not in (b'session_meta',b'turn_context'):
                continue
            try:
                item = json.loads(raw)
            except (ValueError,UnicodeDecodeError):
                continue
            if not isinstance(item,dict) or not isinstance(item.get('payload'),dict):
                continue
            payload = item['payload']
            if item.get('type')=='session_meta' and isinstance(payload.get('id'),str) and payload['id']:
                thread = thread or payload['id']
                created = created or item.get('timestamp') or payload.get('timestamp')
            if item.get('type')=='turn_context' and isinstance(payload.get('cwd'),str) and os.path.isabs(payload['cwd']):
                try:
                    cwd = cwd or str(Path(payload['cwd']).expanduser().resolve())
                except (ValueError,OSError):
                    continue
            if thread and cwd:
                break
    if not thread or not cwd:
        return None
    return {'provider':'codex','conversation_id':thread,'title':(names or {}).get(thread) or 'New conversation', 'created_at':created,'project':cwd,'link':'codex://threads/'+thread}


def title_excerpt(path, thread):
    """Read conversation text only after its project passes the approval filter."""
    with Path(path).open('rb') as stream:
        for raw in stream:
            if b'"response_item"' not in raw:
                continue
            try:
                item = json.loads(raw)
            except (ValueError,UnicodeDecodeError):
                continue
            value = message(item,thread) if isinstance(item,dict) else None
            if value and value['type']=='user':
                return ' '.join(redact(value['message']['content']).split())[:60]
    return 'New conversation'


def preview(home=None):
    home = Path(home or codex_home()).resolve()
    projects = {}
    sessions = home/'sessions'
    if sessions.is_dir() and not sessions.is_symlink():
        for path in sorted(sessions.rglob('rollout-*.jsonl')):
            if path.is_symlink() or not path.resolve().is_relative_to(sessions):
                continue
            try:
                meta = metadata(path)
            except (OSError,ValueError):
                continue
            if meta:
                projects.setdefault(meta['project'],[]).append(path.resolve())
    return projects


def digest(thread):
    return hashlib.sha256(('codex:'+thread).encode()).hexdigest()


def discover(data, bridge):
    entries = data.get('approved_codex_projects',[])
    if not entries:
        return 0
    known = set(data.get('sources',{}))
    excluded = set(data.get('web_exclusions',{}).get('codex',[]))
    excluded_paths = set(data.get('excluded_transcripts',[]))
    added = []
    # Only metadata of unregistered rollout files is inspected to classify projects.
    for home in sorted({entry['home'] for entry in entries}):
        allowed = {entry['path'] for entry in entries if entry['home']==home}
        root = Path(home)/'sessions'
        if not root.is_dir() or root.is_symlink():
            continue
        names = None
        epoch = hashlib.sha256(json.dumps([sorted(allowed),sorted(excluded)],sort_keys=True).encode()).hexdigest()
        for path in root.rglob('rollout-*.jsonl'):
            if str(path) in known or str(path) in excluded_paths or path.is_symlink():
                continue
            source = str(path)
            try:
                info = path.stat()
            except OSError:
                continue
            signature = [info.st_size,info.st_mtime_ns,info.st_ino]
            if bridge._codex_classifications.get(source)==(signature,epoch):
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(root) or str(resolved) in known:
                continue
            source = str(resolved)
            try:
                meta = metadata(resolved)
            except (OSError,ValueError):
                meta = None
            if not meta or meta['project'] not in allowed or digest(meta['conversation_id']) in excluded:
                bridge.db.execute('INSERT OR REPLACE INTO codex_classifications VALUES (?,?,?,?,?)',(*bridge.owner,source,json.dumps(signature),epoch))
                bridge._codex_classifications[source] = (signature,epoch)
                continue
            if names is None:
                names = titles(home)
            meta['title'] = names.get(meta['conversation_id']) or title_excerpt(resolved,meta['conversation_id'])
            bridge.db.execute('DELETE FROM codex_classifications WHERE tenant=? AND employee=? AND source=?',(*bridge.owner,source))
            bridge._codex_classifications.pop(source,None)
            source = str(resolved)
            data.setdefault('sources',{})[source] = meta
            bridge.set_source(source,meta,resolved=True)
            known.add(source)
            added.append(source)
    if added:
        data['approved_transcripts'] = sorted(set(data.get('approved_transcripts',[]))|set(added))
    return len(added)


def import_codex(projects, directory=DEFAULT_ROOT, home=None):
    home = str(Path(home or codex_home()).resolve())
    manager = Sessions(directory)
    with config_lock(manager.config):
        data = json.loads(manager.config.read_text())
        entries = {(entry['home'],entry['path']) for entry in data.get('approved_codex_projects',[])}
        entries.update((home,project) for project in projects)
        data['approved_codex_projects'] = [{'home':h,'path':p} for h,p in sorted(entries)]
        bridge = Bridge(data['database'],*local_identity(data))
        try:
            with bridge.transaction():
                added = discover(data,bridge)
                approved = set(data.get('approved_transcripts',[]))
                for source,meta in data.get('sources',{}).items():
                    if source in approved and meta.get('provider')=='codex':
                        bridge.ingest(source,resolved=True)
                atomic_write(manager.config,data)
        finally:
            bridge.db.close()
    if __package__:
        from .import_lifecycle import finish_import
    else:
        from import_lifecycle import finish_import
    finish_import(manager.root)
    return {'provider':'codex','transcripts_imported':added,'projects_imported':len(projects),'new_sessions_auto_discovered':True}
