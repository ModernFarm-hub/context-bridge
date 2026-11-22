# Pilot regrading: 2026-11-22-formatting-only

Reason: pilot found formatting-only false negatives. No new API calls.

Source: savings-real-pilot-2026-11-22. The original artifacts remain unchanged. This five-task pilot is exploratory, not a qualifying result.

| Phase | Task | Arm | Correct before | Correct after | Grading method | Decision before | Decision after | Compliant before → after | Tokens | Calls |
|---|---|---|---|---|---|---|---|---|---:|---:|
| A | research-01 | original | True | True | facts_json | None | None | None → None | 19262 | 4 |
| A | research-11 | original | False | True | facts_json | None | None | None → None | 8544 | 3 |
| A | research-21 | original | False | True | facts_json | None | None | None → None | 3461 | 2 |
| A | research-31 | original | True | True | facts_json | None | None | None → None | 8485 | 3 |
| A | research-40 | original | True | True | facts_json | None | None | None → None | 7806 | 3 |
| B | research-21 | reuse | False | True | facts_json | None | REUSE | False → True | 13269 | 3 |
| B | research-11 | reuse | False | True | facts_json | CHECK | CHECK | True → True | 13095 | 3 |
| B | research-01 | baseline | True | True | facts_json | None | None | None → None | 11505 | 3 |
| B | research-11 | baseline | True | True | facts_json | None | None | None → None | 8226 | 3 |
| B | research-40 | reuse | True | True | facts_json | REDO | REDO | True → True | 14384 | 3 |
| B | research-31 | reuse | True | True | facts_json | None | None | False → False | 24087 | 4 |
| B | research-40 | baseline | True | True | facts_json | None | None | None → None | 7664 | 3 |
| B | research-21 | baseline | False | True | facts_json | None | None | None → None | 3426 | 2 |
| B | research-01 | reuse | True | True | facts_json | None | None | False → False | 9213 | 2 |
| B | research-31 | baseline | True | True | facts_json | None | None | None → None | 8897 | 3 |

Correctness changes: 5

Fallback: {"overall": {"sessions": 15, "graded_final_answers": 15, "fallback_sessions": 0, "fallback_share": 0.0, "method_not_recorded": 0, "denominator": "Final answers graded by either facts JSON or text fallback; fallback failures included."}, "by_phase_arm": {"A-original": {"sessions": 5, "graded_final_answers": 5, "fallback_sessions": 0, "fallback_share": 0.0, "method_not_recorded": 0, "denominator": "Final answers graded by either facts JSON or text fallback; fallback failures included."}, "B-baseline": {"sessions": 5, "graded_final_answers": 5, "fallback_sessions": 0, "fallback_share": 0.0, "method_not_recorded": 0, "denominator": "Final answers graded by either facts JSON or text fallback; fallback failures included."}, "B-reuse": {"sessions": 5, "graded_final_answers": 5, "fallback_sessions": 0, "fallback_share": 0.0, "method_not_recorded": 0, "denominator": "Final answers graded by either facts JSON or text fallback; fallback failures included."}}}

Decision compliance: {"applicable_sessions": 5, "compliant": 3, "missing_or_ambiguous": 2, "compliance_rate": 0.6, "notice": "A parsed final-answer decision is compliant even if the decision itself is wrong. Decision accuracy remains separate."}

Decision accuracy (distinct from compliance): 0

| Task | Baseline tokens | Reuse tokens | Ratio | Baseline calls | Reuse calls |
|---|---:|---:|---:|---:|---:|
| research-01 | 11505 | 9213 | 0.8008 | 3 | 2 |
| research-11 | 8226 | 13095 | 1.5919 | 3 | 3 |
| research-21 | 3426 | 13269 | 3.873 | 2 | 3 |
| research-31 | 8897 | 24087 | 2.7073 | 3 | 4 |
| research-40 | 7664 | 14384 | 1.8768 | 3 | 3 |

Reuse used more tokens in 4 of 5 tasks. These are documentation lookups; deeper research is a separate future question.

Each session retains its original usage and call count. No task, corpus, arm, call cap, metric formula, bootstrap setting or threshold changed.

A colon after a decision is now accepted. A period followed by prose remains unsupported under the specified separators. All saved final answers in this pilot contain facts JSON; its observed fallback share is zero. A separately labelled prose-only regression fixture tests the new fallback without claiming it occurred in these saved finals.

Source artifact SHA-256 hashes: {"raw-calls.jsonl": "5c0de0c01b76d85f1dbafbdd390475ec0563ec87fcec6a230f6c361c127e0304", "results.jsonl": "cc8a0f7493d90107c021dbab9f02857d9aa1c77f97142d582bddab1446dec3ae", "run.json": "5dd03d70ab2e9731126f4cce2c0a02590c2c7edc5f0105741c33a1ce9498a15a", "summary.json": "9bdd7b83b1a2565b1b99d56ec213a4c32cb2eb03e502c92146ff1ce48f30b624"}
