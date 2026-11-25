# 0.12.0a2 synthetic verification

Audit precision fixtures, verified locally on Python 3.9 / macOS. No real transcripts, personal paths, repository history or real-run findings were used as fixtures. No accuracy or authorship claim is made. No tag, push, publication, issue or PR.

- Full regression suite: 321 tests with and without CI=true, 29 optional skips each.
- Twelve additional fixtures cover ten rewritten Codex commits with equal reachable subjects and nested result wrappers, both root/normal commit result forms, git global/directory/env prefixes, wrapped and looped tests (including tests before a commit in one call), data-parser pipelines versus downloaded execution, device/fd redirects, modifying versus read-only config, scratch info versus normal writes, force versus lease severity, agent path-class grouping, low presence checks and key-file sources.
- Literal Python/Node heredoc fixtures cover relative write targets, literal replacement text and quoted non-write examples. A two-agent author/committer case reconciles their union and recognises tests without remote-code/outside-write/destructive findings. A commit-only case is not labelled partly explained.
- Grouping fixtures verify occurrence/first/last bounds, raw/grouped counts, severity filtering without count loss, concise text and grouped-only Markdown. Existing approval/scope/privacy/no-execution/ledger and trace determinism/budget fixtures remain active. The old non-scratch outside-write fixture explicitly disables temp exemptions for its synthetic home.
- Wheel/sdist payload checks, strict metadata checks and an installed CLI/MCP smoke test pass. The wheel stays below 500000 bytes. No real audit or model call was performed.

[Rules, output semantics and limits](../../AUDIT.md). Planted-case behavior is not real-world detector performance.
