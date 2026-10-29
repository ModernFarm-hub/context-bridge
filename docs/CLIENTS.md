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

## Pin a version

To use this beta explicitly, replace `context-bridge-local` in the uvx arguments with `context-bridge-local==0.7.0b1`:

```sh
uvx --from 'context-bridge-local==0.7.0b1' context-bridge mcp
```

The package source is explicit because the PyPI name `context-bridge` belongs to a different project. [uv's package/command naming documentation](https://docs.astral.sh/uv/guides/tools/#commands-with-different-package-names).

## Alternative: installed command

If you installed with `uv tool install context-bridge-local`, `pipx install context-bridge-local`, the `~/.context-bridge` virtual environment from the README, or a contributor checkout, use that executable's absolute path (`which context-bridge` shows it for tool installs; the README's environment uses `~/.context-bridge/bin/context-bridge`, written out in full):

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

Do not commit a user-specific executable path into a shared repository. Contributor installation is documented in the README's “Install from source” section.

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
