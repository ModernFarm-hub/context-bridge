# 0.10.0b1 local verification

Historical cost-control verification, 2026-11-22, Python 3.9 / macOS. That verification made no paid calls or personal-library analysis. An independent real pilot was subsequently supplied; its grading amendment is documented below. No publication, push, tag, issue or PR.

- Full suite with CI unset: 240 tests, passed; 29 optional skips.
- Full suite with CI=true: 240 tests, passed; 29 optional skips.
- The forty frozen tasks and corpus manifest are byte-for-byte unchanged. All 516 document hashes match; corpus rebuild remains pinned to the original upstream archive hashes. The analysis and cost-helper hashes were registered before any paid run.
- Full fake experiment: 40 Phase A sessions and 240 Phase B sessions, 1080 fake Messages responses. Every request enables automatic ephemeral caching; fake responses contain recorded cache-read and cache-creation counters. Only arithmetic and harness behavior are measured here; the usage values and savings are fabricated.
- Fake pilot exports mean input/output/cache-read/cache-write tokens per call and session, separate phase/arm means, a full-run projection and enforced-ceiling worst case, and mean actual document characters read. Each read remains capped at 12000 characters.
- Decimal budget admission covers cache misses, separate read/write rates and grader prices. Tests cover resume accounting, unfinished-session costs, unknown usage, uncertain charges, request-size limits, preflight dollar stops and unexpected usage above reservation. The fake CLI budget-stop check exits 1, records zero calls, and writes an incomplete, non-qualifying report to both output and requested report destination.
- Wheel: approximately 218 KB, below the enforced 500000-byte budget, with zero corpus files. The source distribution retains all 516 corpus documents. Strict metadata and private/generated payload checks pass.
- Installed-wheel smoke checks pass, including actionable missing-corpus instructions with no benchmark state created. The installed fake pilot succeeds with --corpus-dir pointing to extracted source data.
- Repeat sensitivity uses a single matching pass for thresholds 0.4/0.5/0.6/0.7 and the selected cutoff. Synthetic tests cover zero matches at default with lower-threshold candidates, local review labels, per-threshold precision and coverage, unchanged conservative defaults, and title/date-only output. Controlled vector scores test accounting, not a real embedding model's calibration.

[Full fake summary](../../benchmarks/savings-real-fake.json), [pilot fake summary](../../benchmarks/savings-real-pilot-fake.json), [fake review sheet](../../benchmarks/savings-real-fake-spot-check.csv), [generated fake report](../../benchmarks/savings-real-fake.md), [protocol and limits](../../benchmarks/savings-real-guide.md).

The dollar cap uses supplied prices and a conservative text-byte/framing bound; it is not an account-wide provider billing limit. No personal repeat-rate measurement or measured paid savings claim is made.

## Post-pilot formatting amendment, 2026-11-22

Reason: **pilot found formatting-only false negatives**. The analysis, deterministic grader, decision parser and offline regrader are re-registered in [the amendment](../../../prototype/evals/savings-real/PREREGISTRATION.md). The secondary model-grader rubric is unchanged; no secondary model grading was invoked.

- 246 tests pass both with CI unset and CI=true (29 optional skips). New fixtures cover real pilot JSON and labelled prose excerpts, module suffixes/booleans/quotes, wrong identifiers, negation, swapped fields, separate fallback and compliance reporting, and provider-free regrading.
- Original analysis statements and metric expressions, token/bootstrap functions, neutral prompt, research tools, balanced guide and model constants were compared structurally and are unchanged. Frozen task and corpus hashes are unchanged.
- Fifteen real pilot sessions were regraded using only saved responses. Final text, usage and call counts were cross-checked against raw calls. Five correctness labels change; correctness is 10/15 → 15/15. The independent pilot source files remain unchanged; no library was read or regenerated and no new API calls occurred.
- Decision compliance is 2/5 → 3/5, independently of decision accuracy (0/5). Two period-form markers remain unsupported. All saved final answers have facts JSON: observed fallback use is 0/15; prose-only fixtures are clearly labelled excerpts.
- Reuse used more tokens in four of five comparisons. The documentation lookup sessions were short; ZIP is a higher-token exception to the approximate 3–9k range. Deeper research is a separate future question, not a claim supported by this pilot.
- The new before/after sidecars are scanned for local absolute paths and keys. The task corpus, labels, arms, call caps, metric formulas and thresholds are unchanged. The pilot remains exploratory and non-qualifying.

[Per-session before/after report](../../benchmarks/savings-real-pilot-2026-11-22-regrade/regrade.md) · [JSON sidecar](../../benchmarks/savings-real-pilot-2026-11-22-regrade/regrade.json) · [Pilot interpretation](../../benchmarks/savings-real-guide.md#independent-real-pilot-and-formatting-amendment-2026-11-22).

## Outcome-blind transport amendment, 2026-11-22

No partial results from the reported full run were opened or analyzed. The actual run directory was not inspected, abandoned, migrated or resumed; no paid/API calls were made. Source commit 0d0bec6 was inspected only as code to register its exact legacy runner hash.

- 257 tests pass with CI unset and CI=true (29 optional skips). All new transport tests use fake TLS connections or disposable synthetic runs.
- Tests cover: pre-send connect failure with one automatic retry; send/read errors remaining unresolved; both-connect-fail zero charge; exact-key abandonment with who/time/reason; permanent reservation charge after restart and even a late response; deterministic --attempt-1 resend and tool-result replay; no third send; refusal to abandon received responses; carried charges enforcing the unchanged dollar/global caps.
- Metadata-only legacy adoption preserves original run.json bytes and refuses protected hash changes, altered experiment configuration or a later timeout change. Offline maintenance is tested with outcome-file reads and provider construction blocked.
- Completed full synthetic analysis still qualifies under its original rules when abandonment is disclosed; an incomplete arm/repetition does not. No analysis/grading formulas or thresholds were edited.
- Entire task, corpus manifest, analysis, grader, cost and policy files are byte-identical to the pre-amendment source. Prompt and library-construction functions are unchanged. Session logic adds only physical-attempt cap accounting, so an abandoned send plus resend cannot exceed the existing per-session cap; grading and Message bodies remain unchanged.
- Reports distinguish received-response dollars from permanently charged abandoned reservations. Unknown abandoned token counts are not invented. The original frozen caps remain in force.

[Infrastructure amendment](../../../prototype/evals/savings-real/PREREGISTRATION.md#2026-11-22-outcome-blind-infrastructure-amendment) · [Offline recovery instructions](../../benchmarks/savings-real-guide.md#outcome-blind-infrastructure-amendment-2026-11-22).
