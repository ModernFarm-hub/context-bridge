# Running the public-document research benchmark

This experiment compares balanced Context Bridge reuse with fresh research on forty frozen public-document questions. The repository and source distribution contain about 12 MB of Python documentation with per-file sources, versions, licenses and hashes. **The wheel deliberately omits the corpus** and is checked against a 500000-byte size budget. No benchmark reads your personal library or usage log. The committed report uses fake providers and makes no measured savings claim.

Obtain the repository or download and extract the source distribution for this same version. Its data directory is `prototype/evals/savings-real`. When using an installed wheel, pass `--corpus-dir /path/to/source/prototype/evals/savings-real`. Missing data produces these instructions without making API calls. You can also reconstruct the corpus in a source checkout with `python tools/build_research_corpus.py ARCHIVE_313 ARCHIVE_314 --output prototype/evals/savings-real`; use the official Python 3.13.1 and 3.14.0 source archives. The script verifies pinned archive hashes. Corpus contents and the forty tasks have not changed in this revision.

Read [the preregistration](../../prototype/evals/savings-real/PREREGISTRATION.md), including the cost-control amendment. Task, analysis and cost-helper hashes are checked before running. v1 contains Python 3.13.1 docs; v2 overlays selected actual Python 3.14.0 module docs. It is a controlled documentation snapshot, not an installed mixed Python interpreter.

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

Review the advisory before adding `--yes`. Both `--yes` and the key are still required, and paid mode is refused in CI. No paid run was performed. Prices must cover the selected model and any applicable input tier; they are not fetched automatically. The default model remains claude-sonnet-5-5, configurable with `--model`.

Every Messages request, including optional grading, contains top-level `cache_control: {"type": "ephemeral"}`. This is Anthropic's [automatic caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), which advances the cache breakpoint with the growing conversation. Recorded uncached input, cache creation, cache read and output counters are retained separately in raw calls, transcripts and summaries. A requested cache is not a guaranteed cache hit: minimum lengths, cache expiry and prefix changes can prevent reuse. The guard always budgets a miss at the largest supplied input/read/write rate.

`--max-usd` is mandatory for paid mode and frozen on resume. Before each request, the harness reserves its conservative text-input bound times the largest input/read/write rate, plus `max_tokens` times output price. The bound uses escaped JSON bytes, a 16384-token framing reserve and 256 extra tokens per message, content block and tool schema. It is deliberately much larger than ordinary character/4 estimates. Only inline text/thinking and local tools are accepted. A calculated bound above 1000000 is refused before sending. This enforced ceiling and the total call cap define the upfront worst case; it replaces the old assumed 150000-input-token advisory.

Actual recorded cost is reconciled after every response using decimal arithmetic, across Phase A, both arms and grading. A request is not sent if its reservation plus recorded spending exceeds the cap. A conservative reservation may stop a run with money remaining. Budget stops generate incomplete, non-qualifying reports, including the requested report destination. Missing usage or an interrupted request with an unknown charge blocks new calls. Unexpected usage above the reservation is recorded and stops further requests; an already incurred provider charge cannot be undone. The guard applies to the supplied rates and these text-only bounds, not your account's other activity or a provider invoice. For an independent account-wide guarantee, use provider spending controls too.

After a pilot, stdout and `summary.json` include mean uncached input/output/cache-read/cache-write tokens per research call and per session, phase/arm means, grader means separately, and actual average document characters read per session. A full-run estimate scales the measured session means to forty original, 120 baseline and 120 reuse sessions; optional grading allows 240 judgments without deduplication savings. This projection appears alongside the enforced-ceiling worst case. It is a small-sample extrapolation, not a confidence interval or a spending guarantee, and is never used to admit a request. Use a separate directory for full mode.

`read_doc` still caps each read at 12000 characters. `--call-cap` defaults to 12 per session; `--total-call-cap` defaults to 4000 across all phases and grading. The average characters read reflects actual returned document text, including replayed tool results exactly once per session, not requested length.

Optional `--grader-model` enables a blind grader (claude-opus-5-5 if supplied without a value). Paid grading also requires `--grader-input-price-per-million`, `--grader-output-price-per-million`, `--grader-cache-read-price-per-million` and `--grader-cache-write-price-per-million`. It shares the dollar cap, with its own four rates. Grader costs are separate. Exact required-fact checks remain primary; they can reject a correct paraphrase or miss contradictions in explanatory prose, so inspect the human review sheet and optional grader.

Resume with exactly the same command and output directory. Configuration freezes prices, cap, model and code/data hashes. Completed responses and tool results replay without additional provider calls. A process lock prevents concurrent runs. Unknown billed calls never retry automatically; inspect their journal entries. Do not remove failed tasks or edit a partial run into a qualifying result.

Outputs include `raw-calls.jsonl` and per-call recovery files; original Claude Code-format `transcripts`; an isolated `library`; `results.jsonl`; `summary.json` with budget, usage, costs and strata; a seeded `spot-check.csv` with ten answers per arm; and `savings-real.md`. The CLI also writes `docs/benchmarks/savings-real.md` unless `--report PATH` selects another destination. Responses from unfinished sessions still contribute to recorded cost totals.

Interpret every variant and decision stratum alongside the overall paired ratio and bootstrap interval. Negative savings means reuse lost. Non-inferiority uses a five-percentage-point margin, not literal proof of zero accuracy loss; stale reuse must also be at least as accurate as baseline. Failures are retained. Incomplete, pilot and fake runs cannot qualify. The primary token metric includes all cache token counters; separate cache prices affect dollars, not the token ratio. Corpus dependence and shared Phase A history limit generalization.
