# Changelog

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
