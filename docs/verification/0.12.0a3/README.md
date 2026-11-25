# 0.12.0a3 synthetic verification

Synthetic repositories and invented transcript structures only. No real transcripts or personal data are fixtures; no accuracy or authorship claim is made.

- Full regression suite: 327 tests with and without `CI=true`, with 29 optional skips each.
- Multi-result fixtures cover three commits in one Codex wrapper, distinct hashes, three rewrites and trace links, subject-based pairing, duplicate hash records and a quiet empty result.
- Shell fixtures cover substitutions, backticks, for/while/until bodies, credential-source/network ordering, tests/builds, quoted non-commands, device redirects, absolute literal variables, unknown variables, placeholder credentials and outside log redirects/tee with sensitive-location exceptions. Substitution-local variable assignments do not leak into outer commands.
- Existing trace scoping/determinism, approvals, redaction, output budgets, audit reconciliation and integrity fixtures remain active.

[Rules and limits](../../AUDIT.md). No paid/model call, tag, push, publication, issue or PR.
