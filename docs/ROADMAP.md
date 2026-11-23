# Roadmap

Last updated: 2026-11-22. Context Bridge is a free, open-source, local-first project. Priorities come from public testing and user questions; they can change.

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
- **Candidate: trace a commit to the AI session that produced it.** A local feasibility check matched 31 of 33 commits in this repository to the Claude Code or ChatGPT desktop session that made them. Explaining *why* needs the originating request and tool evidence, and links must stay at turn level so unrelated private content in the same session is never exposed. Built only if users ask for it.

## Later

- Encryption at rest, an administrator policy file, Windows support, a threat model and SBOM.
- More local sources, such as Cursor and Gemini CLI.
- `context_save`: save a decision from the current session as a searchable, cited note.
- Filters (provider, date range, project) and better titles for untitled ChatGPT conversations.

## Not planned

- Paid tiers, hosted services or data collection.
- Scraping chatgpt.com or claude.ai. Web history arrives only through official exports until providers offer a history API.
- Claims of token or cost savings without a pre-registered result that supports them.
