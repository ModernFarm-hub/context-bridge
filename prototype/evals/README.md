# Retrieval baseline evaluation v1

Run from the prototype directory:

```sh
python3 evaluate.py
```

Default output is now the app data directory under `reports/latest`, containing `report.html` and machine-readable `results.json`. Use `context-bridge paths` to locate it, or `--output` to select a directory. No model subscription, API key, server, private transcripts, or network access is required. Existing manager/session data is untouched: each trial gets its own disposable database and source fixtures. Synthetic traces are retained in JSON; temporary source files are removed after each trial.

## Dataset and metrics

`scenarios.json` has 20 retrieval scenarios (18 positive, 2 negative) and 10 control scenarios. Each repeats three times, creating 90 trials. These deterministic repeats are not 90 independent customer tasks and do not establish statistical confidence. Development and reserved heldout labels allow separate reports; the heldout subset was authored in this same project and is not a blind external benchmark. Avoid tuning against it; create an independent customer-informed acceptance set before a pilot.

Expected evidence IDs, optional required passage text, queries and case labels remain outside indexed transcript content. Evidence IDs map to source-file/line locators. Multi-session questions require every annotated passage. A conflict case checks that both sides are retrieved, not whether a model resolves them. The updated-decision case additionally checks first-result ranking, not model reasoning. Missing-answer evidence is scored as retrieval of uncertainty, not demonstrated answer abstention.

- **Macro Recall@5:** required evidence recovered divided by required evidence for each positive scenario, averaged across positive trials. The long-passage probe requires supporting text to be visible in the returned passage, not merely present somewhere in the source record. Exceptions count as failed retrievals.
- **Macro Precision@5:** relevant supported passages divided by returned passages, averaged over positive trials with nonempty results. Missing-result positives are covered by recall; precision is not padded to five when fewer results return.
- **MRR:** reciprocal rank of the first relevant supported passage, averaged over positive trials; missing evidence scores zero.
- **nDCG@5:** discounted binary relevance against the ideal ordering of annotated evidence, averaged over positive trials.
- **Source locator validity:** returned passage is a substring of its original fixture content, with matching session, line, timestamp and role. This is not semantic citation accuracy or claim entailment.
- **Negative-case pass rate:** fraction of expected-empty queries returning no results.
- **Isolation probes:** another employee's or tenant's record is positively confirmed in the same database, then searched/read as the test employee. This proves local filtering for those probes, not production authentication. Control errors fail the gate conservatively and are recorded with a reason; investigate failures before calling them confirmed data leaks.
- **Revocation:** the same service first retrieves the passage, then must stop returning it after an allowlist change completes. This is a serial local-service check, not a distributed concurrency proof.
- **Retrieval + refresh p95:** nearest-rank percentile of the timed service call, including transcript refresh. Setup and model generation are excluded. Fixtures are tiny; this is not a scale benchmark.
- **Local fixture freshness p95:** completed/flushed fixture write to the next query result in append/partial-record probes. Excludes Claude's own transcript flush delay, network and polling. End-to-end live freshness is unmeasured.

Proposed automated gates: recall >=90%; all control probes pass; negative cases all pass; locator validity 100%; local retrieval+refresh p95 <=2,000ms; local fixture freshness p95 <=10,000ms. Passing these narrow gates would not make the system enterprise-ready. The baseline intentionally preserves shortcomings in the current keyword implementation.

## Reproducibility and CI

```sh
python3 evaluate.py --split development --repetitions 3 --output /absolute/path/to/development-report
python3 evaluate.py --split heldout --repetitions 3 --output /absolute/path/to/heldout-report
python3 evaluate.py --fail-on-threshold
```

Default execution exits successfully when the report is generated, even when performance is below target. `--fail-on-threshold` returns exit code 1 for unmet gates. A split missing a required metric cannot establish all acceptance gates. Reports include dataset version/hash, implementation hashes, Python/platform metadata, trial traces, subset metrics and failures. No model is selected or invoked.

To add a retrieval case, author source records, a realistic question, evidence IDs and optional `required_text` / `top_evidence`. Use a unique ID. Add hard distractors and record the provenance of any future customer-informed fixture without copying sensitive data into this repository.

## Separate answer-quality phase

A later opt-in evaluator should call the target AI client/model with retrieved evidence, save model version/prompt/parameters, and grade claims against a reference rubric. Measure completeness, unsupported claims, semantic citation correctness, conflict handling and abstention. Include adversarial retrieved instructions and human review of failures and a sample of passes. Never infer those scores from retrieval metrics. Any paid model use or corporate-data handling must be explicit.


## Compare retrieval revisions

The original run is preserved under `evaluation/baseline`. To produce a fresh candidate and compare without overwriting the original:

```sh
python3 evaluate.py --output ../evaluation/improved
python3 compare_evaluations.py --baseline ../evaluation/baseline/results.json --candidate ../evaluation/improved/results.json --output ../evaluation/comparison.md --fail-on-regression
```

The comparison rejects mismatched dataset hashes, subsets, repetition counts or scenario IDs. Regression gating checks previously passing cases and overall recall; it is separate from the stricter acceptance gate. A candidate may improve with zero regressions while still missing acceptance targets.

The v0.3 lexical candidate scored 28/30 scenarios and 88.9% Recall@5. R10 (latest decision), R14 (long passage), R15 (distractors) and R20 (common-word false positives) improved; no cases regressed. R05 and R06, both paraphrases, remain unresolved. The baseline already exercised the reserved subset, so this is regression evidence rather than independent blind validation. No hard-coded scenario synonym pairs were used.


## Local hybrid candidate

See `SEMANTIC.md` for the installed local embedding runtime and explicit `--semantic-model` commands. The default evaluator remains lexical so historical baselines can be reproduced without optional dependencies. Hybrid reports record the local embedding model, revision, load time and inference count. `model_calls` refers only to generative calls (zero); local embedding calls are counted separately.

Current outcomes: original benchmark 30/30 and 100% Recall@5; new 16-scenario validation 13/16 and 66.7% Recall@5. Both comparisons preserve lexical results and show no case regressions. Do not report the first result as proof of general production recall above 90%.


## Portable alpha

Installed commands are `context-bridge evaluate`, `context-bridge evaluate --validation`, and `context-bridge compare`. State and default reports no longer depend on the checkout layout. Use `--semantic-model` for hybrid evaluation. Default mode remains lexical even when the manager uses hybrid mode. See SEMANTIC.md for installation and default model paths.
