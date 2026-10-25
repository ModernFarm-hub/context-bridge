# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""Evaluate experimental claim support separately from retrieval and answer generation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
if __package__:
    from .support import checker
else:
    from support import checker



def select_cases(dataset, split='all'):
    cases = dataset.get('cases') if isinstance(dataset, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError('Dataset requires a nonempty cases list')
    seen, groups = set(), {}
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get('id'), str) or not case['id'] or case['id'] in seen:
            raise ValueError('Each case requires a unique ID')
        seen.add(case['id'])
        if type(case.get('expected_accept')) is not bool:
            raise ValueError('Each case requires an explicit boolean support label')
        if any(not isinstance(case.get(key), str) or not case[key].strip() for key in ('passage', 'claim')):
            raise ValueError('Each case requires a nonempty passage and claim')
        group = case.get('group_id')
        if group is not None:
            if not isinstance(group, str) or not group:
                raise ValueError('Scenario group IDs must be nonempty strings')
            if group in groups and groups[group] != case.get('split'):
                raise ValueError('A scenario group cannot cross development and heldout splits')
            groups[group] = case.get('split')
    if dataset.get('review_required') and split == 'all':
        raise ValueError('Choose development or heldout explicitly; do not mix reserved validation into tuning')
    selected = [c for c in cases if split == 'all' or c.get('split') == split]
    if not selected:
        raise ValueError('No cases in selected split')
    if dataset.get('review_required'):
        if any(c.get('reviewed') is not True or not isinstance(c.get('reviewed_by'), str) or not c['reviewed_by'].strip() for c in selected):
            raise ValueError('Selected cases still need human label review; no model inference performed')
    if not any(c['expected_accept'] for c in selected) or not any(not c['expected_accept'] for c in selected):
        raise ValueError('Selected split must contain supported and unsupported claims')
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, default=Path(__file__).parent / 'evals/claim-support.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--threshold', type=float, default=.90)
    parser.add_argument('--split', choices=('all', 'development', 'heldout'), default='all')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output directory to preserve earlier results')
    dataset = json.loads(args.dataset.read_text())
    try:
        cases = select_cases(dataset, args.split)
    except ValueError as exc:
        parser.error(str(exc))
    engine = checker(str(args.model.resolve()), args.threshold)
    rows = []
    for case in cases:
        start = time.perf_counter()
        result = engine.check(case['passage'], case['claim'])
        rows.append({**case, 'result': result, 'accepted': result['status'] == 'model_supported', 'latency_ms': (time.perf_counter() - start) * 1000})
    positives = [r for r in rows if r['expected_accept']]
    negatives = [r for r in rows if not r['expected_accept']]
    recall = sum(r['accepted'] for r in positives) / len(positives)
    false_accepts = sum(r['accepted'] for r in negatives)
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'dataset_sha256': hashlib.sha256(args.dataset.read_bytes()).hexdigest(), 'split': args.split, 'selected_case_ids': [c['id'] for c in cases], 'code_sha256': {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest() for name in ('support.py', 'evidence_graph.py', 'retrieval.py', 'setup_support.py', 'evaluate_support.py')}, 'model': engine.model_id, 'threshold': engine.threshold, 'summary': {'cases': len(rows), 'supported_claim_acceptance_recall': recall, 'unsupported_claims_accepted': false_accepts, 'unsupported_claim_count': len(negatives), 'unsupported_claim_rejection_rate': 1 - false_accepts / len(negatives), 'abstentions': sum(r['result']['status'] == 'needs_review' for r in rows), 'passing_cases': sum(r['accepted'] == r['expected_accept'] for r in rows)}, 'acceptance_passed': recall >= .90 and false_accepts == 0, 'limitations': ['Small assistant-authored synthetic development set; not independent validation.', 'No generated answers, end-to-end retrieval, private chats, or external truth verification.', 'Softmax scores are not calibrated probabilities of factual correctness.'], 'cases': rows}
    args.output.mkdir(parents=True)
    (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'summary': report['summary'], 'acceptance_passed': report['acceptance_passed'], 'report': str((args.output / 'results.json').resolve())}, indent=2))


if __name__ == '__main__':
    main()
