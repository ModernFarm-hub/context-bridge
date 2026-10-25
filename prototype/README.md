# Context Bridge — local engineering prototype

This executable spike proves explicit transcript import, cross-session keyword retrieval with record provenance, retry-safe appended records, scoped deletion, and ownership filtering. Python 3.9+; the lexical mode uses the standard library only; no subscription, external packages, network requests, or model calls required.

## Run

From this directory:

```sh
python3 demo.py
python3 -m unittest discover -s tests -v
```

The demo creates disposable synthetic records for Alice's four sessions and Bob's private session, searches Alice's records, and confirms Bob's private finding is excluded. All demo data is temporary.

## Optional explicit import interface

Create a local enrollment JSON file containing `{"tenant":"example-company","employee":"alice"}`. Then use:

```sh
python3 bridge.py --db context.db --enrollment enrollment.json ingest /absolute/path/to/approved-transcript.jsonl
python3 bridge.py --db context.db --enrollment enrollment.json search 'retention policy'
python3 bridge.py --db context.db --enrollment enrollment.json delete-session SESSION_ID
```

Import only approved files. The adapter currently accepts complete newline-terminated JSON records with top-level `type` of `user` or `assistant`, a matching message role, `sessionId`, optional `timestamp`, and `message.role` / `message.content`; content may contain text or nested tool-result text. This is a provisional adapter tested against synthetic fixtures, not a verified guarantee of every Claude transcript format. Thinking blocks, tool arguments, attachments, and non-message events are excluded. No transcript directories are scanned automatically.

## Security boundary and limitations

- Ownership filters apply before records are loaded for ranking. Identity labels come from a local enrollment file; they are NOT verified enterprise identity. Anyone controlling this file or the database can bypass local isolation. Do not use this version for multi-user production storage.
- The database is plaintext, with restrictive permissions for newly created files. Encryption, secrets filtering, enterprise enrollment, policy enforcement, audit exports, retention scheduling, backup deletion, and administrator separation remain unimplemented.
- Search uses owner-scoped BM25 with common-word filtering and conservative plural normalization. It is lexical retrieval, not semantic search or synthesis. It caps query-focused original passages at 4,000 characters and results at 20. Explicit recency queries prioritize subject coverage and valid timestamps. A production system needs indexed retrieval and passage selection around matches.
- Ingestion re-reads an explicitly selected file on each call. Appends and partially written trailing records are supported. Complete-record rewrites and truncation are reconciled. The MCP service withdraws removed allowlist entries and unavailable files before retrieval; upstream document permissions are not revalidated.
- Session deletion removes logical rows only; it does not promise secure erasure of SQLite pages, filesystem copies, or backups. A later re-import can restore deleted records; retention requires tombstones and lifecycle policy.
- Source locators refer to imported files and line numbers, not immutable evidence archives. Retrieval output is untrusted recorded evidence, not instructions.
- No Claude settings were changed, private conversations read, or hooks installed. A local stdio MCP server now exists and refreshes approved files on each query. No background watcher, desktop UI, or cloud service exists yet.

## Test inside Claude Code

Run `python3 setup_demo.py` from this directory. It prepares four persistent synthetic transcripts under the workspace's `work/context-bridge-demo` directory and prints a launch command. Run that command in a terminal where Claude Code is available. It uses a launch-specific MCP configuration and does not install global Claude settings.

Inside Claude, use `/mcp` to check for `context-bridge-demo`. Then ask:

> Use context_search to find Project Cedar retention findings from my other sessions. Cite the session and source line. Use context_read if you need the original passage.

Expect the synthetic 90-day policy and references to `cleanup.py`. The tool returns evidence; Claude writes the explanation. Calling Claude uses your normal Claude account and sends the selected synthetic tool results into that session's model context.

To demonstrate refresh, append a new complete record to the synthetic `research.jsonl` file and query its unique words again. No server restart is needed. For real session enrollment, first verify a selected transcript's format and add only explicitly approved absolute paths to the local `enrollment.json` allowlist. Do not point it at an entire private transcript directory.

The tool arguments contain no employee identity or arbitrary file-import operation. Identity and capture scope come from the launch configuration. This remains a local test boundary, not enterprise authentication. Search and read refresh all approved files on demand; this favors correctness over scale and is not an incremental background collector.

The stdio implementation targets the MCP 2025-11-25 lifecycle and negotiates that version. Subprocess protocol tests pass; a real Claude-client connection is pending verification on the user's terminal. It has not been tested against newer protocol-only clients.

## Next integration milestone

Verify representative Claude transcript fixtures with explicit user-selected files; verify the live Claude-client connection and capture; move refresh to an efficient incremental collector. Search/read through the local MCP interface is implemented. Keep the identity boundary pluggable so production service identity comes from verified company enrollment rather than model arguments.

Claude's [official hooks reference](https://code.claude.com/docs/en/hooks) documents `session_id` and `transcript_path` in lifecycle events. Hook wiring is deliberately pending transcript-format and capture-policy validation.


## Named session manager

Run `python3 session_manager.py` from this directory, or open `Open Context Bridge.command` in Terminal. The manager opens a private local browser page and stays running until Ctrl+C in its Terminal window. If macOS blocks the launcher, use the Python command directly.

1. Enter a name such as “Confluence research” and click **Create and approve**.
2. Click **Open source** on that row. A Terminal window labeled SOURCE opens. Enter harmless findings there and wait for Claude to reply.
3. The manager polls file readiness every four seconds. “Ready” means a nonempty registered transcript exists, not that a background indexer is running.
4. Click **Open reader in Terminal**. This separate window is labeled READER and has only the configured retrieval tools. Ask it to use `context_search` and cite sources.
5. Create additional named sources in the same way. The reader searches all currently approved sources belonging to this local enrollment. Search/read responses include the chosen session names.
6. Click **Revoke** to stop new retrieval and remove the session's indexed rows. Later source hooks cannot reapprove it. **Approve** deliberately reenables capture and makes its existing history available again on the next query.
7. **Rename** changes the displayed name and subsequent tool results. It does not alter the original transcript.

The manager uses a separate workspace under `work/context-bridge-manager`. Earlier revoked live-test sessions remain revoked and are not imported. It creates only fresh sessions or resumes its own registered sessions; it does not discover arbitrary existing conversations.

The UI listens on a random loopback port. Control requests require a random per-launch token, an expected Host header, and a matching Origin when provided. Content names are rendered as text rather than HTML. The private launch URL contains the token in its fragment; keep it private. Local configuration remains editable by the OS user and is not verified enterprise identity. The HTTP handler has in-memory request tests. After local-server permission was granted, loopback binding, browser rendering, named-session creation, and browser revocation were verified. Native Terminal launch remains to be tested with a source/reader pair.

Manager operations and MCP retrieval use the same configuration lock so a completed revocation cannot be undone by a concurrent retrieval refresh. A request already delivering content can complete before revocation. Configuration and index deletion are separate writes: if deletion fails, the allowlist still prevents future retrieval and the next refresh retries withdrawal. This is prototype behavior, not a distributed authorization design.


## Repeatable evaluation

Run `python3 evaluate.py` to evaluate 30 synthetic scenarios, repeated three times, without a model subscription or private session data. The HTML report and JSON traces are written to `outputs/context-bridge/evaluation`. For CI, add `--fail-on-threshold`; an unmet target then exits with code 1. See `evals/README.md` for metric definitions, limits and dataset extension instructions.

The first baseline passed 24/30 scenarios with 77.8% macro Recall@5. All local control probes passed, but retrieval remains below its proposed 90% recall target. Answer quality, semantic citation accuracy and enterprise authentication are not measured by this benchmark.


### Retrieval improvement v0.3

The original baseline is preserved under `evaluation/baseline`; the improved report is under `evaluation/improved`. The same 30 scenarios now pass 28/30 with 88.9% Recall@5, up from 24/30 and 77.8%. No scenario regressed. All local controls still pass. The 90% recall target is still unmet: both remaining failures are paraphrases requiring meaning-based retrieval.

Restart an existing reader process to load the new code: exit that Claude reader and open a fresh reader through the manager. Existing source sessions and approvals can stay in place. Running evaluators does not change the local manager state.

See `evaluation/comparison.md` for the comparison and `evals/README.md` for rerun commands. These directories are relative to the project root above this prototype directory.


### Local semantic search v0.4

Hybrid keyword + semantic retrieval is implemented and enabled for the manager. The model runs locally in a separate virtual environment under `work/semantic-venv`; existing source approvals were preserved. Restart readers to load it. Running `evaluate.py` with no semantic flag still measures the dependency-free lexical baseline.

See `evals/SEMANTIC.md` for installation, reproduction, rollback and boundaries. The original benchmark passes 30/30 at 100% Recall@5; the separate validation set passes 13/16 at 66.7% recall, so general acceptance is not established. Results are in `../evaluation/semantic-summary.md`.
