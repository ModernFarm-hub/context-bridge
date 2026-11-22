# 0.8.1 first-impression verification

Local macOS verification: **186 tests passed** with both local model suites enabled. The dependency-free run passes with 29 optional model tests skipped. Version metadata remains 0.8.1 across packaging, runtime and registry files. No tag, push, package upload or release publication was performed.

The demo creates ten disposable conversations across ChatGPT, Claude and Claude Code, searches three questions including a paraphrase, prints synthetic citations and the exact Claude Code MCP command, and removes its temporary directory. Regression tests block network calls and protect a sentinel user-library file. The installed-wheel/uvx tests also verify cleanup.

Interactive import offers semantic search once per profile; decline/accept decisions are remembered. Empty imports and noninteractive imports do not prompt. Hybrid imports from all four providers warm persistent embeddings before returning. Tests verify that first search needs only query inference, including a CLI import launched through a separate configured runtime. Progress goes to stderr; automated import stdout stays JSON.

The CI uvx smoke script reads the quickstart from wheel metadata rather than maintaining an unrelated example. It executes the literal demo and Claude Code preview commands offline against a wheel and synthetic HOME. Because Claude Code is not installed in CI, registration argv is checked using a stub; actual MCP startup is tested separately. The installed-package smoke and official MCP v1 client tests verify real stdio search/read, snapshot removal and privacy boundaries. CI configuration was updated; GitHub Actions was not triggered because this work was not pushed.

The historical research modules remain for tests/reproducibility, but their commands are no longer in public CLI dispatch. The source package remains in prototype/; [issue #1](https://github.com/ModernFarm-hub/context-bridge/issues/1) tracks a later layout migration.

Reproduce from the checkout:

```sh
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
python3 -m build --outdir /tmp/context-bridge-081-dist
python3 tools/check_artifacts.py /tmp/context-bridge-081-dist
python3 tools/uvx_smoke.py /tmp/context-bridge-081-dist
```

Optional model tests use `CONTEXT_BRIDGE_TEST_MODEL` and `CONTEXT_BRIDGE_TEST_SUPPORT_MODEL` pointing to existing verified local models. They never download models during tests.
