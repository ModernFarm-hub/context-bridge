# SPDX-License-Identifier: Apache-2.0
"""Conservative export-account comparison; persist fingerprints, not email addresses."""
import hashlib
import json
from pathlib import PurePosixPath
import zipfile


class AccountMismatch(ValueError):
    pass


def export_account(path, conversations):
    identifiers = {'account_ids':set(), 'user_ids':set(), 'emails':set()}
    def add(group, value):
        if isinstance(value, (str,int)) and str(value).strip():
            value = str(value).strip()
            if group=='emails':
                value = value.casefold()
            identifiers[group].add(hashlib.sha256(value.encode()).hexdigest())
    def collect(value, context='user'):
        if isinstance(value,list):
            for entry in value:
                collect(entry,context)
        if not isinstance(value,dict):
            return
        for key, item in value.items():
            if key in ('account_id','account_uuid','organization_id'):
                add('account_ids',item)
            elif key in ('user_id','user_uuid'):
                add('user_ids',item)
            elif key in ('id','uuid'):
                add('account_ids' if context=='account' else 'user_ids',item)
            elif key in ('email','email_address'):
                add('emails',item)
            elif key in ('account','accounts','organization'):
                collect(item,'account')
            elif key in ('user','users','profile'):
                collect(item,'user')
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            name = PurePosixPath(entry.filename).name.casefold()
            if entry.is_dir() or entry.filename.startswith('__MACOSX/') or name not in ('user.json','users.json','account.json','accounts.json','profile.json'):
                continue
            if entry.file_size>2*1024*1024:
                raise ValueError('Account metadata exceeds the 2 MB limit; cannot safely identify the export account')
            try:
                metadata = json.loads(archive.read(entry))
            except (ValueError,UnicodeDecodeError) as exc:
                raise ValueError('Invalid account metadata; download a fresh provider export before replacing this library') from exc
            collect(metadata,'account' if name.startswith('account') else 'user')
    for conversation in conversations:
        if not isinstance(conversation,dict):
            continue
        # A conversation id/uuid is never an account identifier.
        for key in ('account_id','account_uuid','user_id','user_uuid'):
            group = 'account_ids' if key.startswith('account') else 'user_ids'
            add(group,conversation.get(key))
    result = {key:sorted(values) for key,values in identifiers.items() if values}
    return result or None


def check_account(data, provider, incoming, confirmed=False):
    previous = data.get('provider_accounts', {}).get(provider)
    existing = any(meta.get('provider')==provider for meta in data.get('sources',{}).values())
    reason = None
    if previous and incoming:
        for field in ('account_ids','user_ids','emails'):
            if previous.get(field) and incoming.get(field):
                if previous[field] != incoming[field]:
                    reason = 'The export appears to belong to a different account.'
                break
        else:
            reason = 'The export account cannot be compared with the account already recorded.'
    elif previous and not incoming:
        reason = 'This export has no account identifiers, so its account cannot be verified.'
    elif existing and incoming and not previous:
        reason = 'Existing conversations have no recorded account identity; account continuity cannot be verified.'
    if reason and not confirmed:
        raise AccountMismatch(reason+' Import into a separate library with --profile NAME, or explicitly use --confirm-account-switch to replace this provider snapshot, including pruning absent conversations.')
    if incoming:
        data.setdefault('provider_accounts',{})[provider] = incoming
    elif confirmed:
        data.get('provider_accounts',{}).pop(provider,None)
    return 'confirmed_switch' if reason else 'matched' if previous and incoming else 'recorded' if incoming else 'unavailable'
