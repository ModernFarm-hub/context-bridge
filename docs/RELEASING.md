# Release preparation and publication

Current candidate: **0.6.0a3**, distribution **context-bridge-local**, executables **context-bridge** and **context-bridge-local**. The GitHub repository is ModernFarm-hub/context-bridge. PyPI ownership/authentication and MCP registry publication remain pending. No public upload is performed by the preparation scripts.

The PyPI name `context-bridge` is already used by another project. Use the explicit package source with uvx, or the package-matching alias `uvx context-bridge-local@0.6.0a3 mcp` once published. Do not claim that `uvx context-bridge` installs this server.

## 1. Verify locally

From the project root:

```sh
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
PYTHONPATH=prototype python3 prototype/benchmark.py --messages 100000 --runs 30
python3 -m venv .build-venv
.build-venv/bin/python -m pip install build twine uv
.build-venv/bin/python -m build
.build-venv/bin/python -m twine check --strict dist/*
.build-venv/bin/python tools/check_artifacts.py dist
.build-venv/bin/python tools/uvx_smoke.py dist
```

Install the wheel into a separate environment and run from outside the checkout:

```sh
python3 -m venv /tmp/context-bridge-release-check
/tmp/context-bridge-release-check/bin/python -m pip install dist/context_bridge_local-0.6.0a3-py3-none-any.whl
/tmp/context-bridge-release-check/bin/python tools/package_smoke.py
```

The smoke script uses temporary invented data and checks import, profile creation, stdio negotiation, opaque citations, redaction and passage reads. The payload checker rejects local state, generated reports and personal workspace paths. It is not a full license or secret audit.

For the optional official SDK-client check, use a separate Python 3.10+ environment:

```sh
python3.12 -m venv /tmp/context-bridge-sdk-check
/tmp/context-bridge-sdk-check/bin/python -m pip install . 'mcp>=1.12,<2'
/tmp/context-bridge-sdk-check/bin/python tools/sdk_smoke.py
```

CI configures the base suite/build/smoke on macOS and Linux across Python 3.9–3.13, plus a separate official SDK-client job. Workflow configuration alone is not evidence of a completed remote run.

## 2. Fill the real publication identity

Choose the real owner/repository and confirm permission to create/publish there. This command only updates local metadata:

```sh
python3 tools/prepare_registry.py ACTUAL_GITHUB_OWNER/ACTUAL_REPOSITORY
```

It generates `server.json`, adds the PyPI `mcp-name` ownership marker to the README, gives the demo GIF an absolute repository URL, and fills project URLs. Review the result. The generated namespace is `io.github.<owner>/context-bridge`; GitHub registry login must control that owner namespace. The default demo URL assumes a `main` branch; adjust it if the repository uses another default branch.

Rebuild and recheck artifacts after metadata changes. Keep repository privacy, enabled private vulnerability reporting, and package ownership explicit. Do not publish the whole surrounding workspace. Internal research notes, state, old release archives and evaluation output are ignored/pruned; curated historical research docs remain in the repository's `research/` section, outside distribution archives.

## 3. Publish the package

Use the chosen PyPI account or configure PyPI Trusted Publishing for the chosen repository/workflow. Authentication belongs in the publishing tool's secure flow; do not paste API tokens into chat, source, logs, or a command argument. Once authenticated, publish the verified artifacts:

```sh
python3 -m twine upload dist/*
```

The package name's availability/ownership must be checked under the chosen account; preparation does not reserve it. PyPI version uploads are immutable. Verify the published package page and install the exact version into a clean environment before claiming distribution works:

```sh
uvx --from 'context-bridge-local==0.6.0a3' context-bridge --version
uvx --from 'context-bridge-local==0.6.0a3' context-bridge mcp
```

## 4. Publish MCP registry metadata

The official registry stores metadata; the package must already be published. PyPI verification checks that its README description contains `mcp-name: <exact server name>`. The generated metadata uses the package-matching `context-bridge-local` console alias, with `mcp` as its package argument.

Install the official `mcp-publisher` CLI using its documented platform instructions, then:

```sh
mcp-publisher login github
mcp-publisher publish
```

Complete the device authorization yourself. Verify the server/version through the official registry API and test the advertised package command. Do not describe a generated template or successful login as a successful registry publication.

References: [official registry quickstart](https://modelcontextprotocol.io/registry/quickstart), [PyPI package verification](https://modelcontextprotocol.io/registry/package-types), [uv package/command names](https://docs.astral.sh/uv/guides/tools/#commands-with-different-package-names).

## Demo and historical material

`tools/make_demo.py` creates the README GIF from actual synthetic import/search/read output. It needs Pillow only for rendering; the product runtime does not. Do not substitute private conversation recordings. `research/` is historical and frozen; no new retrieval study is part of this release process.
