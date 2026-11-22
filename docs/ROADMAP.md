# Roadmap

Last updated: 2026-11-22. Context Bridge is a free, open-source, local-first project. Priorities come from public testing and user questions; they can change.

## Shipped: 0.8.0b1 (2026-11-14)

- Paraphrase recall: a frozen 30-query synthetic benchmark, Porter stemming and title weighting, and `semantic enable` for offline hybrid search with a pinned, checksum-verified local model. On a personal library, paraphrased questions found the right chat first in 5 of 6 cases (0.7.0b2: 1 of 6).
- ChatGPT desktop (Codex) threads are captured automatically from approved project folders.
- Results are grouped by conversation, and the active retrieval mode is reported.

## 0.8.1: first impression

- A `demo` command that searches a disposable synthetic library offline.
- A shorter README with a 60-second Claude Code path and a factual comparison with related tools.
- An offer to enable semantic search after the first import; embeddings built during import.
- Legacy research commands removed from the product CLI.

## 0.9.0b1: implemented locally, pending release

Local accounting, compact results, printed agent guidance and an opt-in bounded hook are implemented. The goal is to make the cost of reuse visible, including failures; no universal or measured real-user savings claim is made.

- **Offline proof fixture:** twenty invented research sessions, explicit synthetic usage counters, measured response character estimates, and stale/wrong/cheap-redo negative cases. [Methods and results](benchmarks/savings.md).
- **Local savings report:** recorded Claude Code/Codex counters or lower-quality visible-text estimates, one counterfactual redo credit per conversation actually read, with all lookup overhead deducted. No query text by default, no telemetry, optional user-priced dollars only. No wall-time savings estimate for historical conversations.
- **Automatic consultation:** a tested CLAUDE.md/AGENTS.md instruction block and an opt-in Claude Code hook. It uses bounded lexical search, not cold semantic inference, within a 200 ms worker budget; host timeout is 250 ms. Misses and timeouts add no context.
- **Compact results:** five concise fields per result; benchmark full and compact response token estimates separately.
- **Live validation remains opt-in and unrun:** a capped synthetic Anthropic agent harness measures provider usage, wall time and reference-substring accuracy with and without reuse tools. It requires a price, --yes and a key, and refuses CI. Public live claims require a separately consented run, including negative cases.

## 0.10: trust at scale

- Encryption at rest for the local database.
- An administrator policy file: excluded projects and folders, redaction rules and retention.
- Windows support and deployment-friendly configuration.
- A threat model, SBOM and security overview.
- Large-library benchmarks (100,000+ conversations), including semantic search.

## Later

- Reuse across a team through a self-hosted service or a shared folder, with permissions. Never a hosted service run by this project.
- More local sources, such as Cursor and Gemini CLI.
- `context_save`: save a decision from the current session as a searchable, cited note.
- Filters (provider, date range, project) and better titles for untitled ChatGPT conversations.

## Not planned

- Paid tiers, hosted services or data collection.
- Scraping chatgpt.com or claude.ai. Web history arrives only through official exports until providers offer a history API.

Risk-weighted reuse guidance and heuristic search signals now distinguish REUSE/CHECK/REDO. Historical small-n synthetic live runs used the old guide; the new policy is tested with fake responses only. Next validation should measure decision accuracy and high-risk answer failures by class, not just token totals. Conflict detection remains disabled pending validation.
