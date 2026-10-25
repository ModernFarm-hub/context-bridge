# Local retrieval comparison — October 24, 2026

The comparison did not produce a candidate that meets every acceptance gate. No model or cutoff was promoted into the running manager, and the downloadable 0.5.0a1 alpha was not changed.

## What was measured

A new, frozen development set contains 52 synthetic cases: 38 positive retrieval questions, seven negative queries and seven capture/access controls. It includes distinct paraphrases, long mixed-topic records and the earlier development regression cases. The existing 16-case validation set was excluded from model selection.

Three pinned local embedding models were compared with 64- and 200-token windows and model-specific cutoffs. A second round checked an optional lexical gate: incomplete keyword matches must also meet semantic relevance. A local cross-encoder experiment was rejected because it removed too much useful evidence. Its implementation was excluded from development source; its reports and source snapshot remain in the local evaluation directory.

These are the configurations with highest development recall per embedding model, followed by negative-case performance and precision to break ties. These rows illustrate the tradeoff; they are **not accepted release candidates**.

| Model/configuration | Retrieval Recall@5 | Focused-read support recall | Negative queries correctly empty |
| --- | ---: | ---: | ---: |
| MiniLM, 64 tokens, cutoff 0.25, original fusion | 76.3% | 76.3% | 57.1% (4/7) |
| BGE small, 64 tokens, cutoff 0.50, lexical gate | 100% | 100% | 57.1% (4/7) |
| E5 small, 64 tokens, cutoff 0.76, lexical gate | 94.7% | 94.7% | 71.4% (5/7) |

At a permissive setting, a question about rotating encryption keys could retrieve a passage about rotating a slide. Raising the similarity threshold also removed valid paraphrases. The tested passage checker reached 100% negative-case rejection but only 34.2% positive recall. A higher recall alone does not meet our target.

All tested access/isolation/revocation controls passed in the valid comparison runs. Original source locators and read spans remained valid. These are local fixture checks, not an identity-security audit. One repetition per development configuration was used for selection; repetition does not add independent questions.

## Validation and regression status

The selection procedure requires all controls and negatives to pass, valid search/read provenance, no focused-read errors, and both retrieval and read recall at least 90% before freezing a candidate. No configuration qualified, so no new candidate was run on the frozen harder validation set. Its previous measured result remains 66.7%; we cannot claim it improved.

The existing MiniLM default was rerun against the original benchmark after these changes: **30/30 scenarios, 100% retrieval and read recall, acceptance passed**. All **58 engineering tests passed**, including actual offline model inference. The same test suite also passed with BGE and E5 during this comparison.

The malformed early harness run is preserved separately as `model-comparison-harness-error`; its execution failures are excluded from model-quality comparisons.

## Reproduce from development source

Use a Python environment with the pinned optional dependencies in `prototype/requirements-semantic-lock.txt`. Run from this project directory, substituting your environment's Python and an empty report directory:

```sh
python prototype/setup_semantic.py --model minilm --directory /absolute/models/all-MiniLM-L6-v2
python prototype/setup_semantic.py --model bge-small --directory /absolute/models/bge-small-en-v1.5
python prototype/setup_semantic.py --model e5-small --directory /absolute/models/e5-small-v2
python prototype/select_retrieval.py --models-root /absolute/models --output /absolute/reports/comparison --gate-lexical
python prototype/select_retrieval.py --models-root /absolute/models --output /absolute/reports/e5 --gate-lexical --e5-only
```

Only setup downloads public assets. Inference uses local files, and all evaluation conversations are synthetic. Model weights, model revisions, integrity hashes, pooling and query/passage prefixes are explicitly specified in `setup_semantic.py`. No third-party executable model code is loaded.

The selection command refuses to overwrite a nonempty output directory. Exit status 1 means no qualifying development candidate; it is an intended failed quality gate. If a future candidate qualifies, settings and dataset/code fingerprints are saved before validation, and both existing evaluation sets run three times. `evaluate.py --retrieval-config /absolute/selected-settings.json` reproduces a frozen configuration. `configure_semantic.py --retrieval-config ...` can explicitly install qualified settings without changing source approvals. No configuration file is generated or installed as an accepted candidate for this experiment.

## Next work

1. Add sentence/paragraph-aligned passages and measure evidence crossing window boundaries. Keep exact original offsets and hashes.
2. Add manually labeled, harmless real-work questions and plausible distractors. Reserve a fresh acceptance set before another tuning round; synthetic results alone cannot demonstrate usefulness.
3. Evaluate relevance/abstention separately from finding a related topic. Preserve the existing hard negatives, including the encryption-key/slide example.
4. Only package an upgrade after the frozen candidate passes recall, passage support, negative-case and access gates. Generated-answer correctness remains a separate future evaluation.
