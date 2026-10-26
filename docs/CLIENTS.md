# Connect your MCP client

Install this checkout in a virtual environment and import an export first. Use the absolute path to that environment's `context-bridge` executable. The server runs over stdio; it waits for an MCP client rather than a chat prompt.

## Claude Code

```sh
claude mcp add --transport stdio context-bridge -- /absolute/path/to/.venv/bin/context-bridge mcp
```

Run `/mcp` in Claude Code and check the connection. All sessions using that configuration can search the same approved local library.

## Claude Desktop

Open Claude Desktop's developer configuration and merge this entry into its `mcpServers` object, then restart/reconnect:

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

## Cursor

Use Cursor's MCP configuration (for example, project `.cursor/mcp.json`) with the same `mcpServers` entry above. Reconnect the server in Cursor's MCP settings. Do not commit a user-specific absolute executable path into a shared repository.

## uvx

Before publication, replace the package source with the absolute checkout path:

```sh
uvx --from /absolute/path/to/context-bridge context-bridge mcp
```

After publication, the corresponding config entry will use:

```json
{
  "mcpServers": {
    "context-bridge": {
      "command": "uvx",
      "args": ["--from", "context-bridge-local==0.6.0a2", "context-bridge", "mcp"]
    }
  }
}
```

The package source is explicit because the PyPI name `context-bridge` belongs to a different project. [uv's package/command naming documentation](https://docs.astral.sh/uv/guides/tools/#commands-with-different-package-names).

## Storage overrides and troubleshooting

If imports use `CONTEXT_BRIDGE_HOME`, give the MCP server the same absolute value in its configuration `env` object. Otherwise it reads the default library and may return no matches. For older local state, `mcp --config /absolute/path/to/enrollment.json` remains accepted; new libraries use `profile.json`.

A source/reader split is optional, not required. If a tool is missing, check the MCP client's connection rather than asking a model to invoke the server through a shell. Errors go to stderr; stdout contains protocol messages only.

These snippets follow [Claude Code's stdio setup](https://code.claude.com/docs/en/mcp) and the common MCP server configuration format. Client UI names can change. ChatGPT conversation exports are supported as sources; this build does not offer a remote ChatGPT connector.


## Listing and deletion

Use `context-bridge list`, `context-bridge stats`, or `context-bridge remove --conversation <id-or-provider-link>` locally. `remove --provider chatgpt`, `claude`, or `claude-code` removes that provider's imported sources. Code originals are not deleted, and removed Code sources are excluded from discovery until explicitly re-approved. A new complete web export replaces that provider's imported snapshot; absent conversations are withdrawn and their managed copies deleted. These controls take effect on the next MCP call, including in already-running clients with cached profile data.
