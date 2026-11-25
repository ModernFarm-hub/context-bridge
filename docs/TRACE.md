# Experimental commit tracing (0.12.0a3)

`trace` ranks local evidence connecting a commit to an already approved Claude Code or ChatGPT desktop (Codex) transcript. The experiment asks whether the selected turns help a person understand why code changed. A match is not proof of authorship. All shipped fixtures and verification use invented repositories and transcripts. One small real-repository check is reported [below](#first-check-on-a-real-repository); it is not a general accuracy or quality claim.

```sh
context-bridge trace HEAD --repo /path/to/repo
context-bridge trace main~10..main --repo /path/to/repo --profile personal --json
context-bridge trace HEAD --repo /path/to/repo --show-text --sensitive-term surprise
context-bridge trace-eval --repo /path/to/repo --sample 20 --seed 42
```

`--max-results` accepts 1–20 candidates per commit (default 3). Ranges are limited to 1000 commits. `--directory` selects an existing library root; `--profile` selects its existing named profile. A missing profile fails without creating state. No unapproved session discovery, import, embedding download, web export search or network request occurs. The command reads original approved tool transcripts because the ordinary search index deliberately omits tool actions.

## First check on a real repository

On 2026-11-24 the maintainer ran `trace` on this repository's own history (35 commits, all built with Claude Code or ChatGPT desktop). No transcripts or answers are published; only these counts.

**Linking.** 34 of 35 commits were linked to a session, all to the correct tool. Results were identical whether a commit was traced alone or within a range. The one unlinked commit had no matching session among the approved sources.

**Raw turns are not enough.** Reading the selected turns directly (`trace-eval`) proved impractical: too long and noisy for a person to judge why a change was made.

**Short AI answers, blind comparison.** For 10 seeded linked commits, fresh AI agents with no knowledge of the project answered "why was this commit made?" in two ways: from `git show` only, and with `context_trace`. Answers were compared against the known history.

| `context_trace` version | Better than git | Tie | Worse than git |
|---|---|---|---|
| 0.11.0a2 (session turns only) | 4 | 1 | 5 |
| 0.11.0a3 (commit message + session, walk back past "commit and push") | **7** | **3** | **0** |

No answer invented a reason, and none contained unrelated private material. Turns matching the maintainer's sensitive terms were withheld. Where trace helped, it found reasons that existed only in conversation: a constraint discovered while setting something up, the event that prompted a safeguard, the request that asked for regression tests. Git-only answers could only guess at these.

**Limits:**
- One repository, 10 commits.
- One grader, who was involved in the work, so the grading is not independent.
- Commit messages here are unusually detailed, because AI agents wrote them. Repositories with terse messages may differ, in either direction.

Treat this as a reason to try it, not as evidence that it works for you. Your own `trace-eval --ai` run is the test that counts.

## Opt-in MCP evidence for your AI

`context_trace` lets your existing AI client read the selected evidence and produce a short explanation. **It is disabled by default and absent from `tools/list` until enabled for that profile. Enabling it authorizes sending selected session text to your AI client and therefore to that client’s model provider.** This changes the privacy boundary from the references-only CLI. The Context Bridge server itself makes no model/API request. Configure the same profile in your MCP client, then reconnect after changing the tool list:

```sh
context-bridge trace enable-mcp --profile personal
context-bridge trace sensitive add 'synthetic-private-topic' --profile personal
context-bridge trace sensitive list --profile personal
context-bridge trace sensitive remove 'synthetic-private-topic' --profile personal
context-bridge trace disable-mcp --profile personal
```

The commands operate on an existing profile, with no discovery or import. Optional `--directory` selects its library root. Settings live in `trace.mcp_enabled` and `trace.sensitive_terms`; a named profile has independent settings. Each call rechecks opt-in, source approvals, snapshot fingerprints and filter settings. Append-only growth after the snapshot’s last complete line is allowed and ignored, including in an active session. Rewrites, truncation, deletion, exclusion or approval/settings changes fail closed before text is returned. The tool does not refresh the search index or record returned evidence in usage logs.

Inputs accept one `commit` hash/ref, a repository-relative `path` with optional positive `line`, or a `range` / `since` query optionally limited to `path`. `repo` is an optional absolute repository path; by default it is the git top-level containing the MCP server’s working directory. Start the server there or supply `repo` explicitly. A path must resolve inside that repository; outside and escaping symlink paths are refused. Path plus line uses read-only porcelain blame of committed HEAD; path alone resolves the latest HEAD-history commit touching that path. The returned `commit` identifies the resolved commit. Uncommitted lines are not attributed. The CLI supports the same location lookup:

```sh
context-bridge trace --path src/x.py --line 42 --repo /path/to/repo
```

### Ask it like this

- “Why is line 42 of src/x.py like this?” → `path: src/x.py`, `line: 42`.
- “What changed in src/auth since Monday and why?” → `path: src/auth`, `since: Monday`.
- “Why was commit abc123 made?” → `commit: abc123`.

For a single commit, structured sections are `git`, `origin`, `go_ahead`, `decisions`, `tool_summaries` and `citations`, plus matching metadata. `git` contains the redacted full commit message (subject and body), author date (no author identity), and capped diffstat with whole-commit totals. The message can be explicitly truncated under the budget; its prefix is capped at half the nominal character limit and fitted within the budget remaining after reserved file context. The tool uses the existing matcher’s candidates, evidence weights, source approvals and repository scoping. An abstention returns no session text; the redacted git context remains available as the baseline.

Short, explicit approvals under twelve words, such as “yes to both”, “do it”, “commit and push” or “continue”, stay in the work block whose substantive request led to relevant edits. The matcher marks substantive origin turns and go-aheads separately. It never searches backwards through an unrelated request block to invent an origin; missing origin evidence remains missing. Selected assistant prose containing reason/alternative cues (because, instead of, so that, rejected, trade-off, root cause, fails when, doesn’t work) ranks ahead of other prose; the cue is a heuristic, not proof of a reason.

Tool summaries contain fixed categories, counts and filtered repository-relative edit paths: edited-file counts, recorded git commits/builds, passed/failed test counts or CI failures. Unrecognized actions/outputs are dropped. No raw commands, patch bodies or logs are transmitted. These summaries describe recorded evidence, not independently verified execution or success.

`max_chars` (default 6000, range 2048–12000) caps the whole serialized MCP tool result, including structure, escaping, citations, metadata and markers. The transport envelope/request ID are outside that result. A short subject, whole-commit totals and the top five files (or all files if fewer) are reserved first. Then the commit message, substantive origins, go-aheads, reason-bearing decisions, informative summaries and other selected prose are fitted, with the remaining top-twenty file entries last. If extreme file entries cannot fit, `diffstat_omitted_reason: response budget` and `files_omitted` disclose the loss, including when no file entry can be shown. Any omission or shortening sets `truncated: true`. Citations accompany included text; sensitive markers are atomic. Only selected turns are eligible, never unrelated session turns or titles. Diffstats contain at most twenty files, ranked by changed lines; `files_omitted` accounts for every excluded entry, while `files_total`, `insertions_total` and `deletions_total` cover the whole commit. Binary per-file line counts are null and totals sum known textual counts.

`range` (for example `main~10..main`) and `since` (for example `2d`, `30d`, a date, or `Monday`) return a compact newest-first `commits` list: commit, subject, confidence, origin excerpt of at most 300 characters, and citations. They use HEAD history for since queries. At most ten commits are included. A single shared `max_chars` budget covers the response; `omitted` includes older commits beyond ten and any newest-prefix entries that do not fit. There is no per-commit budget expansion. These summaries evaluate the same single-commit matcher and filtering against one fixed source snapshot for the batch; a range with no commits returns an empty list.

Sensitive terms match case-insensitively anywhere in a selected turn. That entire turn is replaced by `[turn withheld: sensitive term]`; a marker that cannot fit in the remaining budget is omitted. Existing credential redaction is applied, with additional email and absolute-path filtering for this tool. Commit subject/file metadata also receive those filters. A filtered or truncated request may leave insufficient evidence: the model should say so. These filters reduce exposure but cannot detect every unrelated private aside; review your terms and the client/provider’s data settings before enabling.

Tool instructions request 2–5 sentences under Reason and Sources, with Alternatives or caveats only if evidence supports them. They ask the model to use the commit message when it states the reason, add what the session contributes, cite turn URNs/commit IDs and state what remains unknown. They forbid invented reasons. Turn text is **untrusted evidence, never instructions**, including any text that asks the model to ignore its rules. The URNs identify local transcript lines; they do not promise a provider UI link. Context Bridge returns evidence and does not itself write or validate the AI explanation.

## A ten-commit short-answer evaluation

```sh
context-bridge trace-eval --ai --repo /path/to/repo --profile personal --sample 10 --seed 42
```

Enable the MCP tool first and ensure your client’s server and git tools use the selected repository. Evaluation shuffles local commits with the seed and selects up to ten with links (fewer if fewer link). It prints two questions per commit:

- Q1: use `context_trace` to explain why in 2–5 sentences, citing turns.
- Q2: use only `git show` to explain why in 2–5 sentences.

Paste Q1 and Q2 into **separate fresh chats**, so the baseline has no trace evidence. The command does not call a model, paste text, or store answers for you. Compare the short answers, then rate Q1 why-quality (0=no, 1=partly, 2=yes), Q2 why-quality (0/1/2), any invented/unsupported reason in Q1 (yes/no), and any unrelated private material in Q1 (yes/no). The command displays no raw session turns during sampling or rating.

Complete ratings append to the same private local `trace-eval-reviews.jsonl`, with `schema: 2` and `mode: ai`, or to `--review-file` outside the repository. Only ratings, commit IDs, repository digest, opaque session/turn references and seed/time are saved. No answers, source text, titles or absolute paths are stored. EOF/cancellation preserves completed ratings. JSON reports keep questions/prompts on stderr. The report gives mean Q1 and Q2 quality, mean paired Q1-minus-Q2 difference, invented-reason count and privacy-incident count for completed pairs in this invocation. It is labelled **one person’s judgments on one repository**. Sampling only linked commits does not measure overall coverage. These judgments are not an independently established explanation-quality result.

## Evidence and abstention

The matcher scopes tool actions to the selected repository. An explicit tool working directory, recorded working-directory context, leading `cd`, or simple `git -C` can establish scope. Absolute edit paths can establish file scope even when the tool runs elsewhere. Different repositories and nested repositories are excluded. Ambiguous shell context can be missed rather than guessed.

Evidence ranks in this order:

1. A captured commit object or a captured pre-commit diff with the same stable `git patch-id`. Old observed object hashes are looked up read-only in the selected repository. This can match amend, rebase or metadata rewrites without relying on the current hash, subject or committer date alone. If old objects have expired and no diff was captured, exact patch evidence may be unavailable.
2. A recorded `git commit` command whose normalized first subject line matches. Simple `-m`, `--message`, combined `-am`/`-qam`, repeated `-m`, literal heredocs, `$(cat <<EOF)` messages and `-F`/`--file` forms are recognized. `--amend --no-edit` can use the prior captured subject or resulting commit output. `-F` content comes only from captured file writes/reads or heredocs, never from opening a current message file on disk. Recorded commands and substitutions are never executed. An uncaptured editor message or complex shell expansion may be unavailable.
3. Exact overlap of informative added lines in the commit diff and captured edit content. Claude Code Edit/Write/MultiEdit, Codex apply_patch Add/Update/Delete, wrapped executor calls, and literal shell heredoc/echo/printf writes are supported. File names alone never create a link. Deletion-only changes may use removed-line overlap when old content was captured; a bare delete path is insufficient. Missing or future edit timestamps cannot establish standalone file-edit evidence. When a captured commit has exact patch identity, its original recorded edit/commit order can identify the work origin despite rewritten dates. Patch comparisons are cached in memory only.
4. Time proximity adds at most two tie-break points after other evidence exists; it never creates a link. High confidence requires strong command or patch evidence; content-only matches are generally medium/low. Near-tied candidates are marked ambiguous.

The code uses fixed, conservative heuristics, not calibrated probabilities: informative line length/vocabulary filters, at least 35% added-line coverage for content-only candidates, stronger patch/subject weights, and a weak time adjustment. Generic commit subjects without corroboration are insufficient. A commit request without a captured tool result is downgraded, not treated as confirmed execution; explicit fatal/no-commit output cannot supply command-subject evidence. These choices are synthetic starting points; evaluate them locally instead of interpreting confidence as measured precision. Complex shell scripts, unsupported tool schemas, moved working trees, binary changes, merge commits and unusually short/generic edits can be missed. A human-only commit can return **no AI session found**. That means no sufficient evidence was found, not proof that no agent was involved.

Git commands disable external diff/text conversion, optional locks, filesystem-monitor helpers and lazy fetching. They do not write commits, hooks, notes or repository configuration. Partial/promisor repositories are refused rather than hydrating missing objects. All git network transports are disabled. Read-only trace creates neither library state nor caches. Existing approval settings are not refreshed or rewritten.

## Work segments and turn references

A substantive real user request starts a work block; recognized short continuations remain in that block. Commits do not reset the origin, so a segment can span earlier commits. Relevant edit blocks and their originating/continuation prompts are selected through the matching commit. Test failures, CI-log reads and other tool outputs are reported as turn references. When an unrelated substantive request intervenes, its block is excluded even if a later generic commit prompt finishes earlier work. The selected turn set can therefore be non-contiguous; start/end bounds do not authorize showing every intervening turn.

Turn numbers are physical JSONL record/line numbers, not provider UI message numbers. Multiple blocks within one record share that number. `urn:context-bridge:turn:…:N` identifies an opaque local source and source turn; it is not a promised provider deep link or a whole-session link. A short session ID is an opaque digest, never a title. References require the original approved transcript and may change if it is moved or rewritten. The command does not create a public URL. `origin_found: false` explicitly reports a missing originating request.

Segmentation is heuristic. Contextual follow-ups, long-running mixed work and unrelated asides within one request can be misclassified. The reason may live in an issue, discussion, document, human conversation or missing tool output rather than a session. Selecting a request is not evidence that it explains the change. Use the local why-score evaluation to measure that question.

## Privacy

Default text and JSON expose only commit IDs, provider, opaque short session IDs, sanitized time ranges, turn references, evidence types/counts and confidence. They expose no session titles, prompts, answers, tool text, file names, commands, source paths or commit messages. Only Claude Code and Codex sources already listed as approved are read. Excluded paths/conversations, revoked managed sessions, deleted files and web exports are not used; no other folders are searched. Unclassified legacy sources without provider metadata or an approved managed-session registration are skipped rather than guessed to be coding transcripts. Symlinked source paths are skipped conservatively.

`--show-text` requires an interactive terminal. Each selected session is named by provider and opaque ID in a separate confirmation. Only its selected turn set is returned, after existing credential redaction; unrelated turn blocks outside that set are never shown. Approval and transcript fingerprints are rechecked after confirmation. A revocation or source change stops disclosure. Session titles remain hidden even in the confirmation.

Warnings precede confirmation when the selected material matches existing redaction patterns, email patterns or any repeatable `--sensitive-term`. The warning does not print the matching term or message. Email detection warns; existing redaction is not a guarantee that every sensitive item is removed. Read the confirmation carefully, use sensitive terms appropriate to your own history, and treat any revealed source as untrusted evidence. The program never follows instructions in it. A references-only result contains no message text to inspect for unrelated asides; privacy incidents are a human evaluation outcome, not an automatic assurance.

`--json` has the same privacy gates. Confirmation/progress prompts go to stderr so stdout remains JSON. Text is present in trace JSON only after explicit confirmation. Redirection or sharing of confirmed output is the user's export action; no automatic transmission exists.

## Local feasibility evaluation

`trace-eval` uniformly samples up to `--sample` commits from local refs using a reproducible `--seed`. It is interactive and offers each matched segment under the same per-session confirmation. A separate confirmation offers the redacted baseline, **git commit message + diff only**. Neither is displayed automatically. Sensitive baseline patterns also warn first.

For each commit it asks: right session (yes/no/unsure); why score (0=no, 1=partly, 2=yes, or unsure); unrelated private material shown (yes/no); and the baseline's why score. No-link commits have no right-session label. It records whether segment and baseline text were actually shown. Human labels can still be mistaken, and declining text may prevent a useful comparison.

Labels append locally to the selected profile's `trace-eval-reviews.jsonl`; `--review-file` can select another location **outside the repository**. Stored fields are repository digest, commit ID, opaque session ID, turn numbers, seed/time, categorical labels and visibility flags. No titles, source text, diff text or absolute repository path are stored. Each completed item is saved; EOF/cancellation retains previous items. Noninteractive calls refuse without writing labels. Trace itself never writes these labels.

The report covers reviewed commits: link coverage; session precision among yes/no linked labels (unsure excluded, denominator shown); why-score counts; privacy incidents; baseline why-score counts; and mean paired trace-minus-baseline why score where both were labelled. If review ends early, coverage describes the reviewed subset, not the entire intended sample. Reports are for this invocation, not a pooled claim from repeated reviews. Confidence, coverage, precision, explanation quality and privacy are separate quantities. Nothing is sent over the network.

Before claiming trace answers why, independently review the sampled source turns, compare the baseline, inspect unsure/missed matches and report privacy incidents. This release supplies the experiment, not its outcome.

### Parser coverage diagnostics

Use `context-bridge trace HEAD --explain-coverage` to inspect counts per approved session without revealing titles, paths, commands or message text. The counts include tool calls seen, calls recognized as command wrappers, repository-scoped commit actions, edit actions, and parser failures. Command-call counts can include commands outside the selected repository; commits and edits are scoped. These are parser diagnostics, not matching accuracy or evidence of why a change was made. With `--json`, this option returns an object containing `results`, `coverage` and `coverage_differences`; ordinary JSON output remains unchanged.

The parser reads quoted multiline commit messages across shell chain boundaries and extracts the first message line as the subject. It decodes literal `cmd`/`command` and `workdir`/`cwd` strings from Codex `exec` JavaScript wrappers without evaluating JavaScript or shell substitutions. Relative working directories resolve against the recorded turn directory. An empty, non-error tool result supports a quiet commit command at lower confidence than a confirmed commit hash; it cannot prove that every command in a chain succeeded. `REV^!` and `REV^-` select the named commit itself.


### Range independence and snapshot checks

Each commit is scored independently against the same transcript snapshot, with a fresh memoization scope for that commit. Patch-ID caches store only functions of the selected repository and the recorded object hash or complete diff. Matching does not consume actions, reserve sessions, or derive windows from adjacent commits in the requested range. Subject reuse after `--amend` is resolved from transcript order; patch identity supplies stronger evidence than a reused subject. Subject equality alone is not an exclusive ownership claim: a transcript action may remain a candidate for multiple commits, with the same evidence regardless of the selected range. A captured pre-commit diff is associated only with the next recorded commit action, never all later commits in the same work block.

The previous implementation rechecked the entire transcript fingerprint after each commit and silently removed candidates if the file grew. A synthetic append-during-evaluation fixture reproduced this failure. This establishes a range-dependent failure mechanism; it does not establish the cause of every reported real-data discrepancy. The snapshot now permits append-only growth after its complete last line, ignores those new turns, and validates the original bytes and approval before returning any results. A rewrite, truncation, deletion, exclusion or approval withdrawal invalidates the entire invocation with an error instead of changing later candidates to “none”. Text revelation retains its stricter full-file change check. Results across separate invocations can legitimately differ if the transcript or approval inputs themselves change.

`--explain-coverage` also independently reparses the fixed transcript snapshots and cold-evaluates each selected commit alone. It lists any differing commit IDs in `coverage_differences` (JSON), or `Single/range differences` (text); the expected list is empty. This compares the full public result: confidence, ranked candidates, evidence and segment. It exposes no source text or paths, and adds parsing and git-read cost. The diagnostic compares identical snapshot inputs; it does not claim that a changing live library stays identical across separate commands.


## Counts-only developer self-report (CLI only)

```sh
context-bridge trace report --repo /path/to/repo --since 30d --profile personal --json
```

This explicit local command reports commit counts, counts with evidence by provider and confidence, counts without evidence, and the percentage of changed textual lines in commits that have evidence. Provider counts may overlap for ambiguous candidates; the line fraction counts all changed lines of linked commits, not AI-authored lines. Binary changes have no textual line count. It prints no prompts, session IDs, commit IDs, titles, filenames, author identities or per-person detail. No report tool is exposed over MCP and no source text is printed. The report is the developer’s self-report to share if they choose. It is not monitoring, and evidence is not proof of authorship.

The privacy boundary differs: `context_trace` sends selected redacted turns to the user’s AI client and its model provider; `trace report` computes local aggregate counts and sends nothing. Both use only already approved sources. Neither establishes explanation quality or authorship.
