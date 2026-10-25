# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""Deterministic retrieval/control evaluation. No model calls or private history."""
if __package__:
    from .paths import data_home
else:
    from paths import data_home
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
import math
import os
from pathlib import Path
import platform
import statistics
import tempfile
import time

if __package__:
    from .bridge import Bridge
else:
    from bridge import Bridge
if __package__:
    from .mcp_server import ContextService
else:
    from mcp_server import ContextService
if __package__:
    from .session_manager import atomic_write
else:
    from session_manager import atomic_write

HERE = Path(__file__).resolve().parent


def percentile(values, fraction=.95):
    if not values:
        return None
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def envelope(record):
    role = record.get('role', 'assistant')
    content = record['text']
    if record.get('tool_result'):
        content = [{'type': 'tool_result', 'content': [{'type': 'text', 'text': content}]}]
    return {'type': record.get('type', role), 'sessionId': record['session'], 'timestamp': record.get('timestamp', '2026-10-23T09:00:00Z'), 'message': {'role': role, 'content': content}}


class Fixture:
    def __init__(self, root, retrieval_settings=None):
        root = root.resolve()
        self.root = root
        self.config = root / 'enrollment.json'
        self.data = {'tenant': 'company-a', 'employee': 'alice', 'database': str(root / 'context.db'), 'approved_transcripts': []}
        if retrieval_settings:
            self.data['retrieval'] = retrieval_settings
        self.locators = {}
        self.originals = {}
        self.service = ContextService(self.config)
        self.flush()

    def flush(self):
        atomic_write(self.config, self.data)

    def record(self, identifier, text, session=None, **extra):
        return {'id': identifier, 'text': text, 'session': session or identifier, **extra}

    def load(self, records, owner=None, approve=True):
        for record in records:
            path = self.root / (record['id'] + '.jsonl')
            raw = envelope(record)
            path.write_text(json.dumps(raw) + '\n')
            locator = (str(path), 1)
            self.locators[locator] = record['id']
            self.originals[locator] = raw
            if approve:
                self.data['approved_transcripts'].append(str(path))
            if owner:
                bridge = Bridge(self.data['database'], *owner)
                try:
                    bridge.ingest(path)
                finally:
                    bridge.db.close()
        self.flush()

    def search(self, query):
        return self.service.call('context_search', {'query': query, 'limit': 5})['results']

    def close(self):
        if self.service.bridge:
            self.service.bridge.db.close()


def retrieval(case, fixture, k):
    fixture.load(case['records'])
    start = time.perf_counter()
    result = fixture.service.call('context_search', {'query': case['query'], 'limit': k})['results']
    elapsed = (time.perf_counter() - start) * 1000
    expected = set(case['expected_evidence'])
    ids, useful, provenance = [], [], []
    for row in result:
        locator = (row['source'], row['line'])
        identifier = fixture.locators.get(locator)
        ids.append(identifier)
        original = fixture.originals.get(locator)
        provenance.append(bool(original and row['session'] == original['sessionId'] and row['role'] == original['message']['role'] and row['timestamp'] == original['timestamp'] and row['body'] in Bridge.text(original['message']['content'])))
        contains = case.get('required_text', {}).get(identifier)
        useful.append(identifier in expected and (not contains or contains in row['body']))
    read_ids, read_trace, read_latencies = set(), [], []
    read_valid, read_total, read_errors = 0, 0, 0
    # Read every retrieved candidate using the same question, not gold labels.
    for row in result:
        locator = (row['source'], row['line'])
        identifier = fixture.locators.get(locator)
        started = time.perf_counter()
        try:
            record = fixture.service.call('context_read', {'source': row['source'], 'line': row['line'], 'query': case['query'], 'max_chars': 4000})['record']
            original = fixture.originals.get(locator)
            full_text = Bridge.text(original['message']['content']) if original else ''
            span_valid = bool(original and record['session'] == original['sessionId'] and record['source'] == locator[0] and record['line'] == locator[1] and record['body'] == full_text[record['passage_start']:record['passage_end']] and record['record_sha256'] == hashlib.sha256(full_text.encode()).hexdigest())
            read_total += 1
            read_valid += span_valid
            support = case.get('required_text', {}).get(identifier, full_text)
            if identifier in expected and span_valid and support and support in record['body']:
                read_ids.add(identifier)
            read_trace.append(record)
        except (ValueError, KeyError, TypeError):
            read_errors += 1
            read_trace.append({'source': row['source'], 'line': row['line'], 'error': 'Focused read unavailable'})
        read_latencies.append((time.perf_counter() - started) * 1000)
    reading_recall = len(read_ids & expected) / len(expected) if expected else None
    found = {i for i, valid in zip(ids, useful) if valid}
    recall = len(found & expected) / len(expected) if expected else None
    precision = sum(useful) / len(result) if result else None
    first = next((1 / (n + 1) for n, flag in enumerate(useful) if flag), 0) if expected else None
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(expected), k)))
    ndcg = sum(1 / math.log2(i + 2) for i, flag in enumerate(useful) if flag) / ideal if ideal else None
    passed = (recall == 1 if expected else not result) and all(provenance)
    if case.get('top_evidence'):
        passed = passed and bool(ids) and ids[0] == case['top_evidence']
    return {'passed': passed, 'reading_recall_at_k': reading_recall, 'read_span_valid': read_valid, 'read_span_total': read_total, 'read_errors': read_errors, 'read_latencies_ms': read_latencies, 'read_trace': read_trace, 'recall_at_k': recall, 'precision_at_k': precision, 'mrr': first, 'ndcg_at_k': ndcg, 'returned_evidence': ids, 'expected_evidence': sorted(expected), 'provenance_valid': sum(provenance), 'provenance_total': len(provenance), 'latency_ms': elapsed, 'trace': result, 'reason': 'All required checks passed' if passed else 'Missing required evidence, unsupported passage, wrong top result, invalid locator, or unexpected negative-case results'}


def control(case, f):
    mode = case['mode']
    private = f.record('private', 'VAULT778 confidential retention exception')
    public = f.record('public', 'PUBLIC123 retention is 90 days')
    if mode in ('isolation_employee', 'isolation_tenant', 'direct_read'):
        owner = ('company-b', 'alice') if mode == 'isolation_tenant' else ('company-a', 'bob')
        f.load([private], owner=owner, approve=False)
        f.load([public])
        bridge = Bridge(f.data['database'], *owner)
        try:
            assert bridge.search('VAULT778'), 'Isolation probe has no forbidden data'
        finally:
            bridge.db.close()
        hits = f.search('VAULT778')
        assert not hits, 'Forbidden employee or tenant evidence leaked'
        if mode == 'direct_read':
            try:
                f.service.call('context_read', {'source': str(f.root / 'private.jsonl'), 'line': 1})
            except ValueError:
                pass
            else:
                raise AssertionError('Direct read exposed another employee record')
        return {'passed': True, 'isolation_opportunities': 1, 'isolation_violations': 0}
    f.load([public])
    assert f.search('PUBLIC123'), 'Baseline source is not searchable'
    if mode == 'override':
        try:
            f.service.call('context_search', {'query': 'PUBLIC123', 'employee': 'bob'})
        except ValueError:
            return {'passed': True}
        raise AssertionError('Identity override accepted')
    if mode == 'revoke':
        f.data['approved_transcripts'] = []
        f.flush()
        assert not f.search('PUBLIC123'), 'Revoked source still returned'
        return {'passed': True, 'revocation_opportunities': 1, 'revocation_failures': 0}
    path = f.root / 'public.jsonl'
    if mode == 'missing':
        path.unlink()
        assert not f.search('PUBLIC123'), 'Missing source still returned'
    elif mode == 'internal':
        with path.open('a') as stream:
            stream.write(json.dumps({'type': 'api-request-blob', 'sessionId': 'public', 'message': {'role': 'user', 'content': 'INTERNAL999 secret replay'}}) + '\n')
        assert not f.search('INTERNAL999'), 'Internal request data indexed'
        assert f.search('PUBLIC123')
    elif mode in ('partial', 'append'):
        record = json.dumps(envelope(f.record('new', 'FRESH456 weekly backups', session='public'))) + '\n'
        if mode == 'partial':
            with path.open('a') as stream:
                stream.write(record[:25])
            assert not f.search('FRESH456'), 'Incomplete record indexed'
            with path.open('a') as stream:
                stream.write(record[25:])
                stream.flush(); os.fsync(stream.fileno())
        else:
            with path.open('a') as stream:
                stream.write(record)
                stream.flush(); os.fsync(stream.fileno())
        start = time.perf_counter()
        assert f.search('FRESH456'), 'Completed new record missing'
        return {'passed': True, 'local_freshness_ms': (time.perf_counter() - start) * 1000}
    elif mode == 'malformed':
        with path.open('a') as stream:
            stream.write('invalid-json\n')
        try:
            f.search('PUBLIC123')
        except ValueError:
            return {'passed': True}
        raise AssertionError('Malformed source did not fail closed')
    else:
        raise ValueError('Unknown control mode')
    return {'passed': True}


def mean(rows, name):
    values = [r[name] for r in rows if r.get(name) is not None]
    return statistics.mean(values) if values else None


def aggregate(rows):
    retrievals = [r for r in rows if r['kind'] == 'retrieval']
    positives = [r for r in retrievals if r['expected_evidence']]
    negatives = [r for r in retrievals if not r['expected_evidence']]
    total = sum(r.get('provenance_total', 0) for r in rows)
    read_count = sum(r.get('read_span_total', 0) for r in rows)
    read_times = [value for r in rows for value in r.get('read_latencies_ms', [])]
    return {'reading_recall_at_5': mean(positives, 'reading_recall_at_k'), 'read_span_validity': sum(r.get('read_span_valid', 0) for r in rows) / read_count if read_count else None, 'focused_read_p95_ms': percentile(read_times), 'read_errors': sum(r.get('read_errors', 0) for r in rows), 'runs': len(rows), 'passed_runs': sum(r['passed'] for r in rows), 'macro_recall_at_5': mean(positives, 'recall_at_k'), 'macro_precision_at_5': mean(positives, 'precision_at_k'), 'mrr': mean(positives, 'mrr'), 'ndcg_at_5': mean(positives, 'ndcg_at_k'), 'provenance_locator_validity': sum(r.get('provenance_valid', 0) for r in rows) / total if total else None, 'negative_case_pass_rate': sum(r['passed'] for r in negatives) / len(negatives) if negatives else None, 'isolation_opportunities': sum(r.get('isolation_opportunities', 0) for r in rows), 'isolation_violations': sum(r.get('isolation_violations', 0) for r in rows), 'revocation_opportunities': sum(r.get('revocation_opportunities', 0) for r in rows), 'revocation_failures': sum(r.get('revocation_failures', 0) for r in rows), 'retrieval_refresh_p95_ms': percentile([r['latency_ms'] for r in rows if 'latency_ms' in r]), 'local_freshness_p95_ms': percentile([r['local_freshness_ms'] for r in rows if 'local_freshness_ms' in r])}


def render(report):
    summary = report['summary']
    def metric(value, percent=False):
        if value is None:
            return 'Not measured'
        return f'{value:.1%}' if percent else f'{value:.2f}'
    cards = [('Recall@5', metric(summary['macro_recall_at_5'], True)), ('Focused-read support recall', metric(summary.get('reading_recall_at_5'), True)), ('Source locator validity', metric(summary['provenance_locator_validity'], True)), ('Retrieval + refresh p95', metric(summary['retrieval_refresh_p95_ms']) + ' ms'), ('Scenarios fully passing', str(report['passing_cases']) + ' / ' + str(report['case_count']))]
    cards_html = ''.join('<div class="card"><span>'+html.escape(k)+'</span><strong>'+html.escape(v)+'</strong></div>' for k,v in cards)
    by_case = defaultdict(list)
    for row in report['runs']:
        by_case[row['case_id']].append(row)
    rows = ''
    for case_id, runs in by_case.items():
        row = runs[0]
        expected = ', '.join(row.get('expected_evidence', [])) or 'Control / empty result'
        got = ', '.join(str(v) for v in row.get('returned_evidence', [])) or '—'
        passed = all(r['passed'] for r in runs)
        rows += '<tr><td>'+html.escape(case_id)+'</td><td>'+html.escape(row['category'])+'</td><td>'+html.escape(row['split'])+'</td><td class="'+('pass' if passed else 'fail')+'">'+('Pass' if passed else 'Fail')+'</td><td>'+html.escape(expected)+'</td><td>'+html.escape(got)+'</td></tr>'
    return '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Context Bridge evaluation</title><style>body{font:15px system-ui;color:#172333;background:#f3f5f9;margin:0}main{max-width:1100px;margin:40px auto;padding:24px}.cards{display:flex;gap:16px;flex-wrap:wrap}.card{background:white;border:1px solid #dce3ec;border-radius:12px;padding:20px;min-width:180px}.card span{display:block;color:#526379}.card strong{display:block;font-size:30px;margin-top:10px}p,li{line-height:1.7}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:12px;border-bottom:1px solid #e0e5ee}th{background:#e8edf5}.pass{color:#167045}.fail{color:#b02730}.note{background:#fff4db;padding:20px;border-radius:12px}code{font-size:13px}</style></head><body><main><small>SYNTHETIC RETRIEVAL EVALUATION · NO GENERATIVE MODEL CALLS</small><h1>Context Bridge evaluation</h1><p>'''+html.escape(report['created_at'])+''' · Dataset '''+html.escape(report['dataset_version'])+''' · '''+str(report['repetitions'])+''' repetitions per scenario</p><div class="cards">'''+cards_html+'''</div><p class="note"><strong>'''+('Baseline below acceptance targets.' if not report['acceptance_passed'] else 'Measured baseline targets passed.')+'''</strong> These results measure retrieval and local access-filter behavior. They do not establish enterprise authentication, semantic citation accuracy, answer quality, production scale, or resistance to model prompt injection.</p><h2>How to interpret this</h2><p>Recall requires the expected evidence to appear in the first five results; the long-passage case also requires its supporting text to be visible. Locator validity checks session, line, role, timestamp and passage against the source fixture. It is not a model citation-quality score. Focused-read support recall measures exact annotated evidence present after following retrieved locators with the same question. It does not grade generated answers. Read validity checks original character offsets and a record hash. Retrieval scenario success remains separate for comparison with older reports. Full scenario success additionally checks negative cases and latest-decision ranking where specified.</p><p>Latency includes capture refresh and retrieval on tiny local fixtures. For hybrid runs, embedding model initialization is recorded separately in the JSON metadata; local embedding inference is included in query latency. Freshness is measured from a completed fixture write to the next query result, excluding Claude transcript flush, network, background polling and model time. It is not end-to-end live-session freshness.</p><h2>Scenario results</h2><table><thead><tr><th>ID</th><th>Category</th><th>Subset</th><th>Result</th><th>Expected evidence</th><th>Retrieved evidence, first run</th></tr></thead><tbody>'''+rows+'''</tbody></table><h2>Not measured yet</h2><ul><li>Answer completeness, unsupported claims, semantic citation accuracy and conflict resolution.</li><li>Whether a model follows malicious retrieved instructions. We only verify exclusion of internal request blobs.</li><li>Enterprise identity assurance, concurrent distributed revocation, source-system permissions and production load.</li></ul><p>See <a href="results.json">results.json</a> for thresholds, dataset/code hashes, metrics by subset and full synthetic traces. Reserved cases are labeled heldout, but authored in this project; they are not an independent external benchmark.</p></main></body></html>'''


def run(dataset, repetitions=3, split='all', retrieval_settings=None):
    embedder = None
    embedding_load_ms = None
    initial_calls = 0
    if retrieval_settings:
        if __package__:
            from .semantic import model
        else:
            from semantic import model
        started = time.perf_counter()
        embedder = model(str(Path(retrieval_settings['model_directory']).resolve()))
        embedding_load_ms = (time.perf_counter() - started) * 1000
        initial_calls = embedder.inference_calls
    cases = [c for c in dataset['cases'] if split == 'all' or c['split'] == split]
    rows = []
    for case in cases:
        for repetition in range(repetitions):
            with tempfile.TemporaryDirectory(prefix='context-bridge-eval-') as directory:
                fixture = Fixture(Path(directory), retrieval_settings)
                try:
                    result = retrieval(case, fixture, dataset['k']) if case['kind'] == 'retrieval' else control(case, fixture)
                except Exception as exc:
                    result = {'passed': False, 'reason': type(exc).__name__ + ': ' + str(exc)}
                    if case.get('mode') in ('isolation_employee', 'isolation_tenant', 'direct_read'):
                        result.update(isolation_opportunities=1, isolation_violations=1)
                    if case.get('mode') == 'revoke':
                        result.update(revocation_opportunities=1, revocation_failures=1)
                    # Failed execution cannot disappear from positive-case recall.
                    if case['kind'] == 'retrieval':
                        result.update(reading_recall_at_k=0 if case['expected_evidence'] else None, expected_evidence=case['expected_evidence'], returned_evidence=[], recall_at_k=0 if case['expected_evidence'] else None, mrr=0, ndcg_at_k=0)
                finally:
                    fixture.close()
                rows.append({'case_id': case['id'], 'kind': case['kind'], 'category': case['category'], 'split': case['split'], 'repetition': repetition + 1, **result})
    summary = aggregate(rows)
    controls_passed = all(r['passed'] for r in rows if r['kind'] == 'control') and any(r['kind'] == 'control' for r in rows)
    checks = {'reading_recall_at_5_at_least_90_percent': summary['reading_recall_at_5'] is not None and summary['reading_recall_at_5'] >= .90, 'read_span_validity_100_percent': summary['read_span_validity'] == 1, 'recall_at_5_at_least_90_percent': summary['macro_recall_at_5'] is not None and summary['macro_recall_at_5'] >= .90, 'all_controls_pass': controls_passed, 'negative_cases_pass': summary['negative_case_pass_rate'] == 1, 'source_locator_validity_100_percent': summary['provenance_locator_validity'] == 1, 'retrieval_refresh_p95_under_2000_ms': summary['retrieval_refresh_p95_ms'] is not None and summary['retrieval_refresh_p95_ms'] <= 2000, 'local_fixture_freshness_p95_under_10000_ms': summary['local_freshness_p95_ms'] is not None and summary['local_freshness_p95_ms'] <= 10000}
    return {'created_at': datetime.now(timezone.utc).isoformat(), 'dataset_version': dataset['version'], 'dataset_sha256': hashlib.sha256(json.dumps(dataset, sort_keys=True).encode()).hexdigest(), 'code_sha256': {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in ('bridge.py','retrieval.py','semantic.py','setup_semantic.py','mcp_server.py','session_manager.py','evaluate.py')}, 'environment': {'python': platform.python_version(), 'platform': platform.system(), 'model': None, 'model_calls': 0, 'model_call_definition': 'Generative calls only; local embedding inference is counted separately', 'generative_model_calls': 0, 'embedding_forward_calls': embedder.inference_calls - initial_calls if embedder else 0, 'embedding_load_ms': embedding_load_ms, 'retrieval_settings': retrieval_settings or {'mode': 'lexical'}, 'embedding_model': embedder.model_id if embedder else None}, 'repetitions': repetitions, 'split': split, 'case_count': len(cases), 'passing_cases': sum(all(r['passed'] for r in rows if r['case_id'] == case['id']) for case in cases), 'summary': summary, 'subsets': {name: aggregate([r for r in rows if r['split'] == name]) for name in ('development','heldout')}, 'acceptance_checks': checks, 'acceptance_passed': all(checks.values()), 'unmeasured': ['answer_completeness','unsupported_claim_rate','semantic_citation_accuracy','model_prompt_injection_resistance','enterprise_authentication','production_load','end_to_end_live_freshness'], 'runs': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=HERE / 'evals/scenarios.json')
    parser.add_argument('--validation', action='store_true', help='Use the separate bundled 16-scenario validation dataset')
    parser.add_argument('--output', type=Path, default=data_home() / 'reports' / 'latest')
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--split', choices=['all','development','heldout'], default='all')
    parser.add_argument('--semantic-model', type=Path, help='Verified local ONNX model directory; enables hybrid retrieval')
    parser.add_argument('--retrieval-config', type=Path, help='Frozen retrieval settings JSON; mutually exclusive with --semantic-model')
    parser.add_argument('--fail-on-threshold', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 100:
        parser.error('Repetitions must be between 1 and 100')
    if args.validation:
        args.dataset = HERE / 'evals/semantic-validation.json'
    dataset = json.loads(args.dataset.read_text())
    if dataset.get('k') != 5 or len({c['id'] for c in dataset['cases']}) != len(dataset['cases']):
        parser.error('Dataset must have k=5 and unique case IDs')
    settings = {'mode': 'hybrid', 'model_directory': str(args.semantic_model.resolve()), 'minimum_similarity': .35} if args.semantic_model else None
    if args.retrieval_config:
        if args.semantic_model:
            parser.error('Choose retrieval-config or semantic-model')
        settings = json.loads(args.retrieval_config.read_text())
    report = run(dataset, args.repetitions, args.split, settings)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    (args.output / 'report.html').write_text(render(report))
    print(json.dumps({'scenarios_passing': f"{report['passing_cases']}/{report['case_count']}", 'acceptance_passed': report['acceptance_passed'], 'summary': report['summary'], 'report': str((args.output / 'report.html').resolve())}, indent=2))
    if args.fail_on_threshold and not report['acceptance_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
