# 0.9.0b1 local verification

213 tests passed with the existing local model suites enabled. The dependency-free run passes with 29 optional model tests skipped. New tests cover local accounting, client identity and exact response-text sizes over real stdio; default/opt-in query privacy; profile-scoped clearing; recorded usage, incremental cache accounting, legacy snapshot reinterpretation, the synthetic 37,000-cache-read trivial turn and read-window math; compact/full compatibility; hook diff/confirmation/backups/uninstall and noninteractive/EOF refusal; relevance/empty-output/timeout/budgets; offline negative cases; and paid-mode guards using fake provider responses only.

The [offline experiment](../../benchmarks/savings.md) uses twenty synthetic sessions and a disposable profile. Its original-cost counters are deliberately invented and its lookup tokens are character estimates. It is not a measured real-user savings claim. Three negative-net examples are retained. The paid Anthropic harness was not run; no API key or external paid service was used. No hook was installed in actual user settings. Tests use temporary settings files only.

CI configuration adds an explicit offline savings benchmark; the live branch refuses CI. Local wheel/source builds, payload checks, README/uvx offline smoke, installed-package smoke and official MCP client checks validate packaging and transport. No GitHub Actions run is claimed because changes were not pushed. No tag, release or package upload was performed.

```sh
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
python3 prototype/benchmark.py --savings --output /tmp/savings.json
python3 -m build --outdir /tmp/context-bridge-090-dist
python3 tools/check_artifacts.py /tmp/context-bridge-090-dist
python3 tools/uvx_smoke.py /tmp/context-bridge-090-dist
```

## Context-growth credit correction

The rerun credits 95,687 synthetic conservative lower-bound research tokens: cumulative assistant output plus nonnegative context growth above the first assistant turn. Full lookup costs are 20,015 estimated tokens (75,672 net); compact costs are 13,847 (81,840 net). The 244,165 all-in figure remains only an upper bound including fixed context overhead. These are synthetic counters, not measured real-world savings.

The repeated-ID trivial-turn fixture credits 136 rather than 37,099 and retains a negative net. Multi-turn Claude Code and growing Codex fixtures verify context growth plus outputs. Source accounting rebuilds baselines; legacy usage snapshots lacking those baselines receive output-only credit without rewriting history.

[Full 203-test output](method-fix-tests.log), [dependency-free output](method-fix-default-tests.log), and [build / offline quickstart verification](method-fix-build.log). Version remains 0.9.0b1. No paid run, tag, push, publication, issue or PR was performed.

## Live harness review correction (no paid execution)

205 tests pass with local model suites enabled; the dependency-free run passes with 29 optional model tests skipped. The default live selection is three positive tasks followed by two labelled negatives, reported separately. Fake-provider tests cover four sequential source steps, neutral questions, the product agent-guide system prompt for reuse, actual search/read indicators, unchanged thinking/signature replay, separate input/output pricing, 2,048-token requests, refusal/truncation flags and advisory-only CLI refusal without consent. Research depth defaults to four and determines the per-arm turn cap (depth + two).

No paid mode was run. Model availability, request acceptance and real-world savings remain unverified. The [method documentation](../../benchmarks/savings.md#optional-live-experiment-paid-not-run-here) describes artificial depth/note volume and small-sample limitations. Version remains 0.9.0b1. No tags, pushes, publication, issues or PRs.

[Full test output](live-harness-tests.log), [dependency-free output](live-harness-default-tests.log), [build and offline quickstart checks](live-harness-build.log).

```sh
# Free test run (live provider responses are mocked):
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
# Advisory only: expected nonzero exit without --yes; makes no API calls:
python3 prototype/benchmark.py --savings --live --input-price-per-million 2 --output-price-per-million 10
```

## Risk-weighted reuse policy

211 tests pass with both existing local model suites enabled; the dependency-free suite passes with 29 optional model tests skipped. Build, clean artifact payload and uvx offline quickstart checks pass. No new paid mode was run; all new harness tests use fake responses. The historical old-guide run files were read without modification and are documented with per-task tokens, costs, answer checks and run-to-run differences.

New coverage includes guide snapshots and CLI presets, mandatory high-stakes/volatile and conflicting-evidence REDO guidance, precise fixture signal labels and deliberately documented false positives, compact/full real-stdio signal schemas, bounded hook guidance and empty behavior, decision parsing across assistant turns, fake-provider class reports, cautious policy propagation and a two-task CHECK subset. Conflict detection is explicitly disabled pending reliable validation.

The offline rerun reports 1.0 precision/recall for time-sensitive signals (5 positives) and uncertainty (1 positive) on the controlled labelled fixture only. Compact responses average 174.10 estimated tokens; dropping only signal fields from the same payload gives 139.05, a 35.05-token difference. These are character estimates, not billed tokenizer measurements. All three expected decision classes have at least two examples in the 20-task pool; live runs remain capped at five selectable tasks.

[Full 211-test output](reuse-policy-tests.log), [dependency-free output](reuse-policy-default-tests.log), [build and offline quickstart verification](reuse-policy-build.log), [benchmark method and historical results](../../benchmarks/savings.md).

```sh
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
python3 prototype/benchmark.py --savings --output /tmp/reuse-policy-savings.json
context-bridge agent-guide --policy balanced
context-bridge agent-guide --policy economical
context-bridge agent-guide --policy cautious
```

Version remains 0.9.0b1. No tag, push, publication, issue or PR was created.

## Real-shaped volatility precision correction

212 tests pass with local model suites enabled; the dependency-free run passes with 29 optional model tests skipped. Build, package payload and offline uvx quickstart checks pass. Version remains 0.9.0b1. No paid mode, tags, pushes, publication, issues or PRs.

Volatility hints ignore fenced/inline code and snake_case/camelCase identifiers. Current/latest/now require a nearby volatile noun; decimals require software context unless v-prefixed or multi-dot; percentages are excluded. Financial symbols/codes, numeric scale amounts and financial nouns are recognized. The three reported failure shapes are covered by synthetic regressions, without importing real chat content.

The 21-case expanded fixture reports 11 true positives, 0 false positives, 2 false negatives: precision 100%, recall 84.62%. The misses (“twenty bucks”, “newest platform build”) remain in the denominator. These are controlled fixture metrics, not real-library precision. Further potential false positives/misses are documented in the [benchmark method](../../benchmarks/savings.md#risk-weighted-reuse-policy-and-signals).

All guides use “High stakes with volatility, or conflicting evidence, always require REDO.” Word counts: economical 164, balanced 167, cautious 167.

[Full 212-test output](signal-precision-tests.log), [dependency-free output](signal-precision-default-tests.log), [build and offline smoke output](signal-precision-build.log).

```sh
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
python3 prototype/benchmark.py --savings --output /tmp/signal-precision-savings.json
```

Inspect expanded_volatility_fixture in the benchmark JSON for precision/recall and the retained miss IDs. No live mode is needed.

## Run 3 harness correction

213 tests pass with local model suites enabled; dependency-free tests pass with 29 optional model tests skipped. Build, artifact payload checks and offline uvx quickstart pass. All new live-harness execution uses fake provider responses; no paid mode was run for this change.

Both arms now have research_steps + 4 calls (eight by default). Each reports cap_reached; a capped incomplete arm has answer_status=no_answer and null accuracy, not a wrong final answer. Missing/ambiguous decisions are explicitly non-compliant for reuse arms; baseline compliance is not applicable. The guide requires the decision before the final answer; word counts are economical 166, balanced 169, cautious 169. Fake regressions cover seven-call completion, cap exhaustion in both arms, final completion on the eighth call, and a correct but non-compliant answer.

The [run 3 documentation and label review](../../benchmarks/savings.md#run-3--balanced-guide-before-call-cap-correction) retain the recorded $0.775910 result and both capped no-answer outcomes. Aster/Willow/Comet labels remain unchanged, with risk/evidence reasons documented independently of observed model choices. The raw run JSON was not modified. The advisory now budgets 80 calls by default; at supplied input/output prices of $2/$10 per million it estimates $8.739840, not a guaranteed spending cap.

[Full 213-test output](call-cap-tests.log), [dependency-free output](call-cap-default-tests.log), [build and offline quickstart output](call-cap-build.log).

```sh
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
# Advisory only: expected refusal without --yes; no network call:
python3 prototype/benchmark.py --savings --live --input-price-per-million 2 --output-price-per-million 10
```

Version remains 0.9.0b1. No tags, pushes, publication, issues or PRs.
