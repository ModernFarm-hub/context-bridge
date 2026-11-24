# 0.11.0a2 synthetic verification

Experimental opt-in MCP evidence and short-answer evaluation infrastructure, verified locally on Python 3.9 / macOS. No real conversation library, real repository history, real ratings, employer/client/pilot data, model requests or paid runs were used. No explanation-quality claim is made. No tag, push, publication, issue or PR.

- Full regression suite: 287 tests pass with CI unset and CI=true; 29 optional skips in each run.
- Nine new tests use invented repositories/transcripts and an in-memory JSON-RPC client. They verify disabled listing/calling, enable/disable and profile isolation, selected-turn-only text, no titles or absolute paths, credentials/email filtering, sensitive-turn withholding, request-first budgets, diffstat without diff content, abstention, ambiguous runner-up selection, opt-in revocation, and the same candidate/confidence/evidence/segment references as CLI trace.
- A synthetic prompt-injection sentence is returned as JSON data with an untrusted-evidence notice; no source command or instruction is executed.
- AI evaluation tests cover deterministic linked-only sampling, default ten-commit CLI routing, four local ratings, private text-free rating storage outside the repository, interruption, no-link handling and paired means/invented-reason/privacy counts. Reports are labelled one person's judgments on one repository.
- Existing synthetic range-independence, append/rewrite/revocation, human-commit abstention, scoping and read-only tests remain in the regression suite.
- Wheel/sdist payload checks, strict metadata checks and an installed console/MCP smoke test include enabling/calling/disabling context_trace over a disposable synthetic repository. The wheel remains below the 500000-byte budget.

[Method, data boundary and evaluation instructions](../../TRACE.md). A real short-answer evaluation has not been performed; this release supplies the workflow rather than evidence of its quality.

Response-bound correction: a synthetic thousand-file commit and a long, heavily JSON-escaped selected segment remain within 2048/6000/12000-character serialized tool-result budgets. An actual in-memory stdio protocol call checks the complete MCP result and its text content. Diffstats rank at most 20 files and retain exact whole-commit totals and omitted counts. Active append during formatting returns precisely the snapshot result; rewriting, truncating, deleting, excluding, withdrawing approval or changing trace settings fails closed. All examples, files and labels remain invented; no real verification data was used.
