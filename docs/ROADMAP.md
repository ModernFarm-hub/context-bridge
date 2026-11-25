# Roadmap

Last updated: 2026-11-25. Context Bridge is a free, open-source, local-first project. Priorities come from public testing and user questions; they can change.

## What Context Bridge is for

Finding and citing past AI work across Claude, ChatGPT and Claude Code, privately on your machine: decisions, reasons and context that only your own history contains. It is **not** a token-saving tool for quick lookups; a pre-registered benchmark found the opposite (below).

## Shipped

- **0.8.0b1 (2026-11-14):** paraphrase recall (`semantic enable`, offline hybrid search; on a personal library, paraphrased questions found the right chat first in 5 of 6 cases, up from 1 of 6), automatic ChatGPT desktop (Codex) capture, results grouped by conversation.
- **0.8.1 (2026-11-22):** `demo`, a 60-second README path, a one-time semantic offer at first import, embeddings built during import.
- **0.9.0b1 (2026-11-22):** local usage log and `savings` estimates (conservative lower bound), the REUSE/CHECK/REDO agent guide with presets, age and time-sensitivity hints, compact results and an opt-in Claude Code hook.
- **0.10.0b1:** a pre-registered savings benchmark, the `repeats` opportunity report, and approval of empty project folders.

## Savings benchmark result (0.10.0b1)

Pre-registered before any paid run (commit `8f23796`), with dated formatting and infrastructure amendments made before the confirmatory results were seen. Forty public Python-documentation research tasks, three repetitions per arm, claude-sonnet-5-5:

- **Reuse used 84% more tokens than fresh research** (95% interval: 64% to 108% more). Reuse lost in every variant: same question, paraphrase, related and stale.
- **Accuracy did not suffer:** 97.5% with reuse vs 93.3% without; non-inferiority passed. Stale answers were handled safely.
- The agent guide's decision line appeared in 55% of reuse answers and matched the expected decision 4% of the time.

These tasks were quick documentation lookups (a median of 2 model calls and about 5,400 tokens of fresh research), where redoing research is cheap. Savings for long, expensive research remain untested. [Results and data](benchmarks/savings-real.md).

## Next

- **Real users before new features.** Gather what people actually find, miss or don't need, through GitHub Discussions and issues. No telemetry.
- **Experimental: trace a commit to the AI session that produced it** (0.11 alphas). On this repository it linked 34 of 35 commits. With the commit message plus session evidence, short AI answers to "why was this commit made?" were better than git alone in 7 of 10 sampled commits and never worse ([details and limits](TRACE.md#first-check-on-a-real-repository)). Next: developers trying "why is this line like this?" on their own repositories.

## Later

- Encryption at rest, an administrator policy file, Windows support, a threat model and SBOM.
- More local sources, such as Cursor and Gemini CLI.
- `context_save`: save a decision from the current session as a searchable, cited note.
- Filters (provider, date range, project) and better titles for untitled ChatGPT conversations.

## Not planned

- Paid tiers, hosted services or data collection.
- Scraping chatgpt.com or claude.ai. Web history arrives only through official exports until providers offer a history API.
- Claims of token or cost savings without a pre-registered result that supports them.

## 0.11.0a1: trace feasibility experiment

`trace` links commits to evidence in already approved coding sessions, with references only by default. `trace-eval` collects local human labels and compares the selected segment with git messages/diffs. This is an experimental alpha; matching evidence is not proof of authorship or an explanation of why. No real-session probe or quality result is bundled. Next: review synthetic failures and independently label a local sample before making any quality claim. [Method and privacy](TRACE.md).


## 0.11.0a2: short, cited AI explanations experiment

The opt-in `context_trace` MCP tool sends bounded, redacted selected evidence to the user's AI client and its model provider. It uses the existing matcher, with no new matching rules. Sensitive-term turns are withheld. `trace-eval --ai` lets one person compare short answers against a git-only baseline using a seeded sample of ten linked commits and four quick ratings per item. Next: independently collect those judgments and review unsupported reasons and privacy incidents. No explanation-quality result is claimed. [Flow and privacy](TRACE.md).


## 0.11.0a3: reason-focused evidence and developer questions

Supply the commit message alongside selected origins, approvals, decisions and informative fixed tool summaries; ask the client for a short Reason / supported Alternatives or caveats / Sources answer. Accept code locations and bounded history queries. Offer an explicit local counts-only self-report, with no monitoring or authorship claim. Next: independently judge short answers and inspect missing evidence, unsupported reasons and privacy incidents. These features are an experiment, not a quality result. [Usage and privacy](TRACE.md).

## 0.12.0a1: independent local audit experiment

Compare raw approved agent records with actual git changes, flag notable recorded actions and missing recorded controls, and distinguish unaccounted changes from plausible command-generated changes. Reports default to counts/references, with no network or repository writes. An optional profile-local hash chain can detect later changes to sealed transcript prefixes. Next: independently inspect heuristic false positives, missed actions and incomplete records before drawing conclusions. This is self-run local analysis, not proof or monitoring of other people. [Rules and privacy](AUDIT.md).


## 0.12.0a2: audit precision and concise reports

Recognise wrapped commit/test records, distinguish literal execution from data parsing and config reads, account for linked author/committer contributors, and separate scratch information from higher-severity findings. Group repeated observations while retaining raw counts and provide a severity-filtered printed list. Continue independent inspection of the documented heuristic limits; no real-world accuracy result is claimed. [Rules and limitations](AUDIT.md).

## 0.12.0a3: multi-result and shell audit fixes

Pair distinct commit result records in shared tool calls, retain rewritten-history links, and extend literal shell recognition for substitutions, loop bodies and absolute variable targets. Separate placeholder credentials and outside log output from higher-severity observations. Continue synthetic regression checks and independent review; no accuracy claim.
