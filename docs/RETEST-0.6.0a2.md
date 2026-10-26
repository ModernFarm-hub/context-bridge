# Independent re-test fixes — 0.6.0a2

Local candidate; not published. Retrieval research remains frozen.

## Changes and regression coverage

| Request | Change | Regression coverage |
| --- | --- | --- |
| 1. Deleted conversations and removal | Complete provider snapshots prune absent conversations; report `conversations_removed`. `remove --conversation <id-or-link>` and `remove --provider <name>` remove records, FTS entries, state, handles, metadata, config entries and owned web-import copies. | `test_retest_fixes.py`: snapshot deletion for both providers, empty snapshots, ID/link/provider removal, provider-link isolation, live-reader invalidation. |
| 2. Redaction | Added Stripe, Google, JWT, URL-password, JSON/YAML credentials and explicit OpenAI project/service-account patterns. Policy version 2 upgrades index bodies, metadata and owned working copies; originals stay untouched. | `test_redaction_cases.py`: table-driven positives/negatives, idempotence, URL/JSON fidelity, migration. `test_retest_fixes.py`: copy/title upgrade. |
| 3. Refresh cost | Cache parsed profiles by file identity/mtime/ctime/size, canonical parent paths, metadata hashes and ingestion state. Skip unchanged metadata; batch mutations into one transaction. | Warm refresh performs no profile reread, path resolution or metadata write; changed metadata writes once; revocation invalidates caches even with preserved mtime; multiple appended files commit once. |
| 4. Import cost | One DB connection and transaction per export; one atomic profile write at the end; unchanged copies are not rewritten. Progress goes to stderr. | Connection/transaction/write counts, progress checkpoints and unchanged-file mtimes are checked. |
| 5. Management | Added `list`, `stats` and scoped removal. List includes provider, title, date and message count. | CLI output/count checks and installed-package smoke test. |
| 6. Code freshness | Explicit project approval covers future session files. Refresh discovers only inside those roots and respects removed paths/IDs. | New sessions in approved roots, nested initial files, unapproved project isolation, removal without rediscovery. |
| 7. Tool descriptions | Describe ChatGPT/Claude/Claude Code, `source_label`, `link`, `record_id`, and citing the link. | Description contract checked; official MCP client exercises real stdio. |
| 8. macOS pip | README upgrades pip before installing from source and explains bundled Python 3.9/pip 21.2. | README prerequisite order checked. |

A provider export is an authoritative snapshot, not a merge operation. Use separate profiles for separate account libraries. Unidentified malformed export objects suppress pruning and report `pruning_skipped`; known-but-malformed conversations preserve the previous copy. Removing Code data preserves original transcripts and withdraws discovery permission or excludes the selected conversation. An explicit later import may restore it.

## Complete test output

- [Python 3.9 full run: 136 passed, no skips](verification/0.6.0a2/full-tests.txt). Existing optional local models were enabled; no new research evaluation was run.
- [Python 3.12: 112 passed, 24 optional-model tests skipped](verification/0.6.0a2/python312-tests.txt).
- [Installed-wheel smoke output](verification/0.6.0a2/package-smoke.txt).
- [Official MCP client, persistent real stdio](verification/0.6.0a2/sdk-stdio.txt). Snapshot pruning and explicit removal take effect without restarting the reader. The logged `record_unavailable` error is expected when reading a removed handle.
- [Twine strict checks](verification/0.6.0a2/twine.txt).
- [Offline local-wheel uvx checks](verification/0.6.0a2/uvx.txt).

Remote CI and public publication remain pending. These are local checks.

## Benchmark output

[Full benchmark JSON](verification/0.6.0a2/benchmark-5000.json).

The benchmark uses actual synthetic provider-export import/re-import, 5,000 files, and 104,876 messages distributed 2–40 per file. Search timing includes per-file freshness checks, not just FTS lookup.

| Measurement | Result |
| --- | ---: |
| Initial export import | 12,789.67 ms |
| Unchanged export re-import | 2,955.84 ms |
| First server query | 230.71 ms |
| Search + refresh p50, 30 runs | 151.51 ms |
| Search + refresh p95 | 159.72 ms |
| Search + refresh maximum | 161.41 ms |
| Appended-message refresh + search | 41.68 ms |
| Appended message visible | true |
| p95 target | <300 ms — passed |

These results are specific to this machine and synthetic workload. Initial import and first query are reported separately from warmed-query percentiles.

## Verify from source

From the project root:

```sh
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
PYTHONPATH=prototype python3 prototype/benchmark.py --files 5000 --min-messages 2 --max-messages 40 --runs 30
```

The base suite skips optional model tests unless their dependencies and local model paths are configured. The full saved run enabled both existing model paths through `CONTEXT_BRIDGE_TEST_MODEL` and `CONTEXT_BRIDGE_TEST_SUPPORT_MODEL`, with offline mode enabled.

## Verify the built wheel in a fresh environment

```sh
python3 -m venv /tmp/context-bridge-0.6.0a2-verify
/tmp/context-bridge-0.6.0a2-verify/bin/python -m pip install -U pip
/tmp/context-bridge-0.6.0a2-verify/bin/python -m pip install releases/0.6.0a2/context_bridge_local-0.6.0a2-py3-none-any.whl
/tmp/context-bridge-0.6.0a2-verify/bin/python tools/package_smoke.py
/tmp/context-bridge-0.6.0a2-verify/bin/context-bridge --version
```

The smoke check uses temporary synthetic data and does not touch real conversations.

For a disposable manual library, set `CONTEXT_BRIDGE_HOME` to an absolute test directory before both imports and MCP:

```sh
export CONTEXT_BRIDGE_HOME=/tmp/context-bridge-manual-0.6.0a2
/tmp/context-bridge-0.6.0a2-verify/bin/context-bridge import chatgpt /path/to/synthetic-export.zip
/tmp/context-bridge-0.6.0a2-verify/bin/context-bridge list
/tmp/context-bridge-0.6.0a2-verify/bin/context-bridge stats
/tmp/context-bridge-0.6.0a2-verify/bin/context-bridge remove --conversation CONVERSATION_ID
/tmp/context-bridge-0.6.0a2-verify/bin/context-bridge remove --provider chatgpt
```

Re-import a newer complete synthetic export to check removal counts. Use `import claude-code --projects-root /absolute/path/to/synthetic/projects --yes` for approved-directory discovery, create another JSONL session in an approved directory, and search again. Reconnect an MCP client after installing the new wheel so its tool descriptions refresh.
