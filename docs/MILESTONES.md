# Product milestones

Retrieval research is frozen. These checks exercise product behavior using synthetic data.

## Milestone 1: reproduced bugs

- Complete malformed JSONL lines are skipped, counted and reported without stopping search. Partial trailing writes are deferred.
- New Claude Code session IDs from `/clear` remain attached to the approved named source. Revocation covers its aliases.
- Long natural-language queries are accepted up to 2,000 characters. Errors distinguish invalid queries, changed records and revoked sources. Empty searches return `no_matches`.
- MCP negotiates both `2025-06-18` and `2025-11-25`. Diagnostics use stderr.

From the project directory, verify:

```sh
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -p 'test_milestone1.py' -v
```

## Milestone 2: conversation library

Explicit imports now support ChatGPT exports, Claude.ai exports, and Claude Code transcripts. Import is local and makes those conversations available to all MCP clients using the same local library. There is no required source/reader split.

ChatGPT follows the `current_node` parent chain and excludes sibling branches. Older exports without `current_node` select the latest leaf. Claude.ai imports human and assistant text blocks. Neither web importer includes tool or thinking blocks. Claude Code previews projects before approval and uses `ai-title` records where present.

Results contain a provider/title/date `source_label`, an opaque `record_id`, and a citation `link`. Web imports link to the original conversation, which still requires access to the provider account. Claude Code uses a `urn:context-bridge:record:...` citation handle: use `context_read` to open its passage, rather than treating that handle as a browser URL. Line numbers on web imports identify normalized imported messages, not lines in the provider UI.

The MCP wire interface does not return filesystem locators and accepts only opaque IDs for `context_read`. Internal Python APIs retain local locators for backward compatibility. Diagnostic file warnings use an opaque `source_id` over MCP.

Imports are repeatable: a conversation ID replaces its prior imported snapshot rather than duplicating it. Message IDs preserve citation handles when the active branch moves a message to another line. Deleted messages become unavailable. Re-import a new export to refresh web conversations; this is not live browser capture.

### Try it locally

Install from this checkout (not yet a new PyPI release):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/context-bridge import chatgpt /path/to/chatgpt-export.zip
.venv/bin/context-bridge import claude /path/to/claude-export.zip
```

For Claude Code, first preview the local projects. Nothing is imported by this first command when run noninteractively; in a terminal it asks for approval:

```sh
.venv/bin/context-bridge import claude-code
```

To approve a project from the displayed list explicitly:

```sh
.venv/bin/context-bridge import claude-code --project 'EXACT_PROJECT_NAME' --yes
```

Run the shared MCP server with no reader config:

```sh
.venv/bin/context-bridge mcp
```

It waits for an MCP client on standard input; configure the client instead of typing chat into this process. Import and MCP must use the same local account and `CONTEXT_BRIDGE_HOME` if you override it. Existing named-session capture continues to work.

### Claude Code

Replace the executable path with the absolute path to this installation:

```sh
claude mcp add --transport stdio context-bridge -- /absolute/path/to/.venv/bin/context-bridge mcp
```

### Claude Desktop and Cursor

Add this server entry to Claude Desktop's MCP configuration or Cursor's MCP server configuration, then restart/reconnect the client:

```json
{
  "mcpServers": {
    "context-bridge": {
      "command": "/absolute/path/to/.venv/bin/context-bridge",
      "args": ["mcp"]
    }
  }
}
```

Ask: **“Use context_search to find what I decided about Kafka retries. Cite the conversation link. Use context_read if you need the surrounding passage.”**

### Regression checks

These use temporary synthetic exports and do not import your real chats:

```sh
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -p 'test_imports.py' -v
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
```

Optional model-dependent tests skip when their dependencies/models are absent. Existing retrieval behavior is preserved; no new research evaluation or model comparison was performed.

### Remaining work

Milestone 3 is implemented below. Milestone 4 still needs release packaging, registry publication, CI, security documentation, and the README/demo refresh. The current implementation is a local development build, not a published release.


## Milestone 3: trust and scale

### What changed

- Recognized API keys, AWS access-key IDs, GitHub/Slack tokens, bearer credentials, private-key blocks, and credential assignments are redacted before indexing. Newly imported web-export copies and titles are also redacted. MCP responses apply a final redaction pass. Original provider ZIPs and Claude Code transcripts are not modified.
- Credential assignments such as `API_KEY=...`, `TOKEN=...`, `PASSWORD=...` and `DATABASE_URL=...` are filtered; ordinary settings such as `RETENTION_DAYS=45` remain searchable. Pattern-based filtering cannot recognize every arbitrary secret.
- Only actual human/assistant text is indexed. Tool-use, tool-result, thinking and replayed internal API bodies are excluded. No opt-in tool indexing is enabled.
- Lexical search uses SQLite FTS5/BM25 with a separate FTS corpus per local profile, so another profile cannot affect ranking statistics. Existing optional hybrid search remains available; the performance target below covers the default lexical path.
- Ingestion stores file size, modification/change time, device/inode, complete-line byte offset and line number. Unchanged files are not reread. Appends consume new complete lines. Atomic replacement, truncation, same-size rewrites and changed prefix/tail anchors trigger a rebuild. Partial writes are deferred. Prefix/tail checks are bounded; they are not a full integrity audit of an arbitrarily modified file that also grows. Provider-export reimports use atomic replacement and rebuild correctly.
- Revoked or unavailable sources are removed from both retrieval and incremental state, allowing correct re-import/re-approval later. Removed message handles cannot read a replacement message at the same line.
- New libraries use `profile.json` with `library_id` and `profile_id`. Existing `enrollment.json` files and identity fields still load without changing their ownership scope. Legacy SQLite column names remain private compatibility details; schema additions preserve existing rows and citation handles. Existing stored bodies receive a one-time redaction migration and FTS backfill.
- The local manager uses local-library language and no longer says “ONE EMPLOYEE.” Every window opened by it can search approved sources.

### Verification commands

From this checkout:

```sh
cd /path/to/context-bridge
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -p 'test_trust_scale.py' -v
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
PYTHONPATH=prototype python3 prototype/benchmark.py --messages 100000 --runs 30
```

After reinstalling this checkout, the benchmark also runs as:

```sh
context-bridge benchmark --messages 100000 --runs 30
```

The benchmark creates and deletes its own synthetic library. It reads no real conversations. It reports initial indexing separately from search latency and includes normal refresh checks in timed search calls. It returns a failure exit status if p95 exceeds 300 ms or the appended message is not retrieved.

On the development Mac, 100,000 messages / 30 runs measured:

| Measurement | Time |
| --- | ---: |
| Initial ingestion plus first search | 6,087.81 ms |
| Search plus refresh p50 | 109.57 ms |
| Search plus refresh p95 | 117.11 ms |
| Maximum search plus refresh | 138.35 ms |
| Appended-message ingestion plus search | 8.50 ms |

This is a synthetic single-file benchmark, not a promise for every machine, message length, number of source files, or optional semantic configuration. Retrieval research and model comparisons remain frozen.


## Milestone 4: release candidate prepared; publication pending

Candidate **0.6.0a1** includes a product README, synthetic demo GIF, client configurations, SECURITY.md, a publishing guide and registry metadata template. Research documents moved to `research/docs/`; the research code/data remain unchanged for existing regression coverage and are absent from the primary CLI help. Internal research notes and generated outputs stay excluded from distribution.

The official SDK was considered; the adapter remains dependency-free to preserve Python 3.9. Its supported surface was also checked using the official MCP v1 client, version 1.30.0, on Python 3.12. A future HTTP transport is deferred and its privacy implications are documented.

Local validation:

- Python 3.9: 117 tests passed, including existing optional model tests.
- Python 3.12: 93 passed, 24 optional model tests skipped.
- Source and wheel artifacts built; package-content checks passed.
- Twine 7.0.0 strict metadata checks passed for both artifacts.
- Installed-package import, redaction, citations and stdio search/read checks passed.
- uv 0.13.5 launched the local wheel successfully; both console entry points and MCP negotiation are checked by `tools/uvx_smoke.py`.
- Generated registry metadata validated against the official server JSON schema using a temporary example namespace. No namespace was registered.

GitHub Actions is configured for macOS/Linux, Python 3.9–3.13, plus the official SDK-client smoke check. Remote runs are pending creation/publication of the intended repository; local results do not establish Linux or all-version compatibility.

Verify from the project root:

```sh
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
python3 -m venv .build-venv
.build-venv/bin/python -m pip install build twine uv
.build-venv/bin/python -m build
.build-venv/bin/python -m twine check --strict dist/*
.build-venv/bin/python tools/check_artifacts.py dist
.build-venv/bin/python tools/uvx_smoke.py dist
```

Actual GitHub, PyPI and official MCP registry publication are **not complete**. The intended owner/repository, PyPI account/ownership, and corresponding authentication must be supplied. The PyPI name `context-bridge` is already taken by another project; the prepared distribution remains `context-bridge-local`, with `context-bridge` and `context-bridge-local` console aliases. See [the exact release steps](RELEASING.md). No account credentials should be pasted into chat.
