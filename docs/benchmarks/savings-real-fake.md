# Realistic research savings benchmark

FAKE provider fixtures: no measured savings claim.

This controlled, public-document corpus is not a population estimate. Repeated-question detection measures opportunity, not savings.

| Group | Tasks | Fewer tokens % (95% interval) | Baseline accuracy | Reuse accuracy | Decision accuracy |
|---|---:|---|---:|---:|---:|
| Overall | 40 | 1.79 [-6.7, 10.28] | 1 | 1 | 1 |
| same | 10 | 18.77 [18.77, 18.77] | 1 | 1 | 1 |
| paraphrase | 10 | 18.77 [18.77, 18.77] | 1 | 1 | 1 |
| related | 10 | -49.14 [-49.14, -49.14] | 1 | 1 | 1 |
| stale | 10 | 18.77 [18.77, 18.77] | 1 | 1 | 1 |
| REUSE | 20 | 18.77 [18.77, 18.77] | 1 | 1 | 1 |
| CHECK | 10 | 18.77 [18.77, 18.77] | 1 | 1 | 1 |
| REDO | 10 | -49.14 [-49.14, -49.14] | 1 | 1 | 1 |

Claim eligible: False

Accuracy non-inferiority passed (5-point margin, paired interval): True

Stale safety passed: True

Incomplete tasks: []

Phase B failures: {"baseline": {"cap_reached": 0, "refused": 0, "truncated": 0, "error": 0}, "reuse": {"cap_reached": 0, "refused": 0, "truncated": 0, "error": 0}}

Original research outcomes: {"sessions": 40, "correct": 40, "cap_reached": 0, "refused": 0, "truncated": 0, "error": 0}

Uncached input, cache reads, cache writes and output costs (separate supplied rates): {"A": {"input_tokens": 12000, "cache_read_input_tokens": 1360, "cache_creation_input_tokens": 440, "output_tokens": 2400, "total_input_tokens": 13800, "total_usd": 0.049372, "input_usd": 0.024, "cache_read_input_usd": 0.000272, "cache_creation_input_usd": 0.0011, "output_usd": 0.024}, "B": {"input_tokens": 65250, "cache_read_input_tokens": 12240, "cache_creation_input_tokens": 2640, "output_tokens": 16200, "total_input_tokens": 80130, "total_usd": 0.301548, "input_usd": 0.1305, "cache_read_input_usd": 0.002448, "cache_creation_input_usd": 0.0066, "output_usd": 0.162}, "grader": {"input_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "output_tokens": 0, "total_input_tokens": 0, "total_usd": 0.0, "input_usd": 0.0, "cache_read_input_usd": 0.0, "cache_creation_input_usd": 0.0, "output_usd": 0.0}}

Mean document characters read per session: 20020.52857142857

Budget: {"max_usd": 10.0, "recorded_usd": 0.35092, "unresolved_calls": 0, "stop_reason": null, "basis": "Supplied rates; conservative text-byte plus framing reservations, no assumed cache hits. Not an external billing-service limit."}

Pilot/full usage observations: {"mean_tokens_per_call": {"input_tokens": 71.52777777777777, "cache_read_input_tokens": 12.592592592592593, "cache_creation_input_tokens": 2.8518518518518516, "output_tokens": 17.22222222222222}, "mean_tokens_per_session": {"input_tokens": 275.89285714285717, "cache_read_input_tokens": 48.57142857142857, "cache_creation_input_tokens": 11.0, "output_tokens": 66.42857142857143}, "grader_mean_tokens_per_call": {"input_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "output_tokens": 0}, "by_phase_arm": {"A-original": {"sessions": 40, "mean_tokens_per_session": {"input_tokens": 300.0, "cache_read_input_tokens": 34.0, "cache_creation_input_tokens": 11.0, "output_tokens": 60.0}}, "B-baseline": {"sessions": 120, "mean_tokens_per_session": {"input_tokens": 300.0, "cache_read_input_tokens": 34.0, "cache_creation_input_tokens": 11.0, "output_tokens": 60.0}}, "B-reuse": {"sessions": 120, "mean_tokens_per_session": {"input_tokens": 243.75, "cache_read_input_tokens": 68.0, "cache_creation_input_tokens": 11.0, "output_tokens": 75.0}}}, "mean_characters_read_per_session": 20020.52857142857, "full_run_projected_tokens": {"input_tokens": 77250.0, "cache_read_input_tokens": 13600.0, "cache_creation_input_tokens": 3080.0, "output_tokens": 18600.0}, "full_run_estimated_research_usd": 0.35092, "full_run_estimated_grader_usd": 0.0, "full_run_estimated_usd": 0.35092, "full_run_worst_case_usd": 8468.8128, "full_run_call_limit": 3360, "notice": "Measured pilot extrapolation by phase/arm, not a guarantee or confidence interval. Grader estimate assumes 240 judgments (no deduplication savings). Fake tokens remain fabricated; use a separate full-run directory."}

Reuse loses: ['research-21', 'research-22', 'research-23', 'research-24', 'research-25', 'research-26', 'research-27', 'research-28', 'research-29', 'research-30']

Requested model: claude-sonnet-5-5
Resolved models: ['FAKE-NOT-A-MEASUREMENT']
