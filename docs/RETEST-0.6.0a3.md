# 0.6.0a3 — selection, credential precision and account safety

## Changes

- Real dash-prefixed Claude Code directory names work with `--project -Users-alice-code-app`, without an equals sign. Numbered `--select 1,3`, original `--path /path/to/project` and an interactive numbered picker are also available.
- JSON/YAML redaction uses credential names rather than arbitrary `*_key` names. Primary/foreign/sort/partition/unique/idempotency/cache keys and identifier-valued key IDs remain intact. Recognized secret token formats are still filtered regardless of the containing field.
- Slack incoming webhooks and Discord/legacy/versioned webhook URLs are redacted. Policy version 3 reprocesses stored bodies/copies for this security change. Previously erased schema text requires re-importing an original export; unchanged original Code transcripts can be reprocessed.
- Fallback Code titles use the recorded working-directory folder and the first 60 characters of the first real user message, redacted before truncation. Tool-result content is excluded and explicit `ai-title` wins. Encoded paths are ambiguous for hyphens, so recorded `cwd` takes priority.
- Available account/user identifiers from export metadata are compared before mutations. A different or unverifiable account requires interactive confirmation or `--confirm-account-switch`; `--yes` does not bypass this guard. Stored comparison values are hashes. If both exports lack metadata, account continuity cannot be detected.
- `--profile NAME` gives import, MCP, list/stats/remove and the optional manager a separate local library. Example: import with `--profile personal`, then configure MCP with `["mcp", "--profile", "personal"]`.

## Local verification

[Full run](verification/0.6.0a3/full-tests.txt): 146 tests passed with existing optional local models enabled, no skips. [Installed-wheel smoke](verification/0.6.0a3/package-smoke.txt) exercises the actual console executable, all three project selector forms, schema text, account blocking and profile isolation. Additional table-driven credential cases and interactive cancellation/selection regressions are included. Retrieval research remains frozen.

```sh
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -p 'test_project_account_fixes.py' -v
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -p 'test_redaction_cases.py' -v
```

Without optional models/dependencies, the base suite skips those inference tests. To check the installed artifact, create a fresh virtual environment, upgrade pip, install `releases/0.6.0a3/context_bridge_local-0.6.0a3-py3-none-any.whl`, and run `tools/package_smoke.py` with that environment's Python. Release binaries and local state are ignored and not committed.

## Git and CI

The prior 0.6.0a2 changes were recorded separately as fixes, tests, docs and verification commits. This update is likewise split into focused commits. The configured workflow tests macOS and Linux across Python 3.9–3.13 and runs an additional official SDK-client job. The final response links the actual pushed commit and CI run; a configured workflow alone is not treated as a passed run.
