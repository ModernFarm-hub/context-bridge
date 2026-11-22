# Install Context Bridge

The package is **context-bridge-local**; the command is **context-bridge**. The PyPI name `context-bridge` belongs to an unrelated project. Python 3.9–3.13, macOS and Linux are supported. Default search needs no third-party runtime packages.

## uvx: run without a permanent install

Install [uv](https://docs.astral.sh/uv/) if needed:

```sh
brew install uv
# or: curl -LsSf https://astral.sh/uv/install.sh | sh
uvx --from context-bridge-local context-bridge demo
```

The first uvx run downloads the package. The demo itself is offline and never downloads a model.

## Keep the command on your PATH

```sh
uv tool install context-bridge-local
uv tool update-shell
# Alternative: pipx install context-bridge-local && pipx ensurepath
```

Open a new terminal after updating PATH. If `context-bridge` is still not found, use uvx or the absolute executable path from `which context-bridge`.

## pip and virtual environments

Use a dedicated environment rather than a bare system pip install. macOS's bundled Python 3.9 has an older pip; upgrade pip before installing. Homebrew/python.org installations may reject a bare install as externally managed.

```sh
python3 -m venv ~/.context-bridge
~/.context-bridge/bin/python -m pip install -U pip
~/.context-bridge/bin/python -m pip install context-bridge-local
~/.context-bridge/bin/context-bridge demo
```

Desktop apps may not inherit shell PATH. Use the full executable path in their MCP configuration. See [client instructions](CLIENTS.md).

## Semantic search

```sh
uvx --from context-bridge-local context-bridge semantic enable
# If installed permanently: context-bridge semantic enable
```

Setup downloads approximately 90 MB of pinned, checksum-verified model files plus optional runtime packages. It upgrades pip in a private semantic runtime when needed, then backfills local embeddings. No chats are uploaded; subsequent search is offline. Restart your MCP client after changing modes.

For an unreleased/non-editable source install whose version is absent from PyPI:

```sh
context-bridge semantic enable --from-source /path/to/context-bridge
```

Use the same `--profile NAME` for setup, imports and MCP. [Profiles and privacy controls](USAGE.md).

## Install from source

Run in the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install .
.venv/bin/context-bridge demo
```

The source package remains in `prototype/` for this release. Tracked in [issue #1](https://github.com/ModernFarm-hub/context-bridge/issues/1). A future packaging cleanup must preserve the installed `context_bridge` import and CLI.

Pin the release with `uvx --from 'context-bridge-local==0.8.1' context-bridge mcp`. [Release process](RELEASING.md).
