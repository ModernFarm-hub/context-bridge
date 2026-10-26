# Architecture

Explicit imports → text normalization and redaction → SQLite records and profile-scoped FTS5 → stdio MCP search/read → citations.

The runtime uses the Python standard library. Imports, storage, ranking and MCP adapters are separate modules. `context_read` resolves random, profile-scoped record handles and never accepts a model-supplied filesystem path. Historical internal Python interfaces retain local locators for existing fixtures and migrations.

## MCP SDK decision

We considered the official Python SDK and FastMCP. This candidate retains its small stdio adapter to preserve the requested Python 3.9 support and avoid required runtime dependencies. The official SDK's v1 branch requires Python 3.10+, while its main branch currently requires Python 3.11+. See the official [v1 metadata](https://github.com/modelcontextprotocol/python-sdk/blob/v1.x/pyproject.toml) and [main metadata](https://github.com/modelcontextprotocol/python-sdk/blob/main/pyproject.toml).

The adapter implements initialize/initialized, ping, tools/list and tools/call with newline-delimited JSON-RPC. It negotiates `2025-06-18` and `2025-11-25`, logs diagnostics to stderr, and exposes two tools. It does not claim implementation of optional resources, prompts, subscriptions, tasks, or HTTP transport. Regression tests exercise this supported surface. SDK-client compatibility can be checked with `tools/sdk_smoke.py` in a separate Python 3.10+ environment with the official v1 SDK installed.

Maintaining a protocol adapter has a compatibility cost. If Python 3.9 is dropped, prefer migrating the transport boundary to a supported SDK rather than growing a custom HTTP implementation.

## Storage and incremental ingestion

New local profiles use `library_id`/`profile_id`. Legacy configuration names and SQLite ownership columns remain readable to preserve data and citation handles. No enterprise identity guarantee is implied.

Each local profile has its own FTS5 corpus, maintained by SQLite triggers. Queries use normalized terms, BM25 ranking and source-preserving passage selection. Incremental ingestion tracks file metadata, byte offset, complete-line count and bounded prefix/tail hashes. Profile parsing is cached by inode/size/mtime/ctime, canonical paths and per-source ingestion states are reused, metadata writes compare a SHA-256 hash, and refresh mutations join one transaction. Imports likewise share one connection/transaction and write the profile once. Approved Code directories are rediscovered during refresh; removed paths/IDs stay excluded. Recognized secrets are redacted before indexing; passage offsets and hashes refer to redacted text. See [security boundaries](../SECURITY.md) and [benchmark results](MILESTONES.md).

## HTTP is deferred

The optional localhost manager is not an MCP HTTP endpoint. A future Streamable HTTP transport could connect remote clients, including ChatGPT developer-mode connectors, but would require HTTPS/tunneling plus authentication and a review of who can access imported conversations. Exposing the library through a tunnel changes the privacy boundary. This candidate creates no tunnel and provides no remote connector.
