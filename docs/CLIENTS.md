# Connect your MCP client

Import an export using `uvx --from context-bridge-local context-bridge import chatgpt /path/to/export.zip` or the installed `context-bridge` command. The server runs over stdio; it waits for an MCP client rather than a chat prompt.

## ChatGPT desktop app

The following local STDIO setup was verified by an independent tester on real data: ChatGPT desktop retrieved a past ChatGPT conversation through Context Bridge after built-in history search missed it. It applies to the tested desktop build with **Settings → MCP servers**; UI availability can vary by build.

### Settings setup

1. Open **Settings → MCP servers → Add server → STDIO**.
2. Set **Command** to the absolute path from `which context-bridge` (or `which uvx`).
3. Add **one value per argument field**. For the installed command, enter `mcp`, `--profile`, `personal` as three separate values. With uvx, enter `--from`, `context-bridge-local`, `context-bridge`, `mcp`, `--profile`, `personal` as six separate values.
4. Save, then **Restart**. For configuration edits, fully quit with **⌘Q**, reopen the app, and start a **new chat**.

Import into the same profile first, for example `context-bridge import chatgpt /path/to/export.zip --profile personal`.

### Configuration file setup

For the tested desktop build, merge this into `~/.codex/config.toml` (do not overwrite other settings):

```toml
[mcp_servers.context-bridge]
command = "/absolute/path/to/context-bridge"
args = ["mcp", "--profile", "personal"]
```

Alternatively, use uvx:

```toml
[mcp_servers.context-bridge]
command = "/absolute/path/to/uvx"
args = ["--from", "context-bridge-local", "context-bridge", "mcp"]
```

The uvx example uses the default profile. Append `"--profile", "personal"` to its arguments to search the personal profile. Replace the executable path with the actual absolute path on your machine. Fully quit with **⌘Q**, reopen, and start a new chat after editing.

### Troubleshooting

Entering `mcp --profile personal` in a single argument field creates `args = ["mcp --profile personal"]`. The server exits because it received one command string rather than three arguments. Older versions report **Unknown command**; newer versions explain that arguments must be separate. `/mcp` may still show the server as **Enabled**, while chats say `context_search` is unavailable. Split the arguments, restart the app, and use a new chat. Enabled alone does not prove a working connection.

**Auth unsupported** in `/mcp` is normal for a local server; no authentication flow is required for this local STDIO configuration.

`chatgpt.com/c/<id>` citations are web conversations: open them in a browser signed in to the exported account. They are not desktop-app threads, whose links look like `codex://threads/<id>`. ChatGPT opens a conversation at its end, not at the cited message, so in a long chat the cited passage can be far above where the page lands; use `context_read` for the exact passage.

Ask: “Use context_search to find my past discussion of X. Cite the source conversation link.” Search responses include a readable `Source: label — link` line as well as structured citation fields.

### Limits

`chatgpt.com` in a browser cannot use local STDIO servers. Context Bridge offers no remote mode, and none is planned without an explicit security design. This setup keeps the server local, but retrieved passages are supplied to your AI client and may be processed by its provider under your account settings.

## Claude Code

```sh
claude mcp add --transport stdio context-bridge -- uvx --from context-bridge-local context-bridge mcp
```

Run `/mcp` in Claude Code and check the connection. All sessions using that configuration can search the same approved local library.

## Claude Desktop

Open Claude Desktop's developer configuration and merge this entry into its `mcpServers` object, then restart/reconnect:

```json
{
  "mcpServers": {
    "context-bridge": {
      "command": "/absolute/path/to/uvx",
      "args": ["--from", "context-bridge-local", "context-bridge", "mcp"]
    }
  }
}
```

Replace `/absolute/path/to/uvx` with the output of `which uvx` (for example `/opt/homebrew/bin/uvx`). Desktop apps launched from the Dock may not inherit your shell's PATH, so a bare `uvx` can fail with a "command not found" connection error.

## Cursor

Use Cursor's MCP configuration (for example, project `.cursor/mcp.json`) with the same `mcpServers` entry above. Reconnect the server in Cursor's MCP settings.

## ChatGPT desktop / Codex as a source

Client setup above connects a model to the search tools. Capturing desktop conversations is a separate, explicit approval:

```sh
context-bridge import codex                       # preview only in a noninteractive shell
context-bridge import codex --select 1,3 --yes --profile personal
context-bridge import codex --path /path/to/project --yes --profile personal
```

In an interactive terminal, the preview offers a numbered selection and confirmation. `--yes` without a selection approves all displayed projects. Preview groups threads by their `turn_context.payload.cwd`; it does not index them. Threads with no project cwd or session identifier are skipped. The default state directory is `$CODEX_HOME` or `~/.codex`; override it with `--codex-home`. Only selected projects are approved. The server checks new rollout files in that approved state directory on refresh, classifies their projects, and indexes only approved projects. Classification reads only session/turn headers and stops at the first thread ID and project cwd. A persistent, per-profile rejection cache records paths plus size/mtime/inode and an approval/exclusion hash, never titles or chat text. Unchanged unapproved or unclassifiable files are not opened again; changed files and changed approvals/exclusions invalidate the cache. Title excerpts are computed only after project approval. Previews use the same header-only classifier; unapproved message bodies are not decoded, stored or returned.

Rollouts are read in place from `sessions/YYYY/MM/DD/rollout-*.jsonl`. Complete appended lines are ingested incrementally; malformed lines are skipped and reported in capture status. Unknown record types are ignored. Only `response_item` messages in user/assistant roles contribute `input_text`/`output_text` text. Developer/system messages, reasoning/encrypted content, custom/function tool calls and outputs, events, token usage, turn/world state, and known host-injected user context blocks are excluded. This is a format-specific parser; new envelope formats may need an update. Titles come from `session_index.jsonl`'s `thread_name`, falling back to the first redacted user excerpt.

Results are labeled `ChatGPT desktop · 'Title' · YYYY-MM-DD`, link to `codex://threads/<thread-id>`, and contain opaque record handles without local filesystem locators. Original rollout and index files are never modified.

```sh
context-bridge remove --conversation codex://threads/THREAD_ID --profile personal
context-bridge exclusions list --profile personal
context-bridge exclusions clear --conversation codex://threads/THREAD_ID --profile personal
context-bridge remove --provider codex --profile personal
```

Conversation removal blocks rediscovery using a provider-scoped hash. Clear its exclusion to deliberately allow discovery again while the project remains approved. Provider removal also withdraws all Codex project approvals and excludes currently imported threads. To restore after provider removal, clear the desired exclusions and approve the projects again. No sources are approved by installation or by configuring the MCP client.

## Optional offline hybrid search

```sh
context-bridge semantic enable --profile personal
context-bridge semantic disable --profile personal
```

Enable installs optional `[semantic]` packages in an isolated runtime when missing, fetches pinned checksum-verified MiniLM files, and backfills embeddings for that profile. It reports size, elapsed time and record count. To reuse a verified local model, pass `--model /absolute/path/to/all-MiniLM-L6-v2`. The runtime upgrades pip before installing the extra. If an unreleased version or non-editable source install cannot resolve its own version on PyPI, the command explains the cause. Use `context-bridge semantic enable --from-source /path/to/context-bridge --profile personal` to install the checkout's extra instead. Setup needs network only for missing packages/model files; no chats are uploaded. Search is offline, combines title-weighted BM25 with vectors, and stores embeddings in the local profile database. Restart the MCP client after changing modes; `context-bridge mcp` automatically uses the configured semantic runtime. Default lexical mode remains dependency-free. `matched_terms` helps identify lexical overlap; a semantically relevant result may have an empty list. Clients should try two or three phrasings when an initial search is weak and cite the returned link.

## Pin a version

To pin this alpha explicitly, replace `context-bridge-local` in the uvx arguments with `context-bridge-local==0.12.0a3`:

```sh
uvx --from 'context-bridge-local==0.12.0a3' context-bridge mcp
```

The package source is explicit because the PyPI name `context-bridge` belongs to a different project. [uv's package/command naming documentation](https://docs.astral.sh/uv/guides/tools/#commands-with-different-package-names).

## Alternative: installed command

If you installed with `uv tool install context-bridge-local`, `pipx install context-bridge-local`, the `~/.context-bridge` virtual environment from the [installation guide](INSTALL.md), or a contributor checkout, use that executable's absolute path (`which context-bridge` shows it for tool installs; that environment uses `~/.context-bridge/bin/context-bridge`, written out in full):

```sh
claude mcp add --transport stdio context-bridge -- /absolute/path/to/context-bridge mcp
```

Claude Desktop and Cursor accept the equivalent entry:

```json
{
  "mcpServers": {
    "context-bridge": {
      "command": "/absolute/path/to/context-bridge",
      "args": ["mcp"]
    }
  }
}
```

Do not commit a user-specific executable path into a shared repository. Contributor installation is documented in [Install from source](INSTALL.md#install-from-source).

## Storage overrides and troubleshooting

If imports use `CONTEXT_BRIDGE_HOME`, give the MCP server the same absolute value in its configuration `env` object. Otherwise it reads the default library and may return no matches. For older local state, `mcp --config /absolute/path/to/enrollment.json` remains accepted; new libraries use `profile.json`.

A source/reader split is optional, not required. If a tool is missing, check the MCP client's connection rather than asking a model to invoke the server through a shell. Errors go to stderr; stdout contains protocol messages only.

These snippets follow [Claude Code's stdio setup](https://code.claude.com/docs/en/mcp) and the common MCP server configuration format. Client UI names can change. ChatGPT conversation exports are supported as sources; this build does not offer a remote ChatGPT connector.


## Listing and deletion

Use `context-bridge list`, `context-bridge stats`, or `context-bridge remove --conversation <id-or-provider-link>` locally. `remove --provider chatgpt`, `claude`, or `claude-code` removes that provider's imported sources. Web conversation removal is durable across exports: imports skip excluded IDs and report `conversations_excluded` separately from imports/removals. Per-profile exclusions contain only provider names and SHA-256 hashes, without titles or raw IDs. `context-bridge exclusions list --profile personal` lists them. To deliberately restore eligibility, run `context-bridge exclusions clear --conversation <id-or-provider-link> --profile personal`, then re-import with that profile. A provider link clears only that provider; a bare ID clears matching exclusions across ChatGPT and Claude. `remove --provider chatgpt` (or `claude`) preserves existing exclusions but adds no new ones; removing/re-importing a provider does not reset privacy choices. Snapshot pruning never creates exclusions. Code originals are not deleted, and removed Code sources are excluded from discovery until explicitly re-approved. A new complete web export replaces that provider's imported snapshot; absent conversations are withdrawn and their managed copies deleted. These controls take effect on the next MCP call, including in already-running clients with cached profile data.


## Choose a Claude Code project

Preview `context-bridge import claude-code`. Choose numbered entries interactively or use `--select 1,3 --yes`. You can use `--path /path/to/project --yes` for the original working directory, or `--project -Users-alice-code-app --yes` for the encoded directory name. No `--project=` workaround is required. Explicit `ai-title` records take precedence; fallback titles use the folder and the first redacted user-message excerpt. Encoded folder names are ambiguous for literal hyphens, so recorded `cwd` is preferred over best-effort decoding.

## Separate accounts

Use `import chatgpt export.zip --profile personal`, then append `["--profile", "personal"]` to the MCP arguments (uvx: `["--from", "context-bridge-local", "context-bridge", "mcp", "--profile", "personal"]`; virtual environment: `["mcp", "--profile", "personal"]`). `list`, `stats`, `remove`, `exclusions`, and `start` also accept the same profile name. The default profile retains the existing location; named profiles are stored separately beneath `profiles/NAME` within that base library. The same `CONTEXT_BRIDGE_HOME` and optional `--directory` must be used consistently.

Conflicting export account identifiers stop imports before database/copy/profile changes. Interactive users can confirm; automation must explicitly pass `--confirm-account-switch`. `--yes` alone does not authorize an account switch. When metadata is absent in both old and new exports, identity cannot be verified. Use separate profiles when uncertain.

## Conversation-level results

`context_search` applies `limit` to distinct conversations, returning the best-ranked passage for each. Conversations are identified by provider and conversation ID, not title, so separate “New chat” threads remain distinct. `more_matches_in_conversation` counts the other matching indexed messages in that conversation (the union of qualifying lexical and semantic matches in hybrid mode, without counting a record twice). It does not count text chunks or all unrelated messages. Use `context_read` with the returned record ID for surrounding turns. Readable `Source:` lines appear once per returned conversation.

Every search's `capture_status.retrieval_mode` identifies `bm25` or `hybrid`. `context-bridge stats` reports the same value at the top level and inside capture status.
