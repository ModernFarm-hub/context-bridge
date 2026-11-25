# 0.12.0a1 synthetic verification

Experimental local audit, verified on Python 3.9 / macOS with invented repositories and approved transcript fixtures only. No real conversation library or real history was audited, no model/network request was made, and no accuracy or authorship claim is made. No tag, push, publication, issue or PR.

- Full regression suite: 309 tests with and without CI=true, 29 optional skips each.
- Thirteen audit fixtures plant off-record added lines (including duplicate, short and blank lines), formatter/package-manager uncertainty, ignored lockfiles, dropped and metadata-rewritten commits, secrets followed by network activity, remote download/execute patterns, possible injection chains, outside writes, CI/configuration changes, missing origin/tests/user control, publish/force-push activity and normal human work with no findings.
- Privacy fixtures exercise references-only JSON/Markdown, per-session confirmed details, sensitive-term withholding and redaction. Recorded commands are never executed; unrelated/unapproved/excluded providers are not used; live append preserves the snapshot; default audit changes neither repository nor profile.
- Ledger fixtures check hashes-only private storage, append validation, modification/truncation/deletion, chain corruption, excluded-source refusal and repository/symlink storage refusal.
- Existing trace/parser/snapshot/determinism/budget tests remain in the suite. Exact line counters are additional parser metadata; matching weights and heuristic line sets remain unchanged.
- Wheel/sdist payload checks, strict metadata checks and installed-package smoke verification cover the CLI-only audit over a disposable synthetic repository. The wheel stays below the 500000-byte budget.

[Rules, limitations and privacy](../../AUDIT.md). These tests establish planted-case behavior, not real-world detector performance or proof that an agent's record is truthful.
