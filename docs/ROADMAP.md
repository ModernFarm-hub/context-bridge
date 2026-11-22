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

## 0.9: proof and automatic reuse

The goal is to show, with reproducible numbers, when reusing past research is cheaper than redoing it, and to make reuse happen without the user having to ask.

- **Savings benchmark.** The same research tasks run by an agent with and without Context Bridge, measuring tokens, wall time and answer accuracy. Published method and results that anyone can re-run.
- **`context-bridge savings`.** A local report estimating the tokens and time saved by reused answers. Computed on the user's machine; no telemetry.
- **Automatic consultation.** Ready-made `CLAUDE.md` / `AGENTS.md` guidance and a Claude Code hook or plugin that checks past sessions before new research, with strict token limits.
- **Compact results.** Token cost per tool call is measured, with a compact output mode so a lookup costs far less than the research it replaces.

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
