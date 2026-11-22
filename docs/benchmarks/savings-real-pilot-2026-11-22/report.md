# Realistic research savings benchmark

Measured provider usage on this frozen public corpus only.

This controlled, public-document corpus is not a population estimate. Repeated-question detection measures opportunity, not savings.

| Group | Tasks | Fewer tokens % (95% interval) | Baseline accuracy | Reuse accuracy | Decision accuracy |
|---|---:|---|---:|---:|---:|
| Overall | 5 | -117.0 [-217.36, -33.24] | 0.8 | 0.6 | 0 |
| same | 1 | 19.92 [19.92, 19.92] | 1 | 1 | 0 |
| paraphrase | 1 | -59.19 [-59.19, -59.19] | 1 | 0 | 0 |
| related | 1 | -287.3 [-287.3, -287.3] | 0 | 0 | 0 |
| stale | 2 | -129.21 [-170.73, -87.68] | 1 | 1 | 0 |
| REUSE | 2 | -19.63 [-59.19, 19.92] | 1 | 0.5 | 0 |
| CHECK | 2 | -129.21 [-170.73, -87.68] | 1 | 1 | 0 |
| REDO | 1 | -287.3 [-287.3, -287.3] | 0 | 0 | 0 |

Claim eligible: False

Accuracy non-inferiority passed (5-point margin, paired interval): False

Stale safety passed: True

Incomplete tasks: []

Phase B failures: {"baseline": {"cap_reached": 0, "refused": 0, "truncated": 0, "error": 0}, "reuse": {"cap_reached": 0, "refused": 0, "truncated": 0, "error": 0}}

Original research outcomes: {"sessions": 5, "correct": 3, "cap_reached": 0, "refused": 0, "truncated": 0, "error": 0}

Uncached input, cache reads, cache writes and output costs (separate supplied rates): {"A": {"input_tokens": 40, "cache_read_input_tokens": 22322, "cache_creation_input_tokens": 22697, "output_tokens": 2499, "total_input_tokens": 45059, "total_usd": 0.0862769, "input_usd": 8e-05, "cache_read_input_usd": 0.0044644, "cache_creation_input_usd": 0.0567425, "output_usd": 0.02499}, "B": {"input_tokens": 78, "cache_read_input_tokens": 53394, "cache_creation_input_tokens": 54994, "output_tokens": 5300, "total_input_tokens": 108466, "total_usd": 0.2013198, "input_usd": 0.000156, "cache_read_input_usd": 0.0106788, "cache_creation_input_usd": 0.137485, "output_usd": 0.053}, "grader": {"input_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "output_tokens": 0, "total_input_tokens": 0, "total_usd": 0.0, "input_usd": 0.0, "cache_read_input_usd": 0.0, "cache_creation_input_usd": 0.0, "output_usd": 0.0}}

Mean document characters read per session: 673.4

Budget: {"max_usd": 5.0, "recorded_usd": 0.2875967, "unresolved_calls": 0, "stop_reason": null, "basis": "Supplied rates; conservative text-byte plus framing reservations, no assumed cache hits. Not an external billing-service limit."}

Pilot/full usage observations: {"mean_tokens_per_call": {"input_tokens": 2.6818181818181817, "cache_read_input_tokens": 1720.8181818181818, "cache_creation_input_tokens": 1765.7045454545455, "output_tokens": 177.25}, "mean_tokens_per_session": {"input_tokens": 7.866666666666666, "cache_read_input_tokens": 5047.733333333334, "cache_creation_input_tokens": 5179.4, "output_tokens": 519.9333333333333}, "grader_mean_tokens_per_call": {"input_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "output_tokens": 0}, "by_phase_arm": {"A-original": {"sessions": 5, "mean_tokens_per_session": {"input_tokens": 8.0, "cache_read_input_tokens": 4464.4, "cache_creation_input_tokens": 4539.4, "output_tokens": 499.8}}, "B-baseline": {"sessions": 5, "mean_tokens_per_session": {"input_tokens": 7.6, "cache_read_input_tokens": 3411.0, "cache_creation_input_tokens": 4110.4, "output_tokens": 414.6}}, "B-reuse": {"sessions": 5, "mean_tokens_per_session": {"input_tokens": 8.0, "cache_read_input_tokens": 7267.8, "cache_creation_input_tokens": 6888.4, "output_tokens": 645.4}}}, "mean_characters_read_per_session": 673.4, "full_run_projected_tokens": {"input_tokens": 2192.0, "cache_read_input_tokens": 1460032.0, "cache_creation_input_tokens": 1501432.0, "output_tokens": 147192.0}, "full_run_estimated_research_usd": 5.5218904, "full_run_estimated_grader_usd": 0.0, "full_run_estimated_usd": 5.5218904, "full_run_worst_case_usd": 8468.8128, "full_run_call_limit": 3360, "notice": "Measured pilot extrapolation by phase/arm, not a guarantee or confidence interval. Grader estimate assumes 240 judgments (no deduplication savings). Fake tokens remain fabricated; use a separate full-run directory."}

Reuse loses: ['research-11', 'research-21', 'research-31', 'research-40']

Requested model: claude-sonnet-5-5
Resolved models: ['claude-sonnet-5-5']
