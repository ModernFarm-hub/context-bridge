# Running the public-document research benchmark

This experiment compares balanced Context Bridge reuse with fresh research on forty frozen public-document questions. The repository and source distribution contain about 12 MB of Python documentation with per-file sources, versions, licenses and hashes. **The wheel deliberately omits the corpus** and is checked against a 500000-byte size budget. No benchmark reads your personal library or usage log. The committed main report uses fake providers and makes no measured savings claim. A separate real five-task pilot and its local formatting re-grade are documented below; the pilot is exploratory, not confirmatory.

Obtain the repository or download and extract the source distribution for this same version. Its data directory is `prototype/evals/savings-real`. When using an installed wheel, pass `--corpus-dir /path/to/source/prototype/evals/savings-real`. Missing data produces these instructions without making API calls. You can also reconstruct the corpus in a source checkout with `python tools/build_research_corpus.py ARCHIVE_313 ARCHIVE_314 --output prototype/evals/savings-real`; use the official Python 3.13.1 and 3.14.0 source archives. The script verifies pinned archive hashes. Corpus contents and the forty tasks have not changed in this revision.

Read [the preregistration](../../prototype/evals/savings-real/PREREGISTRATION.md), including the cost-control amendment. Task, analysis, cost-helper, deterministic-grader and decision-parser hashes are checked before running; the last registration for each path is authoritative. v1 contains Python 3.13.1 docs; v2 overlays selected actual Python 3.14.0 module docs. It is a controlled documentation snapshot, not an installed mixed Python interpreter.

From the source checkout, offline verification without a key or API calls:

```sh
python prototype/savings_real.py --fake --output /tmp/context-bridge-real-fake
python prototype/savings_real.py --fake --pilot --grader-model --output /tmp/context-bridge-real-pilot
```

Full mode runs forty cached Phase A original sessions and three repetitions per arm in Phase B. Pilot uses five frozen tasks spanning the four variants and one repetition; it cannot qualify for a savings claim. Fake usage and cache counters are fabricated, including deliberate cases where reuse loses.

Before a future paid run, set ANTHROPIC_API_KEY, choose a fresh output directory, supply all four research-model prices per million tokens, and set `--max-usd`:

- `--input-price-per-million`: uncached input.
- `--cache-read-price-per-million`: cache reads.
- `--cache-write-price-per-million`: cache creation/writes. Supply the applicable write price explicitly; there is no hardcoded multiplier.
- `--output-price-per-million`: output, including thinking as reported by the provider.

Review the advisory before adding `--yes`. Both `--yes` and the key are still required, and paid mode is refused in CI. No paid run was performed during implementation; a subsequently supplied independent pilot cost approximately $0.29. This amendment and re-grade make no new API calls. Prices must cover the selected model and any applicable input tier; they are not fetched automatically. The default model remains claude-sonnet-5-5, configurable with `--model`.

Every Messages request, including optional grading, contains top-level `cache_control: {"type": "ephemeral"}`. This is Anthropic's [automatic caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), which advances the cache breakpoint with the growing conversation. Recorded uncached input, cache creation, cache read and output counters are retained separately in raw calls, transcripts and summaries. A requested cache is not a guaranteed cache hit: minimum lengths, cache expiry and prefix changes can prevent reuse. The guard always budgets a miss at the largest supplied input/read/write rate.

`--max-usd` is mandatory for paid mode and frozen on resume. Before each request, the harness reserves its conservative text-input bound times the largest input/read/write rate, plus `max_tokens` times output price. The bound uses escaped JSON bytes, a 16384-token framing reserve and 256 extra tokens per message, content block and tool schema. It is deliberately much larger than ordinary character/4 estimates. Only inline text/thinking and local tools are accepted. A calculated bound above 1000000 is refused before sending. This enforced ceiling and the total call cap define the upfront worst case; it replaces the old assumed 150000-input-token advisory.

Actual recorded cost is reconciled after every response using decimal arithmetic, across Phase A, both arms and grading. A request is not sent if its reservation plus recorded spending exceeds the cap. A conservative reservation may stop a run with money remaining. Budget stops generate incomplete, non-qualifying reports, including the requested report destination. Missing usage or an interrupted request with an unknown charge blocks new calls. Unexpected usage above the reservation is recorded and stops further requests; an already incurred provider charge cannot be undone. The guard applies to the supplied rates and these text-only bounds, not your account's other activity or a provider invoice. For an independent account-wide guarantee, use provider spending controls too.

After a pilot, stdout and `summary.json` include mean uncached input/output/cache-read/cache-write tokens per research call and per session, phase/arm means, grader means separately, and actual average document characters read per session. A full-run estimate scales the measured session means to forty original, 120 baseline and 120 reuse sessions; optional grading allows 240 judgments without deduplication savings. This projection appears alongside the enforced-ceiling worst case. It is a small-sample extrapolation, not a confidence interval or a spending guarantee, and is never used to admit a request. Use a separate directory for full mode.

`read_doc` still caps each read at 12000 characters. `--call-cap` defaults to 12 per session; `--total-call-cap` defaults to 4000 across all phases and grading. The average characters read reflects actual returned document text, including replayed tool results exactly once per session, not requested length.

Optional `--grader-model` enables a blind grader (claude-opus-5-5 if supplied without a value). Paid grading also requires `--grader-input-price-per-million`, `--grader-output-price-per-million`, `--grader-cache-read-price-per-million` and `--grader-cache-write-price-per-million`. It shares the dollar cap, with its own four rates. Grader costs are separate. Required-fact checks remain primary. The dated formatting amendment permits exact module-name suffixes, booleans, case/quote normalization and exact-value prose fallback when facts JSON is absent. It does not add semantic aliases or fuzzy matching; a present but wrong/incomplete facts object still fails. Fallback use and decision compliance are reported separately. Surface checks can miss contradictions or accept incidental mentions, so inspect the human review sheet and optional grader.

Resume with exactly the same command and output directory. Configuration freezes prices, cap, model and code/data hashes. Completed responses and tool results replay without additional provider calls. A process lock prevents concurrent runs. Unknown billed calls never retry automatically; inspect their journal entries. Do not remove failed tasks or edit a partial run into a qualifying result.

Outputs include `raw-calls.jsonl` and per-call recovery files; original Claude Code-format `transcripts`; an isolated `library`; `results.jsonl`; `summary.json` with budget, usage, costs and strata; a seeded `spot-check.csv` with ten answers per arm; and `savings-real.md`. The CLI also writes `docs/benchmarks/savings-real.md` unless `--report PATH` selects another destination. Responses from unfinished sessions still contribute to recorded cost totals.

Interpret every variant and decision stratum alongside the overall paired ratio and bootstrap interval. Negative savings means reuse lost. Non-inferiority uses a five-percentage-point margin, not literal proof of zero accuracy loss; stale reuse must also be at least as accurate as baseline. Failures are retained. Incomplete, pilot and fake runs cannot qualify. The primary token metric includes all cache token counters; separate cache prices affect dollars, not the token ratio. Corpus dependence and shared Phase A history limit generalization.

## Independent real pilot and formatting amendment, 2026-11-22

The supplied real pilot ran five tasks on claude-sonnet-5-5 with a $5 guard and cost approximately $0.29. It completed with exit 0. Its original [saved artifacts](savings-real-pilot-2026-11-22/) remain unchanged. The dated amendment's reason is **pilot found formatting-only false negatives**. It was written after observing the pilot, before any confirmatory run. No task, variant, label, corpus, arm, call cap, analysis formula, bootstrap setting or threshold was changed. This is an acknowledged post-pilot measurement correction, not an untouched prospective analysis.

[Before/after results for every session](savings-real-pilot-2026-11-22-regrade/regrade.md) and the [machine-readable sidecar](savings-real-pilot-2026-11-22-regrade/regrade.json) re-grade final answers from saved responses only. The regrader cross-checks text, usage and call counts against the raw responses. It loads no library, invokes no provider and does not call the optional secondary grader. The original correctness labels remain in the source files.

Required-fact correctness changes from 10/15 to 15/15 across Phase A and B: original research 3/5 → 5/5, baseline 4/5 → 5/5, reuse 3/5 → 5/5. The changes come from qualified identifier formatting. JSON booleans already matched in the original grader and now have an explicit regression fixture. All fifteen saved final answers contain facts JSON, so the observed fallback share is 0/15. Prose-only excerpts/renderings are separately labelled regression fixtures; they are not represented as missing-JSON finals in the saved pilot.

The parser now recognizes the pilot's `Reuse decision: REUSE: an earlier conversation…` format. Reuse-arm compliance changes from 2/5 to 3/5. The two period-form markers (`CHECK.` and `REDO.` followed by prose) remain non-compliant under the specified separators. Decision accuracy remains 0/5: recognizing a marker does not make the policy choice right. The policy guide and expected labels are unchanged.

Per-session token totals use the registered sum of uncached input, cache-read input, cache-creation input and output:

| Task | Baseline tokens | Reuse tokens | Reuse / baseline | Baseline calls | Reuse calls |
|---|---:|---:|---:|---:|---:|
| research-01 | 11,505 | 9,213 | 0.8008 | 3 | 2 |
| research-11 | 8,226 | 13,095 | 1.5919 | 3 | 3 |
| research-21 | 3,426 | 13,269 | 3.8730 | 2 | 3 |
| research-31 | 8,897 | 24,087 | 2.7073 | 3 | 4 |
| research-40 | 7,664 | 14,384 | 1.8768 | 3 | 3 |

Reuse used more tokens in **four of five** comparisons. Fresh research was cheap: sessions took 2–4 calls, and four of the five baseline lookups used approximately 3–9k tokens. The ZIP lookup is an exception: its baseline used 11,505 tokens and its Phase A original used 19,262. The other original Phase A sessions used 3,461–8,544. Stating all originals were 3–9k would hide that exception. Lookup and verification overhead can dominate such short research sessions.

This benchmark measures reuse on **documentation lookups**. Whether reuse saves tokens on deeper research is a separate future question. Five exploratory tasks, corrected formatting labels and non-inferior required-fact accuracy do not establish a general savings claim. The token comparisons above are unchanged by regrading.

To reproduce the local re-grade without API calls:

```sh
python prototype/savings_real_regrade.py \
  --pilot-dir docs/benchmarks/savings-real-pilot-2026-11-22 \
  --output docs/benchmarks/savings-real-pilot-2026-11-22-regrade
```

Use a new directory for the future confirmatory run. Do not resume the old pilot with the amended grader or rewrite its source artifacts. The new run freezes the amended analysis, grader and parser hashes. Fallback share uses all final answers graded by JSON or fallback (including failed fallback checks), excludes nonfinal answers, and reports historical missing method metadata explicitly.

## Outcome-blind infrastructure amendment, 2026-11-22

A full run from commit `0d0bec6` was reported to have stopped on a read timeout. No partial outcomes were opened or analyzed to prepare this amendment, and implementation does not resume or alter that real run. Read [the dated amendment](../../prototype/evals/savings-real/PREREGISTRATION.md#2026-11-22-outcome-blind-infrastructure-amendment) before recovery. Tasks, labels, corpus, research arms, caps, grading and analysis are unchanged.

`--abandon-unresolved EXACT_KEY` is an **offline maintenance action**, not paid mode. It requires `--abandon-by` and `--abandon-reason`, works without an API key, and sends no requests even if other paid flags are present. It reads run configuration, source hashes and the exact reservation's metadata; it does not read outcome summaries, result rows or libraries. It refuses a key with any recorded response. Supply a deliberate tester identity and an infrastructure-only reason; do not include secrets or paths in audit text.

The following is a recovery example for the reported reservation. It has **not been executed** against the real run:

```sh
python prototype/savings_real.py \
  --output "$HOME/context-bridge-benchmark-runs/full-2026-11-22" \
  --abandon-unresolved B-research-07-baseline-0-00 \
  --abandon-by "independent tester" \
  --abandon-reason "read timeout; no outcomes inspected" \
  --read-timeout 300
```

The original reservation is marked abandoned/possibly billed. Its entire stored reservation (reported as $0.06843 in this case) is permanently charged to the conservative recorded total, never refunded because of a cheaper resend, later response or restart. Audit records retain who, UTC time, reason and exact key. Repeating the same abandonment is idempotent. The ledger is authoritative even if interruption occurs before the reservation file is annotated.

For the exact legacy runner from `0d0bec6`, this explicit action can adopt the registered infrastructure changes. It verifies protected task/corpus/grading/analysis/cost hashes and stores the old runner and original `run.json` hashes, adopter and reason in `infrastructure.json`. Original `run.json` remains unchanged. The code permits only this registered runner migration; any change to the experiment, caps, prices, model or protected hashes refuses resume. Do not hand-edit `run.json` to bypass the guard.

After reviewing the audit, resume **separately** with the original full-run command and all its original price/budget/model/cap arguments. This is the step that can make paid calls; it was not run during implementation. Timeouts are frozen in `infrastructure.json`; omit timeout flags to reuse those stored values or repeat their exact values. The default read timeout is 300 seconds, configurable with `--read-timeout`; the separate connect timeout defaults to 30 seconds (`--connect-timeout`). The default is not silently applied over an already frozen timeout.

The abandoned logical request may send the identical Messages body once under `B-research-07-baseline-0-00--attempt-1`. That new reservation consumes both the existing per-session request cap and global call cap, plus the dollar budget in addition to the original permanent charge. A completed attempt and its tool results replay from that exact new key. A second unresolved send can be explicitly abandoned and charged too, but there is no third send; missing data keeps the run incomplete. Other unresolved calls continue to block all new requests. The per-session cap remains unchanged; if the abandoned attempt has used its last slot, no resend is sent and the existing cap-reached outcome is reported.

Transport separates direct TLS connection establishment from HTTP request transmission. A connect-stage failure before any HTTP headers/body are sent may automatically retry the connection once. If both connects fail, it records a definitely-not-sent zero-cost failure and stops; resume does not silently reset that automatic allowance. Any error during transmission, reading headers/body, or decoding the response remains unresolved/possibly billed; it is never automatically retried, even if its exception type also occurs during connection establishment. A read timeout is not evidence that the provider did no work.

On the next separately requested resume, `summary.json` and the report disclose all abandonment keys, who/when/why, full reserved charges, response dollars, combined conservative spending and frozen timeouts. The offline action itself only changes the audit ledger and infrastructure metadata; it does not open a partial outcome report to rewrite it.

An abandonment does not by itself disqualify the run. Eligibility still requires every task, both arms and all three repetitions, plus every existing non-inferiority, stale-safety and token-ratio rule, with abandonment disclosed. No task may be excluded or replaced, no cap increased, and no known response may be retried to choose a better answer. Abandoned token usage is unknown: the unchanged token analysis uses received usage counters, while conservative dollars also include the full abandoned reservation. No token counts are invented. Keep that limitation visible when interpreting any qualifying result.
