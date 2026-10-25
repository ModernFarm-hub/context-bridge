# Experimental claim-support checking

This development experiment separates finding a related passage from deciding whether it supports a proposed answer. It is a standalone local checker; it has not been enabled in the session manager, MCP tools, or the downloadable alpha.

The motivating example is a passage saying Maya approves cleanup-job deployments. That passage must not be used to support the claim that Maya approves customer refunds. Search may legitimately retrieve related material; answer support is a separate question.

The latest frozen candidate uses a pinned local DeBERTa model and reaches **24/26 supported claims accepted (92.3%), 0/26 unsupported accepted** on 52 synthetic development cases. All 94 engineering tests pass. Twenty fresh cases remain unreviewed and untested. The original candidate's first validation result remains 80%; later repeats are regression results. The checker is not enabled in MCP or the alpha.

## How it works

The optional, pinned MiniLM or DeBERTa model processes the original passage and one proposed atomic claim. Its upstream label order is contradiction, entailment, neutral. All inference is local; only setup downloads public assets. The model card and configuration are retained beside verified weights. See [the upstream model card](https://huggingface.co/cross-encoder/nli-MiniLM2-L6-H768).

The default cutoff remains 0.90. Round-2 trials of lower cutoffs were rejected after introducing false acceptance; the new candidate uses 0.90. This score is not a calibrated probability that a statement is true.

Results are deliberately limited:

- `model_supported`: the model predicts support within the supplied passage, subject to the guards below. This is not verified truth or proof of permission.
- `not_supported`: the model predicts insufficient information or contradiction. This does not establish that the claim is false in the real world.
- `needs_review`: uncertain, too long, introduces a number/project identifier absent from the passage, or lacks individual-sentence support.

Inputs beyond the 512-token pair window are rejected for review instead of silently truncated. Inputs are bounded to 12,000 passage characters and 2,000 claim characters. The current development candidate groups sentence spans into evidence components using shared identifiers, named tokens and qualified repeated phrases. Generic shared actions alone do not link sentences. Each component is judged by the local model, and a confident whole-context rejection prevents a component from overriding its context. This permits some cross-message joins while checking role mixing. The linking rules are lexical heuristics, not a proof graph, and do not solve general attribution or reasoning.

## Measured result

Twenty assistant-authored synthetic development cases were written before initial inference: eight supported and twelve unsupported claims. Cases include activity mismatch, names, numbers, negation, units, conditions, role swapping, unverified attribution and paraphrases. They are not independent validation or real-user data.

| Measurement | Initial implementation | With sentence consistency |
| --- | ---: | ---: |
| Supported claims accepted | 7/8 (87.5%) | 7/8 (87.5%) |
| Unsupported claims incorrectly accepted | 1/12 | 0/12 |
| Cases passing | 18/20 | 19/20 |
| Acceptance gate | Fail | Fail |

The initial model wrongly accepted “Maya approves refunds” from “Maya approves cleanup deployments. Sam approves refunds.” The sentence consistency check moves that case to review. The remaining missed positive is a paraphrase of a nightly schedule: the model score is below the fixed threshold, so the system abstains.

The overall 19/20 result must not be presented as passing the product's 90% goal: supported-claim acceptance recall is still only 87.5%, and this is a repeatedly inspected development set. The existing harder retrieval-validation result is unchanged. This experiment does not evaluate generated answers, citation use by Claude, or end-to-end retrieval-to-answer quality.

All 72 engineering tests pass with the optional embedding and support assets enabled. Tests cover offline execution, corrupted assets, argument bounds, overlong-input abstention, identifier/number guards and the observed relation errors. Previous runs are retained in `evaluation/claim-support-v1`, `claim-support-v2` and `claim-support-current`.

## Run from development source

Use an environment with the pinned optional dependencies from `prototype/requirements-semantic-lock.txt`:

```sh
python prototype/setup_support.py --directory /absolute/models/nli-MiniLM2-L6-H768
python prototype/evaluate_support.py --model /absolute/models/nli-MiniLM2-L6-H768 --output /absolute/new-claim-report
```

For a single experiment, create a local JSON file containing exactly `passage` and `claim`:

```json
{
  "passage": "Maya must approve cleanup-job changes before deployment.",
  "claim": "Maya must approve customer refunds."
}
```

Then run:

```sh
python prototype/support.py --model /absolute/models/nli-MiniLM2-L6-H768 --input /absolute/example.json
```

This command reads only that explicitly supplied input and model files. It does not search or enroll sessions. Do not pass a whole multi-part answer as a single claim. A model-supported result is limited to the source statement; a synthetic test finding or assistant acknowledgment does not become an independently verified policy.

## Before integration

Collect a separately reviewed development/calibration set and reserve fresh acceptance cases before further tuning. Measure supported-claim recall and unsupported acceptance separately. Include ambiguous names, quoted/negated claims, conditions and cross-message dependencies.

Any future MCP integration must refresh approvals, reread the original record under its owner scope, check its hash, and bind the verdict to those exact source spans. It must invalidate stale/revoked evidence and avoid accepting caller-supplied fabricated excerpts as source evidence. Those checks are required before exposing this standalone model inside the live retrieval workflow; they are not implemented by this experiment.

## Broader review set in progress

A new 60-case synthetic draft reserves 40 development and 20 validation cases across six categories. Supported/unsupported pairs share a split. No inference has run on these new cases; human label review is pending in five-case batches. The initial draft and split manifest are stored locally under `evaluation/claim-review-v1`. Review-required datasets now require an explicit split and completed review of selected cases before model loading. All 77 engineering tests pass. This preparation does not change the measured 87.5% supported-claim recall from the earlier experiment.

## Reviewed development baseline

All 40 development cases have now been confirmed by the user and frozen. The baseline accepts 12/20 supported claims (60%) and no unsupported claims among 20 negatives. Four valid cross-message claims are blocked by the individual-sentence guard; four additional positives are below the fixed model cutoff. The acceptance gate fails. The 20 reserved validation cases remain unreviewed and untested. This broader baseline supersedes the earlier 87.5% figure as the current development measurement; the earlier result is preserved as a smaller-set observation. No inference thresholds or source labels were changed during the baseline run.

## Linked-evidence follow-up

Replacing the blanket individual-sentence rule with linked evidence components improves development recall from 60% to 90%, retaining zero unsupported acceptance among 20 negatives. The 0.90 confidence cutoff and all source labels remain unchanged. Two conflict/precedence positives still abstain. The earlier small suite remains at 87.5% recall without regression. A source snapshot and hashes are stored under `evaluation/claim-review-v1/candidate-linked-v1`; human review of the reserved validation labels is the next step. No validation inference has run.

## First reserved validation run

After all 20 reserved labels were reviewed and frozen, the unchanged source snapshot accepted eight of ten supported claims and none of ten unsupported claims. The gate fails at 80% supported-claim recall. One approved-policy statement scored just below the fixed cutoff; one rollout/schedule join failed the lexical linking guard. No code or threshold was changed during validation. The snapshot and first-run report are preserved under `evaluation/claim-review-v1`. If those failures guide future fixes, treat this set as regression data for those versions and reserve fresh acceptance cases rather than claiming repeated unseen validation.

## Reference and calibration follow-up

The next development iteration adds conservative definite-subject references with ambiguity rejection. On the expanded 52-case development set (40 previously reviewed cases plus 12 assistant-authored probes), it accepts 23/26 supported claims (88.5%) and no unsupported claims among 26 negatives. The former validation set now scores 9/10 supported and 0/10 unsupported accepted; because its errors informed the change, this is regression performance, not fresh validation. Twenty fresh synthetic cases were reserved before code changes and remain unreviewed and untested. All 93 engineering tests pass.

Calibration trials at 0.80, 0.85 and 0.90 did not improve positive recall; the lowest cutoff introduced false acceptance. A paragraph fallback also introduced false acceptance and was removed. The default cutoff remains 0.90. Policy-status reasoning remains unresolved, so no new validation candidate or live integration was promoted. Full development results are under `evaluation/claim-round2/SUMMARY.md`.

## Stronger-model candidate

An additional trusted, pinned `cross-encoder/nli-deberta-v3-base` model is available through `setup_support.py --variant deberta`. At the unchanged 0.90 cutoff it accepts 24/26 supported development claims and no unsupported claims among 26 negatives. The earlier two regression suites show no worsening: 9/10 supported on former validation and 8/8 on the older suite, with zero unsupported acceptance. All 94 engineering tests and 12 MiniLM support-compatibility checks pass. The default MiniLM setup option and live manager remain unchanged.

The new candidate is frozen under `evaluation/claim-round2/candidate-deberta-v2`. Twenty fresh same-author synthetic cases were reserved before code changes and require human label review before inference. Full results and rejected trials are in `evaluation/claim-round2/SUMMARY.md`. No fresh validation or real-user accuracy result exists yet.
