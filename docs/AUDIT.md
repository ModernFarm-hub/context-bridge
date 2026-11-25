# Experimental local audit (0.12.0a3)

`audit` compares the raw coding-agent records you already approved with actual changes in your local git history, then flags notable recorded actions and missing recorded controls. **Self-run local audit; heuristics; not proof.** This is a developer's local check, not monitoring of other people. No accuracy, authorship, security-assurance or explanation-quality result is claimed.

Records written at commit time can be incomplete, skipped or edited. Checking git changes separately from the record can expose discrepancies, including history from before installation if approved transcripts still exist. Raw transcripts are also incomplete and editable: this check cannot prove who acted, that a tool really executed successfully, or that an absent record means no action occurred.

```sh
context-bridge audit --repo /path/to/repo --since 30d --profile personal
context-bridge audit --repo /path/to/repo --range main~10..main --profile personal --json
context-bridge audit --repo /path/to/repo --since 30d --markdown
context-bridge audit --repo /path/to/repo --since 30d --fail-on high
```

The command is CLI only; there is no audit MCP tool. It uses the existing trace action parser, matcher, approved Claude Code/Codex sources, repository scoping, sensitive terms and append-only snapshot policy. It reads no new data source, makes no network/model request, never executes recorded commands and writes nothing to the repository. Partial/promisor clones are refused to prevent lazy fetching. Select an existing profile with `--profile` / `--directory`; no import, discovery, embeddings or search-index refresh occurs.

`--since` defaults to 30d, using git date syntax (including durations such as 2d). `--range` selects a git revision range instead. At most 1000 commits are audited per invocation. Reconciliation and missing controls cover selected commits; reverse reconciliation checks all reachable local refs, not just the selected range. Actions in a since query are filtered by their recorded time; unknown-time actions in the repository context are included and counted explicitly. Range actions use selected work segments or the interval from the first selected commit's parent to the last selected commit. Rewritten dates, missing timestamps and partial transcripts can affect that scope. Relevant push/publish follow-ups are checked until the next commit or substantive request.

## Record versus reality

For each selected commit, the report includes its ID and classification:

- **explained**: the union of approved linked sessions’ recorded edits cover the non-ignored added lines/files. This is content correspondence, not proof that the agent made every change.
- **partly_explained**: some non-ignored added lines/files have neither covering edits nor a plausible modifying command. Counts and percentages of unaccounted added lines/files are included. Paths stay hidden by default.
- **command_modified**: remaining changes could plausibly come from a recorded formatter, generator, package manager, literal in-place edit, script, or git move/checkout/restore/merge/apply operation. These are not called unexplained; they cannot be verified line by line from the available record.
- **commit_only**: a linked session recorded committing, but no linked contributor recorded edits or a modifying command for these files. This is not labelled partly explained and is not a reconciliation finding by itself.
- **no_ai_record**: no linked session. This is normal for human work and creates no finding by itself.

The comparison counts exact added-line text, including short, blank and repeated lines, using captured Write/Edit/MultiEdit, patch and literal-shell-write content. It uses the maximum observed per-file line multiplicity across captured edits, rather than summing snapshots that may repeat the same content. Partial edits, identical additions in separate captures, alternative contributors, unrecorded formatting and unsupported schemas can therefore look partly explained. All approved trace-linked candidates contribute. The report lists contributor roles (`author` for recorded edits/modifications and `committer` for recorded commit actions); these are evidence roles, not trusted git identities. Counts use the union of contributors without double-counting matching lines. Ambiguous links and incomplete joint-agent records still need inspection. Removed-only/binary files without a covering edit remain unverifiable. Merge changes are compared with the first parent. This does not verify binary content or claim removed-line correctness.

A broad script or package command can conceal an off-record change under command_modified; the label states uncertainty, not correctness or approval. Failed/partial commands and complex shell expansions also need review. Command recognition uses quote-aware shell segments and literal prefixes, retains multiline command headers and ignores quoted examples/comments; it is not a shell interpreter or a reconstruction of every filesystem side effect.

**recorded_but_missing** reports a captured successful-looking commit whose observed hash (or subject when no hash was captured) is absent from reachable local history. Quiet subject-only commits require a tool result without a known failure. A captured hash line remains a positive commit record even if a later command in that call fails. Multiple wrapper results are decoded separately. Commit commands consume distinct hash records, matching subjects first and otherwise using recorded order; quiet empty results retain their own chunk. Missing hashes are deduplicated per source and hash. An old hash does not veto a subject or patch match to rewritten history. Wrapped Claude Code/Codex results, including `[branch (root-commit) hash]`, are decoded as data. An unreachable observed hash is reported even when an equal subject is reachable. Matching stable patch IDs and `rewritten: true` are included when a rewrite can be recovered from a retained old object or captured pre-commit diff. Amend/rebase/drop operations can be legitimate; unreachable objects may expire; equal subjects are not unique identities. This finding does not prove a force-push or a dishonest record.

### Ignored changes

The output lists the active ignore globs and counts ignored files/added lines. Defaults are package-lock.json, yarn.lock, pnpm-lock.yaml, poetry.lock, uv.lock, Cargo.lock, `*.min.*`, `build/**`, `dist/**`, and `*.egg-info/**`. Globs match repository-relative paths or basenames, case-sensitively. `--ignore GLOB` adds a pattern. An existing profile can replace defaults, including with an empty list:

```json
{"audit": {"ignore_globs": ["dist/**", "*.min.*"]}}
```

Ignores affect reconciliation, not notable-action rules. Ignore-only linked commits are marked `ignored_only`; their explained label means no non-ignored changes remained to check. It is not verification of ignored content. Totals count file occurrences per commit, not distinct files across the run.

## Notable recorded actions

Each finding identifies its report group and has a fixed category/description, severity, opaque session ID, source-turn URN and canonical recorded time (or null). Counts are grouped per report and category. Rules are documented heuristics, not a complete detector:

| Category | Fixed recognition | Severity / limitations |
|---|---|---|
| secrets | Credential-like arguments; reads of .env/.ssh/.aws, home dot-key files, PEM/id_* files, .netrc/.npmrc/.pypirc/credentials*; environment/store reads | high for sources/non-placeholder values; credential-like values shorter than 16 characters or containing fake/dummy/example/placeholder/test/invalid/xxx/changeme/never-valid (case-insensitive) are low and never escalate network; `env | grep -c NAME` and `printenv NAME | wc` are low presence checks and do not escalate later network findings. Filename patterns can include benign files; indirect reads may be missed. |
| remote_code | A curl/wget pipeline into a shell or Python stdin interpreter, or a literal downloaded target later executed | high; Python `-c`/`-m` data parsing and unrelated local scripts are excluded. Literal saved downloads are tracked within 20 parsed turns. Dynamic file names remain unsupported. |
| outside_repo_writes | Literal non-scratch write targets outside the selected repository | high; device/fd redirects are excluded. Scratch writes are separate info counts. Agent memory/settings writes use persistence_config instead. Script-internal dynamic writes remain unsupported. |
| log_output | Redirects or tee to outside-repository `.log` targets | low; sensitive, credential and persistence locations retain their normal rules. This does not inspect log content. |
| persistence_config | Real configuration write targets or modifying git config commands (value, --unset/--add/--replace-all) | medium; config queries/bare-key reads and strings mentioning release/hooks are excluded. Home .claude/.codex paths group once per session/path class, across work blocks. Legitimate maintenance still triggers. |
| destructive | Recursive forced rm targets, reset --hard, history rewriting, recursive permission changes and force pushes | medium, except plain --force/-f push is high. --force-with-lease remains medium. rm flags come only from its own segment; outside-repository scratch cleanup is info. |
| network | Literal network commands, recognised fetch tools and push/tag/publish operations | low, high following a high secrets observation within the same command or 20 parsed turns; presence-only checks do not escalate it. Correlation is not proof of data transfer. |
| dependencies | Package installs or dependency-file changes | low; no package-trust assessment and not every manager is recognised. |
| possible_injection_chain | Instruction-like tool output followed by a high/medium action within 10 parsed turns | high, explicitly heuristic. Examples and legitimate instructions may trigger; subtle instructions can be missed. |
| scratch_write / scratch_cleanup | Literal writes/recursive forced removals outside the repo in configured scratch dirs | info only; these counts describe recorded observations, not verified file operations. |


Turn windows count parsed source turns, excluding provider metadata. Sessions and actions are scoped by recorded working directory, literal explicit directory changes or absolute in-repository edit targets. Outside writes initiated from the selected repository are included; unrelated repositories are excluded. Spoofed/missing directory metadata and mixed-purpose sessions remain limitations. An escalation links recorded events; it does not infer intent or causation. Raw commands and outputs are never executed by audit.

### Scratch directories and literal scripts

`audit.scratch_dirs` replaces the scratch defaults; an empty list disables the exemption. Defaults include OS temporary directories (`/tmp`, `/private/tmp`, `/var/folders`, the OS temp directory and `$TMPDIR` when set). Entries must be absolute paths. A sibling work folder may be listed explicitly when it is used as scratch space. Scratch settings themselves are not printed, avoiding personal path disclosure. Writes inside the selected repository keep normal treatment even if that repository lives under an OS temp directory. Home `.claude` / `.codex` writes are classified as agent persistence before scratch checks.

Literal Python/Node heredocs are inspected statically for `Path(...).write_text`, `open(..., 'w').write`, with-open writes, and `writeFile`/`writeFileSync` calls on literal paths. Unknown content is credited only as command_modified for those targets; literal write values and literal `.replace('old','new')` additions may supply exact line evidence. Scripts are never evaluated and target files are never opened by the analyser. Dynamic paths, transformations, control flow and aliasing can remain unknown. Statements are visited in source order, but this is not a Python/JavaScript interpreter or proof of execution. Strings/comments mentioning writes do not create Node write targets.

Git `-c` (including repeated options), `--no-pager`, `-C`, and leading environment assignments are recognised. Tests/builds accept assignments, literal `env` wrappers (including unknown variable expansions before a known executable) and for/while/until-loop bodies. Commands inside `$()` and backticks are inspected as literal command syntax in source order, including credential, network, test/build and commit rules. Single-quoted examples and heredoc data are not treated as executable commands. Earlier standalone `NAME=/absolute/literal` assignments can resolve `$NAME/…` and `${NAME}/…` write, redirect and removal targets; unknown expansions stay unknown. No substitution output is evaluated. These limited recognisers do not model shell control flow, conditional execution or dynamic values. Known tests earlier in the same call than the commit are recognised; tests after the commit are not a pre-commit control. Unknown expansions are never executed or used to invent commands.

## Missing recorded controls

For AI-linked commits only, fixed findings flag:

- no substantive originating request (medium);
- no recorded test/build between the last modification and commit (medium);
- no user turn after that modification and before the commit (low; an autonomous commit, not necessarily unauthorized);
- push, tag or publish activity associated with the work (medium);
- changes to CI/release configuration, auth/crypto-named paths or dependency manifests (medium).

A qualifying recorded test/build in any linked contributor can supply the test-control evidence. Tests may have run elsewhere; a build is not necessarily a test; earlier user approval can authorize autonomous work; a sensitive filename does not establish a sensitive behavior. These are missing records or review prompts, not proof of defects. A no-record human commit is not flagged simply for lacking these controls.

## Privacy and sharing

Default text is a short summary followed by grouped findings; Markdown contains counts and grouped findings, without repeating all reconciliation rows. JSON retains structured reconciliation data. All formats contain counts, fixed labels/descriptions and references only: commit IDs, opaque session IDs and turn URNs. No session titles, transcript prose, commands, changed filenames, hosts or outputs are shown. Configured ignore patterns are explicitly listed as configuration, not as discovered file names. Stable URNs identify local source lines, not guaranteed provider UI links.

Findings with the same session, category and fixed rule in one substantive work block are grouped. Each group retains occurrences, first/last turns and URNs, time bounds and associated commit references. Agent memory/settings path classes deliberately group across work blocks. A group takes its highest observed severity. Top-level raw/grouped counts and raw severity/category counts remain available. `--min-severity info|low|medium|high` defaults to medium and filters only the printed findings list; counts, reconciliation and the fail threshold still use the whole run. Use `--min-severity info` to include scratch and other low-level observations. Grouping counts observations in records, not independently verified distinct real actions.

`--show-details` requires a terminal and explicit confirmation per opaque session. It can then show relevant captured commands/outputs and repository-relative unaccounted/sensitive paths. Credential and email redaction is applied. Profile `trace.sensitive_terms` drops an entire matching turn, replacing it with `[turn withheld: sensitive term]`; path details are filtered too. A refused confirmation leaves references only. Prompts go to stderr with `--json`. Append-only source growth is ignored; rewriting/truncating/deleting an audited snapshot, withdrawing approval or changing settings aborts before output.

Details can contain unrelated material from imperfectly segmented records. Filtering is not a guarantee that every private item is recognized. You decide whether to export confirmed details; default Markdown is the references-only shareable summary. No output is transmitted automatically. `--fail-on high` exits 1 for high findings; `--fail-on medium` exits 1 for medium or high. Low findings alone do not fail either threshold. Input/storage errors exit 2. Without the flag, findings do not block anything automatically.

## Optional integrity seal

```sh
context-bridge audit --repo /path/to/repo --since 30d --seal --profile personal --json
context-bridge audit verify --profile personal --json
```

Sealing explicitly appends to a private `audit-ledger.jsonl` in the profile directory, outside the repository. Each record contains SHA-256 snapshot hashes, hashed source/repository locators, prefix sizes, a counts-only summary, the previous record hash and its own hash. It contains no transcript text, raw paths, subjects, hosts or session titles. The append is locked and synced; symlink/hardlink ledger targets and repository-local storage are refused. Audit without `--seal` creates no ledger.

Verify checks the chain and every sealed prefix. It reports unchanged, appended, modified, truncated, deleted, or unavailable/revoked sources using hashes only. Legitimate append-only growth after a complete sealed prefix is reported as appended and is not a failure. Revoked/excluded sources are not opened; relocated/unregistered sources cannot be resolved without their original approved configuration. Verification is read-only and exits nonzero on a broken chain or an unavailable/changed source.

The ledger has no signature, trusted external anchor or independent witness. Someone able to rewrite the entire ledger can recompute its chain; sealing cannot establish integrity before the first seal or prove authorship. This is a local aid to later comparison, not tamper-proof evidence, an accuracy claim or monitoring of other people.
