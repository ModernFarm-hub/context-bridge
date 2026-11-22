# Savings: method, tasks and limits

Context Bridge is free and open source. These results are a **synthetic counterfactual**, not measured customer savings. No employer, client, pilot or private conversation data was used. No new paid API run was performed for this policy change. Previously recorded synthetic live runs are reported below. There is no dollar result without an explicitly supplied price.

## Reproduce offline (free, default)

```sh
context-bridge benchmark --savings --output /tmp/savings.json
# From a checkout, without installing anything:
python3 prototype/benchmark.py --savings --output /tmp/savings.json
```

CI runs only this offline mode. The unit tests also block network calls in the offline path. The benchmark uses a disposable profile, never your real library. This published local run used Darwin arm64, Python 3.9.6 and SQLite 3.51.0. It samples one pipeline per task per format and one hook call per task; the JSON includes the fixture SHA-256 hash. Exact task definitions, reference answers, synthetic token budgets and negative-case labels are in [savings-tasks.json](../../prototype/evals/savings-tasks.json); [complete local results](savings-offline.json) include per-task counters, response costs, ranks, correctness checks and hook measurements. The expected answers/validity labels are not passed into retrieval or injected by the hook.

Each of twenty invented sessions contains a user question, a tool-planning assistant message, excluded tool-output/placeholder-thinking filler, and final assistant findings. Input/output/cache counters are **invented**, split across the assistant messages, not measured by a provider or tokenizer. Only indexed question/finding text is returned. Original counterfactual budgets remain an assumption even when response sizes are measured. Questions are ordinary keyword-rich retrieval questions, not a paraphrase challenge. The code actually searches and reads the selected top conversation (including surrounding indexed turns), then checks the visible passage for the reference substring. It does not run a model or score generated answers. Gold labels are used only by the benchmark to deny credit to known stale/wrong answers; the real usage report cannot infer validity.

## Local offline result

Method: conservative lower-bound credit = cumulative outputs plus nonnegative context growth above the first assistant turn, assuming one redo for a correct reused conversation; lookup = sum of `ceil(len(returned text)/4)` for search and read responses. Full MCP text includes the separate readable Source lines. Compact search returns label, link, record_id, snippet, more_matches, age_days, time_sensitive and up to three time_sensitive_terms. Requests, generated model answers, embeddings/setup and CPU are excluded. Alternatives below are separate experimental arms and must not be added together.

| Arm | Hypothetical research credit | Lookup / added-context estimate | Estimated tokens avoided |
| --- | ---: | ---: | ---: |
| Full search + read | 95,687 | 20,750 | 74,937 |
| Compact search + read | 95,687 | 14,422 | 81,265 |
| Compact pipeline + optional hook | 95,687 | 16,142 | 79,545 |

The all-in upper bound is **244,165 tokens, including fixed context overhead**. It is not used as savings credit. All figures above use synthetic counters.

Top-1 and top-5 target-conversation retrieval on the 18 non-stale/non-wrong tasks were 100% and 100%. Across all 20 tasks the read-passage/reference check passed for 18 (90%): the two deliberately stale/wrong answers fail. These easy synthetic results are not a real-library recall claim. Reference-substring presence is only an answer-passage check and can misjudge useful paraphrases. No live answer-accuracy score is claimed.

Average estimated **search response** tokens: full **490.75**, compact **174.35**. Shared read responses are included in the pipeline totals but not these search-only averages. JSON serialization, score rendering and platform differences can change the estimates slightly; opaque random IDs have fixed lengths.

The optional hook added **86.00 estimated tokens per prompt** on average. This counts actual additionalContext characters divided by four, rounded up. It excludes Claude Code framing, the original prompt and model output; it is not billed-token measurement. Its conservative content ceiling is 400 UTF-8 bytes, additionally bounded by 1,200 characters and three results. The local worker timeout is 200 ms and host timeout 250 ms; measured local subprocess p95 was **105.616 ms**. The hook uses lexical retrieval to avoid cold semantic-model loading. OS scheduling and larger libraries may time out; then no context is injected. These are local macOS measurements, not a cross-machine latency guarantee.

## When reuse loses

| Task | Condition | Credited original tokens | Compact lookup estimate | Net avoided estimate |
| --- | --- | ---: | ---: | ---: |
| mint | cheap-redo | 23 | 825 | -802 |
| pine | stale | 0 | 671 | -671 |
| reef | wrong | 0 | 644 | -644 |

The cheap calculation costs more to look up than redo. Stale and wrong findings receive no research credit while still paying lookup costs. Repeated reads are not independent savings. Searching without reading earns no research credit; an empty search earns none either. In real use a read may never be used, and a correct old answer may no longer be correct. Re-verify time-sensitive answers.

## Local report method

`context-bridge savings --explain` and `--json` describe the method. Each conversation receives at most one credit: the largest original-cost snapshot among messages actually included in read pages, not merely off-page neighbor metadata. All logged search/read/hook-response estimates are subtracted, including misses, errors and unused searches. Negative totals are retained. Shared search responses are allocated once to the first later read of a returned ID; this is an attribution heuristic, not proof of causality. Per-conversation allocated lookup costs plus unassigned costs equal the total lookup cost.

- **Claude Code:** conservative lower-bound estimate = cumulative deduplicated assistant output tokens through the cited turn + `max(0, cited context - first assistant context)`. Each turn's context is `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`. This excludes the initial system/tool context whether freshly cached or read from cache. Replayed message IDs update existing counters rather than adding another turn. The sum of all input/output/cache counters is retained only as an upper bound including fixed context overhead. Exclude API-request blobs.
- **Codex:** the same output-plus-context-growth rule. Per-turn input already includes cached input; do not add cached input a second time. Prefer `last_token_usage.input_tokens` for context; when only cumulative totals exist, use their input delta. Cumulative output includes reasoning once. Associate the first following usage event with the preceding assistant passage when needed. Counter resets or unrecognized schemas can undercount.

- **ChatGPT/Claude.ai exports:** no provider usage is available. Estimate only indexed visible text through that message at characters/4. This is lower-quality and can miss original system prompts, repeated input, tools, reasoning and earlier research. It is not an original invoice estimate.

The synthetic trivial-turn regression has 2 input, 136 output, 12,121 cache-creation and 24,840 cache-read tokens, repeated with the same message ID. Credit is only **136**, while **37,099** is the upper bound including fixed context overhead. Lookup costs exceed the small credit, so the estimated net is negative. A multi-turn fixture grows context from 170 to 370 tokens and produces 30 output tokens: credit is **230**. Codex's growing-file fixture produces 200 output tokens and 500 context-growth tokens: credit is **700**.

This is a **conservative lower-bound estimate**, not a guaranteed lower bound on actual savings: a redo may never happen, outputs may be irrelevant, and new context may contain overhead. Context compaction can hide growth. Missing counters also undercount. All-in counters show the upper end of the research-cost range, not additional avoided tokens; the net can be negative after lookup cost.

The ingestion-state version is bumped so existing local source counters are rebuilt with first-turn and cited-turn context baselines. Historical usage snapshots cannot reconstruct per-turn baselines from cumulative sums alone: they receive output-only credit, preserving their all-in upper bound. Re-read a passage to capture the context-growth snapshot. Raw usage history remains unchanged.

Usage records store UTC machine time, client-reported name, opaque record IDs, response size, estimated tokens and numeric original-cost snapshots. No title, snippet or query text is stored in the usage log by default. Opt-in redacted query logging is explicit; it can still contain sensitive information because pattern redaction is imperfect. Titles/links for the report are resolved from the current local index; removed conversations can be shown as unavailable. Disabling logging affects future calls and cannot retroactively remove prior rows; `usage clear` deletes the selected profile's call history. Abrupt process death or unavailable/corrupt storage can prevent a log entry; no audit-completeness guarantee is made.

## Risk-weighted reuse policy and signals

`context-bridge agent-guide --policy economical|balanced|cautious` prints the policy (balanced by default). REUSE is for stable, low-stakes exact matches; CHECK verifies only changed facts or older evidence; REDO treats history as a lead when stakes, uncertainty or mismatch demand new research. Every preset states: “High stakes with volatility, or conflicting evidence, always require REDO.” Presets vary preferences for unclear age, evidence and match; they never prefer savings over safety. Agents state `Reuse decision: REUSE|CHECK|REDO — reason` and never present reuse as fresh verification. This is guidance, not enforced classification or a correctness guarantee. The bounded hook injects a one-line balanced summary, without increasing its hard budgets.

Full results add age_days, time_sensitive, time_sensitive_terms, uncertainty and conflicts. Compact adds only age_days, time_sensitive and up to three terms: 8 fields instead of 5. Average compact search is **174.35 estimated tokens**, versus **139.15** when only the three signal fields are dropped from the exact same payload: **+35.20 tokens per search** attributable to signals. Full search averages **490.75** tokens. These are character estimates, not model-tokenizer measurements.

Age uses the matched passage timestamp, UTC, whole days, clamped at zero for future dates; absent/invalid dates give null. Volatility detection now masks fenced code, inline code, snake_case and camelCase identifiers. “Current”, “latest” and “now” require a volatile noun within three words in the same sentence (version, release, price/pricing, rate, policy, law, regulation, API, plan, salary or valuation). Thus Java's “current prefix” does not trigger. Versions require a v prefix, at least two dots, or nearby version/release/Python/Node/API context. Percentages, including “6.25 percent” and “62.5%”, are excluded even beside API/version words; plain decimals are not version evidence. Currency symbols ($, €, £, ₹), codes (USD/EUR/GBP/INR), amounts such as “5 billion dollars” and financial words price/valuation/salary/rate trigger. Years/dates, policy/pricing and deprecated wording remain hints. Terms are returned in passage order, at most three.

The [expanded 21-case fixture](../../prototype/evals/volatility-signals.json) includes the three synthetic real-shaped regressions: current-prefix Java (negative), RSU percentages (negative), and “$5 billion valuation” / “$1 strike” (positive). It records **11 true positives, 0 false positives and 2 false negatives: precision 100%, recall 84.62%**. Both known misses remain in the recall denominator: “twenty bucks” and “newest platform build”. This small controlled fixture is not measured real-library precision. The 20-task savings fixture separately reports time_sensitive precision/recall **1.0/1.0** (6 positives), uncertainty **1.0/1.0** (1 positive).

These signals remain hints, not verdicts. Historical years, semantic-looking numeric addresses, nonfinancial “rate”, or schema discussions of “price” may still be false positives; unsupported currencies, colloquial amounts, unusual identifier styles, spelled-out versions and subtle hedges can be missed. Masking code can hide actual version/price facts intentionally. Hedges such as not sure, might, unverified, TODO and I think flag uncertainty, including possible code TODO false positives. Absence of a signal means neither safe nor certain. Conflict detection is **disabled**, always false, with a TODO to validate topic-aware contradictions before enabling it; differing numbers alone are unreliable.

Every savings task has stakes, volatility and expected_decision labels, with at least two examples per decision across the 20-task pool. Pine remains stale/high/volatile/REDO. The independent expanded volatility fixture is evaluated alongside them, without changing retrieval scores or forcing agent decisions.

## Live runs (real, small n)

These are real API measurements on **synthetic tasks**, already stored before this policy change, using the **old guide**, claude-sonnet-5-5, five tasks and four assumed research steps. They motivated the new policy; they do not validate it or establish a savings claim. No new paid run was made. Costs use the supplied $2 input/$10 output per million assumptions (no cache tariff adjustments).

### Run 1

[Raw recorded result](savings-live-run1.json); total user-priced estimate **$0.997004**.

| Task | Baseline tokens | Reuse tokens | Token change | Baseline USD | Reuse USD | Correct (baseline / reuse) | Reuse outcome |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| aster | 43,234 | 49,056 | +13.47% | 0.089516 | 0.101616 | True / True | final answer |
| willow | 43,169 | 52,287 | +21.12% | 0.089434 | 0.109382 | True / True | final answer |
| comet | 43,201 | 56,675 | +31.19% | 0.089730 | 0.118430 | True / True | final answer |
| mint | cheap-redo | 23 | 825 | -802 |
| pine | stale | 0 | 671 | -671 |

### Run 2

[Raw recorded result](savings-live-run2.json); total user-priced estimate **$0.891586**.

| Task | Baseline tokens | Reuse tokens | Token change | Baseline USD | Reuse USD | Correct (baseline / reuse) | Reuse outcome |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| aster | 43,215 | 52,506 | +21.50% | 0.089462 | 0.109444 | True / True | final answer |
| willow | 43,213 | 52,337 | +21.11% | 0.089754 | 0.109738 | True / True | final answer |
| comet | 43,183 | 54,097 | +25.27% | 0.089438 | 0.112842 | True / True | final answer |
| mint | cheap-redo | 23 | 825 | -802 |
| pine | stale | 0 | 671 | -671 |

All six positive-task reuse arms re-did all four research steps; five also read history (Aster run 1 searched but did not read). Token overhead ranged **+13.47% to +31.19%**. Mint run 2 used three API calls and one current-research step after searching/reading: **10,277 vs 43,143 tokens (−76.18%)**, with a correct answer. Mint run 1 re-did all four steps. Pine's reuse failed both times: wrong answer in run 1; call cap/no answer in run 2. Its baselines were correct both times. Outcomes varied run to run; n is tiny. Old outputs have no explicit decision line, so do not retroactively score decision accuracy. “Correct” here means reference-substring scoring, not independently audited reasoning.

## Optional live experiment (paid; not run here)

```sh
# Advisory only: refuses before any request because --yes is absent.
context-bridge benchmark --savings --live --input-price-per-million 2 --output-price-per-million 10
# Only after reviewing and explicitly consenting (requires your own API key):
context-bridge benchmark --savings --live --tasks 5 --research-steps 4 --policy balanced --model claude-sonnet-5-5 --input-price-per-million 2 --output-price-per-million 10 --yes --output /tmp/live-savings.json
```

Supply ANTHROPIC_API_KEY through your environment. The default requested model is `claude-sonnet-5-5`, configurable with `--model`; there is no silent substitution. The request uses `thinking: {"type": "between_tools"}`, `output_config: {"effort": "low"}` and `max_tokens: 2048`. It sends no temperature, top_p, top_k or forced tool_choice. Full assistant content, including thinking/signature blocks, is replayed unchanged. The new-policy harness is tested only with fake responses here. The historical old-guide runs used the requested model/settings; no new-policy paid request was made. Refusal and max_tokens stop reasons are explicitly recorded as `refused` / `truncated`, with no final-answer credit.

Default **five tasks** run positive-first: Aster, Willow, Comet, then the labelled negative cases Mint (cheap-redo) and Pine (stale). `--tasks 3` selects only the three positives; the maximum is five. `positive_results` and `negative_results` are reported separately, with condition labels retained in each row. Do not pool them as a representative savings average. Mint's offline cheap-redo label does not make the live gated research cheap: the fixed research protocol applies to every task.

Both arms receive the exact same neutral question. The baseline has only the `research` tool. The reuse arm also has Context Bridge tools and exactly the chosen product `agent-guide --policy` text as its system prompt. This compares the recommended product setup, not the isolated effect of retrieval under identical instructions. The live report parses a single explicit decision line across assistant turns, including before tool calls (missing or ambiguous lines score incorrect), compares expected decisions, reports tokens/costs/answer checks by expected class and the CHECK path versus its paired full-redo baseline. Primary metrics are wrong final answers and unanswered high-stakes/volatile tasks, low-stakes/stable savings, and decision accuracy; inspect every class before any aggregate. A CHECK path is intended to cost less, but the harness reports measured cost without assuming that success. `--task-ids aster,lantern,orbit,mint,pine` can select a different capped subset; the full pool has at least two examples per class, while any one run remains at most five. Rows explicitly report `called_context_search` and `called_context_read`, tool history, completed research steps, provider input/output/cache counters, elapsed time, stop reasons and reference-substring answer checks. Consultation and lower cost are not forced or guaranteed.

`--research-steps` controls sequential synthetic research depth (default **4**, allowed 1–10). Each step returns roughly 13,000 characters (about 3,000–4,000 estimated tokens) of invented supporting notes. Only the final step exposes the current reference answer; skipped or repeated steps receive no new notes. This forces several source calls, not genuine reasoning difficulty. The historical library contains the past findings; stale negative cases require current verification. Artificial depth and note volume strongly influence measured costs. A model can still answer without researching; the report shows that behavior rather than hiding it.

Each arm is capped at `research_steps + 2` API responses (default six), each with 2,048 maximum output tokens, including thinking. The harness makes no automatic retries. With five tasks and depth four, the advisory allows **60 API calls**, assumes **40,288 input tokens per call**, and budgets up to **122,880 output tokens**. Input assumption = `12000 + research_steps*4000 + (research_steps+2)*2048`, allowing approximate guide/tool framing, growing notes and assistant output. This is an advisory estimate, not a guaranteed spending cap; request serialization, multiple tool calls and failed-response charges can differ.

Both price flags are required; 2 and 10 are supplied USD-per-million input/output assumptions in the examples, not automatically fetched prices. Dollar estimates apply the input rate to input, cache-read and cache-creation counters and the output rate to output. They omit cache discounts and creation surcharges, so they are not invoices. The harness refuses CI, missing prices, missing consent or missing API key before any network call. No private library or usage log is sent; only invented benchmark materials go to Anthropic after consent.

**What it can show:** actual token usage, latency, consultation behavior and simple reference-substring outcomes for a small, synthetic, fixed-depth experiment if explicitly run. **What it cannot show:** representative real-world savings, factual correctness in general, realistic research complexity, reliable aggregate effects at small n, or guaranteed reuse benefits. Reference-substring checks can reject useful paraphrases or accept an answer without supporting reasoning. Report positive and negative cases, model/date, depth, prices, errors and truncations separately.

Tests use fake provider responses only. Their fabricated counters are not live measurements. The two historical old-guide runs above are the only live results reported here; no new-policy paid run was performed, and no real-world savings claim is made.

Implementation references: [Claude Code hooks](https://code.claude.com/docs/en/hooks), [Messages API](https://platform.claude.com/docs/en/api/messages). Usage counters are not one-to-one with visible text, and hook context is untrusted evidence rather than an instruction to follow.
