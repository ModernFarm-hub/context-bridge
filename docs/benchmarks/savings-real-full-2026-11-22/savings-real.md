# Realistic research savings benchmark

Measured provider usage on this frozen public corpus only.

This controlled, public-document corpus is not a population estimate. Repeated-question detection measures opportunity, not savings.

| Group | Tasks | Fewer tokens % (95% interval) | Baseline accuracy | Reuse accuracy | Decision accuracy |
|---|---:|---|---:|---:|---:|
| Overall | 40 | -84.33 [-107.63, -64.46] | 0.933 | 0.975 | 0.042 |
| same | 10 | -43.02 [-56.19, -26.37] | 0.9 | 1 | 0 |
| paraphrase | 10 | -88.66 [-157.7, -41.76] | 1 | 1 | 0 |
| related | 10 | -86.89 [-116.65, -54.31] | 0.833 | 0.9 | 0.167 |
| stale | 10 | -118.77 [-159.68, -80.99] | 1 | 1 | 0 |
| REUSE | 20 | -65.84 [-104.11, -40.43] | 0.95 | 1 | 0 |
| CHECK | 10 | -118.77 [-159.68, -80.99] | 1 | 1 | 0 |
| REDO | 10 | -86.89 [-116.65, -54.31] | 0.833 | 0.9 | 0.167 |

Claim eligible: False

Accuracy non-inferiority passed (5-point margin, paired interval): True

Stale safety passed: True

Incomplete tasks: []

Phase B failures: {"baseline": {"cap_reached": 0, "refused": 0, "truncated": 0, "error": 0}, "reuse": {"cap_reached": 0, "refused": 0, "truncated": 0, "error": 0}}

Original research outcomes: {"sessions": 40, "correct": 36, "cap_reached": 0, "refused": 0, "truncated": 0, "error": 0}

Uncached input, cache reads, cache writes and output costs (separate supplied rates): {"A": {"input_tokens": 306, "cache_read_input_tokens": 186360, "cache_creation_input_tokens": 188285, "output_tokens": 18216, "total_input_tokens": 374951, "total_usd": 0.6907565, "input_usd": 0.000612, "cache_read_input_usd": 0.037272, "cache_creation_input_usd": 0.4707125, "output_usd": 0.18216, "abandoned_reserved_usd": 0.0}, "B": {"input_tokens": 1716, "cache_read_input_tokens": 1127089, "cache_creation_input_tokens": 1164602, "output_tokens": 124515, "total_input_tokens": 2293407, "total_usd": 4.4539348, "input_usd": 0.003432, "cache_read_input_usd": 0.2254178, "cache_creation_input_usd": 2.911505, "output_usd": 1.24515, "abandoned_reserved_usd": 0.06843}, "grader": {"input_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "output_tokens": 0, "total_input_tokens": 0, "total_usd": 0.0, "input_usd": 0.0, "cache_read_input_usd": 0.0, "cache_creation_input_usd": 0.0, "output_usd": 0.0, "abandoned_reserved_usd": 0.0}}

Mean document characters read per session: 633.45

Budget: {"max_usd": 10.0, "recorded_usd": 5.1446913, "recorded_response_usd": 5.0762613, "abandoned_reserved_usd": 0.06843, "abandoned_calls": [{"key": "B-research-07-baseline-0-00", "reserved_usd": "0.06843", "who": "Vineeth Ayyat Kochaniyan (run owner), executed by independent tester", "when": "2026-11-23T00:16:02.953687+00:00", "why": "transport read timeout after send; no outcomes inspected", "possibly_billed": true, "never_refunded": true, "retry_key": "B-research-07-baseline-0-00--attempt-1"}], "unresolved_calls": 0, "stop_reason": null, "basis": "Supplied rates, with abandoned reservations permanently charged in full in addition to successful response costs; no assumed cache hits."}

Pilot/full usage observations: {"mean_tokens_per_call": {"input_tokens": 2.766073871409029, "cache_read_input_tokens": 1796.7838577291382, "cache_creation_input_tokens": 1850.734610123119, "output_tokens": 195.25444596443228}, "mean_tokens_per_session": {"input_tokens": 7.2214285714285715, "cache_read_input_tokens": 4690.8892857142855, "cache_creation_input_tokens": 4831.739285714286, "output_tokens": 509.75357142857143}, "grader_mean_tokens_per_call": {"input_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "output_tokens": 0}, "by_phase_arm": {"A-original": {"sessions": 40, "mean_tokens_per_session": {"input_tokens": 7.65, "cache_read_input_tokens": 4659.0, "cache_creation_input_tokens": 4707.125, "output_tokens": 455.4}}, "B-baseline": {"sessions": 120, "mean_tokens_per_session": {"input_tokens": 7.083333333333333, "cache_read_input_tokens": 3242.391666666667, "cache_creation_input_tokens": 3862.3166666666666, "output_tokens": 430.7}}, "B-reuse": {"sessions": 120, "mean_tokens_per_session": {"input_tokens": 7.216666666666667, "cache_read_input_tokens": 6150.016666666666, "cache_creation_input_tokens": 5842.7, "output_tokens": 606.925}}}, "mean_characters_read_per_session": 633.45, "full_run_projected_tokens": {"input_tokens": 2022.0, "cache_read_input_tokens": 1313449.0, "cache_creation_input_tokens": 1352887.0, "output_tokens": 142731.0}, "full_run_estimated_research_usd": 5.0762613, "full_run_estimated_grader_usd": 0.0, "full_run_estimated_usd": 5.0762613, "full_run_worst_case_usd": 8468.8128, "full_run_call_limit": 3360, "notice": "Measured pilot extrapolation by phase/arm, not a guarantee or confidence interval. Grader estimate assumes 240 judgments (no deduplication savings). Fake tokens remain fabricated; use a separate full-run directory."}

Fallback grading: {"overall": {"sessions": 280, "graded_final_answers": 280, "fallback_sessions": 0, "fallback_share": 0.0, "method_not_recorded": 0, "denominator": "Final answers graded by either facts JSON or text fallback; fallback failures included."}, "by_phase_arm": {"A-original": {"sessions": 40, "graded_final_answers": 40, "fallback_sessions": 0, "fallback_share": 0.0, "method_not_recorded": 0, "denominator": "Final answers graded by either facts JSON or text fallback; fallback failures included."}, "B-baseline": {"sessions": 120, "graded_final_answers": 120, "fallback_sessions": 0, "fallback_share": 0.0, "method_not_recorded": 0, "denominator": "Final answers graded by either facts JSON or text fallback; fallback failures included."}, "B-reuse": {"sessions": 120, "graded_final_answers": 120, "fallback_sessions": 0, "fallback_share": 0.0, "method_not_recorded": 0, "denominator": "Final answers graded by either facts JSON or text fallback; fallback failures included."}}}

Decision compliance (separate from decision accuracy): {"applicable_sessions": 120, "compliant": 66, "missing_or_ambiguous": 54, "compliance_rate": 0.55, "notice": "A parsed final-answer decision is compliant even if the decision itself is wrong. Decision accuracy remains separate."}

Reuse loses: ['research-01', 'research-02', 'research-03', 'research-05', 'research-06', 'research-07', 'research-08', 'research-09', 'research-10', 'research-11', 'research-12', 'research-13', 'research-14', 'research-15', 'research-16', 'research-17', 'research-19', 'research-20', 'research-21', 'research-22', 'research-23', 'research-24', 'research-25', 'research-26', 'research-27', 'research-28', 'research-29', 'research-31', 'research-32', 'research-33', 'research-34', 'research-35', 'research-36', 'research-37', 'research-38', 'research-39', 'research-40']

Requested model: claude-sonnet-5-5
Resolved models: ['claude-sonnet-5-5']

## Infrastructure amendment and abandoned requests

Abandon/retry does not by itself disqualify a run. All tasks, arms and repetitions must complete and all existing accuracy/token/safety criteria must pass; abandonments must be disclosed. Unknown abandoned token usage is not invented or substituted into the token metric.

Frozen connect/read timeouts (seconds): 30 / 300.0

Conservatively charged abandoned reservations: USD 0.06843

| Exact attempt key | Permanently charged USD | Who | When (UTC) | Why |
|---|---:|---|---|---|
| B-research-07-baseline-0-00 | 0.06843 | Vineeth Ayyat Kochaniyan (run owner), executed by independent tester | 2026-11-23T00:16:02.953687+00:00 | transport read timeout after send; no outcomes inspected |

These charges remain even if a later response or cheaper retry is recorded. Abandoned token usage is unknown; no token counters are fabricated.
