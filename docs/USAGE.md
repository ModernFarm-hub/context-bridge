# Using Context Bridge

[Quickstart](../README.md) · [Installation](INSTALL.md) · [Client setup](CLIENTS.md)

## Existing Claude Code conversations

Preview the projects available on this machine:

```sh
uvx --from context-bridge-local context-bridge import claude-code
```

Approve the displayed list at the prompt, or select one project explicitly:

```sh
uvx --from context-bridge-local context-bridge import claude-code --select 1,3 --yes
uvx --from context-bridge-local context-bridge import claude-code --path /path/to/project --yes
```

The preview numbers projects; an interactive terminal lets you choose numbers before approving. Raw dash-prefixed names also work with `--project -Users-alice-code-app` without an equals sign. The prompt approves the selected project directories, including future session files. New sessions are discovered during search refresh; other projects remain excluded. Existing 0.6.0a1 file-only imports need this project approval again to enable discovery. Session titles come from Claude Code's `ai-title` records when available. The optional `context-bridge start` manager creates and approves live Claude Code sessions; those sessions refresh automatically when searched.

## Sources

| Source | Capture | Approval |
| --- | --- | --- |
| ChatGPT web | Official export ZIP | Explicit import; re-import to refresh |
| Claude.ai | Official export ZIP | Explicit import; re-import to refresh |
| Claude Code | Automatic local transcript discovery | Selected project directories only |
| ChatGPT desktop / Codex | Automatic, no export | Selected project folders only |

### ChatGPT desktop / Codex capture

```sh
context-bridge import codex
context-bridge import codex --select 1,3 --yes --profile personal
# Or select one original working directory:
context-bridge import codex --path /path/to/project --yes --profile personal
```

The first command previews threads grouped by project without importing anything. Approval includes future threads in those project folders; search refresh discovers them automatically. It reads rollout files under `~/.codex/sessions`, honoring `CODEX_HOME` (or `--codex-home /path/to/state`). Original files are never modified. Discovery stops at the thread/project headers and caches rejected or unclassifiable files by file signature; unchanged unapproved rollouts are not re-read on each search. Title excerpts are read only for approved projects. Only user and assistant text is indexed; tools, reasoning, developer/system messages, events and known injected context envelopes are excluded. Titles use `session_index.jsonl`, with a redacted first-user-message fallback. Citations use `codex://threads/<thread-id>` to open the desktop thread. [Capture and consent details](CLIENTS.md#chatgpt-desktop--codex-as-a-source).

## Paraphrases and optional offline semantic search

The default needs no third-party dependencies: SQLite FTS5 with Porter stemming and weighted conversation titles. `matched_terms` shows the query terms that matched. Results use one slot per conversation, with the best passage and `more_matches_in_conversation` counting other matching indexed messages. `capture_status.retrieval_mode` and `context-bridge stats` report `bm25` or `hybrid`. It cannot reliably connect unrelated wording; try two or three phrasings, or opt into local hybrid search:

```sh
context-bridge semantic enable --profile personal
```

For a source install or an unreleased version absent from PyPI, run `context-bridge semantic enable --from-source /path/to/context-bridge --profile personal` using the checkout containing `pyproject.toml`.

This explicitly installs the optional `[semantic]` dependencies if needed in a private runtime (upgrading its pip first), downloads checksum-verified MiniLM model files, and backfills embeddings for approved records. Setup reports model bytes, embedding count and elapsed time. Package/model downloads use the network; no conversation text is sent. Later searches combine BM25 and local vectors fully offline. Embeddings persist in the profile's local database, respect removal, and update as content changes. Restart your MCP client after enabling so it uses the selected runtime. Return to the dependency-free mode with `context-bridge semantic disable --profile personal` (this does not erase downloaded model files).

On the frozen 30-conversation synthetic paraphrase fixture:

| Mode | Top-1 | Top-5 | MRR@20 |
| --- | ---: | ---: | ---: |
| 0.7.0b2 baseline | 3.3% | 3.3% | 0.0333 |
| 0.8 BM25 + stemming/title | 3.3% | 6.7% | 0.0444 |
| 0.8 hybrid MiniLM | 86.7% | 90.0% | 0.8833 |

These are synthetic conversation-level retrieval measurements, not a real-library accuracy claim. Semantic mode remains opt-in: its recall gains come with an approximately 90 MB model plus optional runtime packages. No built-in synonym list was added. [Reproduce the benchmark and inspect all per-query ranks](verification/0.8.0b1/README.md).

## Keep accounts separate

Export metadata (`user.json`, account IDs or user IDs when present) is compared before any imported data is changed. A different or unverifiable account stops a noninteractive import; in a terminal you can explicitly confirm replacement. `--yes` does not bypass this check. Prefer a separate named profile:

```sh
uvx --from context-bridge-local context-bridge import chatgpt /path/to/export.zip --profile personal
uvx --from context-bridge-local context-bridge list --profile personal
uvx --from context-bridge-local context-bridge mcp --profile personal
```

Use the same `--profile` on import, MCP, list/stats/remove and the optional manager. Named profiles have separate files/databases under the base library's `profiles/NAME` directory. Only hashed account identifiers are stored. If both exports omit all account identifiers, account changes cannot be detected. Existing unidentified sources require explicit confirmation before adopting an identified account. To deliberately replace a provider's account snapshot, use `--confirm-account-switch`; absent conversations will be removed.

## Manage your library

```sh
uvx --from context-bridge-local context-bridge list
uvx --from context-bridge-local context-bridge stats
uvx --from context-bridge-local context-bridge remove --conversation 'https://chatgpt.com/c/CONVERSATION_ID'
uvx --from context-bridge-local context-bridge remove --conversation CONVERSATION_ID
uvx --from context-bridge-local context-bridge remove --provider chatgpt
uvx --from context-bridge-local context-bridge exclusions list --profile personal
uvx --from context-bridge-local context-bridge exclusions clear --conversation 'https://chatgpt.com/c/CONVERSATION_ID' --profile personal
```

Provider names are `chatgpt`, `claude`, `claude-code`, and `codex`. List returns provider, title, creation date and indexed message count. Removal deletes index rows, FTS data, ingestion state, citation handles, metadata/config entries, and owned web-import copies. Original export ZIPs, Claude Code transcripts and Codex rollout files stay untouched. Removing a Claude Code provider also withdraws project-directory approval; removing one Code conversation prevents its automatic rediscovery. Removing a web conversation creates a durable exclusion in that profile: future ChatGPT/Claude imports skip it. Exclusions store only a provider and a SHA-256 digest of the provider/conversation ID, without titles or plaintext conversation IDs. `exclusions list` shows those hashes; use the original ID or provider link with `exclusions clear --conversation` to restore eligibility, then re-import. A link selects one provider; clearing a bare ID clears matching exclusions across web providers and Codex. Use the same `--profile` consistently. Removing a whole provider preserves existing conversation exclusions but does not create exclusions for every remaining chat; a later export can restore those remaining chats. Only explicit `exclusions clear` clears the saved web exclusions.

Codex removal uses the same hashed exclusions: `remove --conversation codex://threads/THREAD_ID`, then optionally `exclusions clear --conversation codex://threads/THREAD_ID` to allow discovery again. `remove --provider codex` withdraws all Codex project approvals and excludes the currently imported threads; clearing a thread exclusion alone does not re-approve its project.

Large export imports show progress on stderr and report `conversations_removed` and `conversations_excluded`. Excluded IDs are counted as skips, never imports or snapshot removals. Snapshot pruning does not create exclusions; absent chats can return in a later export. If an export contains objects without identifiable conversation IDs, pruning is skipped and reported as `pruning_skipped`; malformed entries with known IDs preserve their prior copy rather than masquerading as deletions.

## What you get

| Tool | Result |
| --- | --- |
| `context_search` | Relevant redacted passages with title, provider, date, conversation link and opaque record ID |
| `context_read` | Surrounding indexed turns (context=2 by default, maximum 10 each side), with pagination and changed-window checks |

ChatGPT imports follow the active message-tree branch. Claude.ai imports human/assistant text. Tools, thinking blocks and internal replayed API requests are excluded. Re-importing a new export updates the conversation without duplicate messages. Each provider export is an authoritative snapshot: re-importing it removes conversations absent from that export, including their index and managed copies. Do not use a partial export to merge accounts. Export imports do not capture new browser chats automatically.

Web citations open `chatgpt.com/c/<id>` or `claude.ai/chat/<uuid>` and require your normal provider access. Claude Code citations use `urn:context-bridge:record:<id>` handles resolved by `context_read`. They are not browser URLs. The MCP interface does not expose local filesystem locators. [Passage behavior](PASSAGE-READING.md).

Search retrieves recorded statements; it does not establish that those statements are true. Explicit recency words influence ranking, but arbitrary date-range filtering is not implemented.

## Local-first privacy

- No Context Bridge account, hosted storage, analytics or usage telemetry.
- Indexing and default SQLite FTS5/BM25 search run locally, with no required runtime dependencies or cloud embedding calls.
- Recognized credentials, Slack/Discord webhook URLs and URL passwords are redacted before indexing and again on MCP output. JSON/YAML schema keys such as `primary_key`, `sort_key` and `cache_key` are preserved. Pattern matching cannot detect every arbitrary secret.
- Only explicitly imported or approved conversations are available. Original export ZIPs and Claude Code transcripts are not modified.
- Selected results are sent to your MCP client. If that client uses a cloud model, the provider receives those passages under your account settings.
- The database is plaintext. Local filesystem access can expose its content. Revocation prevents new retrieval; it cannot recall prior model responses.

Default macOS storage is `~/Library/Application Support/ContextBridge`; Linux uses `$XDG_DATA_HOME/context-bridge` or `~/.local/share/context-bridge`. Run `context-bridge paths`, or set the same absolute `CONTEXT_BRIDGE_HOME` for imports and MCP. [Security policy and boundaries](../SECURITY.md).

## Test it

```sh
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
PYTHONPATH=prototype python3 prototype/benchmark.py --files 5000 --min-messages 2 --max-messages 40 --runs 30
```

The tests and benchmark use invented conversations. Model-dependent tests skip without optional local assets. The benchmark uses 5,000 conversation files with 2–40 messages each, imports/re-imports an actual synthetic provider export, and measures search including per-file freshness checks. Its p95 target is 300 ms. Import, re-import and first-server-query times are reported separately; results depend on hardware and workload. [Independent 0.6.0a2 re-test results](RETEST-0.6.0a2.md). [Verification details](MILESTONES.md).


## First import and embeddings

After the first successful import in an interactive terminal, Context Bridge offers semantic search once per profile. The default is no, and a decline is remembered. Scripts, pipes and CI never prompt or automatically download a model. Enable it later with `context-bridge semantic enable`.

If hybrid search is already enabled, imports build local embeddings before returning, with progress on stderr. Noninteractive import JSON stays on stdout. A failed embedding step leaves the imported conversations saved and reports how to repair the runtime; retry the import after repair. Newly discovered live sessions still refresh on search.

## Local usage and savings estimates

Search/read accounting stays in the selected profile database. Each call records UTC machine time, client-reported name, opaque IDs, response characters and `ceil(characters/4)` estimated tokens. It stores no response bodies, snippets, titles or query text by default. Original-cost snapshots contain numeric counters and opaque identifiers; titles/links are resolved locally when reporting. The machine clock and client name are not an authentication or audit guarantee. Explicit CLI output can of course be shared if you ask an AI client to read it.

```sh
context-bridge usage --json --profile personal
context-bridge savings --explain --profile personal
context-bridge savings --json --profile personal
context-bridge savings --price-per-million 1.00 --profile personal
context-bridge usage clear --profile personal
context-bridge usage configure --disable --profile personal
context-bridge usage configure --enable --profile personal
# Explicit opt-in to redacted query text; undo with --no-query-text:
context-bridge usage configure --store-queries --profile personal
context-bridge usage configure --no-query-text --profile personal
```

Equivalent profile config: `"usage": {"enabled": false, "store_queries": false}`. Disabling affects future calls; clear deletes that profile's call history, including query text and saved cost snapshots, but does not delete imported sources or their numeric ingestion metadata. Other profiles are untouched. Recognized secrets are redacted in opt-in queries; pattern matching cannot find every arbitrary secret.

Every savings number is an estimate. Conservative lower-bound credit is cumulative assistant output plus nonnegative context growth above the first assistant turn. Claude Code context includes input, cache creation and cache reads; Codex context is per-turn input, already including cached input. All-in counts appear only as upper bounds including fixed context overhead. Reads are a proxy for possible reuse, not evidence that an answer was used or correct. Each conversation gets one hypothetical redo credit through the latest message actually returned in a read page. Repeated reads/pages do not repeatedly earn credit. All response overhead is deducted, including misses and searches with no read. Shared search cost is assigned once to the first later read of a returned ID; unmatched costs reduce the total. Prices are absent unless you supply a uniform USD-per-million-token price; this is not a provider invoice or cache-specific tariff. Historical wall time is not estimated. [Full method and limits](benchmarks/savings.md).

## Automatic consultation

```sh
context-bridge agent-guide
context-bridge claude-code hook --print --profile personal
context-bridge claude-code hook --install --profile personal
context-bridge claude-code hook --uninstall --profile personal
```

Review the agent-guide block before adding it to CLAUDE.md or AGENTS.md. Printing does not edit those files. The optional hook's install/uninstall shows a settings diff and asks for confirmation. Existing settings are preserved and a unique `.bak` file is created before each change. Default settings are `~/.claude/settings.json`; use `--settings /path/to/settings.json` to target a different file. Backups remain local and can contain your original settings.

On UserPromptSubmit the hook searches only the approved profile, using compact local BM25 results even when normal MCP is hybrid. This avoids cold model loading under a 200 ms worker deadline. It considers at most three results with score at least `0.00001` and at least 40% lexical-term coverage. This is a heuristic: it can miss relevant paraphrases or surface irrelevant matches. Normal MCP calls retain their configured retrieval mode. The host hook timeout is 250 ms; wall time is not a hard real-time guarantee under OS load. No result, error or timeout injects nothing and does not block your prompt.

Injected content is capped at 1,200 characters and a conservative 400 UTF-8-byte token ceiling (typically much less than 400 model tokens). This is a content budget, not an exact Anthropic token count; host framing is excluded. The actual character estimate and benchmark overhead are reported separately. A lexical hook cannot replace careful research or freshness checks. Retrieved passages remain untrusted and instructions within them must not be followed.

Install and uninstall require an interactive terminal for confirmation; noninteractive calls refuse without changing settings. Use `--print` to inspect the configuration.

Installing enables automatic sharing of selected approved passages with your Claude Code client on prompts. Choose the profile intentionally. Context Bridge makes no network calls in the hook and never transmits the usage log, but your AI client may send injected passages to its model provider. Nothing is installed by default. Reinstall the hook if you move the checkout, remove its Python environment, or clear the uvx runtime cache that its absolute command references. Start/restart Claude Code so settings changes take effect.

## Repeat-research opportunity (local, no API calls)

```sh
context-bridge repeats --profile personal
context-bridge repeats --profile personal --json
context-bridge repeats --profile personal --min-similarity 0.90
context-bridge repeats --profile personal --review
```

This reports **opportunity for reuse, not proof of savings**. It reads only imported/approved indexed conversations in the selected profile; it neither imports other chats nor contacts a model API. Existing local hybrid mode is used when enabled, without downloading models. Otherwise it uses BM25/Porter over opening questions with a stricter overlap threshold. Hybrid's existing private Python runtime is honored. A missing local runtime/model produces an error rather than a download.

The denominator is conversations with indexed records. Each conversation contributes its first two indexed user turns (up to 1,000 characters each); these are opening-turn proxies, not guaranteed questions. Only strictly earlier dated conversations can match: creation time is preferred, otherwise the first available message timestamp. Unknown dates and equal timestamps cannot establish ordering and do not count as repeats. The report shows unknown-date counts. Different providers can match; a conversation cannot match itself. Each repeat gets its best earlier match, breaking score ties toward the most recent earlier conversation. Connected chains are grouped into repeated topics. Topic labels are conversation titles only; ten highest-scoring sample pairs (or fewer if unavailable) show titles and dates only, never questions, answers, snippets, IDs or local paths.

BM25 selects at most 100 earlier candidate conversations using opening text only. Its score threshold is content-token Jaccard overlap (default 0.85) with at least three shared terms; raw BM25 scores are not calibrated similarity. Hybrid scores all earlier opening-question vectors using 85% local cosine similarity plus 15% token overlap (default 0.78). `--min-similarity` overrides the mode's threshold in [0,1]; lowering it increases false-positive risk. Scores are heuristics, not probabilities and not comparable between modes. A negation-mismatch veto rejects obvious opposite intents, but cannot reliably understand intent or entity differences. Short questions, paraphrases in lexical mode, truncated opening turns and questions occurring later in a chat can be missed. Similar questions can be legitimate follow-ups, routine recurring work, changed requirements or unrelated lookalikes.

The report includes conversation and repeat counts/rates, per-provider totals, and the estimated research cost of each repeated conversation counted once through its final indexed message. Claude Code/Codex use the same conservative lower-bound output-plus-context-growth rule as `savings`; exports and transcripts without usage counters use lower-quality visible-text estimates. Cost methods are broken out by provider. This is **research cost attached to possible repeats**, not avoidable tokens, a bill, actual reuse, or net savings. No dollar conversion or hypothetical lookup deduction is made. The report also shows the share with any time-sensitive hint or high-stakes term in indexed turns. This intentionally broad **likely-REDO proxy** can include cases the actual policy would CHECK; it is not a decision verdict and prevents presenting every match as safely reusable.

`--review` is the recommended way to choose a threshold and requires an interactive terminal. It offers up to ten title/date-only pairs down to 0.4 (or your lower selected threshold), even if the default finds zero. When there are more than ten, it covers score bands before filling the sample; this is still selection-biased. Enter y (real repeat), n (not a repeat), or s (skip). Labels persist locally in the profile database as hashed provider/conversation pairs, a yes/no value and review time: no titles or message text are copied into the label table. EOF ends review cleanly, retaining prior labels. Precision is confirmed repeats divided by labelled pairs still present in the current report; unreviewed pairs are not counted. These top-score, user-selected labels are selection-biased and do not measure recall or population precision. Labels do not change the algorithmic repeat rate. Profiles remain isolated; removed sources no longer appear, while historical hashed labels contain no recoverable conversation text.

Everything stays local unless you deliberately save/share output (for example redirecting `--json`). Titles can themselves be sensitive. Similarity vectors are computed locally in memory; large hybrid reports compare all earlier pairs and can take substantially longer than ordinary search. No performance or accuracy guarantee is claimed for large libraries. Report thresholds and review precision before interpreting a repeat rate.

Existing folders can be approved before they have their first thread:

```sh
context-bridge import codex --path /path/to/existing-project --yes
context-bridge import claude-code --path /path/to/existing-project --yes
```

`--yes` confirms approval for future sessions in that folder. Without it, the CLI asks interactively or leaves the preview unchanged. A new approval requires an existing project folder; previously captured projects can still be selected after their original folder moves. Claude Code's future transcript directory is inferred from its standard encoded project-folder name.

For the isolated public-document savings experiment, see [the benchmark guide](benchmarks/savings-real-guide.md). Its fake-provider mode makes no API calls and uses a disposable library.

Every report also shows a sensitivity table at 0.4, 0.5, 0.6 and 0.7, plus the selected threshold. Each row includes repeats/rate, reviewed count, labelled precision, and review coverage. An unreviewed row has null precision, never zero or assumed perfect precision. Matching is computed once; all rows use the same best strictly earlier match for each conversation. Rates can change substantially across thresholds. Zero at the default does not show that no research was repeated.

Thresholds are **library-dependent**. Defaults remain hybrid 0.78 and lexical 0.85: conservative starting points checked against synthetic exact-positive chains and a negated lookalike, not empirically calibrated probabilities or optimized thresholds for real libraries. Keeping a high starting cutoff favors precision in those fixtures and can miss real paraphrases. The sensitivity tests also include controlled synthetic scores crossing the lower cutoffs; they verify reporting and label accounting, not a real embedding model's precision. No default was tuned to a particular user's data. Start with `context-bridge repeats --review`, inspect precision and coverage across thresholds, and select an appropriate `--min-similarity`. Re-review as your library changes. A handful of hand-picked labels is not population precision or recall; follow-up questions can legitimately resemble earlier research.
