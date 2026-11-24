# 0.11.0a3 synthetic verification

Experimental reason-evidence infrastructure, verified locally on Python 3.9 / macOS. No real conversation library, repository history, evaluation answers, employer/client/pilot data or model calls were used. No explanation-quality claim is made. No tag, push, publication, issue or PR.

- Full regression suite: 296 tests with CI unset and CI=true, 29 optional skips each.
- Six new synthetic tests cover redacted full commit body and author date; substantive origin plus short approvals without unrelated blocks; decision prose priority; fixed edit/test/build/commit/CI summaries without raw commands or logs; committed-line blame and latest-path resolution on MCP/CLI; outside/symlink path refusal; range/since/path filtering, newest-ten cap and shared total response budget; counts-only self-report output; and git baseline context without session evidence.
- Report fixtures check exact counts/line percentage and absence of prompts, identifiers, file names, paths and session information. The report is not listed or callable as an MCP tool.
- Existing matcher determinism, human-commit abstention, approval/exclusion/deletion filters, active append/rewrite/revocation handling, thousand-file diffstat caps and 2048/6000/12000 serialized tool-result budget fixtures remain in the suite.
- Wheel/sdist payload checks, strict metadata validation and an installed console/MCP smoke test cover opt-in context_trace and its structured git context. The wheel remains below the 500000-byte budget.

[Method, queries, data boundary and limitations](../../TRACE.md). This release supplies evidence and an evaluation workflow; it does not establish that an AI explanation is correct or better than a git-only answer.

File-reservation correction: three additional synthetic fixtures verify a 600-file commit with an exactly 4,000-character message and long selected turns retains the top five files plus totals at 2048/6000/12000 serialized tool-result budgets; small commits retain their complete message, origin and file list; and extreme file-name metadata reports explicit budget omissions. No real-data verification output was used.
