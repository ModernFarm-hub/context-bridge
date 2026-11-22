# 0.10.0b1 local verification

Cost-control revision, 2026-11-22, Python 3.9 / macOS. No paid benchmark, personal-library analysis, publication, push, tag, issue or PR.

- Full suite with CI unset: 240 tests, passed; 29 optional skips.
- Full suite with CI=true: 240 tests, passed; 29 optional skips.
- The forty frozen tasks and corpus manifest are byte-for-byte unchanged. All 516 document hashes match; corpus rebuild remains pinned to the original upstream archive hashes. The analysis and cost-helper hashes were registered before any paid run.
- Full fake experiment: 40 Phase A sessions and 240 Phase B sessions, 1080 fake Messages responses. Every request enables automatic ephemeral caching; fake responses contain recorded cache-read and cache-creation counters. Only arithmetic and harness behavior are measured here; the usage values and savings are fabricated.
- Fake pilot exports mean input/output/cache-read/cache-write tokens per call and session, separate phase/arm means, a full-run projection and enforced-ceiling worst case, and mean actual document characters read. Each read remains capped at 12000 characters.
- Decimal budget admission covers cache misses, separate read/write rates and grader prices. Tests cover resume accounting, unfinished-session costs, unknown usage, uncertain charges, request-size limits, preflight dollar stops and unexpected usage above reservation. The fake CLI budget-stop check exits 1, records zero calls, and writes an incomplete, non-qualifying report to both output and requested report destination.
- Wheel: approximately 218 KB, below the enforced 500000-byte budget, with zero corpus files. The source distribution retains all 516 corpus documents. Strict metadata and private/generated payload checks pass.
- Installed-wheel smoke checks pass, including actionable missing-corpus instructions with no benchmark state created. The installed fake pilot succeeds with --corpus-dir pointing to extracted source data.
- Repeat sensitivity uses a single matching pass for thresholds 0.4/0.5/0.6/0.7 and the selected cutoff. Synthetic tests cover zero matches at default with lower-threshold candidates, local review labels, per-threshold precision and coverage, unchanged conservative defaults, and title/date-only output. Controlled vector scores test accounting, not a real embedding model's calibration.

[Full fake summary](../../benchmarks/savings-real-fake.json), [pilot fake summary](../../benchmarks/savings-real-pilot-fake.json), [fake review sheet](../../benchmarks/savings-real-fake-spot-check.csv), [generated report](../../benchmarks/savings-real.md), [protocol and limits](../../benchmarks/savings-real-guide.md).

The dollar cap uses supplied prices and a conservative text-byte/framing bound; it is not an account-wide provider billing limit. No personal repeat-rate measurement or measured paid savings claim is made.
