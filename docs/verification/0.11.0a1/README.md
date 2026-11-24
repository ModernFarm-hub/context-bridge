# 0.11.0a1 synthetic verification

Experimental trace feasibility infrastructure, verified locally on Python 3.9 / macOS. No real conversation library, feasibility probe or real evaluation labels were used. No explanation-quality or real-world matching claim is made. No repository publication, tag, push, issue or PR.

- Full regression suite: 278 tests pass with CI unset and with CI=true; 29 optional skips.
- Twenty-one trace tests use only temporary synthetic repositories/transcripts and invented labels. They cover -m/-am/-qam/repeated -m, heredocs and literal cat substitution, -F captured files, --amend/--no-edit, amend/rebase/filter-branch identity, rewritten dates, captured patch identity without an old object, and origin across an earlier commit.
- Content overlap selects the right session among same-file edits. Human-only changes abstain. Claude Edit/Write/MultiEdit, Codex apply_patch Add/Update/Delete, wrapped executor calls and literal shell writes are exercised.
- Mixed-purpose sessions retain originating request, edit and test/CI references while excluding unrelated turn blocks. Default text/JSON include no title or message text. Confirmed display is scoped and redacted, warns for sensitive patterns, and rechecks withdrawal/source changes. Web exports, unknown providers, revoked/excluded/deleted sources are not used.
- Snapshot tests verify trace changes neither repository nor profile. Partial/promisor repositories are refused without lazy fetch; git network transports and executable diff helpers are disabled.
- Local evaluation tests cover labels, coverage, precision/unsure denominators, why scores, privacy incidents, baseline comparison, refusal of noninteractive review, local-only label storage and clean JSON stdout under an interactive terminal.
- Runtime/version metadata and active release pins are 0.11.0a1; historical versioned evidence remains historical. No existing benchmark outputs were reinterpreted as trace results.

[Method, limitations and privacy](../../TRACE.md). A real evaluation must be performed and independently assessed before making any claim that trace explains why code changed.

Parser correction fixtures cover multiline quiet commits in chains, Codex custom-tool `exec` JavaScript literals with escaped commands, relative workdir, heredoc edits, empty tool results, scoped abstention, single-commit selectors and counts-only coverage.

Range-independence correction: five shuffled orders and a normal range match individual public results across several commits/sessions, quiet commands, a real synthetic amend, two commits in one work block, and a human-only commit. Parsed actions remain unchanged. A fixture reproduced the old silent loss of candidates when a transcript appended during evaluation; append-only growth now retains the snapshot, while rewriting existing bytes or revoking approval aborts the full result. Coverage self-check returns no differences and a deliberately injected result mutation is detected. Real-data range independence remains to be re-verified by the tester; static synthetic properties do not establish the cause of all reported real-data discrepancies.
