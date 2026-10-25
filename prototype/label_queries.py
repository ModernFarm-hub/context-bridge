# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""Prepare and freeze manually reviewed evaluation data. Never reads chat history."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def template(count=12):
    return {'version': 'manual-queries-1', 'description': 'Unreviewed template; not benchmark evidence.', 'k': 5, 'cases': [
        {'id': f'H{i+1:03d}', 'kind': 'retrieval', 'category': 'manual-workflow',
         'split': 'development' if i < count * 2 // 3 else 'heldout',
         'origin': '', 'reviewed_by': '', 'reviewed': False, 'query': '',
         'records': [{'id': 'evidence-1', 'session': '', 'text': ''}],
         'expected_evidence': None, 'required_text': {}}
        for i in range(count)]}


def validate(data):
    errors = []
    if not isinstance(data, dict) or data.get('k') != 5 or not isinstance(data.get('cases'), list) or not data['cases']:
        return ['Dataset requires k=5 and a nonempty cases list.']
    seen = set()
    for index, case in enumerate(data['cases']):
        if not isinstance(case, dict):
            errors.append(f'Case {index + 1}: must be an object.')
            continue
        cid = case.get('id')
        prefix = f'Case {index + 1} ({cid}): '
        if not isinstance(cid, str) or not cid.strip() or cid in seen:
            errors.append(prefix + 'provide a unique nonempty ID.')
        else:
            seen.add(cid)
        if case.get('reviewed') is not True or not isinstance(case.get('reviewed_by'), str) or not case['reviewed_by'].strip():
            errors.append(prefix + 'human review and reviewer name/alias are required.')
        if case.get('origin') not in ('personal', 'synthetic'):
            errors.append(prefix + 'origin must be personal or synthetic; never mislabel examples as real usage.')
        if case.get('kind') != 'retrieval' or case.get('split') not in ('development', 'heldout'):
            errors.append(prefix + 'use retrieval kind and development/heldout split.')
        if not isinstance(case.get('query'), str) or not case['query'].strip():
            errors.append(prefix + 'write a question.')
        records = case.get('records')
        lookup = {}
        if not isinstance(records, list) or not records:
            errors.append(prefix + 'provide source excerpts, including distractors for negative questions.')
        else:
            for record in records:
                if not isinstance(record, dict) or not all(isinstance(record.get(k), str) and record[k].strip() for k in ('id', 'session', 'text')):
                    errors.append(prefix + 'each excerpt needs a nonempty ID, session and text.')
                    continue
                if record['id'] in lookup:
                    errors.append(prefix + 'excerpt IDs must be unique within the case.')
                lookup[record['id']] = record['text']
        expected = case.get('expected_evidence')
        if not isinstance(expected, list) or not all(isinstance(item, str) for item in expected):
            errors.append(prefix + 'label expected_evidence explicitly; [] means no answer is present.')
            continue
        if len(expected) != len(set(expected)) or any(item not in lookup for item in expected):
            errors.append(prefix + 'expected evidence must reference unique excerpt IDs.')
        support = case.get('required_text')
        if not isinstance(support, dict):
            errors.append(prefix + 'required_text must map evidence IDs to exact supporting quotes.')
            continue
        for key in expected:
            quote = support.get(key)
            if not isinstance(quote, str) or not quote.strip() or quote not in lookup.get(key, ''):
                errors.append(prefix + f'{key} needs an exact supporting quote contained in its excerpt.')
        if any(key not in expected for key in support):
            errors.append(prefix + 'support quotes must refer only to expected evidence.')
    return errors


def freeze(source, destination):
    data = json.loads(source.read_text())
    errors = validate(data)
    if errors:
        raise ValueError('\n'.join(errors))
    if destination.exists():
        raise ValueError('Choose a new output directory; frozen datasets are never overwritten.')
    payload = (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode()
    manifest = {'frozen_at': datetime.now(timezone.utc).isoformat(),
                'sha256': hashlib.sha256(payload).hexdigest(), 'case_count': len(data['cases']),
                'split_counts': {split: sum(c['split'] == split for c in data['cases']) for split in ('development', 'heldout')},
                'origin_counts': {origin: sum(c['origin'] == origin for c in data['cases']) for origin in ('personal', 'synthetic')},
                'notice': 'Manual review is self-attested. Do not tune on heldout cases. No independent-review or real-user accuracy claim is implied.'}
    destination.mkdir(parents=True)
    (destination / 'dataset.json').write_bytes(payload)
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('init', 'validate', 'freeze'))
    parser.add_argument('--file', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'init':
        with args.file.open('x') as handle:
            json.dump(template(), handle, indent=2)
            handle.write('\n')
        print('Created 12 unreviewed question slots. Follow research/docs/LABELING-QUERIES.md before freezing.')
        return
    try:
        if args.action == 'freeze':
            if args.output is None:
                parser.error('freeze requires --output pointing to a new directory')
            print(json.dumps(freeze(args.file, args.output), indent=2))
        else:
            errors = validate(json.loads(args.file.read_text()))
            if errors:
                raise ValueError('\n'.join(errors[:12]) + (f'\n{len(errors)} issues in total.' if len(errors) > 12 else ''))
            print('All cases have explicit review, evidence labels and valid supporting quotes.')
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
