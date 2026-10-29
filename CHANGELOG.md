# Changelog

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
