# Changelog

## 0.9.0b1 — local reuse accounting and automatic consultation (unpublished)

- Use conservative lower-bound research credit: cumulative assistant outputs plus nonnegative context growth above the first assistant turn, for Claude Code and Codex. Deduplicate repeated message IDs, retain all-in counters as upper bounds including fixed context overhead, and preserve negative net estimates. Rebuild source accounting baselines; legacy usage snapshots without baselines receive output-only credit.
- Refuse noninteractive hook installation/removal cleanly without changing settings or printing a traceback.
- Record profile-local lookup metadata and estimated response tokens, with no query text by default; add usage controls and deletion.
- Add conservative savings reports: recorded Claude Code/Codex counters when available, clearly labelled visible-text estimates for exports, conversation deduplication and all lookup overhead subtracted. Dollar estimates require a user-supplied price.
- Add compact search results without changing the default full format. Measure both formats in a synthetic offline benchmark with stale, wrong and cheap-redo negative cases.
- Add a printed agent guide and opt-in Claude Code hook with a settings diff, explicit confirmation, backups and uninstall. Bound lexical consultation to three results, a minimum score, content budgets and a 200 ms worker timeout; fail open with no context on misses/timeouts.
- Raise the shared live per-arm cap to research depth + four, update the advisory, report cap_reached/no-answer separately from wrong answers, and explicitly report missing decision-line non-compliance. Require the decision before the final answer in guides of at most 170 words. Document balanced run 3 and retain the independently reviewed Aster/Willow/Comet labels. Fake-provider tests only.
- Tighten volatility hints: ignore code/identifiers and plain decimals, require software context for versions and volatile nouns near current/latest/now, exclude percentages, and recognize financial amounts/terms including rupees. Add a 21-case fixture retaining documented misses; clarify that high stakes with volatility OR conflicting evidence independently requires REDO.
- Add risk-weighted economical/balanced/cautious reuse guides, bounded hook guidance, local age/volatility/uncertainty hints (conflict detection disabled), decision-labelled fixtures and fake-provider decision metrics. Document both historical old-guide paid runs without a savings claim.
- Fix the live synthetic harness: positive-first tasks, separately labelled negatives, configurable sequential research depth, product agent-guide in the reuse arm, explicit consultation/refusal/truncation reporting, 2,048-token thinking-aware requests, depth-based turn caps and separate input/output prices. Test only with fake responses.
- Add a separately gated, capped Anthropic agent experiment; never run paid mode in CI and never run it without --yes and a user-supplied price. No live results are claimed in this release.

## 0.8.1 — first-run polish (unpublished)

- Replace the research demo with ten disposable synthetic conversations across ChatGPT, Claude and Claude Code; run three cited searches offline and print the exact Claude Code setup command.
- Put the demo and Claude Code quickstart first in the README. Move installation details to INSTALL.md and profile/account/removal details to USAGE.md; add a factual comparison and retain privacy boundaries.
- Offer optional local semantic search once after a successful interactive import, remember declines, and never prompt or download automatically from noninteractive imports.
- Backfill local embeddings during imports when hybrid mode is enabled, using the configured runtime and progress on stderr.
- Remove legacy research commands from public CLI dispatch and mark research documentation archived. Keep the prototype/ source directory unchanged tracked in [issue #1](https://github.com/ModernFarm-hub/context-bridge/issues/1).
- Test the offline demo, consent, import-time embedding and README quickstart through the existing CI smoke scripts.

## 0.8.0b1 — paraphrase recall and desktop capture (unpublished)

- Make Codex classification header-only and stop at the thread ID/project cwd. Cache unapproved/failed classifications across restarts using size, nanosecond mtime, inode and an approval/exclusion hash; never cache chat text. Read title excerpts only after project approval.
- Add a 200 × 5 MiB Codex discovery benchmark (five approved files), including no-Codex baseline, first refresh and steady-state p95.
- Use the FTS5 rank cursor to select distinct conversations, then compute exact match counts only for returned conversations. Preserve integer counts and remove global per-hit metadata grouping from ordinary BM25 search.

- Group results before applying `limit`: one best passage and `more_matches_in_conversation` per provider/conversation, including after hybrid fusion. Keep one readable Source line per conversation.
- Add `semantic enable --from-source PATH`, upgrade the private runtime's pip first, and explain recovery when an unreleased package version is absent from PyPI.
- Report `retrieval_mode` (`bm25`/`hybrid`) in search capture status and library stats.
- Replace the roadmap-derived fixture query with a new paraphrase and recompute the old-code baseline and current modes on the revised fixture, preserving the scoring method.

- Freeze a 30-conversation paraphrase benchmark before retrieval changes: baseline top-5 3.3%; Porter/title-weighted BM25 6.7%; local MiniLM hybrid 90.0%, MRR@20 0.8833. Expose it through `benchmark --paraphrases` and regression tests.
- Migrate existing FTS indexes to Porter stemming and weighted title columns without changing citation handles. Report stem/title matches in `matched_terms`; guide clients to try alternate phrasings.
- Add `semantic enable`: optional dependency setup, pinned model checksum verification, embedding backfill and persistent profile-local caching. Keep semantic mode opt-in and the default free of third-party dependencies.
- Add opt-in `import codex` with project previews, numbered/path selections, CODEX_HOME support and approved-project thread discovery. Parse only allowed response text; exclude injected host context, tools, reasoning and metadata. Add desktop titles, redacted fallbacks, durable exclusions and `codex://threads/` citations.
- Document source/client distinction, consent, restore/revoke commands, offline setup, benchmark limits and version 0.8.0b1 registry metadata. No remote transport is introduced.

## 0.7.0b2 — first public beta

- `context_read` returns surrounding conversation turns (`context`, default 2, maximum 10 each side) in order, with per-message record IDs, roles, timestamps and a target marker; conversation text appears once in the combined body.
- `remove --conversation` now records a hashed, per-profile exclusion: removed ChatGPT and Claude chats stay out on re-import and are reported as `conversations_excluded`. `exclusions list` and `exclusions clear` restore eligibility deliberately.
- Search results add a readable `Source: label — link` line for clients that ignore structured fields.
- Document ChatGPT desktop app STDIO setup; arguments passed as one string now produce an explicit error instead of "Unknown command".
- CI runs Python 3.9 on Ubuntu 24.04, because `ubuntu-latest` (26.04) has no 3.9 build.
- 0.7.0b1 was uploaded to TestPyPI only as a release rehearsal; it was never published to PyPI.


## 0.7.0b1 — first beta release preparation

- Prepare the `io.github.ModernFarm-hub/context-bridge` MCP registry identity, README ownership marker, repository/issue URLs and generated server metadata before the first PyPI upload.
- Synchronize the package, runtime, MCP server and registry package versions at 0.7.0b1; mark the distribution as beta.
- Carry forward the independently tested local import/search, scoped removal, project selection, credential redaction and account-isolation features from the alpha series.
- PyPI and MCP registry publication remain pending; this entry records release preparation, not a completed upload.


## 0.6.0a3 — project selection and account safety

- Accept dash-prefixed project names, numbered `--select`, original `--path` and an interactive numbered picker.
- Restrict structured credential names so database schema fields remain intact; redact Slack/Discord webhooks.
- Upgrade redaction to policy 3 for stored webhook credentials. Already-erased schema values require re-importing an original export; original Claude Code transcripts can be reprocessed.
- Improve fallback Code titles using the project folder and redacted first-user excerpt.
- Compare hashed export account identifiers before replacing a provider snapshot; require explicit confirmation for switches and offer separate named profiles across import/MCP/management.
- Commit 0.6.0a2 in logical groups; run the updated matrix through GitHub Actions before publication.


## 0.6.0a2 — independent re-test fixes, publication pending

- Reconcile provider export snapshots and remove absent conversations, reporting removal counts.
- Add `list`, `stats`, and scoped conversation/provider removal with complete index/copy cleanup.
- Expand credential redaction, bump the policy to version 2, and migrate existing index metadata and owned working copies.
- Batch export imports into one database transaction/connection and one profile write, with progress and unchanged-copy detection.
- Cache profile parsing and canonical paths; skip unchanged metadata writes and batch refresh updates.
- Discover new Claude Code sessions only within explicitly approved project directories; respect removals.
- Update MCP descriptions, macOS pip setup guidance, and the benchmark to 5,000 files containing 2–40 messages each.


## 0.6.0a1 — local release candidate, publication pending

- Import official ChatGPT and Claude.ai exports with conversation URLs and metadata.
- Preview and approve existing Claude Code projects before importing.
- Search one shared local library from stdio MCP clients, with no required source/reader split.
- Add opaque record IDs, source labels, paginated reads and changed-record checks. Public MCP `context_read` now requires `record_id`; reconnect clients after upgrading so they refresh the tool schema.
- Skip malformed transcript lines with diagnostics; preserve named-source capture across new session IDs.
- Negotiate supported MCP versions and return actionable tool errors.
- Redact recognized secrets before indexing and on MCP output; exclude tool/thinking bodies.
- Add incremental ingestion and profile-specific SQLite FTS5/BM25 indexing.
- Use local profile terminology while retaining legacy configuration/database compatibility.
- Prepare a product README/demo, security policy, CI matrix and publishing/registry instructions. Move historical research docs aside; retrieval research remains frozen.

The distribution name is `context-bridge-local`; `context-bridge` on PyPI is an unrelated project. Publication and remote CI results must be verified separately from local build checks.
