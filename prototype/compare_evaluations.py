# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""Compare two results on the same dataset, split and repetition count."""
import argparse
import json
from pathlib import Path


def cases(report):
    result = {}
    for row in report['runs']:
        result[row['case_id']] = result.get(row['case_id'], True) and row['passed']
    return result


def compare(baseline, candidate):
    for key in ('dataset_sha256', 'repetitions', 'split'):
        if baseline[key] != candidate[key]:
            raise ValueError('Reports differ in ' + key + '; comparison rejected')
    old, new = cases(baseline), cases(candidate)
    if old.keys() != new.keys():
        raise ValueError('Reports contain different scenarios')
    return {'baseline_cases_passing': sum(old.values()), 'candidate_cases_passing': sum(new.values()), 'improved_cases': sorted(k for k in old if not old[k] and new[k]), 'regressed_cases': sorted(k for k in old if old[k] and not new[k]), 'remaining_failures': sorted(k for k in new if not new[k]), 'recall_change_percentage_points': 100 * (candidate['summary']['macro_recall_at_5'] - baseline['summary']['macro_recall_at_5']), 'candidate_acceptance_passed': candidate['acceptance_passed']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fail-on-regression', action='store_true')
    args = parser.parse_args()
    baseline, candidate = (json.loads(path.read_text()) for path in (args.baseline, args.candidate))
    result = compare(baseline, candidate)
    old, new = baseline['summary'], candidate['summary']
    lines = ['# Context Bridge retrieval comparison', '', f"Same synthetic dataset; {baseline['case_count']} scenarios, each repeated {baseline['repetitions']} times. No generative model calls or private conversations. Local embedding inference is used when configured.", '', '| Metric | Original | Improved |', '| --- | ---: | ---: |', f"| Scenarios passing | {result['baseline_cases_passing']}/{baseline['case_count']} | {result['candidate_cases_passing']}/{candidate['case_count']} |"]
    for title, key in [('Macro Recall@5', 'macro_recall_at_5'), ('Macro Precision@5, nonempty results', 'macro_precision_at_5'), ('Source locator validity', 'provenance_locator_validity'), ('Negative-case pass rate', 'negative_case_pass_rate')]:
        previous = f'{old[key]:.1%}' if old[key] is not None else 'Not defined'
        current = f'{new[key]:.1%}' if new[key] is not None else 'Not defined'
        lines.append(f'| {title} | {previous} | {current} |')
    lines.extend([f"| Isolation probe violations / opportunities | {old['isolation_violations']}/{old['isolation_opportunities']} | {new['isolation_violations']}/{new['isolation_opportunities']} |", f"| Revocation probe failures / opportunities | {old['revocation_failures']}/{old['revocation_opportunities']} | {new['revocation_failures']}/{new['revocation_opportunities']} |", '', 'Recall changed by %.1f percentage points. Measured acceptance targets are not all met; inspect the candidate report for failed checks.' % result['recall_change_percentage_points'] if not candidate['acceptance_passed'] else 'Measured acceptance targets passed.', '', '## What changed', '', 'See report implementation hashes and retrieval settings for the compared engines. Hybrid mode adds local embedding search and reciprocal-rank fusion to owner-scoped BM25. Passages retain original source offsets. Relevance is not factual verification.', '', 'Improved cases: ' + (', '.join(result['improved_cases']) or 'none') + '.', 'Regressed cases: ' + (', '.join(result['regressed_cases']) or 'none') + '.', 'Remaining failures: ' + (', '.join(result['remaining_failures']) or 'none') + '.', '', 'Inspect remaining failed traces for the actual cause. No benchmark-specific synonym substitutions were added.', '', '## Limits', '', 'This dataset and its reserved subset were already exercised in the baseline, so the improved results are a regression comparison, not an independent blind validation. A small deterministic synthetic dataset does not establish production reliability. The isolation checks exercise local owner filters; enterprise identity is unimplemented. Answer completeness, semantic citation accuracy, prompt-injection resistance and end-to-end live freshness are unmeasured.', '', 'The existing manager and running reader processes are not restarted by evaluation. Restart readers to load the new retrieval code. Original source transcripts and access approvals are unchanged.', ''])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text('\n'.join(lines))
    args.output.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if args.fail_on_regression and (result['regressed_cases'] or result['recall_change_percentage_points'] < 0):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
