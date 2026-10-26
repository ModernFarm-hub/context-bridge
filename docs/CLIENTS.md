# Connect your MCP client

Import an export using `uvx --from context-bridge-local context-bridge import chatgpt /path/to/export.zip` or the installed `context-bridge` command. The server runs over stdio; it waits for an MCP client rather than a chat prompt.

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
      "command": "uvx",
      "args": ["--from", "context-bridge-local", "context-bridge", "mcp"]
    }
  }
}
```

## Cursor

Use Cursor's MCP configuration (for example, project `.cursor/mcp.json`) with the same `mcpServers` entry above. Reconnect the server in Cursor's MCP settings.

## Pin a version

To use this beta explicitly, replace `context-bridge-local` in the uvx arguments with `context-bridge-local==0.7.0b1`:

```sh
uvx --from 'context-bridge-local==0.7.0b1' context-bridge mcp
```

The package source is explicit because the PyPI name `context-bridge` belongs to a different project. [uv's package/command naming documentation](https://docs.astral.sh/uv/guides/tools/#commands-with-different-package-names).

## Alternative: installed virtual environment

If you prefer an existing pip installation or a contributor checkout, use its absolute executable path:

```sh
claude mcp add --transport stdio context-bridge -- /absolute/path/to/.venv/bin/context-bridge mcp
```

Claude Desktop and Cursor accept the equivalent entry:

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

Do not commit a user-specific executable path into a shared repository. Contributor installation is documented in the README's “Install from source” section.

## Storage overrides and troubleshooting

If imports use `CONTEXT_BRIDGE_HOME`, give the MCP server the same absolute value in its configuration `env` object. Otherwise it reads the default library and may return no matches. For older local state, `mcp --config /absolute/path/to/enrollment.json` remains accepted; new libraries use `profile.json`.

A source/reader split is optional, not required. If a tool is missing, check the MCP client's connection rather than asking a model to invoke the server through a shell. Errors go to stderr; stdout contains protocol messages only.

These snippets follow [Claude Code's stdio setup](https://code.claude.com/docs/en/mcp) and the common MCP server configuration format. Client UI names can change. ChatGPT conversation exports are supported as sources; this build does not offer a remote ChatGPT connector.


## Listing and deletion

Use `context-bridge list`, `context-bridge stats`, or `context-bridge remove --conversation <id-or-provider-link>` locally. `remove --provider chatgpt`, `claude`, or `claude-code` removes that provider's imported sources. Code originals are not deleted, and removed Code sources are excluded from discovery until explicitly re-approved. A new complete web export replaces that provider's imported snapshot; absent conversations are withdrawn and their managed copies deleted. These controls take effect on the next MCP call, including in already-running clients with cached profile data.


## Choose a Claude Code project

Preview `context-bridge import claude-code`. Choose numbered entries interactively or use `--select 1,3 --yes`. You can use `--path /path/to/project --yes` for the original working directory, or `--project -Users-alice-code-app --yes` for the encoded directory name. No `--project=` workaround is required. Explicit `ai-title` records take precedence; fallback titles use the folder and the first redacted user-message excerpt. Encoded folder names are ambiguous for literal hyphens, so recorded `cwd` is preferred over best-effort decoding.

## Separate accounts

Use `import chatgpt export.zip --profile personal`, then append `["--profile", "personal"]` to the MCP arguments (uvx: `["--from", "context-bridge-local", "context-bridge", "mcp", "--profile", "personal"]`; virtual environment: `["mcp", "--profile", "personal"]`). `list`, `stats`, `remove`, and `start` also accept the same profile name. The default profile retains the existing location; named profiles are stored separately beneath `profiles/NAME` within that base library. The same `CONTEXT_BRIDGE_HOME` and optional `--directory` must be used consistently.

Conflicting export account identifiers stop imports before database/copy/profile changes. Interactive users can confirm; automation must explicitly pass `--confirm-account-switch`. `--yes` alone does not authorize an account switch. When metadata is absent in both old and new exports, identity cannot be verified. Use separate profiles when uncertain.
